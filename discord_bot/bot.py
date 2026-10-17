"""Reveria Guild Hall bot: chat XP and automatic license-rank promotions.

Members earn 15-25 XP for a message, at most once a minute (the usual MEE6 pace), and climb Fantasy Life's license
ranks. The ladder ends at Legend: the bot never grants a role outside RANKS, so Guild Master and Guild Officer stay
hand-given, and Discord itself refuses to let a bot assign any role placed above the bot's own role.

Run:  py -3.12 bot.py          (token in .env as DISCORD_TOKEN)
"""

from __future__ import annotations

import os
import random
import sqlite3
import time
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

import moderation as mod

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "data" / "levels.db"

# level reached -> license rank role (Fantasy Life's own rank names), with the role colour
RANKS = [
    (1, "Fledgling", 0x95A5A6),
    (5, "Apprentice", 0x2ECC71),
    (10, "Adept", 0x1ABC9C),
    (20, "Expert", 0x3498DB),
    (35, "Master", 0x9B59B6),
    (50, "Hero", 0xE67E22),
    # the top earnable rank: ~835,000 XP, about 42,000 counted minutes (~700 hours) of chatting
    (75, "Legend", 0xE91E63),
]
RANK_NAMES = {name for _, name, _ in RANKS}
STAFF_ROLES = {"Guild Master", "Guild Officer"}
# handing out any of these, or giving any role a DANGEROUS permission, is DMed to the owner
WATCHED_ROLES = STAFF_ROLES | {"Mustang's Guard"}
DANGEROUS = discord.Permissions(administrator=True, manage_guild=True, manage_roles=True, manage_channels=True,
                                manage_webhooks=True, ban_members=True, mention_everyone=True,
                                manage_expressions=True, manage_events=True)
XP_RANGE = (15, 25)
COOLDOWN_S = 60


def xp_for_next(level: int) -> int:
    return 5 * level * level + 50 * level + 100


def level_of(xp: int) -> tuple[int, int, int]:
    """Total XP -> (level, XP into this level, XP needed for the next)."""
    level = 0
    while xp >= xp_for_next(level):
        xp -= xp_for_next(level)
        level += 1
    return level, xp, xp_for_next(level)


def rank_for(level: int) -> str | None:
    rank = None
    for need, name, _ in RANKS:
        if level >= need:
            rank = name
    return rank


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS xp (guild INTEGER, user INTEGER, xp INTEGER, last REAL, "
                        "PRIMARY KEY (guild, user))")
        self.db.execute("CREATE TABLE IF NOT EXISTS strikes (guild INTEGER, user INTEGER, at REAL, rule TEXT)")
        self.db.commit()

    def strike(self, guild: int, user: int, rule: str, window_s: float, now: float | None = None) -> int:
        """Record a strike; returns how many the user has inside the window, this one included."""
        now = time.time() if now is None else now
        self.db.execute("INSERT INTO strikes VALUES (?,?,?,?)", (guild, user, now, rule))
        self.db.commit()
        return self.db.execute("SELECT COUNT(*) FROM strikes WHERE guild=? AND user=? AND at>?",
                               (guild, user, now - window_s)).fetchone()[0]

    def get(self, guild: int, user: int) -> tuple[int, float]:
        row = self.db.execute("SELECT xp, last FROM xp WHERE guild=? AND user=?", (guild, user)).fetchone()
        return row or (0, 0.0)

    def put(self, guild: int, user: int, xp: int, last: float) -> None:
        self.db.execute("INSERT INTO xp VALUES (?,?,?,?) ON CONFLICT(guild, user) DO UPDATE SET xp=?, last=?",
                        (guild, user, xp, last, xp, last))
        self.db.commit()

    def top(self, guild: int, n: int = 10) -> list[tuple[int, int]]:
        return self.db.execute("SELECT user, xp FROM xp WHERE guild=? ORDER BY xp DESC LIMIT ?", (guild, n)).fetchall()

    def place(self, guild: int, xp: int) -> int:
        return self.db.execute("SELECT COUNT(*) FROM xp WHERE guild=? AND xp>?", (guild, xp)).fetchone()[0] + 1


async def ensure_rank_roles(guild: discord.Guild) -> dict[str, discord.Role]:
    roles = {r.name: r for r in guild.roles}
    for _, name, colour in RANKS:
        if name not in roles:
            roles[name] = await guild.create_role(name=name, colour=discord.Colour(colour), hoist=True,
                                                  reason="Reveria Guild Hall license ranks")
    await order_rank_roles(guild, roles)
    return {name: roles[name] for name in RANK_NAMES}


