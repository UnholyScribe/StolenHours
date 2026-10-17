"""Info posts: #welcome guide, #roles ladder, a news channel per game (#fl-news, #flo-news, #fli-news), codes
where the game has them (#fl-passwords, #fli-gift-codes), links in #fli-help-and-tips, and a note in #announcements.

Creating the news/codes channels and locking them needs Manage Channels on the bot's role for the run (take it back
afterwards). Without it, each post goes to that game's existing channels (FALLBACK) and moves on a later run.
Safe to re-run: each post is matched by its first embed's title; the bot's copies anywhere else are deleted.
Run:  py -3.12 setup_info.py [--dry]      (--dry prints sizes and posts nothing)

Sources (checked 2026-10-12): fantasylife.jp patch notes 2.2.0 / 2.2.2 and gift-code guide; Gematsu, Siliconera,
Famitsu (DLC, 2026-09-10); fantasylife.wiki.gg Gift_Codes and GameWith (same codes in Japan). Reward effects,
stars and sell prices come from the game's own item tables (research/gift_items.py).
"""

from __future__ import annotations

import os
import sys
import traceback

import discord
from dotenv import load_dotenv

import info_classic as classic
from bot import HERE, RANKS

GUILD_NAME = "Reveria Guild Hall"
GOLD, BLUE, GREEN, PINK = 0xF1C40F, 0x3498DB, 0x2ECC71, 0xE91E63
# new channel -> (category, topic); created at the top of their game's category, read-only
NEW_CHANNELS = {
    "fl-news": ("Fantasy Life (3DS)", "Fantasy Life (3DS) news: DLC, eShop and online status. Read-only."),
    "fl-passwords": ("Fantasy Life (3DS)", "Every 3DS password, sorted by region and language. Read-only."),
    "flo-news": ("Fantasy Life Online", "Fantasy Life Online news and its code archive. Read-only."),
    "fli-news": ("Fantasy Life i", "Fantasy Life i updates, patch notes and DLC news. Read-only."),
    "fli-gift-codes": ("Fantasy Life i", "Every Fantasy Life i gift code and exactly what it gives. Read-only."),
}
# where those posts go while the new channels can't be created; removed from here once the channels exist
FALLBACK = {"fl-news": "fl-general", "fl-passwords": "fl-help-and-tips", "flo-news": "flo-general",
            "fli-news": "fli-general", "fli-gift-codes": "fli-help-and-tips"}

# ---------- #fli-news ----------
NEWS = [
    {"title": "Latest update: version 2.2.0 (August 20, 2026)", "colour": BLUE,
     "url": "https://www.fantasylife.jp/fli/en/patchnote/ver_2_2_0/",
     "desc": "The current version on **Switch 2, Switch, PS5, PS4, Xbox Series X|S and Steam**.\n\n"
             "**What's new**\n"
             "- **Crossplay with the new mobile version** (iOS and Android).\n"
             "- **Free costume packs for everyone:** the *True Gentleman's Costume Pack* and the *Jibanyan Costume "
             "Pack*. Claim them from the **Treasure Chest in the Eternia Village Guild Office**.\n"
             "- Fonts changed for some languages (licensing).\n\n"
             "**Fixes worth knowing**\n"
             "- The Plundering Panther at Buffalo Base (Ginormosia) now reliably gives the **True Time** equipment "
             "recipe.\n"
             "- Giving up a buddy's Personal Request no longer plays a fake item-receive animation.\n"
             "- The Novice Angler Challenge no longer stalls after the fishing guide.\n"
             "- Buddy models no longer glitch in the Goddess Statue's Power Up tab after Revert Strangeling."},
    {"title": "Mobile version and follow-up patches", "colour": BLUE,
     "url": "https://www.fantasylife.jp/fli/en/patchnote/ver_2_2_2/",
     "desc": "**iOS and Android launched on August 20, 2026** for **$24.99**, no in-app purchases. It includes "
             "the Digital Deluxe content and the free *Bazario* DLC, with **cross-save** and **crossplay**. "
             "2-player local Family Co-op is not on mobile; online play is.\n\n"
             "**2.2.1** (Aug 21, Android only): fixed downloads failing on mobile data.\n"
             "**2.2.2** (Sep 8, iOS and Android only): fewer crashes (Ginormosia on iPhone, at launch), iPad "
             "screen cut-off, held skill buttons blocking Charged Attacks, Auto-Select Target OFF not applying, "
             "Android downloads stalling after an update, and stuck buttons on the first Hagram Build.\n\n"
             "Consoles and Steam stay on **2.2.0**; 2.2.1 and 2.2.2 were mobile-only."},
    {"title": "New paid DLC: The Celestial Express", "colour": GOLD,
     "url": "https://www.gematsu.com/2026/09/fantasy-life-i-the-girl-who-steals-time-paid-dlc-the-celestial-express-announced",
     "desc": "Announced by LEVEL-5 on **September 10, 2026** (LEVEL5 VISION 2026 II). Japanese title: "
             "*天界列車としあわせの終着駅*. **Paid** DLC. The free one before it was *The Sinister Broker "
             "Bazario's Schemes* (v2.0, December 2025).\n\n"
             "**Confirmed so far**\n"
             "- **Two new Life Ranks above Hero:** *God-in-Training* and *God*, with new challenges for every Life.\n"
             "- **God Crafting:** one recipe can come out in different looks. Items from **God Recipes** can roll "
             "special **God Skills**.\n"
             "- **Wingmate:** a new accessory type that flies beside you and helps on adventures.\n"
             "- **A special mount** you can upgrade with parts made by God-rank crafting Lives. It changes looks "
             "and stats, and you can **attack while riding**.\n"
             "- **God Crown** monsters, a tier stronger than Gold Crown.\n"
             "- Buddy-themed weapons, armor and outfits; new furniture sets and house designs; new monsters and "
             "gatherables.\n\n"
             "**Not announced yet:** release date, price, and which platforms get it. Nothing official points to "
             "2026, so treat the date as unknown.\n"
             "We'll update this post when LEVEL-5 shares more."},
]

