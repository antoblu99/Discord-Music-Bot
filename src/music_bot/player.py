"""One playback worker and one inactivity timeout per guild."""

import asyncio
import contextlib
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import discord

from .media import Media, Track

log = logging.getLogger(__name__)


class Player:
    def __init__(self, voice, channel, media: Media, timeout: int, limit: int):
        self.voice = voice
        self.channel = channel
        self.media = media
        self.timeout = timeout
        self.queue: asyncio.Queue[Track] = asyncio.Queue(maxsize=limit)
        self.current: Track | None = None
        self.closed = False
        self.task = asyncio.create_task(self.run())

    async def notify(self, message: str):
        with contextlib.suppress(discord.HTTPException):
            await self.channel.send(message, allowed_mentions=discord.AllowedMentions.none())

    async def run(self):
        try:
            while True:
                try:
                    track = await asyncio.wait_for(self.queue.get(), timeout=self.timeout)
                except TimeoutError:
                    await self.notify("Disconnected due to inactivity.")
                    return
                self.current = track
                try:
                    with TemporaryDirectory(prefix="music-bot-") as directory:
                        path = await self.media.download(track, Path(directory))
                        if not self.voice.is_connected():
                            return
                        loop = asyncio.get_running_loop()
                        finished = loop.create_future()

                        def complete(error, finished=finished):
                            if not finished.done():
                                finished.set_result(error)

                        def after(error, loop=loop, complete=complete):
                            loop.call_soon_threadsafe(complete, error)

                        source = discord.FFmpegPCMAudio(str(path), options="-vn")
                        try:
                            self.voice.play(source, after=after)
                            await self.notify(
                                f"Now playing: {discord.utils.escape_markdown(track.title)}"
                            )
                            error = await finished
                            if error:
                                await self.notify("Playback failed. Moving to the next track.")
                        finally:
                            self.voice.stop()
                            source.cleanup()
                except Exception:
                    # Extractor errors may contain sensitive URLs; keep them out of logs/chat.
                    log.warning("Track playback failed")
                    await self.notify("Unable to play this track. Moving to the next track.")
                finally:
                    self.current = None
                    self.queue.task_done()
        finally:
            self.closed = True
            self.clear()
            if self.voice.is_connected():
                await self.voice.disconnect(force=True)

    def clear(self):
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()

    async def close(self):
        self.closed = True
        self.voice.stop()
        self.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.task
        if self.voice.is_connected():
            await self.voice.disconnect(force=True)
