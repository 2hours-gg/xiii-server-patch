# xiii-server-mapchange

Live map and mode changes, map rotation, map voting and bots for the **XIII (2003) dedicated server**.

The stock XIII server cannot change map while it runs. It has no remote console. Typing into its window does nothing. If a map change is forced anyway, the server crashes. This repository fixes both problems:

| Part | What it is | Size |
|---|---|---|
| [`patch/xiii_engine_patch.py`](patch/xiii_engine_patch.py) | Patches `Engine.dll` so a map change no longer crashes the server | 7 bytes changed |
| [`patch/xiii_clienttravel_patch.py`](patch/xiii_clienttravel_patch.py) | Patches `Engine.u` so players connected during a map change are told to follow it, instead of crashing the server | 1 byte changed |
| [`patch/xiii_bot_patch.py`](patch/xiii_bot_patch.py) | Patches `XIIIMP.u` and `XIIIMP.dll` so the dedicated server can run bots | 1 byte + 32 bytes |
| [`TwoHoursCtl/`](TwoHoursCtl/Classes/) | A small server add-on in UnrealScript. It accepts local commands (`status`, `travel`, `say`, `kick`, `ban`, `tell`, `poll`, `bots`), catches chat commands such as `!map DM_Banque` or `!vote DM_Pal`, and reports the end of each match | 25 KB `.u` |
| [`tools/xiii_ctl.py`](tools/xiii_ctl.py) | A command-line client for the add-on | |
| [`tools/xiii_netclient.py`](tools/xiii_netclient.py) | A minimal XIII network client for tests: it joins a server over UDP like a player | |
| [`build/`](build/) | How the add-on is compiled, since the server files cannot compile UnrealScript | |

