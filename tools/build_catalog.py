"""Builds dmb-1.7.json, the one mod list Dead Man's Boots' launcher reads: VCMI's official mod index
merged with DMB's accepted entries (entries/<mod-id>.json). When an id is in both, DMB's entry wins.
The catalog holds pointers only: every mod stays its own project, with its mod.json and its download
wherever its author publishes them.

    python tools/build_catalog.py [--vcmi-index URL_OR_FILE] [--check]

--check validates the entries and the merge without writing (the pull-request check). Otherwise
dmb-1.7.json is written when its content changed. If VCMI's index cannot be read, nothing is written
and the exit code is 1, so the last good list stays in place.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VCMI_INDEX = "https://raw.githubusercontent.com/vcmi/vcmi-mods-repository/develop/vcmi-1.7.json"
OUT = os.path.join(ROOT, "dmb-1.7.json")
REQUIRED = {"mod": str, "download": str, "downloadSize": (int, float)}
OPTIONAL = {"screenshots": list, "descriptionURL": str, "githubStars": int}


def load_vcmi(source):
    if re.match(r"https?://", source):
        with urllib.request.urlopen(source, timeout=60) as r:
            doc = json.loads(r.read())
    else:
        with open(source, encoding="utf-8") as fh:
            doc = json.load(fh)
    mods = doc.get("availableMods") if isinstance(doc, dict) else None
    if not isinstance(mods, dict) or not mods:
        raise ValueError("VCMI's index has no availableMods")
    return mods


def load_entries():
    """DMB's entries: one file per mod, named for the mod's id (lower case, as the launcher keys them)."""
    folder = os.path.join(ROOT, "entries")
    entries, problems = {}, []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        mod_id = name[:-5]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", mod_id):
            problems.append("%s: the file name must be the mod's id, lower case" % name)
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                entry = json.load(fh)
        except ValueError as exc:
            problems.append("%s: not JSON (%s)" % (name, exc))
            continue
        for key, kind in REQUIRED.items():
            if not isinstance(entry.get(key), kind):
                problems.append("%s: %s is missing or not a %s" % (name, key, getattr(kind, "__name__", "number")))
        for key in entry:
            if key not in REQUIRED and key not in OPTIONAL:
                problems.append("%s: unknown key %s" % (name, key))
        for key in ("mod", "download"):
            if isinstance(entry.get(key), str) and not entry[key].startswith("https://"):
                problems.append("%s: %s must be an https address" % (name, key))
        entries[mod_id] = entry
    return entries, problems


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vcmi-index", default=VCMI_INDEX)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    entries, problems = load_entries()
    if problems:
        print("entries with problems:\n  " + "\n  ".join(problems))
        return 1
    try:
        vcmi = load_vcmi(args.vcmi_index)
    except (OSError, ValueError) as exc:
        print("VCMI's index could not be read (%s); the list is left as it was" % exc)
        return 1
    merged = {k.lower(): v for k, v in vcmi.items()}
    replaced = sorted(set(merged) & set(entries))
    merged.update(entries)
    text = json.dumps({"availableMods": dict(sorted(merged.items()))}, indent="\t", ensure_ascii=False) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    print("%d mods: %d from VCMI's index, %d DMB entries (%d replacing VCMI's own)%s"
          % (len(merged), len(vcmi), len(entries), len(replaced), "; " + ", ".join(replaced) if replaced else ""))
    if args.check:
        return 0
    if text != old:
        with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("dmb-1.7.json written")
    else:
        print("dmb-1.7.json unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
