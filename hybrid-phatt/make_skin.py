"""Hybrid Phatt skin: an MPC 60 x E-mu Phatt hardware look for the MPC touch screen.

Draws every picture (textured metal pages with printed section boxes, black knurled knobs with red
LED rings, chrome vertical faders, grey key caps with LEDs, the backlit LCD) and writes the
hand-written Plugin Skins (TUI.json + Q-Links.json) into skins/. build.py then copies skins/ verbatim.

    python tools/build.py "plugins/Hybrid Phatt"        (makes build/params.json)
    python "plugins/Hybrid Phatt/make_skin.py"
    python tools/build.py "plugins/Hybrid Phatt"        (copies skins/ into the plugin)
"""
import json
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "skins")
W, H = 1280, 628                      # a tab's content area
FRAMES = 128
SS = 3                                # supersampling for smooth knobs

# palette
INK = (38, 34, 43)
INK_SOFT = (60, 54, 68)
PURPLE_TOP, PURPLE_BOT = (94, 70, 131), (69, 48, 95)
LED = (255, 59, 34)
LCD_BG = (174, 189, 98)
LCD_FG = (29, 35, 16)
VALUE_TXT = "ffff4b2e"
LCD_TXT = "ff1d2310"

# ------------------------------------------------------------------ fonts
def font(size, weight="SemiBold Condensed"):
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", size)
        f.set_variation_by_name(weight)
        return f
    except Exception:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)


def text_center(d, cx, cy, text, f, fill, spacing=0):
    if spacing:
        text = (" " * 0).join(text)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), text, font=f, fill=fill)


def spaced(s, n=1):
    return (" " * n).join(s) if False else s


# ------------------------------------------------------------------ metal plate
def metal_plate(w, h, seed=1):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None]
    top, mid, bot = np.array([205, 200, 188]), np.array([189, 183, 170]), np.array([172, 165, 152])
    g = np.empty((h, w, 3), np.float32)
    t = np.clip(y / 0.4, 0, 1)
    u = np.clip((y - 0.4) / 0.6, 0, 1)
    col = np.where(y < 0.4, top + (mid - top) * t, mid + (bot - mid) * u)    # (h,1,3) broadcast
    g[:] = col[:, None, :] if col.ndim == 2 else col
    grain = rng.normal(0, 1, (h, w)).astype(np.float32)
    streak = rng.normal(0, 1, (h, 1)).astype(np.float32)                   # faint horizontal brushing
    g += (grain * 5.0 + streak * 2.5)[..., None]
    img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(0.4))
    return img.convert("RGBA")


def screw(d, x, y, r=6):
    d.ellipse((x - r, y - r, x + r, y + r), fill=(120, 116, 108), outline=(70, 66, 60))
    d.ellipse((x - r + 2, y - r + 2, x + r - 3, y + r - 3), fill=(205, 202, 195))
    d.line((x - r + 3, y + r - 3, x + r - 3, y - r + 3), fill=(80, 76, 70), width=2)


def panel_box(img, x, y, w, h, title):
    d = ImageDraw.Draw(img)
    # printed outline with a light line under it (looks silk-screened onto metal)
    d.rounded_rectangle((x + 1, y + 1, x + w, y + h), radius=6, outline=(255, 255, 255, 110), width=2)
    d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=6, outline=INK_SOFT + (150,), width=2)
    if title:
        f = font(17, "Bold Condensed")
        l, t, r, b = d.textbbox((0, 0), title, font=f)
        tw = r - l + 26
        tab = Image.new("RGBA", (tw, 26))
        td = ImageDraw.Draw(tab)
        for i in range(26):
            c = tuple(int(PURPLE_TOP[k] + (PURPLE_BOT[k] - PURPLE_TOP[k]) * i / 25) for k in range(3))
            td.line((0, i, tw, i), fill=c + (255,))
        mask = Image.new("L", (tw, 26), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw - 1, 25), radius=3, fill=255)
        img.paste(tab, (x + 12, y - 12), mask)
        d.text((x + 25 - l, y - 12 + (26 - (b - t)) / 2 - t), title, font=f, fill=(239, 232, 247))
    for sx, sy in ((x + 10, y + h - 10), (x + w - 11, y + h - 10)):
        screw(d, sx, sy, 5)


def led_window(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x - 1, y - 1, x + w, y + h + 1), radius=4, fill=(255, 255, 255, 90))
    d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=4, fill=(12, 10, 10), outline=(0, 0, 0))
    d.line((x + 3, y + 2, x + w - 4, y + 2), fill=(40, 36, 36), width=1)


def silk(img, cx, cy, text, size=18):
    d = ImageDraw.Draw(img)
    f = font(size)
    text_center(d, cx, cy + 1, text.upper(), f, (255, 255, 255, 120))
    text_center(d, cx, cy, text.upper(), f, INK)


def lcd(img, x, y, w, h):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x - 8, y - 8, x + w + 8, y + h + 8), radius=8, fill=(20, 19, 22), outline=(0, 0, 0))
    d.rounded_rectangle((x - 9, y - 9, x + w + 9, y + h + 9), radius=9, outline=(255, 255, 255, 100), width=1)
    arr = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    glow = 1.0 - 0.18 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h * 0.4) / (h / 1.2)) ** 2)
    arr[:] = np.array(LCD_BG, np.float32)
    arr *= glow[..., None]
    arr[(yy % 3) == 2] *= 0.94                                             # pixel rows
    arr[:6] *= 0.8
    img.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA"), (x, y))


# ------------------------------------------------------------------ knob film strips
def radial(K, cx, cy, r, inner, outer, power=1.0):
    yy, xx = np.mgrid[0:K, 0:K]
    t = np.clip(np.hypot(xx - cx, yy - cy) / r, 0, 1) ** power
    a = np.array(inner, np.float32)[None, None]
    b = np.array(outer, np.float32)[None, None]
    return (a + (b - a) * t[..., None]).astype(np.uint8)