async def order_rank_roles(guild: discord.Guild, roles: dict[str, discord.Role]) -> None:
    """Stack the ranks directly under the bot's role, Legend highest, so the member list groups by rank."""
    ladder = [roles[name] for _, name, _ in RANKS]
    top = guild.me.top_role.position
    others = sorted((r for r in guild.roles if 0 < r.position < top and r not in ladder), key=lambda r: r.position)
    wanted = {r: i for i, r in enumerate(others + ladder, start=1)}
    if any(r.position != p for r, p in wanted.items()):
        try:
            await guild.edit_role_positions(wanted, reason="order license ranks")
        except discord.Forbidden:
            print("can't order the rank roles: drag the bot's role above them in Server Settings > Roles")


async def promote(member: discord.Member, level: int, ranks: dict[str, discord.Role]) -> str | None:
    """Give the member the rank for their level and drop the lower ranks. Returns the new rank if it changed."""
    target = rank_for(level)
    have = {r.name for r in member.roles}
    if target is None or have & STAFF_ROLES:
        return None
    stale = [ranks[n] for n in RANK_NAMES & have if n != target]
    if stale:
        await member.remove_roles(*stale, reason="license rank up")
    if target in have:
        return None
    await member.add_roles(ranks[target], reason=f"reached level {level}")
    return target


class GuildBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(
            self, allowed_contexts=app_commands.AppCommandContext(guild=True),
            allowed_installs=app_commands.AppInstallationType(guild=True))
        self.store = Store()
        self.ranks: dict[int, dict[str, discord.Role]] = {}

    async def setup_hook(self) -> None:
        register(self)
        await self.tree.sync()

    async def on_ready(self) -> None:
        for g in self.guilds:
            self.ranks[g.id] = await ensure_rank_roles(g)
        print(f"logged in as {self.user} in {[g.name for g in self.guilds]}", flush=True)

    async def on_message(self, msg: discord.Message) -> None:
        if msg.author.bot or msg.guild is None or not isinstance(msg.author, discord.Member):
            return
        xp, last = self.store.get(msg.guild.id, msg.author.id)
        now = time.time()
        if now - last < COOLDOWN_S:
            return
        before = level_of(xp)[0]
        xp += random.randint(*XP_RANGE)
        self.store.put(msg.guild.id, msg.author.id, xp, now)
        level = level_of(xp)[0]
        if level == before:
            return
        ranks = self.ranks.get(msg.guild.id) or await ensure_rank_roles(msg.guild)
        try:
            new_rank = await promote(msg.author, level, ranks)
        except discord.Forbidden:
            new_rank = None
        line = f"{msg.author.mention} reached **level {level}**!"
        if new_rank:
            line += f" The Guild grants you the **{new_rank}** license."
        await msg.channel.send(line, allowed_mentions=discord.AllowedMentions(users=[msg.author]))

    def mod_log(self, guild: discord.Guild) -> discord.TextChannel | None:
        return discord.utils.get(guild.text_channels, name=mod.MOD_LOG)

    async def on_automod_action(self, execution: discord.AutoModAction) -> None:
        """Every AutoMod block is a strike; enough strikes in the window earn a timeout."""
        if execution.action.type != discord.AutoModRuleActionType.block_message:
            return
        g = execution.guild
        try:
            rule = (await g.fetch_automod_rule(execution.rule_id)).name
        except discord.HTTPException:
            rule = "AutoMod"
        count = self.store.strike(g.id, execution.user_id, rule, mod.STRIKE_WINDOW.total_seconds())
        line = (f"Strike {count} for <@{execution.user_id}>: **{rule}**"
                + (f" (matched `{execution.matched_keyword}`)" if execution.matched_keyword else "")
                + (f" in <#{execution.channel_id}>" if execution.channel_id else "") + ".")
        length = mod.timeout_for(count)
        if length:
            try:
                member = g.get_member(execution.user_id) or await g.fetch_member(execution.user_id)
                if member.id != g.owner_id and (member.timed_out_until is None
                                                or member.timed_out_until < discord.utils.utcnow() + length):
                    await member.timeout(length, reason=f"{count} AutoMod strikes in 24h")
                    line += f" Timed out for {length}."
                    try:
                        await member.send(f"You were timed out in **{g.name}** for {length} after {count} rule "
                                          f"breaks in a day. Read #rules before you post again.")
                    except discord.HTTPException:
                        pass
            except discord.HTTPException as e:
                line += f" Could not time them out ({e.status}): they may rank above the bot."
        log = self.mod_log(g)
        if log:
            await log.send(line, allowed_mentions=discord.AllowedMentions.none())

    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry) -> None:
        g = entry.guild
        who = f"<@{entry.user_id}>" if entry.user_id else "someone"
        alerts = []
        if entry.action == discord.AuditLogAction.member_role_update:
            added = [r.name for r in getattr(entry.after, "roles", []) if getattr(r, "name", None) in WATCHED_ROLES]
            if added:
                alerts.append(f"{who} gave <@{entry.target.id}> **{', '.join(added)}**.")
        elif entry.action in (discord.AuditLogAction.role_create, discord.AuditLogAction.role_update):
            perms = getattr(entry.after, "permissions", None)
            if perms is not None and perms.value & DANGEROUS.value:
                bad = [p for p, v in discord.Permissions(perms.value & DANGEROUS.value) if v]
                alerts.append(f"{who} gave the role **{getattr(entry.target, 'name', entry.target.id)}** "
                              f"dangerous permissions: {', '.join(bad)}.")
        if not alerts:
            return
        try:
            owner = await self.fetch_user(g.owner_id)
            await owner.send(f"**{g.name} security check**\n" + "\n".join(alerts)
                             + "\nIf that wasn't meant, undo it in Server Settings.")
        except discord.HTTPException:
            print("could not DM the owner:", *alerts, flush=True)


