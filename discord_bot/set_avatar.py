"""Set the bot's profile picture from assets/bot_avatar.png.

Run:  py -3.12 set_avatar.py
"""

import os

import discord
from dotenv import load_dotenv

from bot import HERE

AVATAR = HERE / "assets" / "bot_avatar.png"


def main() -> None:
    load_dotenv(HERE / ".env")
    client = discord.Client(intents=discord.Intents.none())

    @client.event
    async def on_ready():
        try:
            await client.user.edit(avatar=AVATAR.read_bytes())
            print("avatar set for", client.user)
        finally:
            await client.close()

    client.run(os.environ["DISCORD_TOKEN"], log_handler=None)


if __name__ == "__main__":
    main()
