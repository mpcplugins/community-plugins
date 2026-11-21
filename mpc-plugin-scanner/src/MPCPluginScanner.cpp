// MPC Plugin Scanner - by The Disk King. Copyright (c) 2026 The Disk King.
//
// Put it on a Plugin track. It checks every plugin in every "VST2 Plugins" folder on every drive of the MPC
// for things a music plugin should not contain (see scan.h) and lists them with a green / yellow / red light.
// Tap a plugin to see why. SCAN AGAIN checks again. It never changes, moves or runs any file, and sends nothing
// anywhere. It makes no sound.
//
// Parameter order is permanent once released. The skin finds parameters by index (see make_skin.py).

#include "mpc_plugin.h"
#include "scan.h"

#include <atomic>
#include <chrono>
#include <cmath>
#include <ctime>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr int kRows = 6;
constexpr int kLines = 10;              // reason lines on the details side
constexpr size_t kMax = 31;             // the MPC shows at most 31 characters of a value text
enum P
{
    kVolume = 0, kScan, kPrev, kNext,
    kRow1,                               // kRows buttons
    kSummary = kRow1 + kRows, kStatus, kPage,
    kName1,                              // kRows names
    kInfo1 = kName1 + kRows,             // kRows short results
    kLight1 = kInfo1 + kRows,            // kRows lights: 0 none, 1 green, 2 yellow, 3 red
    kDTitle = kLight1 + kRows, kDVerdict, kDLight, kDWhere,
    kDLine1,                             // kLines reason lines
    kBadge1 = kDLine1 + kLines,          // added in 1.1: kRows "verified creator" badges (0 none, 1 shown)
    kDBadge = kBadge1 + kRows,           // added in 1.1: badge on the details side
    kNumParams
};
std::string fit(std::string s) { if (s.size() > kMax) { s.resize(kMax - 1); s += "."; } return s; }
std::string pluginName(const std::string& folder)
{
    size_t p = folder.find(" - VST - ");
    return p == std::string::npos ? folder : folder.substr(p + 9);
}
}

class MPCPluginScanner : public mpc::Plugin
{
public:
    MPCPluginScanner() : mpc::Plugin(makeInfo())
    {
        addParam(mpc::floatParam("volume", "Volume", -60.0f, 0.0f, -60.0f, "dB", 0));   // harmless parameter 0
        addParam(mpc::boolParam("scan", "Scan Again", false));
        addParam(mpc::boolParam("prev", "Prev", false));
        addParam(mpc::boolParam("next", "Next", false));
        for (int r = 1; r <= kRows; ++r) { std::string id = "row" + std::to_string(r), n = "Row " + std::to_string(r); addParam(mpc::boolParam(id.c_str(), n.c_str(), false)); }
        addText("Summary"); addText("Status"); addText("Page");
        for (const char* base : {"Name ", "Info "}) for (int r = 1; r <= kRows; ++r) addText((std::string(base) + std::to_string(r)).c_str());
        for (int r = 1; r <= kRows; ++r) { std::string id = "light" + std::to_string(r), n = "Light " + std::to_string(r); auto p = mpc::intParam(id.c_str(), n.c_str(), 0, 4, 0); p.automatable = false; addParam(p); }
        addText("D Title"); addText("D Verdict");
        { auto p = mpc::intParam("dlight", "D Light", 0, 4, 0); p.automatable = false; addParam(p); }
        addText("D Where");
        for (int k = 1; k <= kLines; ++k) addText(("D Line " + std::to_string(k)).c_str());
        for (int r = 1; r <= kRows; ++r) { std::string id = "badge" + std::to_string(r), n = "Badge " + std::to_string(r); auto p = mpc::intParam(id.c_str(), n.c_str(), 0, 1, 0); p.automatable = false; addParam(p); }
        { auto p = mpc::intParam("dbadge", "D Badge", 0, 1, 0); p.automatable = false; addParam(p); }
        text_.assign(kNumParams, std::string());
        text_[kSummary] = "MPC PLUGIN SCANNER";
        text_[kStatus] = "Starting...";
    }

    ~MPCPluginScanner() override
    {
        stopping_ = true;
        if (worker_.joinable()) worker_.join();
    }

    void prepare(double, int) override
    {
        if (!worker_.joinable()) worker_ = std::thread([this] { loop(); });
    }

    void process(mpc::ProcessContext& ctx) override
    {
        (void)ctx;
        playing_.store(true, std::memory_order_relaxed);   // makes no sound
    }

