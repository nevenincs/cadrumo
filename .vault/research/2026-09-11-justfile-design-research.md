---
tags:
  - '#research'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3d2b705823c6cedaa2296b8977839636ce05a09020e28fe68dda8383358d04f2'
related: []
---
# `justfile-design` research: operator-intent command and tooling boundaries

The root justfile exposes most development operations, but its namespaces mix subject, execution posture, implementation location, and policy composition. A recipe name therefore cannot reliably say whether an operation is blocking, advisory, mutating, capability-dependent, or destructive. The evidence favors a thin public surface organized by operator intent and authority, backed by one semantic owner per primitive fact in `dev/`; the ADR must settle the verb contracts, aggregate boundaries, documentation exception, registry lifecycle surface, and legacy retirement.

## Findings

### The current public taxonomy cannot communicate execution authority

The `check` group combines code quality, registry and corpus correctness, generated documentation state, identity controls, workflow contracts, hook replay, and a local resident-service semantic check. The `test` group combines product populations, registry conformance, repository metatests, packaging campaigns, external tools, platform tests, and cross-group calls; `test-all` includes `check-registry` and `docs-check`. `justfile:240-417`, `justfile:576-607`, `justfile:702-1151`.

The `audit` prefix is also verdict-ambiguous: it covers advisory output, non-zero finding commands, a RED-failing report, and the hard CI dependency-vulnerability gate. `justfile:1153-1288`. Tool-based grouping preserves this confusion; posture-only grouping still conflates subjects. A stable action contract plus subject carries both facts.

### Environment and artifact lifecycle names overlap

`init-python` and `setup-install` both advertise pinned-environment synchronization, while `dev.init` delegates provisioning to `dev.env`. `doctor-env` mixes tool probes, package consistency, browser launch, and an ignored resident-service status. `justfile:49-171`, `dev/init`, `dev/env`.

`build-distributions` constructs published deliverables, `build-python-cohort` constructs a temporary packaging fixture, and container recipes build infrastructure images; `build-all` contains the first two but excludes the images. `justfile:419-558`. Minimal convergence, optional provisioning, diagnosis, release artifacts, test fixtures, and infrastructure are separate operator intents.

### Implementation and mutation names hide authority

The `dev-*` wrappers cover locale mutation, modelo scaffolding, registry checking and publication, TUI operations, migration generation, and database upgrade. They share only an implementation root, and generic argument forwarding can cross read/write authority. `justfile:672-700`, `justfile:1374-1387`.

Ruff repairs are mechanical source changes; corpus sidecars, API stubs, CLI goldens, and catalogues are committed-derived-state generation. Fetching authoritative inputs is a third, domain-owned mutation. `justfile:390-417`, `justfile:609-670`.

### Tests have subject owners and capability qualifiers

The recipes reveal product, registry/calculation, repository/tooling, packaging, and capability-bound subjects. Docker, LibreOffice, Windows, TUI rendering, interactive keychain, and live AEAT operations cannot honestly belong to a portable default. Focused CLI, TUI, smoke, and coverage commands overlap or re-profile canonical populations. `justfile:448-558`, `justfile:702-1151`.

`dev.test_runs` supplies execution transport rather than semantic ownership. `test-dev-tooling` is an otherwise-unowned path backstop spanning many subjects, not a durable lane. `justfile:860-965`, `dev/test_runs`.

### Registry lifecycle questions are distinct facts

Whole-registry validity is established by `dev.registry.conformance integrity`: it checks runtime-artifact currency/readability, compiles validated authority, and verifies the legal catalogue, but does not claim calculation or filing correctness. `dev/registry/conformance/cli.py:161-231`.

Oracle bindings are separate, modelos-only, raw-loader checks that depend on integrity running first when composed. `dev/registry/parity/maintenance_cli.py:33-42`, `dev/registry/parity/maintenance.py:53-69`.

Per-target currentness is canonically established without writes by `dev.registry.pipeline check`, which verifies current rendering, provenance, loader semantics, members, and bytes. The older `pipeline.render_check --check` overlaps but proves a weaker boundary. `dev/registry/pipeline/cli.py:373-411`, `dev/registry/pipeline/_tree_check.py:85-164`, `dev/registry/pipeline/render_check.py:366-465`.

