# Hybrid Phatt (The Disk King)

A 90s-style ROM sound module for Akai MPC standalone hardware, in the spirit of the classic hip-hop / R&B rack modules: layered multi-sample voices, a big backlit LCD, and a hardware-style screen that crosses an old MPC 60 with a 90s sound module.

**Version 0.1.0 — early beta. Tested on an Akai MPC Live III (MPC OS 3.10.1). Use at your own risk.**

## What is in 0.1

- Six touch-screen pages: **MAIN, LAYERS, FILTER, MOD, GROOVE, FX**, with LED-ring knobs, vertical chrome faders, lit keys and a backlit LCD. Q-Links mapped in groups of four on every page.
- A sample-bank engine that plays an E-mu Emulator X style bank: 4 banks of 128 presets, every voice with its key and velocity splits, root keys, tuning, volume, pan, filter and 6-stage envelope, grouped into 4 layers.
- PREV / NEXT / BANK 0–3 preset browsing, preset name and category on the LCD, layer lights.

## What is not in 0.1

- **No sound bank is included.** Without one the plugin plays a simple test saw and the LCD says "SOUND BANK NOT FOUND". A bundled original sound set is planned.
- The MOD, GROOVE and FX pages are on screen but do not change the sound yet.

## Install

Needs MPC OS 3.10.1 or later, with **Preferences → Enhancements (Beta) → Enable Enhancements** and **External Plugin Support** turned on.

1. Download `hybrid-phatt-0.1.0-mpc.zip` from the Releases page.
2. Copy the folder `The Disk King - VST - Hybrid Phatt` into a folder named `VST2 Plugins` on your MPC's internal drive.
3. Restart the MPC and load **Hybrid Phatt** on a plugin track.

## Build from source

Built with Akai's MPC Plugin SDK. Put this folder in the SDK's `plugins/` folder as `Hybrid Phatt`, then:

```
python tools/build.py "plugins/Hybrid Phatt"
python "plugins/Hybrid Phatt/make_skin.py"
python tools/build.py "plugins/Hybrid Phatt"
```

## Disclaimer

Provided as is, with no warranty of any kind. Use entirely at your own risk; The Disk King is not responsible in any way for any loss, damage or problem from using it.

More MPC sounds: https://thediskking.com
