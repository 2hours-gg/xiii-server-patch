//=============================================================================
// TwoHoursChat: in-game admin chat commands for the XIII dedicated server.
//
// In XIII the only text a player can send to the server is chat: `Admin <cmd>`
// runs on the client and there is no Mutate. Say and TeamSay reach
// Level.Game.Broadcast / BroadcastTeam, which hand the line to
// Level.Game.BroadcastHandler. TwoHoursCtl swaps this class in as that handler.
//
// A chat line starting with "!" is a command and is never shown to anyone:
//   - from an admin (joined with ?Password=<admin password>, so the game made
//     them an XIIIMP.XIIIAdmin): queued as "<player name><TAB><text without !>"
//     for the box's bridge, which reads it with the `poll` control command,
//     runs it and answers with `tell` (games/xiii/boot/lib/chat_commands.py);
//   - from anyone else: a private "Admin only" reply.
// Every other line is chat as usual (BroadcastHandler).
//=============================================================================
class TwoHoursChat extends BroadcastHandler;

var string Queue[8];
var int QueueLen;
var string AdminOnlyText;
var string BusyText;

// S without leading spaces.
function string LeftTrim(string S)
{
	while (Left(S, 1) == " ")
		S = Mid(S, 1);
	return S;
}

// S with tabs and line breaks turned into spaces (they separate queue fields).
function string OneLine(string S)
{
	local int i;
	local string C, Out;

	for (i = 0; i < Len(S); i++)
	{
		C = Mid(S, i, 1);
		if (C == Chr(9) || C == Chr(10) || C == Chr(13))
			C = " ";
		Out = Out $ C;
	}
	return Out;
}

// True when Msg was a "!" command (handled here, never broadcast).
function bool HandleCommand(Actor Sender, string Msg)
{
	local PlayerController P;
	local string Cmd, Who;

	Cmd = LeftTrim(Msg);
	if (Left(Cmd, 1) != "!")
		return false;
	P = PlayerController(Sender);
	if (P == None)
		return false;
	if (!P.IsA('XIIIAdmin'))
	{
		P.ClientMessage(AdminOnlyText);
		return true;
	}
	if (P.PlayerReplicationInfo != None)
		Who = OneLine(P.PlayerReplicationInfo.PlayerName);
	Cmd = OneLine(Mid(Cmd, 1));
	if (QueueLen >= ArrayCount(Queue))
	{
		P.ClientMessage(BusyText);
		return true;
	}
	Queue[QueueLen] = Who $ Chr(9) $ Cmd;
	QueueLen++;
	Log("TwoHoursChat: admin command from" @ Who $ ": !" $ Cmd);
	return true;
}

// The queued commands as "\n<name>\t<command>" lines; empties the queue.
function string TakeQueue()
{
	local int i;
	local string S;

	for (i = 0; i < QueueLen; i++)
	{
		S = S $ Chr(10) $ Queue[i];
		Queue[i] = "";
	}
	QueueLen = 0;
	return S;
}

function Broadcast(Actor Sender, coerce string Msg, optional name Type)
{
	if (HandleCommand(Sender, Msg))
		return;
	Super.Broadcast(Sender, Msg, Type);
}

function BroadcastTeam(Controller Sender, coerce string Msg, optional name Type)
{
	if (HandleCommand(Sender, Msg))
		return;
	Super.BroadcastTeam(Sender, Msg, Type);
}

defaultproperties
{
	AdminOnlyText="Admin only. Join with ?Password=<admin password>."
	BusyText="Busy, try again in a second."
	RemoteRole=ROLE_None
}