def knob_body(S):
    K = S * SS
    img = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    c = K / 2
    # soft shadow
    sh = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((c - 0.37 * K, c - 0.33 * K, c + 0.37 * K, c + 0.41 * K), fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(K * 0.03)))
    # skirt with knurled edge
    skirt = Image.fromarray(radial(K, c - 0.08 * K, c - 0.1 * K, 0.42 * K, (70, 70, 76), (8, 8, 10), 0.8)).convert("RGBA")
    m = Image.new("L", (K, K), 0)
    ImageDraw.Draw(m).ellipse((c - 0.36 * K, c - 0.36 * K, c + 0.36 * K, c + 0.36 * K), fill=255)
    img.paste(skirt, (0, 0), m)
    d = ImageDraw.Draw(img)
    for i in range(72):
        a = 2 * math.pi * i / 72
        r1, r2 = 0.30 * K, 0.355 * K
        col = (0, 0, 0, 200) if i % 2 == 0 else (60, 60, 66, 160)
        d.line((c + r1 * math.cos(a), c + r1 * math.sin(a), c + r2 * math.cos(a), c + r2 * math.sin(a)), fill=col, width=max(1, SS))
    # cap
    cap = Image.fromarray(radial(K, c - 0.09 * K, c - 0.12 * K, 0.36 * K, (78, 78, 86), (10, 10, 12), 0.9)).convert("RGBA")
    m2 = Image.new("L", (K, K), 0)
    ImageDraw.Draw(m2).ellipse((c - 0.285 * K, c - 0.285 * K, c + 0.285 * K, c + 0.285 * K), fill=255)
    img.paste(cap, (0, 0), m2)
    d.ellipse((c - 0.285 * K, c - 0.285 * K, c + 0.285 * K, c + 0.285 * K), outline=(44, 44, 50, 255), width=SS)
    hl = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse((c - 0.22 * K, c - 0.25 * K, c + 0.05 * K, c - 0.08 * K), fill=(255, 255, 255, 40))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(K * 0.02)))
    return img


def knob_strip(S, bipolar, fname):
    body = knob_body(S)
    K = S * SS
    c = K / 2
    strip = Image.new("RGBA", (S, S * FRAMES), (0, 0, 0, 0))
    dots = [(-135 + 27 * i) for i in range(11)]
    for fr in range(FRAMES):
        n = fr / (FRAMES - 1)
        a = -135 + 270 * n
        im = Image.new("RGBA", (K, K), (0, 0, 0, 0))
        glow = Image.new("RGBA", (K, K), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        gd = ImageDraw.Draw(glow)
        rr, dr = 0.455 * K, 0.034 * K
        for i, da in enumerate(dots):
            f = i / 10
            lit = (min(0.5, n) - 1e-6 <= f <= max(0.5, n) + 1e-6) if bipolar else (f <= n + 1e-6)
            x, y = c + rr * math.sin(math.radians(da)), c - rr * math.cos(math.radians(da))
            if lit:
                gd.ellipse((x - dr * 2.2, y - dr * 2.2, x + dr * 2.2, y + dr * 2.2), fill=LED + (120,))
                d.ellipse((x - dr, y - dr, x + dr, y + dr), fill=(255, 140, 110), outline=LED)
            else:
                d.ellipse((x - dr, y - dr, x + dr, y + dr), fill=(70, 40, 34), outline=(40, 30, 28))
        im = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(dr * 1.2)), im)
        im.alpha_composite(body)
        d = ImageDraw.Draw(im)
        r1, r2 = 0.07 * K, 0.255 * K
        sa, ca = math.sin(math.radians(a)), -math.cos(math.radians(a))
        d.line((c + r1 * sa, c + r1 * ca, c + r2 * sa, c + r2 * ca), fill=(243, 239, 228), width=int(0.045 * K))
        strip.paste(im.resize((S, S), Image.LANCZOS), (0, fr * S))
    strip.save(os.path.join(OUT, fname), optimize=True)


# ------------------------------------------------------------------ fader film strips (vertical)
FW, CAPH = 60, 28


def fader_strip(h, fname):
    track = Image.new("RGBA", (FW, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(track)
    top, bot = CAPH // 2, h - CAPH // 2
    for i in range(11):
        y = top + (bot - top) * i / 10
        L = 9 if i % 5 == 0 else 6
        d.line((4, y, 4 + L, y), fill=INK + (220,), width=2)
        d.line((FW - 5 - L, y, FW - 5, y), fill=INK + (220,), width=2)
    d.rounded_rectangle((FW / 2 - 4, top - 6, FW / 2 + 4, bot + 6), radius=4, fill=(6, 6, 7), outline=(255, 255, 255, 90))
    cap = Image.new("RGBA", (50, CAPH + 8), (0, 0, 0, 0))
    sh = Image.new("RGBA", cap.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((2, 6, 48, CAPH + 6), radius=3, fill=(0, 0, 0, 170))
    cap.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2)))
    cd = ImageDraw.Draw(cap)
    stops = [(0, 251), (0.18, 201), (0.4, 142), (0.46, 227), (0.47, 28), (0.53, 28), (0.54, 227), (0.7, 154), (0.88, 212), (1.0, 122)]
    for yy in range(CAPH):
        t = yy / (CAPH - 1)
        for (t0, v0), (t1, v1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                v = int(v0 + (v1 - v0) * (t - t0) / max(1e-6, t1 - t0))
                break
        cd.line((1, yy, 48, yy), fill=(v, v, v, 255))
    cd.rounded_rectangle((0, 0, 49, CAPH - 1), radius=3, outline=(26, 26, 26))
    strip = Image.new("RGBA", (FW, h * FRAMES), (0, 0, 0, 0))
    for fr in range(FRAMES):
        n = fr / (FRAMES - 1)
        y = int(round((1 - n) * (h - CAPH)))
        f = track.copy()
        f.alpha_composite(cap, (5, y))
        strip.paste(f, (0, fr * h))
    strip.save(os.path.join(OUT, fname), optimize=True)


# ------------------------------------------------------------------ key caps and list buttons
def keycap(w, h, text, on, fname, led=True, size=None):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lip = 2 if on else 4
    d.rounded_rectangle((0, 2, w - 1, h - 1), radius=5, fill=(70, 65, 58))                      # body/lip
    top_h = h - lip - 1
    face = Image.new("RGBA", (w - 2, top_h - 1))
    fd = ImageDraw.Draw(face)
    for i in range(top_h - 1):
        t = i / max(1, top_h - 2)
        c = tuple(int(a + (b - a) * t) for a, b in zip((232, 228, 218), (176, 170, 158)))
        fd.line((0, i, w, i), fill=c + (255,))
    m = Image.new("L", face.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, face.size[0] - 1, face.size[1] - 1), radius=4, fill=255)
    oy = 1 + (2 if on else 0)
    im.paste(face, (1, oy), m)
    d.rounded_rectangle((1, oy, w - 2, oy + top_h - 2), radius=4, outline=(94, 88, 77))
    d.line((4, oy + 1, w - 5, oy + 1), fill=(255, 255, 255, 140))
    f = font(size or 18)
    tx = w / 2
    if led:
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        tx = w / 2 + 8
        lx, ly = tx - (r - l) / 2 - 14, oy + top_h / 2
        if on:
            g = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((lx - 9, ly - 9, lx + 9, ly + 9), fill=LED + (150,))
            im.alpha_composite(g.filter(ImageFilter.GaussianBlur(3)))
            d = ImageDraw.Draw(im)
            d.ellipse((lx - 4, ly - 4, lx + 4, ly + 4), fill=(255, 200, 170), outline=LED)
        else:
            d.ellipse((lx - 4, ly - 4, lx + 4, ly + 4), fill=(90, 40, 30), outline=(50, 24, 18))
    if text:
        text_center(d, tx, oy + top_h / 2, text, f, (42, 38, 46))
    im.save(os.path.join(OUT, fname))


