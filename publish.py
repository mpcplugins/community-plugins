"""Publishes approved uploads from thediskking.com/plugins/share as GitHub releases of this repo.
Copyright (c) 2026 The Disk King. All rights reserved.

Runs in GitHub Actions (see .github/workflows/publish.yml). Needs:
  COMMUNITY_FEED_KEY  the publishing key from thediskking.com/plugins/admin (a repo secret)
  GH_TOKEN            GitHub's own per-run pass (to create releases)
For each approved upload: download it, check the zip holds a "Maker - VST - Name" folder with its plugin.json,
publish it as release "<slug>-v<version>" with the asset "<Slug>-<version>-mpc-sdk.zip" (the name plugin lists
recognise), save its screenshot, maker and description in this repo, then tell the site it is published.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

SITE = "https://thediskking.com/plugins/api/"
REPO = "mpcplugins/community-plugins"
KEY = os.environ.get("COMMUNITY_FEED_KEY", "").strip()


def api(action, params=None, data=None, raw=False):
    q = urllib.parse.urlencode(dict(params or {}, key=KEY))
    req = urllib.request.Request(SITE + action + "?" + q, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={"User-Agent": "community-plugins-publisher"})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
    return body if raw else json.loads(body)


def slug(name):
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", name)).strip("-")


def check_zip(path):
    """The plugin folder in the zip, or None. Accepts the folder at the top or one level down."""
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            return None, "the zip is damaged (%s)" % bad
        names = z.namelist()
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            return None, "the zip has unsafe paths"
        for n in names:
            parts = n.split("/")
            if parts[-1] == "plugin.json" and len(parts) in (2, 3) and " - VST - " in parts[-2]:
                return "/".join(parts[:-1]), None
    return None, "no 'Maker - VST - Name' folder with a plugin.json inside"


def run(*args):
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)


def main():
    if not KEY:
        sys.exit("COMMUNITY_FEED_KEY is not set")
    uploads = api("approved.json")["uploads"]
    print("approved uploads waiting:", len(uploads))
    os.makedirs("work", exist_ok=True)
    os.makedirs("docs/screenshots", exist_ok=True)
    info = json.load(open("community.json", encoding="utf-8")) if os.path.exists("community.json") else {}
    tested = json.load(open("tested.json", encoding="utf-8")) if os.path.exists("tested.json") else []
    changed = False
    for u in uploads:
        name, ver = u["name"], u["version"]
        s = slug(name)
        tag = "%s-v%s" % (s.lower(), ver)
        zpath = os.path.join("work", "%s-%s-mpc-sdk.zip" % (s, ver))
        open(zpath, "wb").write(api("upload-file", {"id": u["id"], "file": "zip"}, raw=True))
        folder, problem = check_zip(zpath)
        if problem:
            print("SKIPPED %s %s: %s (left in the queue for The Disk King)" % (name, ver, problem))
            continue
        assets = [zpath]
        if u.get("shot"):
            ext = u["shot"].rsplit(".", 1)[-1]
            spath = os.path.join("docs", "screenshots", "%s.%s" % (s, ext))
            open(spath, "wb").write(api("upload-file", {"id": u["id"], "file": "shot"}, raw=True))
            changed = True
        notes = ("**%s %s** by **%s**\n\n%s\n\n%s"
                 "Uploaded by its maker at thediskking.com/plugins/share and approved by The Disk King.\n\n"
                 "**Install:** unzip it and copy the folder `%s` into `VST2 Plugins` on your MPC (MPC OS 3.10.1 with "
                 "External Plugin Support on), then restart. Or install it with MPC Plugins Manager.\n\n"
                 "Provided as is by its maker. The Disk King is not responsible in any way for any damage or loss. Back up first."
                 % (name, ver, u["maker"], u["description"], ("Tested by its maker on: %s\n\n" % u["tested"]) if u.get("tested") else "",
                    folder.split("/")[-1]))
        exists = subprocess.run(["gh", "release", "view", tag, "--repo", REPO], capture_output=True).returncode == 0
        if not exists:
            run("gh", "release", "create", tag, *assets, "--repo", REPO, "--title", "%s %s by %s" % (name, ver, u["maker"]), "--notes", notes)
        info[s] = {"name": name, "maker": u["maker"], "kind": u["kind"], "description": u["description"], "folder": folder.split("/")[-1]}
        if u.get("tested"):
            tested = [t for t in tested if not (t.get("id") == s.lower() and t.get("version") == ver)]
            tested.append({"id": s.lower(), "version": ver, "device": u["tested"], "firmware": "", "date": u.get("reviewed", "")[:10]})
        changed = True
        url = "https://github.com/%s/releases/tag/%s" % (REPO, tag)
        api("published", data={"key": KEY, "id": u["id"], "url": url})
        print("PUBLISHED", name, ver, url)
    if changed:
        json.dump(info, open("community.json", "w", encoding="utf-8"), indent=1, sort_keys=True)
        json.dump(tested, open("tested.json", "w", encoding="utf-8"), indent=1)
        open("changed.flag", "w").write("1")


if __name__ == "__main__":
    main()