    void parameterChanged(int index, float plain) override
    {
        if (plain < 0.5f) return;
        if (index == kScan) want_.fetch_or(1);
        else if (index == kPrev) want_.fetch_or(2);
        else if (index == kNext) want_.fetch_or(4);
        else if (index >= kRow1 && index < kRow1 + kRows) want_.fetch_or(8u << (index - kRow1));
    }

    bool formatValue(int index, float, std::string& out) override
    {
        if (index < kSummary || (index >= kLight1 && index < kLight1 + kRows) || index == kDLight || index >= kBadge1) return false;
        std::lock_guard<std::mutex> g(mu_);
        out = text_[(size_t)index];
        return true;
    }

private:
    static mpc::PluginInfo makeInfo()
    {
        mpc::PluginInfo i;
        i.name = "MPC Plugin Scanner";
        i.vendor = "The Disk King";
        i.uniqueId = MPC_FOURCC('T', 'D', 'K', 'S');   // must match plugin.json "uid"
        i.version = 1200;
        i.isInstrument = true;
        i.numInputs = 0;
        i.numOutputs = 2;
        return i;
    }
    void addText(const char* name)
    {
        std::string id = name;
        id.erase(std::remove(id.begin(), id.end(), ' '), id.end());
        for (char& c : id) c = (char)std::tolower((unsigned char)c);
        auto p = mpc::floatParam(id.c_str(), name, 0.0f, 1.0f, 0.0f, "", 0);
        p.automatable = false;
        addParam(p);
    }

