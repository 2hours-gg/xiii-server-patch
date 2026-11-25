//=============================================================================
// TwoHoursCtl: 2hours.gg box-side remote control for the XIII dedicated server.
//
// XIII has no RCON and no web admin, and its in-game admin can only kick
// (docs/xiii.md). This ServerActor gives the box a local control channel:
//
//   XIII.ini  [Engine.GameEngine]  ServerActors=TwoHoursCtl.TwoHoursCtl
//             [TwoHoursCtl.TwoHoursCtl]  CtlPort=7098  CtlKey=<secret>
//
// It binds UDP CtlPort and takes ONE command per datagram from the local
// bridge (games/xiii/boot/lib/console_rcon.py):
//
//   "<key> <id> <command> [args]"   ->   reply "<id> <text>"
//
//   status            ok + map, game class, url options, players
//   players           one line, counts only (the metrics reporter's player
//                     count): "ok humans=<n> bots=<n> max=<n> map=<map>";
//                     humans = CountHumans, bots = CountBots
//   travel [<wait>] <url>  server travel (TravelTo): players are sent the map
//                     only and reconnect to it; with players on and a wait
//                     (seconds), they leave through the menu first and the
//                     switch waits for them, at most <wait> (see TravelTo).
//                     "error a map change is already running" while one is
//   say <text>        chat line to every player
//   kick <name>       AccessControl.Kick (the in-game admin's kick)
//   ban <name>        AccessControl.KickBan (kick + IP ban in XIII.ini)
//   tell <name>\t<text>  private message to one player (ClientMessage);
//                     without a tab the name is the first word
//   poll              ok + the queued chat commands and events, one
//                     "<name>\t<a|p|s>\t<command>" line each (TwoHoursChat),
//                     then clears; "\ts\t#matchend" when a match ends
//   bots <n> <skill>  n bots (0 = none, at most 8), skill 0-3; players never
//                     count toward n (by design). Saved in
//                     XIII.ini, applied at every match start
//   labhold on|off    LAB ONLY (LabInject=True): keep a throwaway player
//                     controller on the server so a match starts without a
//                     client
//   inject admin|player <text>   LAB ONLY, refused unless LabInject=True:
//                     a throwaway controller of that kind "says" <text>, so a
//                     lab can drive the chat path without a game client
//
// It also swaps TwoHoursChat in as Level.Game.BroadcastHandler (checked every
// second, so the order of InitGame and ServerActors does not matter): admin
// chat lines starting with "!" become commands for the bridge.
//
// Only datagrams from 127.0.0.1 with the right key are obeyed; anything else
// is dropped without a reply. The actor is not replicated (clients never need
// this package) and is spawned again by the engine after every map change.
//
// Build: games/xiii/ctl/build_ctl.py (UCC make under Wine) compiles this into
// games/xiii/boot/lib/ctl_package.py, which the boot installs as
// System/TwoHoursCtl.u.
//=============================================================================
class TwoHoursCtl extends UdpLink config;

var config int CtlPort;
var config string CtlKey;
var config bool LabInject;
var config int BotTarget;
var config int BotSkill;
var TwoHoursChat Chat;
var bool bSawMatchOver;
var PlayerController LabHeld;
var config string AdminPassword;
var TwoHoursLogin LoginHook;
var PlayerController HeldFor[16];
var string HeldText[16];
var float HeldAt[16];
var config float LeaveDelay;
var config string LeaveURL;
var float LeaveAt;
var bool bWaitLeave;

function PostBeginPlay()
{
	local int Bound;

	Super.PostBeginPlay();
	if (Level.NetMode != NM_DedicatedServer)
		return;
	if (CtlKey == "")
	{
		Log("TwoHoursCtl: no CtlKey, control channel disabled");
		return;
	}
	LinkMode = MODE_Text;
	Bound = BindPort(CtlPort, false);
	if (Bound == 0)
	{
		Log("TwoHoursCtl: cannot bind UDP port" @ CtlPort);
		return;
	}
	Log("TwoHoursCtl: listening on UDP port" @ Bound);
	InstallChat();
	ApplyBots();
	SetTimer(1.0, true);
}

function Timer()
{
	InstallChat();
	WatchMatch();
	ApplyBots();
	TrimBots();
}

// Queue "#matchend" once when the game enters MatchOver (XIIIMPGameInfo
// CheckEndGame). Without us the game restarts the match on the same map.
function WatchMatch()
{
	if (Level.Game == None)
		return;
	if (Level.Game.IsInState('MatchOver'))
	{
		if (!bSawMatchOver)
		{
			bSawMatchOver = true;
			Log("TwoHoursCtl: match over");
			if (Chat != None)
				Chat.Push(Chr(9) $ "s" $ Chr(9) $ "#matchend");
		}
	}
	else
		bSawMatchOver = false;
}