# ---------- #fli-gift-codes ----------
REDEEM = {"title": "How to redeem a gift code", "colour": GREEN,
          "url": "https://www.fantasylife.jp/fli/en/guide/password/",
          "desc": "1. Play until you've **picked your first Life at the Guild Office**. That adds **Gifts** to the "
                  "Menu.\n"
                  "2. Menu > **Gifts** > **Gift Code Entry**.\n"
                  "3. Choose **Connect** if asked (most codes need the internet), then type the code. "
                  "Codes are **case-sensitive**.\n"
                  "4. The items go straight to you. Some only become usable later in the story.\n\n"
                  "**Switch / Switch 2:** redeeming needs an internet connection **and a Nintendo Switch Online "
                  "membership**.\n"
                  "**If a correct code shows an error:** go back, choose Connect, and try again."}
SORTING = {"title": "Region and platform: one list for everyone", "colour": GREEN,
           "desc": "LEVEL-5 hasn't released region- or platform-specific codes. **Every code below works on every "
                   "platform** (Switch 2, Switch, PS5, PS4, Xbox, Steam, iOS, Android) and in every region. The "
                   "same codes were posted by the English and Japanese official accounts and the Steam hub.\n\n"
                   "- Each code works **once per save**.\n"
                   "- No code has an announced expiry, but redeem them early anyway.\n"
                   "- **Ignore the long lists of extra codes** from before launch (e.g. X3T8E45Q, K8XYRPNV). They "
                   "were never announced, and players report they don't work.\n"
                   "- No code is needed for the **2.2.0 costume packs** (True Gentleman's and Jibanyan). They're in "
                   "the Treasure Chest at the Eternia Village Guild Office."}
LEGENDARY = ("**Legendary Don Horn x3** and **Legendary Don Meat x3** (monster drops), **Legendary Shiny Diamond x3** "
             "(ore), **Legendary Divine Log x3** (wood), **Legendary Rocket Fish x3** (fish), **Legendary King Spud "
             "x3** (crop). All 5-star, the top tier of crafting materials, for high-end recipes. Each sells for "
             "1,000 Dosh. They can't be handed to other players in multiplayer.")
