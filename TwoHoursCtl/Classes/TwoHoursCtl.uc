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
	local string Rest, Key, Id, Cmd;

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
	else
		SendText(Addr, Id @ "error unknown command" @ Cmd);
}

defaultproperties
{
	CtlPort=7098
	RemoteRole=ROLE_None
}
