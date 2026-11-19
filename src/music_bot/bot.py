"""Guild-scoped slash commands and lifecycle management."""

import asyncio
import logging

import discord
from discord import app_commands

from .config import Settings
from .media import Media
from .player import Player


async def sync_commands(tree, guild_id: int):
    """Replace this application's legacy globals and target-guild commands once on login."""
    guild = discord.Object(id=guild_id)
    tree.copy_global_to(guild=guild)
    tree.clear_commands(guild=None)
    await tree.sync()  # Remove legacy globals (including /dio).
    await tree.sync(guild=guild)  # Replace guild commands; no duplicate global scope.


class MusicBot(discord.Client):
    def __init__(self, settings: Settings):
        super().__init__(
            intents=discord.Intents.default(),
            activity=discord.Game(name="Ready to play music"),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.tree = app_commands.CommandTree(self)
        self.media = Media(settings.max_duration)
        self.players: dict[int, Player] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.register_commands()
        self.tree.error(self.on_command_error)

    async def setup_hook(self):
        await sync_commands(self.tree, self.settings.guild_id)
        logging.getLogger(__name__).info("Guild commands synchronized")

    async def close(self):
        await asyncio.gather(*(p.close() for p in list(self.players.values())))
        await super().close()

    def player(self, interaction):
        if not interaction.guild or interaction.guild.id != self.settings.guild_id:
            raise ValueError("This bot is restricted to its configured server.")
        voice = getattr(interaction.user, "voice", None)
        if not voice or not voice.channel:
            raise ValueError("Join a voice channel first.")
        player = self.players.get(interaction.guild.id)
        if player and not player.closed and player.voice.is_connected():
            if player.voice.channel.id != voice.channel.id:
                raise ValueError("Join the bot's voice channel to control playback.")
            return player
        return None

    async def connect(self, interaction):
        player = self.player(interaction)
        if player:
            return player
        old = self.players.pop(interaction.guild.id, None)
        if old:
            await old.close()
        voice = interaction.guild.voice_client
        if voice:
            await voice.disconnect(force=True)
        voice = await interaction.user.voice.channel.connect(self_deaf=True)
        player = Player(
            voice,
            interaction.channel,
            self.media,
            self.settings.idle_timeout,
            self.settings.queue_limit,
        )
        self.players[interaction.guild.id] = player
        return player

    async def on_command_error(self, interaction, error):
        cause = getattr(error, "original", error)
        message = (
            str(cause)
            if isinstance(cause, ValueError)
            else ("The command failed. Check voice permissions and try again.")
        )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    def register_commands(self):
        @self.tree.command(description="Join your voice channel")
        @app_commands.guild_only()
        async def join(interaction: discord.Interaction):
            self.player(interaction)
            await interaction.response.defer()
            async with self.locks.setdefault(interaction.guild.id, asyncio.Lock()):
                await self.connect(interaction)
            await interaction.followup.send("Connected to your voice channel.")

        @self.tree.command(description="Play a YouTube URL or search for a track")
        @app_commands.guild_only()
        @app_commands.describe(query="YouTube URL or search terms")
        async def play(interaction: discord.Interaction, query: str):
            self.player(interaction)
            await interaction.response.defer()
            async with self.locks.setdefault(interaction.guild.id, asyncio.Lock()):
                track = await self.media.resolve(query)
                player = await self.connect(interaction)
                try:
                    player.queue.put_nowait(track)
                except asyncio.QueueFull:
                    raise ValueError(
                        "The queue is full. Try again after a track finishes."
                    ) from None
            await interaction.followup.send(
                f"Queued: {discord.utils.escape_markdown(track.title)}",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        @self.tree.command(description="Skip the currently playing track")
        @app_commands.guild_only()
        async def skip(interaction: discord.Interaction):
            player = self.player(interaction)
            if not player or not (player.voice.is_playing() or player.voice.is_paused()):
                raise ValueError("No track is playing yet.")
            player.voice.stop()
            await interaction.response.send_message("Skipped the current track.")

        @self.tree.command(description="Pause playback")
        @app_commands.guild_only()
        async def pause(interaction: discord.Interaction):
            player = self.player(interaction)
            if not player or not player.voice.is_playing():
                raise ValueError("Nothing is playing.")
            player.voice.pause()
            await interaction.response.send_message("Playback paused.")

        @self.tree.command(description="Resume paused playback")
        @app_commands.guild_only()
        async def resume(interaction: discord.Interaction):
            player = self.player(interaction)
            if not player or not player.voice.is_paused():
                raise ValueError("Playback is not paused.")
            player.voice.resume()
            await interaction.response.send_message("Playback resumed.")

        async def disconnect(interaction):
            self.player(interaction)
            await interaction.response.defer()
            async with self.locks.setdefault(interaction.guild.id, asyncio.Lock()):
                player = self.player(interaction)
                if player:
                    await player.close()
                    self.players.pop(interaction.guild.id, None)
            await interaction.followup.send("Playback stopped, queue cleared, and disconnected.")

        @self.tree.command(description="Stop playback, clear the queue, and disconnect")
        @app_commands.guild_only()
        async def stop(interaction: discord.Interaction):
            await disconnect(interaction)

        @self.tree.command(description="Leave your voice channel and clear the queue")
        @app_commands.guild_only()
        async def leave(interaction: discord.Interaction):
            await disconnect(interaction)

        @self.tree.command(name="queue", description="Show the current track and queue")
        @app_commands.guild_only()
        async def show_queue(interaction: discord.Interaction):
            player = self.player(interaction)
            if not player:
                raise ValueError("No active player.")
            title = player.current.title if player.current else "Nothing"
            await interaction.response.send_message(
                f"Current: {discord.utils.escape_markdown(title)}\n"
                f"Waiting tracks: {player.queue.qsize()}",
                ephemeral=True,
            )
