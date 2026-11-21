"""MPC Plugin Scanner skin: one page, a list of plugins with status lights and a details side.

    python tools/build.py "plugins/MPC Plugin Scanner"
    python "plugins/MPC Plugin Scanner/make_skin.py"
    python tools/build.py "plugins/MPC Plugin Scanner"
Parameter indices must match src/MPCPluginScanner.cpp.
"""
import json
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "skins")
W, H = 1280, 628
ROWS, LINES = 6, 10
# parameter indices (see the enum in MPCPluginScanner.cpp)
P_VOLUME, P_SCAN, P_PREV, P_NEXT, P_ROW1 = 0, 1, 2, 3, 4
P_SUMMARY = P_ROW1 + ROWS
P_STATUS, P_PAGE = P_SUMMARY + 1, P_SUMMARY + 2
P_NAME1 = P_SUMMARY + 3
P_INFO1 = P_NAME1 + ROWS
P_LIGHT1 = P_INFO1 + ROWS
P_DTITLE = P_LIGHT1 + ROWS
P_DVERDICT, P_DLIGHT, P_DWHERE = P_DTITLE + 1, P_DTITLE + 2, P_DTITLE + 3
P_DLINE1 = P_DTITLE + 4
P_BADGE1 = P_DLINE1 + LINES          # added in 1.1
P_DBADGE = P_BADGE1 + ROWS
BLUE = (29, 155, 240)                 # verified creator

ORANGE = (234, 134, 26)
BG1, BG2 = (24, 24, 28), (14, 14, 17)
PANEL = (34, 34, 40)
EDGE = (62, 62, 72)
TXT = "ffe8e6ea"
DIM = "ffa8a6b0"


def font(size, weight="SemiBold Condensed"):
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", size)
        f.set_variation_by_name(weight)
        return f
    except Exception:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)


def center(d, cx, cy, text, f, fill):
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), text, font=f, fill=fill)


def background():
    y = np.linspace(0, 1, H)[:, None, None]
    g = np.array(BG1, np.float32) + (np.array(BG2, np.float32) - np.array(BG1, np.float32)) * y
    g = np.broadcast_to(g, (H, W, 3)).copy()
    g += np.random.default_rng(5).normal(0, 2.2, (H, W, 1)).astype(np.float32)
    im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    # header
    d.text((24, 12), "MPC PLUGIN SCANNER", font=font(40, "Bold Condensed"), fill=ORANGE)
    d.text((26, 58), "by The Disk King  |  checks every plugin on this MPC for things a music plugin should not contain",
           font=font(17, "SemiCondensed"), fill=(170, 168, 178))
    d.line((20, 88, W - 20, 88), fill=EDGE, width=2)
    # list cards
    for r in range(ROWS):
        y = 100 + r * 76
        d.rounded_rectangle((20, y, 800, y + 70), radius=10, fill=PANEL, outline=EDGE)
        d.ellipse((34, y + 16, 72, y + 54), fill=(10, 10, 12), outline=(30, 30, 36), width=2)
    # details panel
    d.rounded_rectangle((816, 100, 1260, 556), radius=12, fill=PANEL, outline=EDGE)
    d.text((834, 110), "DETAILS", font=font(16, "Bold Condensed"), fill=(150, 148, 160))
    d.ellipse((832, 134, 876, 178), fill=(10, 10, 12), outline=(30, 30, 36), width=2)
    d.line((832, 248, 1244, 248), fill=EDGE, width=1)
    # legend + footer
    fy = 576
    for i, (col, word) in enumerate((((60, 200, 90), "CLEAN"), ((240, 190, 40), "CHECK"), ((235, 60, 50), "RISKY"), (BLUE, "VERIFIED"))):
        x = 470 + i * 86
        d.ellipse((x, fy + 4, x + 16, fy + 20), fill=col)
        d.text((x + 22, fy + 2), word, font=font(17, "Bold Condensed"), fill=(200, 198, 206))
    d.text((834, 566), "A warning-sign scan, not a guarantee.", font=font(16, "SemiCondensed"), fill=(150, 148, 160))
    d.text((834, 588), "Nothing is changed, run or sent anywhere.", font=font(16, "SemiCondensed"), fill=(150, 148, 160))
    return im


