"""News and codes posts for the older games: Fantasy Life (3DS) and Fantasy Life Online.

Sources (checked 2026-10-12): fantasylife.wiki.gg Passwords (table from Nintendo's regional X accounts); Nintendo
support (3DS eShop purchases ended 2023-03-27, 3DS online services ended 2024-04-08); Siliconera / Nintendo Insider
(Origin Island in the West); Famitsu / Anime News Network (FLO Japan end 2021-12-15); Nintendo Connect / MMOs.com
(FLO global end 2023-02-06); Gfinity (FLO code list, all expired).
"""

from __future__ import annotations

BLUE, GREEN, GREY, PURPLE = 0x3498DB, 0x2ECC71, 0x95A5A6, 0x9B59B6

# ---------- Fantasy Life (3DS) ----------
FL_NEWS = [
    {"title": "Fantasy Life (3DS): where things stand", "colour": BLUE,
     "desc": "**Released:** Japan December 27, 2012; Europe September 26, 2014; North America October 24, 2014. "
             "The Western release is the enhanced *Fantasy Life Link!* version with online co-op built in.\n\n"
             "**Origin Island DLC** adds a new island, more story, higher Life ranks, stronger gear, and bird and "
             "dragon pets. It **can no longer be bought**: the 3DS eShop stopped all purchases on **March 27, "
             "2023**. If you already own it, you can still **redownload** it.\n\n"
             "**Online play ended on April 8, 2024**, when Nintendo shut down 3DS online services. That covers "
             "online co-op and data distribution. **Local wireless co-op still works**, and so does everything "
             "single-player.\n\n"
             "**Passwords still work.** They're typed in the game and don't use the internet. See {fl-passwords}.\n\n"
             "The series continues with **Fantasy Life i: The Girl Who Steals Time** (2025). Its news is in "
             "{fli-news}."},
]

# reward -> what it is; the order matches the wiki table
PW_KIND = {
    "Honey Pudding": "food", "Butler's Outfit": "outfit", "Cute Outfit": "outfit", "Angel Costume": "outfit",
    "Demon Costume": "outfit", "Dancer's Outfit": "outfit", "Dragon Tamer Costume": "outfit",
    "Spring Indoor Decoration Set": "home", "Spring Outdoor Decoration Set": "home", "Sailor's Outfit": "outfit",
    "Summer Fun Costume": "outfit", "Summer Outdoor Decoration Set": "home", "Island Resort Decoration Set": "home",
    "Pool Decoration Set": "home", "Mysterious Costume": "outfit", "Witch's Hat": "outfit",
    "Pumpkin Outfit": "outfit", "Halloween Furniture Set": "home", "Festive Costume": "outfit",
    "Festive Furniture Set": "home", "Elegant Outfit": "outfit", "Frilly Outfit": "outfit", "Heart Rug": "home",
    "Sweet Furniture Set": "home", "Cacto Costume": "outfit", "Ninja Costume": "outfit",
    "Fluffkin Costume": "outfit", "Sheep Outfit": "outfit", "Plushling Outfit": "outfit",
    "Princely Outfit": "outfit", "Yippee-Ki-Yay Costume": "outfit", "Snowman Outfit": "outfit",
    "Snowman (Decoration)": "home", "Snow Outfit": "outfit", "Laura's Hat": "outfit", "Yuelia's Outfit": "outfit",
    "Choco Mat": "home", "Fairy Doll": "home", "Teddy Bear": "home", "Toy Camel": "home",
    "Football Pitch": "home", "Cuddly Sea Turtle": "home",
}
REGIONS = ["North America (English)", "UK & Australia (English)", "France (French)", "Germany (German)",
           "Italy (Italian)", "Spain (Spanish)"]
