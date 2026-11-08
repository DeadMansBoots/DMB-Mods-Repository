"""Builds dmb-1.7.json, the one mod list Dead Man's Boots' launcher reads: VCMI's official mod index
merged with DMB's accepted entries (entries/<mod-id>.json). When an id is in both, DMB's entry wins.
The catalog holds pointers only: every mod stays its own project, with its mod.json and its download
wherever its author publishes them.

    python tools/build_catalog.py [--vcmi-index URL_OR_FILE] [--check] [--gate-report FILE] [--selftest]

--check validates the entries and the merge without writing (the pull-request check). Otherwise
dmb-1.7.json is written when its content changed. If VCMI's index cannot be read, nothing is written
and the exit code is 1, so the last good list stays in place.

The engine gate: every mod's newest mod.json (the address in its entry) is compared with the engine
version DMB is built on (read from DMB's own source). A mod that needs a newer engine than DMB has
(its "compatibility" min above it, or its max below it) is not offered: the catalog keeps the
mod's previous entry when that one is still compatible, and leaves the mod out when it is not. The
mods this happened to are written to the --gate-report file, and the workflow opens an issue for each.
A mod whose mod.json cannot be read is left as it is (nothing is known about it).
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VCMI_INDEX = "https://raw.githubusercontent.com/vcmi/vcmi-mods-repository/develop/vcmi-1.7.json"
# the engine DMB is built on, read from DMB's source so the gate follows the game; the fallback is used when that cannot be read
ENGINE_SOURCE = "https://raw.githubusercontent.com/DeadMansBoots/Dead-Mans-Boots/dmb/cmake_modules/VersionDefinition.cmake"
ENGINE_FALLBACK = (1, 7, 5)
VCMI_RELEASES = "https://api.github.com/repos/vcmi/vcmi/releases?per_page=30"
OUT = os.path.join(ROOT, "dmb-1.7.json")
REQUIRED = {"mod": str, "download": str, "downloadSize": (int, float)}
# "pinned": why this entry points at DMB's own copy of a mod (a mod DMB keeps at a version its engine can run); such an entry is not marked as DMB's own mod
OPTIONAL = {"screenshots": list, "descriptionURL": str, "githubStars": int, "codeSha256": (str, list), "pinned": str}
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


# ---------------------------------------------------------------------------------------------------
# the engine gate

def version_tuple(text):
    """'1.8.0' -> (1, 8, 0); '1.8' -> (1, 8); anything without a leading number -> None."""
    found = re.match(r"\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    if not found:
        return None
    return tuple(int(part) for part in found.groups() if part is not None)


def read_engine(fetch):
    """The engine version DMB is built on: VCMI_VERSION_MAJOR, MINOR and PATCH in DMB's VersionDefinition.cmake."""
    text = fetch(ENGINE_SOURCE)
    if text:
        parts = [re.search(r"set\(VCMI_VERSION_%s (\d+)\)" % name, text) for name in ("MAJOR", "MINOR", "PATCH")]
        if all(parts):
            return tuple(int(p.group(1)) for p in parts)
    print("warning: the engine version could not be read from DMB's source; using %s" % ".".join(map(str, ENGINE_FALLBACK)))
    return ENGINE_FALLBACK


def modjson_facts(text):
    """(version, min, max) from a mod.json's text. mod.json is VCMI's lenient JSON (comments, trailing commas), so it is read with patterns, not a JSON parser:
    the first "version" at the top (its own, before any submod) and the "compatibility" block with "min" and "max"."""
    version = re.search(r'"version"\s*:\s*"([^"]*)"', text)
    block = re.search(r'"compatibility"\s*:\s*\{([^}]*)\}', text)
    low = high = None
    if block:
        a = re.search(r'"min"\s*:\s*"([^"]*)"', block.group(1))
        b = re.search(r'"max"\s*:\s*"([^"]*)"', block.group(1))
        low = version_tuple(a.group(1)) if a else None
        high = version_tuple(b.group(1)) if b else None
    return (version.group(1) if version else "?"), low, high


