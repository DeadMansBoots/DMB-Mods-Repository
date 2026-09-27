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
import tempfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VCMI_INDEX = "https://raw.githubusercontent.com/vcmi/vcmi-mods-repository/develop/vcmi-1.7.json"
OUT = os.path.join(ROOT, "dmb-1.7.json")
REQUIRED = {"mod": str, "download": str, "downloadSize": (int, float)}
OPTIONAL = {"screenshots": list, "descriptionURL": str, "githubStars": int, "codeSha256": (str, list)}
# A mod that brings code (an AI plugin's "ai" folder, a map generator's "generator" folder) runs in DMB
# only when its entry here pins that folder: DMB's release\addon_hash.py prints the pin. Only DMB's own
# entries may pin; a pin arriving from VCMI's index is dropped.
PIN = re.compile(r"[0-9a-f]{64}")


MAX_DOWNLOAD = 512 * 1024 * 1024


def pin_problem(value):
    pins = value if isinstance(value, list) else [value]
    if not pins or not all(isinstance(p, str) and PIN.fullmatch(p) for p in pins):
        return "codeSha256 must be 64 lower-case hex digits, or a list of them"
    return None


def verify_pins(entries, strict):
    """Fetches each pinned entry's download and hashes it as the game will: every code folder in it
    must be one of the entry's pins. A download that cannot be fetched fails only a strict (pull
    request) check; a pin that does not match always fails."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from addon_hash import zip_pins
    problems = []
    for mod_id, entry in sorted(entries.items()):
        if "codeSha256" not in entry:
            continue
        pins = entry["codeSha256"] if isinstance(entry["codeSha256"], list) else [entry["codeSha256"]]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                archive = os.path.join(tmp, "mod.zip")
                size = 0
                with urllib.request.urlopen(entry["download"], timeout=300) as r, open(archive, "wb") as fh:
                    for chunk in iter(lambda: r.read(1 << 20), b""):
                        size += len(chunk)
                        if size > MAX_DOWNLOAD:
                            raise ValueError("larger than %d MB" % (MAX_DOWNLOAD >> 20))
                        fh.write(chunk)
                found = zip_pins(archive)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            message = "%s: its download could not be checked (%s)" % (mod_id, exc)
            if strict:
                problems.append(message)
            else:
                print("warning: " + message)
            continue
        if not found:
            problems.append("%s: codeSha256 is given, but its download has no ai or generator folder beside a mod.json" % mod_id)
        for folder, (value, count) in found.items():
            if value in pins:
                print("%s: %s pinned (%d files, %s)" % (mod_id, folder, count, value))
            else:
                problems.append("%s: %s in the download hashes to %s, which codeSha256 does not list" % (mod_id, folder, value))
    return problems


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
        if "codeSha256" in entry and pin_problem(entry["codeSha256"]):
            problems.append("%s: %s" % (name, pin_problem(entry["codeSha256"])))
        entries[mod_id] = entry
    return entries, problems


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vcmi-index", default=VCMI_INDEX)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    entries, problems = load_entries()
    if not problems:
        problems = verify_pins(entries, strict=args.check)
    if problems:
        print("entries with problems:\n  " + "\n  ".join(problems))
        return 1
    try:
        vcmi = load_vcmi(args.vcmi_index)
    except (OSError, ValueError) as exc:
        print("VCMI's index could not be read (%s); the list is left as it was" % exc)
        return 1
    merged = {k.lower(): {key: value for key, value in v.items() if key != "codeSha256"} if isinstance(v, dict) else v
              for k, v in vcmi.items()}
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
