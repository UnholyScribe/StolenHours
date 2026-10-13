"""One-off server setup through the bot: icon, license-rank roles, and the Stolen Hours screenshots in #save-editing.

Run:  py -3.12 setup_server.py [--icon] [--roles] [--screenshots]   (no flags = all three)
Posting is skipped if the bot already posted screenshots in that channel.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import discord
from dotenv import load_dotenv

from bot import HERE, ensure_rank_roles

GUILD_NAME = "Reveria Guild Hall"
ICON = HERE / "assets" / "guild_icon.png"
SHOTS = HERE / "screenshots"
CHANNEL = "save-editing"
# screenshot file -> caption, in tab order
CAPTIONS = [
    ("overview.png", "**Adventurer**: name, Dosh and your character in 3D, wearing your current gear (read live "
                     "from the game when it's running). Pick any Life's pose."),
    ("lives.png", "**Licenses**: every Life's level, exp and rank. The 3D view shows that Life's starter outfit "
                  "and tool."),
    ("inventory.png", "**Bag**: every pocket with the game's own icons; change stacks or add any item."),
    ("appearance.png", "**Look**: the full character creator (hair, eyes, face parts, colours, build) with a "
                       "live 3D preview."),
    ("live.png", "**Time Hook**: talks to the running game through a small UE4SS mod: read and set Dosh live, "
                 "dump game data."),
    ("file.png", "**Records**: pick the save. Every write checks the game is closed, backs up with a SHA-256 and "
                 "verifies a byte-exact repack."),
]
INTRO = ("# Stolen Hours\nA save editor and live game hook for **Fantasy Life i: The Girl Who Steals Time**, "
         "styled after the game's own menus. Here is every tab:")


async def run(client: discord.Client, what: set[str]) -> None:
    guild = discord.utils.get(client.guilds, name=GUILD_NAME)
    if guild is None:
        raise SystemExit(f"the bot is not in {GUILD_NAME}")
    if "icon" in what:
        await guild.edit(icon=ICON.read_bytes(), reason="Guild crest")
        print("icon set")
    if "roles" in what:
        print("rank roles:", ", ".join((await ensure_rank_roles(guild)).keys()))
    if "screenshots" in what:
        channel = discord.utils.get(guild.text_channels, name=CHANNEL)
        if channel is None:
            raise SystemExit(f"no #{CHANNEL}")
        async for m in channel.history(limit=50):
            if m.author == client.user and m.attachments:
                print(f"screenshots already in #{CHANNEL}; skipped")
                return
        await channel.send(INTRO)
        for name, caption in CAPTIONS:
            await channel.send(caption, file=discord.File(SHOTS / name))
        print(f"posted {len(CAPTIONS)} screenshots to #{CHANNEL}")


def main() -> None:
    load_dotenv(HERE / ".env")
    what = {a.lstrip("-") for a in sys.argv[1:]} or {"icon", "roles", "screenshots"}
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        try:
            await run(client, what)
        finally:
            await client.close()

    client.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    main()