def step_cap(w, h, on, fname):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    keycap(w, h, "", False, "_tmp.png", led=False)
    base = Image.open(os.path.join(OUT, "_tmp.png"))
    im.alpha_composite(base)
    if on:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        gd.rounded_rectangle((4, 4, w - 5, h - 8), radius=4, fill=(255, 80, 40, 255))
        g = g.filter(ImageFilter.GaussianBlur(2))
        im.alpha_composite(g)
        ImageDraw.Draw(im).rounded_rectangle((7, 7, w - 8, h - 11), radius=3, fill=(255, 170, 130))
    im.save(os.path.join(OUT, fname))


def layer_light_strip(param, n):
    w, h = 42, 24
    strip = Image.new("RGBA", (w, h * 3), (0, 0, 0, 0))
    f = font(16, "SemiBold Condensed")
    for fr in range(3):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if fr == 0:
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3, outline=LCD_FG + (90,), width=2)
            text_center(d, w / 2, h / 2, "L%d" % n, f, LCD_FG + (90,))
        elif fr == 1:
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3, outline=LCD_FG + (220,), width=2, fill=tuple(int(c * 0.8) for c in LCD_BG) + (255,))
            text_center(d, w / 2, h / 2, "L%d" % n, f, LCD_FG)
        else:
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3, fill=LCD_FG + (255,))
            text_center(d, w / 2, h / 2, "L%d" % n, f, LCD_BG)
        strip.paste(im, (0, fr * h))
    strip.save(os.path.join(OUT, "light%d.png" % n))


HELP_TITLE = "HYBRID PHATT  -  SOUND BANK"
HELP_BODY = [
    ("p", "Hybrid Phatt was created with the Mo'Phatt sound bank (Mo'Phatt.exb and its SamplePool), "
          "but those sounds cannot be released with the plugin because of copyright."),
    ("p", "Contact the creator at thediskking.com if more information is needed."),
    ("h", "LOAD YOUR OWN BANK  (E-mu Emulator X / Proteus X  .exb)"),
    ("n", "1.  Connect your MPC to a computer in Computer Mode, or put the bank on a USB stick."),
    ("n", "2.  At the top of any MPC drive (internal, SSD or USB) make a folder named:  Hybrid Phatt Sets"),
    ("n", "3.  Copy your bank folder into it: the .exb file together with its SamplePool folder."),
    ("c", "Hybrid Phatt Sets / My Bank / My Bank.exb"),
    ("c", "Hybrid Phatt Sets / My Bank / SamplePool / (the .ebl sound files)"),
    ("n", "4.  Remove Hybrid Phatt from the track and add it again. The bank name and presets show on the LCD."),
]


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textbbox((0, 0), t, font=f)[2] > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def help_panel(fname):
    """Full-tab instructions card: dimmed page behind, metal card with purple title bar."""
    im = Image.new("RGBA", (W, H), (10, 8, 14, 200))
    cx, cy, cw, ch = 150, 26, 980, 520
    card = metal_plate(cw, ch, seed=99)
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=12, fill=255)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((cx + 6, cy + 10, cx + cw + 6, cy + ch + 10), radius=12, fill=(0, 0, 0, 160))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    im.paste(card, (cx, cy), m)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((cx, cy, cx + cw - 1, cy + ch - 1), radius=12, outline=INK_SOFT, width=2)
    bar = Image.new("RGBA", (cw, 54))
    bd = ImageDraw.Draw(bar)
    for i in range(54):
        c = tuple(int(PURPLE_TOP[k] + (PURPLE_BOT[k] - PURPLE_TOP[k]) * i / 53) for k in range(3))
        bd.line((0, i, cw, i), fill=c + (255,))
    bm = Image.new("L", (cw, 54), 0)
    ImageDraw.Draw(bm).rounded_rectangle((0, 0, cw - 1, 70), radius=12, fill=255)
    im.paste(bar, (cx, cy), bm)
    text_center(d, cx + cw / 2, cy + 27, HELP_TITLE, font(30, "Bold Condensed"), (239, 232, 247))
    y = cy + 76
    fp, fh, fc = font(22, "SemiCondensed"), font(22, "Bold Condensed"), font(20, "SemiBold Condensed")
    for kind, text in HELP_BODY:
        if kind == "h":
            y += 8
            d.text((cx + 40, y), text, font=fh, fill=(69, 48, 95))
            y += 34
            continue
        if kind == "c":
            d.rounded_rectangle((cx + 80, y - 2, cx + cw - 80, y + 28), radius=4, fill=LCD_BG, outline=LCD_FG)
            d.text((cx + 94, y + 1), text, font=fc, fill=LCD_FG)
            y += 36
            continue
        f = fp
        indent = 40 if kind == "p" else 56
        for ln in wrap(d, text, f, cw - indent - 40):
            d.text((cx + indent, y), ln, font=f, fill=INK)
            y += 29
        y += 6
    for sx, sy in ((cx + 14, cy + ch - 14), (cx + cw - 15, cy + ch - 14)):
        screw(d, sx, sy, 6)
    im.save(os.path.join(OUT, fname))
    return cx, cy, cw, ch


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def piano_key(black, w, h, on, label, fname):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if black:
        top, bot = ((255, 120, 90), (200, 40, 20)) if on else ((70, 70, 76), (12, 12, 14))
        for y in range(h - 6):
            t = y / max(1, h - 7)
            d.line((1, y, w - 2, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3, outline=(0, 0, 0))
        d.rectangle((3, h - 14, w - 4, h - 4), fill=(255, 170, 140) if on else (40, 40, 44))
    else:
        top, bot = ((255, 214, 190), (255, 96, 60)) if on else ((250, 248, 242), (214, 208, 194))
        for y in range(h):
            t = y / max(1, h - 1)
            d.line((0, y, w - 1, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))
        d.rectangle((0, 0, w - 1, h - 1), outline=(60, 56, 50))
        d.rectangle((1, h - 8, w - 2, h - 2), fill=(196, 188, 172) if not on else (230, 70, 40))
        if label:
            text_center(d, w / 2, h - 26, label, font(15, "SemiBold Condensed"), (90, 84, 96) if not on else (60, 10, 0))
    im.save(os.path.join(OUT, fname))


def lcd_item(w, h, text, on, fname):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(18, "SemiBold Condensed")
    if on:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=3, fill=LCD_FG + (255,))
        d.text((10, (h - 20) / 2), text, font=f, fill=LCD_BG)
    else:
        d.text((10, (h - 20) / 2), text, font=f, fill=LCD_FG + (190,))
    im.save(os.path.join(OUT, fname))


