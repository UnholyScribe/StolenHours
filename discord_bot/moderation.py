"""Reveria Guild Hall rules, the AutoMod filters that enforce them, and the strike ladder.

AutoMod (Discord's own filter) blocks rule-breaking messages even while the bot is offline; the bot counts each block
as a strike and times repeat offenders out. Bullying needs judgement, so it is handled through member reports.
"""

from __future__ import annotations

from datetime import timedelta

import discord

MOD_LOG = "mod-log"
RULES_CHANNEL = "rules"
# read-only for members; the bot and the owner post there
LOCKED_CHANNELS = ("welcome", "rules", "announcements", "roles", "fl-news", "fl-passwords", "flo-news", "fli-news",
                   "fli-gift-codes")
# everything else is age-restricted: adult content is allowed, and Discord requires it to sit behind the 18+ gate
UNGATED_CHANNELS = ("welcome", "rules")

AGE_BANNER = ("# 18+ ONLY\n"
              "**This server is for adults. If you are not 18 or older, leave now. You don't belong here.**\n"
              "Nudity and adult content are allowed. Every channel past this one is age-restricted.")

RULES = [
    ("Talk about anything",
     "Anything goes, games, life, memes, adult stuff, except the few things below."),
    ("No politics",
     "No parties, politicians, elections or hot-button political issues. Take it somewhere else."),
    ("No religion",
     "No preaching, debating or bashing any faith, or the lack of one."),
    ("No bullying",
     "**Bullying** is deliberately targeting a specific person, again and again or after they've asked you to stop, "
     "to hurt, humiliate, intimidate or isolate them. That includes:\n"
     "- keeping on at someone who asked you to stop, or following them into other channels or DMs\n"
     "- dogpiling: getting others to gang up on one person\n"
     "- threats of any kind\n"
     "- slurs, or attacking who someone *is* (race, ethnicity, nationality, gender, sexuality, disability)\n"
     "- doxxing: posting someone's real name, address, photos or other personal info\n"
     "- posting someone's pictures or messages to mock them\n"
     "**Not bullying:** trash talk, banter, roasting, or someone calling you an idiot in an argument. "
     "Grow some tougher skin. If it really crosses the line, right-click the message, then "
     "**Apps > Report to the Guild**."),
    ("No illegal content or piracy",
     "No ROMs, ISOs, NSPs/XCIs, cracked or \"free\" games, piracy sites, torrents or leaked keys. Nothing that can "
     "get anyone in trouble. Mods and save editing for games **you own** are fine: that's what this place is for. "
     "And obviously nothing illegal at all: anything sexual involving minors is an instant ban and gets reported, "
     "and so are intimate images shared without consent."),
]
ENFORCEMENT = ("AutoMod blocks posts that break these rules and every block is a strike. "
               "3 strikes in 24 hours = 1 hour timeout, 5 = 1 day timeout. Staff handle reports and bans. "
               "The Guild Master's word is final.")


def rules_embeds() -> list[discord.Embed]:
    banner = discord.Embed(description=AGE_BANNER, colour=0xE74C3C)
    rules = discord.Embed(title="Reveria Guild Hall: the rules", colour=0xF1C40F)
    for i, (name, text) in enumerate(RULES, 1):
        rules.add_field(name=f"{i}. {name}", value=text, inline=False)
    rules.add_field(name="Enforcement", value=ENFORCEMENT, inline=False)
    return [banner, rules]


# AutoMod keyword rules: whole words unless wrapped in *. Fantasy Life's own "God" rank is why "god" is not listed.
FILTERS = {
    "No politics": [
        "politics", "political", "politician*", "trump", "biden", "kamala", "obama", "maga", "democrat*",
        "republican*", "gop", "dnc", "rnc", "leftist*", "left-wing", "right-wing", "liberals", "conservatives",
        "election*", "ballot*", "congress", "senator*", "abortion*", "pro-life", "pro-choice", "immigration",
        "communism", "communist*", "socialism", "fascism", "fascist*", "antifa",
    ],
    "No religion": [
        "religion*", "religious", "jesus", "christ", "christian*", "christianity", "bible*", "church*", "muslim*",
        "islam*", "allah", "quran", "koran", "mosque*", "jewish", "judaism", "torah", "synagogue*", "hindu*",
        "buddhis*", "atheis*", "scripture*", "preach*", "sermon*", "satanis*",
    ],
    "No piracy": [
        "rom", "roms", "romset*", "*.nsp", "*.xci", "nsp", "xci", "nsz", "xcz", "*.3ds", "*.cia", "torrent*",
        "magnet:*", "pirated", "piracy", "cracked game*", "game crack*", "warez", "free download*",
        "*fitgirl*", "*dodi-repacks*", "*steamunlocked*", "*igg-games*", "*nxbrew*", "*ziperto*", "*nswgame*", "*romsfun*", "*hexrom*",
        "*romspure*", "*vimm.net*", "*emuparadise*", "*cdromance*", "*nopaystation*", "*myrient*", "*rutracker*",
        "*1337x*", "*thepiratebay*", "*gamesdrive*", "*skidrow*", "*ovagames*", "*crackwatch*",
    ],
}
BLOCK_MESSAGES = {
    "No politics": "Rule 2: no politics in Reveria Guild Hall.",
    "No religion": "Rule 3: no religion in Reveria Guild Hall.",
    "No piracy": "Rule 5: no ROMs, piracy or free-game links here.",
    "Slurs": "Rule 4: slurs aren't allowed here.",
    "Mention spam": "Too many mentions in one message.",
}

STRIKE_WINDOW = timedelta(hours=24)
# strikes inside the window -> timeout length
STRIKE_TIMEOUTS = [(5, timedelta(days=1)), (3, timedelta(hours=1))]


def timeout_for(strikes: int) -> timedelta | None:
    for need, length in STRIKE_TIMEOUTS:
        if strikes >= need:
            return length
    return None