// XIIIMPGameInfo.StartMatch adds Level.BotNumber bots (capped at
// Level.IdealPlayerCount minus the humans) when no bot exists yet. Stock XIII
// does that only offline (NM_StandAlone); lib/botpatch.py lets a dedicated
// server do it too.
// BotTarget is the number of BOTS, players never count toward it (by
// design): the cap is the server's seats, so a match starts with
// Min(BotTarget, MaxPlayers - humans) bots. LevelInfo has 8 bot slots
// (BotLevel[8]), so 8 is the most. Run every second too: Level.Game may not
// exist yet at PostBeginPlay.
function ApplyBots()
{
	local int i;

	BotTarget = Clamp(BotTarget, 0, 8);
	BotSkill = Clamp(BotSkill, 0, 3);
	Level.BotNumber = BotTarget;
	if (BotTarget > 0 && Level.Game != None)
		Level.IdealPlayerCount = Level.Game.MaxPlayers;
	for (i = 0; i < 8; i++)
	{
		Level.BotLevel[i] = BotSkill;
		Level.BotTeam[i] = i % 2;
	}
}

// Connected players with a PlayerReplicationInfo: exactly who `status`
// lists, so the `players` header matches the names (a demo recorder or a
// controller still joining has none).
function int CountHumans()
{
	local Controller C;
	local PlayerController P;
	local int N;

	for (C = Level.ControllerList; C != None; C = C.NextController)
	{
		P = PlayerController(C);
		if (P != None && P.PlayerReplicationInfo != None && NetConnection(P.Player) != None)
			N++;
	}
	return N;
}

function int CountBots()
{
	local Controller C;
	local int N;

	for (C = Level.ControllerList; C != None; C = C.NextController)
		if (C.IsA('BotController'))
			N++;
	return N;
}

// A bot leaves when there are more than BotTarget bots, or when a human needs
// its seat (humans plus bots over MaxPlayers; GameInfo.AtCapacity counts
// humans only, so a human still gets in). One per second.
function TrimBots()
{
	local Controller C;
	local int Bots;

	Bots = CountBots();
	if (Bots == 0)
		return;
	if (Bots <= BotTarget && (Level.Game == None || CountHumans() + Bots <= Level.Game.MaxPlayers))
		return;
	for (C = Level.ControllerList; C != None; C = C.NextController)
		if (C.IsA('BotController'))
			break;
	if (C == None)
		return;
	Log("TwoHoursCtl: bot leaves" @ C);
	if (C.Pawn != None)
		C.Pawn.Destroy();
	C.Destroy();
}

// Make TwoHoursChat the game's BroadcastHandler, keeping the old one's state.
function InstallChat()
{
	local BroadcastHandler Old;

	if (Level.Game == None)
		return;
	Old = Level.Game.BroadcastHandler;
	if (Chat != None && Old == Chat)
		return;
	if (Chat == None)
		Chat = Spawn(class'TwoHoursChat');
	if (Chat == None)
		return;
	if (Old != None)
	{
		Chat.bMuteSpectators = Old.bMuteSpectators;
		Chat.SentText = Old.SentText;
		Log("TwoHoursCtl: chat commands on, BroadcastHandler" @ Old.Class @ "->" @ Chat.Class);
		Old.Destroy();
	}
	else
		Log("TwoHoursCtl: chat commands on, BroadcastHandler" @ Chat.Class);
	Level.Game.BroadcastHandler = Chat;
}

function PlayerController FindPlayer(string Who)
{
	local Controller C;
	local PlayerController P;

	for (C = Level.ControllerList; C != None; C = C.NextController)
	{
		P = PlayerController(C);
		if (P != None && P.PlayerReplicationInfo != None
				&& P.PlayerReplicationInfo.PlayerName ~= Who)
			return P;
	}
	return None;
}

// LAB ONLY (LabInject=True): keep (or drop) a player controller with no
// client, so PendingMatch sees a player and starts a match.
function string LabHold(bool bOn)
{
	local class<PlayerController> PC;

	if (!bOn)
	{
		if (LabHeld != None)
			LabHeld.Destroy();
		LabHeld = None;
		return "ok";
	}
	if (LabHeld != None)
		return "ok";
	PC = class<PlayerController>(DynamicLoadObject("XIIIMP.XIIIMPPlayerController", class'Class'));
	if (PC == None)
		return "error no controller class";
	LabHeld = Spawn(PC);
	if (LabHeld == None)
		return "error spawn failed";
	if (LabHeld.PlayerReplicationInfo != None)
		LabHeld.PlayerReplicationInfo.PlayerName = "labhold";
	Log("TwoHoursCtl: LAB hold" @ LabHeld);
	return "ok";
}