# ------------------------------------------------------------------ TUI.json helpers
P = {}                        # param id -> index
CHOICES = {}                  # index -> choices (choice/bool)
REPL = {}                     # "Parameter N" -> strings


def pid(i):
    return P[i]


def bounds(x, y, w, h, focus="Yes", show="Hide"):
    return {"version": 1, "acceptsHWFocus": focus, "showWhenDataModelInvalid": show, "whenVisible": "Always",
            "boundsType": "Absolute", "bounds": "%d %d %d %d" % (x, y, w, h)}


def entry(name, typ, data, b, remap=None):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": typ, "data": data},
            "handle remapping": {"version": 1, "map": [{"key": "Data", "value": remap}] if remap else []}, "bounds": b}


def textstyle(size, colour, just="horizontallyCentred verticallyCentred", style="SemiBold", case="Original"):
    return {"version": 1, "font": {"version": 1, "name": "Titillium Web", "style": style, "height": float(size)},
            "colour": colour, "justification": just, "case": case}


def bg_none():
    return {"version": 1, "focussed": {"version": 1, "colour": "0", "image": ""}, "unfocussed": {"version": 1, "colour": "0", "image": ""}}


DEFS = {}


def define_control(key, img, size_w, size_h, frames_h, comp_w, label_h=24):
    """A knob or vertical fader: film strip + LED value readout underneath, focus ring, Q-Link + overlay actions."""
    comp_h = frames_h + 6 + label_h
    x0 = (comp_w - size_w) // 2
    DEFS[key] = {
        "version": 2,
        "actions": [
            {"version": 1, "onAction": "Mouse Down", "handler": "Q-Link", "handleName": "Data", "additionalData": ""},
            {"version": 1, "onAction": "Double Click", "handler": "Show Overlay", "handleName": "Data", "additionalData": "knob overlay"},
            {"version": 1, "onAction": "Enter Pressed", "handler": "Show Overlay", "handleName": "Data", "additionalData": "knob overlay"}],
        "backgroundData": bg_none(), "ignoreMousePresses": False, "disableCoarseDataWheel": False,
        "componentsData": [
            entry("focus", "Focus", {"version": 1, "backgroundColour": "14ff3b22", "outlineColour": "ffff3b22", "backgroundInset": 2.0, "outlineThickness": 2.0},
                  {**bounds(0, 0, comp_w, comp_h, "No", "Show"), "whenVisible": "WhenFocussed"}),
            entry("control", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": img, "numFrames": FRAMES, "invert": False,
                                      "dragOrientation": "Vertical", "handleName": "Data"}, bounds(x0, 0, size_w, frames_h, "No", "Show")),
            entry("value", "Label", {"version": 1, "textStyle": textstyle(17, VALUE_TXT), "type": "Value", "handleName": "Data"},
                  bounds((comp_w - 84) // 2, frames_h + 6, 84, label_h, "No", "Show")),
        ]}
    return comp_w, comp_h


def define_chip(key, w, h):
    DEFS[key] = {
        "version": 2,
        "actions": [
            {"version": 1, "onAction": "Mouse Down", "handler": "Show Overlay", "handleName": "Data", "additionalData": "menu overlay"},
            {"version": 1, "onAction": "Enter Pressed", "handler": "Show Overlay", "handleName": "Data", "additionalData": "menu overlay"}],
        "backgroundData": bg_none(), "ignoreMousePresses": False, "disableCoarseDataWheel": False,
        "componentsData": [
            entry("focus", "Focus", {"version": 1, "backgroundColour": "14ff3b22", "outlineColour": "ffff3b22", "backgroundInset": 1.0, "outlineThickness": 2.0},
                  {**bounds(0, 0, w, h, "No", "Show"), "whenVisible": "WhenFocussed"}),
            entry("value", "Label", {"version": 1, "textStyle": textstyle(18, VALUE_TXT, "left verticallyCentred"), "type": "Value", "handleName": "Data"},
                  bounds(12, 0, w - 16, h, "No", "Show")),
        ]}


# ------------------------------------------------------------------ page builder
class Page:
    def __init__(self, name, key, direction):
        self.name, self.key, self.direction = name, key, direction
        self.img = metal_plate(W, H, seed=key + 3)
        self.items = []
        self.overlays = []
        self.groups = []           # 4 lists of 4 param ids (Q-Link banks), None = unassigned
        self.qrects = []

    def control(self, kind, param, cx, y, label=None, label_size=18):
        """Place a knob/fader component centred at cx with its top at y."""
        spec = CONTROL_SPECS[kind]
        bip = BIPOLAR.get(param, False)
        key = kind + ("b" if bip else "")
        cw, ch = spec["comp"]
        x = int(cx - cw / 2)
        if label:
            silk(self.img, cx, y - 14, label, label_size)
        led_window(self.img, x + (cw - 84) // 2, y + spec["fh"] + 6, 84, 24)
        self.items.append(entry(param, key, {"version": 1, "handleName": "Data"}, bounds(x, y, cw, ch), "Parameter %d" % pid(param)))

    def button(self, param, x, y, w, h, button_id, n, text, size=None, img_kind="key"):
        base = "btn_%s_%d" % (param, button_id)
        if img_kind == "key":
            keycap(w, h, text, True, base + "_on.png", size=size)
            keycap(w, h, text, False, base + "_off.png", size=size)
        elif img_kind == "step":
            step_cap(w, h, True, base + "_on.png")
            step_cap(w, h, False, base + "_off.png")
        else:
            lcd_item(w, h, text, True, base + "_on.png")
            lcd_item(w, h, text, False, base + "_off.png")
        self.items.append(entry(param, "Button", {"version": 2, "onImage": base + "_on.png", "offImage": base + "_off.png", "buttonId": button_id,
                                                  "numButtonsInGroup": n, "handleName": "Parameter %d" % pid(param), "gestureBehaviour": "Instant"},
                                bounds(x, y, w, h)))
        if n > 1 or True:
            REPL["Parameter %d" % pid(param)] = CHOICES[pid(param)]

    def radio(self, param, x, y, w, h, cols, gap=6, size=None, kind="key", labels=None):
        ch = CHOICES[pid(param)]
        for i, c in enumerate(ch):
            r, k = divmod(i, cols)
            self.button(param, x + k * (w + gap), y + r * (h + gap), w, h, i, len(ch), (labels or ch)[i].upper() if kind == "key" else (labels or ch)[i], size, kind)

    def toggle(self, param, x, y, w, h, text, size=None, momentary=False):
        self.button(param, x, y, w, h, 1, 1, text.upper(), size)
        if momentary:
            self.items[-1]["componentData"]["data"]["handleName"] = "ResetOnGestureEnd/Parameter %d" % pid(param)

    def chip(self, param, x, y, w, h):
        d = ImageDraw.Draw(self.img)
        d.rounded_rectangle((x - 1, y - 1, x + w, y + h + 1), radius=4, fill=(255, 255, 255, 90))
        d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=4, fill=(12, 10, 10), outline=(0, 0, 0))
        self.items.append(entry(param, "menuChip", {"version": 1, "handleName": "Data"}, bounds(x, y, w, h), "Parameter %d" % pid(param)))
        REPL["Parameter %d" % pid(param)] = CHOICES[pid(param)]

    def label(self, param, x, y, w, h, size, colour, just="left verticallyCentred", style="SemiBold"):
        self.items.append(entry(param + " text", "Label", {"version": 1, "textStyle": textstyle(size, colour, just, style), "type": "Value",
                                                           "handleName": "Parameter %d" % pid(param)}, bounds(x, y, w, h, "No", "Show")))

    def fixed_text(self, text, x, y, w, h, size, colour, just="left verticallyCentred", style="SemiBold"):
        self.items.append(entry("text", "Label", {"version": 1, "textStyle": textstyle(size, colour, just, style), "type": "Text",
                                                  "handleName": "Invalid", "text": text}, bounds(x, y, w, h, "No", "Show")))

    def tab(self, index):
        fn = "page_%s.png" % self.name.lower()
        self.img.convert("RGB").save(os.path.join(OUT, fn), optimize=True)
        root = {"version": 2, "actions": [],
                "backgroundData": {"version": 1, "focussed": {"version": 1, "colour": "ffbdb7aa", "image": fn},
                                   "unfocussed": {"version": 1, "colour": "ffbdb7aa", "image": fn}},
                "ignoreMousePresses": False, "disableCoarseDataWheel": False, "componentsData": self.items + self.overlays}
        return {"version": 1, "tabName": self.name, "fnKeyIndex": index, "fnKeySubIndex": 0,
                "componentDefinition": root, "qlinkBoundsData": ["%d %d %d %d" % r for r in self.qrects]}

    def qmap(self, index):
        q = {}
        for g, grp in enumerate(self.groups):
            for i, p in enumerate(grp):
                n = (13 - 4 * g + i) if self.direction == "RowTopDown" else (13 + g - 4 * i)
                q["Q-Link %d" % n] = pid(p) if p else -1
        for n in range(1, 17):
            q.setdefault("Q-Link %d" % n, -1)
        ordered = {"Q-Link %d" % n: q["Q-Link %d" % n] for n in range(1, 17)}
        return {"Tab": index + 1, "SubTab": 1, "Bank Direction": self.direction, "Q-Links": ordered}


CONTROL_SPECS = {}
BIPOLAR = {}


# ------------------------------------------------------------------ JSON writer (overlays need duplicate "version" keys)
class Dup(list):
    """An object written as ordered key/value pairs, duplicates allowed."""


def dump(o, ind=0):
    sp = " " * ind
    if isinstance(o, Dup):
        return "{" + ", ".join(json.dumps(k) + ": " + dump(v, ind) for k, v in o) + "}"
    if isinstance(o, dict):
        if not o:
            return "{}"
        return "{\n" + ",\n".join(sp + " " + json.dumps(k) + ": " + dump(v, ind + 1) for k, v in o.items()) + "\n" + sp + "}"
    if isinstance(o, list):
        if not o:
            return "[]"
        return "[\n" + ",\n".join(sp + " " + dump(v, ind + 1) for v in o) + "\n" + sp + "]"
    return json.dumps(o)


def overlay_def(widget_type, data_pairs):
    return {"version": 2, "actions": [], "backgroundData": bg_none(), "ignoreMousePresses": True, "disableCoarseDataWheel": False,
            "componentsData": [{"version": 2, "componentData": {"version": 1, "name": "overlay", "type": widget_type, "data": Dup(data_pairs)},
                                "handle remapping": {"version": 1, "map": []},
                                "bounds": {"version": 1, "acceptsHWFocus": "Yes", "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
                                           "boundsType": "Absolute", "bounds": "0 0 1280 800"}}]}


FOCUS_LOST = [{"version": 1, "onAction": "Focus Lost", "handler": "Focus Lost", "handleName": "Focus Lost", "additionalData": ""}]


# ------------------------------------------------------------------ main
def main():
    params_json = os.path.join(HERE, "build", "params.json")
    if not os.path.isfile(params_json):
        sys.exit("build/params.json missing: run tools/build.py on this plugin first")
    plist = json.load(open(params_json, encoding="utf-8"))["params"]
    ids = ["volume", "bank", "preset", "prev", "next", "cutoff", "reso", "morph", "drive", "attack", "decay", "sustain", "release", "glide", "tune"]
    ids += ["lvl%d" % i for i in range(1, 5)] + ["pan%d" % i for i in range(1, 5)] + ["coarse%d" % i for i in range(1, 5)]
    ids += ["fine%d" % i for i in range(1, 5)] + ["on%d" % i for i in range(1, 5)]
    ids += ["ftype", "fenv", "keytrk", "velfilt", "fa", "fd", "fs", "fr"]
    for k in (1, 2):
        ids += ["lfoshape%d" % k, "lforate%d" % k, "lfodepth%d" % k, "lfodelay%d" % k, "lfosync%d" % k]
    ids += ["msrc%d" % k for k in range(1, 7)] + ["mdst%d" % k for k in range(1, 7)] + ["mamt%d" % k for k in range(1, 7)]
    ids += ["arpon", "latch", "arpmode", "arprate", "arpgate", "arpswing", "arpoct", "beatplay", "beatvar"]
    ids += ["blvl%d" % k for k in range(1, 5)] + ["bswing", "bhum"]
    ids += ["rvon", "rvtype", "rvsize", "rvdamp", "rvpre", "rvmix", "chon", "chtype", "chrate", "chdepth", "chfb", "chmix"]
    ids += ["dlon", "dltime", "dlfb", "dltone", "dlwidth", "dlmix", "lofi"] + ["step%d" % k for k in range(64)]
    ids += ["info", "act1", "act2", "act3", "act4", "bankstate", "lastnote"] + ["key%d" % k for k in range(61)]
    if len(ids) != len(plist):
        sys.exit("parameter list mismatch: %d ids vs %d params" % (len(ids), len(plist)))
    for i, (pi, p) in enumerate(zip(ids, plist)):
        P[pi] = p["index"]
        CHOICES[p["index"]] = p["choices"] if p["choices"] else ["Off", "On"]
    for b in ("tune", "attack", "decay", "sustain", "release", "fenv", "pan1", "pan2", "pan3", "pan4", "coarse1", "coarse2", "coarse3",
              "coarse4", "fine1", "fine2", "fine3", "fine4", "mamt1", "mamt2", "mamt3", "mamt4", "mamt5", "mamt6"):
        BIPOLAR[b] = True

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # film strips and the components that use them
    print("drawing knobs and faders ...")
    for key, S in (("kL", 104), ("kM", 84), ("kS", 62), ("kT", 46)):
        knob_strip(S, False, key + ".png")
        knob_strip(S, True, key + "b.png")
        cw = max(S + 16, 96)
        for suffix in ("", "b"):
            CONTROL_SPECS.setdefault(key, {"fh": S})
            CONTROL_SPECS[key]["comp"] = define_control(key + suffix, key + suffix + ".png", S, S, S, cw)
    for key, h in (("f120", 120), ("f170", 170), ("f300", 300)):
        fader_strip(h, key + ".png")
        for suffix in ("", "b"):
            CONTROL_SPECS.setdefault(key, {"fh": h})
            CONTROL_SPECS[key]["comp"] = define_control(key + suffix, key + ".png", FW, h, h, 96)
    define_chip("menuChip", 150, 40)

    pages = []
    print("drawing pages ...")
    # ---------------- MAIN
    pg = Page("MAIN", 0, "RowTopDown")
    panel_box(pg.img, 24, 22, 410, 214, "")
    lcd(pg.img, 40, 38, 378, 182)
    pg.label("bank", 54, 44, 170, 28, 20, LCD_TXT, style="Regular", just="left verticallyCentred")
    pg.label("preset", 54, 78, 356, 60, 30, LCD_TXT, style="SemiBold")
    pg.label("info", 54, 138, 356, 28, 18, LCD_TXT, style="Regular")
    d = ImageDraw.Draw(pg.img)
    f = font(16, "SemiBold Condensed")
    d.text((56, 186), "LAYERS", font=f, fill=LCD_FG)
    for i in range(4):
        layer_light_strip("act%d" % (i + 1), i + 1)
        pg.items.append(entry("light%d" % (i + 1), "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": "light%d.png" % (i + 1),
                                                            "numFrames": 3, "handleName": "Parameter %d" % pid("act%d" % (i + 1))},
                              bounds(130 + i * 52, 182, 42, 24, "No", "Show")))
    pg.toggle("prev", 24, 252, 200, 52, "<  PREV", momentary=True)
    pg.toggle("next", 234, 252, 200, 52, "NEXT  >", momentary=True)
    pg.radio("bank", 24, 316, 98, 46, 4, gap=6, size=17)
    panel_box(pg.img, 24, 392, 410, 222, "PERFORMANCE")
    for i, (p, lbl) in enumerate((("glide", "Glide"), ("tune", "Tune"), ("rvmix", "Reverb"), ("chmix", "Chorus"))):
        pg.control("kS", p, 24 + 410 * (i + 0.5) / 4, 452, lbl)
    panel_box(pg.img, 452, 22, 804, 384, "SOUND")
    for i, (p, lbl) in enumerate((("cutoff", "Cutoff"), ("reso", "Resonance"), ("morph", "Morph"), ("drive", "Drive"))):
        pg.control("kL", p, 452 + 804 * (i + 0.5) / 4, 72, lbl)
    for i, (p, lbl) in enumerate((("attack", "Attack"), ("decay", "Decay"), ("release", "Release"), ("volume", "Volume"))):
        pg.control("kL", p, 452 + 804 * (i + 0.5) / 4, 248, lbl)
    panel_box(pg.img, 452, 424, 804, 190, "LAYER MIX")
    for i in range(4):
        pg.control("f120", "lvl%d" % (i + 1), 452 + 804 * (i + 0.5) / 4, 450, None)
        silk(pg.img, 452 + 804 * (i + 0.5) / 4 - 62, 510, "L%d" % (i + 1), 22)
    keycap(96, 34, "HELP", True, "btn_help_on.png", size=16)
    keycap(96, 34, "HELP", False, "btn_help_off.png", size=16)
    pg.items.append(entry("help", "Button", {"version": 2, "onImage": "btn_help_on.png", "offImage": "btn_help_off.png", "buttonId": 1,
                                              "numButtonsInGroup": 1, "handleName": "Local/2/help", "gestureBehaviour": "Instant"},
                          bounds(326, 380, 96, 34, "Yes", "Show")))
    cx, cy, cw, ch = help_panel("help_panel.png")
    keycap(200, 50, "CLOSE", False, "btn_close_off.png", size=20, led=False)
    keycap(200, 50, "CLOSE", True, "btn_close_on.png", size=20, led=False)
    DEFS["helpPanel"] = {
        "version": 4, "actions": [], "backgroundData": bg_none(), "ignoreMousePresses": False, "disableCoarseDataWheel": False,
        "repeats": 1, "hideQLinkBounds": True,
        "componentsData": [
            entry("card", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": "help_panel.png"}, bounds(0, 0, W, H, "No", "Show")),
            entry("close", "Button", {"version": 2, "onImage": "btn_close_on.png", "offImage": "btn_close_off.png", "buttonId": 1,
                                      "numButtonsInGroup": 1, "handleName": "Data", "gestureBehaviour": "Instant"},
                  bounds(cx + cw - 230, cy + ch - 70, 200, 50, "Yes", "Show")),
        ]}
    st = "Parameter %d" % pid("bankstate")
    auto = entry("instructions", "helpPanel", {"version": 1, "handleName": "Data"}, bounds(0, 0, W, H, "Children", "Show"), "Local/2/dismiss")
    auto["bounds"] = {**auto["bounds"], "version": 2, "additionalInvalidatingHandles": ["IndexedEnabling/2/3/" + st, "IndexedEnabling/0/2/Local/2/dismiss"]}
    manual = entry("help panel", "helpPanel", {"version": 1, "handleName": "Data"}, bounds(0, 0, W, H, "Children", "Show"), "Local/2/help")
    manual["bounds"] = {**manual["bounds"], "version": 2, "additionalInvalidatingHandles": ["IndexedEnabling/1/2/Local/2/help"]}
    pg.overlays = [auto, manual]
    pg.groups = [["cutoff", "reso", "morph", "drive"], ["attack", "decay", "release", "volume"],
                 ["lvl1", "lvl2", "lvl3", "lvl4"], ["glide", "tune", "rvmix", "chmix"]]
    pg.qrects = [(462, 46, 784, 176), (462, 222, 784, 176), (462, 436, 784, 172), (32, 416, 394, 192)]
    pages.append(pg)

    # ---------------- LAYERS
    pg = Page("LAYERS", 1, "Column")
    for i in range(4):
        x = 24 + i * 312
        panel_box(pg.img, x, 22, 296, 592, "LAYER %d" % (i + 1))
        pg.toggle("on%d" % (i + 1), x + 176, 40, 104, 40, "ON", size=17)
        silk(pg.img, x + 66, 104, "Level")
        pg.control("f300", "lvl%d" % (i + 1), x + 66, 122, None)
        for j, (p, lbl) in enumerate((("pan", "Pan"), ("coarse", "Coarse"), ("fine", "Fine"))):
            pg.control("kM", "%s%d" % (p, i + 1), x + 210, 122 + j * 150, lbl)
    pg.groups = [["lvl%d" % (i + 1), "pan%d" % (i + 1), "coarse%d" % (i + 1), "fine%d" % (i + 1)] for i in range(4)]
    pg.qrects = [(24 + i * 312 + 6, 90, 284, 516) for i in range(4)]
    pages.append(pg)

    # ---------------- FILTER
    pg = Page("FILTER", 2, "RowTopDown")
    panel_box(pg.img, 24, 22, 250, 300, "TYPE")
    lcd(pg.img, 38, 44, 222, 264)
    pg.radio("ftype", 38, 48, 222, 28, 1, gap=1, kind="lcd")
    panel_box(pg.img, 290, 22, 966, 300, "FILTER")
    for i, (p, lbl) in enumerate((("cutoff", "Cutoff"), ("reso", "Resonance"), ("morph", "Morph"), ("fenv", "Env Amount"),
                                  ("keytrk", "Key Track"), ("velfilt", "Velocity"))):
        pg.control("kM", p, 290 + 966 * (i + 0.5) / 6, 96, lbl)
    panel_box(pg.img, 24, 342, 610, 272, "FILTER ENVELOPE")
    for i, (p, lbl) in enumerate((("fa", "A"), ("fd", "D"), ("fs", "S"), ("fr", "R"))):
        pg.control("f170", p, 24 + 610 * (i + 0.5) / 4, 384, lbl, 20)
    panel_box(pg.img, 646, 342, 610, 272, "AMP ENVELOPE")
    for i, (p, lbl) in enumerate((("attack", "A"), ("decay", "D"), ("sustain", "S"), ("release", "R"))):
        pg.control("f170", p, 646 + 610 * (i + 0.5) / 4, 384, lbl, 20)
    pg.groups = [["cutoff", "reso", "morph", "fenv"], ["keytrk", "velfilt", "ftype", None],
                 ["fa", "fd", "fs", "fr"], ["attack", "decay", "sustain", "release"]]
    pg.qrects = [(296, 60, 640, 252), (936, 60, 314, 252), (32, 366, 594, 242), (654, 366, 594, 242)]
    pages.append(pg)

    # ---------------- MOD
    pg = Page("MOD", 3, "RowTopDown")
    for k in (1, 2):
        y = 22 + (k - 1) * 304
        panel_box(pg.img, 24, y, 816, 288, "LFO %d" % k)
        pg.radio("lfoshape%d" % k, 44, y + 40, 72, 44, 5, gap=6, size=16)
        pg.toggle("lfosync%d" % k, 44, y + 100, 180, 44, "TEMPO SYNC", size=16)
        for j, (p, lbl) in enumerate((("lforate", "Rate"), ("lfodepth", "Depth"), ("lfodelay", "Delay"))):
            pg.control("kM", "%s%d" % (p, k), 520 + j * 108, y + 70, lbl)
    panel_box(pg.img, 856, 22, 400, 592, "MOD MATRIX")
    silk(pg.img, 930, 52, "Source", 16)
    silk(pg.img, 1092, 52, "Destination", 16)
    for i in range(6):
        y = 70 + i * 88
        pg.chip("msrc%d" % (i + 1), 868, y + 8, 132, 40)
        silk(pg.img, 1012, y + 28, ">", 24)
        pg.chip("mdst%d" % (i + 1), 1026, y + 8, 132, 40)
        pg.control("kT", "mamt%d" % (i + 1), 1206, y - 6, None)
    pg.groups = [["lforate1", "lfodepth1", "lfodelay1", "lfoshape1"], ["lforate2", "lfodepth2", "lfodelay2", "lfoshape2"],
                 ["mamt1", "mamt2", "mamt3", "mamt4"], ["mamt5", "mamt6", None, None]]
    pg.qrects = [(30, 46, 804, 270), (30, 350, 804, 270), (1160, 60, 92, 356), (1160, 412, 92, 190)]
    pages.append(pg)

    # ---------------- GROOVE
    pg = Page("GROOVE", 4, "RowTopDown")
    panel_box(pg.img, 24, 22, 430, 592, "ARPEGGIATOR")
    pg.toggle("arpon", 44, 44, 186, 46, "ARP ON")
    pg.toggle("latch", 248, 44, 186, 46, "LATCH")
    silk(pg.img, 239, 112, "Mode", 16)
    pg.radio("arpmode", 44, 126, 126, 42, 3, gap=7, size=16)
    silk(pg.img, 239, 240, "Rate", 16)
    pg.radio("arprate", 44, 254, 126, 42, 3, gap=7, size=16)
    for j, (p, lbl) in enumerate((("arpgate", "Gate"), ("arpswing", "Swing"), ("arpoct", "Octaves"))):
        pg.control("kM", p, 24 + 430 * (j + 0.5) / 3, 420, lbl)
    panel_box(pg.img, 470, 22, 786, 592, "BEATS")
    pg.toggle("beatplay", 490, 44, 150, 46, "PLAY")
    lcd(pg.img, 658, 48, 300, 38)
    ImageDraw.Draw(pg.img).text((672, 55), "PATTERN 01   BOOM BAP   92 BPM", font=font(20, "SemiBold Condensed"), fill=LCD_FG)
    pg.radio("beatvar", 990, 44, 78, 46, 3, gap=6, size=16)
    lanes = ["KICK", "SNARE", "HAT", "PERC"]
    for r in range(4):
        silk(pg.img, 520, 152 + r * 58, lanes[r], 17)
        for c in range(16):
            x = 566 + c * 42
            if r == 0:
                silk(pg.img, x + 19, 114, str(c + 1), 14)
            pg.button("step%d" % (r * 16 + c), x, 130 + r * 58, 38, 46, 1, 1, "", img_kind="step")
    for j, (p, lbl) in enumerate((("blvl1", "Kick"), ("blvl2", "Snare"), ("blvl3", "Hat"), ("blvl4", "Perc"), ("bswing", "Swing"), ("bhum", "Humanize"))):
        pg.control("kS", p, 470 + 786 * (j + 0.5) / 6, 420, lbl)
    pg.groups = [["arpgate", "arpswing", "arpoct", "arpmode"], ["blvl1", "blvl2", "blvl3", "blvl4"],
                 ["bswing", "bhum", "arprate", "beatvar"], [None, None, None, None]]
    pg.qrects = [(30, 380, 418, 228), (476, 380, 520, 228), (996, 380, 254, 228)]
    pages.append(pg)

    # ---------------- FX
    pg = Page("FX", 5, "Column")
    fx = [("REVERB", "rvon", "rvtype", (("rvsize", "Size"), ("rvdamp", "Damp"), ("rvpre", "Pre-Delay"), ("rvmix", "Mix"))),
          ("CHORUS", "chon", "chtype", (("chrate", "Rate"), ("chdepth", "Depth"), ("chfb", "Feedback"), ("chmix", "Mix"))),
          ("DELAY", "dlon", "dltime", (("dlfb", "Feedback"), ("dltone", "Tone"), ("dlwidth", "Width"), ("dlmix", "Mix")))]
    for i, (title, onp, typ, knobs) in enumerate(fx):
        x = 24 + i * 316
        panel_box(pg.img, x, 22, 300, 592, title)
        pg.toggle(onp, x + 180, 34, 104, 40, "ON", size=17)
        n = len(CHOICES[pid(typ)])
        pg.radio(typ, x + 18, 92, 128, 40, 2, gap=8, size=16)
        for j, (p, lbl) in enumerate(knobs):
            r, c = divmod(j, 2)
            pg.control("kM", p, x + 150 + (c - 0.5) * 136, 250 + r * 172, lbl)
    panel_box(pg.img, 972, 22, 284, 592, "OUTPUT")
    pg.control("kS", "drive", 1042, 72, "Drive")
    pg.control("kS", "lofi", 1186, 72, "Lo-Fi")
    pg.control("f300", "volume", 1114, 226, "Volume")
    pg.groups = [["rvsize", "rvdamp", "rvpre", "rvmix"], ["chrate", "chdepth", "chfb", "chmix"],
                 ["dlfb", "dltone", "dlwidth", "dlmix"], ["drive", "lofi", "volume", None]]
    pg.qrects = [(30 + i * 316, 210, 288, 398) for i in range(3)] + [(978, 46, 272, 562)]
    pages.append(pg)

    # ---------------- KEYS
    pg = Page("KEYS", 6, "RowTopDown")
    panel_box(pg.img, 24, 22, 1232, 592, "KEYS")
    lcd(pg.img, 44, 50, 560, 64)
    pg.label("lastnote", 58, 50, 540, 64, 30, LCD_TXT, style="SemiBold")
    d = ImageDraw.Draw(pg.img)
    tip = font(19, "SemiCondensed")
    d.text((630, 54), "Hit a drum pad and its key lights up.", font=tip, fill=INK)
    d.text((630, 82), "Tap a key to play it. C3 = note 60. MPC pads start at C#1 (37).", font=tip, fill=INK)
    x0, y0, ww, wh, bw, bh = 46, 236, 33, 340, 21, 210
    first = 36
    whites = [n for n in range(first, first + 61) if NOTE_NAMES[n % 12].find("#") < 0]
    wx = {n: x0 + i * ww for i, n in enumerate(whites)}

    def note_x(n):
        if n in wx:
            return wx[n]
        return wx[n - 1] + ww - bw // 2

    # range bars: MPC Key 61 (C1-C6) and MPC Key 37 (C2-C5)
    for (lo, hi, label, yy) in ((36, 96, "MPC KEY 61   C1 - C6", 150), (48, 84, "MPC KEY 37   C2 - C5", 186)):
        xa, xb = note_x(lo), note_x(hi) + ww
        d.rounded_rectangle((xa, yy, xb, yy + 26), radius=4, fill=(PURPLE_BOT if lo == 36 else PURPLE_TOP) + (255,))
        text_center(d, (xa + xb) / 2, yy + 13, label, font(17, "Bold Condensed"), (239, 232, 247))
    d.rounded_rectangle((x0 - 6, y0 - 8, x0 + len(whites) * ww + 6, y0 + wh + 8), radius=6, fill=(20, 18, 22))
    for black in (False, True):
        for k in range(61):
            n = first + k
            is_black = "#" in NOTE_NAMES[n % 12]
            if is_black != black:
                continue
            label = ("C%d" % (n // 12 - 2)) if NOTE_NAMES[n % 12] == "C" else ""
            w, h = (bw, bh) if black else (ww, wh)
            base = "key_%d" % k
            piano_key(black, w, h, True, label, base + "_on.png")
            piano_key(black, w, h, False, label, base + "_off.png")
            pg.items.append(entry("key%d" % k, "Button", {"version": 2, "onImage": base + "_on.png", "offImage": base + "_off.png",
                                                           "buttonId": 1, "numButtonsInGroup": 1,
                                                           "handleName": "ResetOnGestureEnd/Parameter %d" % pid("key%d" % k),
                                                           "gestureBehaviour": "Instant"},
                                  bounds(note_x(n), y0, w, h, "No", "Show")))
    pg.groups = [["volume", "cutoff", "reso", "tune"], [None, None, None, None], [None, None, None, None], [None, None, None, None]]
    pg.qrects = []
    pages.append(pg)

    # ---------------- write TUI.json + Q-Links.json
    if os.path.exists(os.path.join(OUT, "_tmp.png")):
        os.remove(os.path.join(OUT, "_tmp.png"))
    tabs = [pg.tab(i) for i, pg in enumerate(pages)]
    defs = [{"key": k, "value": v} for k, v in DEFS.items()]
    defs.append({"key": "knob overlay", "value": overlay_def("KnobOverlay", [
        ("version", 2), ("version", 1), ("actions", FOCUS_LOST), ("overlayType", "Knob With Header"), ("scaleType", "Linear"),
        ("polarityType", "Unipolar"), ("showMinusSign", True), ("handleName", "Data")])})
    defs.append({"key": "menu overlay", "value": overlay_def("MenuOverlay", [
        ("version", 1), ("version", 1), ("actions", FOCUS_LOST), ("withNumbers", False), ("handleName", "Data")])})
    tui = {"pageData": {"version": 1,
                        "componentDefinitions": {"version": 2, "importFiles": [], "localComponentDefinitions": defs},
                        "replacementStrings": [{"key": k, "value": v} for k, v in REPL.items()],
                        "info": {"version": 1, "type": "CompleteDescription"},
                        "tabs": tabs}}
    with open(os.path.join(OUT, "TUI.json"), "w", encoding="utf-8") as fh:
        fh.write(dump(tui))
    prog = ["cutoff", "reso", "morph", "drive", "attack", "decay", "release", "volume", "lvl1", "lvl2", "lvl3", "lvl4", "glide", "tune", "rvmix", "chmix"]
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [pg.qmap(i) for i, pg in enumerate(pages)]},
          "Program Mode Q-Links": {"Q-Link %d" % (i + 1): pid(p) for i, p in enumerate(prog)}}
    with open(os.path.join(OUT, "Q-Links.json"), "w", encoding="utf-8") as fh:
        json.dump(ql, fh, indent=1)
    print("skins/ written:", len(os.listdir(OUT)), "files")


if __name__ == "__main__":
    main()
