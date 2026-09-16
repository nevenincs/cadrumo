# Protect access to your data

Cadrumo encrypts each profile under its own data key. The profile passphrase
opens that key for normal login and daily work. An optional recovery code can
open the same key for one purpose only: setting a new passphrase when the old
one is forgotten. It never participates in login.

Use this guide to store the passphrase safely, decide whether to set up a
recovery code, change or reset the passphrase, run commands without an
interactive prompt, log out safely, and reset local state only as a last
resort.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md).
- Your current profile passphrase.

Use `--language en`, `es`, `ca`, or `hu` when you need a specific output
language.

## Store your passphrase safely

Your passphrase opens the key to your encrypted data. Treat it accordingly:

- Write the passphrase down and keep it offline, separate from your computer.
- Keep a second copy somewhere you can still reach after a disk failure.
- Never store it in a shared shell profile, a committed script, or a log.

If you lose the passphrase and have not set up a recovery code, the encrypted
data is permanently unreadable. The only way forward is a reset, which deletes
it.

Do not reset when only *some* records fail to open. Quarantine them first.
Quarantine moves each unreadable record, still encrypted, into an archive
inside the same storage and leaves every readable record untouched, so it
deletes nothing and can be previewed before it runs. See
[diagnose and repair your local setup](troubleshooting.md).

## Set up a recovery code (optional)

A recovery code is a second way to open the profile data key. It exists so a
forgotten passphrase can be replaced instead of costing the records. It is off
by default: a profile is created with its passphrase as its only door, and you
choose whether to add the code.

When you create a profile at a terminal, Cadrumo asks once whether to set up a
recovery code and defaults to no. The full-screen registration asks the same
question on its own screen with a `Skip for now` choice. Either way you can
decide later.

To enable it on the active profile:

```text
aeat config profile recovery enable
```

Cadrumo asks for the current passphrase, shows the code once on the terminal,
and asks you to type it back before anything is installed. The code looks like
`XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`; case, hyphens and spaces do not matter
when you type it. Write it down and keep it apart from your passphrase and
apart from the computer holding the data. Cadrumo keeps no copy and cannot show
it again.

Anyone holding the code can set a new passphrase for the profile, so treat it
as you would the passphrase itself. To check or remove it:

```text
aeat config profile recovery status
aeat config profile recovery disable
```

Disabling asks for the current passphrase. Enabling again issues a fresh code;
the old one stops working.

The code stays valid across ordinary passphrase changes. It does not travel
inside a backup archive: a restored profile always starts without recovery, and
the restore command says so. Enable it again after a restore if you want it.

### Reset a forgotten passphrase

If you have the recovery code and have forgotten the passphrase:

```text
aeat config passphrase reset PROFILE
```

Enter the recovery code, then the new passphrase twice. Nothing is echoed. The
existing key is re-wrapped under the new passphrase, so no record is
re-encrypted and the recovery code keeps working afterwards. A wrong code, a
profile without recovery, a new passphrase that is too short, or two copies
that do not match all refuse and leave the profile untouched.

To reset without an interactive prompt, send
`{"recovery_code": "...", "new_passphrase": "...",
"new_passphrase_confirmation": "..."}` through `--secrets-stdin` or
`--secrets-fd FD`.

### Enable recovery without a terminal

A recovery code can only be shown on a terminal, so a headless caller must take
delivery of it explicitly. Provide `--secrets-stdin` or `--secrets-fd FD` with
`{"passphrase": "..."}`, plus both `--recovery-handoff-fd WRITE_FD` and
`--recovery-verification-fd READ_FD`. Read exactly one object shaped as
`{"recovery_code":"..."}` from the first pipe, store the code securely, then
send the same strict object through the second pipe. Use distinct anonymous
pipes and distinct descriptor numbers; neither descriptor may be 0, 1, or 2 or
collide with `--secrets-fd`. The process closes each descriptor after its one
bounded operation. A missing half, malformed proof, mismatch, oversized
payload, descriptor collision, or I/O failure enrols nothing.

## Change your passphrase

Change the passphrase whenever you suspect it has been seen, or on whatever
schedule your own policy sets:

```{cli-sequence} protect-data-access-passphrase-change
```

Enter the current passphrase, then the new one twice. Nothing is echoed.

The change re-wraps the existing key rather than replacing it, so:

- No record is re-encrypted, and every existing record stays readable.
- A recovery code you set up earlier stays correct.

The command reports both facts back to you. If the current passphrase is wrong,
the new one is too short, or the two copies do not match, it refuses and leaves
the existing passphrase working.

To change the passphrase without an interactive prompt, pass the three values as
one JSON object through a leaf secret channel:

```{cli-sequence} protect-data-access-passphrase-change-stdin
```

Use `--secrets-stdin` when standard input is free. Use `--secrets-fd FD` with
the same object when another input owns standard input. Send
`{"current_passphrase": "...", "new_passphrase": "...",
"new_passphrase_confirmation": "..."}`. Never pass a passphrase as a
command-line argument: arguments are visible in the process list and in shell
history.

(run-without-a-passphrase-prompt)=
## Run without a passphrase prompt

Automation cannot answer an interactive passphrase prompt. Supply a bounded
UTF-8 JSON object through an explicit input channel. Do not put a profile
passphrase, recovery code, or certificate passphrase in an environment
variable or command-line argument. The CLI does not use
`CADRUMO_SECRET_PASSPHRASE` as a secret-input fallback.

There are two separate option pairs:

- Use leaf `--secrets-stdin` or `--secrets-fd FD` when the command itself owns
  the secret. The leaf commands and their exact objects are listed below.
- Use root `--profile-secrets-stdin` or `--profile-secrets-fd FD` before
  `config` when a profile-bound command needs to authenticate a selected
  profile after its persisted session cannot resume. Its object is
  `{"profile_passphrase": "..."}`.

The root options do not replace leaf options. For example, certificate-secret
storage may need a root profile passphrase and a certificate passphrase in the
same invocation. Supply them through two non-colliding channels.

### Supply a secret owned by a leaf command

Use the same two leaf flags on each scalar-secret command:

| Command | Strict JSON object |
| --- | --- |
| `aeat config login` | `{"passphrase": "..."}` |
| `aeat config profile create` | `{"passphrase": "...", "passphrase_confirmation": "..."}` |
| `aeat config passphrase change` | `{"current_passphrase": "...", "new_passphrase": "...", "new_passphrase_confirmation": "..."}` |
| `aeat config passphrase reset PROFILE` | `{"recovery_code": "...", "new_passphrase": "...", "new_passphrase_confirmation": "..."}` |
| `aeat config profile archive import` | `{"passphrase": "..."}` |
| `aeat config profile recovery enable` | `{"passphrase": "..."}` |
| `aeat config profile recovery disable` | `{"passphrase": "..."}` |
| `aeat config auth certificate secret set` | `{"certificate_passphrase": "..."}` |

