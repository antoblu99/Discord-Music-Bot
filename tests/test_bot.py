import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from music_bot.bot import MusicBot, sync_commands
from music_bot.config import Settings
from music_bot.media import Media, Track, youtube_query
from music_bot.player import Player


def test_configuration(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DISCORD_TOKEN"):
        Settings.from_env()
    monkeypatch.setenv("DISCORD_TOKEN", "private-test-value")
    monkeypatch.setenv("DISCORD_GUILD_ID", "123")
    settings = Settings.from_env()
    assert settings.guild_id == 123
    assert "private-test-value" not in repr(settings)
    monkeypatch.setenv("QUEUE_LIMIT", "0")
    with pytest.raises(ValueError, match="QUEUE_LIMIT"):
        Settings.from_env()


@pytest.mark.parametrize(
    "query",
    [
        "http://youtube.com/watch?v=x",
        "https://example.com/x",
        "https://youtube.com.evil.test/x",
        "",
        "file:///etc/passwd",
    ],
)
def test_invalid_queries(query):
    with pytest.raises(ValueError):
        youtube_query(query)


def test_search():
    assert youtube_query("music") == "ytsearch1:music"
    assert youtube_query("https://youtu.be/example") == "https://youtu.be/example"


async def test_command_sync_removes_legacy_scopes():
    bot = MusicBot(Settings("unused", 123))
    expected = {"join", "leave", "play", "skip", "pause", "resume", "stop", "queue"}
    assert {c.name for c in bot.tree.get_commands()} == expected
    bot.tree.sync = AsyncMock()
    await sync_commands(bot.tree, 123)
    assert bot.tree.get_commands() == []
    guild = SimpleNamespace(id=123)
    assert {c.name for c in bot.tree.get_commands(guild=guild)} == expected
    assert len(bot.tree.sync.await_args_list) == 2
    assert bot.tree.sync.await_args_list[0].kwargs == {}
    assert bot.tree.sync.await_args_list[1].kwargs["guild"].id == 123


async def test_voice_access_control():
    bot = MusicBot(Settings("unused", 123))
    interaction = SimpleNamespace(guild=SimpleNamespace(id=123), user=SimpleNamespace(voice=None))
    with pytest.raises(ValueError, match="Join a voice"):
        bot.player(interaction)
    interaction.user.voice = SimpleNamespace(channel=SimpleNamespace(id=1))
    bot.players[123] = SimpleNamespace(
        closed=False,
        voice=SimpleNamespace(is_connected=lambda: True, channel=SimpleNamespace(id=2)),
    )
    with pytest.raises(ValueError, match="bot's voice channel"):
        bot.player(interaction)


async def test_media_resolution(monkeypatch):
    extractor = MagicMock()
    extractor.__enter__.return_value = extractor
    extractor.extract_info.return_value = {
        "entries": [
            None,
            {
                "extractor_key": "Youtube",
                "title": "Track",
                "webpage_url": "https://youtu.be/x",
                "duration": 100,
            },
        ]
    }
    monkeypatch.setattr("music_bot.media.yt_dlp.YoutubeDL", lambda _: extractor)
    assert await Media(200).resolve("track") == Track("Track", "https://youtu.be/x")
    with pytest.raises(ValueError, match="shorter"):
        await Media(50).resolve("track")


async def test_player_queue_cleanup_and_single_idle_notice(monkeypatch):
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.disconnect = AsyncMock()
    channel = SimpleNamespace(send=AsyncMock())
    paths = []

    async def download(track, directory):
        path = directory / "audio.webm"
        path.touch()
        paths.append(path)
        return path

    media = SimpleNamespace(download=download)
    monkeypatch.setattr("music_bot.player.discord.FFmpegPCMAudio", MagicMock())
    voice.play.side_effect = lambda source, after: after(None)
    player = Player(voice, channel, media, 0.02, 2)
    player.queue.put_nowait(Track("One", "https://youtu.be/one"))
    player.queue.put_nowait(Track("Two", "https://youtu.be/two"))
    await asyncio.wait_for(player.task, 2)
    assert voice.play.call_count == 2
    assert len(paths) == 2 and all(not Path(p).exists() for p in paths)
    notices = [call.args[0] for call in channel.send.await_args_list]
    assert notices.count("Disconnected due to inactivity.") == 1
    voice.disconnect.assert_awaited_once()
    assert player.closed and player.queue.empty()


async def test_player_failure_continues_queue(monkeypatch):
    voice = MagicMock()
    voice.disconnect = AsyncMock()
    channel = SimpleNamespace(send=AsyncMock())
    media = SimpleNamespace(download=AsyncMock(side_effect=RuntimeError("extractor failed")))
    player = Player(voice, channel, media, 0.01, 2)
    player.queue.put_nowait(Track("One", "https://youtu.be/one"))
    player.queue.put_nowait(Track("Two", "https://youtu.be/two"))
    await asyncio.wait_for(player.task, 2)
    assert media.download.await_count == 2
    assert player.queue.empty()


async def test_stop_during_download_cleans_files():
    voice = MagicMock()
    voice.disconnect = AsyncMock()
    started = asyncio.Event()
    release = asyncio.Event()
    paths = []

    async def download(track, directory):
        path = directory / "partial.webm"
        path.touch()
        paths.append(path)
        started.set()
        try:
            await asyncio.shield(release.wait())
        except asyncio.CancelledError:
            await release.wait()
            raise

    player = Player(
        voice, SimpleNamespace(send=AsyncMock()), SimpleNamespace(download=download), 10, 2
    )
    player.queue.put_nowait(Track("Track", "https://youtu.be/x"))
    await started.wait()
    closing = asyncio.create_task(player.close())
    await asyncio.sleep(0)
    release.set()
    await asyncio.wait_for(closing, 2)
    assert player.closed and player.queue.empty()
    assert all(not path.exists() for path in paths)
    voice.play.assert_not_called()


async def test_media_download_cancellation_waits_for_thread(monkeypatch, tmp_path):
    import threading

    started = threading.Event()
    release = threading.Event()
    extractor = MagicMock()
    extractor.__enter__.return_value = extractor

    def extract(*args, **kwargs):
        started.set()
        assert release.wait(timeout=2)
        return {}

    extractor.extract_info.side_effect = extract
    extractor.prepare_filename.return_value = str(tmp_path / "audio.webm")
    monkeypatch.setattr("music_bot.media.yt_dlp.YoutubeDL", lambda _: extractor)
    task = asyncio.create_task(Media(200).download(Track("x", "https://youtu.be/x"), tmp_path))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
