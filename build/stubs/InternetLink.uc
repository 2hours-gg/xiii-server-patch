//=============================================================================
// InternetLink: declaration-only stand-in for XIII's stripped IpDrv.InternetLink.
// Build-time only (build/build_ctl.py injects it into a scratch copy
// of IpDrv.u so UCC make can parse the superclass chain). Members and order
// match the compiled class in the shipped IpDrv.u; never shipped to a server.
//=============================================================================
class InternetLink extends InternetInfo
	native
	transient;

var enum ELinkMode
{
	MODE_Text,
	MODE_Line,
	MODE_Binary
} LinkMode;

var const int Socket;
var const int Port;
var const int RemoteSocket;
var private native const int PrivateResolveInfo;
var const int DataPending;

var enum EReceiveMode
{
	RMODE_Manual,
	RMODE_Event
} ReceiveMode;

struct IpAddr
{
	var int Addr;
	var int Port;
};

native function bool IsDataPending();
native function bool ParseURL(coerce string URL, out string Addr, out int Port, out string LevelName, out string EntryName);
native function Resolve(coerce string Domain);
native function int GetLastError();
native function string IpAddrToString(IpAddr Arg);
native function bool StringToIpAddr(string Str, out IpAddr Addr);
native function string Validate(string ValidationString, string GameName);
native function GetLocalIP(out IpAddr Arg);

event Resolved(IpAddr Addr);
event ResolveFailed();
