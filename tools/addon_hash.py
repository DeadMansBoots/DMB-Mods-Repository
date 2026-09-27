"""Prints the codeSha256 that DMB's mod catalog pins for an addon: the hash the game computes
(DMB's lib/modding/AddonCode.cpp, folderHash) over an AI plugin's "ai" folder or a map generator's
"generator" folder, before it runs anything from it.

Every file under the folder becomes a line "<its SHA-256>  <its path>\\n", the path relative to the
folder with "/" separators. The lines are sorted by path, and the SHA-256 of all of them together is
the pin. They are the lines sha256sum prints, so a shell can check a pin too:

    cd generator && find . -type f | sed 's|^./||' | LC_ALL=C sort | xargs -d '\\n' sha256sum | sha256sum

    py addon_hash.py FOLDER             the pin of one code folder
    py addon_hash.py --mod MODFOLDER    the pins of a mod folder's "ai" and "generator" folders
    py addon_hash.py --zip MOD.zip      the same for a mod archive, read in place as the launcher
                                        would unpack it
"""
import argparse
import hashlib
import os
import sys
import zipfile

KINDS = ("ai", "generator")


def pin(files):
    """files: (path relative to the code folder with "/" separators, content hash) pairs."""
    lines = "".join("%s  %s\n" % (digest, path) for path, digest in sorted(files, key=lambda f: f[0].encode("utf-8")))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def folder_pin(folder):
    files = []
    for directory, _, names in os.walk(folder):
        for name in names:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                files.append((os.path.relpath(path, folder).replace(os.sep, "/"), file_hash(path)))
    return pin(files), len(files)


def zip_pins(archive):
    """The pins of every code folder in a mod archive: {"<mod>/<kind>": (pin, file count)}."""
    found = {}
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = info.filename.replace("\\", "/").split("/")
            # <mod>/<kind>/... as VCMI's mod archives lay a mod out
            for i, part in enumerate(parts[:-1]):
                if part in KINDS and i >= 1 and z.namelist() and "/".join(parts[:i]) + "/mod.json" in z.namelist():
                    key = "/".join(parts[:i + 1])
                    found.setdefault(key, []).append(("/".join(parts[i + 1:]), hashlib.sha256(z.read(info)).hexdigest()))
                    break
    return {key: (pin(files), len(files)) for key, files in sorted(found.items())}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--mod", help="a mod folder: its ai and generator folders")
    ap.add_argument("--zip", help="a mod archive")
    args = ap.parse_args(argv)
    if args.zip:
        pins = zip_pins(args.zip)
        if not pins:
            print("no ai or generator folder beside a mod.json in %s" % args.zip)
            return 1
        for key, (value, count) in pins.items():
            print("%s  %s  (%d files)" % (value, key, count))
    elif args.mod:
        folders = [os.path.join(args.mod, kind) for kind in KINDS if os.path.isdir(os.path.join(args.mod, kind))]
        if not folders:
            print("no ai or generator folder in %s" % args.mod)
            return 1
        for folder in folders:
            value, count = folder_pin(folder)
            print("%s  %s  (%d files)" % (value, folder, count))
    elif args.folder:
        value, count = folder_pin(args.folder)
        print("%s  (%d files)" % (value, count))
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
