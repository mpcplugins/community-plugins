// HybridPhatt.cpp - Hybrid Phatt (The Disk King): a Mo'Phatt-style sound module for the MPC.
//
// STAGE 2: plays the sound bank in Content/Mo'Phatt/ (an E-mu Emulator X bank: Mo'Phatt.exb with the
// presets, SamplePool/*.ebl with the sounds). The bank is the owner's own copy for personal use; it
// must never be shipped with a released build.
//
// At load time a worker thread reads the whole bank into memory (never in process()):
//   - every preset: voices with key/velocity windows, volume (dB), pan, fine tune, filter (type, cutoff, Q)
//     and the 6-stage amp envelope (Attack 1/2, Decay 1/2 = sustain, Release 1/2), each voice's zones
//     (sound number, root key, fine tune, volume, key/velocity windows)
//   - every sound as 16-bit frames (mono or stereo) with its own sample rate and loop
// Until it is ready the plugin plays a simple saw so it is never silent.
//
// Per note: every voice whose key/velocity window contains the note, and in it every matching zone,
// starts one "part": interpolated sample playback at (note - root + tuning) -> lowpass SVF (the
// preset's filter and the Cutoff knob, whichever is lower) -> 6-stage envelope -> pan -> mix.
// Voices are grouped into 4 layers (voice 1, 5, 9.. = layer 1; 2, 6, 10.. = layer 2; ...) for the
// LAYERS page. Not yet wired (stage 3): the preset's own LFOs, cords and effects, morph filter types,
// the MOD / GROOVE / FX pages.
//
// Parameter ids and order are PERMANENT once anyone saves a project with this plugin.
// Append new parameters at the end only.

#include "mpc_plugin.h"
#include "dsp/math.h"
#include "dsp/svf.h"

#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>
#include <filesystem>
#include <map>
#include <string>
#include <thread>
#include <vector>

using namespace mpc::dsp;

