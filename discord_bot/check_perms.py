"""Read-only: the bot's roles, what each grants, and where every role sits. Run:  py -3.12 check_perms.py"""

from __future__ import annotations

import os
import traceback

import discord
from dotenv import load_dotenv

from bot import HERE

GUILD_NAME = "Reveria Guild Hall"
KEY = ("administrator", "manage_guild", "manage_channels", "manage_roles", "manage_messages")


async def run(client: discord.Client) -> None:
    g = discord.utils.get(client.guilds, name=GUILD_NAME)
    me = g.me
    print(f"bot: {me} | effective:", {k: getattr(me.guild_permissions, k) for k in KEY})
    for r in sorted(g.roles, key=lambda r: -r.position):
        mark = "  <- bot has" if r in me.roles else ""
        print(f"{r.position:>3} {r.name!r} managed={r.managed}", {k: True for k in KEY if getattr(r.permissions, k)}, mark)


def main() -> None:
    load_dotenv(HERE / ".env")
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        try:
            await run(client)
        except Exception:
            traceback.print_exc()
        finally:
            await client.close()

    client.run(os.environ["DISCORD_TOKEN"], log_handler=None)


if __name__ == "__main__":
    main()