def register(bot: GuildBot) -> None:
    @bot.tree.command(description="Show your level and license rank (or someone else's)")
    async def rank(inter: discord.Interaction, member: discord.Member | None = None):
        member = member or inter.user
        xp, _ = bot.store.get(inter.guild_id, member.id)
        level, into, need = level_of(xp)
        rank_name = next((r.name for r in member.roles if r.name in STAFF_ROLES | RANK_NAMES), "Novice")
        bar = "█" * int(10 * into / need) + "░" * (10 - int(10 * into / need))
        await inter.response.send_message(
            f"**{member.display_name}**: {rank_name}, level {level}\n`{bar}` {into}/{need} XP "
            f"(#{bot.store.place(inter.guild_id, xp)} in the Guild)")

    @bot.tree.command(description="The Guild's top adventurers")
    async def leaderboard(inter: discord.Interaction):
        rows = bot.store.top(inter.guild_id)
        if not rows:
            await inter.response.send_message("Nobody has earned XP yet.")
            return
        lines = [f"**{i}.** <@{u}>: level {level_of(x)[0]} ({x} XP)" for i, (u, x) in enumerate(rows, 1)]
        await inter.response.send_message("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())

    @bot.tree.command(description="The license ranks and the level each one needs")
    async def ranks(inter: discord.Interaction):
        lines = [f"Level {need}: **{name}**" for need, name, _ in RANKS]
        await inter.response.send_message("\n".join(lines) + "\nGuild Officer and Guild Master are appointed, "
                                          "not earned.")

    @bot.tree.command(description="Show the Guild rules")
    async def rules(inter: discord.Interaction):
        await inter.response.send_message(embeds=mod.rules_embeds(), ephemeral=True)

    async def report(inter: discord.Interaction, message: discord.Message):
        log = bot.mod_log(inter.guild)
        if log is None:
            await inter.response.send_message("Reports aren't set up yet.", ephemeral=True)
            return
        e = discord.Embed(title="Member report", colour=0xE67E22, description=(message.content or "*no text*")[:1500],
                          timestamp=message.created_at)
        e.add_field(name="Author", value=f"{message.author.mention} ({message.author})")
        e.add_field(name="Reported by", value=inter.user.mention)
        e.add_field(name="Message", value=f"[jump to it]({message.jump_url}) in {message.channel.mention}",
                    inline=False)
        if message.attachments:
            e.add_field(name="Attachments", value="\n".join(a.url for a in message.attachments[:5]), inline=False)
        await log.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        await inter.response.send_message("Thanks, the Guild staff have it. You can block the user in the meantime "
                                          "if you need to.", ephemeral=True)

    bot.tree.add_command(app_commands.ContextMenu(name="Report to the Guild", callback=report))

    @bot.tree.command(description="Guild Master only: give or take XP")
    @app_commands.default_permissions(administrator=True)
    async def givexp(inter: discord.Interaction, member: discord.Member, amount: int):
        if inter.user.id != inter.guild.owner_id:
            await inter.response.send_message("Only the Guild Master can do that.", ephemeral=True)
            return
        xp, last = bot.store.get(inter.guild_id, member.id)
        xp = max(0, xp + amount)
        bot.store.put(inter.guild_id, member.id, xp, last)
        level = level_of(xp)[0]
        new_rank = await promote(member, level, bot.ranks[inter.guild_id]) if not member.bot else None
        await inter.response.send_message(f"{member.display_name} now has {xp} XP (level {level})"
                                          + (f", promoted to **{new_rank}**." if new_rank else "."), ephemeral=True)


def main() -> None:
    load_dotenv(HERE / ".env")
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Put DISCORD_TOKEN=... in discord_bot\\.env first.")
    GuildBot().run(token)


if __name__ == "__main__":
    main()