class HybridPhatt : public mpc::Plugin
{
public:
    enum Params
    {
        kVolume, kBank, kPreset, kPrev, kNext,
        kCutoff, kReso, kMorph, kDrive,
        kAttack, kDecay, kSustain, kRelease,
        kGlide, kTune,
        kLvl1, kLvl2, kLvl3, kLvl4,
        kPan1, kPan2, kPan3, kPan4,
        kCoarse1, kCoarse2, kCoarse3, kCoarse4,
        kFine1, kFine2, kFine3, kFine4,
        kOn1, kOn2, kOn3, kOn4,
        kFType, kFEnvAmt, kKeyTrack, kVelFilt, kFA, kFD, kFS, kFR,
        kL1Shape, kL1Rate, kL1Depth, kL1Delay, kL1Sync,
        kL2Shape, kL2Rate, kL2Depth, kL2Delay, kL2Sync,
        kM1Src, kM2Src, kM3Src, kM4Src, kM5Src, kM6Src,
        kM1Dst, kM2Dst, kM3Dst, kM4Dst, kM5Dst, kM6Dst,
        kM1Amt, kM2Amt, kM3Amt, kM4Amt, kM5Amt, kM6Amt,
        kArpOn, kLatch, kArpMode, kArpRate, kArpGate, kArpSwing, kArpOct,
        kBeatPlay, kBeatVar, kBL1, kBL2, kBL3, kBL4, kBSwing, kBHum,
        kRvOn, kRvType, kRvSize, kRvDamp, kRvPre, kRvMix,
        kChOn, kChType, kChRate, kChDepth, kChFb, kChMix,
        kDlOn, kDlTime, kDlFb, kDlTone, kDlWidth, kDlMix,
        kLoFi,
        kStep0,                          // 64 step switches: 4 lanes x 16 steps
        kInfo = kStep0 + 64,             // display only: category and voice count of the current preset
        kAct1, kAct2, kAct3, kAct4,      // display only: layer lights (0 unused, 1 used by the preset, 2 playing)
        kBankState,                      // display only: 0 bank ready, 1 loading, 2 no bank found (shows the instructions)
        kLastNote,                       // display only: last note played (KEYS tab)
        kKey0,                           // 61 keys C1..C6 (MIDI 36..96): lit while held; tapping one plays it
        kKeyLast = kKey0 + 60,
        kNumParams
    };

    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo i;
        i.name = "Hybrid Phatt";
        i.vendor = "The Disk King";
        i.uniqueId = MPC_FOURCC('T', 'H', 'y', 'P');   // must match "uid" in plugin.json
        i.version = 2000;
        i.isInstrument = true;
        i.numInputs = 0;
        i.numOutputs = 2;
        return i;
    }

    HybridPhatt() : mpc::Plugin(makeInfo())
    {
        using namespace mpc;
        // MAIN
        addParam(floatParam ("volume",  "Volume", -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(choiceParam("bank",    "Bank", {"Bank 0", "Bank 1", "Bank 2", "Bank 3"}, 0));
        addParam(intParam   ("preset",  "Preset", 0, 127, 0));
        addParam(boolParam  ("prev",    "Prev", false));
        addParam(boolParam  ("next",    "Next", false));
        addParam(logParam   ("cutoff",  "Cutoff", 20.0f, 20000.0f, 20000.0f, "Hz", 0));
        addParam(floatParam ("reso",    "Resonance", 0.0f, 100.0f, 10.0f, "%", 0));
        addParam(floatParam ("morph",   "Morph", 0.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("drive",   "Drive", 0.0f, 100.0f, 0.0f, "%", 0));
        // Envelope controls are offsets on the preset's own envelope: 0 = as programmed.
        addParam(floatParam ("attack",  "Attack", -100.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("decay",   "Decay", -100.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("sustain", "Sustain", -100.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("release", "Release", -100.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("glide",   "Glide", 0.0f, 2000.0f, 0.0f, "ms", 0, 0.5f));
        addParam(intParam   ("tune",    "Tune", -24, 24, 0, "st"));
        // LAYERS
        for (int l = 1; l <= 4; ++l) addParam(floatParam(id("lvl", l), name("Layer ", l, " Level"), -40.0f, 6.0f, 0.0f, "dB", 1));
        for (int l = 1; l <= 4; ++l) addParam(floatParam(id("pan", l), name("Layer ", l, " Pan"), -100.0f, 100.0f, 0.0f, "", 0));
        for (int l = 1; l <= 4; ++l) addParam(intParam  (id("coarse", l), name("Layer ", l, " Coarse"), -24, 24, 0, "st"));
        for (int l = 1; l <= 4; ++l) addParam(floatParam(id("fine", l), name("Layer ", l, " Fine"), -100.0f, 100.0f, 0.0f, "ct", 0));
        for (int l = 1; l <= 4; ++l) addParam(boolParam (id("on", l), name("Layer ", l, " On"), true));
        // FILTER
        addParam(choiceParam("ftype",   "Filter Type", {"Phatt Low", "Smooth Low", "Band Sweep", "High Air", "Vowel Ah-Ee",
                                                        "Vowel Oo-Ah", "Phaser", "Comb Metal", "Peak Boost"}, 0));
        addParam(floatParam ("fenv",    "Env Amount", -100.0f, 100.0f, 0.0f, "%", 0));
        addParam(floatParam ("keytrk",  "Key Track", 0.0f, 100.0f, 50.0f, "%", 0));
        addParam(floatParam ("velfilt", "Vel>Filter", 0.0f, 100.0f, 30.0f, "%", 0));
        addParam(logParam   ("fa",      "Filt Attack", 1.0f, 10000.0f, 5.0f, "ms", 0));
        addParam(logParam   ("fd",      "Filt Decay", 1.0f, 10000.0f, 300.0f, "ms", 0));
        addParam(floatParam ("fs",      "Filt Sustain", 0.0f, 100.0f, 40.0f, "%", 0));
        addParam(logParam   ("fr",      "Filt Release", 1.0f, 10000.0f, 300.0f, "ms", 0));
        // MOD
        const std::vector<std::string> lfoShapes = {"Sine", "Triangle", "Saw", "Square", "S&H"};
        for (int k = 1; k <= 2; ++k)
        {
            addParam(choiceParam(id("lfoshape", k), name("LFO ", k, " Shape"), lfoShapes, k == 1 ? 0 : 1));
            addParam(logParam   (id("lforate", k),  name("LFO ", k, " Rate"), 0.05f, 30.0f, k == 1 ? 2.0f : 0.5f, "Hz", 2));
            addParam(floatParam (id("lfodepth", k), name("LFO ", k, " Depth"), 0.0f, 100.0f, 0.0f, "%", 0));
            addParam(logParam   (id("lfodelay", k), name("LFO ", k, " Delay"), 1.0f, 5000.0f, 1.0f, "ms", 0));
            addParam(boolParam  (id("lfosync", k),  name("LFO ", k, " Sync"), false));
        }
        const std::vector<std::string> srcs = {"LFO 1", "LFO 2", "Filter Env", "Velocity", "Mod Wheel", "Aftertouch", "Key", "Random"};
        const std::vector<std::string> dsts = {"Cutoff", "Pitch", "Pan", "Level", "Morph", "Reso", "LFO 1 Rate", "Layer Mix"};
        const int defSrc[6] = {0, 1, 3, 4, 5, 7}, defDst[6] = {0, 2, 3, 4, 1, 5};
        for (int k = 1; k <= 6; ++k) addParam(choiceParam(id("msrc", k), name("Mod ", k, " Source"), srcs, defSrc[k - 1]));
        for (int k = 1; k <= 6; ++k) addParam(choiceParam(id("mdst", k), name("Mod ", k, " Dest"), dsts, defDst[k - 1]));
        for (int k = 1; k <= 6; ++k) addParam(floatParam (id("mamt", k), name("Mod ", k, " Amount"), -100.0f, 100.0f, 0.0f, "%", 0));
        // GROOVE
        addParam(boolParam  ("arpon",   "Arp On", false));
        addParam(boolParam  ("latch",   "Latch", false));
        addParam(choiceParam("arpmode", "Arp Mode", {"Up", "Down", "Up/Dn", "Random", "Played", "Chord"}, 0));
        addParam(choiceParam("arprate", "Arp Rate", {"1/4", "1/8", "1/8T", "1/16", "1/16T", "1/32"}, 3));
        addParam(floatParam ("arpgate", "Arp Gate", 5.0f, 100.0f, 60.0f, "%", 0));
        addParam(floatParam ("arpswing","Arp Swing", 50.0f, 75.0f, 54.0f, "%", 0));
        addParam(intParam   ("arpoct",  "Octaves", 1, 4, 1));
        addParam(boolParam  ("beatplay","Beat Play", false));
        addParam(choiceParam("beatvar", "Variation", {"A", "B", "Fill"}, 0));
        const char* lanes[4] = {"Kick", "Snare", "Hat", "Perc"};
        for (int k = 0; k < 4; ++k) addParam(floatParam(id("blvl", k + 1), keep(std::string(lanes[k]) + " Level"), -40.0f, 6.0f, 0.0f, "dB", 1));
        addParam(floatParam ("bswing",  "Beat Swing", 50.0f, 75.0f, 56.0f, "%", 0));
        addParam(floatParam ("bhum",    "Humanize", 0.0f, 100.0f, 20.0f, "%", 0));
        // FX
        addParam(boolParam  ("rvon",    "Reverb On", true));
        addParam(choiceParam("rvtype",  "Reverb Type", {"Room", "Hall", "Plate", "Spring"}, 2));
        addParam(floatParam ("rvsize",  "Size", 0.0f, 100.0f, 55.0f, "%", 0));
        addParam(floatParam ("rvdamp",  "Damp", 0.0f, 100.0f, 40.0f, "%", 0));
        addParam(logParam   ("rvpre",   "Pre-Delay", 1.0f, 200.0f, 15.0f, "ms", 0));
        addParam(floatParam ("rvmix",   "Reverb", 0.0f, 100.0f, 25.0f, "%", 0));
        addParam(boolParam  ("chon",    "Chorus On", true));
        addParam(choiceParam("chtype",  "Chorus Type", {"Chorus", "Ensemble", "Flanger"}, 0));
        addParam(logParam   ("chrate",  "Chorus Rate", 0.05f, 10.0f, 0.6f, "Hz", 2));
        addParam(floatParam ("chdepth", "Chorus Depth", 0.0f, 100.0f, 45.0f, "%", 0));
        addParam(floatParam ("chfb",    "Chorus Fdbk", 0.0f, 100.0f, 10.0f, "%", 0));
        addParam(floatParam ("chmix",   "Chorus", 0.0f, 100.0f, 10.0f, "%", 0));
        addParam(boolParam  ("dlon",    "Delay On", false));
        addParam(choiceParam("dltime",  "Delay Time", {"1/8", "1/8D", "1/4", "1/4D"}, 1));
        addParam(floatParam ("dlfb",    "Delay Fdbk", 0.0f, 100.0f, 35.0f, "%", 0));
        addParam(logParam   ("dltone",  "Delay Tone", 200.0f, 20000.0f, 6000.0f, "Hz", 0));
        addParam(floatParam ("dlwidth", "Delay Width", 0.0f, 100.0f, 80.0f, "%", 0));
        addParam(floatParam ("dlmix",   "Delay", 0.0f, 100.0f, 20.0f, "%", 0));
        addParam(floatParam ("lofi",    "Lo-Fi", 0.0f, 100.0f, 0.0f, "%", 0));
        // GROOVE steps (boom bap pattern by default)
        const char* pat[4] = {"1000001010000010", "0000100000001000", "1010101010111010", "0001000000100100"};
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 16; ++c)
                addParam(boolParam(id("step", r * 16 + c), keep(std::string(lanes[r]) + " " + std::to_string(c + 1)), pat[r][c] == '1'));
        // display only (appended in stage 2)
        {
            Param p = intParam("info", "Info", 0, 1, 0);
            p.automatable = false;
            addParam(p);
            for (int l = 1; l <= 4; ++l) { Param a = intParam(id("act", l), name("Layer ", l, " Light"), 0, 2, 0); a.automatable = false; addParam(a); }
            Param bs = intParam("bankstate", "Bank State", 0, 2, 1); bs.automatable = false; addParam(bs);
            Param ln = intParam("lastnote", "Last Note", 0, 127, 0); ln.automatable = false; addParam(ln);
            static const char* nn[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
            for (int k = 0; k <= 60; ++k)
            {
                const int note = kFirstKey + k;
                Param kp = boolParam(id("key", k), keep(std::string("Key ") + nn[note % 12] + std::to_string(note / 12 - 2)), false);
                kp.automatable = false; addParam(kp);
            }
        }
        if (numParams() != kNumParams) mpc::log("HybridPhatt: parameter count mismatch (%d vs %d)", numParams(), (int)kNumParams);

        loader_ = std::thread([this] { loadBank(); });
    }

    ~HybridPhatt() override
    {
        quit_.store(true);
        if (loader_.joinable()) loader_.join();
    }

    // ----- lifecycle --------------------------------------------------------
    void prepare(double sampleRate, int /*maxBlockSize*/) override
    {
        sr_ = (float)sampleRate;
        for (auto& v : voices_) { v.filter.setSampleRate(sampleRate); v.active = false; }
        volSmooth_ = dbToGain(get(kVolume));
    }

    void reset() override
    {
        for (auto& v : voices_) { v.active = false; v.filter.reset(); }
    }

    // PREV / NEXT are momentary buttons: step the preset number, then let the button go.
    void parameterChanged(int index, float plain) override
    {
        // The MPC owns the button (lit while touched, dark when released). Step once on the press only,
        // and tell the screen about the new preset from process(), not from inside the host's own call.
        if (index >= kKey0 && index <= kKeyLast)
        {
            if (!selfSet_) (plain >= 0.5f ? tapPress_ : tapRelease_)[index - kKey0].fetch_add(1);   // counted: a quick tap is never lost
            return;
        }
        if (index == kPrev || index == kNext)
        {
            const bool down = plain >= 0.5f;
            bool& was = index == kNext ? nextDown_ : prevDown_;
            if (down && !was && !stepping_)
            {
                stepping_ = true;
                int p = getInt(kPreset) + (index == kNext ? 1 : -1), b = getInt(kBank);
                if (p > 127) { p = 0; b = (b + 1) % 4; }
                if (p < 0)   { p = 127; b = (b + 3) % 4; }
                set(kBank, (float)b); set(kPreset, (float)p);
                stepping_ = false;
                notifyPending_.store(true);
            }
            was = down;
        }
        else if ((index == kBank || index == kPreset) && !stepping_) notifyPending_.store(true);
    }

    bool formatValue(int index, float plain, std::string& out) override
    {
        if (index == kPreset)
        {
            const int p = (int)std::lround(plain);
            char b[96];
            const Preset* pr = currentPreset(getInt(kBank), p);
            if (pr) std::snprintf(b, sizeof b, "%03d  %s", p, pr->title.c_str());
            else std::snprintf(b, sizeof b, "%03d", p);
            out = b;
            return true;
        }
        if (index == kInfo)
        {
            const int st = state_.load(std::memory_order_acquire);
            if (st == 0) { out = "LOADING SOUNDS..."; return true; }
            if (st == 2) { out = "SOUND BANK NOT FOUND"; return true; }
            const Preset* pr = currentPreset(getInt(kBank), getInt(kPreset));
            if (!pr) { out = "EMPTY"; return true; }
            char b[96];
            std::snprintf(b, sizeof b, "%s  -  %d VOICE%s", pr->cat.c_str(), (int)pr->voices.size(), pr->voices.size() == 1 ? "" : "S");
            out = b;
            return true;
        }
        if (index == kLastNote)
        {
            static const char* nn[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
            const int n = lastNote_.load(), v = lastVel_.load();
            if (n < 0) { out = "HIT A PAD OR TAP A KEY"; return true; }
            char b[48]; std::snprintf(b, sizeof b, "%s%d   NOTE %d   VEL %d", nn[n % 12], n / 12 - 2, n, v); out = b; return true;
        }
        if (index == kBank)
        {
            char b[96];
            const int st = state_.load(std::memory_order_acquire);
            std::snprintf(b, sizeof b, "%s%sBANK %d", st == 1 ? bankName_.c_str() : "", st == 1 ? "  -  " : "", (int)std::lround(plain));
            out = b;
            return true;
        }
        if (index >= kPan1 && index <= kPan4)
        {
            const int v = (int)std::lround(plain);
            out = v == 0 ? "C" : (v < 0 ? "L" + std::to_string(-v) : "R" + std::to_string(v));
            return true;
        }
        // units on every readout (the MPC shows only the value text)
        const mpc::Param& pr = param(index);
        if (pr.kind == mpc::Param::Kind::Choice || pr.kind == mpc::Param::Kind::Bool || pr.unit.empty()) return false;
        char b[32];
        const std::string& u = pr.unit;
        if (u == "Hz") { if (plain >= 1000.0f) std::snprintf(b, sizeof b, "%.1f kHz", plain / 1000.0f); else if (plain < 10.0f) std::snprintf(b, sizeof b, "%.2f Hz", plain); else std::snprintf(b, sizeof b, "%d Hz", (int)std::lround(plain)); }
        else if (u == "ms") { if (plain >= 1000.0f) std::snprintf(b, sizeof b, "%.2f s", plain / 1000.0f); else std::snprintf(b, sizeof b, "%d ms", (int)std::lround(plain)); }
        else if (u == "%") std::snprintf(b, sizeof b, "%s%d%%", (pr.min < 0.0f && plain > 0.5f) ? "+" : "", (int)std::lround(plain));
        else if (u == "dB") std::snprintf(b, sizeof b, "%s%.1f dB", plain > 0.05f ? "+" : "", std::fabs(plain) < 0.05f ? 0.0f : plain);
        else if (u == "st" || u == "ct") std::snprintf(b, sizeof b, "%s%d %s", plain > 0.5f ? "+" : "", (int)std::lround(plain), u.c_str());
        else return false;
        out = b;
        return true;
    }

    // ----- audio ------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        readBlockSettings();
        // screen keys: every press plays; a release ends the note, but never sooner than 0.25 s (quick taps still sound)
        for (int k = 0; k <= 60; ++k)
        {
            const int pr = tapPress_[k].load(), rl = tapRelease_[k].load();
            if (pr != pressSeen_[k])
            {
                pressSeen_[k] = pr;
                if (tapHeld_[k]) noteOff(kFirstKey + k);
                tapHeld_[k] = true; tapLeft_[k] = (int)(0.25f * sr_); releaseWait_[k] = false;
                lastNote_.store(kFirstKey + k); lastVel_.store(100); noteDirty_ = true;
                noteOn(kFirstKey + k, 100);
            }
            if (rl != releaseSeen_[k]) { releaseSeen_[k] = rl; if (tapHeld_[k]) releaseWait_[k] = true; }
            if (tapHeld_[k])
            {
                tapLeft_[k] -= ctx.numFrames;
                if (releaseWait_[k] && tapLeft_[k] <= 0) { tapHeld_[k] = false; releaseWait_[k] = false; noteOff(kFirstKey + k); }
            }
        }
        int pos = 0;
        for (int e = 0; e < ctx.numMidiEvents; ++e)
        {
            const mpc::MidiEvent& ev = ctx.midi[e];
            if (ev.sampleOffset > pos) { render(ctx, pos, ev.sampleOffset); pos = ev.sampleOffset; }
            handleMidi(ev);
        }
        render(ctx, pos, ctx.numFrames);
        updateLights(ctx.numFrames);
    }

private:
    int lightCount_ = 0;
    int lights_[4] = {-1, -1, -1, -1};
    void updateLights(int frames)
    {
        lightCount_ += frames;
        if (lightCount_ < (int)(sr_ / 30.0f)) return;
        lightCount_ = 0;
        {
            const int st = state_.load(std::memory_order_acquire), shown = st == 1 ? 0 : (st == 0 ? 1 : 2);
            if (shown != shownState_) { shownState_ = shown; set(kBankState, (float)shown); notifyHostParameterChanged(kBankState);
                                        notifyPending_.store(true); }
        }
        if (notifyPending_.exchange(false))
        {
            notifyHostParameterChanged(kBank); notifyHostParameterChanged(kPreset); notifyHostParameterChanged(kInfo);
        }
        if (noteDirty_) { noteDirty_ = false; set(kLastNote, (float)lastNote_.load()); notifyHostParameterChanged(kLastNote); }
        for (int k = 0; k <= 60; ++k)
        {
            const bool lit = held_[kFirstKey + k] > 0 || tapHeld_[k];
            if (lit != getBool(kKey0 + k))
            {
                keyLit_[k] = lit; selfSet_ = true; set(kKey0 + k, lit ? 1.0f : 0.0f); selfSet_ = false; notifyHostParameterChanged(kKey0 + k);
            }
        }
        const Preset* pr = currentPreset(b_.bank, b_.preset);
        for (int l = 0; l < 4; ++l)
        {
            bool playing = false;
            for (const auto& p : voices_) if (p.active && !p.released && p.layer == l && !p.fallbackSaw) { playing = true; break; }
            const int v = playing ? 2 : ((pr && (int)pr->voices.size() > l) ? 1 : 0);
            if (v != lights_[l]) { lights_[l] = v; set(kAct1 + l, (float)v); notifyHostParameterChanged(kAct1 + l); }
        }
    }

    // ======================================================================= bank data
    struct Sample
    {
        std::vector<int16_t> data;       // interleaved when stereo
        int ch = 1, frames = 0;
        float rate = 44100.0f;
        int loopStart = 0, loopEnd = -1;  // inclusive end; loopEnd < loopStart = no loop
    };
    struct Zone
    {
        int sample = -1;                 // index into samples_
        int root = 60;
        float fine = 0.0f, gain = 1.0f;
        uint8_t klo = 0, khi = 127, vlo = 0, vhi = 127;
    };
    struct VoiceDef
    {
        uint8_t klo = 0, khi = 127, vlo = 0, vhi = 127;
        float gain = 1.0f, pan = 0.0f, fine = 0.0f, filterHz = 0.0f, filterQ = 0.0f;
        float env[6][2] = {{0, 1}, {0, 1}, {0, 1}, {0, 1}, {0.05f, 0}, {0, 0}};
        int zoneFirst = 0, zoneCount = 0;
    };
    struct Preset
    {
        std::string title, cat;
        std::vector<VoiceDef> voices;
        std::vector<Zone> zones;
    };

    const Preset* currentPreset(int bank, int preset) const
    {
        if (state_.load(std::memory_order_acquire) != 1) return nullptr;
        const int i = clamp(bank, 0, 3) * 128 + clamp(preset, 0, 127);
        if (i < 0 || i >= (int)presets_.size() || presets_[(size_t)i].voices.empty()) return nullptr;
        return &presets_[(size_t)i];
    }

    // big-endian readers
    static uint32_t be32(const uint8_t* p) { return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
    static uint16_t be16(const uint8_t* p) { return (uint16_t)((p[0] << 8) | p[1]); }
    static uint32_t le32(const uint8_t* p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
    static float bef(const uint8_t* p) { uint32_t u = be32(p); float f; std::memcpy(&f, &u, 4); return std::isfinite(f) ? f : 0.0f; }
    static std::string utf16(const uint8_t* p, int n)
    {
        std::string s;
        for (int i = 0; i + 1 < n; i += 2) { const int c = p[i] | (p[i + 1] << 8); if (!c) break; s += (c < 128) ? (char)c : '?'; }
        return s;
    }
    struct TocEntry { char tag[5]; uint32_t size, off; int idx; std::string name; };
    static bool readToc(const std::vector<uint8_t>& d, std::vector<TocEntry>& out)
    {
        if (d.size() < 20 || std::memcmp(d.data(), "FORM", 4) || std::memcmp(d.data() + 8, "E5B0", 4)) return false;
        const uint32_t n = be32(&d[16]) / 78;
        for (uint32_t i = 0; i < n; ++i)
        {
            const size_t o = 20 + (size_t)i * 78;
            if (o + 78 > d.size()) break;
            TocEntry e;
            std::memcpy(e.tag, &d[o], 4); e.tag[4] = 0;
            e.size = be32(&d[o + 4]); e.off = be32(&d[o + 8]); e.idx = be16(&d[o + 12]);
            e.name = utf16(&d[o + 14], 64);
            out.push_back(e);
        }
        return true;
    }
    struct Chunk { std::string tag; size_t o = 0, n = 0; std::vector<Chunk> kids; };
    static void chunks(const std::vector<uint8_t>& d, size_t o, size_t end, std::vector<Chunk>& out, int depth = 0)
    {
        while (o + 8 <= end && end <= d.size() && depth < 8)
        {
            Chunk c;
            c.tag.assign((const char*)&d[o], 4);
            const size_t sz = be32(&d[o + 4]), s = o + 8;
            if (s + sz > end) break;
            if (c.tag == "LIST" && sz >= 4) { c.tag = "LIST:" + std::string((const char*)&d[s], 4); chunks(d, s + 4, s + sz, c.kids, depth + 1); }
            else if (c.tag == "E5V1") chunks(d, s, s + sz, c.kids, depth + 1);
            else { c.o = s; c.n = sz; }
            out.push_back(std::move(c));
            o = s + sz;
        }
    }
    static const Chunk* find(const std::vector<Chunk>& v, const char* tag)
    {
        for (const auto& c : v) if (c.tag == tag) return &c;
        return nullptr;
    }
    static std::string catName(const std::string& pre)
    {
        static const std::map<std::string, std::string> m = {{"bas", "BASS"}, {"bts", "BEATS"}, {"kit", "KIT"}, {"prc", "PERC"}, {"key", "KEYS"},
            {"syn", "SYNTH"}, {"led", "LEAD"}, {"pad", "PAD"}, {"str", "STRINGS"}, {"gtr", "GUITAR"}, {"brs", "BRASS"}, {"hit", "HITS"},
            {"vox", "VOX"}, {"amb", "AMBIENT"}, {"org", "ORGAN"}, {"drm", "DRUMS"}, {"sfx", "FX"}};
        auto it = m.find(pre);
        if (it != m.end()) return it->second;
        std::string u = pre; for (auto& ch : u) ch = (char)std::toupper((unsigned char)ch);
        return u;
    }

    // one .ebl sound file -> Sample (returns false if unreadable)
    static bool parseEbl(const std::vector<uint8_t>& d, Sample& s, std::string* nameOut)
    {
        std::vector<TocEntry> toc;
        if (!readToc(d, toc)) return false;
        for (const auto& e : toc)
        {
            if (std::strcmp(e.tag, "E5S1")) continue;
            if (nameOut) *nameOut = e.name;
            const size_t o = e.off;
            if (o + 78 + 56 > d.size()) return false;
            uint32_t P[14];
            for (int i = 0; i < 14; ++i) P[i] = le32(&d[o + 78 + (size_t)i * 4]);
            const bool stereo = (P[11] & 0x20000u) && P[2] != P[1];
            const size_t maxFrames = (d.size() - o - std::max(P[1], P[2])) / 2;
            const int n = (int)std::min<size_t>((P[3] - P[1]) / 2 + 1, maxFrames);
            if (n <= 0) return false;
            s.ch = stereo ? 2 : 1; s.frames = n; s.rate = (float)std::max<uint32_t>(3000, P[9]);
            s.data.resize((size_t)n * (size_t)s.ch);
            for (int c = 0; c < s.ch; ++c)
            {
                const uint8_t* src = &d[o + (c ? P[2] : P[1])];
                for (int i = 0; i < n; ++i) s.data[(size_t)i * (size_t)s.ch + (size_t)c] = (int16_t)(src[i * 2] | (src[i * 2 + 1] << 8));
            }
            if (P[7] > P[5]) { s.loopStart = (int)((P[5] - P[1]) / 2); s.loopEnd = std::min(n - 1, (int)((P[7] - P[1]) / 2)); }
            return true;
        }
        return false;
    }

    // A bank is a folder holding one .exb file and its sounds (.ebl files, normally in a SamplePool folder).
    // Looked for, in order: the plugin's own Content/ folder, then "Hybrid Phatt Sets" at the top of every drive.
    static std::string findExb(const std::string& dir)
    {
        namespace fs = std::filesystem;
        try { for (const auto& f : fs::directory_iterator(dir)) { std::string n = f.path().filename().string(), l = n;
            for (auto& c : l) c = (char)std::tolower((unsigned char)c);
            if (l.size() > 4 && l.substr(l.size() - 4) == ".exb" && f.is_regular_file()) return f.path().string(); } }
        catch (...) {}
        return "";
    }
    static void banksIn(const std::string& dir, std::vector<std::pair<std::string, std::string>>& out)   // (folder, exb)
    {
        namespace fs = std::filesystem;
        const std::string here = findExb(dir);
        if (!here.empty()) { out.push_back({dir, here}); return; }
        try { for (const auto& f : fs::directory_iterator(dir)) if (f.is_directory()) {
            const std::string e = findExb(f.path().string());
            if (!e.empty()) out.push_back({f.path().string(), e}); } }
        catch (...) {}
    }
    std::vector<std::pair<std::string, std::string>> findBanks()
    {
        namespace fs = std::filesystem;
        std::vector<std::pair<std::string, std::string>> out;
        banksIn(mpc::contentFolder(), out);
        std::vector<std::string> roots = {"/nvme"};
        try { for (const auto& f : fs::directory_iterator("/media")) if (f.is_directory()) roots.push_back(f.path().string()); } catch (...) {}
        // the drive that holds "VST2 Plugins" (works on any system)
        std::string up = mpc::pluginFolder();
        for (int i = 0; i < 4 && !up.empty(); ++i) { const size_t s = up.find_last_of('/'); if (s == std::string::npos) break; up = up.substr(0, s); roots.push_back(up); }
        for (const auto& r : roots) banksIn(r + "/Hybrid Phatt Sets", out);
        return out;
    }

    void loadBank()
    {
        namespace fs = std::filesystem;
        const auto banks = findBanks();
        if (banks.empty()) { mpc::log("HybridPhatt: no sound bank found"); state_.store(2); return; }
        const std::string root = banks[0].first;
        bankName_ = fs::path(banks[0].second).stem().string();
        std::vector<uint8_t> exb;
        if (!mpc::readFile(banks[0].second, exb)) { state_.store(2); return; }
        std::vector<TocEntry> toc;
        if (!readToc(exb, toc)) { state_.store(2); return; }

        // sound files by number (SL####), and sound names from the bank's list
        std::map<int, std::string> files, bankNames;
        for (const auto& e : toc) if (!std::strcmp(e.tag, "E5SL")) bankNames[e.idx] = e.name;
        try
        {
            for (const auto& f : fs::recursive_directory_iterator(root))
            {
                if (!f.is_regular_file()) continue;
                std::string fn = f.path().filename().string(), low = fn;
                for (auto& c : low) c = (char)std::tolower((unsigned char)c);
                if (low.size() < 5 || low.substr(low.size() - 4) != ".ebl") continue;
                const size_t p = low.rfind("sl");
                if (p == std::string::npos) continue;
                files[std::atoi(fn.c_str() + p + 2)] = f.path().string();
            }
        }
        catch (...) { state_.store(2); return; }
        if (files.empty()) { state_.store(2); return; }

        // load every sound; files numbered outside the bank's list are matched by their sound name
        std::map<std::string, int> needByName;
        for (const auto& kv : bankNames) if (!files.count(kv.first)) needByName[kv.second] = kv.first;
        std::map<int, int> slot;                       // bank sound number -> samples_ index
        samples_.reserve(files.size());
        std::vector<uint8_t> buf;
        for (const auto& kv : files)
        {
            if (quit_.load()) return;
            if (!mpc::readFile(kv.second, buf)) continue;
            Sample s; std::string nm;
            if (!parseEbl(buf, s, &nm)) continue;
            int num = kv.first;
            if (!bankNames.count(num))
            {
                auto it = needByName.find(nm);
                if (it == needByName.end()) continue;
                num = it->second; needByName.erase(it);
            }
            slot[num] = (int)samples_.size();
            samples_.push_back(std::move(s));
        }

        // presets
        presets_.assign(512, Preset());
        for (const auto& e : toc)
        {
            if (std::strcmp(e.tag, "E5P1") || e.idx >= 512 || e.off + 10 > exb.size()) continue;
            Preset& pr = presets_[(size_t)e.idx];
            const size_t colon = e.name.find(':');
            pr.title = colon == std::string::npos ? e.name : e.name.substr(colon + 1);
            pr.cat = catName(colon == std::string::npos ? std::string("misc") : e.name.substr(0, colon));
            std::vector<Chunk> top;
            // use the preset chunk's own size: the table of contents lists it 2 bytes short
            const size_t own = (size_t)be32(&exb[e.off + 4]);
            chunks(exb, e.off + 10, std::min<size_t>(exb.size(), (size_t)e.off + 8 + std::max<size_t>(own, e.size)), top);
            const Chunk* vl = find(top, "LIST:E5VL");
            if (!vl) continue;
            for (const auto& v : vl->kids)
            {
                if (v.tag != "E5V1") continue;
                VoiceDef vd;
                if (const Chunk* tw = find(v.kids, "LIST:TWL "))
                {
                    if (tw->kids.size() > 0 && tw->kids[0].n >= 8) { vd.klo = exb[tw->kids[0].o + 4]; vd.khi = exb[tw->kids[0].o + 7]; }
                    if (tw->kids.size() > 1 && tw->kids[1].n >= 8) { vd.vlo = exb[tw->kids[1].o + 4]; vd.vhi = exb[tw->kids[1].o + 7]; }
                }
                if (const Chunk* am = find(v.kids, "E5Am"); am && am->n >= 9)
                {
                    vd.gain = dbToGain(clamp(bef(&exb[am->o + 4]), -96.0f, 24.0f));
                    vd.pan = clamp((float)(int8_t)exb[am->o + 8] / 64.0f, -1.0f, 1.0f);
                }
                if (const Chunk* oc = find(v.kids, "E5Oc"); oc && oc->n >= 20) vd.fine = clamp(bef(&exb[oc->o + 16]), -100.0f, 100.0f);
                if (const Chunk* fl = find(v.kids, "E5Fl"); fl && fl->n >= 13)
                {
                    const float cut = bef(&exb[fl->o + 5]);
                    if (cut > 0.0f) { vd.filterHz = 57.0f * std::pow(350.0f, clamp(cut, 0.0f, 1.0f)); vd.filterQ = clamp(bef(&exb[fl->o + 9]), 0.0f, 1.0f); }
                }
                if (const Chunk* ev = find(v.kids, "LIST:EvL "); ev && !ev->kids.empty() && ev->kids[0].n >= 63)
                {
                    static const int offs[6] = {10, 19, 28, 37, 46, 55};
                    for (int s = 0; s < 6; ++s)
                    {
                        vd.env[s][0] = clamp(bef(&exb[ev->kids[0].o + (size_t)offs[s]]), 0.0f, 60.0f);
                        vd.env[s][1] = clamp(bef(&exb[ev->kids[0].o + (size_t)offs[s] + 4]), 0.0f, 100.0f) * 0.01f;
                    }
                }
                vd.zoneFirst = (int)pr.zones.size();
                if (const Chunk* zl = find(v.kids, "LIST:E5ZL"))
                {
                    for (size_t i = 0; i < zl->kids.size(); ++i)
                    {
                        const Chunk& z = zl->kids[i];
                        if (z.tag != "Zhdr" || z.n < 15) continue;
                        Zone zn;
                        auto it = slot.find(be16(&exb[z.o + 4]));
                        if (it == slot.end()) continue;
                        zn.sample = it->second;
                        zn.fine = clamp(bef(&exb[z.o + 6]), -100.0f, 100.0f);
                        zn.root = exb[z.o + 10];
                        zn.gain = dbToGain(clamp(bef(&exb[z.o + 11]), -96.0f, 24.0f));
                        if (i + 1 < zl->kids.size() && zl->kids[i + 1].tag == "LIST:TWL ")
                        {
                            const auto& k = zl->kids[i + 1].kids;
                            if (k.size() > 0 && k[0].n >= 8) { zn.klo = exb[k[0].o + 4]; zn.khi = exb[k[0].o + 7]; }
                            if (k.size() > 1 && k[1].n >= 8) { zn.vlo = exb[k[1].o + 4]; zn.vhi = exb[k[1].o + 7]; }
                        }
                        pr.zones.push_back(zn);
                    }
                }
                vd.zoneCount = (int)pr.zones.size() - vd.zoneFirst;
                pr.voices.push_back(vd);
            }
        }
        mpc::log("HybridPhatt: loaded %d sounds and %d presets", (int)samples_.size(), (int)presets_.size());
        state_.store(1, std::memory_order_release);
    }

    // ======================================================================= playback
    struct Part
    {
        bool active = false;
        int key = -1, layer = 0, age = 0;
        const Sample* smp = nullptr;
        double pos = 0.0, inc = 1.0;
        float gL = 0.0f, gR = 0.0f;
        // 6-stage envelope
        const float (*env)[2] = nullptr;
        int stage = 0, left = 0;
        float level = 0.0f, step = 0.0f, sustain = 1.0f;
        bool released = false, fallbackSaw = false;
        float sawPhase = 0.0f, sawInc = 0.0f;
        float presetHz = 0.0f, presetQ = 0.0f;
        SVF filter;
        bool useFilter = false;
    };
    static constexpr int kParts = 48;
    Part voices_[kParts];

    struct Block
    {
        float vol, cutoff, reso, drive, aMul, dMul, rMul, susOff, keyTrack, tune;
        float lvl[4], panOff[4], tuneL[4];
        bool on[4];
        int bank, preset, mode;
    } b_{};

    void readBlockSettings()
    {
        b_.vol = dbToGain(get(kVolume));
        b_.cutoff = get(kCutoff); b_.reso = get(kReso) * 0.01f; b_.drive = get(kDrive) * 0.01f;
        b_.aMul = std::pow(2.0f, get(kAttack) * 0.04f); b_.dMul = std::pow(2.0f, get(kDecay) * 0.04f);
        b_.rMul = std::pow(2.0f, get(kRelease) * 0.04f); b_.susOff = get(kSustain) * 0.01f;
        b_.keyTrack = get(kKeyTrack) * 0.01f; b_.tune = (float)getInt(kTune);
        for (int l = 0; l < 4; ++l)
        {
            b_.on[l] = getBool(kOn1 + l); b_.lvl[l] = dbToGain(get(kLvl1 + l));
            b_.panOff[l] = get(kPan1 + l) * 0.01f; b_.tuneL[l] = (float)getInt(kCoarse1 + l) + get(kFine1 + l) * 0.01f;
        }
        b_.bank = getInt(kBank); b_.preset = getInt(kPreset);
        static const int modes[9] = {0, 0, 1, 2, 4, 4, 3, 4, 4};
        b_.mode = modes[clamp(getInt(kFType), 0, 8)];
        // filters of sounding parts follow the Cutoff / Resonance knobs
        for (auto& p : voices_) if (p.active) setPartFilter(p);
    }

    void setPartFilter(Part& p)
    {
        float hz = b_.cutoff * std::pow(2.0f, b_.keyTrack * ((float)p.key - 60.0f) / 12.0f);
        float q = b_.reso;
        if (p.presetHz > 0.0f) { hz = std::min(hz, p.presetHz); q = std::max(q, p.presetQ * 0.9f); }
        p.useFilter = hz < 18000.0f || b_.mode != 0;
        if (p.useFilter) p.filter.set(clamp(hz, 20.0f, 0.45f * sr_), clamp(q, 0.0f, 0.98f));
    }

    void startStage(Part& p, int s)
    {
        while (s < 6)
        {
            float t = p.env[s][0];
            t *= s < 2 ? b_.aMul : (s < 4 ? b_.dMul : b_.rMul);
            float target = p.env[s][1];
            if (s == 3) target = clamp(target + p.sustain, 0.0f, 1.0f);
            const int n = (int)(t * sr_);
            if (n > 0) { p.stage = s; p.left = n; p.step = (target - p.level) / (float)n; return; }
            p.level = target;
            if (s == 3 && !p.released) { p.stage = 3; p.left = -1; p.step = 0.0f; return; }   // sustain
            ++s;
        }
        p.stage = 6; p.left = 0; p.step = 0.0f;
    }

    void handleMidi(const mpc::MidiEvent& ev)
    {
        if (ev.isNoteOn()) { held_[ev.note() & 127]++; lastNote_.store(ev.note()); lastVel_.store(ev.velocity()); noteDirty_ = true; noteOn(ev.note(), ev.velocity()); }
        else if (ev.isNoteOff()) { if (held_[ev.note() & 127] > 0) held_[ev.note() & 127]--; noteOff(ev.note()); }
        else if (ev.isAllNotesOff()) { for (auto& p : voices_) if (p.active) release(p); for (auto& h : held_) h = 0; }
        else if (ev.isPitchBend()) bend_ = ev.pitchBend() * 2.0f;
    }

    Part* freePart()
    {
        Part* best = nullptr;
        for (auto& p : voices_) { if (!p.active) return &p; if (!best || p.age > best->age) best = &p; }
        return best;                                    // steal the oldest
    }

    void noteOn(int key, int vel)
    {
        for (auto& p : voices_) if (p.active) ++p.age;
        const float vgain = (0.25f + 0.75f * (float)vel / 127.0f) * 0.3f;
        const Preset* pr = currentPreset(b_.bank, b_.preset);
        if (!pr)
        {
            Part* p = freePart();
            *p = Part(); p->filter.setSampleRate(sr_);
            p->active = true; p->key = key; p->fallbackSaw = true; p->env = kFallbackEnv; p->sustain = 0.0f;
            p->sawInc = 440.0f * std::pow(2.0f, ((float)key - 69.0f + b_.tune) / 12.0f) / sr_;
            p->gL = p->gR = vgain * 0.3f;
            setPartFilter(*p); startStage(*p, 0);
            return;
        }
        for (size_t k = 0; k < pr->voices.size(); ++k)
        {
            const VoiceDef& vd = pr->voices[k];
            const int L = (int)(k % 4);
            if (!b_.on[L] || key < vd.klo || key > vd.khi || vel < vd.vlo || vel > vd.vhi) continue;
            for (int z = vd.zoneFirst; z < vd.zoneFirst + vd.zoneCount; ++z)
            {
                const Zone& zn = pr->zones[(size_t)z];
                if (key < zn.klo || key > zn.khi || vel < zn.vlo || vel > zn.vhi || zn.sample < 0) continue;
                Part* p = freePart();
                *p = Part(); p->filter.setSampleRate(sr_);
                p->active = true; p->key = key; p->layer = L;
                p->smp = &samples_[(size_t)zn.sample];
                const float semis = (float)(key - zn.root) + (vd.fine + zn.fine) * 0.01f + b_.tune + b_.tuneL[L] + bend_;
                p->inc = (double)p->smp->rate / (double)sr_ * std::pow(2.0, (double)semis / 12.0);
                const float g = vgain * vd.gain * zn.gain;
                const float pan = clamp(vd.pan + b_.panOff[L], -1.0f, 1.0f);
                p->gL = g * std::sqrt(0.5f * (1.0f - pan)) * 1.4142f;
                p->gR = g * std::sqrt(0.5f * (1.0f + pan)) * 1.4142f;
                p->env = vd.env; p->sustain = b_.susOff;
                p->presetHz = vd.filterHz; p->presetQ = vd.filterQ;
                setPartFilter(*p); startStage(*p, 0);
            }
        }
    }

    void release(Part& p) { if (!p.released) { p.released = true; startStage(p, 4); } }
    void noteOff(int key) { for (auto& p : voices_) if (p.active && p.key == key) release(p); }

    void render(mpc::ProcessContext& ctx, int from, int to)
    {
        float* L = ctx.outputs[0];
        float* R = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        for (auto& p : voices_)
        {
            if (!p.active) continue;
            const float lg = b_.lvl[p.layer];
            for (int i = from; i < to; ++i)
            {
                // envelope
                if (p.left > 0) { p.level += p.step; if (--p.left == 0) startStage(p, p.stage + 1); }
                if (p.stage >= 6 || (p.stage >= 4 && p.left == 0 && p.level <= 0.0005f)) { p.active = false; break; }
                float sl, sr;
                if (p.fallbackSaw)
                {
                    sl = sr = 2.0f * p.sawPhase - 1.0f;
                    p.sawPhase += p.sawInc; if (p.sawPhase >= 1.0f) p.sawPhase -= 1.0f;
                }
                else
                {
                    const Sample& s = *p.smp;
                    const int i0 = (int)p.pos;
                    if (i0 >= s.frames) { p.active = false; break; }
                    const float fr = (float)(p.pos - i0);
                    int i1 = i0 + 1;
                    if (s.loopEnd > s.loopStart && i1 > s.loopEnd) i1 = s.loopStart;
                    if (i1 >= s.frames) i1 = i0;
                    if (s.ch == 2)
                    {
                        const int16_t* a = &s.data[(size_t)i0 * 2]; const int16_t* b = &s.data[(size_t)i1 * 2];
                        sl = ((float)a[0] + ((float)b[0] - (float)a[0]) * fr) * (1.0f / 32768.0f);
                        sr = ((float)a[1] + ((float)b[1] - (float)a[1]) * fr) * (1.0f / 32768.0f);
                    }
                    else
                    {
                        const float a = s.data[(size_t)i0], b = s.data[(size_t)i1];
                        sl = sr = (a + (b - a) * fr) * (1.0f / 32768.0f);
                    }
                    p.pos += p.inc;
                    if (s.loopEnd > s.loopStart && p.pos > (double)s.loopEnd + 1.0) p.pos -= (double)(s.loopEnd + 1 - s.loopStart);
                }
                if (p.useFilter)
                {
                    const float m = 0.5f * (sl + sr), y = p.filter.process(m, b_.mode);
                    const float k = std::fabs(m) > 1e-6f ? y / m : 0.0f;   // keep the stereo image: scale both sides
                    sl *= clamp(k, -4.0f, 4.0f); sr *= clamp(k, -4.0f, 4.0f);
                }
                const float e = p.level * lg;
                L[i] += sl * p.gL * e;
                if (R) R[i] += sr * p.gR * e;
            }
        }
        // drive and master volume
        const float drv = 1.0f + b_.drive * 8.0f;
        for (int i = from; i < to; ++i)
        {
            volSmooth_ += (b_.vol - volSmooth_) * 0.002f;
            float l = L[i] * drv, r = R ? R[i] * drv : 0.0f;
            if (b_.drive > 0.0f) { l = l / (1.0f + std::fabs(l)); r = r / (1.0f + std::fabs(r)); }
            L[i] = l * volSmooth_;
            if (R) R[i] = r * volSmooth_;
        }
    }

    // ======================================================================= helpers
    std::deque<std::string> names_;
    const char* keep(std::string s) { names_.push_back(std::move(s)); return names_.back().c_str(); }
    const char* id(const char* base, int n) { return keep(std::string(base) + std::to_string(n)); }
    const char* name(const char* a, int n, const char* b) { return keep(std::string(a) + std::to_string(n) + b); }

    static constexpr float kFallbackEnv[6][2] = {{0.003f, 1.0f}, {0.0f, 1.0f}, {0.3f, 0.7f}, {0.0f, 0.7f}, {0.2f, 0.0f}, {0.0f, 0.0f}};

    std::vector<Sample> samples_;
    std::vector<Preset> presets_;
    std::atomic<int> state_{0};      // 0 loading, 1 ready, 2 bank missing
    std::string bankName_;           // written by the loader before state_ becomes 1
    int shownState_ = -1;
    std::atomic<bool> quit_{false};
    std::thread loader_;
    float sr_ = 44100.0f, volSmooth_ = 1.0f, bend_ = 0.0f;
    bool stepping_ = false, prevDown_ = false, nextDown_ = false;
    static constexpr int kFirstKey = 36;     // C1
    std::atomic<int> tapPress_[61] = {}, tapRelease_[61] = {};   // counts of screen presses / releases
    int pressSeen_[61] = {}, releaseSeen_[61] = {}, tapLeft_[61] = {};
    bool releaseWait_[61] = {};
    bool tapHeld_[61] = {}, keyLit_[61] = {}, noteDirty_ = false, selfSet_ = false;
    int held_[128] = {};
    std::atomic<int> lastNote_{-1}, lastVel_{0};
    std::atomic<bool> notifyPending_{false};
};

MPC_PLUGIN_ENTRY(HybridPhatt)
