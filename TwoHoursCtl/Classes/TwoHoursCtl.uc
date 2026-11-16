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
//   travel <url>      Level.ServerTravel(url, false): players stay connected
//   say <text>        chat line to every player
//   kick <name>       AccessControl.Kick (the in-game admin's kick)
//   ban <name>        AccessControl.KickBan (kick + IP ban in XIII.ini)
//   tell <name>\t<text>  private message to one player (ClientMessage);
//                     without a tab the name is the first word
//   poll              ok + the queued chat commands and events, one
//                     "<name>\t<a|p|s>\t<command>" line each (TwoHoursChat),
//                     then clears; "\ts\t#matchend" when a match ends
//   bots <n> <skill>  bots fill the server to n players (0 = none), skill 0-3;
//                     saved in XIII.ini, applied at every match start
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
function ApplyBots()
{
	local int i;

	BotTarget = Clamp(BotTarget, 0, 16);
	BotSkill = Clamp(BotSkill, 0, 3);
	Level.BotNumber = Min(BotTarget, 8);
	if (BotTarget > 0)
		Level.IdealPlayerCount = BotTarget;
	for (i = 0; i < 8; i++)
	{
		Level.BotLevel[i] = BotSkill;
		Level.BotTeam[i] = i % 2;
	}
}

function int CountHumans()
{
	local Controller C;
	local int N;

	for (C = Level.ControllerList; C != None; C = C.NextController)
		if (PlayerController(C) != None && NetConnection(PlayerController(C).Player) != None)
			N++;
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

// Bots leave as humans join: never more than BotTarget players in total.
function TrimBots()
{
	local Controller C;

	if (CountBots() == 0 || CountHumans() + CountBots() <= BotTarget)
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

event ReceivedText(IpAddr Addr, string Text)
{
	local string Rest, Key, Id, Cmd, Who;
	local PlayerController P;
	local int i;

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
	else if (Cmd == "TRAVEL")
	{
		if (Rest == "")
		{
			SendText(Addr, Id @ "error travel needs a URL");
			return;
		}
		Log("TwoHoursCtl: ServerTravel" @ Redact(Rest));
		SendText(Addr, Id @ "ok");
		Level.ServerTravel(Rest, false);
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
		P.ClientMessage(Rest);
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
		Log("TwoHoursCtl: bots fill to" @ BotTarget @ "skill" @ BotSkill);
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
	RemoteRole=ROLE_None
}
