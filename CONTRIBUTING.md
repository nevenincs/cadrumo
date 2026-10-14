# Contributing to Cadrumo

This guide is for people changing Cadrumo itself. To use Cadrumo, follow the
[installation guide](docs/workstation-setup.md).

## Set up a worktree

You need [`uv`](https://docs.astral.sh/uv/), [`just`](https://just.systems/)
1.38 or later, and on Windows PowerShell 7.4 or later. From the repository
root, run:

```console
just init
```

`just init` syncs the locked Python environment with the development
dependencies, creates `env/.env` from `env/.env.example` when it is missing and
copies in the values you set in the `main` worktree's `env/.env`, installs the repository tooling, provisions the local search service, and
publishes the runtime registry authority. Each step prints its own progress,
and the command is safe to run again. `just setup` runs only the environment
and tooling steps; CI and the devcontainer use it.

The devcontainer (`.devcontainer/devcontainer.json`) runs `just setup` for you.
Browser automation is optional: `just setup-browser` installs the Playwright
channels and `just doctor-browser` checks them.

The published authority lives in `.authority/`, which is not committed. `just`
recipes, `python -m dev.*`, and `pytest` find it on their own. To run the `aeat`
command against it from a checkout, point the product at it yourself:

```powershell
$env:CADRUMO_AUTHORITY_ROOT = "$PWD\.authority"
```

## Author, publish, and verify the registry

The registry is the tax-rule knowledge Cadrumo calculates and exports from.
Changing it is one pipeline, run in this order:

1. **Author.** Edit the declarations under `src/cadrumo/_data/registry/aeat/`
   and the legal evidence under `src/cadrumo/_data/corpus/`. Start a new modelo
   with `just registry-modelo-scaffold`, or a new revision of an existing one
   with `just registry-modelo-new-edition`; `just registry-modelo-checklist`
   lists what a revision needs. Store a revision as its differences from the
   one before it, not as a copy. Export layouts are generated from the inputs in
   `dev/registry/mappings/` and `dev/registry/render_profiles/`; write one with
   `just registry-publish-target` and confirm it with
   `just check-registry-target-current`.
2. **Publish.** Run `just registry-publish-authority-if-authority-stale`. It
   compiles and validates the whole registry and replaces `.authority/` only
   when the result is valid; when nothing changed it reports
   `published=skipped-current` in seconds. Installed code reads only this
   publication, never the source tree.
3. **Verify.** Run `just check-registry-gate` (validity, runtime load, and
   integrity against the publication) and `just test-registry`.
   `just check-registry` reports the registry's overall health.

Commit the authored source and generated export layouts. Never commit
`.authority/`. For details, see
[Publish a validated runtime authority](docs/how-to/publish-runtime-authority.md),
[Registry conformance](REGISTRY-CONFORMANCE.md), and
[the registry tooling](dev/registry/README.md).

## Verification principles

- Ground every rate, threshold, formula, and record layout that affects a
  filing in the exact AEAT or BOE provision, instruction, or record design for
  that modelo and period, and cite it.
- Test through the real registry, compiler, resolver, and calculation. Use test
  doubles only to isolate pure logic in unit tests, never for the behavior a
  test claims to check.
- Take expected values from an independent source, such as an official worked
  example or a separate calculation, never from the output of the code under
  test.
- Keep missing, unsupported, and zero distinct. A total is complete only when
  every required input is present; never fill a gap with zero.
- A check must catch the defect it guards against. Show it failing on a planted
  defect in a temporary fixture, and passing on the real tree.
- A result is the command you ran and its exit status. Report failures you
  found but did not cause separately from ones you introduced.

## Runtime and native-host test guidance

### Test lifetimes

Do not start a shared runtime before running pytest. Unit tests exercise contracts
and isolated behavior without a background runtime. Integration fixtures that need
native IPC or profile workers start their own runtime/server in a temporary
synthetic storage root, wait for verified transport readiness, and stop and reap
their resources during teardown, including failures and cancellation. Test-owned
startup and cleanup are permitted; they do not install a service or introduce
product autostart or health management. Never point fixtures at a developer's
existing runtime or private profile root.

The native launch-door tests own finite child processes through `_fixture`;
installed-entrypoint tests use `launch` with an `ExitStack`; authenticated CLI/MCP
tests use `native_api_cli_session` and `NativeRuntimeFixtureOwner`. Preserve these
owners when adding tests so teardown also runs when setup or assertions fail.
Installed-entrypoint checks must use the installed executable and real bootstrap.
Tests that bind `ProfileWorkerCustody` directly must run that body in a disposable
child process: its immutable profile binding deliberately survives custody close.
Do not reset that production binding to make a later test pass. Publish file-based
readiness payloads atomically so existence also means the full payload is readable.

Run both runtime test scopes explicitly; the default pytest selection is unit-only:

```powershell
uv run pytest -n0 -m 'unit or integration' src/cadrumo_runtime/application/tests src/cadrumo_runtime/adapters/tests src/cadrumo_runtime/commands/tests src/cadrumo_runtime/contracts/tests src/cadrumo_runtime/host --durations=20
```

Native platform skips are coverage limits, not successful cross-platform checks.
Measure cold startup separately from request execution. Registry preparation
must finish before a fixture exposes transport readiness. Installed-runtime
fixtures allow 60 seconds for cold bootstrap; request deadlines stay independent.
Diagnose and record startup phases before changing a setup budget, and never
substitute a fixture server to conceal an installed-runtime startup failure.

For manual CLI/TUI/MCP testing, explicitly run `cadrumo-runtime` in a separate
development terminal with the same absolute storage root, native endpoint storage
identity and installed product version as the client. Its required arguments are
`--storage-root`, `--storage-identity` and `--expected-version`. Stop that owned
runtime when the development session ends. Clients only connect; they do not
start or repair it. Application provisioning will define the eventual launch policy.
Load local development environment values explicitly, for example with
`uv run --env-file env/.env cadrumo-runtime ...`; product settings do not read
dotenv files themselves. Session-admission overrides belong to the runtime owner,
and tests must select their intended policy explicitly rather than inherit a
developer's local override.

### Native host and credential-store coverage

`just test-native-host` selects the explicit Unix peer, worker-containment, and
custody cohort, using the `unit` and `integration` markers while excluding
`os_keychain` tests. Native platform skips are coverage limits, not successful
cross-platform checks. `just test-native-host-facilities` selects only the
explicit macOS peer fixture and disposable Linux GNOME Secret Service
collection, which need their respective native host facilities.

Read `os_keychain` as a capability of the **logon session**, not of the dependency
set. A headless continuous-integration runner, and an agent reaching the host over
SSH, each hold a network logon that carries no credentials: a real credential
backend is selected and then refuses every call, so no session key can be custodied
there at all. Run these tests from an interactive desktop session. On a host that
cannot custody one, each case needing the store is skipped at the explicit
`require_os_credential_store()` precondition, under an
`OsCredentialStoreRefusedWarning` naming the measured refusal. This reports the
host; it is neither a defect nor coverage. The precondition is called per case,
not keyed on the label, so a labelled case asserting the refusal path still runs.

Label only what is irreducibly capability-bound. A case provable without the
capability must stay unlabelled, or it silently leaves every automated lane.
The `os_keychain` cases require a separate interactive-desktop verdict: CI and
agent hosts cannot run them, and the automated suite does not cover profile-session
custody. A test-support credential backend would be a production-shaped fake, and
writing both halves of the split-knowledge pair to disk would make the assertion
vacuous; treat the remaining coverage gap as live risk.

Run `just test-os-keychain` from an interactive desktop session. This is a
**recurring** obligation, not a one-time sign-off: every change to login, logout,
session resume, or session-key custody re-opens the gap, and only a desktop run
closes it again. A green run once does not vouch for the code as it stands now.
The keychain lane scope and lane reachability gates keep the gap visible; they do
not fill it.

## Standards

- Import each symbol from the module that defines it. Keep `__init__.py` files
  empty: no re-exports, aliases, or wrappers.
- Put tests in the nearest `tests/` directory of the code they cover.
- When you move or replace something, update every caller and delete the old
  path in the same change. Do not add compatibility shims.
- Never hand-edit generated files, such as API stubs, locale catalogues, and
  generated export layouts. Change the source and run its generator.
- Extend the CLI under its two root commands, `config` and `app`.
- Use the official Spanish term for tax concepts, such as modelo and casilla.
- Keep real taxpayer data, credentials, and certificates out of code, fixtures,
  logs, and issues. Tests use synthetic data.
- Write comments that explain why, not what.

## Before you open a pull request

Run these from the repository root. Each must exit 0:

```console
just check-code
just check-registry-gate
just test-gate
```

- `just check-code` runs the linter, the code and data format checks, the type
  checkers, the import-boundary lint, and the dependency, reachability, usage,
  and docstring-reference checks. `just check-import-boundaries` runs the import
  lint on its own.
- `just check-registry-gate` checks the registry against its publication.
- `just test-gate` runs the tests affected by your change against `origin/main`,
  as CI does.

Then run `just report-code-health`. It reports duplication, import quality, and
complexity across the whole repository, and exits 1 while any of them is red.
Read it for your change: import quality must be green, and no function you
added or changed may be listed as a complexity hotspot. `--full` lists every
hotspot.

If a check fails on code you did not touch, it fails on `main` too. Say so in
the pull request instead of fixing it in the same change.

`just fix-code path/to/file.py` repairs lint, type, and format issues in one
file. The CI merge gate also scans workflows and security; `just gate-local`
runs the full local gate.

Release mechanics live in [RELEASING.md](RELEASING.md).
