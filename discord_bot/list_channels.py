"""Read-only: prints the server's categories, channels (with topics and permissions the bot holds) and how many
messages the bot already has in each. Run:  py -3.12 list_channels.py
"""

from __future__ import annotations

import os
import traceback

import discord
from dotenv import load_dotenv

from bot import HERE

GUILD_NAME = "Reveria Guild Hall"


async def run(client: discord.Client) -> None:
    g = discord.utils.get(client.guilds, name=GUILD_NAME)
    me = g.me
    print(f"{g.name}: {g.member_count} members; bot perms manage_channels={me.guild_permissions.manage_channels} "
          f"manage_guild={me.guild_permissions.manage_guild}")
    for cat, chans in g.by_category():
        print(f"\n[{cat.name if cat else '(no category)'}]")
        for ch in chans:
            p = ch.permissions_for(me)
            line = f"  #{ch.name} ({ch.type}) view={p.view_channel} send={p.send_messages}"
            if isinstance(ch, discord.TextChannel):
                ours = 0
                if p.view_channel and p.read_message_history:
                    async for m in ch.history(limit=50):
                        ours += m.author == client.user
                line += f" ours={ours} topic={ch.topic!r}"
            print(line)


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
