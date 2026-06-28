---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S22'
related:
  - '[[2026-05-21-state-architecture-plan]]'
  - '[[2026-05-21-state-architecture-w05-audit]]'
  - '[[2026-05-21-state-architecture-testimonial-regression-audit]]'
---

# `cli-workflow-redesign` `W05.S22`

Ran the final CLI, registry, cross-store integrity, and testimonial
regression gate for the state-architecture plan.

- Modified: `.vault/plan/2026-05-21-state-architecture-plan.md`
- Modified: `.vault/audit/2026-05-21-state-architecture-testimonial-regression-audit.md`
- Modified: `src/aeat/core/i18n/_render.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Deleted: `src/aeat/_data/registry/aeat/modelos/303.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0001-export-layout.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0002-export-layout.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.toml`
- Created: `.vault/exec/2026-05-21-cli-workflow-redesign/2026-05-21-cli-workflow-redesign-W05-S22.md`

## Description

The broad gate surfaced two actionable blockers before W05.S22 could
close.

First, `list_registry_manuals` failed the central output-language
override test because the i18n override cache key used only the
override object's `id()`. A later `override_settings` object can reuse
the same Python object id and receive a stale cached language. The
cache key now includes the language, explicit-field signal, active
profile, state root, database URL, secret-store backend, and
unencrypted-mode flag.

Second, the full domain registry suite failed the reviewability gate
because `modelos/303.toml` had grown to 5,003 lines. Modelo 303 was
migrated to the established directory-mode registry layout. The
manifest, revision metadata, casillas, and export-layout record groups
now live in separate TOML fragments, all below the committed fragment
line threshold. The registry loader merges the fragments back into
the same Modelo 303 definition.

The testimonial batch used the real CLI against
`var/tmp/state-w05-s22-persona` with an unsecured local test backend.
It created profile `w05-operator`, checked profile status, auth
status, auth test, overview status, Modelo 111 readiness, created a
Modelo 111 work unit, calculated a revision from operator casilla
input, verified it, and rechecked overview and integrity. The active
profile UUID was `6b94b5fc-8ad6-4269-8275-e16adf7990a0`; the work
unit was `ce57316721e56051213a26236adb9239ecc1fe6af2660ebae659121ffb5cb454`;
the calculation revision was
`5258d526e2c2508f17a570ad4e39e3374b9eb7d47c1ccef069854628bcf57223`.

The rerun transcript confirmed `auth status` and `auth test` agree on
the active profile and local auth state, `overview status --verbose`
sees the in-progress Modelo work unit, the calculation revision is
`verificado_completo`, and a repeat `work verify` refuses because only
draft revisions can be verified.

## Tests

Validation commands:

- `uv run pytest src/aeat/entrypoints/cli -q -n 8 --dist loadscope`
- `uv run pytest src/aeat/domain/calculations/registry -q -n 8 --dist loadscope`
- `uv run pytest src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/application/registry src/aeat/core/i18n/test_output_language.py src/aeat/core/i18n/test_render_override.py -q`
- `uv run pytest src/aeat/application/test_state_projection.py src/aeat/application/user_profile/test_aggregate.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_profile_census_verbs.py src/aeat/entrypoints/cli/test_config_profile_surface_inventory.py src/aeat/entrypoints/cli/_config/test_apoderado.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_modelos_do_not_keep_stale_single_file_siblings src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_fragmented_revision_directories_are_schema_owned src/aeat/domain/calculations/registry/test_modelo_303_registry.py -q`
- `uv run aeat app registry verify`
- `uv run aeat config repair integrity objects`
- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run ruff check src/aeat/core/i18n/_render.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/application/registry/test_corpus.py`

Results:

- full CLI tree: 629 passed, 8 third-party deprecation warnings.
- full domain registry tree: 1,826 passed.
- registry CLI/application/i18n focused gate: 87 passed.
- state/profile projection focused gate: 105 passed.
- Modelo 303 fragmentation focused gate: 19 passed.
- registry verify: `Verificado=True`.
- cross-store integrity: 7 readable, 0 unreadable across 7 namespaces.
- locale audit and scaffold check: ca/en/es/hu ok.
