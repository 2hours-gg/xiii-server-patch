# Changelog

Dates are when each step was proven on a test server.

## 1.0.0 (2026-11-25)

First release.

- `install.py`: `check`, `install` and `uninstall` for all patches, the add-on and the `XIII.ini` lines, with `--dry-run`, `.orig` backups and refusal of unknown files.
- Tests that run without game files, CI on Linux and Windows, and tag releases with `SHA256SUMS`, `MD5SUMS` and a signed build provenance attestation.
- Reproducible add-on builds: `build_ctl.py` replaces the random package GUID that UCC writes with one derived from the sources. `--compare` compares two builds. The shipped `dist/TwoHoursCtl.u` is such a build: two clean builds of the same sources gave the same bytes (2026-11-25).
- Add-on source comments reworded as neutral statements (no code change), and the add-on rebuilt.
- Documented: the InsideXIII master server lists the name from the URL option `?ServerName=` (not from `XIII.ini`), and a join password is `GamePassword` in `XIII.ini` plus `?IsPrivate=Y` in the URL (2026-11-25).

`dist/TwoHoursCtl.u`: sha256 `07a89bdba247df37fbf439038be83175560f5c8aa4c072cd5d8bae91fda4cedf`, 39046 bytes.

## Before 1.0.0

These steps were published in this repository before it had releases.

### 2026-11-22 and 2026-11-23: bots and admin

- `bots <n>` is the number of bots. Players never count toward it. At most 8, and a player joining a full server takes a bot's seat.
- The admin password works in any case (`TwoHoursLogin`, a mutator in the add-on).
- Private replies wait until the player has a pawn, so a dead player or one on "Press Fire to begin" still sees them.
- `players` command: humans, bots, max players and map in one line.

### 2026-11-21: players follow a map change and stay

- A real XIII client followed each map change, then dropped to its menu 4 seconds later. Run headless under Wine, the client showed why: its `Engine.dll` arms a 5 second "connection failed" timer when the server closes the old connection.
- `travel [<wait>] <url>`: players get only the map (their own options stay), then the menu map, and the server switches once they all left. They join the new map and stay.
- The 3rd change in one process runs as a travel into a restart, and players land on the restarted server by themselves.
- `tools/xiii_netclient.py --follow`: reconnect after a travel, like a game client.

### 2026-11-18: map changes with players connected

- A live map change with a real player crashed the server: `Cast of TcpipConnection to Viewport failed`. `ClientTravel` was declared `static`, so it ran on the server instead of being sent to the player.
- `patch/xiii_clienttravel_patch.py`: 1 byte in `Engine.u` clears the static flag.
- `tools/xiii_netclient.py`: a minimal network client that joins over UDP like a player, for tests.
- The admin password goes in `XIII.ini`, out of the travel URL that every player receives.

### 2026-11-16: live map changes, admin chat, rotation, voting and bots

- `patch/xiii_engine_patch.py`: 7 bytes in `Engine.dll` stop the crash on any map change on a dedicated server.
- The add-on `TwoHoursCtl.u`: a local control port (`status`, `travel`, `say`, `kick`, `ban`, `tell`, `poll`) and `!` chat commands queued for a poller.
- Map rotation at the end of a match, and map voting in chat.
- `patch/xiii_bot_patch.py`: 1 byte in `XIIIMP.u` and 32 in `XIIIMP.dll` let the dedicated server run bots.