Each object must contain exactly the fields shown. Profile creation through a
machine channel never asks about recovery; enable it afterwards with the
handoff pair described in [enable recovery without a
terminal](#enable-recovery-without-a-terminal). Duplicate, missing, extra,
oversized, malformed, or non-UTF-8 input is refused. The former restore field
`password` and certificate field `secret` are not accepted.

Inspect the current flags without supplying a secret:

```{cli-sequence} protect-data-access-machine-secret-help
:verify: Confirm every scalar-secret leaf exposes both explicit channels.
```

### Authenticate a profile for one command

Place a root option before the command path. Name the exact profile on the
target command when it accepts a profile target. For example:

```text
aeat --profile-secrets-stdin config profile view PROFILE
```

This source is used only after the exact profile is known, the command requires
a profile session, no matching live session exists, and persisted-session
resume has failed. It is refused without being read when the command does not
need profile authentication, when the exact target already has a live or
resumed session, or when the command is self-authenticating. Login, create,
restore, logout, passphrase change, passphrase reset, and recovery enable or
disable do not accept this root proof.

On a host without usable keychain persistence, successful root authentication
continues only the current process. The command emits a Notice that the
passphrase must be supplied again in the next process. Each new process repeats
the Argon2 password derivation; this deliberate cost is not cached in a weaker
credential or transferable bearer token.

### Keep two secret sources distinct

Choose sources before either is read:

- Do not select both stdin and a descriptor for the same option pair.
- Do not assign stdin to both the root and leaf scopes.
- Do not assign the same descriptor number to both scopes.
- Use root fd plus leaf stdin, root stdin plus leaf fd, or two different
  descriptors when one invocation needs both objects.

A selected source that does not apply to the resolved command or exact profile
is refused as unused. This protects scripts from sending a credential to the
wrong target after a command-line mistake.

### Pass an inherited descriptor safely

Use an anonymous pipe when standard input already carries another value. The
caller owns the descriptor's backing object and lifetime. Cadrumo performs one
bounded read and closes the descriptor locally after reading begins, including
on refusal. Descriptor `0` is allowed as a stdin-equivalent; descriptors `1`
and `2`, negative descriptors, closed descriptors, and unreadable descriptors
are refused.

On POSIX, start the process with the pipe's read descriptor in the child
process's `pass_fds` allowlist, then pass that number to `--secrets-fd` or
`--profile-secrets-fd`. On Windows, do not assume a numeric CRT descriptor is
inherited directly. Allowlist inheritable Windows HANDLEs and use the supported
bootstrap wrapper to convert them with `msvcrt.open_osfhandle`. Recovery
enrolment uses one writable handoff HANDLE and one readable verification
HANDLE:

```text
python -m cadrumo.entrypoints.cli._windows_profile_secret_bootstrap --profile-handle ROOT_HANDLE --secrets-handle LEAF_HANDLE -- config auth certificate secret set --name SOURCE
python -m cadrumo.entrypoints.cli._windows_profile_secret_bootstrap --recovery-handoff-handle WRITE_HANDLE --recovery-verification-handle READ_HANDLE -- config profile recovery enable --quiet --secrets-stdin
```

Omit `--profile-handle` or `--secrets-handle` when the invocation needs only
one scope. The wrapper inserts the matching canonical descriptor option; do not
also add it to the command tail. Prefer the stdin channel for a directly
launched portable command.

Cadrumo bounds the input, wipes mutable read buffers on a best-effort basis,
and releases secret-bearing references promptly. Python may create immutable
strings while decoding JSON and validating secret fields, so the application
does not claim guaranteed memory erasure. Never reuse the pipe, redirect it to
a regular file, or log the JSON object.

Interactive commands may prompt only on a verified terminal. A redirected or
non-interactive invocation without the required explicit channel is refused.

## Log out of the active profile

Run `aeat config logout` when you finish working with a profile. Logout
closes the active storage session, discards in-memory key material, disposes the
bucket engines, and keeps the profile selected for the next exact login:

```{cli-sequence} protect-data-access-logout
:verify: Confirm logout closes the active session without deleting the profile.
```

Nothing in the profile is deleted. Log in again with `aeat config login` to use
the selected profile, or name another exact profile when you return.

## Reset local state (last resort)

Export every profile you want to keep before continuing. Reset permanently deletes
every profile stored locally, related local authentication state, and the active
profile selection. It doesn't delete exports stored elsewhere. You can't undo
the reset. Deleting is also not a way to hide activity: any copies of your data
that left the machine (exports, filings, backups) are outside Cadrumo's control
and nothing in Cadrumo can retract them.

```{cli-sequence} protect-data-access-reset
```

1. Use `start` only when you intend to remove all local profiles. Confirm the
   reset explicitly. It checks retention requirements before deleting anything
   and refuses to start while another reset is incomplete.
2. Use the read-only `status` command to inspect the latest operation without
   changing local data. Provide an operation ID to inspect an exact operation.
   Status reports an incomplete, paused, or complete operation. Its output
   includes the operation ID and any pause reason.
3. Use `resume` after an interruption or pause. Confirm the reset again. It
   continues the same incomplete operation instead of creating another. Provide
   an operation ID to resume an exact operation. After deletion starts, resuming
   the reset doesn't restore deleted data.

If legal retention requirements pause the reset, stop if you must keep the
affected records. Override the pause only after reviewing and accepting the
legal retention consequence, and always provide a non-empty reason. If you
provide a reason without the override, the command refuses to continue.

See [Set up your taxpayer profile](profile-setup.md) for sealed archive
backup instructions.

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  see where encrypted custody ends and deliberate plaintext handoffs begin.
- [Set up your taxpayer profile](profile-setup.md) - create, export, and
  import profiles.
- [Diagnose and repair your local setup](troubleshooting.md) - quarantine
  unreadable records and fix storage or integrity problems without a reset.
- [CLI reference](../cli/index.rst) - full option reference.
