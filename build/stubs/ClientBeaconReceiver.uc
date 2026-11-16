//=============================================================================
// ClientBeaconReceiver: empty stand-in for XIII's stripped IpDrv.ClientBeaconReceiver (a script class).
// Build-time only, see InternetLink.uc: UCC make re-parses every class of a
// loaded package, so each needs SOME source. Nothing here reaches a server.
//=============================================================================
class ClientBeaconReceiver extends UdpBeacon;
