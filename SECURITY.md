# Security

## Reporting a problem

Please report security problems privately, through a GitHub security advisory:
[Report a vulnerability](https://github.com/2hours-gg/xiii-server-patch/security/advisories/new).
Do not open a public issue for them.

A report helps most with the version or commit, the steps to reproduce it and what an attacker gains.
You should get a first answer within a week.

## What is in scope

- `install.py` and the patch scripts: anything that makes them write a file they should refuse, or write outside the server's `System` folder.
- The add-on `TwoHoursCtl.u`: anything that lets a datagram from another machine, or one without the `CtlKey`, run a command; anything that lets a player who is not an admin run an admin command.
- The release: a zip, checksum or attestation that does not match this repository.

## How the add-on is exposed

- It binds UDP `CtlPort` (7098 by default) and answers only datagrams from `127.0.0.1` that start with `CtlKey`. Anything else gets no reply.
- `CtlKey` is stored in plain text in `XIII.ini`, like the game's own passwords. Anyone who can run code on the server machine can use it.
- `LabInject=True` turns on test commands that fake players. Keep it `False` on a real server (`install.py` writes `False`).
- Chat commands are only queued by the add-on. Deciding who may run what is the job of the program that polls the queue.

## Verifying a release

See "Verify it yourself" in the [README](README.md#verify-it-yourself): `sha256sum -c SHA256SUMS`, `gh attestation verify <zip> -R 2hours-gg/xiii-server-patch`, and `python3 build/build_ctl.py --verify dist/TwoHoursCtl.u`.
