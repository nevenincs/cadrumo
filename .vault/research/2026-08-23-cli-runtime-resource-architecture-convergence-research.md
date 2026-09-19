---
tags:
  - '#research'
  - '#cli-runtime-resource-architecture-convergence'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:766b92694e2fbceba3c9b6915fb5a01e8ad74c8d26209b4559bd7ce02a323499'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
---

# `cli-runtime-resource-architecture-convergence` research: `runtime CLI authority and release-lane convergence`

Two independent read-only architecture reviews on 2026-08-23 converge that the
current S11 resource and proposed S14 resource are release-blocking: ignored
generated files are read by shipped modules, while release construction starts
from tracked Git objects and excludes development tooling. They also converge
that removing JSON is insufficient unless one import-light,
production-authored command specification replaces every parallel structural
authority. The second review corrects one dependency claim from the first:
S14 does not call `full_command_tree`; it independently reassembles nine
application families, while S11 calls `full_command_tree` and therefore inherits
the app-manifest generation order. The ADR must settle the single authority,
its build and runtime invariants, and an atomic cutover.

## Findings

### AGREE — shipped code depends on ignored, untracked generated resources

The S11 runtime loader names `command_registration_metadata.v1.json` and reads
it from package resources; the S14 worktree loader does the same for
`app_lazy_manifest.v1.json`. `src/cadrumo/entrypoints/cli/_command_schema.py:226`
`src/cadrumo/entrypoints/cli/_command_schema.py:282`
`src/cadrumo/entrypoints/cli/_app_lazy_registration.py:66`

Both resources are ignored rather than tracked. `git ls-files` returns neither,
while `git status --ignored` identifies both as ignored. The ignore comments
call them build/runtime artifacts that must never be committed. `.gitignore:489`
The runtime readers therefore succeed only when prior local development
generation has populated the source package.

This violates the accepted 2026-08-22 decision before any preference about
generated code is applied. That decision rejects a plaintext cache or manifest
because it creates another authority, and requires lightweight command metadata
and loader references inside the demand-loaded production design.
`.vault/adr/2026-08-22-secure-storage-performance-hardening-adr.md:29`
`.vault/adr/2026-08-22-secure-storage-performance-hardening-adr.md:66`

### AGREE — repository build and shipping lanes cannot supply the resources

The generators live under `dev/quality`, and their default outputs point into
`src/cadrumo/entrypoints/cli`. `dev/quality/generate_command_registration_metadata.py:20`
`dev/quality/generate_app_lazy_manifest.py:129` The sdist explicitly excludes
`dev` and all descendants. `pyproject.toml:246` The immutable Python cohort
rejects source drift, archives one commit, and builds both wheel and sdist from
that archive; ignored files cannot enter this lane.
`dev/packaging/python_cohort.py:343`
`dev/packaging/python_cohort.py:366`
`dev/packaging/python_cohort.py:376`

Consequently the same defect reaches clean checkout, editable install from a
clean checkout, direct wheel build, sdist-to-wheel build, Git-archive cohort,
and installed runtime: none has an authorized step that can materialize both
resources before the shipped loaders import them. An implicit generator step
would instead make production packaging depend on excluded development code and
on materializing the production tree it is trying to describe.

### MODIFY — the dependency failure is shadow assembly plus an ordered cycle

The first review described S14 as a direct generator/bootstrap cycle. Exact
source narrows that claim. S14 imports and manually composes nine application
families, supplemental telemetry, review, and participation registrars, then
walks the reconstructed Typer tree; it does not call `full_command_tree`.
`dev/quality/generate_app_lazy_manifest.py:19`
`dev/quality/generate_app_lazy_manifest.py:31`
`dev/quality/generate_app_lazy_manifest.py:39`

That correction does not make the design independent. The manual composition is
a second structural authority that can omit or miscompose a family. S11 does
import `full_command_tree`, and that runtime tree imports the S14 resource
through app lazy registration. The observed dependency is therefore:

```text
production Typer declarations
    -> dev S14 shadow assembly -> ignored app manifest
    -> production app registration
    -> runtime full_command_tree
    -> dev S11 projection -> ignored registration metadata
    -> production schema/operator discovery
```

`dev/quality/generate_command_registration_metadata.py:74`
`dev/quality/generate_command_registration_metadata.py:131`
This is an ordered generated-resource cycle across production and development
lanes, not a single recursive function call.

### AGREE — the replacement must remove parallel structural authorities

Both reviews favor import-light production-authored command specifications only
under a stronger condition: the specification must replace, not mirror, Typer
decorators, callback-attached execution policy, generated registration
projections, lazy path tables, and hand-kept verb catalogues as the structural
authority. Otherwise a new `CommandSpec` would merely add another parity surface.

The minimum production declaration must own the operator tokens and tree edge,
node kind and invocation behavior, parameter schema and localized translation
keys, execution policy and write route, and lazy handler/schema targets. A
production assembler may compile those declarations into Typer/Click objects at
runtime without importing handler modules. Development tools may traverse and
validate the declarations, but may emit only disposable evidence outside the
runtime dependency graph.

Alternatives remain materially weaker:

- committing the JSON makes the ignored cache available but preserves duplicate
  authority and noisy regeneration;
- build-time generation moves the missing-file failure into a production-to-dev
  dependency and cannot make editable or clean-source behavior equivalent;
- runtime generation imports or reconstructs the heavy tree and restores the
  startup amplification the campaign exists to remove;
- keeping decorators plus a mirrored `CommandSpec` adds drift rather than
  eliminating it.

### AGREE — runtime resources and development evidence require different rules

The profiling baseline under `dev/benchmarks/cli` is development evidence: it is
not imported by production, need not ship, and may be retained according to the
campaign's audit and reproducibility needs. The two CLI JSON files are different
because production imports them to construct or discover executable behavior.
Their deterministic generation and parity tests cannot change that authority
flow.

The corrective ADR must define one invariant across a clean checkout, editable
install, direct wheel, sdist rebuilt into a wheel, immutable Git-archive cohort,
and installed runtime: all executable CLI structure is present in tracked
production Python and no generated runtime cache or `dev` dependency is needed.
It must also require a hard cut without fallback or compatibility shim. Detailed
performance after the cut and the pure secure-storage inventory remain for the
campaign plan; this research did not benchmark a prototype `CommandSpec`.

## Sources

- `src/cadrumo/entrypoints/cli/_command_schema.py:226`
- `src/cadrumo/entrypoints/cli/_command_schema.py:282`
- `src/cadrumo/entrypoints/cli/_app_lazy_registration.py:66`
- `.gitignore:489`
- `.vault/adr/2026-08-22-secure-storage-performance-hardening-adr.md:29`
- `.vault/adr/2026-08-22-secure-storage-performance-hardening-adr.md:66`
- `dev/quality/generate_command_registration_metadata.py:20`
- `dev/quality/generate_command_registration_metadata.py:74`
- `dev/quality/generate_command_registration_metadata.py:131`
- `dev/quality/generate_app_lazy_manifest.py:19`
- `dev/quality/generate_app_lazy_manifest.py:31`
- `dev/quality/generate_app_lazy_manifest.py:39`
- `dev/quality/generate_app_lazy_manifest.py:129`
- `pyproject.toml:246`
- `dev/packaging/python_cohort.py:343`
- `dev/packaging/python_cohort.py:366`
- `dev/packaging/python_cohort.py:376`
