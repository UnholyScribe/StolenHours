# Stolen Hours

A free save editor for **Fantasy Life i: The Girl Who Steals Time** (PC, Steam).

![Adventurer](images/adventurer.png)

## Download

Get the latest zip from [Releases](../../releases), unzip it anywhere and run `StolenHours.exe`.
Nothing to install: it finds Steam, the game and your save by itself.

Needs Windows 10 or 11 (with the Microsoft Edge WebView2 runtime, which Windows already has) and the game installed
through Steam.

## What it does

| Tab | What you can change |
|---|---|
| Adventurer | Name, Dosh, island name, play time |
| Licenses | Level, exp and rank of every Life |
| Skill boards | Learn or reset skill panels |
| Bag | Item amounts, add new items to any pocket |
| Look | Your appearance, with a 3D preview |
| Map | Which map events show up, time and weather |
| Live Map | Every map with towers, towns, shrines, shops, campfires, gathering spots and monsters; live map events and where you are while the game runs |
| Time Hook | Change the running game (Dosh) |
| Records | Your play records |
| Backups | Automatic backups, one-click restore |

The Live Map's places work on their own; its live events, your position and the Time Hook need [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) in the game. The editor installs its own
small mod for you (from either tab) once UE4SS is there. Everything else works on the save file alone.

## Every tab

| | |
|---|---|
| **Adventurer**<br>![Adventurer](images/adventurer.png) | **Licenses**<br>![Licenses](images/licenses.png) |
| **Skill board**<br>![Skill board](images/skillboard.png) | **Bag**<br>![Bag](images/bag.png) |
| **Look**<br>![Look](images/look.png) | **Map**<br>![Map](images/map.png) |
| **Live Map**<br>![Live Map](images/livemap.png) | **Time Hook**<br>![Time Hook](images/timehook.png) |
| **Records**<br>![Records](images/records.png) | **Backups**<br>![Backups](images/backups.png) |

## Keeping your save safe

- It won't write while the game is running. Close the game before you press **Save to file**.
- A save only opens if it decrypts and repacks byte for byte, so the editor never works on a file it can't fully read.
- Before every write it makes a backup with a SHA-256, writes the new file in one go and reads it back to check it.
- If the game saved since you opened the file, it refuses to overwrite it.

Still, keep your own copy of your save. Use it offline and at your own risk; don't take edited saves into multiplayer.


## Credits

- Built by Unholy with his friend Tock, his AI coding partner.
- Item, flag and skill lists from Niedzielan's fli_save_editor.
- Fantasy Life i is © LEVEL-5. This is a fan-made tool, not affiliated with or endorsed by LEVEL-5.
