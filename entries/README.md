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

`downloadSize` is in MB. `screenshots` and `descriptionURL` are optional. A mod is submitted as a
pull request that adds its file here; the catalog's check validates it, and merging the pull
request accepts the mod. The same file under the id of one of VCMI's own mods replaces that mod's
listing in DMB's catalog.

Every mod comes in this way, including the ones DMB's own team makes: its own repository,
wherever its author wants to host it (a personal account is fine; it does not belong under DMB's
organization), and one entry here by pull request.