REDUX = "Redux Stones let you re-forge crafted gear for another roll at its bonus skills."
# (code, occasion, date posted, reward lines)
CODES = [
    ("X43H5MV6", "1st Anniversary", "May 2026", [
        "**Redux Stone x200**. " + REDUX,
        "**Crit Aid+ x5** (4★): big critical-hit-rate boost for 20 seconds",
        "**Berserk Potion+ x5** (4★): +50% Attack but -50% Defense for 60 seconds",
        "**Elixir+ x5** (5★): fully restores HP and SP, then heals HP for 30 more seconds",
        "**De-Paralyzer+ x5** (3★): cures Paralysis for you and your Buddies and heals 10% HP",
        "**Monstroganoff+ x5** (5★ meal): +1,100 HP, +230 SP and +6 Combat Power for 60 seconds"]),
    ("G67W5CLX", "1.5 million copies sold", "January 2026", [LEGENDARY, "**Redux Stone x150**. " + REDUX]),
    ("M53UA8Y2", "Japan Game Awards (Award for Excellence)", "September 2025", [
        "**Salud Glass x1** (2★ crafted item)",
        "**Plate of Trip Cake x1** (5★ crafted item, sells for 4,540 Dosh)",
        "**Trip Doll x1** (5★ crafted item, sells for 4,490 Dosh)",
        "**Redux Stone x100**. " + REDUX]),
    ("Q8RD9AME", "Version 1.5.0 announcement", "August 2025", [
        "**Roast of Legend+ x3** (5★ meal): +1,200 HP and +6 Attack for 60 seconds",
        "**Magical Milkshake+ x3** (5★ dessert): +240 SP and +6 Gathering for 6 attempts",
        "**Ragnarok Salad+ x3** (5★ salad): +230 SP and +6 Crafting for 6 attempts",
        "**Redux Stone x50**. " + REDUX]),
    ("K9E8VADB", "1.2 million copies sold", "July 2025", [LEGENDARY]),
    ("AF579XS2", "1 million copies sold", "June 2025", [
        "**The full Raccoon costume:** Raccoon Head, Raccoon Outfit, Raccoon Mittens and Raccoon Boots, all "
        "5★. Some guides call the boots \"Raccoon Slippers\". The set can't be sold or given away."]),
    ("X95SB4UD", "800,000 copies sold", "June 2025", [
        "**Hi-HP Potion+ x10**: heals 1,200 HP",
        "**Hi-SP Potion+ x10**: recovers 460 SP",
        "**Life Cure+ x5**: revives with full HP"]),
    ("E47LWJGP", "Surprise Dosh gift", "May 2025", [
        "**Sack of Silver x5** (sells for 1,000 Dosh each)",
        "**Sack of Gold x5** (sells for 3,000 Dosh each)",
        "That's **20,000 Dosh** if you sell them all."]),
    ("A5C9X7VR", "500,000 copies sold", "May 2025", [
        "**Diamond Ring x1** (4★ accessory, sells for 5,360 Dosh)",
        "**Corsage x1** (1★ accessory)",
        "**Great Lucky Bream x1** (5★ fish)",
        "**Courtship Fireworks x5** (4★, sets off heart-shaped fireworks)",
        "**Sack of Gold x10** (3,000 Dosh each)",
        "*The Japanese list shows one firework and one Sack of Gold, so your amounts may differ.*"]),
    ("A56LCE87", "Wishlist campaign reward", "May 2025", [
        "**Hi-HP Potion x5**: heals 800 HP",
        "**Hi-SP Potion x5**: recovers 230 SP",
        "**Healing Powder x5**: heals 410 HP for you and your Buddies",
        "**Energy Powder x5**: recovers 100 SP for you and your Buddies",
        "**Life Cure x3**: revives with 50% HP"]),
    ("T2GC6EQL", "Launch celebration", "May 2025", [
        "**HP Potion x5**: heals 200 HP",
        "**SP Potion x5**: recovers 50 SP",
        "**Life Cure x3**: revives with 50% HP",
        "**Power Aid x3**: +20% Attack for 60 seconds",
        "**Resistance Aid x3**: +20% Defense for 60 seconds",
        "**Healing Powder x3**: heals 410 HP for you and your Buddies"]),
]

