# Discord Music Bot

A music bot for a private Discord server, originally developed by
[antoblu](https://git.antoblu.me/antoblu) as Cippalippa Discord Bot.
Modernized for Python 3.12, current Discord voice support, and Docker/Unraid.

## Discord setup

Create an application and bot in the Discord Developer Portal. Reset any token
previously embedded in source or shared archives before deploying. Invite the
bot with `bot` and `applications.commands` scopes and View Channel, Send Messages,
Connect, and Speak permissions. Administrator and privileged intents are unnecessary.
Enable Developer Mode in Discord to copy your server ID.

```sh
cp .env.example .env
# Set DISCORD_TOKEN and DISCORD_GUILD_ID in .env securely.
docker compose up -d --build
docker compose logs -f --tail=100
```

Never commit `.env`. Compose loads it into the process; the Python application
reads environment variables directly. The image includes FFmpeg, Node.js 24 for
YouTube JavaScript challenges, and hash-verified Python dependencies including EJS.
It runs as UID 10001. No inbound ports or persistent volumes are needed. Outbound
HTTPS and Discord voice UDP must work. Queues are lost on restart.

## Unraid

The native Community Applications template is
[`templates/discord-music-bot.xml`](templates/discord-music-bot.xml), with repository
metadata in [`ca_profile.xml`](ca_profile.xml). It follows the official
[Community Apps starter](https://github.com/unraid/unraid-community-apps-starter).
See the [Unraid installation and publishing guide](docs/unraid.md) for template
testing, image publication, and the CA Validate/Scan submission steps.

The GHCR image is a publication target, not an already published release. Until
the maintainer publishes it and CA approves the submission, build locally and
use the local-template test described in that guide, Docker CLI, or Compose.
Compose Manager is optional; installing from Apps does not require it.

## Docker CLI (without Compose)

You can build locally below, or download a ready-to-load image from the GitHub
**Actions > CI** run's **discord-music-bot-linux-amd64** artifact. Unzip the download
and run `docker load --input discord-music-bot-linux-amd64.tar.gz`, then skip the
`docker build` step below. See the [Unraid guide](docs/unraid.md) for details.

```sh
cp .env.example .env
# Set DISCORD_TOKEN and DISCORD_GUILD_ID securely before starting.
docker build -t discord-music-bot:local .
docker run -d --name discord-music-bot \
  --env-file .env --restart unless-stopped --init \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=1g,mode=1777 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --log-opt max-size=10m --log-opt max-file=3 \
  discord-music-bot:local
docker logs -f --tail=100 discord-music-bot
```

Choose Docker CLI, Compose, or the Unraid template for a given bot; run only one
instance with the same token. No ports or host directories need to be mounted.
Increase the 1 GiB temporary filesystem limit for larger tracks; downloads
exceeding it fail and advance the queue. To stop the CLI container, use
`docker stop discord-music-bot`; Compose uses `docker compose down`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | required | Private bot token |
| `DISCORD_GUILD_ID` | required | Server receiving commands |
| `IDLE_TIMEOUT` | `180` | Seconds waiting for a new track before disconnecting |
| `QUEUE_LIMIT` | `50` | Maximum waiting tracks |
| `MAX_DURATION` | `3600` | Maximum track duration in seconds |

## Commands

| Command | Action |
| --- | --- |
| `/join` | Join your voice channel |
| `/play query` | Queue a YouTube URL or first search result |
| `/queue` | Show current track and waiting count |
| `/pause`, `/resume` | Control playback |
| `/skip` | Skip current playback, after download completes |
| `/stop`, `/leave` | Clear the queue, stop playback, and disconnect |

Controls require membership in the bot's voice channel. Paused playback does not
count as idle. Live streams and tracks with unknown duration are unsupported.
Playlist URLs play only the selected video. Tracks are downloaded into isolated
temporary directories and removed after playback. Announcements use the text
channel selected on connection, without storing expiring interaction tokens.
Stopping waits for an in-flight download before removing its temporary files.

## Migration and duplicate commands

Stop all old bot instances before starting this version: two processes with the
same token can process an interaction twice. During login, this bot replaces this
application's global commands with an empty list and registers the current command
list only in `DISCORD_GUILD_ID`. This removes stale global duplicates and `/dio`.
Use a dedicated application: unrelated global commands belonging to it will also
be removed. Old guild commands in other servers need separate cleanup. Refresh
Discord if cached commands remain visible. Sync runs once in `setup_hook`, not
on every reconnect. One playback worker owns the inactivity timer, preventing the
old repeated disconnect notifications from voice-state events.

## Development

Install Python 3.12+, FFmpeg, Node.js 24 and uv:

```sh
uv sync --frozen
uv run ruff check .
uv run pytest
# Export configuration variables in your shell first.
PYTHONPATH=src uv run python -m music_bot
```

The application does not automatically read `.env` outside Compose. Code is split
into configuration, extraction, playback, and Discord command modules under
`src/music_bot`. Tests use fake media/Discord clients and require no credentials.
CI checks lint, tests, lockfile consistency, and the Docker build.

Update dependencies deliberately, committing both lockfiles:

```sh
uv lock --upgrade
uv sync --frozen
uv export --frozen --no-dev --no-emit-project --no-header --format requirements-txt --output-file requirements.lock
uv run ruff check .
uv run pytest
docker compose up -d --build
```

For a live smoke test, invite the bot to a test server, queue two public YouTube
tracks, exercise pause/resume/skip/stop, and verify exactly one inactivity notice.
YouTube extraction can require future yt-dlp updates or authentication; restricted
content is not guaranteed. Only play content you are authorized to access.

The old Windows virtual environment and embedded configuration are not imported.
Licensed under GPL-3.0; see [LICENSE](LICENSE).