// LAB ONLY (LabInject=True): a throwaway controller of class Kind says Msg.
function string Inject(string Kind, string Msg)
{
	local class<PlayerController> PC;
	local PlayerController P;

	if (Kind ~= "admin")
		PC = class<PlayerController>(DynamicLoadObject("XIIIMP.XIIIAdmin", class'Class'));
	else
		PC = class'PlayerController';
	if (PC == None)
		return "error no controller class";
	P = Spawn(PC);
	if (P == None)
		return "error spawn failed";
	if (P.PlayerReplicationInfo != None)
		P.PlayerReplicationInfo.PlayerName = "lab" $ Kind;
	Log("TwoHoursCtl: LAB inject as" @ P.Class $ ":" @ Msg);
	Level.Game.Broadcast(P, Msg, 'Say');
	P.Destroy();
	return "ok";
}

// The first space-separated word of S; S keeps the rest.
function string NextWord(out string S)
{
	local int i;
	local string W;

	i = InStr(S, " ");
	if (i < 0)
	{
		W = S;
		S = "";
	}
	else
	{
		W = Left(S, i);
		S = Mid(S, i + 1);
	}
	return W;
}

// Level.ServerTravel without GameInfo.ProcessServerTravel's ClientTravel of
// the WHOLE URL: each connected player gets only the map part (as UT2004's
// ProcessServerTravel does), relative, so their own options (name, password)
// stay and the server's session options (?Game= ?NP= ?GS= ...) stay on the
// server. ?GS= in a follower's URL made XIIIMP's Login start a Ubi.com match
// for them ("Unable to join my own room", real client, 2026-11-21). Then the
// same switch ServerTravel arms: NextURL, which the engine loads when
// NextSwitchCountdown runs out.
//
// With players on, a plain follow drops them: the client's Engine.dll arms a
// 5 s "connection failed" (UGameEngine::ReportNetFailure, from
// ULevel::TickNetClient) when its OLD connection closes while its old level
// still ticks, re-arms it every frame until the pending connection's map has
// loaded, and only a client-side travel clears it, so it fires after the
// client joined the new map and sends it to the menu (real client run
// headless, 2026-11-21). The server's switch is what closes that connection
// (a Destroy of the player's controller does not), and the new map accepts
// the pending connection in its first ticks, before any script can refuse it.
// So with players on and a Wait, nothing is left for the switch to close:
// LeaveDelay after the ClientTravel (each client has started its pending
// connection, which resends HELLO until accepted; NextURL refuses it here),
// every player gets a second ClientTravel to LeaveURL, the menu map: the
// client loads it, which ends its old level and closes the old connection
// from its side (nothing armed), while the pending connection lives on. Once
// no player is left (or Wait ran out) the switch runs and the new map
// accepts the pending connections.
function TravelTo(string URL, float Wait)
{
	local PlayerController P;
	local string ClientURL;
	local int Q, Humans;

	if (Level.NextURL != "")
		return;
	Q = InStr(URL, "?");
	if (Q > 0)
		ClientURL = Left(URL, Q);
	else
		ClientURL = URL;
	foreach DynamicActors(class'PlayerController', P)
		if (NetConnection(P.Player) != None)
		{
			P.ClientTravel(ClientURL, TRAVEL_Relative, false);
			Humans++;
		}
	Level.bNextItems = false;
	Level.NextURL = URL;
	if (Humans > 0 && Wait > 0)
	{
		Level.NextSwitchCountdown = Wait;
		LeaveAt = Level.TimeSeconds + LeaveDelay;
		Log("TwoHoursCtl: travel with" @ Humans @ "players: they leave through" @ LeaveURL @ "first (at most" @ Wait @ "s)");
	}
}

event Tick(float DeltaTime)
{
	local PlayerController P;

	if (LoginHook == None)
		InstallLogin();
	FlushHeld();
	if (LeaveAt > 0 && Level.TimeSeconds >= LeaveAt)
	{
		LeaveAt = 0;
		bWaitLeave = true;
		foreach DynamicActors(class'PlayerController', P)
			if (NetConnection(P.Player) != None)
				P.ClientTravel(LeaveURL, TRAVEL_Absolute, false);
	}
	else if (bWaitLeave && CountHumans() == 0)
	{
		bWaitLeave = false;
		if (Level.NextURL != "" && Level.NextSwitchCountdown > 0.1)
			Level.NextSwitchCountdown = 0.1;
		Log("TwoHoursCtl: every player left, switching");
	}
}