# ---------- links in #fli-help-and-tips ----------
LINKS = {"title": "Useful links", "colour": BLUE,
         "desc": "- [Official site](https://www.fantasylife.jp/fli/en/): news, FAQ and troubleshooting\n"
                 "- [Patch notes 2.2.0](https://www.fantasylife.jp/fli/en/patchnote/ver_2_2_0/)\n"
                 "- [Gift code guide (official)](https://www.fantasylife.jp/fli/en/guide/password/)\n"
                 "- [Fantasy Life Wiki](https://fantasylife.wiki.gg/): items, recipes, Lives and the update "
                 "history\n"
                 "- Official X: [@FANTASYLIFE_EN](https://x.com/FANTASYLIFE_EN) (English), "
                 "[@L5_fantasylife](https://x.com/L5_fantasylife) (Japanese)\n\n"
                 "**Good to know**\n"
                 "- **Cross-save** links your progress between console, PC and mobile. See *How to Use Cross-Save* "
                 "on the official site.\n"
                 "- **Crossplay** covers every platform, mobile included, since 2.2.0.\n"
                 "- For game news and DLC, check {fli-news}. For codes, see {fli-gift-codes}."}


def welcome_embed() -> dict:
    return {"title": "Welcome to the Reveria Guild Hall", "colour": PINK,
            "desc": "A guild hall for every Fantasy Life game, with the newest, **Fantasy Life i: The Girl Who "
                    "Steals Time**, front and centre.\n\n"
                    "**Start here**\n"
                    "- Read {rules} first. This is an **18+ server**.\n"
                    "- Say hi in {introductions}, then chat in {general}.\n"
                    "- Server news is posted in {announcements}.\n\n"
                    "**Fantasy Life i**\n"
                    "- Game updates and DLC news: {fli-news}\n"
                    "- Every gift code and what it gives: {fli-gift-codes}\n"
                    "- Questions: {fli-help-and-tips}. Lives and skills: {fli-lives-and-skills}. "
                    "Time and events: {fli-time-and-events}.\n"
                    "- Spoilers go **only** in {fli-spoilers}.\n\n"
                    "**Fantasy Life (3DS)**\n"
                    "- News (Origin Island, eShop and online status): {fl-news}\n"
                    "- Every password, sorted by region and language: {fl-passwords}\n"
                    "- Chat: {fl-general}. Questions: {fl-help-and-tips}.\n\n"
                    "**Fantasy Life Online**\n"
                    "- What happened to it, plus the old code archive: {flo-news}\n"
                    "- Memories: {flo-memories}\n\n"
                    "**Also here**\n"
                    "- Mods and save editing: {save-editing} and {modding-help}.\n"
                    "- Chatting earns XP and **license-rank roles** (see {roles})."}


def roles_embed() -> dict:
    ladder = "\n".join(f"- Level **{need}**: **{name}**" for need, name, _ in RANKS)
    return {"title": "License ranks", "colour": GOLD,
            "desc": "Every message earns **15-25 XP**, at most once a minute. As you level up, the bot promotes "
                    "you through Fantasy Life's license ranks:\n\n" + ladder + "\n\n"
                    "**Commands:** `/rank` (your level, or someone else's), `/leaderboard` (top adventurers), "
                    "`/ranks` (this ladder).\n"
                    "Guild Master and Guild Officer are staff roles. They're appointed, not earned."}


def announce_embed() -> dict:
    return {"title": "News and codes for every game", "colour": GOLD,
            "desc": "Every game now has its own news, and its codes where it has them:\n\n"
                    "**Fantasy Life i**\n"
                    "- {fli-news}: update 2.2.0 and the new paid DLC, **The Celestial Express**\n"
                    "- {fli-gift-codes}: all 11 gift codes with exactly what each one gives\n\n"
                    "**Fantasy Life (3DS)**\n"
                    "- {fl-news}: Origin Island, the eShop closure and the end of online play\n"
                    "- {fl-passwords}: all 42 password rewards, sorted by region and language\n\n"
                    "**Fantasy Life Online**\n"
                    "- {flo-news}: the shutdown, plus an archive of its (expired) codes\n\n"
                    "{welcome} has a guide to the whole server."}


def code_embeds() -> list[dict]:
    out = []
    for code, why, when, lines in CODES:
        out.append({"title": f"{code}", "colour": GREEN,
                    "desc": f"**{why}** · posted {when}\n" + "\n".join(f"- {x}" for x in lines)})
    return out


