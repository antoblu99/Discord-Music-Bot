import logging
import shutil
import sys

from .bot import MusicBot
from .config import Settings


def main():
    try:
        settings = Settings.from_env()
        if not shutil.which("ffmpeg") or not shutil.which("node"):
            raise ValueError("FFmpeg and Node.js are required; use the Docker image.")
    except ValueError as error:
        sys.exit(str(error))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    MusicBot(settings).run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