def pad_ring(size):
    """Verified light, styled like a lit MPC pad but round: a dark pad inside a glowing blue ring made of
    8 segments with small gaps, a soft halo around it and a bright core in each segment."""
    S = 4
    K = size * S
    c = K / 2
    r_out, r_in = K * 0.44, K * 0.31
    ring = Image.new("L", (K, K), 0)
    rd = ImageDraw.Draw(ring)
    rd.ellipse((c - r_out, c - r_out, c + r_out, c + r_out), fill=255)
    rd.ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=0)
    gap = K * 0.035
    for k in range(8):                                   # cut the ring into 8 segments
        a = np.pi / 8 + k * np.pi / 4
        dx, dy = np.cos(a), np.sin(a)
        px, py = -dy * gap, dx * gap
        rd.polygon([(c + px, c + py), (c - px, c - py), (c - px + dx * K, c - py + dy * K), (c + px + dx * K, c + py + dy * K)], fill=0)
    core = ring.filter(ImageFilter.MinFilter(5))         # thinner bright line inside each segment
    im = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    halo = Image.new("RGBA", (K, K), BLUE + (0,))
    halo.putalpha(ring.filter(ImageFilter.GaussianBlur(K * 0.06)).point(lambda v: int(v * 0.85)))
    im.alpha_composite(halo)
    d = ImageDraw.Draw(im)
    d.ellipse((c - r_in + 2, c - r_in + 2, c + r_in - 2, c + r_in - 2), fill=(8, 10, 14, 255))          # the dark pad
    d.ellipse((c - r_in * 0.92, c - r_in * 0.92, c + r_in * 0.92, c + r_in * 0.92), outline=(22, 26, 34, 255), width=S)
    seg = Image.new("RGBA", (K, K), (36, 150, 255, 255))
    seg.putalpha(ring)
    im.alpha_composite(seg)
    hot = Image.new("RGBA", (K, K), (170, 222, 255, 255))
    hot.putalpha(core.filter(ImageFilter.GaussianBlur(S * 0.6)))
    im.alpha_composite(hot)
    return im.resize((size, size), Image.LANCZOS)


def light_strip(size, fname):
    """5 frames: none, green, yellow, red, blue (verified creator)."""
    cols = [None, (60, 200, 90), (240, 190, 40), (235, 60, 50), BLUE]
    strip = Image.new("RGBA", (size, size * 5), (0, 0, 0, 0))
    for i, col in enumerate(cols):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        if col:
            g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((2, 2, size - 3, size - 3), fill=col + (170,))
            im.alpha_composite(g.filter(ImageFilter.GaussianBlur(3)))
            # a lit lamp: brighter in the middle, even edge, no shine spot (so it reads as a light, not a knob)
            yy, xx = np.mgrid[0:size, 0:size]
            rr = np.hypot(xx - (size - 1) / 2, yy - (size - 1) / 2) / ((size - 12) / 2)
            hot = np.array([min(255, c + 90) for c in col], np.float32)
            lamp = hot[None, None] + (np.array(col, np.float32) - hot)[None, None] * np.clip(rr, 0, 1)[..., None] ** 1.5
            a = (np.clip((1.0 - rr) * (size / 2 - 6), 0, 1) * 255).astype(np.uint8)
            im.alpha_composite(Image.fromarray(np.dstack([lamp.clip(0, 255).astype(np.uint8), a]), "RGBA"))
        strip.paste(im, (0, i * size))
    strip.save(os.path.join(OUT, fname))


BW, BH = 206, 44


