"""One-off rules setup: the 18+ age gate, read-only info channels, #mod-log, AutoMod filters and the rules post.

Needs Manage Server and Manage Channels on the bot's role for the run; take both back afterwards
(the bot keeps Timeout Members for strike timeouts). Safe to re-run: everything is matched by name and updated.
Run:  py -3.12 setup_rules.py
"""

from __future__ import annotations

import os
import traceback

import discord
from dotenv import load_dotenv

import moderation as mod
from bot import HERE

GUILD_NAME = "Reveria Guild Hall"
A = discord.AutoModRuleAction
T = discord.AutoModTrigger


async def ensure_rule(g, existing, name, trigger, log, alert=True):
    actions = [A(custom_message=mod.BLOCK_MESSAGES.get(name, "Blocked by the Guild rules."))]
    if alert:
        actions.append(A(channel_id=log.id))
    rule = existing.get(name)
    if rule:
        await rule.edit(trigger=trigger, actions=actions, enabled=True)
    else:
        await g.create_automod_rule(name=name, event_type=discord.AutoModRuleEventType.message_send,
                                    trigger=trigger, actions=actions, enabled=True, reason="Guild rules")
    print("automod:", name)


async def run(client: discord.Client) -> None:
    g = discord.utils.get(client.guilds, name=GUILD_NAME)
    me = g.me
    perms = me.guild_permissions
    if not (perms.manage_guild and perms.manage_channels and perms.moderate_members):
        raise SystemExit("give the bot's role Manage Server, Manage Channels and Timeout Members first")
    everyone, bot_role = g.default_role, me.top_role
    officer = discord.utils.get(g.roles, name="Guild Officer")

    # #mod-log: owner, officers and the bot only
    hall = discord.utils.get(g.categories, name="Guild Hall")
    log_ow = {everyone: discord.PermissionOverwrite(view_channel=False),
              officer: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
              bot_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True,
                                                    read_message_history=True)}
    log = discord.utils.get(g.text_channels, name=mod.MOD_LOG)
    if log is None:
        log = await g.create_text_channel(mod.MOD_LOG, category=hall, overwrites=log_ow,
                                          topic="AutoMod blocks, strikes, timeouts and member reports.")
    else:
        await log.edit(overwrites=log_ow)
    print("#mod-log ready")

    # read-only info channels
    for name in mod.LOCKED_CHANNELS:
        ch = discord.utils.get(g.text_channels, name=name)
        if ch is None:
            continue
        await ch.set_permissions(everyone, send_messages=False, create_public_threads=False,
                                 create_private_threads=False, add_reactions=True)
        await ch.set_permissions(bot_role, view_channel=True, send_messages=True, embed_links=True,
                                 read_message_history=True)
    print("read-only:", ", ".join(mod.LOCKED_CHANNELS))

    # 18+ gate on every channel except the two you see before agreeing
    gated, hidden = 0, []
    for ch in g.channels:
        if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)) and ch.name not in mod.UNGATED_CHANNELS:
            if not ch.permissions_for(me).view_channel:
                hidden.append(ch.name)
                continue
            if not ch.nsfw:
                await ch.edit(nsfw=True)
            gated += 1
    print(f"age-restricted {gated} channels" + (f"; can't see {hidden}, set those by hand" if hidden else ""))

    # AutoMod
    existing = {r.name: r for r in await g.fetch_automod_rules()}
    for name, words in mod.FILTERS.items():
        await ensure_rule(g, existing, name, T(type=discord.AutoModRuleTriggerType.keyword, keyword_filter=words), log)
    await ensure_rule(g, existing, "Slurs", T(presets=discord.AutoModPresets(slurs=True)), log)
    await ensure_rule(g, existing, "Mention spam", T(mention_limit=6, mention_raid_protection=True), log)

    # the rules post: edit ours if it exists, else post it
    rules = discord.utils.get(g.text_channels, name=mod.RULES_CHANNEL)
    ours = None
    async for m in rules.history(limit=20):
        if m.author == client.user:
            ours = m
            break
    if ours:
        await ours.edit(embeds=mod.rules_embeds())
        print("rules updated")
    else:
        await rules.send(embeds=mod.rules_embeds())
        print("rules posted")


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
