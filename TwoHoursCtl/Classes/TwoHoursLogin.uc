//=============================================================================
// TwoHoursLogin: the XIII admin password works in any case.
//
// XIII's AccessControl.AdminLogin compares ?Password= with AdminPassword
// using == (case-sensitive): ?Password=LAB joined as a plain player on a
// server whose password is "lab" (owner, real client, 2026-11-21).
// XIIIMPGameInfo.Login runs BaseMutator.ModifyLogin BEFORE it reads
// ?Password=, so this mutator (put in the chain by TwoHoursCtl) rewrites a
// password that matches in any case to the exact one. A wrong password (any
// case) is left alone, and an empty AdminPassword matches nothing, as before.
// No password is ever logged.
//=============================================================================
class TwoHoursLogin extends Mutator;

var string AdminPassword;

function ModifyLogin(out string Portal, out string Options)
{
	local string Given;

	if (AdminPassword != "")
	{
		Given = Level.Game.ParseOption(Options, "Password");
		if (Given != "" && Given != AdminPassword && Caps(Given) == Caps(AdminPassword))
			Options = WithPassword(Options, AdminPassword);
	}
	Super.ModifyLogin(Portal, Options);
}

// Options ("?Key=Value?...") with every Password= value replaced by P.
function string WithPassword(string Options, string P)
{
	local string Rest, Pair, Out;

	Rest = Options;
	while (Level.Game.GrabOption(Rest, Pair))
	{
		if (Left(Pair, 9) ~= "Password=")
			Pair = "Password=" $ P;
		Out = Out $ "?" $ Pair;
	}
	return Out;
}

defaultproperties
{
}
