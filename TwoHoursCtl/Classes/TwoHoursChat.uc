//=============================================================================
// TwoHoursChat: in-game admin chat commands for the XIII dedicated server.
//
// In XIII the only text a player can send to the server is chat: `Admin <cmd>`
// runs on the client and there is no Mutate. Say and TeamSay reach
// Level.Game.Broadcast / BroadcastTeam, which hand the line to
// Level.Game.BroadcastHandler. TwoHoursCtl swaps this class in as that handler.
//
// A chat line starting with "!" is a command and is never shown to anyone.
// It is queued as "<player name><TAB><a|p><TAB><text without !>" for the
// box's bridge, which reads it with the `poll` control command, runs it and
// answers with `tell` (games/xiii/boot/lib/chat_commands.py). The flag is "a"
// for an admin (joined with ?Password=<admin password>, so the game made them
// an XIIIMP.XIIIAdmin) and "p" for anyone else: the bridge decides what each
// may run (any player can !vote, only an admin can !map).
// TwoHoursCtl also pushes events here ("<TAB>s<TAB>#matchend").
// Every other line is chat as usual (BroadcastHandler).
//=============================================================================
class TwoHoursChat extends BroadcastHandler;

var string Queue[16];
var int QueueLen;
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
	local string Cmd, Who, Flag;

	Cmd = LeftTrim(Msg);
	if (Left(Cmd, 1) != "!")
		return false;
	P = PlayerController(Sender);
	if (P == None)
		return false;
	if (P.PlayerReplicationInfo != None)
		Who = OneLine(P.PlayerReplicationInfo.PlayerName);
	if (P.IsA('XIIIAdmin'))
		Flag = "a";
	else
		Flag = "p";
	Cmd = OneLine(Mid(Cmd, 1));
	if (!Push(Who $ Chr(9) $ Flag $ Chr(9) $ Cmd))
	{
		P.ClientMessage(BusyText);
		return true;
	}
	Log("TwoHoursChat: command from" @ Who @ "(" $ Flag $ "): !" $ Cmd);
	return true;
}

// Add one queue line; false when the queue is full.
function bool Push(string Line)
{
	if (QueueLen >= ArrayCount(Queue))
		return false;
	Queue[QueueLen] = Line;
	QueueLen++;
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
	BusyText="Busy, try again in a second."
	RemoteRole=ROLE_None
}