Publication has two products. `publish-authority` replaces the runtime artifact; `publish` replaces one static generated export tree; `republish` adds an expected-manifest guard. `dev/registry/pipeline/cli.py:74-124`, `dev/registry/pipeline/cli.py:441-611`, `dev/registry/pipeline/authority_publication.py:133-328`, `dev/registry/pipeline/_tree_publication.py:121-240`.

The product runtime uses artifact-backed `bundled_authority()` without source compilation or repair. No development command invokes that exact path as a loadability verdict: integrity decodes and recompiles separately, while load census traces a development compiler. This is a missing primitive owner. `src/cadrumo/domain/calculations/registry/authority.py:562-617`, `src/cadrumo/domain/calculations/registry/authority_artifact.py:239-284`, `dev/registry/analysis/load_census.py:78-85`, `dev/registry/analysis/load_census.py:742-761`.

The operator view therefore needs explicit valid, generated-current, authority-published/current, and runtime-loadable axes. A generic `registry-update` would erase the observation/publication boundary.

### Documentation is a coherent discoverability exception

Documentation has checks, builds, serving, generated state, terminology governance, preview, provisioning, and publication. These have different authorities but one strong contributor subject. A `docs-*` namespace preserves discoverability when names retain explicit posture. `justfile:1290-1422`.

### Existing decisions overlap this redesign

The accepted justfile-redesign record established action prefixes but also mandates the RAG lifecycle and a narrower group model, conflicting with the proposed removal and subject aggregates. `.vault/adr/2026-06-09-justfile-redesign-adr.md`.

The tooling-bootstrap record preserves the useful blocking/advisory distinction, but its `quality` and `quality-audit` vocabulary is displaced. `.vault/adr/2026-06-04-just-tooling-bootstrap-adr.md`.

The CI ruling that verdict granularity follows determinism remains compatible and constrains aggregates. `.vault/adr/2026-08-05-ci-lane-deconflation-adr.md`. The immutable runtime-authority decision also remains compatible and grounds distinct validity, publication, and loadability facts. `.vault/adr/2026-09-10-registry-authority-artifact-boundary-adr.md`.

### RAG removal must include connected recipes

Removing only the five `rag-*` recipes leaves the ignored doctor probe, `check-semantic`, resident-service tests, and the resident terminology sweep with an undiscoverable prerequisite. The public cluster must retire together. `justfile:115-131`, `justfile:173-181`, `justfile:571-579`, `justfile:631-634`, `justfile:982-997`, `justfile:1247-1250`.

This does not determine whether underlying RAG packages should be deleted; it establishes only that they do not belong to the justfile interface.

## Sources

- `justfile:49-181`
- `justfile:240-417`
- `justfile:419-558`
- `justfile:571-700`
- `justfile:702-1151`
- `justfile:1153-1288`
- `justfile:1290-1422`
- `dev/init`
- `dev/env`
- `dev/test_runs`
- `dev/registry/conformance/cli.py:161-231`
- `dev/registry/parity/maintenance_cli.py:33-42`
- `dev/registry/parity/maintenance.py:53-69`
- `dev/registry/pipeline/cli.py:74-124`
- `dev/registry/pipeline/cli.py:373-411`
- `dev/registry/pipeline/cli.py:441-611`
- `dev/registry/pipeline/_tree_check.py:85-164`
- `dev/registry/pipeline/render_check.py:366-465`
- `dev/registry/pipeline/authority_publication.py:133-328`
- `dev/registry/pipeline/_tree_publication.py:121-240`
- `dev/registry/analysis/load_census.py:78-85`
- `dev/registry/analysis/load_census.py:742-761`
- `src/cadrumo/domain/calculations/registry/authority.py:562-617`
- `src/cadrumo/domain/calculations/registry/authority_artifact.py:239-284`
- `.vault/adr/2026-06-04-just-tooling-bootstrap-adr.md`
- `.vault/adr/2026-06-09-justfile-redesign-adr.md`
- `.vault/adr/2026-08-05-ci-lane-deconflation-adr.md`
- `.vault/adr/2026-09-10-registry-authority-artifact-boundary-adr.md`
