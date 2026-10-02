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