def badge_strip(fname):
    """2 frames: nothing / VERIFIED CREATOR styled like a lit MPC pad, but rounded: a dark button with a glowing
    blue edge made of segments with small gaps, a soft halo, and glowing blue text with a check seal."""
    S = 4
    w, h = BW * S, BH * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    edge = Image.new("L", (w, h), 0)
    ed = ImageDraw.Draw(edge)
    pad = 5 * S
    rad = 3 * S                                                   # a box with softly rounded corners, like a pad
    ed.rounded_rectangle((pad, pad, w - pad - 1, h - pad - 1), radius=rad, fill=255)
    t = int(2.6 * S)
    ed.rounded_rectangle((pad + t, pad + t, w - pad - 1 - t, h - pad - 1 - t), radius=rad - t, fill=0)
    g = int(1.6 * S)
    ed.rectangle((w / 2 - g, 0, w / 2 + g, h), fill=0)            # each side split in the middle, like the MPC pad light
    ed.rectangle((0, h / 2 - g, w, h / 2 + g), fill=0)
    halo = Image.new("RGBA", (w, h), BLUE + (0,))
    halo.putalpha(edge.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda v: int(v * 0.9)))
    body = Image.new("L", (w, h), 0)
    ImageDraw.Draw(body).rounded_rectangle((pad + t, pad + t, w - pad - 1 - t, h - pad - 1 - t), radius=rad - t, fill=255)
    dark = Image.new("RGBA", (w, h), (10, 12, 18, 255)); dark.putalpha(body)
    im.alpha_composite(dark)
    im.alpha_composite(halo)
    seg = Image.new("RGBA", (w, h), (40, 156, 255, 255)); seg.putalpha(edge)
    im.alpha_composite(seg)
    hot = Image.new("RGBA", (w, h), (175, 225, 255, 255)); hot.putalpha(edge.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(S * 0.5)))
    im.alpha_composite(hot)
    d = ImageDraw.Draw(im)
    fnt = font(17 * S, "Bold Condensed")
    tw = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), "VERIFIED CREATOR", font=fnt)[2]
    r = h * 0.17
    gapx = 7 * S
    x0 = (w - (2 * r + gapx + tw)) / 2                         # seal + text centred in the box
    cx, cy = x0 + r, h / 2
    # a plain lit check mark in the same pad blue (no social-media seal)
    tick = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tick).line((cx - r * 0.85, cy + r * 0.05, cx - r * 0.2, cy + r * 0.7, cx + r * 0.95, cy - r * 0.75),
                              fill=(120, 200, 255), width=int(S * 3.2), joint="curve")
    im.alpha_composite(tick.filter(ImageFilter.GaussianBlur(2 * S))); im.alpha_composite(tick)
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(txt).text((x0 + 2 * r + gapx, h / 2), "VERIFIED CREATOR", font=fnt, fill=(120, 200, 255), anchor="lm")
    glow = txt.filter(ImageFilter.GaussianBlur(2 * S))
    im.alpha_composite(glow); im.alpha_composite(txt)
    strip = Image.new("RGBA", (BW, BH * 2), (0, 0, 0, 0))
    strip.paste(im.resize((BW, BH), Image.LANCZOS), (0, BH))
    strip.save(os.path.join(OUT, fname))