def judge(entry, engine, fetch):
    """('ok'|'needs-newer'|'too-old'|'unknown', version, min, max) for one catalog entry, from the mod.json its address names."""
    text = fetch(entry.get("mod", "")) if isinstance(entry, dict) else None
    if not text:
        return "unknown", "?", None, None
    version, low, high = modjson_facts(text)
    if low and tuple(engine[:len(low)]) < low:
        return "needs-newer", version, low, high
    if high and tuple(engine[:len(high)]) > high:
        return "too-old", version, low, high
    return "ok", version, low, high


def apply_gate(merged, previous, engine, fetch, workers=12):
    """Takes the merged list; returns (list, report). An entry that needs a newer engine is replaced by the previous list's entry for that mod when that one is compatible,
    otherwise left out. Entries with no readable mod.json stay."""
    ids = sorted(merged)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = dict(zip(ids, pool.map(lambda i: judge(merged[i], engine, fetch), ids)))
    result, report = dict(merged), []
    for mod_id in ids:
        state, version, low, high = verdicts[mod_id]
        if state == "unknown":
            # nothing is known about this version this time (a failed fetch): when the previous list had the mod at another address, that one stays rather than a version that may be the held-back one
            before = previous.get(mod_id)
            if isinstance(before, dict) and before.get("download") != merged[mod_id].get("download") and "dmbEntry" not in merged[mod_id] and "pinned" not in merged[mod_id]:
                result[mod_id] = before
            continue
        if state == "ok":
            continue
        before = previous.get(mod_id)
        action = "left out of the list"
        if isinstance(before, dict) and before.get("download") != merged[mod_id].get("download") and judge(before, engine, fetch)[0] == "ok":
            result[mod_id] = before
            action = "kept the previous entry"
        else:
            del result[mod_id]
        report.append({"mod": mod_id, "version": version, "needsMin": ".".join(map(str, low)) if low else "", "needsMax": ".".join(map(str, high)) if high else "",
                       "engine": ".".join(map(str, engine)), "state": state, "action": action})
    return result, report


def newer_vcmi_releases(engine, fetch):
    """VCMI releases (not drafts, not pre-releases) newer than the engine DMB runs on, as report items: moving DMB to a newer VCMI is a deliberate step, so each one opens an issue."""
    text = fetch(VCMI_RELEASES)
    try:
        releases = json.loads(text) if text else []
    except ValueError:
        releases = []
    found = []
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = str(release.get("tag_name", ""))
        number = version_tuple(tag.lstrip("vV"))
        if number and number > tuple(engine[:len(number)]) and len(number) >= 2:
            found.append({"kind": "engine", "version": tag, "published": str(release.get("published_at", ""))[:10], "engine": ".".join(map(str, engine))})
    return found


def fetch_text(url, timeout=25):
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    try:
        headers = {"User-Agent": "dmb-catalog-gate"}
        if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return r.read(2 * 1024 * 1024).decode("utf-8-sig", errors="replace")
    except (OSError, ValueError):
        return None


