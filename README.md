# xiii-server-mapchange

Live map and mode changes for the **XIII (2003) dedicated server**.

The stock XIII server cannot change map while it runs. It has no remote console. Typing into its window does nothing. If a map change is forced anyway, the server crashes. This repository fixes both problems:

| Part | What it is | Size |
|---|---|---|
| [`patch/xiii_engine_patch.py`](patch/xiii_engine_patch.py) | Patches `Engine.dll` so a map change no longer crashes the server | 7 bytes changed |
| [`TwoHoursCtl/`](TwoHoursCtl/Classes/) | A small server add-on in UnrealScript. It accepts local commands (`status`, `travel`, `say`, `kick`, `ban`, `tell`, `poll`) and catches admin chat commands such as `!map DM_Banque` | 19 KB `.u` |
| [`tools/xiii_ctl.py`](tools/xiii_ctl.py) | A command-line client for the add-on | |
| [`build/`](build/) | How the add-on is compiled, since the server files cannot compile UnrealScript | |

This is the code behind the web console of the XIII servers on **[2hours.gg/xiii](https://2hours.gg/xiii)**. There, the map and mode change from a browser while players stay connected.

No Ubisoft files are in this repository. The patcher edits a copy of `Engine.dll` that you already have.

---

## Install

### 1. Get the server

Use the community dedicated server from InsideXIII ([servers page](https://www.insidexiii.com/servers.php), "How to Host"):

- `xiii_server_829_0611.7z` (XIII Server Only, version 829, June 2011)
- `xiii_server_829_0611_update.7z` (the 2018 update files)

Extract the first one, then extract the update over it. Check the result against the [binary reference](#binary-reference) below.

### 2. Patch `Engine.dll`

You need Python 3.8 or newer. The patcher has no dependencies.

```
python3 patch/xiii_engine_patch.py check  <XIII>/System
python3 patch/xiii_engine_patch.py apply  <XIII>/System
```

- `apply` patches only the exact known file. It checks the sha256 before and after.
- The original is kept as `Engine.dll.orig`.
- Running `apply` twice is safe: the second run does nothing.
- `revert` puts the original bytes back.
- Any other `Engine.dll` is left untouched, and the script exits with code 1.

You can also patch it by hand with a hex editor:

| File offset | Original | Patched |
|---|---|---|
| `0x7C44D` | `E8 6E C3 FF FF` | `90 90 90 90 90` |
| `0x7C5C6` | `EB 08` | `EB 3F` |

### 3. Install the add-on

Copy [`dist/TwoHoursCtl.u`](dist/TwoHoursCtl.u) into `<XIII>/System/`.

Then edit `<XIII>/System/XIII.ini`. Add one line to `[Engine.GameEngine]`, next to the other `ServerActors` lines, and add a new section at the end:

```ini
[Engine.GameEngine]
ServerActors=TwoHoursCtl.TwoHoursCtl

[TwoHoursCtl.TwoHoursCtl]
CtlPort=7098
CtlKey=pick-a-long-random-key
```

- `CtlKey` must be letters and digits only (a space would split it), for example `k7f3q9x2m4w8z1`.
- `LabInject` (default `False`) is a test hook, see [In-game admin commands](#in-game-admin-commands). Leave it off.
- The add-on only listens when `CtlKey` is set.
- It only obeys datagrams from `127.0.0.1`, so the port does not need to be opened in a firewall.

### 4. Start the server

Same as usual, from `<XIII>/System`. Under Wine on Linux, prefix it with `wine`:

```
UCC.exe server "DM_Amos.unr?MapName=FBI?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPGameInfo?GameIdx=0?Mutator=?AdminPassword=secret" -PORT=7777
```

- The URL must not contain spaces, or UCC fails with `Invalid URL`.
- The log should show `TwoHoursCtl: listening on UDP port 7098`.
- Then `TwoHoursCtl: chat commands on, BroadcastHandler Engine.BroadcastHandler -> TwoHoursCtl.TwoHoursChat`.

### 5. Change the map

Run these on the server machine:

```
python3 tools/xiii_ctl.py --key <CtlKey> status
python3 tools/xiii_ctl.py --key <CtlKey> travel "CTF_Base.unr?MapName=USS-Patriot?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPCTFGameInfo?GameIdx=2?Mutator=?AdminPassword=secret"
python3 tools/xiii_ctl.py --key <CtlKey> say "new map in 10 seconds"
python3 tools/xiii_ctl.py --key <CtlKey> kick PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> ban PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> tell PlayerName "only this player sees this"
python3 tools/xiii_ctl.py --key <CtlKey> poll
```

- `ban` is the game's own kick + IP ban. The ban is saved in `XIII.ini`.
- `tell` sends a private message (`ClientMessage`) to the player with that exact name (any case).
- `poll` returns the queued admin chat commands, see below.

A travel URL is a full session URL, like the one on the command line. Repeat every option you want to keep, `AdminPassword` included: the new map uses only the options in the new URL. `MapName` is the map's display name without spaces.

Modes are the `Game` and `GameIdx` pair in the URL:

| Mode | `Game=` | `GameIdx=` | Map prefix |
|---|---|---|---|
| Deathmatch | `XIIIMP.XIIIMPGameInfo` | 0 | `DM_` |
| Team Deathmatch | `XIIIMP.XIIIMPTeamGameInfo` | 1 | `DM_` |
| Capture the Flag | `XIIIMP.XIIIMPCTFGameInfo` | 2 | `CTF_` |
| The Hunt | `XIIIMP.XIIIMPDuckGameInfo` | 3 | `DM_` |
| Sabotage | `XIIIMP.XIIIMPBombGame` | 4 | `SB_` |
| Power Up | `XIIIMP.XIIIMPTeamGameInfo` + `Mutator=XIIIMP.MarioMutator` | 5 | `DM_` |

**Limit: 2 live changes per server process.** The engine shuts the server down on its 4th map load (see [step 7](#7-the-third-change-ends-the-server-by-design)). A third change therefore needs a restart. Stop the server and start it again with the new map in the URL.

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
- From an admin (the game makes admins an `XIIIMP.XIIIAdmin`), the command is queued as `<player name><TAB><command without !>`. The queue holds 8 commands.
- From anyone else, the sender gets a private reply: `Admin only. Join with ?Password=<admin password>.`
- Every other line is normal chat.

### Running the queued commands

The add-on only queues commands. Something on the server machine must read the queue with `poll`, run each command and answer with `tell`. 2hours.gg servers do this with a small Python program, about once a second.

A server without that program needs its own poller. To see what is queued:

```
python3 tools/xiii_ctl.py --key <CtlKey> poll
```

```
ok
Boss	map DM_Banque ctf
Boss	players
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
| `!help` | The list above |

The admin gets the answer privately. A map change is also announced to everyone with `say`. The 2-live-changes limit still applies: the third change restarts the server.

### Testing without a game client

`LabInject=True` in `[TwoHoursCtl.TwoHoursCtl]` enables one more command: `inject admin|player <text>`. It spawns a temporary admin or player that "says" the text through `Level.Game.Broadcast`, then removes it. It is meant for test servers only and is off by default.

---

## Binary reference

All hashes are sha256.

| File | Size (bytes) | sha256 | Notes |
|---|---|---|---|
| `xiii_server_829_0611.7z` | | `e5466270ac48c916faf66f207fc9afab3443c8256f990755cf220ec8fef06e07` | InsideXIII server package |
| `xiii_server_829_0611_update.7z` | | `a4fa488d66d156ac9c9ff3729c1d6a7a57732ad5661c7d28e239162aa932014b` | InsideXIII 2018 update |
| `System/Engine.dll` (original) | 2433024 | `810b0c9600d06e104104f1dbf04d7989584b6d931d75e4a5ff933be598cdafdc` | PE32 i386, image base `0x10300000`, linked 2003-10-21 18:26:41 UTC |
| `System/Engine.dll` (patched) | 2433024 | `ff6183bfdbb908a0005a8dbecc7ce9fe7de11c92c8dc321780ca7fc1aa02e864` | |
| `System/UCC.exe` | 61440 | `2909a98bd77ddf66b688f4d4f5ffaccfbaf269e72a7feb3e282c072b964f2bf9` | Unchanged |
| `dist/TwoHoursCtl.u` | 19048 | `b8973532b6d315d40f78ca6b29634f8a7ffda9ef2ba500454bfe1a3ca1f76fd8` | Built from `TwoHoursCtl/Classes/TwoHoursCtl.uc` and `TwoHoursChat.uc` |
| `Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe` | | `4cd267d92353ffd99894d65794fc8f50b8a387476b2cac3dfd42d2f78866d0c7` | Build-time only (compiler toolchain) |

In `Engine.dll`, the `.text` section has the same file offset and virtual address (`0x1000`). So a file offset `X` in the code is the address `0x10300000 + X` in a debugger.

A `.u` package stores its own UnrealScript source text. This command checks that `dist/TwoHoursCtl.u` was built from the `.uc` files in this repository:

```
python3 build/build_ctl.py --verify dist/TwoHoursCtl.u
```

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
- `travel <url>` calls `Level.ServerTravel(url, false)`.
- `status` reports the map, the game class, the URL (admin password masked) and each player's name, score and ping.
- `say` broadcasts a chat line. `kick` uses the game's own access control.
- It is not replicated (`RemoteRole=ROLE_None`), so players do not need it.

### 4. Compiling it was the first wall

`UCC make` compiles UnrealScript. Unlike later engines, XIII's compiler re-parses the **source text** of every class it loads, including the parents of the class being compiled.

- The server's `Core.u` and `Engine.u` have their source text stripped, so the server files cannot compile anything.
- The community client patch 1.4.2.1 (which every player installs) has a full `UCC.exe` and `Core.u`/`Engine.u` with their source. That became the toolchain.
- Even there, `IpDrv.u` is stripped, and `UdpLink` lives in `IpDrv.u`. So [`build/stubs/`](build/stubs/) holds declaration-only stand-ins (the native function signatures, no logic) for its 9 classes.
- [`build/upkg.py`](build/upkg.py), a small UE2 package writer, injects them into a **scratch copy** of `IpDrv.u` used only for the build.

The output is a small package (19 KB) that refers to `Core`, `Engine` and `IpDrv` by name. On the server it links against the server's own packages. Nothing from the patch ends up in it.

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

The practical rule: 2 live changes per process, then a restart for the 3rd. Restarting a UE2 server takes a few seconds. Players rejoin the same address.

### 8. Why nobody hit this before

XIII's own multiplayer never travels a dedicated server. At the end of a match, `XIIIMPGameRules.HandleRestartGame` cancels the restart and sends players back to the menu. The broken code path only runs when something calls `ServerTravel` on a dedicated server, and nothing in the shipped game does.

Community servers work around the missing map change by restarting the process. [Opaquit's XIII Files](https://xiii.opaquit.com/2026b.php) describes its servers as restarting every hour with a random map. No public fix for in-process map changes was found: InsideXIII, Opaquit's XIII Files, ModDB and GitHub were all searched.

---

## Status

| | |
|---|---|
| Server travels across all 6 modes, server stays up | Tested |
| `status`, `say` sent, wrong key ignored | Tested |
| 4th-load exit and restart fallback | Tested |
| A real XIII client following a `ServerTravel` onto the new map | **Not yet tested** |
| `say` showing in a player's chat, `kick` removing a player | **Not yet tested** |
| Chat handler in place on every map, `poll`, `tell` (unknown name), `ban` | Tested |
| `!` commands from a temporary admin (`LabInject`) queued, run and answered by a poller | Tested |
| A real admin's `!` chat line reaching the server, private replies showing in XIII's chat | **Not yet tested** |

Reports from real games are welcome as issues.

## Repository layout

```
patch/xiii_engine_patch.py     check / apply / revert the 7-byte Engine.dll patch
TwoHoursCtl/Classes/           the add-on source (UnrealScript): TwoHoursCtl, TwoHoursChat
dist/TwoHoursCtl.u             the compiled add-on
tools/xiii_ctl.py              command-line client (status, travel, say, kick, ban, tell, poll)
build/build_ctl.py             compiles the add-on with UCC under Wine
build/upkg.py                  minimal UE2 package reader/writer
build/stubs/                   declaration-only IpDrv classes for the compiler
```

The header comments of the `.uc` files mention file paths from the 2hours.gg codebase. They are kept byte-identical so that `dist/TwoHoursCtl.u`, which embeds their source, still matches them.

To rebuild the add-on, you need Wine (32-bit prefix), 7-Zip and both the patch 1.4.2.1 installer and the server files:

```
7zz x Classic_XIII___Patch_by_Arthur_v1.4.2.1_2019-09-04.exe -o/tmp/patch
python3 build/build_ctl.py --client-dir /tmp/patch/Dir --server-system <XIII>/System \
    --work /tmp/xiii-ctl-build --out dist/TwoHoursCtl.u
```

## Credits

- [InsideXIII](https://www.insidexiii.com/) keeps the dedicated server package and the master server alive.
- [Opaquit's XIII Files](https://xiii.opaquit.com/) hosts the community patch 1.4.2.1 by Arthur Muszynski. Its toolchain made compiling the add-on possible.
- XIII is a trademark of Ubisoft. This project is not affiliated with or endorsed by Ubisoft.

Hosted XIII servers with this web console built in: **[2hours.gg/xiii](https://2hours.gg/xiii)**.

## License

MIT. See [LICENSE](LICENSE).