PASSWORDS = [
    ("Honey Pudding", "Reveria", "Reveria", "Rêveria", "Reveria", "Reveria", "Reveria"),
    ("Butler's Outfit", "Butting in", "At your service", "À votre service", "Zu Diensten", "Al tuo servizio!", "A su servicio"),
    ("Cute Outfit", "Exceedingly cute", "Cutie pie", "Mignonnette", "Spitzenspätzchen", "Ehi, dolcezza!", "Qué monada"),
    ("Angel Costume", "I'm finished!", "Angelic chorus", "Chœur angélique", "Engelschor", "Coro angelico", "Coro celestial"),
    ("Demon Costume", "Fiendish fashion", "Fiery fiend", "Furie démoniaque", "Feurige Furie", "Demoni birboni", "Ferocidad feroz"),
    ("Dancer's Outfit", "Got the fever?", "Lady of the ball", "La reine du bal", "Juwel des Balls", "Regina ballerina", "Reina del baile"),
    ("Dragon Tamer Costume", "Fired up!", "Dragon tamer", "Dompte le dragon", "Drachenzähmer", "Doma il drago!", "Domadragones"),
    ("Spring Indoor Decoration Set", "Spring Cleaning", "Spring flowers", "Air printanier", "Frühlingsblumen", "Fiori in boccio", "Flor primaveral"),
    ("Spring Outdoor Decoration Set", "Spring fling", "Life in bloom", "Vie florissante", "In voller Blüte", "Prati in fiore", "Brote de color"),
    ("Sailor's Outfit", "Sailor's delight", "Seasick sailors", "Marins nauséeux", "Ahoi Matrose!", "Mal di mare", "Marinos mareados"),
    ("Summer Fun Costume", "Beach Bum", "Fun in the sun", "Au soleil", "Sonniger Spaß", "Festa al sole", "Fiesta al sol"),
    ("Summer Outdoor Decoration Set", "Don Gero!", "Croakie dokie", "Croâ croâ", "Alles krächzens", "Cra cra cra", "¡Croac, croac!"),
    ("Island Resort Decoration Set", "Forgot my lotion", "Surf's up!", "Vive les vagues", "Wellenreiten", "Cavalca l'onda!", "¡A la playa!"),
    ("Pool Decoration Set", "Floating fun", "Splish splosh", "Plouf plouf", "Plitsch, platsch", "Splash splash", "Plaf, chof"),
    ("Mysterious Costume", "Alakazam", "Abracadabra", "Abracadabra", "Abrakadabra", "Abracadabra", "Abracadabra"),
    ("Witch's Hat", "Witching hour", "Toil and trouble", "Vilaine sorcière", "Harte Arbeit", "Giro giro tondo", "Pata de cabra"),
    ("Pumpkin Outfit", "Seedy deeds", "Jack-o'-Lantern", "Citrouilles", "Kürbislaterne", "Zucca vuota", "Calabasusto"),
    ("Halloween Furniture Set", "Trick or Treat!", "Trick or treat?", "Joyeux Halloween", "Schaurig schön", "Dolcetto o...", "¿Susto o chuche?"),
    ("Festive Costume", "Forever festive", "Winter wonders", "Joyeux Noël !", "Frohes Fest!", "Gioia invernale", "Felices fiestas"),
    ("Festive Furniture Set", "Just add cookies", "Chimneypot Claus", "Ramoneur d'hiver", "Kamin-Klaus", "Viva le feste", "Papá no es"),
    ("Elegant Outfit", "Strike a pose", "Cute chic", "Féru de mode", "Mode-Guru", "Viva la moda!", "A la última"),
    ("Frilly Outfit", "Lace case", "Frilliant!", "Style frivole", "Rüschtastisch!", "Decora e rimira!", "¡Volantástico!"),
    ("Heart Rug", "Love-ly carpet", "Huggable rug", "Tapis mimi", "Kuschelvorleger", "Comodo tappeto", "Alfombra mimosa"),
    ("Sweet Furniture Set", "Sweet Furniture", "Sweet treats", "Douceurs sucrées", "Süßer Genuss", "Dolci sorprese", "Dulce sorpresa"),
    ("Cacto Costume", "Pokey pretender", "Prickly poser", "Tenues épineuses", "Stachelige Mode", "Faccende spinose", "Disfraz espinoso"),
    ("Ninja Costume", "Masked Mercenary", "Vanishing act", "Comme par magie", "Aus dem Nichts", "Puff... sparito!", "¡Chas! ¡No está!"),
    ("Fluffkin Costume", "Fur couture", "Fluffkin facade", "Style Fourruchon", "Pelzling-Mode", "Caro pelliccione", "Pelpuréate"),
    ("Sheep Outfit", "Shear Comfort", "A bit sheepish", "Mouton noir", "Etwas belämmert", "Pecora nera", "Balando voy..."),
    ("Plushling Outfit", "Pretty in plush", "Plushling parade", "Style Mascotton", "Knufflingsparade", "Nimbossibile!", "Desfile peluche"),
    ("Princely Outfit", "Not charming", "Princely threads", "Tenue princière", "Prinzen-Pracht", "Principe azzurro", "Hilos reales"),
    ("Yippee-Ki-Yay Costume", "Ride 'em cowboy", "Buckin' bronco", "Cheval sauvage", "Bockendes Pferd", "Toro meccanico", "Potro desbocado"),
    ("Snowman Outfit", "Stay frosty!", "Slippery snowman", "Costume hivernal", "Mann aus Schnee", "Nobile nevischio", "Señor resbalón"),
    ("Snowman (Decoration)", "Wanna build me?", "Snowman-ia!", "Boule de neige", "Schneespaß", "Naso di carota", "Don Níveo"),
    ("Snow Outfit", "Snow daze!", "Snow joke", "Drôle de neige", "Frostiger Spaß", "Nevica!", "Broma nívea"),
    ("Laura's Hat", "Hidden princess", "Laura lookalike", "Sosie de Laura", "Doppelte Laura", "Sosia di Laura", "Fan de Laura"),
    ("Yuelia's Outfit", "Moonerfly magic", "All of a flutter", "Style Flotillon", "Flatterling-Mode", "Franfalla chic", "Estilo Maripósea"),
    ("Choco Mat", "A little peckish", "Tiny treat", "Petit plaisir", "Kleiner Genuss", "Sorpresina", "Date un homenaje"),
    ("Fairy Doll", "Dolled up", "All dolled up", "Vieux amis", "Puppenspieler", "Vecchi amici", "Viejos amigos"),
    ("Teddy Bear", "Un-bear-able", "Yummy honey bear", "Petit ourson", "Leckerhonig-Bär", "Orso golosone", "Oso meloso"),
    ("Toy Camel", "Spittin' image", "Sandy snuggles", "Câlins ensablés", "Kuschel-Höcker", "Sella di sabbia", "Abrazos arenosos"),
    ("Football Pitch", "Sports ball", "On the ball", "Balle au centre", "Am Ball", "Palla al centro", "¡Gol!"),
    ("Cuddly Sea Turtle", "Shell of a time", "Timid turtle", "Tortue timide", "Süße Schildkröte", "Timida tartaruga", "Tortuga tímida"),
]
KIND_LABEL = {"outfit": "Outfits and costumes (wearable)", "home": "Furniture and decorations (for your home)",
              "food": "Food"}

