# Disposable Windows guest

This Docker container runs a full Windows 11 Enterprise LTSC guest under QEMU/KVM;
it is not a Windows process container. It installs the normal OS and virtualization
drivers, with no Python, pytest, SDK, compiler, or product test dependencies.

The pinned Linux/amd64 image is from [dockur/windows](https://github.com/dockur/windows).
Its [configuration reference](https://github.com/dockur/windows/blob/master/docs/environment.md)
documents `UUID`, KVM, LTSC selection, qcow2, and OEM commands. The pinned image resets
`SM_BIOS` internally, so the explicit hardware template uses its final `ARGUMENTS`
option instead. The OEM script enables
Windows' built-in HTTPS PowerShell remoting, disables the HTTP listener and basic
authentication, and records the actual guest hardware identity in `C:\OEM\guest-ready.json`.
Only the dedicated disposable administrator receives a full remote token.
The initial campaigns use that same split-token account: user scope runs an
interactive task with `LeastPrivilege`, machine scope with `Highest`. Native
token evidence must confirm the actual elevation. A separate standard account
is an additional proof, not evidence established by this fixture's first campaign.

Before starting, verify `/dev/kvm` can be opened and `KVM_CREATE_VM` succeeds inside
an isolated container. Merely finding the device is insufficient. Do not restart
Docker, WSL, host services, or unrelated containers to run this fixture.

Set `CADRUMO_WINDOWS_GUEST_STORAGE` and `CADRUMO_WINDOWS_GUEST_EXCHANGE` to dedicated
directories under `build/runtime-lifecycle-windows-guest`, and provide a fresh
`CADRUMO_WINDOWS_GUEST_UUID`. Generate a strong random guest password into
`CADRUMO_WINDOWS_GUEST_PASSWORD` for the launching process. Persist it only with
Windows DPAPI in the private build directory, never in `.env`, source, command
arguments, logs, or printed Compose configuration.

Create a dedicated Docker Linux volume and set `CADRUMO_WINDOWS_GUEST_VOLUME`
to its exact name. Label it `cadrumo.fixture=runtime-lifecycle-windows-guest`
and `cadrumo.guest.uuid` with the selected UUID; inspect those labels before
reuse or removal. This external volume owns `/storage`; the host storage
directory holds the read-only ISO and diagnostic artifacts. Linux storage
avoids slow guest disk flushes through Windows bind mounts. Check free space
on Docker Desktop's host drive separately from the build artifact drive.

Place the complete official Windows 11 Enterprise LTSC evaluation media in the
storage directory as `custom.iso`, retaining its Microsoft URL and SHA-256 in
the build artifacts. Verify the installation WIM with the pinned image's
`wimlib-imagex verify` before booting; file size and a locally calculated hash
alone do not establish intact media. The read-only `/custom.iso` mount avoids restarting slow
downloads through Docker's proxy; the container detects its normal LTSC edition.

Run `docker compose -f dev/runtime_lifecycle/windows-guest/compose.yaml up -d`.
The viewer, RDP and WinRM HTTPS ports bind only to host loopback, respectively
18006, 13389 and 15986. No host credentials or checkout are shared: `/shared`
contains only the explicitly copied package, command fixtures and result artifacts.
The disk is thin 64 GiB qcow2, meeting the normal OS's
[minimum storage requirement](https://learn.microsoft.com/windows/whats-new/windows-11-requirements),
with 2 guest CPUs and 4 GiB guest RAM. The container uses
at most 2 CPUs and 6 GiB RAM, and does not restart automatically.

Use HTTPS PowerShell remoting for command-only setup and execution. Validate the
guest certificate and actual CIM UUID before running the installed-guest guard;
the guard's selected ID must equal that actual UUID. A genuine interactive logon
must be verified separately for user-login and credential-receipt evidence.
The explicitly configured SMBIOS template is manufacturer `QEMU`, model
`CadrumoRuntimeGuest`, version `1.0`; verify those actual CIM values after boot.
Booting the guest alone does not pass lifecycle or installed-service acceptance.

The pinned unattended template sets `EnableLUA=0`. Restore normal Windows UAC
(`EnableLUA=1`) and reboot before comparing this administrator's `LeastPrivilege`
and `Highest` tasks; verify their actual tokens through the existing native guard.
Check guest UTC against real host UTC and query native licensing status. Correct
ordinary time synchronization before issuing the final HTTPS certificate.
Remoting must not change host TrustedHosts, certificate stores or WinRM settings.
Keep a public leaf pin and compare it with the guest's exported certificate;
per-session CA/name exceptions alone do not enforce that pin.

Prepare a clean baseline before installing the product: gracefully power down
Windows, verify this container has exited, then create an internal qcow2 disk
snapshot with the pinned image's `qemu-img snapshot -c clean`. Preserve the small
writable firmware/TPM files separately. Restore both only while the guest is
fully stopped, and verify fresh product state after its real reboot. Never run
`qemu-img` against an active disk. The [QEMU image tool documentation](https://www.qemu.org/docs/master/tools/qemu-img.html)
defines offline creation/application of these snapshots; no full raw disk copy
or artificial clock is required.

Stop only this fixture with the same Compose file's `stop` command. Use `down`
to remove its container and network; it preserves the external guest volume.
Restore `clean` with `qemu-img snapshot -a clean /storage/data.qcow2` in an
isolated pinned-image helper mounting only that exact volume, while the guest
is stopped, and restore its saved firmware/TPM files before starting again.
Preserve the dedicated disk while collecting results. At disposal, verify the
volume's UUID/fixture labels, then use `docker volume rm` with its exact name;
delete only the verified guest build directory for the accompanying artifacts.

## Canonical installed acceptance

Installed acceptance is a separate installation step, never part of building the
package. On Windows, the `installed-guest-acceptance` target builds `bundle` and
then runs `acceptance.ps1` synchronously. It fails when the guest configuration or
either immutable cohort is absent, and when any actual native phase fails.
`app-payload`, `bundle` and `msi-bootstrap-kit` produce and check the package; they
do not claim installed acceptance. No saved acceptance receipt can substitute for
this invocation's native phases.

Set `CADRUMO_INSTALLED_GUEST_CONFIG` to a private JSON file with `schema: 1`.
`CADRUMO_INSTALLED_GUEST_POWERSHELL` selects the PowerShell 7 executable; configure
finds `pwsh` by default. The configuration contains these actual fixture bindings:

| Fields | Binding |
| --- | --- |
| `uuid`, `sid`, `computer`, `account` | Selected real VM and dedicated account; never session or logon IDs |
| `container`, `volume`, `network` | Exact existing disposable resources; container and volume carry the fixture/UUID labels |
| `guestImage`, `rdpImage` | Immutable **local image IDs** in `sha256:…` form, distinct from repository distribution digests |
| `tlsPin`, `port` | Actual HTTPS leaf SHA-256 and loopback WinRM port |
| `fixtureRoot`, `passwordFile` | Private fixture directory and existing DPAPI password file; no plaintext password field |
| `baselineReceipt`, `baselineReceiptSha256` | Existing product-free, stopped, normal-UAC/clock baseline receipt and exact hash |
| `firmwareVarsSha256`, `firmwareMacSha256` | Exact saved `windows.vars` and `windows.mac` beside that receipt |
| `P1`, `P2` | Each has `archive`, `receipt`, `sha256`, `version`; P1 is the prior release and P2 the newer current candidate |

The saved baseline must explicitly record its matching UUID, volume, snapshot,
normal clock/UAC, absent helpers/products, stopped guest and `tpmPresent: false`.
This owner supports the existing fixture without a TPM; a different baseline
requires its own demonstrated firmware/TPM custody. The current P2 app/services
bytes must match the current CMake stage, and both archives must contain the
current seven campaign owner modules. ZIP path validation, archive receipt hashes
and native kit/plan verification remain mandatory.

The promoted `transport.ps1` is action-free when dot-sourced. The coordinator
restores only the exact labeled, stopped fixture disk and saved firmware. It runs
the current P2 candidate's precommit ABI rejection/rollback on a fresh restore,
restores again, then runs P1 hold and P2 upgrade through
the existing Python campaign: hold, real login transition, scope refusal,
upgrade and native cleanup. Machine scope additionally proves real prelogin boot
and ordinary-user Cadrumo fallback while its SCM service is stopped. Windows
Task Scheduler supplies actual InteractiveToken Least/Highest processes; genuine
RDP credentials travel only through private stdin. Python's existing native
SID/token/logon/credential and authenticated CLI/TUI/MCP assertions decide health.

Only actual cleanup with `full_installation_acceptance: passed`, no pending
obligations and settled resources completes a scope. A fresh invocation UUID
binds both scopes' results under the CMake testing directory. Any failure leaves
the fixture stopped and records failure; that transport settlement is not a
successful native cleanup or installed-health claim. Restore never runs against
an active qcow2 disk, and the owner performs no host product installation.
