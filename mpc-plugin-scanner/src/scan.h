// scan.h - MPC Plugin Scanner (The Disk King). Copyright (c) 2026 The Disk King.
//
// Looks inside installed MPC plugins for things a music plugin should not contain, WITHOUT running them:
//   * the plugin's code libraries (ELF .so files) are read and the system functions they call are listed
//     (running other programs, taking over the system, using the internet, deleting files ...)
//   * text inside the code is searched for shell commands and system paths (/bin/sh, rm -rf, /etc/shadow ...)
//   * the plugin folder is searched for programs, scripts, kernel modules, hidden files, links that lead
//     outside the folder, and files that would run with special rights (setuid)
// Each plugin gets a level: 0 CLEAN, 1 CLEAN with notes, 2 CHECK (can do something risky; fine if you trust
// the maker), 3 RISKY (contains something a music plugin should never need).
//
// This is a warning-sign scan, not a guarantee: code can hide what it does. It never changes or runs any file.

#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>

#if !defined(_WIN32)
#include <sys/stat.h>
#endif

namespace scan {

namespace fs = std::filesystem;

enum Level { kClean = 0, kNote = 1, kCheck = 2, kRisky = 3 };

struct Finding
{
    int level = kNote;
    std::string text;                    // plain words, short (fits the MPC screen)
    std::string detail;                  // which file / which names
};

struct Report
{
    std::string folder;                  // "Maker - VST - Name"
    std::string drive;                   // drive label
    std::string path;
    int level = kClean;
    int codeFiles = 0, files = 0;
    std::vector<Finding> findings;
    void add(int lv, const std::string& t, const std::string& d)
    {
        for (auto& f : findings) if (f.text == t) { if (f.detail.find(d) == std::string::npos && f.detail.size() < 200) f.detail += ", " + d; f.level = std::max(f.level, lv); level = std::max(level, lv); return; }
        findings.push_back({lv, t, d});
        level = std::max(level, lv);
    }
};

// ------------------------------------------------------------------ rules
struct Rule { const char* name; int level; const char* text; };

inline const std::vector<Rule>& importRules()
{
    static const std::vector<Rule> r = {
        // running other programs
        {"system", kRisky, "Can run other programs"}, {"popen", kRisky, "Can run other programs"},
        {"execl", kRisky, "Can run other programs"}, {"execle", kRisky, "Can run other programs"},
        {"execlp", kRisky, "Can run other programs"}, {"execv", kRisky, "Can run other programs"},
        {"execve", kRisky, "Can run other programs"}, {"execvp", kRisky, "Can run other programs"},
        {"execvpe", kRisky, "Can run other programs"}, {"fexecve", kRisky, "Can run other programs"},
        {"posix_spawn", kRisky, "Can run other programs"}, {"posix_spawnp", kRisky, "Can run other programs"},
        // taking over the system
        {"ptrace", kRisky, "Can spy on programs"}, {"process_vm_readv", kRisky, "Can spy on programs"},
        {"process_vm_writev", kRisky, "Can spy on programs"},
        {"setuid", kRisky, "Can change its rights"}, {"setgid", kRisky, "Can change its rights"},
        {"seteuid", kRisky, "Can change its rights"}, {"setegid", kRisky, "Can change its rights"},
        {"setreuid", kRisky, "Can change its rights"}, {"setregid", kRisky, "Can change its rights"},
        {"setresuid", kRisky, "Can change its rights"}, {"setresgid", kRisky, "Can change its rights"},
        {"chroot", kRisky, "Can change system setup"}, {"pivot_root", kRisky, "Can change system setup"},
        {"mount", kRisky, "Can change system setup"}, {"umount", kRisky, "Can change system setup"},
        {"umount2", kRisky, "Can change system setup"}, {"sethostname", kRisky, "Can change system setup"},
        {"swapon", kRisky, "Can change system setup"}, {"swapoff", kRisky, "Can change system setup"},
        {"reboot", kRisky, "Can restart the MPC"},
        {"init_module", kRisky, "Can load system drivers"}, {"finit_module", kRisky, "Can load system drivers"},
        {"delete_module", kRisky, "Can load system drivers"}, {"kexec_load", kRisky, "Can load system drivers"},
        // the internet / network
        {"socket", kCheck, "Uses the internet"}, {"connect", kCheck, "Uses the internet"},
        {"bind", kCheck, "Uses the internet"}, {"listen", kCheck, "Uses the internet"},
        {"accept", kCheck, "Uses the internet"}, {"accept4", kCheck, "Uses the internet"},
        {"getaddrinfo", kCheck, "Uses the internet"}, {"gethostbyname", kCheck, "Uses the internet"},
        {"sendto", kCheck, "Uses the internet"}, {"recvfrom", kCheck, "Uses the internet"},
        // background processes
        {"fork", kCheck, "Starts background tasks"}, {"vfork", kCheck, "Starts background tasks"},
        {"clone", kCheck, "Starts background tasks"}, {"daemon", kCheck, "Starts background tasks"},
        {"kill", kCheck, "Can stop other programs"},
        // files (normal for saving presets, so only a note)
        {"unlink", kNote, "Can delete files"}, {"unlinkat", kNote, "Can delete files"}, {"remove", kNote, "Can delete files"},
        {"rmdir", kNote, "Can delete files"}, {"rename", kNote, "Can move or rename files"},
        {"renameat", kNote, "Can move or rename files"}, {"renameat2", kNote, "Can move or rename files"},
        {"chmod", kNote, "Changes file permissions"}, {"fchmod", kNote, "Changes file permissions"},
        {"fchmodat", kNote, "Changes file permissions"}, {"chown", kNote, "Changes file permissions"},
        {"lchown", kNote, "Changes file permissions"}, {"fchown", kNote, "Changes file permissions"},
        {"symlink", kNote, "Can make file links"}, {"symlinkat", kNote, "Can make file links"},
        {"dlopen", kNote, "Loads extra code"},
    };
    return r;
}

inline const std::vector<Rule>& stringRules()
{
    static const std::vector<Rule> r = {
        {"/bin/sh", kRisky, "Contains shell commands"}, {"/bin/bash", kRisky, "Contains shell commands"},
        {"/bin/busybox", kRisky, "Contains shell commands"}, {"sh -c ", kRisky, "Contains shell commands"},
        {"rm -rf", kRisky, "Can wipe files (rm -rf)"}, {"rm -r /", kRisky, "Can wipe files (rm -rf)"},
        {"mkfs.", kRisky, "Can erase disks"}, {"dd if=", kRisky, "Can erase disks"},
        {"/etc/shadow", kRisky, "Reads system passwords"}, {"/etc/passwd", kCheck, "Reads system user list"},
        {"authorized_keys", kRisky, "Can add remote logins"}, {"dropbear", kRisky, "Can add remote logins"},
        {"telnetd", kRisky, "Can add remote logins"},
        {"crontab", kRisky, "Can start itself on boot"}, {"/etc/init.d", kRisky, "Can start itself on boot"},
        {"systemctl ", kRisky, "Can start itself on boot"}, {"/etc/systemd", kRisky, "Can start itself on boot"},
        {"/proc/self/mem", kRisky, "Can change running code"}, {"LD_PRELOAD", kCheck, "Can inject code"},
        {"wget ", kRisky, "Has download commands"}, {"curl -", kRisky, "Has download commands"},
        {"chmod 777", kRisky, "Opens file permissions"}, {"chmod +s", kRisky, "Gives special file rights"},
        {"nc -l", kRisky, "Opens a back door"}, {"/dev/tcp/", kRisky, "Opens a back door"},
        {"stratum+tcp", kRisky, "Contains a crypto miner"}, {"xmrig", kRisky, "Contains a crypto miner"},
        {"/media/az01", kCheck, "Touches MPC system areas"}, {"/usr/share/Akai", kCheck, "Touches MPC system areas"},
    };
    return r;
}

// libraries a normal plugin links to; anything else is listed as a note (CHECK for a few known ones)
inline int libraryLevel(const std::string& lib, std::string& why)
{
    static const char* normal[] = {"libc.so", "libm.so", "libstdc++.so", "libgcc_s.so", "libpthread.so", "libdl.so", "librt.so",
                                   "ld-linux", "libasound.so", "libatomic.so"};
    for (const char* n : normal) if (lib.rfind(n, 0) == 0) return kClean;
    if (lib.find("curl") != std::string::npos || lib.find("ssl") != std::string::npos || lib.find("crypto") != std::string::npos)
    { why = "Uses internet libraries"; return kCheck; }
    why = "Needs extra libraries";
    return kNote;
}

// ------------------------------------------------------------------ ELF reading
struct Elf
{
    bool ok = false, is64 = false;
    int machine = 0, type = 0;
    bool hasInterp = false;             // a program (not a library)
    std::vector<std::string> imports, needed;
};

template <typename T> inline bool rd(const std::vector<uint8_t>& d, size_t off, T& out)
{
    if (off + sizeof(T) > d.size() || off + sizeof(T) < off) return false;
    std::memcpy(&out, &d[off], sizeof(T));
    return true;
}

inline Elf readElf(const std::vector<uint8_t>& d)
{
    Elf e;
    if (d.size() < 52 || std::memcmp(d.data(), "\x7f" "ELF", 4) != 0 || d[5] != 1) return e;   // little endian only
    e.is64 = d[4] == 2;
    uint16_t type = 0, mach = 0, phnum = 0, shnum = 0, phentsize = 0, shentsize = 0;
    uint64_t phoff = 0, shoff = 0;
    rd(d, 16, type); rd(d, 18, mach);
    e.type = type; e.machine = mach;
    if (e.is64)
    {
        if (d.size() < 64) return e;
        rd(d, 32, phoff); rd(d, 40, shoff); rd(d, 54, phentsize); rd(d, 56, phnum); rd(d, 58, shentsize); rd(d, 60, shnum);
    }
    else
    {
        uint32_t p32 = 0, s32 = 0;
        rd(d, 28, p32); rd(d, 32, s32); rd(d, 42, phentsize); rd(d, 44, phnum); rd(d, 46, shentsize); rd(d, 48, shnum);
        phoff = p32; shoff = s32;
    }
    for (uint32_t i = 0; i < phnum && i < 256; ++i)
    {
        uint32_t ptype = 0;
        if (rd(d, (size_t)(phoff + (uint64_t)i * phentsize), ptype) && ptype == 3) e.hasInterp = true;   // PT_INTERP
    }
    // sections: find the dynamic symbol table and the dynamic section
    struct Sec { uint32_t type = 0, link = 0; uint64_t off = 0, size = 0, entsize = 0; };
    std::vector<Sec> secs;
    for (uint32_t i = 0; i < shnum && i < 4096; ++i)
    {
        size_t o = (size_t)(shoff + (uint64_t)i * shentsize);
        Sec s;
        if (e.is64)
        {
            if (!rd(d, o + 4, s.type) || !rd(d, o + 24, s.off) || !rd(d, o + 32, s.size) || !rd(d, o + 40, s.link) || !rd(d, o + 56, s.entsize)) break;
        }
        else
        {
            uint32_t off = 0, size = 0, ent = 0;
            if (!rd(d, o + 4, s.type) || !rd(d, o + 16, off) || !rd(d, o + 20, size) || !rd(d, o + 24, s.link) || !rd(d, o + 36, ent)) break;
            s.off = off; s.size = size; s.entsize = ent;
        }
        secs.push_back(s);
    }
    auto str = [&](const Sec& strtab, uint64_t idx) -> std::string {
        uint64_t p = strtab.off + idx;
        if (idx >= strtab.size || p >= d.size()) return "";
        size_t end = (size_t)p;
        while (end < d.size() && end < strtab.off + strtab.size && d[end]) ++end;
        return std::string((const char*)&d[(size_t)p], end - (size_t)p);
    };
    for (const Sec& s : secs)
    {
        if (s.type == 11 && s.link < secs.size())          // SHT_DYNSYM
        {
            const Sec& st = secs[s.link];
            const uint64_t ent = s.entsize ? s.entsize : (e.is64 ? 24 : 16);
            for (uint64_t k = 1; k * ent + ent <= s.size && k < 200000; ++k)
            {
                size_t o = (size_t)(s.off + k * ent);
                uint32_t name = 0; uint16_t shndx = 0;
                if (!rd(d, o, name)) break;
                if (!rd(d, o + (e.is64 ? 6 : 14), shndx)) break;
                if (shndx == 0) { std::string n = str(st, name); size_t at = n.find('@'); if (at != std::string::npos) n = n.substr(0, at); if (!n.empty()) e.imports.push_back(n); }
            }
        }
        if (s.type == 6 && s.link < secs.size())           // SHT_DYNAMIC
        {
            const Sec& st = secs[s.link];
            const uint64_t ent = e.is64 ? 16 : 8;
            for (uint64_t k = 0; (k + 1) * ent <= s.size && k < 4096; ++k)
            {
                size_t o = (size_t)(s.off + k * ent);
                uint64_t tag = 0, val = 0;
                if (e.is64) { if (!rd(d, o, tag) || !rd(d, o + 8, val)) break; }
                else { uint32_t t = 0, v = 0; if (!rd(d, o, t) || !rd(d, o + 4, v)) break; tag = t; val = v; }
                if (tag == 0) break;
                if (tag == 1) e.needed.push_back(str(st, val));   // DT_NEEDED
            }
        }
    }
    std::sort(e.imports.begin(), e.imports.end());
    e.imports.erase(std::unique(e.imports.begin(), e.imports.end()), e.imports.end());
    e.ok = true;
    return e;
}

inline bool readAll(const fs::path& p, std::vector<uint8_t>& out, size_t limit = 64u << 20)
{
    std::ifstream f(p, std::ios::binary);
    if (!f) return false;
    f.seekg(0, std::ios::end);
    std::streamoff n = f.tellg();
    if (n < 0) return false;
    f.seekg(0);
    out.resize((size_t)std::min<std::streamoff>(n, (std::streamoff)limit));
    if (!out.empty()) f.read((char*)out.data(), (std::streamsize)out.size());
    return true;
}

inline bool contains(const std::vector<uint8_t>& d, const char* s)
{
    const size_t n = std::strlen(s);
    if (n == 0 || d.size() < n) return false;
    return std::search(d.begin(), d.end(), s, s + n) != d.end();
}

// ------------------------------------------------------------------ one plugin folder
inline Report scanPlugin(const fs::path& folder, const std::string& driveLabel)
{
    Report r;
    r.folder = folder.filename().string();
    r.drive = driveLabel;
    r.path = folder.string();
    std::error_code ec;
    const fs::path base = fs::weakly_canonical(folder, ec);
    int seen = 0;
    for (auto it = fs::recursive_directory_iterator(folder, fs::directory_options::skip_permission_denied, ec);
         !ec && it != fs::recursive_directory_iterator(); it.increment(ec))
    {
        if (++seen > 20000) { r.add(kCheck, "Too many files to check", ""); break; }
        const fs::path p = it->path();
        const std::string name = p.filename().string();
        std::string low = name;
        for (auto& c : low) c = (char)std::tolower((unsigned char)c);
        std::error_code e2;
        const fs::path relp = fs::relative(p, folder, e2);
        const std::string rel = e2 ? name : relp.generic_string();
        if (it->is_symlink(e2))
        {
            fs::path target = fs::weakly_canonical(p, e2);
            std::string t = target.generic_string(), b = base.generic_string();
            if (e2 || t.rfind(b, 0) != 0) r.add(kRisky, "Link leads outside folder", rel);
            it.disable_recursion_pending();
            continue;
        }
        if (it->is_directory(e2)) { if (!low.empty() && low[0] == '.') r.add(kNote, "Has hidden folders", rel); continue; }
        if (!it->is_regular_file(e2)) { r.add(kCheck, "Has special system files", rel); continue; }
        ++r.files;
        if (!low.empty() && low[0] == '.') r.add(kNote, "Has hidden files", rel);
#if !defined(_WIN32)
        struct stat st {};
        if (::lstat(p.c_str(), &st) == 0 && (st.st_mode & (S_ISUID | S_ISGID))) r.add(kRisky, "Files with special rights", rel);
        const bool exec = ::lstat(p.c_str(), &st) == 0 && (st.st_mode & 0111);
#else
        const bool exec = false;
#endif
        auto ends = [&](const char* x) { size_t n = std::strlen(x); return low.size() >= n && low.compare(low.size() - n, n, x) == 0; };
        if (ends(".ko")) { r.add(kRisky, "Contains a system driver", rel); continue; }
        std::vector<uint8_t> head;
        {
            std::ifstream f(p, std::ios::binary);
            head.resize(4);
            if (!f.read((char*)head.data(), 4)) head.clear();
        }
        const bool isElf = head.size() == 4 && std::memcmp(head.data(), "\x7f" "ELF", 4) == 0;
        const bool isScript = head.size() >= 2 && head[0] == '#' && head[1] == '!';
        if (isScript || ends(".sh")) { r.add(kRisky, "Contains a script", rel); continue; }
        if (!isElf)
        {
            if (exec && !ends(".png") && !ends(".json") && !ends(".txt") && !ends(".wav") && !ends(".xml"))
                r.add(kNote, "Has files marked runnable", rel);
            continue;
        }
        ++r.codeFiles;
        std::vector<uint8_t> d;
        if (!readAll(p, d)) { r.add(kCheck, "Code file unreadable", rel); continue; }
        Elf e = readElf(d);
        if (!e.ok) { r.add(kCheck, "Code file unreadable", rel); continue; }
        if (e.hasInterp || e.type == 2) { r.add(kRisky, "Contains a program", rel); }
        if (e.machine != 40 && e.machine != 183) r.add(kNote, "Computer code, not MPC", rel);
        std::set<std::string> hit;
        for (const Rule& ru : importRules())
            if (std::binary_search(e.imports.begin(), e.imports.end(), std::string(ru.name)))
                r.add(ru.level, ru.text, ru.name);
        for (const std::string& lib : e.needed)
        {
            std::string why;
            int lv = libraryLevel(lib, why);
            if (lv > kClean) r.add(lv, why, lib);
        }
        for (const Rule& ru : stringRules())
            if (contains(d, ru.name)) r.add(ru.level, ru.text, ru.name);
        if (e.imports.empty() && e.needed.empty()) r.add(kNote, "Code hides what it uses", rel);
    }
    if (r.codeFiles == 0) r.add(kCheck, "No plugin code found", "");
    std::stable_sort(r.findings.begin(), r.findings.end(), [](const Finding& a, const Finding& b) { return a.level > b.level; });
    return r;
}

inline const char* levelName(int lv) { return lv >= kRisky ? "RISKY" : lv == kCheck ? "CHECK" : "CLEAN"; }

// ------------------------------------------------------------------ every drive
struct Drive { std::string root, label; };

inline std::vector<Drive> drives()
{
    std::vector<Drive> out;
    std::set<std::string> seen;
    auto add = [&](const fs::path& p, const std::string& label) {
        std::error_code ec;
        if (!fs::is_directory(p / "VST2 Plugins", ec)) return;
        std::string key = fs::weakly_canonical(p, ec).string();
        if (!seen.insert(key).second) return;
        out.push_back({p.string(), label});
    };
    if (const char* over = std::getenv("SCANNER_DRIVE")) add(over, "Test drive");   // tests on a computer
#if !defined(_WIN32)
    add("/nvme", "Internal");
    add("/sdcard", "Internal");
    std::error_code ec;
    for (auto& e : fs::directory_iterator("/media", ec))
    {
        std::string n = e.path().filename().string();
        if (n.rfind("az01-", 0) == 0 || n == "root") continue;
        add(e.path(), n);
    }
#endif
    return out;
}

// selfFolder: this scanner's own folder. It is left out: its code holds the very list of warning words it looks
// for ("rm -rf", "wget", ...), so it would always flag itself.
inline std::vector<Report> scanAll(const std::string& selfFolder = "")
{
    std::vector<Report> all;
    std::error_code sec;
    const std::string self = selfFolder.empty() ? "" : fs::weakly_canonical(fs::path(selfFolder), sec).string();
    for (const Drive& d : drives())
    {
        std::error_code ec;
        std::vector<fs::path> folders;
        for (auto& e : fs::directory_iterator(fs::path(d.root) / "VST2 Plugins", ec))
            if (e.is_directory(ec) || e.is_symlink(ec)) folders.push_back(e.path());
        std::sort(folders.begin(), folders.end());
        for (const fs::path& f : folders)
        {
            if (!self.empty() && fs::weakly_canonical(f, ec).string() == self) continue;
            all.push_back(scanPlugin(f, d.label));
        }
    }
    std::stable_sort(all.begin(), all.end(), [](const Report& a, const Report& b) { return a.level > b.level; });
    return all;
}

} // namespace scan