// TwoHoursLogin into the game's mutator chain, with the boot's copy of the
// admin password ([TwoHoursCtl.TwoHoursCtl] AdminPassword). From Tick: the
// BaseMutator exists after InitGame, and every login (a follower's too) comes
// after the level's first tick.
function InstallLogin()
{
	if (Level.NetMode != NM_DedicatedServer || Level.Game == None || Level.Game.BaseMutator == None)
		return;
	LoginHook = Spawn(class'TwoHoursLogin');
	if (LoginHook == None)
		return;
	LoginHook.AdminPassword = AdminPassword;
	Level.Game.BaseMutator.AddMutator(LoginHook);
	if (AdminPassword != "")
		Log("TwoHoursCtl: the admin password works in any case");
}

// A private chat line to P. A player with no pawn (the "Press Fire to begin"
// scoreboard after a join or a map change, or dead) does not see chat: the
// real client drew none of those replies (T3c, headless 2026-11-21). So the
// line waits (up to 16 lines, 60 s) until P has a pawn, in order.
function Tell(PlayerController P, string Text)
{
	local int i;

	if (P.Pawn != None && !HasHeld(P))
	{
		P.ClientMessage(Text);
		return;
	}
	for (i = 0; i < ArrayCount(HeldFor); i++)
		if (HeldFor[i] == None)
		{
			HeldFor[i] = P;
			HeldText[i] = Text;
			HeldAt[i] = Level.TimeSeconds;
			return;
		}
	P.ClientMessage(Text);
}

function bool HasHeld(PlayerController P)
{
	local int i;

	for (i = 0; i < ArrayCount(HeldFor); i++)
		if (HeldFor[i] == P)
			return true;
	return false;
}

// Held lines out, oldest first, once their player has a pawn; dropped after
// 60 s or when the player left.
function FlushHeld()
{
	local int i, Best;

	while (true)
	{
		Best = -1;
		for (i = 0; i < ArrayCount(HeldFor); i++)
		{
			if (HeldFor[i] == None)
				continue;
			if (HeldFor[i].bDeleteMe || Level.TimeSeconds - HeldAt[i] > 60)
			{
				HeldFor[i] = None;
				HeldText[i] = "";
				continue;
			}
			if (HeldFor[i].Pawn != None && (Best < 0 || HeldAt[i] < HeldAt[Best]))
				Best = i;
		}
		if (Best < 0)
			return;
		HeldFor[Best].ClientMessage(HeldText[Best]);
		HeldFor[Best] = None;
		HeldText[Best] = "";
	}
}

// The URL with the AdminPassword value masked.
function string Redact(string U)
{
	local int i, j;
	local string Rest;

	i = InStr(Caps(U), "?ADMINPASSWORD=");
	if (i < 0)
		return U;
	Rest = Mid(U, i + 15);
	j = InStr(Rest, "?");
	if (j < 0)
		return Left(U, i + 15) $ "***";
	return Left(U, i + 15) $ "***" $ Mid(Rest, j);
}

function string StatusText()
{
	local Controller C;
	local PlayerController P;
	local string S, Line;
	local int N;

	S = "ok";
	S = S $ Chr(10) $ "map=" $ Left(string(Level), InStr(string(Level), "."));
	S = S $ Chr(10) $ "game=" $ string(Level.Game.Class);
	S = S $ Chr(10) $ "url=" $ Redact(Level.GetLocalURL());
	S = S $ Chr(10) $ "max=" $ Level.Game.MaxPlayers;
	S = S $ Chr(10) $ "state=" $ Level.Game.GetStateName();
	S = S $ Chr(10) $ "bots=" $ CountBots();
	S = S $ Chr(10) $ "bottarget=" $ BotTarget;
	S = S $ Chr(10) $ "botskill=" $ BotSkill;
	for (C = Level.ControllerList; C != None; C = C.NextController)
	{
		P = PlayerController(C);
		if (P == None || P.PlayerReplicationInfo == None || NetConnection(P.Player) == None)
			continue;
		N++;
		Line = Chr(10) $ "player=" $ P.PlayerReplicationInfo.PlayerName;
		Line = Line $ Chr(9) $ int(P.PlayerReplicationInfo.Score);
		Line = Line $ Chr(9) $ P.PlayerReplicationInfo.Ping;
		S = S $ Line;
	}
	S = S $ Chr(10) $ "players=" $ N;
	return S;
}

