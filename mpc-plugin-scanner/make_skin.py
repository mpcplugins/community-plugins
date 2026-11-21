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
        d.ellipse((34, y + 16, 72, y + 54), fill=(10, 10, 12), outline=(70, 70, 80), width=2)
    # details panel
    d.rounded_rectangle((816, 100, 1260, 556), radius=12, fill=PANEL, outline=EDGE)
    d.text((834, 110), "DETAILS", font=font(16, "Bold Condensed"), fill=(150, 148, 160))
    d.ellipse((832, 134, 876, 178), fill=(10, 10, 12), outline=(70, 70, 80), width=2)
    d.line((832, 248, 1244, 248), fill=EDGE, width=1)
    # legend + footer
    fy = 576
    for i, (col, word) in enumerate((((60, 200, 90), "CLEAN"), ((240, 190, 40), "CHECK"), ((235, 60, 50), "RISKY"))):
        x = 540 + i * 92
        d.ellipse((x, fy + 4, x + 16, fy + 20), fill=col)
        d.text((x + 22, fy + 2), word, font=font(17, "Bold Condensed"), fill=(200, 198, 206))
    d.text((834, 566), "A warning-sign scan, not a guarantee.", font=font(16, "SemiCondensed"), fill=(150, 148, 160))
    d.text((834, 588), "Nothing is changed, run or sent anywhere.", font=font(16, "SemiCondensed"), fill=(150, 148, 160))
    return im


def light_strip(size, fname):
    """4 frames: none, green, yellow, red."""
    cols = [None, (60, 200, 90), (240, 190, 40), (235, 60, 50)]
    strip = Image.new("RGBA", (size, size * 4), (0, 0, 0, 0))
    for i, col in enumerate(cols):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        if col:
            g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((2, 2, size - 3, size - 3), fill=col + (170,))
            im.alpha_composite(g.filter(ImageFilter.GaussianBlur(3)))
            d = ImageDraw.Draw(im)
            d.ellipse((6, 6, size - 7, size - 7), fill=col)
            d.ellipse((size * 0.28, size * 0.22, size * 0.5, size * 0.42), fill=(255, 255, 255, 120))
        strip.paste(im, (0, i * size))
    strip.save(os.path.join(OUT, fname))


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
                                                "numFrames": 4, "handleName": "Parameter %d" % param}, bounds(x, y, size, size))


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
    row_button(False, "row_off.png")
    row_button(True, "row_on.png")

    items = []
    items.append(btn("scan", P_SCAN, 1040, 16, 220, 56, "scan_on.png", "scan_off.png"))
    items.append(label(P_SUMMARY, 560, 14, 460, 34, 24, "ffea861a", "right verticallyCentred", "Bold"))
    items.append(label(P_STATUS, 560, 48, 460, 28, 18, DIM, "right verticallyCentred", "Regular"))
    for r in range(ROWS):
        y = 100 + r * 76
        items.append(light(P_LIGHT1 + r, 34, y + 16, 38, "light38.png"))
        items.append(label(P_NAME1 + r, 90, y + 6, 690, 32, 24, TXT, style="SemiBold"))
        items.append(label(P_INFO1 + r, 90, y + 38, 690, 26, 18, DIM, style="Regular"))
        items.append(btn("row %d" % (r + 1), P_ROW1 + r, 20, y, 780, 70, "row_on.png", "row_off.png"))
    items.append(btn("prev", P_PREV, 20, 568, 150, 44, "prev_on.png", "prev_off.png"))
    items.append(btn("next", P_NEXT, 180, 568, 150, 44, "next_on.png", "next_off.png"))
    items.append(label(P_PAGE, 344, 568, 180, 44, 18, DIM, style="Regular"))
    items.append(light(P_DLIGHT, 832, 134, 44, "light44.png"))
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
