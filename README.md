# XIII server patch: live map changes, bots and admin commands for the 2003 dedicated server

[![ci](https://github.com/2hours-gg/xiii-server-patch/actions/workflows/ci.yml/badge.svg)](https://github.com/2hours-gg/xiii-server-patch/actions/workflows/ci.yml)

The stock **XIII (2003)** dedicated server cannot change map while it runs, has no remote console and cannot run bots. Forcing a map change crashes it. This project fixes that:

- **Live map and mode changes.** Players stay connected and follow the server to the new map.
- **Bots** on the dedicated server, in all 6 modes.
- **Admin commands** from the in-game chat (`!map`, `!mode`, `!kick`, `!ban`, `!bots`, `!vote`, ...) and from the server machine.

**Why it is safe to run:**

- Four tiny binary patches: 28 bytes differ in total, all listed below with their offsets. Each patch touches only the exact known file. Its sha256 is checked before and after, and any other file is left alone.
- Every original is kept as `<file>.orig`. `install.py uninstall` puts them back.
- The add-on `TwoHoursCtl.u` carries its own source text. One command checks it was built from the `.uc` files in this repository, and the build is reproducible: build it yourself and you get the same sha256 as the release.
- Releases come with `SHA256SUMS` and a signed build provenance attestation from GitHub Actions.
- No Ubisoft files are in this repository. Plain Python 3.8+, standard library only. MIT license.

**Quick start** (needs Python 3.8 or newer, and the community XIII server 829 with its 2018 update):

```
sha256sum -c --ignore-missing SHA256SUMS     # the zip is intact
python3 install.py check   <XIII>            # what would change; changes nothing
python3 install.py install <XIII>            # patch, with .orig backups
```

XIII is a trademark of Ubisoft. This project is not affiliated with or endorsed by Ubisoft.

It is the code behind the XIII servers on [2hours.gg/xiii](https://2hours.gg/xiii). The full engineering write-up: [2hours.gg/guide/xiii-server-engineering](https://2hours.gg/guide/xiii-server-engineering).

## What this changes in your files

All in `<XIII>/System`. Sizes in bytes, hashes are sha256.

| File | Original sha256 | Patched sha256 | Bytes that differ | Why |
|---|---|---|---|---|
| `Engine.dll` (2433024) | `810b0c9600d06e104104f1dbf04d7989584b6d931d75e4a5ff933be598cdafdc` | `ff6183bfdbb908a0005a8dbecc7ce9fe7de11c92c8dc321780ca7fc1aa02e864` | 6 (in 7 rewritten) | A map change no longer crashes the server |
| `Engine.u` (547891) | `da24040b4fca0d3ec6dd92aa3b192d3ee82b25fa358170bbeded4d8432683234` | `019296366fe36805fbf2721cb09c365dd117d42ad05a6128f2444aa21a4af7f6` | 1 | Connected players are told to follow a map change |
| `XIIIMP.dll` (53248) | `a504c2e3ccbe5fbfeb92a8b33c1caa4a5490172a2c22e77a80dbbbd3fec04a9b` | `58ca02dc8036b2390b655b917c9cdcf847086cadddda0026b1a8a1e6fe4ef35e` | 20 (in 32 rewritten) | Bots no longer crash the server |
| `XIIIMP.u` (941397) | `6f5f07f13b5fadd61abfaf9622e8dd15f91675f36a6525d7bd14de715a2c3450` | `d4771d0002c4a324bfef6f8891958e2a3fb2c5d17b38294c2673493b69ac5e1e` | 1 | The dedicated server adds bots |
| `TwoHoursCtl.u` (39046) | new file | `07a89bdba247df37fbf439038be83175560f5c8aa4c072cd5d8bae91fda4cedf` | | The add-on: control port, chat commands, bots |
| `XIII.ini` | | | 1 line + 1 section | Loads the add-on, see [below](#what-install-writes-in-xiiiini) |

"Bytes that differ" is what `cmp -l original patched | wc -l` prints. Clients are not changed: players keep their own files.

---

## Install

### 1. Get the server

Use the community dedicated server from InsideXIII ([servers page](https://www.insidexiii.com/servers.php), "How to Host"):

- `xiii_server_829_0611.7z` (XIII Server Only, version 829, June 2011)
- `xiii_server_829_0611_update.7z` (the 2018 update files)

Extract the first one, then extract the update over it. The [binary reference](#binary-reference) lists their hashes.

### 2. Download and verify the release

Download `xiii-server-patch-v1.0.0.zip`, `SHA256SUMS` and `MD5SUMS` from the [latest release](https://github.com/2hours-gg/xiii-server-patch/releases/latest). Then check the zip is the one GitHub Actions built from this repository:

```
sha256sum -c --ignore-missing SHA256SUMS
gh attestation verify xiii-server-patch-v1.0.0.zip -R 2hours-gg/xiii-server-patch
```

`SHA256SUMS` also lists the add-on, `dist/TwoHoursCtl.u`. Run the same `sha256sum -c SHA256SUMS` inside the unzipped folder to check it, or rebuild it yourself and compare (see [Build it yourself](#build-it-yourself)). On macOS, use `shasum -a 256` in place of `sha256sum`.

On Windows, `certutil -hashfile xiii-server-patch-v1.0.0.zip SHA256` prints the hash to compare with `SHA256SUMS`. `gh` is the [GitHub CLI](https://cli.github.com/).

### 3. Check, then install

Unzip it, then point `install.py` at the server folder (the one holding `System/`). Use `python3` on Linux and `py` on Windows:

```
python3 install.py check   <XIII>
python3 install.py install <XIII>
```

- `check` names every file as `original`, `patched` or `unknown` and prints what `install` would change. It changes nothing.
- `install` refuses to change anything when one file is unknown (exit code 1) or missing (exit code 2).
- It patches the four files, copies `TwoHoursCtl.u` and edits `XIII.ini`. Originals are kept as `<file>.orig`.
- It ends by printing each file's sha256 next to the expected one.
- Running it twice is safe. `--dry-run` shows what it would do.
- `python3 install.py uninstall <XIII>` restores the originals and removes the add-on and its `XIII.ini` lines.

#### What install writes in XIII.ini

```ini
[Engine.GameEngine]
ServerActors=TwoHoursCtl.TwoHoursCtl      ; added after ServerActors=IpDrv.UdpServerQuery

[TwoHoursCtl.TwoHoursCtl]
CtlPort=7098
CtlKey=<32 random letters and digits, kept on a second install>
LabInject=False
AdminPassword=<a copy of [Engine.AccessControl] AdminPassword>
```

- The add-on only obeys datagrams from `127.0.0.1` that start with `CtlKey`. The port does not need to be opened in a firewall.
- `AdminPassword` lets the admin password work in any case (`LAB`, `Lab`, `lab`). The game keeps its own copy private to UnrealScript, so the add-on needs this one. Run `install` again after changing the admin password. Empty means the game's own case-sensitive check.
- `LabInject` is a test hook, see [Testing without a game client](#testing-without-a-game-client). Leave it off.
- The add-on also saves `BotTarget` and `BotSkill` there.

### 4. Start the server

Same as usual, from `<XIII>/System`. Under Wine on Linux, prefix it with `wine`:

```
UCC.exe server "DM_Amos.unr?MapName=FBI?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPGameInfo?GameIdx=0?Mutator=?ServerName=My_XIII_Server" -PORT=7777
```

- The URL must not contain spaces, or UCC fails with `Invalid URL`.
- **Server name in the InsideXIII list:** the master server lists the name from the URL option `?ServerName=` (no spaces). A `ServerName` in `XIII.ini` does not reach the list.
- **Admin password:** put it in `XIII.ini`, not in the URL. A live map change sends the whole travel URL to every connected player.
- **Join password:** `GamePassword` in `XIII.ini`, plus `?IsPrivate=Y` in the URL.

  ```ini
  [Engine.AccessControl]
  AdminPassword=pick-a-password
  GamePassword=pick-a-join-password
  ```

- The log should show `TwoHoursCtl: listening on UDP port 7098`.
- Then `TwoHoursCtl: chat commands on, BroadcastHandler Engine.BroadcastHandler -> TwoHoursCtl.TwoHoursChat`.

### 5. Change the map

Run these on the server machine:

```
python3 tools/xiii_ctl.py --key <CtlKey> status
python3 tools/xiii_ctl.py --key <CtlKey> players
python3 tools/xiii_ctl.py --key <CtlKey> travel 4 "CTF_Base.unr?MapName=USS-Patriot?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPCTFGameInfo?GameIdx=2?Mutator=?ServerName=My_XIII_Server"
python3 tools/xiii_ctl.py --key <CtlKey> say "new map in 10 seconds"
python3 tools/xiii_ctl.py --key <CtlKey> kick PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> ban PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> tell PlayerName "only this player sees this"
python3 tools/xiii_ctl.py --key <CtlKey> poll
python3 tools/xiii_ctl.py --key <CtlKey> bots 4 2
```

- `travel [<wait>] <url>`: with players connected, pass a wait in seconds (4 works). Each player gets the new map, then the menu map, and the switch runs once they all left, at most `<wait>` seconds later. They then join the new map and stay. Without a wait, a real client drops to its menu about 5 seconds after joining the new map (see [step 10](#10-players-followed-then-dropped-to-the-menu)).
- `players` answers one line: `ok humans=1 bots=3 max=12 map=CTF_Base`.
- `ban` is the game's own kick + IP ban. The ban is saved in `XIII.ini`.
- `tell` sends a private message to the player with that exact name (any case). A player with no pawn (dead, or on "Press Fire to begin") cannot see chat, so the line waits until they have one (60 seconds at most).
- `poll` returns the queued admin chat commands, see below.

A travel URL is a full session URL, like the one on the command line. Repeat every option you want to keep: the new map uses only the options in the new URL. Keep the admin password out of it. `MapName` is the map's display name without spaces.

Modes are the `Game` and `GameIdx` pair in the URL:

| Mode | `Game=` | `GameIdx=` | Map prefix |
|---|---|---|---|
| Deathmatch | `XIIIMP.XIIIMPGameInfo` | 0 | `DM_` |
| Team Deathmatch | `XIIIMP.XIIIMPTeamGameInfo` | 1 | `DM_` |
| Capture the Flag | `XIIIMP.XIIIMPCTFGameInfo` | 2 | `CTF_` |
| The Hunt | `XIIIMP.XIIIMPDuckGameInfo` | 3 | `DM_` |
| Sabotage | `XIIIMP.XIIIMPBombGame` | 4 | `SB_` |
| Power Up | `XIIIMP.XIIIMPTeamGameInfo` + `Mutator=XIIIMP.MarioMutator` | 5 | `DM_` |

**Limit: 2 live changes per server process.** The engine shuts the server down on its 4th map load (see [step 7](#7-the-third-change-ends-the-server-by-design)). The third change is therefore a restart. Run it as a travel anyway: players start connecting to the new map, the process exits, and a supervisor (systemd `Restart=always`, a shell loop) starts it again with the new map in the URL. A client keeps trying to connect for 60 seconds, so players land on the restarted server by themselves.

### Patching by hand

Each patch is also a standalone script with `check`, `apply` and `revert`. Exit codes: 0 done, 1 unknown file (left untouched), 2 file missing.

```
python3 patch/xiii_engine_patch.py       apply <XIII>/System
python3 patch/xiii_clienttravel_patch.py apply <XIII>/System
python3 patch/xiii_bot_patch.py          apply <XIII>/System
```

Or with a hex editor:

| File | File offset | Original | Patched |
|---|---|---|---|
| `Engine.dll` | `0x7C44D` | `E8 6E C3 FF FF` | `90 90 90 90 90` |
| `Engine.dll` | `0x7C5C6` | `EB 08` | `EB 3F` |
| `Engine.u` | `222008` (decimal) | `1B` | `13` |
| `XIIIMP.u` | `98449` (decimal) | `9A` | `9B` |
| `XIIIMP.dll` | `0x3A90` | `8B 44 24 04 A3 0C B3 D0 11 B8 01 00 00 00 C2 0C 00` + 15 x `90` | `8B 44 24 04 A3 0C B3 D0 11 83 7C 24 08 01 75 05 E8 0B 00 00 00 B8 01 00 00 00 C2 0C 00 90 90 90` |

Then copy `dist/TwoHoursCtl.u` into `<XIII>/System/` and add the `XIII.ini` lines above.

---

## Verify it yourself

- **The patches.** Compare a patched file with its `.orig`. Only the offsets in the table above may differ:

  ```
  cmp -l Engine.dll.orig Engine.dll
  ```

  The disassembly of each site is in [How it was found](#how-it-was-found) and in the header of each patch script.
- **The add-on.** `TwoHoursCtl.u` stores the source text of each class it was compiled from. This checks that text against `TwoHoursCtl/Classes/*.uc` and prints the package sha256:

  ```
  python3 build/build_ctl.py --verify dist/TwoHoursCtl.u
  ```

  The check covers each class body. UnrealScript stores the `defaultproperties` block apart from the text, so that block is not covered: it holds `LeaveDelay=0.5` and `LeaveURL="MapMenu.unr"` (in `TwoHoursCtl.uc`).
- **The release.** `sha256sum -c --ignore-missing SHA256SUMS` and `gh attestation verify` (above) tie the zip to a commit and a workflow run of this repository. [CI](.github/workflows/ci.yml) runs the tests and the add-on check on every push.
- **The tests.** They run without any game file (the real files are Ubisoft's), on synthetic files with patch tables built for them:

  ```
  python3 -m unittest discover -s tests
  ```

## Build it yourself

The server files cannot compile UnrealScript (see [step 4](#4-compiling-it-was-the-first-wall)), so the build uses the compiler from the community patch 1.4.2.1. You need Linux or macOS with Wine (a 32-bit prefix), 7-Zip (`7zz`), Python 3.8+, the server files from step 1 and the patch installer:

- `Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe` from [Opaquit's XIII Files](https://xiii.opaquit.com/downloads-2020/Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe), sha256 `4cd267d92353ffd99894d65794fc8f50b8a387476b2cac3dfd42d2f78866d0c7`

```
7zz x Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe -o/tmp/patch
python3 build/build_ctl.py --patch-exe Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe \
    --client-dir /tmp/patch/Dir --server-system <XIII>/System \
    --work /tmp/xiii-ctl-build --out /tmp/TwoHoursCtl.u
python3 build/build_ctl.py --verify /tmp/TwoHoursCtl.u
python3 build/build_ctl.py --compare dist/TwoHoursCtl.u /tmp/TwoHoursCtl.u
```

`WINEPREFIX` defaults to `/wine`. Set it to your 32-bit prefix.

**Reproducibility.** `UCC make` writes a random GUID into every package header: each `TwoHoursCtl.u` built so far has a different one, a version 4 UUID. `build_ctl.py` replaces it with one derived from the sources and the toolchain, so two builds of the same sources are byte-identical. The add-on is never sent to clients, so the GUID only needs to be stable.

- `--compare` exits 0 for identical files, 1 when only the GUID differs, 2 otherwise (and lists the bytes).
- `dist/TwoHoursCtl.u` is a build with the derived GUID, so a rebuild of the same sources with the same toolchain compares as identical (exit 0). It is also the build the 2hours.gg servers run.
- Proven on a Linux test server (Wine, 2026-11-25): two builds from clean `--work` folders both gave sha256 `07a89bdba247df37fbf439038be83175560f5c8aa4c072cd5d8bae91fda4cedf`. Two builds with `--keep-ucc-guid` compared as "identical except the package GUID" (exit 1).

CI cannot compile the add-on (no Wine, and the patch installer is not redistributed here). A release therefore ships the committed `dist/TwoHoursCtl.u`, and CI checks it with `--verify`.

---

## In-game admin commands

Admins can also run commands from the in-game chat. An admin is a player who joined with the admin password: `SWITCHLEVEL <ip>:7777?Password=<admin password>`.

### Why chat

In XIII, chat is the only text a player can send to the server:

- `Admin <command>` runs on the player's own PC.
- There is no `Mutate` command.
- `Say` and `TeamSay` are sent to the server. They end in `Level.Game.Broadcast` and `BroadcastTeam`, which pass the line to `Level.Game.BroadcastHandler`.

### What the add-on does

- `TwoHoursChat` (in the same package) extends `BroadcastHandler`. `TwoHoursCtl` puts it in place of the game's handler. It keeps the old handler's settings and checks again every second, so it is also in place after every map change.
- A chat line that starts with `!` is a command. It is never shown to other players.
- The command is queued as `<player name><TAB><flag><TAB><command without !>`. The flag is `a` for an admin (the game makes admins an `XIIIMP.XIIIAdmin`) and `p` for anyone else. The queue holds 16 lines.
- The poller decides who may run what. 2hours.gg lets everyone vote and read lists, and only admins change maps, kick or set bots. Others get a private `Admin only. Join with ?Password=<admin password>.`
- The admin password is checked in any case: `TwoHoursLogin`, a mutator in the same package, rewrites a `?Password=` that matches it in any case to the exact one before the game reads it. A wrong password is left alone.
- The add-on also queues `<TAB>s<TAB>#matchend` when a match ends, see [Map rotation](#map-rotation).
- Every other line is normal chat.

### Running the queued commands

The add-on only queues commands. Something on the server machine must read the queue with `poll`, run each command and answer with `tell`. 2hours.gg servers do this with a small Python program, about once a second.

A server without that program needs its own poller. To see what is queued:

```
python3 tools/xiii_ctl.py --key <CtlKey> poll
```

```
ok
Boss	a	map DM_Banque ctf
Ann	p	vote DM_Pal
	s	#matchend
```

`poll` empties the queue. A poller can then call `travel`, `kick`, `ban`, `tell` or `say` with the same key.

The commands 2hours.gg runs (any case, map names in any case):

| Command | What it does |
|---|---|
| `!map <map> [mode]` | Change map. Aliases: `!changelevel`, `!servertravel` |
| `!mode <mode> [map]` | Change mode |
| `!restart` | Reload the current map and mode |
| `!maps [mode]`, `!modes`, `!players` | Lists, sent privately |
| `!kick <name>`, `!ban <name>` | Kick, or kick and ban the IP |
| `!next`, `!rotation on\|off` | Skip to the next map, turn the rotation on or off |
| `!bots <n> [skill]` | Play with n bots (players do not count) |
| `!vote <map>`, `!vote <mode> <map>`, `!votes`, `!rotation` | Everyone: vote, show the votes, show the rotation |
| `!help` | The list above |

Everyone may use the `!vote` row, `!maps`, `!modes`, `!players` and `!help`; the rest is for admins. The answer is private. A map change is also announced to everyone with `say`. The 2-live-changes limit still applies: the third change restarts the server.

### Testing without a game client

`LabInject=True` in `[TwoHoursCtl.TwoHoursCtl]` enables two more commands, for test servers only (off by default):

- `inject admin|player <text>` spawns a temporary admin or player that "says" the text through `Level.Game.Broadcast`, then removes it.
- `labhold on|off` keeps a player controller with no client on the server. A match only starts when a player is present, so this lets a match (and bots) start without a game client.

These fake players have **no network connection**, so they do not test anything that is sent to players. A live map change passed every test with them and still crashed with the first real player. For that, use [`tools/xiii_netclient.py`](tools/xiii_netclient.py): it joins over UDP like a real client (the server logs `Join succeeded`), answers every packet so it stays connected, and can search what the server sends it:

```
python3 tools/xiii_netclient.py --server 127.0.0.1:7777 --name Tester --password <admin pw> \
    --seconds 60 --dump BristolSuites
```

`--follow DM_Banque,CTF_Base` makes it reconnect to each listed map after a travel, like a game client, and print how long each follow took.

---

## Map rotation

Stock XIII has no map rotation. When a match ends, `XIIIMPGameInfo` enters the state `MatchOver`. About 7 seconds later it goes back to `PendingMatch` and plays the **same** map again.

- `TwoHoursCtl` checks every second whether `Level.Game.IsInState('MatchOver')`. At each match end it queues `#matchend` once.
- The poller then changes map. 2hours.gg picks the most voted map, else the next map of the rotation: the maps of the current mode, in a fixed order, starting after the current map. It says `Next map: <map>` with `say`, waits 3 seconds, and sends `travel 4 <url>`.
- The usual limit applies: the 3rd change in one server process is a restart (fine at the end of a match).
- With rotation off, nothing happens and XIII plays the same map again.

## Map voting

Voting is chat only. Players do not need any extra file.

- `!vote <map>` votes for a map of the current mode. `!vote <mode> <map>` votes for another mode. A new vote replaces the old one.
- `!votes` shows the count and how many votes are needed.
- When more than half of the connected players vote for the same map, it changes at once. A vote can change the map at most once every 3 minutes; an admin's `!map` is not limited.
- At the end of a match the most voted map wins over the rotation.
- Votes reset on every map change. A player who leaves loses their vote.

The add-on only queues the votes. The counting is the poller's job (2hours.gg's is in Python).

## Bots

XIII has bots (`BotController` and its team, CTF, Sabotage and Hunt variants in `XIIIMP.u`), but stock XIII uses them only offline. On a dedicated server they never appear, and forcing them in crashes the server. [`patch/xiii_bot_patch.py`](patch/xiii_bot_patch.py) fixes both:

```
python3 patch/xiii_bot_patch.py check  <XIII>/System
python3 patch/xiii_bot_patch.py apply  <XIII>/System
```

1. **`XIIIMP.u`, 1 byte.** `XIIIMPGameInfo.StartMatch` adds `Level.BotNumber` bots only `if ( !Level.bLonePlayer && Level.NetMode == NM_StandAlone )`. The comparison is compiled bytecode: the int `==` operator, native 154, the byte `9A` at file offset 98449. It becomes native 155, `!=`. A dedicated server now adds the bots. Clients use their own `XIIIMP.u`, so nothing changes for them.
2. **`XIIIMP.dll`, 32 bytes.** With only the first fix, the first bot crashed the server:

   ```
   Critical: Failed to find function None in BotController DM_Amos.BotController2
   Critical: ABotController::execAddOrder <- UObject::ProcessEvent <- ... PendingMatch.Timer ...
   ```

   The bot code in `XIIIMP.dll` calls script functions by name (`AddDefaultOrders`, `LogOrderList`, ...). It fills those names in its exported function `XIIIMPInitNativePackage()`. The game client `XIII.exe` imports and calls it. `UCC.exe` never does, so on a server the names stay `None`. The patch makes the DLL's `DllMain` call `XIIIMPInitNativePackage` when the DLL loads, using the padding after `DllMain` (see the disassembly in the script). It is the same gap as the map change crash: code that assumed the game client.

Then `bots <n> <skill>` (or `BotTarget`/`BotSkill` in `[TwoHoursCtl.TwoHoursCtl]`) sets `Level.BotNumber`, `Level.IdealPlayerCount`, `Level.BotLevel` and `Level.BotTeam`:

- n is the number of bots. Players never count toward it. XIII has 8 bot slots, so 8 is the most. Skill goes from 0 to 3.
- Bots join at the next match start, which needs one human. A match starts with n bots, or fewer when the seats run out.
- One bot leaves every second while there are more than n bots, or while players plus bots are over the server's max players. So a player can always take a bot's seat. `bots 0` removes them all.
- The setting is saved in `XIII.ini`, so it survives map changes and restarts.

Tested on a test server: 3 bots played whole matches in all 6 modes, the next match started with them again, and the server stayed up for 10 minutes with no error. How they feel against real players is not tested yet.

---

## Binary reference

All hashes are sha256.

| File | Size (bytes) | sha256 | Notes |
|---|---|---|---|
| `xiii_server_829_0611.7z` | | `e5466270ac48c916faf66f207fc9afab3443c8256f990755cf220ec8fef06e07` | InsideXIII server package |
| `xiii_server_829_0611_update.7z` | | `a4fa488d66d156ac9c9ff3729c1d6a7a57732ad5661c7d28e239162aa932014b` | InsideXIII 2018 update |
| `System/Engine.dll` (original) | 2433024 | `810b0c9600d06e104104f1dbf04d7989584b6d931d75e4a5ff933be598cdafdc` | PE32 i386, image base `0x10300000`, linked 2003-10-21 18:26:41 UTC |
| `System/Engine.dll` (patched) | 2433024 | `ff6183bfdbb908a0005a8dbecc7ce9fe7de11c92c8dc321780ca7fc1aa02e864` | |
| `System/Engine.u` (original) | 547891 | `da24040b4fca0d3ec6dd92aa3b192d3ee82b25fa358170bbeded4d8432683234` | Server build, no source text |
| `System/Engine.u` (patched) | 547891 | `019296366fe36805fbf2721cb09c365dd117d42ad05a6128f2444aa21a4af7f6` | `ClientTravel` no longer static |
| `System/UCC.exe` | 61440 | `2909a98bd77ddf66b688f4d4f5ffaccfbaf269e72a7feb3e282c072b964f2bf9` | Unchanged |
| `System/XIIIMP.u` (original) | 941397 | `6f5f07f13b5fadd61abfaf9622e8dd15f91675f36a6525d7bd14de715a2c3450` | Server build, carries its UnrealScript source text |
| `System/XIIIMP.u` (patched) | 941397 | `d4771d0002c4a324bfef6f8891958e2a3fb2c5d17b38294c2673493b69ac5e1e` | |
| `System/XIIIMP.dll` (original) | 53248 | `a504c2e3ccbe5fbfeb92a8b33c1caa4a5490172a2c22e77a80dbbbd3fec04a9b` | Image base `0x11D00000` |
| `System/XIIIMP.dll` (patched) | 53248 | `58ca02dc8036b2390b655b917c9cdcf847086cadddda0026b1a8a1e6fe4ef35e` | |
| `dist/TwoHoursCtl.u` | 39046 | `07a89bdba247df37fbf439038be83175560f5c8aa4c072cd5d8bae91fda4cedf` | Built from `TwoHoursCtl/Classes/TwoHoursCtl.uc`, `TwoHoursChat.uc` and `TwoHoursLogin.uc` |
| `Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe` | | `4cd267d92353ffd99894d65794fc8f50b8a387476b2cac3dfd42d2f78866d0c7` | Build-time only (compiler toolchain) |

In `Engine.dll`, the `.text` section has the same file offset and virtual address (`0x1000`). So a file offset `X` in the code is the address `0x10300000 + X` in a debugger.

The `.uc` files mention paths and dates from the codebase they come from. They are kept byte-identical, because `dist/TwoHoursCtl.u` embeds their text and `--verify` compares it.

---

## How it was found

XIII runs on Unreal Engine 2. The engine is C++, compiled into DLLs (`Core.dll`, `Engine.dll`, ...). The gameplay is UnrealScript, compiled to bytecode in `.u` packages (`Engine.u`, `XIIIMP.u`, ...). Both layers matter here.

### 1. The goal

In Unreal, a server changes map with `ServerTravel`. Connected players get the new URL and load the new map with the server, without leaving. The goal was to trigger that from outside the game.

### 2. No way to send commands

Several routes were tried first, and none worked:

- **Remote console.** XIII has none. The web admin from other Unreal games (`UWeb`) is not shipped, and `[UWeb.WebServer] bEnabled=False`.
- **The server's console window.** Commands piped to stdin (`servertravel`, `switchlevel`, `say`, even `q`) do nothing. With a terminal, the text is echoed but UCC never reads it. The "Press 'q' to terminate" message is only a log line.
- **In-game admin.** Joining with `?Password=<admin password>` does make a player admin (`Administrator logged in`). But XIII's admin class (`XIIIAdmin` in `XIIIMP.u`) only sends `Kick` and `KickBan` to the server. `Admin ServerTravel <map>` runs on the player's own PC and changes nothing.

### 3. A server add-on of our own

Unreal servers load extra actors listed as `ServerActors=` in the ini. The engine spawns them on every map. One such actor can open a socket:

- `TwoHoursCtl` extends `IpDrv.UdpLink` and binds UDP port 7098.
- It obeys only datagrams from `127.0.0.1` that start with the right key. Everything else gets no reply.
- Request: `<key> <id> <command>`. Reply: `<id> <text>`.
- `travel <url>` first called `Level.ServerTravel(url, false)`. Steps 8 and 10 explain why it now does more.
- `status` reports the map, the game class, the URL (admin password masked) and each player's name, score and ping.
- `say` broadcasts a chat line. `kick` uses the game's own access control.
- It is not replicated (`RemoteRole=ROLE_None`), so players do not need it.

### 4. Compiling it was the first wall

`UCC make` compiles UnrealScript. Unlike later engines, XIII's compiler re-parses the **source text** of every class it loads, including the parents of the class being compiled.

- The server's `Core.u` and `Engine.u` have their source text stripped, so the server files cannot compile anything.
- The community client patch 1.4.2.1 (which every player installs) has a full `UCC.exe` and `Core.u`/`Engine.u` with their source. That became the toolchain.
- Even there, `IpDrv.u` is stripped, and `UdpLink` lives in `IpDrv.u`. So [`build/stubs/`](build/stubs/) holds declaration-only stand-ins (the native function signatures, no logic) for its 9 classes.
- [`build/upkg.py`](build/upkg.py), a small UE2 package writer, injects them into a **scratch copy** of `IpDrv.u` used only for the build.

The output is a small package (39 KB today) that refers to `Core`, `Engine` and `IpDrv` by name. On the server it links against the server's own packages. Nothing from the patch ends up in it.

### 5. The first map change crashed the server

With the add-on loaded, the first `travel` killed the server every time. The UCC log ended with a call stack. Two of them, one per fix:

```
Critical: ClearActorBindings <- ExitLevel <- UGameEngine::LoadMap <- ...
Critical: ExitLevel <- UGameEngine::LoadMap <- ...
```

`UGameEngine::LoadMap` unloads the old level (`ExitLevel`) before loading the new one. That code was written for a game client and assumes two things exist:

1. **A local player (`Client`)**, so it can clear its input bindings. A dedicated server has no local player, so `Client` is `NULL`.
2. **An Entry level (`GEntry`)**, the small level Unreal keeps loaded between maps. XIII loads it only when a local player exists, so on `UCC server` `GEntry` is also `NULL`.

### 6. Reading the machine code

There is no source for `Engine.dll`, so the fix is in the compiled x86 code. The DLL was disassembled around both crash sites with Capstone, and the import table gave names to the calls into `Core.dll`. No assembly was written. Two existing instructions were changed in place.

**Site 1, the unguarded `ClearActorBindings(Client)` call:**

```
1037c449: 8b404c        mov  eax, [eax+0x4c]
1037c44c: 50            push eax                    ; argument
1037c44d: e86ec3ffff    call 0x103787c0             ; ClearActorBindings -> reads NULL->+0x2c
1037c452: 8b4de8        mov  ecx, [ebp-0x18]
1037c455: 8b89b0010000  mov  ecx, [ecx+0x1b0]
1037c45b: 83c404        add  esp, 4                 ; caller pops the argument
```

`E8 rel32` is a 5-byte call. It is replaced by five 1-byte `NOP`s (`90`). The `push` before it stays. The caller removes that argument itself with `add esp, 4`, so the stack stays balanced. Nothing was bound on a server with no player, so there is nothing to clear.

**Site 2, the walk over `GEntry->Actors`:**

Before collecting garbage, `ExitLevel` marks every object (`SetFlags(0x400)` over `GObjObjects`). It then un-marks the Entry level's actors (`ClearFlags(0x400)`) so they survive, and calls `CollectGarbage`:

```
1037c5c4: 33f6          xor  esi, esi               ; i = 0
1037c5c6: eb08          jmp  0x1037c5d0             ; -> loop head        (patched: eb3f -> 0x1037c607)
1037c5d0: 8b4de8        mov  ecx, [ebp-0x18]
1037c5d3: 8b89b4010000  mov  ecx, [ecx+0x1b4]       ; GEntry (NULL on a server)
1037c5d9: 83c12c        add  ecx, 0x2c              ; &GEntry->Actors
1037c5dc: ff1530e04610  call [Core!FArray::Num]     ; crash: reads NULL+0x2c
1037c5e2: 3bf0          cmp  esi, eax
1037c5e4: 7d21          jge  0x1037c607
   ...                                              ; ClearFlags(0x400) on each actor
1037c605: ebc9          jmp  0x1037c5d0
1037c607: 6800000004    push 0x4000000
1037c60c: ff1520e74610  call [Core!UObject::CollectGarbage]
```

`EB xx` is a 2-byte short jump. Its target is the address of the next instruction plus the signed byte `xx`. The next instruction is at `0x1037c5c8`:

- `EB 08`: `0x1037c5c8 + 0x08 = 0x1037c5d0`, the loop head.
- `EB 3F`: `0x1037c5c8 + 0x3F = 0x1037c607`, the `CollectGarbage` call right after the loop.

The loop is skipped. That is correct on a server: there is no Entry level, so none of its actors need saving. The loop's own exit also lands on `0x1037c607`, so skipping it leaves the program in the same state as running it zero times.

### 7. The third change ends the server, by design

With both fixes, all 6 modes traveled cleanly, and the server answered queries throughout. On the next map, `status` answered about 0.5 s after the travel.

The **4th map load** in one process (the first map plus 3 travels) always ended the server with exit code 0 (`appRequestExit(0)`, then `Exit: Preparing to exit`), whatever the map or mode.

- In `UGameEngine::LoadMap`, a counter of map loads is checked.
- From the 4th load, the engine calls into a hidden module. That module is decompressed in memory and called through XOR-masked function pointers. When it returns 0, the engine exits.
- This looks like copy protection, so it is **deliberately not patched**.

The practical rule: 2 live changes per process, then a restart for the 3rd. Restarting a UE2 server takes a few seconds. Since step 10, the 3rd change also runs as a travel: the players' clients are already connecting to the new map when the process exits, and they keep retrying for 60 seconds, so they land on the restarted server without doing anything. A real client rejoined after a 3.5 second gap and stayed.

### 8. The first real player crashed it

Everything above was tested with nobody connected. The first map change with a real XIII client on the server crashed it:

```
ProcessServerTravel: DM_Banque.unr?...
Cast of TcpipConnection Transient.TcpipConnection2 to Viewport failed
History: UGameEngine::SetClientTravel <- UObject::ProcessEvent <- ...
```

`ProcessServerTravel` tells each connected player to follow the server to the new map:

```
foreach DynamicActors( class'PlayerController', P )
  if( NetConnection( P.Player)!=None )
    P.ClientTravel( URL, TRAVEL_Relative, bItems );
```

`ClientTravel` is in the replication list (`reliable if( Role==ROLE_Authority ... ) ClientTravel`), so the server should send it to the player. But XIII declares it

```
native static function event ClientTravel( string URL, ETravelType TravelType, bool bItems );
```

and the engine never sends a `static` function over the network. The native code ran on the server. There, the player object is a network connection (`TcpipConnection`), not a screen (`Viewport`), and the cast failed.

**Finding the bit.** A function's flags are stored as one 32-bit value in the package. Comparing functions whose declarations are known (the client patch's `Engine.u` carries its source text):

| Function | Declaration | Flags |
|---|---|---|
| `GetPlayerNetworkAddress`, `Spawn`, `Destroy` | `native(...) static final` | `0x00190100` |
| `Sleep` | `native(256) final latent` (not static) | `0x00110500` |
| `ClientTravel` | `native static event`, replicated | `0x001b3000` |

Every `static` function has `0x00080000`; `Sleep` does not. Clearing it on `ClientTravel` (file offset 222008, `1B` to `13`) makes the server send the call to each player. Players keep their own `Engine.u`, where the native runs locally as it must.

**Proof.** [`tools/xiii_netclient.py`](tools/xiii_netclient.py) is a minimal network client. It speaks the UDP protocol (packet ids, bunches, the text control channel `HELLO`, `CHALLENGE`, `LOGIN`, `WELCOME`, `JOIN`). The login challenge is answered like the game does (`UGameEngine::ChallengeResponse` in `Engine.dll`: `(c*237) ^ (c>>16) ^ (c<<16) ^ 0x93fe92ce`).

- Unpatched, with the client joined: the same crash.
- Patched: the server changed map and stayed up. The client received the call with the full URL, `DM_Pal.unr?MapName=BristolSuites?...`, about 1 second after the change. A new connection then joined the new map.
- The real client then followed, but dropped to its menu a few seconds later: see [step 10](#10-players-followed-then-dropped-to-the-menu).

### 9. Why nobody hit this before

XIII's own multiplayer never travels a dedicated server. At the end of a match the server waits for players and plays the same map again. The restart path that could travel (`GameInfo.RestartGame`) is not reached on a dedicated server, and `XIIIMPGameRules.HandleRestartGame` cancels it anyway. The broken code path only runs when something calls `ServerTravel` on a dedicated server, and nothing in the shipped game does.

Community servers work around the missing map change by restarting the process. [Opaquit's XIII Files](https://xiii.opaquit.com/2026b.php) describes its servers as restarting every hour with a random map. In February 2025, InsideXIII described map changes the same way: stop the server and start another, with no built-in map rotation. A 2021 community test server had F5 map voting, but its method is unknown and was never published. No public fix for in-process map changes was found: InsideXIII, Opaquit's XIII Files, ModDB and GitHub were all searched.

### 10. Players followed, then dropped to the menu

With the `Engine.u` fix (2026-11-18), a real XIII 1.4.2.1 client followed each map change: it connected to the new map about 0.45 s after the travel and the server logged `Join succeeded`. Then, 4 seconds later, the client closed the connection itself and showed its menu.

The first suspect was the URL. `ProcessServerTravel` sends the server's whole session URL, and its `?GS=` option made `XIIIMPGameInfo.Login` try to start a Ubi.com match for each follower (`Unable to join my own room`). The add-on now sends each player only the map (`CTF_Base.unr`, relative), as Unreal Tournament 2004 does, so a follower logs in with its own options like a fresh join. The message was gone. The drop was not.

To see the client side, the real `XIII.exe` ran headless under Wine on a test machine and joined a test server. The cause is in the client's `Engine.dll` (the patch 1.4.2.1 build):

- `ULevel::TickNetClient` (`0x10390fa0`): when the old server connection is closed and no failure is armed yet, it calls `ReportNetFailure` with a 5 second delay.
- `UGameEngine::Tick` (`0x1037e548`): when that delay runs out, it sends the client to the menu (`SetClientTravel("?failed")`). It never checks whether the new connection succeeded in the meantime.
- The flag is cleared only after the client itself loads a travel URL. And `TickNetClient` arms it again every frame while the old level still ticks with a closed connection.

So when the server's level switch closes the old connection, the client goes to the menu 5 seconds later, after it already joined the new map. Two other ideas failed on the real client: destroying the players' controllers before the switch (the switch still closes the connection), and holding the connections on the new map (the engine clears `NextURL` right after loading it).

The fix is in `TwoHoursCtl.TravelTo`, used when players are on and a wait is given:

1. Each player gets the map. The client starts a new connection and resends `HELLO` until the server accepts it. The server refuses it while the change is pending.
2. 0.5 s later, each player gets a second travel, to the menu map `MapMenu.unr`. The client loads the menu itself. That ends its old level and closes the old connection from its own side, so nothing is armed. The pending connection lives on.
3. Once no player is left, or the wait ran out, the server switches. The new map accepts the pending connections.

Players see a short loading screen, the menu for about a second, then the new map. With the real client, in 3 rounds:

| Change | Players left the old map | In game on the new map |
|---|---|---|
| `!map dm_banque` (DM to DM) | 0.55 s after the travel | 1.4 to 1.9 s after the chat command |
| `!mode ctf` (DM to CTF) | 0.55 s | 1.7 to 2.0 s |
| 3rd change (the process exits and restarts) | 0.55 s after a 4 s warning | 3.2 to 13.3 s after the exit |

Each case was still in game 60 seconds later, with no `?failed`.

### 11. The admin password was case-sensitive

`AccessControl.AdminLogin` compares the password with `==`. A client that joined with `?Password=LAB` on a server whose password is `lab` became a normal player, with no error. `XIIIMPGameInfo.Login` runs the mutators' `ModifyLogin` before it reads `?Password=`, so `TwoHoursLogin` (a mutator) rewrites a password that matches in any case to the exact one. With the real client: `LAB`, `Lab` and `lab` became admin; `wrong`, `WRONG` and no password stayed players. No password is ever logged.

The same client also showed that a private reply sent while a player has no pawn (dead, or on "Press Fire to begin") is never drawn. The add-on now holds such lines until the player has a pawn.

### 12. Bots count as bots

`bots <n>` first meant "fill the server to n players". It now means n bots: players never count toward n, and a player joining a full server takes a bot's seat (2026-11-23). `XIIIMPGameInfo.StartMatch` caps the bots at `Level.IdealPlayerCount` minus the humans, so the add-on sets `IdealPlayerCount` to the server's max players. With one client joined, `bots 3` gave 3 bots and the count survived a map change.

### 13. The server name in the list, and a join password

On a cloud server on 2026-11-25:

- The InsideXIII master server lists the name given by the URL option `?ServerName=` (no spaces). A `ServerName` in `XIII.ini` does not reach the list.
- A join password works with `[Engine.AccessControl] GamePassword` in `XIII.ini` and `?IsPrivate=Y` in the URL.

---

## Status

| | |
|---|---|
| Server travels across all 6 modes, server stays up | Tested |
| `status`, `players`, `say` sent, wrong key ignored | Tested |
| 4th-load exit, and the 3rd change as a travel into a restart | Tested |
| A map change with a real player connected | Tested (crashed before `xiii_clienttravel_patch.py`) |
| A real XIII client following a map change and staying in game | Tested (headless real client, 3 rounds) |
| Chat handler on every map, `poll`, `tell`, `ban` | Tested |
| A real admin's `!` commands reaching the server, private replies showing in XIII's chat | Tested |
| Admin password in any case | Tested |
| Match end detected, rotation to the next map, a vote that passed | Tested |
| Bots on the dedicated server in all 6 modes, `bots 0`, the count surviving a map change | Tested |
| `say` showing in a player's chat, `kick` removing a player | **Not yet tested** |
| Bots against real players, a bot leaving when a player joins a full server | **Not yet tested** |
| Two Wine builds of the add-on byte-identical (derived GUID), and identical apart from the GUID with `--keep-ucc-guid` | Tested |

Reports from real games are welcome as issues. Security reports: see [SECURITY.md](SECURITY.md).

## Repository layout

```
install.py                     check / install / uninstall everything
patch/binpatch.py              the sha256-gated byte patch used by all patches
patch/xiii_engine_patch.py     check / apply / revert the 7-byte Engine.dll patch
patch/xiii_clienttravel_patch.py  check / apply / revert the 1-byte Engine.u patch
patch/xiii_bot_patch.py        check / apply / revert the bot patches (XIIIMP.dll, XIIIMP.u)
TwoHoursCtl/Classes/           the add-on source (UnrealScript): TwoHoursCtl, TwoHoursChat, TwoHoursLogin
dist/TwoHoursCtl.u             the compiled add-on
tools/xiii_ctl.py              command-line client (status, players, travel, say, kick, ban, tell, poll, bots)
tools/xiii_netclient.py        minimal XIII network client for tests
build/build_ctl.py             compiles the add-on with UCC under Wine; --verify, --compare
build/upkg.py                  minimal UE2 package reader/writer
build/stubs/                   declaration-only IpDrv classes for the compiler
tests/                         unit tests, no game files needed
```

## Credits

- [InsideXIII](https://www.insidexiii.com/) keeps the dedicated server package and the master server alive.
- [Opaquit's XIII Files](https://xiii.opaquit.com/) hosts the community patch 1.4.2.1 by Arthur Muszynski. Its toolchain made compiling the add-on possible.
- XIII is a trademark of Ubisoft. This project is not affiliated with or endorsed by Ubisoft.

Hosted XIII servers with this built in: **[2hours.gg/xiii](https://2hours.gg/xiii)**. The full write-up: [2hours.gg/guide/xiii-server-engineering](https://2hours.gg/guide/xiii-server-engineering).

## License

MIT. See [LICENSE](LICENSE).
