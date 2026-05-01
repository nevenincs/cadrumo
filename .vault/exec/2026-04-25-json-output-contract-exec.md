---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/exec/ location)
# Feature tag (replace json-output-contract with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#exec'
  - '#json-output-contract'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-25'
# Related documents as quoted wiki-links - MUST link to parent PLAN
# (e.g., "[[2026-02-04-feature-plan]]")
related:
  - "[[2026-04-25-json-output-contract-plan]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-04-25-json-output-contract-audit]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `json-output-contract` `phase-1` `implementation-and-verification`

Implemented the standalone foundations for issue `#399` without crossing into
the sibling-owned `#398`, `#393`, or `#239` surfaces.

- Modified: `src/aeat/logging.py`, `src/aeat/config.py`, `env/.env.example`,
  `src/aeat/entrypoints/cli/__init__.py`, `docs/coverage/kent-capabilities.md`,
  `src/aeat/entrypoints/cli/workflow/_test_doubles.py`
- Created: `src/aeat/entrypoints/cli/_schemas.py`, `src/aeat/entrypoints/cli/_exit_codes.py`,
  `src/aeat/entrypoints/cli/_tty.py`, `src/aeat/entrypoints/cli/_log_levels.py`,
  `src/aeat/entrypoints/cli/test_schemas_registry.py`, `src/aeat/entrypoints/cli/test_exit_codes.py`,
  `src/aeat/entrypoints/cli/test_tty.py`, `src/aeat/entrypoints/cli/test_log_levels.py`,
  `src/aeat/test_logging_scrubbing.py`, `docs/exit-codes.md`,
  `docs/json-contract.md`

## Description

Phase 1 now provides:

- the strict `OutputSchema` / `SchemaEnvelope` registry surface and duplicate
  protection
- the stable eleven-value `ExitCode` table and `exit_with()` helper
- TTY probes, color/progress gating, and typed non-TTY stdin refusal support
- the four-level log resolver wired to `AEAT_LOG_LEVEL`
- record-level secret scrubbing at the logging boundary, backed by shared
  `SCRUB_FIELD_PATTERNS`
- user-facing docs that describe the shipped Phase 1 contract honestly and
  defer Phase 2 / Phase 3 work explicitly

The mandatory review found two defects in the first implementation pass. Both
were fixed before the final verification pass:

- inline secret text in log messages was not scrubbed when tuple `%` args were
  also present
- `register_schema()` accepted non-`OutputSchema` classes at runtime

The repo-wide marker integrity failure from `src/aeat/entrypoints/cli/workflow/_test_doubles.py`
was also corrected by adding the required module-level `pytestmark`.

## Tests

Validation completed with:

- `uv run pytest src/aeat/entrypoints/cli/test_schemas_registry.py src/aeat/entrypoints/cli/test_exit_codes.py src/aeat/entrypoints/cli/test_tty.py src/aeat/entrypoints/cli/test_log_levels.py src/aeat/test_logging_scrubbing.py tests/test_config.py`
- `uv run pytest tests/test_marker_integrity.py -k workflow/_test_doubles`
- `just lint`
- `just typecheck`
- `just hooks`
- `just test`

`just test` still fails outside the scope of this issue: four protected
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` timeout cases remain red. The final
full-suite run ended at `2997 passed, 13 skipped, 24 deselected, 4 failed`.

Related audit: `2026-04-25-json-output-contract-audit`.
