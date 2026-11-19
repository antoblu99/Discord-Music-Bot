"""Check that the native Unraid template stays usable as configuration evolves."""

import shlex
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from music_bot.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_template_configuration_matches_application(monkeypatch):
    template = ET.parse(ROOT / "templates/discord-music-bot.xml").getroot()
    assert template.tag == "Container" and template.attrib["version"] == "2"
    configs = template.findall("Config")
    targets = {config.attrib["Target"]: config for config in configs}
    assert len(targets) == len(configs)
    assert all(config.attrib["Type"] == "Variable" for config in configs)
    assert targets["DISCORD_TOKEN"].attrib["Mask"] == "true"
    for key in ("DISCORD_TOKEN", "DISCORD_GUILD_ID"):
        assert targets[key].attrib["Required"] == "true"
        assert targets[key].attrib["Default"] == ""
        assert not (targets[key].text or "").strip()
    for key, config in targets.items():
        monkeypatch.setenv(key, config.attrib["Default"])
    monkeypatch.setenv("DISCORD_TOKEN", "test-only-not-a-real-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "123")
    settings = Settings.from_env()
    assert settings.idle_timeout == int(targets["IDLE_TIMEOUT"].text)
    assert settings.queue_limit == int(targets["QUEUE_LIMIT"].text)
    assert settings.max_duration == int(targets["MAX_DURATION"].text)
    assert template.findtext("Network") == "bridge"
    assert template.findtext("Privileged") == "false"
    assert template.find("WebUI") is None
    params = shlex.split(template.findtext("ExtraParams"))
    assert "--read-only" in params and "--init" in params
    assert "/tmp:rw,noexec,nosuid,size=1g,mode=1777" in params


def test_ca_profile_and_raw_urls_reference_repository_files():
    profile = ET.parse(ROOT / "ca_profile.xml").getroot()
    template = ET.parse(ROOT / "templates/discord-music-bot.xml").getroot()
    assert profile.tag == "CommunityApplications"
    assert profile.findtext("Profile").strip()
    assert template.findtext("Repository") == "ghcr.io/antoblu99/discord-music-bot:latest"
    assert template.findtext("Project") or template.findtext("Support")
    for url in (
        profile.findtext("Icon"),
        template.findtext("Icon"),
        template.findtext("TemplateURL"),
        template.findtext("ReadMe"),
    ):
        parsed = urlparse(url)
        assert parsed.scheme == "https" and parsed.hostname == "raw.githubusercontent.com"
        prefix = "/antoblu99/Discord-Music-Bot/main/"
        assert parsed.path.startswith(prefix)
        assert (ROOT / parsed.path.removeprefix(prefix)).is_file()
    assert template.findtext("TemplateURL").endswith("/templates/discord-music-bot.xml")
    icon = (ROOT / "icon.png").read_bytes()
    assert icon[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", icon[16:24]) == (256, 256)