This is the code behind the web console of the XIII servers on **[2hours.gg/xiii](https://2hours.gg/xiii)**. There, the map and mode change from a browser while players stay connected.

No Ubisoft files are in this repository. The patchers edit copies of `Engine.dll`, `Engine.u`, `XIIIMP.u` and `XIIIMP.dll` that you already have.

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

Then patch `Engine.u`. **Without this, a map change crashes the server as soon as a real player is connected** (see [step 8](#8-the-first-real-player-crashed-it)):

```
python3 patch/xiii_clienttravel_patch.py apply <XIII>/System
```

By hand: file offset `222008` (decimal), `1B` -> `13`.

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
UCC.exe server "DM_Amos.unr?MapName=FBI?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPGameInfo?GameIdx=0?Mutator=" -PORT=7777
```

- The URL must not contain spaces, or UCC fails with `Invalid URL`.
- Put the admin password in `XIII.ini`, not in the URL:

  ```ini
  [Engine.AccessControl]
  AdminPassword=pick-a-password
  ```

  The game reads it on every map. A password in the URL (`?AdminPassword=`) also works, but a live map change sends the whole travel URL to every connected player.
- The log should show `TwoHoursCtl: listening on UDP port 7098`.
- Then `TwoHoursCtl: chat commands on, BroadcastHandler Engine.BroadcastHandler -> TwoHoursCtl.TwoHoursChat`.

### 5. Change the map

Run these on the server machine:

```
python3 tools/xiii_ctl.py --key <CtlKey> status
python3 tools/xiii_ctl.py --key <CtlKey> travel "CTF_Base.unr?MapName=USS-Patriot?NP=12?FF=0?FR=40?TI=20?Game=XIIIMP.XIIIMPCTFGameInfo?GameIdx=2?Mutator="
python3 tools/xiii_ctl.py --key <CtlKey> say "new map in 10 seconds"
python3 tools/xiii_ctl.py --key <CtlKey> kick PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> ban PlayerName
python3 tools/xiii_ctl.py --key <CtlKey> tell PlayerName "only this player sees this"
python3 tools/xiii_ctl.py --key <CtlKey> poll
```

- `ban` is the game's own kick + IP ban. The ban is saved in `XIII.ini`.
- `tell` sends a private message (`ClientMessage`) to the player with that exact name (any case).
- `poll` returns the queued admin chat commands, see below.

A travel URL is a full session URL, like the one on the command line. Repeat every option you want to keep: the new map uses only the options in the new URL. Keep the admin password out of it (it goes to every player); set it in `XIII.ini` as above. `MapName` is the map's display name without spaces.

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
- The command is queued as `<player name><TAB><flag><TAB><command without !>`. The flag is `a` for an admin (the game makes admins an `XIIIMP.XIIIAdmin`) and `p` for anyone else. The queue holds 16 lines.
- The poller decides who may run what. 2hours.gg lets everyone vote and read lists, and only admins change maps, kick or set bots. Others get a private `Admin only. Join with ?Password=<admin password>.`
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
| `!bots <n> [skill]` | Bots fill the server to n players |
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

---

## Map rotation

Stock XIII has no map rotation. When a match ends, `XIIIMPGameInfo` enters the state `MatchOver`. About 7 seconds later it goes back to `PendingMatch` and plays the **same** map again.

- `TwoHoursCtl` checks every second whether `Level.Game.IsInState('MatchOver')`. At each match end it queues `#matchend` once.
- The poller then changes map. 2hours.gg picks the most voted map, else the next map of the rotation: the maps of the current mode, in a fixed order, starting after the current map. It says `Next map: <map>` with `say`, waits 3 seconds, and sends `travel`.
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

- Bots fill the server to n players (XIII adds at most 8) at the next match start, which needs one human. Skill goes from 0 to 3.
- While players plus bots are more than n, one bot leaves every second. `bots 0` removes them all.
- The setting is saved in `XIII.ini`, so it survives map changes and restarts.

Tested on a lab server: 3 bots played whole matches in all 6 modes, the next match started with them again, and the server stayed up for 10 minutes with no error. How they feel against real players is not tested yet.

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
| `dist/TwoHoursCtl.u` | 25615 | `65dafa6384134f4e1b94aee878fdcb87481f0a6415f661b1e90e558d61609dfc` | Built from `TwoHoursCtl/Classes/TwoHoursCtl.uc` and `TwoHoursChat.uc` |
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

The output is a small package (25 KB) that refers to `Core`, `Engine` and `IpDrv` by name. On the server it links against the server's own packages. Nothing from the patch ends up in it.

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
- Whether the real game client loads the new map and stays on the server is not tested yet.

### 9. Why nobody hit this before

XIII's own multiplayer never travels a dedicated server. At the end of a match the server waits for players and plays the same map again. The restart path that could travel (`GameInfo.RestartGame`) is not reached on a dedicated server, and `XIIIMPGameRules.HandleRestartGame` cancels it anyway. The broken code path only runs when something calls `ServerTravel` on a dedicated server, and nothing in the shipped game does.

Community servers work around the missing map change by restarting the process. [Opaquit's XIII Files](https://xiii.opaquit.com/2026b.php) describes its servers as restarting every hour with a random map. In February 2025, Locke (InsideXIII) described map changes the same way: stop the server and start another, with no built-in map rotation. A 2021 community test server had F5 map voting, but its method is unknown and was never published. No public fix for in-process map changes was found: InsideXIII, Opaquit's XIII Files, ModDB and GitHub were all searched.

---

## Status

| | |
|---|---|
| Server travels across all 6 modes, server stays up | Tested |
| `status`, `say` sent, wrong key ignored | Tested |
| 4th-load exit and restart fallback | Tested |
| A map change with a real player connected | **Crashed** with the first real client; fixed by `xiii_clienttravel_patch.py` |
| The server sending the travel to a connected network client (`tools/xiii_netclient.py`) | Tested |
| A real XIII client following a `ServerTravel` onto the new map | **Not yet tested** |
| `say` showing in a player's chat, `kick` removing a player | **Not yet tested** |
| Chat handler in place on every map, `poll`, `tell` (unknown name), `ban` | Tested |
| `!` commands from a temporary admin (`LabInject`) queued, run and answered by a poller | Tested |
| A real admin's `!` chat line reaching the server, private replies showing in XIII's chat | **Not yet tested** |
| Match end detected, rotation to the next map, a vote that passed | Tested |
| Bots on the dedicated server in all 6 modes, `bots 0` | Tested |
| Bots against real players, a bot leaving when a player joins | **Not yet tested** |

Reports from real games are welcome as issues.

## Repository layout

```
patch/xiii_engine_patch.py     check / apply / revert the 7-byte Engine.dll patch
patch/xiii_bot_patch.py        check / apply / revert the bot patches (XIIIMP.u, XIIIMP.dll)
patch/xiii_clienttravel_patch.py  check / apply / revert the 1-byte Engine.u patch (live changes with players)
TwoHoursCtl/Classes/           the add-on source (UnrealScript): TwoHoursCtl, TwoHoursChat
dist/TwoHoursCtl.u             the compiled add-on
tools/xiii_ctl.py              command-line client (status, travel, say, kick, ban, tell, poll, bots)
tools/xiii_netclient.py        minimal XIII network client for tests
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
