# Hybrid Phatt (The Disk King)

A 90s-style ROM sound module for Akai MPC standalone hardware, in the spirit of the classic hip-hop / R&B rack modules: layered multi-sample voices, a big backlit LCD, and a hardware-style screen that crosses an old MPC 60 with a 90s sound module.

**Version 0.2.0 — beta. Tested on an Akai MPC Live III (MPC OS 3.10.1). Use at your own risk.**

![Hybrid Phatt on an MPC Live III](hybrid-phatt.png)

## All screens

| | |
|---|---|
| ![MAIN](screens/01-main.png) | ![LAYERS](screens/02-layers.png) |
| ![FILTER](screens/03-filter.png) | ![MOD](screens/04-mod.png) |
| ![GROOVE](screens/05-groove.png) | ![FX](screens/06-fx.png) |

## What is new in 0.2

- **KEYS page (7th tab):** an on-screen keyboard with Key 61 and Key 37 ranges. Hit a pad and the matching key lights up; tap a key on the screen to play it (handy on an MPC with no keys, like the Live III).
- **HELP popup** on the MAIN page: where the sounds come from and how to load your own bank.
- **Load your own E-mu bank:** put it in a folder named `Hybrid Phatt Sets` at the top of any MPC drive (internal, SSD or USB):
  `Hybrid Phatt Sets / My Bank / My Bank.exb` and `Hybrid Phatt Sets / My Bank / SamplePool / (the .ebl files)`.
- LCD shows **LAYERS L1-L4**: lit when a layer is used, flashing while it plays. Bank line reads "Hybrid Phatt bank".
- Knob and fader values show their units (Hz, ms, dB, semitones).
- PREV / NEXT step one preset per tap and no longer stick down.

## Also in Hybrid Phatt

- Pages: **MAIN, LAYERS, FILTER, MOD, GROOVE, FX, KEYS**, with LED-ring knobs, vertical chrome faders, lit keys and a backlit LCD. Q-Links mapped in groups of four on every page.
- A sample-bank engine that plays an E-mu Emulator X style bank: 4 banks of 128 presets, every voice with its key and velocity splits, root keys, tuning, volume, pan, filter and 6-stage envelope, grouped into 4 layers.

## Not yet

- **No sound bank is included** (copyright). Without one the plugin plays a simple test saw and the LCD says "SOUND BANK NOT FOUND". Load your own .exb as above.
- The MOD, GROOVE and FX pages are on screen but do not change the sound yet.

## Install

Needs MPC OS 3.10.1 or later, with **Preferences → Enhancements (Beta) → Enable Enhancements** and **External Plugin Support** turned on.

1. Download `Hybrid-Phatt-0.2.0-mpc-sdk.zip` from the Releases page.
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
