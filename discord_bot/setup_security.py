"""One-off permission hardening and the private Mustang's Hold area.

The server owner holds every permission by ownership, so no role grants anything dangerous: handing someone the wrong
role by accident can't give away the server. Guild Officer gets moderation tools only, every other role is cosmetic,
and Mustang's Hold (text + voice) is visible only to the owner and the Mustang's Guard role.

Needs the bot's role temporarily above Guild Officer with Administrator; take both back afterwards.
Run:  py -3.12 setup_security.py
"""

from __future__ import annotations

import os

import discord
from dotenv import load_dotenv

from bot import HERE

GUILD_NAME = "Reveria Guild Hall"
GUARD = "Mustang's Guard"
HOLD = "Mustang's Hold"
HOLD_TEXT = "war-table"
HOLD_VOICE = "Captain's Quarters"

OFFICER = discord.Permissions(kick_members=True, moderate_members=True, manage_messages=True, manage_threads=True,
                              manage_nicknames=True, mute_members=True, deafen_members=True, move_members=True,
                              view_audit_log=True)
EVERYONE_REMOVE = discord.Permissions(mention_everyone=True, create_events=True, create_expressions=True)
GUARD_ACCESS = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True,
                                           embed_links=True, attach_files=True, add_reactions=True, connect=True,
                                           speak=True, stream=True, use_voice_activation=True,
                                           send_voice_messages=True)


async def run(client: discord.Client) -> None:
    g = discord.utils.get(client.guilds, name=GUILD_NAME)
    me = g.me.top_role
    officer = discord.utils.get(g.roles, name="Guild Officer")
    master = discord.utils.get(g.roles, name="Guild Master")
    if not g.me.guild_permissions.administrator or me <= officer:
        raise SystemExit("give the bot's role Administrator and drag it above Guild Officer first")

    await g.edit(verification_level=discord.VerificationLevel.medium,
                 explicit_content_filter=discord.ContentFilter.all_members,
                 default_notifications=discord.NotificationLevel.only_mentions, reason="hardening")
    print("server: verified email + 5 min account age, scan all media, mentions-only notifications")

    everyone = g.default_role
    perms = discord.Permissions(everyone.permissions.value & ~EVERYONE_REMOVE.value)
    await everyone.edit(permissions=perms, reason="hardening")
    print("@everyone: no @everyone pings, no creating events or emoji")

    await officer.edit(permissions=OFFICER, reason="moderation only")
    print("Guild Officer:", ", ".join(p for p, v in OFFICER if v))
    for r in g.roles:
        if r not in (everyone, officer, me) and not r.managed and r.permissions.value:
            await r.edit(permissions=discord.Permissions.none(), reason="cosmetic roles grant nothing")
            print("cleared", r.name)

    guard = discord.utils.get(g.roles, name=GUARD)
    if guard is None:
        guard = await g.create_role(name=GUARD, colour=discord.Colour(0xC0C0C0), permissions=discord.Permissions.none(),
                                    reason="private Mustang's Hold access")
    # Guard sits above the bot (once the bot's role goes back under Guild Officer), so the bot can never grant it.
    lead = [me, guard, officer]
    rest = [r for r in sorted(g.roles, key=lambda r: -r.position) if r not in lead and r not in (master, everyone)]
    order = lead + rest
    await g.edit_role_positions({r: len(order) - i for i, r in enumerate(order)}, reason="role order")
    print("roles: Guild Master > Mustang's Guard > Guild Officer > Flutter (after you drag Flutter back down)")

    overwrites = {everyone: discord.PermissionOverwrite(view_channel=False, connect=False),
                  guard: GUARD_ACCESS,
                  me: discord.PermissionOverwrite(view_channel=False, connect=False)}
    cat = discord.utils.get(g.categories, name=HOLD)
    if cat is None:
        cat = await g.create_category(HOLD, overwrites=overwrites, position=0, reason="private area")
    else:
        await cat.edit(overwrites=overwrites)
    text = discord.utils.get(cat.text_channels, name=HOLD_TEXT)
    if text is None:
        text = await cat.create_text_channel(HOLD_TEXT, overwrites=overwrites,
                                             topic="Captain Mustang's private war table. Invitation only.")
    else:
        await text.edit(overwrites=overwrites)
    voice = discord.utils.get(cat.voice_channels, name=HOLD_VOICE)
    if voice is None:
        voice = await cat.create_voice_channel(HOLD_VOICE, overwrites=overwrites)
    else:
        await voice.edit(overwrites=overwrites)
    print(f"{HOLD}: #{text.name} + {voice.name}, owner and {GUARD} only")


def main() -> None:
    load_dotenv(HERE / ".env")
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        try:
            await run(client)
        finally:
            await client.close()

    client.run(os.environ["DISCORD_TOKEN"], log_handler=None)


if __name__ == "__main__":
    main()
