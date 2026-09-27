# DMB-Mods-Repository

The mod list of [Dead Man's Boots](https://github.com/DeadMansBoots/Dead-Mans-Boots), a Heroes of Might and Magic III engine built on VCMI. DMB's launcher reads this list for its mod manager, so every mod here installs from the launcher. It holds VCMI's own community mods, refreshed every day, plus the mods made for DMB.

Nothing here contains a mod's files. Each entry points at a mod that its author publishes in their own repository, wherever they keep it.

## Adding a mod

1. Publish the mod in its own repository, with a `mod.json` and a zip of the mod that can be downloaded without signing in (a GitHub release works).
2. Open a pull request that adds one file, `entries/<mod-id>.json`, in the format described in [entries/README.md](entries/README.md).
3. The pull request's check tells you if the entry is incomplete. Merging it starts a rebuild of the list, and the mod appears in DMB's launcher when that finishes, a few minutes later.

Every mod comes in this way, including the ones DMB's own team makes.

## What is in this repository

| File | What it is |
|---|---|
| `dmb-1.7.json` | The mod list the launcher shows: VCMI's official index merged with DMB's entries. Generated; do not edit by hand. VCMI 1.7's format: `availableMods` maps each mod's id to its `mod` (the URL of its mod.json), `download` (the URL of its zip), `downloadSize` (in megabytes) and `screenshots`, plus an optional `descriptionURL`. |
| `entries/` | DMB's own entries, one file per accepted mod (see `entries/README.md`). A mod is submitted as a pull request adding its file; merging it is the acceptance. |
| `tools/build_catalog.py` | The merge. When an id is in both, DMB's entry wins. If VCMI's index cannot be read, the last good list stays. |
| `.github/workflows/build-catalog.yml` | Runs the merge every day and whenever an entry changes, and commits the list only when it changed; checks every pull request's entries. Nobody curates VCMI's mods by hand. |
| `dmb-updates.json` | The launcher's update notice. `version` is the newest DMB release, `updateType` is minor, major or critical (the launcher colours it gray, orange or red), `changeLog` is shown as text, and `downloadLinks` gives the download page (`other`, or `windows`, `macos`, `linux`, `android` or `ios` for one platform). The launcher shows it only to builds whose own version is listed in `history`, so a new release adds the previous versions there. |

DMB's launcher reads the list as its one mod repository, and the notice as its update check:

    https://raw.githubusercontent.com/DeadMansBoots/DMB-Mods-Repository/main/dmb-1.7.json
    https://raw.githubusercontent.com/DeadMansBoots/DMB-Mods-Repository/main/dmb-updates.json

The launcher's rules for both files are in VCMI's source: `launcher/modManager/cmodlistview_moc.cpp`
(the mod list) and `launcher/updatedialog_moc.cpp` (the update notice).

## License

This repository's own files, the merge tool, the entry format and these docs, are under the [MIT license](LICENSE). The entries that come from VCMI's index are VCMI's, from [vcmi/vcmi-mods-repository](https://github.com/vcmi/vcmi-mods-repository), and every mod belongs to its authors.