    // ---------------------------------------------------------------- our own thread
    void loop()
    {
        // Wait until we really run on a track (the MPC also loads plugins briefly while it scans them).
        int ticks = 0;
        while (!stopping_)
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(250));
            if (playing_.load() && ++ticks >= 6) break;
        }
        bool first = true;
        while (!stopping_)
        {
            unsigned w = want_.exchange(0);
            if (first || (w & 1)) { first = false; runScan(); }
            if (w & 2) { if (page_ > 0) --page_; refresh(); }
            if (w & 4) { if ((page_ + 1) * kRows < (int)reports_.size()) ++page_; refresh(); }
            for (int r = 0; r < kRows; ++r)
                if (w & (8u << r)) { const int i = page_ * kRows + r; if (i < (int)reports_.size()) { selected_ = i; refresh(); } }
            if (w & 0xE) releaseButtons();
            if (w & 1) release(kScan);
            std::this_thread::sleep_for(std::chrono::milliseconds(60));
        }
    }

    // 1 green, 2 yellow, 3 red, 4 blue (verified creator: our own official tools)
    static int lightOf(const scan::Report& rp) { return rp.verified ? 4 : rp.level >= scan::kRisky ? 3 : rp.level == scan::kCheck ? 2 : 1; }

    void release(int i) { setNormalised(i, 0.0f); notifyHostParameterChanged(i); }
    void releaseButtons() { release(kPrev); release(kNext); for (int r = 0; r < kRows; ++r) release(kRow1 + r); }

    void runScan()
    {
        publish({{kStatus, "Scanning your plugins..."}}, {});
        auto t0 = std::chrono::steady_clock::now();
        std::vector<scan::Report> rep = scan::scanAll(mpc::pluginFolder());   // never lists itself; marks our own tools verified
        const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        reports_ = std::move(rep);
        page_ = 0; selected_ = reports_.empty() ? -1 : 0;
        int n[4] = {0, 0, 0, 0};
        for (auto& r : reports_) n[r.verified ? 0 : std::min(3, std::max(0, r.level))]++;
        char sum[64], st[64];
        std::snprintf(sum, sizeof sum, "OK %d  |  CHECK %d  |  RISKY %d", n[0] + n[1], n[2], n[3]);
        std::time_t now = std::time(nullptr);
        char tm[16] = "";
        std::strftime(tm, sizeof tm, "%H:%M", std::localtime(&now));
        std::snprintf(st, sizeof st, "%d plugins scanned at %s", (int)reports_.size(), tm); (void)secs;
        summary_ = sum; status_ = reports_.empty() ? "No VST2 Plugins folders found" : st;
        refresh();
    }

    void refresh()
    {
        std::vector<std::pair<int, std::string>> t;
        std::vector<std::pair<int, float>> f;
        t.push_back({kSummary, fit(summary_)});
        t.push_back({kStatus, fit(status_)});
        const int pages = std::max(1, ((int)reports_.size() + kRows - 1) / kRows);
        t.push_back({kPage, "PAGE " + std::to_string(page_ + 1) + " / " + std::to_string(pages)});
        for (int r = 0; r < kRows; ++r)
        {
            const int i = page_ * kRows + r;
            if (i < (int)reports_.size())
            {
                const scan::Report& rp = reports_[(size_t)i];
                std::string info = std::string(scan::levelName(rp.level));
                if (rp.verified) info = "VERIFIED: The Disk King tool";
                else if (rp.level >= scan::kCheck && !rp.findings.empty()) info += ": " + rp.findings[0].text;
                else if (rp.level == scan::kClean) info += ": nothing found";
                else info += ": only normal file use";
                t.push_back({kName1 + r, fit((i == selected_ ? "> " : "") + pluginName(rp.folder))});
                t.push_back({kInfo1 + r, fit(info)});
                f.push_back({kLight1 + r, (float)lightOf(rp)});
                f.push_back({kBadge1 + r, rp.verified ? 1.0f : 0.0f});
            }
            else
            {
                t.push_back({kName1 + r, ""}); t.push_back({kInfo1 + r, ""}); f.push_back({kLight1 + r, 0.0f}); f.push_back({kBadge1 + r, 0.0f});
            }
        }
        // details of the selected plugin
        std::vector<std::string> lines;
        std::string title, verdict, where;
        int light = 0;
        if (selected_ >= 0 && selected_ < (int)reports_.size())
        {
            const scan::Report& rp = reports_[(size_t)selected_];
            title = pluginName(rp.folder);
            where = "by " + rp.folder.substr(0, rp.folder.find(" - VST - ")) + " | " + rp.drive;
            light = lightOf(rp);
            verdict = rp.verified ? "Verified creator: The Disk King"
                    : rp.level >= scan::kRisky ? "RISKY: remove unless trusted" : rp.level == scan::kCheck ? "CHECK: OK if you trust maker" : "CLEAN: no warning signs";
            if (rp.verified) lines.push_back("Official build, files match");
            for (const auto& fd : rp.findings)
            {
                if (lines.size() >= kLines) break;
                lines.push_back(std::string(rp.verified ? "- " : fd.level >= scan::kRisky ? "! " : fd.level == scan::kCheck ? "? " : "- ") + fd.text);
            }
            if (rp.findings.empty()) lines.push_back("No risky parts found.");
            if (lines.size() < kLines) lines.push_back(std::to_string(rp.files) + " files, " + std::to_string(rp.codeFiles) + " code checked");
        }
        t.push_back({kDTitle, fit(title)}); t.push_back({kDVerdict, fit(verdict)}); t.push_back({kDWhere, fit(where)});
        f.push_back({kDLight, (float)light});
        f.push_back({kDBadge, (selected_ >= 0 && selected_ < (int)reports_.size() && reports_[(size_t)selected_].verified) ? 1.0f : 0.0f});
        for (int k = 0; k < kLines; ++k) t.push_back({kDLine1 + k, k < (int)lines.size() ? fit(lines[(size_t)k]) : ""});
        publish(t, f);
    }

    // Only what changed. A text value is nudged so the MPC re-reads it (same trick as MPC Plugins Manager).
    void publish(const std::vector<std::pair<int, std::string>>& texts, const std::vector<std::pair<int, float>>& frames)
    {
        std::vector<int> changed;
        {
            std::lock_guard<std::mutex> g(mu_);
            for (auto& t : texts) if (text_[(size_t)t.first] != t.second) { text_[(size_t)t.first] = t.second; changed.push_back(t.first); }
        }
        for (int i : changed) { setNormalised(i, getNormalised(i) > 0.5f ? 0.1f : 0.9f); notifyHostParameterChanged(i); }
        for (auto& f : frames) if (std::fabs(get(f.first) - f.second) > 0.01f) { set(f.first, f.second); notifyHostParameterChanged(f.first); changed.push_back(f.first); }
        if (!changed.empty()) requestDisplayUpdate();
    }

    std::vector<std::string> text_;
    std::mutex mu_;
    std::vector<scan::Report> reports_;
    std::string summary_ = "MPC PLUGIN SCANNER", status_;
    int page_ = 0, selected_ = -1;
    std::atomic<unsigned> want_{0};
    std::atomic<bool> playing_{false}, stopping_{false};
    std::thread worker_;
};

MPC_PLUGIN_ENTRY(MPCPluginScanner)