def selftest():
    docs = {
        "https://x/ok.json": '{ "version" : "1.2", "compatibility" : { "min" : "1.7.0" }, }',
        "https://x/new.json": '{ "version" : "2.0", "compatibility" : { "min" : "1.8.0" }, }',
        "https://x/nocompat.json": '{ "version" : "3" }',
        "https://x/old.json": '{ "version" : "4", "compatibility" : { "min" : "1.7.0", "max" : "1.6" } }',
        "https://x/maxok.json": '{ "version" : "5", "compatibility" : { "min" : "1.6.0", "max" : "1.7" } }',
        "https://x/pin.json": '{ "version" : "1.0.49", "compatibility" : { "min" : "1.7.0" } }',
        ENGINE_SOURCE: "set(VCMI_VERSION_MAJOR 1)\nset(VCMI_VERSION_MINOR 7)\nset(VCMI_VERSION_PATCH 5)\n",
        VCMI_RELEASES: json.dumps([{"tag_name": "1.8.0", "draft": False, "prerelease": False, "published_at": "2027-01-02T00:00:00Z"},
                                   {"tag_name": "1.9.0-rc1", "draft": False, "prerelease": True}, {"tag_name": "1.7.5", "draft": False, "prerelease": False},
                                   {"tag_name": "1.8.1", "draft": True, "prerelease": False}]),
    }
    fetch = docs.get
    engine = read_engine(fetch)
    assert engine == (1, 7, 5), engine
    assert read_engine(lambda u: None) == ENGINE_FALLBACK
    assert version_tuple("1.8") == (1, 8) and version_tuple("junk") is None
    entry = lambda name, dl="d": {"mod": "https://x/%s.json" % name, "download": "https://x/%s.zip" % dl, "downloadSize": 1}
    merged = {"a-ok": entry("ok"), "b-new": entry("new", "newdl"), "c-none": entry("nocompat"), "d-old": entry("old"), "e-maxok": entry("maxok"), "f-gone": entry("missing"),
              "g-new-keep": entry("new", "newdl2"), "h-pinned": dict(entry("pin", "pindl"), pinned="kept")}
    previous = {"b-new": entry("new", "newdl"), "g-new-keep": entry("ok", "olddl")}
    result, report = apply_gate(merged, previous, engine, fetch)
    assert set(result) == {"a-ok", "c-none", "e-maxok", "f-gone", "g-new-keep", "h-pinned"}, sorted(result)
    assert result["g-new-keep"]["download"] == "https://x/olddl.zip"
    got = {r["mod"]: (r["state"], r["action"]) for r in report}
    assert got == {"b-new": ("needs-newer", "left out of the list"), "d-old": ("too-old", "left out of the list"), "g-new-keep": ("needs-newer", "kept the previous entry")}, got
    unreadable = {"i-down": {"mod": "https://x/unreachable.json", "download": "https://x/newdl.zip", "downloadSize": 1}}
    kept, _ = apply_gate(unreadable, {"i-down": entry("ok", "olddl")}, engine, fetch)
    assert kept["i-down"]["download"] == "https://x/olddl.zip", kept
    kept2, _ = apply_gate(unreadable, {}, engine, fetch)
    assert kept2["i-down"]["download"] == "https://x/newdl.zip", kept2
    news = newer_vcmi_releases(engine, fetch)
    assert [n["version"] for n in news] == ["1.8.0"], news
    assert newer_vcmi_releases(engine, lambda u: None) == []
    print("selftest: 12 checks pass")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vcmi-index", default=VCMI_INDEX)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--gate-report", help="write the mods the engine gate held back to this JSON file")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
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
    # pins and DMB's own mark come only from DMB's entries, never through VCMI's index
    merged = {k.lower(): {key: value for key, value in v.items() if key not in ("codeSha256", "dmbEntry", "pinned")}
              if isinstance(v, dict) else v for k, v in vcmi.items()}
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    report = []
    engine = None
    if not args.check:
        engine = read_engine(fetch_text)
        # a pinned entry is DMB's stand-in for a mod whose upstream build DMB's engine cannot run: when upstream's own entry runs on the engine again, the pin is let go
        for mod_id in sorted(entries):
            if "pinned" in entries[mod_id] and mod_id in merged and judge(merged[mod_id], engine, fetch_text)[0] == "ok":
                print("%s: upstream's entry runs on VCMI %s again; the pin is not used" % (mod_id, ".".join(map(str, engine))))
                del entries[mod_id]
    replaced = sorted(set(merged) & set(entries))
    # "dmbEntry" marks DMB's own entries, which DMB's launcher lists in its "DMB Mods" tab; a "pinned" entry is a community mod DMB keeps at a version its engine can run
    merged.update({mod_id: dict(entry, dmbEntry=True) if "pinned" not in entry else dict(entry) for mod_id, entry in entries.items()})
    if not args.check:
        try:
            previous = json.loads(old).get("availableMods", {}) if old else {}
        except ValueError:
            previous = {}
        merged, report = apply_gate(merged, previous, engine, fetch_text)
        print("engine gate (DMB runs on VCMI %s): %d mod(s) held back%s" % (".".join(map(str, engine)), len(report),
              "".join("\n  %s %s needs %s%s: %s" % (r["mod"], r["version"], r["needsMin"] or "-", " to " + r["needsMax"] if r["needsMax"] else "", r["action"]) for r in report)))
        newer = newer_vcmi_releases(engine, fetch_text)
        for item in newer:
            print("VCMI %s is out (%s); DMB runs on VCMI %s" % (item["version"], item["published"], item["engine"]))
        report = report + newer
        if args.gate_report:
            with open(args.gate_report, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=1)
    text = json.dumps({"availableMods": dict(sorted(merged.items()))}, indent="\t", ensure_ascii=False) + "\n"
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