def pad_check_strip(size, fname):
    """2 frames: nothing / a square MPC drum pad lit blue (edge split in the middle of each side) with a lit check."""
    S = 4
    K = size * S
    im = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    pad, t, g = 5 * S, int(3 * S), int(1.8 * S)
    edge = Image.new("L", (K, K), 0)
    ed = ImageDraw.Draw(edge)
    ed.rounded_rectangle((pad, pad, K - pad - 1, K - pad - 1), radius=3 * S, fill=255)
    ed.rounded_rectangle((pad + t, pad + t, K - pad - 1 - t, K - pad - 1 - t), radius=2 * S, fill=0)
    ed.rectangle((K / 2 - g, 0, K / 2 + g, K), fill=0)
    ed.rectangle((0, K / 2 - g, K, K / 2 + g), fill=0)
    body = Image.new("L", (K, K), 0)
    ImageDraw.Draw(body).rounded_rectangle((pad + t, pad + t, K - pad - 1 - t, K - pad - 1 - t), radius=2 * S, fill=255)
    dark = Image.new("RGBA", (K, K), (10, 12, 18, 255)); dark.putalpha(body)
    halo = Image.new("RGBA", (K, K), BLUE + (0,)); halo.putalpha(edge.filter(ImageFilter.GaussianBlur(3 * S)).point(lambda v: int(v * 0.9)))
    seg = Image.new("RGBA", (K, K), (40, 156, 255, 255)); seg.putalpha(edge)
    hot = Image.new("RGBA", (K, K), (175, 225, 255, 255)); hot.putalpha(edge.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(S * 0.5)))
    for layer in (dark, halo, seg, hot):
        im.alpha_composite(layer)
    c, r = K / 2, K * 0.2
    tick = Image.new("RGBA", (K, K), (0, 0, 0, 0))
    ImageDraw.Draw(tick).line((c - r * 0.95, c + r * 0.05, c - r * 0.25, c + r * 0.75, c + r * 1.0, c - r * 0.7),
                              fill=(140, 210, 255), width=int(S * 3.4), joint="curve")
    im.alpha_composite(tick.filter(ImageFilter.GaussianBlur(2 * S))); im.alpha_composite(tick)
    strip = Image.new("RGBA", (size, size * 2), (0, 0, 0, 0))
    strip.paste(im.resize((size, size), Image.LANCZOS), (0, size))
    strip.save(os.path.join(OUT, fname))


def pad_check(param, x, y, size, img):
    return entry("padcheck %d" % param, "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": img,
                                                  "numFrames": 2, "handleName": "Parameter %d" % param}, bounds(x, y, size, size))


def badge(param, x, y, img):
    return entry("badge %d" % param, "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": img,
                                               "numFrames": 2, "handleName": "Parameter %d" % param}, bounds(x, y, BW, BH))


def button(w, h, text, on, fname, accent=False):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top, bot = ((255, 170, 70), ORANGE) if (on or accent) else ((70, 70, 80), (44, 44, 52))
    if on and not accent:
        top, bot = (110, 110, 124), (80, 80, 92)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line((0, y, w, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=8, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(im, (0, 0), m)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=8, outline=(20, 20, 24), width=2)
    center(d, w / 2, h / 2, text, font(22, "Bold Condensed"), (20, 16, 10) if (on or accent) else (230, 228, 236))
    out.save(os.path.join(OUT, fname))


def row_button(on, fname):
    im = Image.new("RGBA", (780, 70), (0, 0, 0, 0))
    if on:
        ImageDraw.Draw(im).rounded_rectangle((0, 0, 779, 69), radius=10, outline=ORANGE + (255,), width=3)
    im.save(os.path.join(OUT, fname))


def bounds(x, y, w, h, focus="No"):
    return {"version": 1, "acceptsHWFocus": focus, "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
            "boundsType": "Absolute", "bounds": "%d %d %d %d" % (x, y, w, h)}


def entry(name, typ, data, b):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": typ, "data": data},
            "handle remapping": {"version": 1, "map": []}, "bounds": b}


def label(param, x, y, w, h, size, colour, just="left verticallyCentred", style="SemiBold"):
    return entry("text %d" % param, "Label", {"version": 1, "textStyle": {"version": 1, "font": {"version": 1, "name": "Titillium Web",
                 "style": style, "height": float(size)}, "colour": colour, "justification": just, "case": "Original"},
                 "type": "Value", "handleName": "Parameter %d" % param}, bounds(x, y, w, h))


def btn(name, param, x, y, w, h, on_img, off_img, momentary=True):
    handle = ("ResetOnGestureEnd/Parameter %d" if momentary else "Parameter %d") % param
    return entry(name, "Button", {"version": 2, "onImage": on_img, "offImage": off_img, "buttonId": 1, "numButtonsInGroup": 1,
                                  "handleName": handle, "gestureBehaviour": "Instant"}, bounds(x, y, w, h, "Yes"))


