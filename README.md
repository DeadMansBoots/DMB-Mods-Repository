# DMB-Mods-Repository

Dead Man's Boots' mod catalog and its update notice: the files DMB's launcher downloads. They live
in their own public repository because the launcher fetches them without logging in to GitHub.

The catalog is the one place DMB lists mods, both VCMI's community mods and mods made for DMB. It
holds pointers only. Every mod stays its own project, and its `mod.json` and its download are
published by its author wherever they choose; nothing here contains a mod's code or art.

| File | What it is |
|---|---|
| `dmb-1.7.json` | The mod list the launcher shows: VCMI's official index merged with DMB's entries. Generated; do not edit by hand. VCMI 1.7's format: `availableMods` maps each mod's id to its `mod` (the URL of its mod.json), `download` (the URL of its zip), `downloadSize` (in megabytes) and `screenshots`, plus an optional `descriptionURL`. |
| `entries/` | DMB's own entries, one file per accepted mod (see `entries/README.md`). A mod is submitted as a pull request adding its file; merging it is the acceptance. |
| `tools/build_catalog.py` | The merge. When an id is in both, DMB's entry wins. If VCMI's index cannot be read, the last good list stays. |
| `.github/workflows/build-catalog.yml` | Runs the merge every day and whenever an entry changes, and commits the list only when it changed; checks every pull request's entries. Nobody curates VCMI's mods by hand. |
| `dmb-updates.json` | The update notice. `version` is the newest DMB release, `updateType` is minor, major or critical (the launcher colours it gray, orange or red), `changeLog` is shown as text, and `downloadLinks` gives the download page (`other`, or `windows`, `macos`, `linux`, `android` or `ios` for one platform). The launcher shows it only to builds whose own version is listed in `history`, so a new release adds the previous versions there. |

DMB's launcher reads the list as its one mod repository, and the notice as its update check:

    https://raw.githubusercontent.com/DeadMansBoots/DMB-Mods-Repository/main/dmb-1.7.json
    https://raw.githubusercontent.com/DeadMansBoots/DMB-Mods-Repository/main/dmb-updates.json

The launcher's rules for both files are in VCMI's source: `launcher/modManager/cmodlistview_moc.cpp`
(the mod list) and `launcher/updatedialog_moc.cpp` (the update notice).