def build(ch: dict[str, str]) -> dict[str, list[list[dict]]]:
    """channel name -> posts (each post = up to 10 embeds); {name} placeholders become channel mentions."""
    def fill(e: dict) -> dict:
        d = e["desc"]
        for name, mention in ch.items():
            d = d.replace("{" + name + "}", mention)
        return {**e, "desc": d}
    codes = code_embeds()
    plan = {
        "welcome": [[welcome_embed()]],
        "roles": [[roles_embed()]],
        "fli-news": [[e] for e in NEWS],
        "fli-gift-codes": [[REDEEM, SORTING]] + [codes[i:i + 4] for i in range(0, len(codes), 4)],
        "fli-help-and-tips": [[LINKS]],
        "fl-news": [[e] for e in classic.FL_NEWS],
        "fl-passwords": classic.fl_password_posts(),
        "flo-news": [[e] for e in classic.FLO_NEWS],
        "announcements": [[announce_embed()]],
    }
    return {name: [[fill(e) for e in post] for post in posts] for name, posts in plan.items()}


def to_embed(e: dict) -> discord.Embed:
    return discord.Embed(title=e["title"], description=e["desc"], colour=e["colour"], url=e.get("url"))


def check_sizes(plan: dict) -> None:
    for name, posts in plan.items():
        for post in posts:
            total = sum(len(e["title"]) + len(e["desc"]) for e in post)
            worst = max(len(e["desc"]) for e in post)
            print(f"#{name}: {len(post)} embed(s), {total} chars (longest description {worst})")
            assert len(post) <= 10 and total <= 6000 and worst <= 4096, f"#{name} post too big"


async def ensure_channels(g: discord.Guild) -> list[str]:
    me, missing = g.me, [n for n in NEW_CHANNELS if not discord.utils.get(g.text_channels, name=n)]
    if missing and not me.guild_permissions.manage_channels:
        return missing
    for name, (category, topic) in NEW_CHANNELS.items():
        ch = discord.utils.get(g.text_channels, name=name)
        if ch is None:
            cat = discord.utils.get(g.categories, name=category)
            ch = await g.create_text_channel(name, category=cat, topic=topic, nsfw=True,
                                             reason="Game news and codes")
            siblings = [n for n, (c, _) in NEW_CHANNELS.items() if c == category]
            await ch.move(beginning=True, category=cat, offset=siblings.index(name))
            print("created", "#" + name)
        if me.guild_permissions.manage_channels:
            await ch.set_permissions(g.default_role, send_messages=False, create_public_threads=False,
                                     create_private_threads=False, add_reactions=True)
            await ch.set_permissions(me.top_role, view_channel=True, send_messages=True, embed_links=True,
                                     read_message_history=True)
    return []


async def our_posts(client: discord.Client, ch: discord.TextChannel) -> dict[str, discord.Message]:
    ours = {}
    async for m in ch.history(limit=100):
        if m.author == client.user and m.embeds and m.embeds[0].title:
            ours.setdefault(m.embeds[0].title, m)
    return ours


async def publish(client: discord.Client, ch: discord.TextChannel, posts: list[list[dict]]) -> None:
    ours = await our_posts(client, ch)
    for post in posts:
        embeds = [to_embed(e) for e in post]
        old = ours.get(post[0]["title"])
        if old:
            await old.edit(content=None, embeds=embeds)
        else:
            await ch.send(embeds=embeds)
    print(f"#{ch.name}: {len(posts)} post(s) {'updated' if ours else 'posted'}")


async def run(client: discord.Client) -> None:
    g = discord.utils.get(client.guilds, name=GUILD_NAME)
    skipped = await ensure_channels(g)
    ch = {c.name: c.mention for c in g.text_channels}
    for name in skipped:
        ch[name] = ch[FALLBACK[name]]
    plan = build(ch)
    check_sizes(plan)
    for name in skipped:
        plan.setdefault(FALLBACK[name], []).extend(plan.pop(name))
        print(f"#{name} can't be created (no Manage Channels): its posts go to #{FALLBACK[name]}")
    # a post lives in exactly one channel: the bot's copies elsewhere (old stand-ins) are deleted
    home = {post[0]["title"]: name for name, posts in plan.items() for post in posts}
    for c in g.text_channels:
        if not c.permissions_for(g.me).read_message_history:
            continue
        for title, m in (await our_posts(client, c)).items():
            if title in home and home[title] != c.name:
                await m.delete()
                print(f"removed '{title}' from #{c.name} (it lives in #{home[title]})")
    for name, posts in plan.items():
        await publish(client, discord.utils.get(g.text_channels, name=name), posts)


def main() -> None:
    if "--dry" in sys.argv:
        check_sizes(build({}))
        return
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
