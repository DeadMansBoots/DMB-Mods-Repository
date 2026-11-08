"""Opens one issue in this repository for each mod the engine gate held back (build_catalog.py --gate-report FILE), unless an open issue with the same title exists.
Runs in the catalog workflow with its own token (GITHUB_TOKEN) and repository (GITHUB_REPOSITORY); nothing is posted anywhere else.

    python tools/open_gate_issues.py FILE
"""
import json
import os
import sys
import urllib.request

API = "https://api.github.com"


def call(path, token, data=None):
    request = urllib.request.Request(API + path, data=json.dumps(data).encode("utf-8") if data is not None else None,
                                     headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "dmb-catalog-gate", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as r:
        return json.loads(r.read() or b"[]")


def title_of(item):
    if item.get("kind") == "engine":
        return "VCMI %s is out and DMB runs on VCMI %s: moving to it is a decision" % (item["version"], item["engine"])
    needs = ("needs VCMI %s or newer" % item["needsMin"]) if item["state"] == "needs-newer" else ("only runs up to VCMI %s" % item["needsMax"])
    return "%s %s needs a newer game engine than this version of DMB has (%s; DMB has VCMI %s)" % (item["mod"], item["version"], needs, item["engine"]) \
        if item["state"] == "needs-newer" else "%s %s does not run on this version of DMB's game engine (%s; DMB has VCMI %s)" % (item["mod"], item["version"], needs, item["engine"])


def body_of(item):
    if item.get("kind") == "engine":
        return ("VCMI %s was published on %s. Dead Man's Boots runs on VCMI %s. Moving DMB to a newer VCMI changes saves, the lobby and the add-on interface, so it is a decision, "
                "not something the catalog does by itself. Until then the list keeps offering the mods that run on VCMI %s.\n\n"
                "Close this issue when DMB has moved or the decision is made.\n" % (item["version"], item["published"] or "recently", item["engine"], item["engine"]))
    return ("The engine gate found that the newest %s (version %s) %s. Dead Man's Boots runs on VCMI %s, so the launcher cannot run it.\n\n"
            "What the catalog did: %s.\n\n"
            "What to do: when a version that runs on VCMI %s is published, nothing is needed (the next catalog run offers it). If the mod should stay available, "
            "make a release of this repository with the last version that runs (a zip and its mod.json, unchanged) and add entries/%s.json with a \"pinned\" note, as for tides-of-war. "
            "Close this issue when that is done or the mod runs on DMB's engine again.\n"
            % (item["mod"], item["version"], ("needs VCMI %s or newer" % item["needsMin"]) if item["state"] == "needs-newer" else ("only runs up to VCMI %s" % item["needsMax"]),
               item["engine"], item["action"], item["engine"], item["mod"]))


def main(argv):
    token, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
    if len(argv) != 1 or not token or not repo:
        print("usage: open_gate_issues.py FILE (with GITHUB_TOKEN and GITHUB_REPOSITORY set)")
        return 2
    report = json.load(open(argv[0], encoding="utf-8"))
    if not report:
        print("the engine gate held nothing back")
        return 0
    open_titles = {issue["title"] for issue in call("/repos/%s/issues?state=open&per_page=100" % repo, token) if "pull_request" not in issue}
    for item in report:
        title = title_of(item)
        if title in open_titles:
            print("already open:", title)
            continue
        made = call("/repos/%s/issues" % repo, token, {"title": title, "body": body_of(item)})
        print("opened #%s: %s" % (made["number"], title))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
