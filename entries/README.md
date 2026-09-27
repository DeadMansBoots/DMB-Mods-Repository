# Entries: the mods DMB's catalog adds

Each file here is one accepted mod, named for its id in lower case, `<mod-id>.json`. It is a
pointer: the mod itself stays its own project, and its `mod.json` and its download are published by
its author, not stored here.

    {
        "mod": "https://github.com/<author>/<mod>/releases/download/<version>/mod.json",
        "download": "https://github.com/<author>/<mod>/releases/download/<version>/<mod>.zip",
        "downloadSize": 1.5,
        "screenshots": [ "https://raw.githubusercontent.com/<author>/<mod>/main/screenshots/1.png" ]
    }

`downloadSize` is in MB. `screenshots` and `descriptionURL` are optional.

A mod that brings code needs one more key, `codeSha256`. That covers an AI plugin (its `ai`
folder) and a map generator (its `generator` folder). DMB runs such code only when it matches the
pin here, and anything that does not match stays unused, with the reason shown to the player.
`python tools/addon_hash.py --zip <mod>.zip` prints the pin for your release zip. The check
downloads the zip and computes the same thing, so a wrong pin fails the pull request. A mod with
both folders lists both pins, as a list. So can a mod whose older release should keep working for a
while.

    "codeSha256": "f374ad5e6824bcb9d573c8ae7970513ecd92ec278897f4ecf0285e6143605acd"

A new release with changed code needs its new pin here before players can run it.

The list's builder marks every entry from this folder with `dmbEntry`, and DMB's launcher shows those
mods in its own "DMB Mods" tab as well as in the full list. The mark is the builder's to set: an
entry that carries it itself fails the check. A mod is submitted as a
pull request that adds its file here; the catalog's check validates it, and merging the pull
request accepts the mod. The same file under the id of one of VCMI's own mods replaces that mod's
listing in DMB's catalog.

Every mod comes in this way, including the ones DMB's own team makes: its own repository,
wherever its author wants to host it (a personal account is fine; it does not belong under DMB's
organization), and one entry here by pull request.