// Humans and bots apart (bots are not players), no names, so the
// reply stays one short line whatever the players are called.
function string PlayersText()
{
	local string S;

	S = "ok humans=" $ CountHumans();
	S = S @ "bots=" $ CountBots();
	S = S @ "max=" $ Level.Game.MaxPlayers;
	S = S @ "map=" $ Left(string(Level), InStr(string(Level), "."));
	return S;
}

event ReceivedText(IpAddr Addr, string Text)
{
	local string Rest, Key, Id, Cmd, Who;
	local PlayerController P;
	local int i;
	local float Wait;

	// Local bridge only: a datagram from anywhere else gets no reply at all.
	if (Left(IpAddrToString(Addr), 10) != "127.0.0.1:")
		return;
	Rest = Text;
	if (Right(Rest, 1) == Chr(10))
		Rest = Left(Rest, Len(Rest) - 1);
	Key = NextWord(Rest);
	if (Key != CtlKey)
	{
		Log("TwoHoursCtl: bad key from" @ IpAddrToString(Addr));
		return;
	}
	Id = NextWord(Rest);
	Cmd = Caps(NextWord(Rest));

	if (Cmd == "STATUS")
		SendText(Addr, Id @ StatusText());
	else if (Cmd == "PLAYERS")
		SendText(Addr, Id @ PlayersText());
	else if (Cmd == "TRAVEL")
	{
		Wait = 0;
		if (Left(Rest, 1) >= "0" && Left(Rest, 1) <= "9")
			Wait = float(NextWord(Rest));
		if (Rest == "")
		{
			SendText(Addr, Id @ "error travel needs a URL");
			return;
		}
		if (Level.NextURL != "")
		{
			SendText(Addr, Id @ "error a map change is already running");
			return;
		}
		Log("TwoHoursCtl: ServerTravel" @ Redact(Rest));
		SendText(Addr, Id @ "ok");
		TravelTo(Rest, Wait);
	}
	else if (Cmd == "SAY")
	{
		if (Rest != "")
			Level.Game.Broadcast(self, Rest, 'Say');
		SendText(Addr, Id @ "ok");
	}
	else if (Cmd == "KICK")
	{
		if (Level.Game.AccessControl != None && Rest != "")
			Level.Game.AccessControl.Kick(Rest);
		SendText(Addr, Id @ "ok");
	}
	else if (Cmd == "BAN")
	{
		if (Level.Game.AccessControl != None && Rest != "")
			Level.Game.AccessControl.KickBan(Rest);
		SendText(Addr, Id @ "ok");
	}
	else if (Cmd == "TELL")
	{
		i = InStr(Rest, Chr(9));
		if (i >= 0)
		{
			Who = Left(Rest, i);
			Rest = Mid(Rest, i + 1);
		}
		else
			Who = NextWord(Rest);
		P = FindPlayer(Who);
		if (P == None || Rest == "")
		{
			SendText(Addr, Id @ "error no player" @ Who);
			return;
		}
		Tell(P, Rest);
		SendText(Addr, Id @ "ok");
	}
	else if (Cmd == "POLL")
	{
		if (Chat == None)
			SendText(Addr, Id @ "ok");
		else
			SendText(Addr, Id @ "ok" $ Chat.TakeQueue());
	}
	else if (Cmd == "BOTS")
	{
		BotTarget = int(NextWord(Rest));
		if (Rest != "")
			BotSkill = int(NextWord(Rest));
		ApplyBots();
		SaveConfig();
		TrimBots();
		Log("TwoHoursCtl: bots" @ BotTarget @ "skill" @ BotSkill);
		SendText(Addr, Id @ "ok");
	}
	else if (Cmd == "LABHOLD")
	{
		if (!LabInject)
		{
			SendText(Addr, Id @ "error labhold is off (lab only)");
			return;
		}
		SendText(Addr, Id @ LabHold(Rest ~= "on"));
	}
	else if (Cmd == "INJECT")
	{
		if (!LabInject)
		{
			SendText(Addr, Id @ "error inject is off (lab only)");
			return;
		}
		Who = NextWord(Rest);
		SendText(Addr, Id @ Inject(Who, Rest));
	}
	else
		SendText(Addr, Id @ "error unknown command" @ Cmd);
}

defaultproperties
{
	CtlPort=7098
	LeaveDelay=0.5
	LeaveURL="MapMenu.unr"
	RemoteRole=ROLE_None
}
