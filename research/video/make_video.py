"""Render the captioned Stolen Hours tour video from the scene screenshots.

usage: py -3.12 research/video/make_video.py [scene_dir] [out.mp4]
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / "editor" / "stolenhours" / "webgui" / "web" / "game"
SCENES = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Pictures" / "Stolen Hours" / "video"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else SCENES.parent / "Stolen Hours - Tour.mp4"

W, H, FPS = 1920, 1080, 30
HOLD, FADE = 5.0, 0.6
CAPTION_H = 190

# (screenshot or None for a title card, heading, caption line)
SCRIPT = [
    (None, "Stolen Hours", "A save editor for Fantasy Life i: The Girl Who Steals Time (PC)"),
    ("vid_01_overview.png", "Adventurer", "Change your name, Dosh, island name and play time."),
    ("vid_02_lives.png", "Licenses", "Set the level, exp and rank of every Life."),
    ("vid_03_board.png", "Skill Boards", "Learn or reset skill panels. Click to learn, right-click to forget."),
    ("vid_04_bag.png", "Bag", "Change item amounts or add new items to any pocket."),
    ("vid_05_look.png", "Look", "Change your appearance, with a 3D preview of your character."),
    ("vid_06_map.png", "Map", "Pick which map events show up, and set the time and weather."),
    ("vid_07_livemap.png", "Live Map", "Every map with its towns, towers and more, plus live events and where you are."),
    ("vid_08_timehook.png", "Time Hook", "Change the running game. Needs UE4SS; the editor installs its own mod."),
    ("vid_09_records.png", "Records", "Your play records, and a check that the save is safe to write."),
    ("vid_10_backups.png", "Backups", "A backup is made before every save. Restore any of them in one click."),
    (None, "Made by Unholy and Tock", "Built by Unholy with his friend Tock, his AI coding partner."),
    (None, "Close the game before saving", "Download link in the description. Use offline, at your own risk."),
]


def font(name, size):
    return ImageFont.truetype(str(GAME / "fonts" / name), size)


def background():
    wp = Image.open(GAME / "wallpaper.jpg").convert("RGB")
    scale = max(W / wp.width, H / wp.height)
    wp = wp.resize((round(wp.width * scale), round(wp.height * scale)), Image.LANCZOS)
    left, top = (wp.width - W) // 2, (wp.height - H) // 2
    wp = wp.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(6))
    return Image.blend(wp, Image.new("RGB", (W, H), (20, 14, 8)), 0.35)


def centered(draw, y, text, fnt, fill, stroke=0):
    width = draw.textlength(text, font=fnt)
    draw.text(((W - width) / 2, y), text, font=fnt, fill=fill,
              stroke_width=stroke, stroke_fill=(60, 35, 10))


def caption(img, heading, line):
    band = Image.new("RGBA", (W, CAPTION_H), (30, 20, 10, 200))
    img.paste(band, (0, H - CAPTION_H), band)
    d = ImageDraw.Draw(img)
    centered(d, H - CAPTION_H + 28, heading, font("heading.otf", 58), (255, 214, 120), 3)
    centered(d, H - CAPTION_H + 112, line, font("body_bold.otf", 40), (255, 250, 240))


def scene(bg, shot, heading, line):
    img = bg.copy()
    if shot is None:
        d = ImageDraw.Draw(img)
        centered(d, H // 2 - 130, heading, font("heading.otf", 120), (255, 214, 120), 5)
        centered(d, H // 2 + 40, line, font("body_bold.otf", 46), (255, 250, 240), 2)
        return img
    pic = Image.open(SCENES / shot).convert("RGB")
    ph = H - CAPTION_H - 50
    pw = round(pic.width * ph / pic.height)
    pic = pic.resize((pw, ph), Image.LANCZOS)
    x, y = (W - pw) // 2, 25
    shadow = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((20, 20, pw + 20, ph + 20), 24, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img.paste(shadow, (x - 20, y - 12), shadow)
    img.paste(pic, (x, y))
    caption(img, heading, line)
    return img


def main():
    bg = background()
    stills = [scene(bg, *s) for s in SCRIPT]
    hold, fade = round(HOLD * FPS), round(FADE * FPS)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-movflags", "+faststart", str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    black = Image.new("RGB", (W, H))
    frames = 0
    for i, still in enumerate(stills):
        raw = still.tobytes()
        start = fade if i == 0 else 0
        for f in range(start):
            proc.stdin.write(Image.blend(black, still, f / fade).tobytes())
        for _ in range(hold):
            proc.stdin.write(raw)
        nxt = stills[i + 1] if i + 1 < len(stills) else black
        for f in range(1, fade + 1):
            proc.stdin.write(Image.blend(still, nxt, f / fade).tobytes())
        frames += start + hold + fade
    proc.stdin.close()
    if proc.wait():
        sys.exit(f"ffmpeg failed ({proc.returncode})")
    print(f"{OUT}  {frames / FPS:.1f}s")


if __name__ == "__main__":
    main()
