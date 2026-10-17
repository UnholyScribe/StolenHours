"""Move a bot token from the clipboard into .env without ever printing it, then clear the clipboard.

Copy the token in the Developer Portal first, then run:  py -3.12 set_token.py
"""

import re
import subprocess
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}$")


def main() -> None:
    clip = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                          capture_output=True, text=True).stdout.strip()
    if not TOKEN.match(clip):
        raise SystemExit("The clipboard doesn't hold a bot token. Click Copy under the token and run this again.")
    old = ENV.read_text(encoding="ascii").strip().removeprefix("DISCORD_TOKEN=") if ENV.exists() else ""
    if clip == old:
        raise SystemExit("That is the token already in .env; reset the token first to get a new one.")
    ENV.write_text(f"DISCORD_TOKEN={clip}\n", encoding="ascii")
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"])
    print(f"Saved the new token to .env ({len(clip)} characters) and cleared the clipboard.")


if __name__ == "__main__":
    main()