FL_HOWTO = {"title": "How 3DS passwords work", "colour": GREEN,
            "desc": "1. Finish Flutter's request **Tale of the Goddess**. That unlocks the **Password Clerk**.\n"
                    "2. Go to the **post office in Castele Square** and talk to the Password Clerk behind the "
                    "counter.\n"
                    "3. Type the password **exactly**: capitals, spaces and punctuation all count.\n\n"
                    "**Sorted by region:** Nintendo posted different passwords in each region and language. The "
                    "password that works depends on your **game's language**, not where you live. Use the list "
                    "for the language your game runs in. The wiki notes that switching the game's language lets "
                    "you redeem another region's version of an item.\n\n"
                    "Every reward is listed once per region below: 42 in all. Most are outfits; the rest are "
                    "furniture and decoration sets for your home, plus one food."}


def fl_password_posts() -> list[list[dict]]:
    posts = [[FL_HOWTO]]
    for col, region in enumerate(REGIONS, start=1):
        lines = []
        for kind, label in KIND_LABEL.items():
            rows = [f"{r[0]}: `{r[col]}`" for r in PASSWORDS if PW_KIND[r[0]] == kind]
            lines.append(f"**{label}**\n" + "\n".join(rows))
        posts.append([{"title": f"Passwords: {region}", "colour": GREEN, "desc": "\n\n".join(lines)}])
    posts.append([{"title": "Passwords: Japan (Japanese)", "colour": GREEN,
                   "desc": "Japanese copies use different passwords, handed out at events and with merchandise. "
                           "Two are known:\n"
                           "- **Cowboy Set:** `ロデオできめろカウボーイ`\n"
                           "- **Devil Set:** `まっかなスイートリトルデビル`\n\n"
                           "The bulletin board on the left wall of the Castele post office also gives clues to "
                           "Japanese passwords."}])
    return posts


# ---------- Fantasy Life Online ----------
FLO_NEWS = [
    {"title": "Fantasy Life Online has shut down", "colour": GREY,
     "desc": "**Fantasy Life Online** was LEVEL-5's free-to-play mobile Fantasy Life for iOS and Android. It "
             "started life as *Fantasy Life 2: Twin Moons and the Sacred Village*.\n\n"
             "- **Japan:** launched July 23, 2018; **service ended December 15, 2021**.\n"
             "- **Worldwide** (published by Boltrend Games): launched December 7, 2021. Purchases stopped and "
             "the game left the app stores on December 13, 2022; **servers closed February 6, 2023**.\n\n"
             "The game can't be played anymore: it needed its servers. Unused paid currency was refunded during "
             "the shutdown window, which has also closed.\n\n"
             "Share your memories and screenshots in {flo-memories} and {flo-screenshots}."},
    {"title": "Fantasy Life Online codes (archive, all expired)", "colour": GREY,
     "desc": "These were the worldwide version's promo codes. **None work anymore**: they were confirmed expired "
             "on December 6, 2022, and the servers are gone. They're kept here for the record.\n\n"
             "- `FLOxDiscord5k`: 50 diamonds\n"
             "- `FLOxDISCORD`, `FLOxFB`, `FLOxKangGaming`: 40 diamonds each\n"
             "- `FLOxZennosh`, `FLOxMF`, `FLOxDerker`: 20 diamonds each\n"
             "- `FLOxSS`, `FLOxVA`, `FLOxPROAPK`, `FLOxKG`, `FLOxPapi`, `FLOxARedCloud`, `FLOxHayzink`: 20 "
             "diamonds, 2 Life Cures and 5 XP orbs each\n\n"
             "Diamonds were the game's premium currency."},
]