def light(param, x, y, size, img):
    return entry("light %d" % param, "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": img,
                                                "numFrames": 5, "handleName": "Parameter %d" % param}, bounds(x, y, size, size))


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    background().convert("RGB").save(os.path.join(OUT, "page.png"), optimize=True)
    light_strip(38, "light38.png")
    light_strip(44, "light44.png")
    button(220, 56, "SCAN AGAIN", False, "scan_off.png", accent=True)
    button(220, 56, "SCANNING", True, "scan_on.png")
    for n in ("PREV", "NEXT"):
        button(150, 44, n, False, n.lower() + "_off.png")
        button(150, 44, n, True, n.lower() + "_on.png")
    badge_strip("badge.png")
    pad_check_strip(52, "padcheck.png")
    row_button(False, "row_off.png")
    row_button(True, "row_on.png")

    items = []
    items.append(btn("scan", P_SCAN, 1040, 16, 220, 56, "scan_on.png", "scan_off.png"))
    items.append(label(P_SUMMARY, 560, 14, 460, 34, 24, "ffea861a", "right verticallyCentred", "Bold"))
    items.append(label(P_STATUS, 560, 48, 460, 28, 18, DIM, "right verticallyCentred", "Regular"))
    for r in range(ROWS):
        y = 100 + r * 76
        items.append(light(P_LIGHT1 + r, 34, y + 16, 38, "light38.png"))
        items.append(label(P_NAME1 + r, 90, y + 6, 470, 32, 24, TXT, style="SemiBold"))
        items.append(badge(P_BADGE1 + r, 566, y + 13, "badge.png"))
        items.append(label(P_INFO1 + r, 90, y + 38, 690, 26, 18, DIM, style="Regular"))
        items.append(btn("row %d" % (r + 1), P_ROW1 + r, 20, y, 780, 70, "row_on.png", "row_off.png"))
    items.append(btn("prev", P_PREV, 20, 568, 150, 44, "prev_on.png", "prev_off.png"))
    items.append(btn("next", P_NEXT, 180, 568, 150, 44, "next_on.png", "next_off.png"))
    items.append(label(P_PAGE, 344, 568, 180, 44, 18, DIM, style="Regular"))
    items.append(light(P_DLIGHT, 832, 134, 44, "light44.png"))
    items.append(pad_check(P_DBADGE, 1196, 106, 52, "padcheck.png"))   # verified: a lit drum pad with a check
    items.append(label(P_DTITLE, 886, 128, 364, 34, 26, TXT, style="Bold"))
    items.append(label(P_DWHERE, 886, 160, 364, 24, 16, DIM, style="Regular"))
    items.append(label(P_DVERDICT, 834, 196, 416, 44, 20, "ffea861a", style="SemiBold"))
    for k in range(LINES):
        items.append(label(P_DLINE1 + k, 834, 256 + k * 29, 416, 28, 18, TXT, style="Regular"))

    root = {"version": 2, "actions": [],
            "backgroundData": {"version": 1, "focussed": {"version": 1, "colour": "ff18181c", "image": "page.png"},
                               "unfocussed": {"version": 1, "colour": "ff18181c", "image": "page.png"}},
            "ignoreMousePresses": False, "disableCoarseDataWheel": False, "componentsData": items}
    tui = {"pageData": {"version": 1, "componentDefinitions": {"version": 2, "importFiles": [], "localComponentDefinitions": []},
                        "replacementStrings": [], "info": {"version": 1, "type": "CompleteDescription"},
                        "tabs": [{"version": 1, "tabName": "SCAN", "fnKeyIndex": 0, "fnKeySubIndex": 0,
                                  "componentDefinition": root, "qlinkBoundsData": []}]}}
    json.dump(tui, open(os.path.join(OUT, "TUI.json"), "w", encoding="utf-8"), indent=1)
    q = {"Q-Link %d" % i: -1 for i in range(1, 17)}
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [{"Tab": 1, "SubTab": 1, "Bank Direction": "Column", "Q-Links": q}]},
          "Program Mode Q-Links": {**q, "Q-Link 1": P_VOLUME}}
    json.dump(ql, open(os.path.join(OUT, "Q-Links.json"), "w", encoding="utf-8"), indent=1)
    print("skins/ written:", len(os.listdir(OUT)), "files")


if __name__ == "__main__":
    main()
