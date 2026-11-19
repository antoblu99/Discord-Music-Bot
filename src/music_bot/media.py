"""Resolve and download one YouTube track without blocking the Discord event loop."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp


@dataclass(frozen=True)
class Track:
    title: str
    url: str


def youtube_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("Enter a YouTube URL or a search query of at most 500 characters.")
    if "://" in query:
        parsed = urlparse(query)
        if (
            parsed.scheme != "https"
            or parsed.hostname
            not in {
                "youtube.com",
                "www.youtube.com",
                "m.youtube.com",
                "music.youtube.com",
                "youtu.be",
            }
            or parsed.username
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Only HTTPS YouTube URLs are supported.")
        return query
    return f"ytsearch1:{query}"


class Media:
    def __init__(self, max_duration: int):
        self.max_duration = max_duration
        # Limit simultaneous extractor processes across all guilds.
        self.slots = asyncio.Semaphore(2)

    def options(self):
        return {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 20,
            "retries": 2,
            "extractor_retries": 2,
            "cachedir": False,
            "js_runtimes": {"node": {}},
        }

    async def resolve(self, query: str) -> Track:
        query = youtube_query(query)

        def extract():
            with yt_dlp.YoutubeDL(self.options()) as ydl:
                data = ydl.extract_info(query, download=False)
            if data and "entries" in data:
                data = next((entry for entry in data["entries"] if entry), None)
            if not data or data.get("extractor_key") != "Youtube":
                raise ValueError("No playable YouTube video found.")
            if data.get("is_live") or not data.get("duration"):
                raise ValueError("Live streams and tracks with unknown duration are unsupported.")
            if data["duration"] > self.max_duration:
                raise ValueError(f"Tracks must be shorter than {self.max_duration} seconds.")
            return Track(data["title"], data["webpage_url"])

        async with self.slots:
            return await asyncio.to_thread(extract)

    async def download(self, track: Track, directory: Path) -> Path:
        def extract():
            options = self.options() | {"outtmpl": str(directory / "audio.%(ext)s")}
            with yt_dlp.YoutubeDL(options) as ydl:
                data = ydl.extract_info(track.url, download=True)
                return Path(ydl.prepare_filename(data))

        async with self.slots:
            # Await the thread even during cancellation before its temporary directory is removed.
            task = asyncio.create_task(asyncio.to_thread(extract))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
