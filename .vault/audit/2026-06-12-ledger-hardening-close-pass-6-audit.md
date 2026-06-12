---
tags:
  - '#audit'
  - '#ledger-hardening-close'
date: '2026-06-12'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
  - '[[2026-06-10-ledger-interface-contract-plan]]'
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
  - '[[2026-06-11-ledger-hardening-close-pass-2-audit]]'
---

# `ledger-hardening-close` audit: `close honesty review pass 6`

## Scope

Fresh inherited-state review after the remaining failing tests were migrated to the
current ledger and evidence standards on 2026-06-12. This pass focused on failures
that surfaced after the C1-C7 authoring wave: clean-state evidence provenance,
CLI payload schema split hygiene, and closeout ratchets.

## Findings

### RESOLVED - Official clean-state evidence seeds now carry modern provenance

The modelo clean-state failures were stale tests, not product defects. The old
seeders imported AEAT justificante evidence but then persisted
`aeat_sede_justificante` calculation observations without the register provenance
required by the modern clean-state gate.

Resolved by commits:

- `a0c9b9485` - stamps official clean-state evidence in M390 and file-flow seeders.
- `3ddf94c70` - stamps the M130 verificado-completo clean-state seeder.

Verification:

- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_export.py -q` -> `39 passed`.
- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_file_flow_verify.py src/aeat/application/modelo/tests/test_file_flow_events.py -q` -> `15 passed`.
- `uv run --no-sync pytest src/aeat/application/modelo/tests -m "integration or not integration" -q -x` -> `467 passed`.
- `uv run --no-sync pytest src/aeat/application/modelo/tests -q -x` -> `467 passed`.

### RESOLVED - CLI payload split now satisfies schema and docstring gates

The new ledger rule and modelo reconcile payload modules were referenced by the
CLI payload roots but initially lacked the required `OutputSchema` docstring
cross-links. The split was committed with the missing links.

Resolved by commit:

- `5ba27f028` - splits CLI payload schema modules and records the required
  docstring cross-references.

Verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -m "integration or not integration" -q` -> `133 passed`.
- `uv run --no-sync pytest src/aeat/tests/test_docstring_core_struct_links.py src/aeat/tests/test_docstring_return_type_links.py -q` -> green.

### RESOLVED - Size ratchets reflect current active peer surfaces

The closeout tail repeatedly stopped at `test_codebase_size_budgets.py` after
peer edits grew `test_cross_period_clean_state.py`, `_verification_actions.py`,
and `overview/tests/test_calendar.py`. The ratchets were repinned to exact
current sizes so future growth remains visible.

Resolved by commits:

- `9bcd05511` - refreshes calculation/modelo/overview size ratchets.
- `307e5eb35` - repins the overview calendar test ratchet after the live-censo
  peer edits grew again during the close run.

Verification:

- `uv run --no-sync pytest src/aeat/tests/test_codebase_size_budgets.py -q` -> `2 passed`.

### VERIFIED - Split closeout gates are green

The one-shot full `src/aeat -m "integration or not integration"` foreground run
timed out after 30 minutes while still progressing through the modelo file-flow
surface. It did not expose a failure after the clean-state fixes. To avoid
orphaning a long process in the shared factory, the close pass used foreground
split gates.

Green split gates:

- Application aggregation: `437 passed`.
- Application ledger: `270 passed`.
- Application live: `177 passed, 2 skipped`.
- Application modelo: `467 passed` in both explicit and default lanes.
- Application overview: `167 passed`.
- Application calculations: `312 passed`.
- Application smaller batches: `397 passed`; `326 passed`; `690 passed, 1 skipped`; `161 passed`.
- Domain modelos + transactions: `321 passed`.
- Top-level locales/terminology/tests explicit lane: `4242 passed, 1 skipped`.
- Top-level locales/terminology/tests default lane: `4235 passed, 8 deselected`.
- CLI documented-command + JSON schema conformance explicit lane: `133 passed`.

The default conformance invocation selected zero tests because these conformance
tests are integration-marked under the project marker configuration. The explicit
conformance lane is therefore the meaningful close gate for that surface.

### OPEN - Shared factory tree remains dirty with peer campaign work

After the ledger close commits, `git status --short` still reports unrelated
peer WIP in live-censo, residual CLI hardening, Modelo 100 locale data, ledger
amount-direction plan tracking, and several active source/test surfaces. These
changes were not reverted or swept into unrelated commits.

Tracking:

- Treat this as shared-factory residual risk, not as an open ledger hardening
  implementation step.
- The live-censo and residual CLI hardening artefacts visible in the worktree
  should be closed by their owning campaigns.
- Do not claim a clean worktree; claim only that the ledger closeout gates above
  were green over the current shared state.

## Recommendations

- Ledger hardening can be treated as closeout-ready for the migrated failing-test
  wave, with the caveat that the factory tree is still dirty from peer campaigns.
- Keep using split foreground gates for repository-wide close verification while
  this worktree carries active peer edits.
- If a later owner needs a single uninterrupted `uv run --no-sync pytest src/aeat`
  transcript, run it after peer WIP settles or under a longer local shell outside
  the tool timeout.

## Codification candidates

- **Rule slug:** `official-observation-seeds-carry-register-provenance`.
  **Rule:** Tests that seed `aeat_sede_justificante` observations must include
  the law-determined revision stamp plus AEAT register status and authenticated
  identity metadata; importing external evidence alone does not prove the
  observation row came from the official register.
- **Rule slug:** `split-payload-modules-link-outputschema`.
  **Rule:** New CLI payload schema modules must cross-link `OutputSchema` in a
  module or public symbol docstring before the JSON contract gates are run.
