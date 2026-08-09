---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:114d8e0c6c17933d8f826d77c4501b945e35c6c59637b71f1d8b52dcc8018796'
step_id: 'S36'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Run the mandatory fresh-context honesty review against the full P01-P08 closure and action every finding

## Scope

- `.vault/audit/`
- `src/cadrumo/application/user_profile/_preflight.py`
- `src/cadrumo/application/modelo/_profile_readiness_gate.py`
- four test files

## Description

Dispatched a fresh-context reviewer (no prior conversation memory) with the full plan, every P05-P08 execution record, all three P05/P08 reference documents, the governing audit, and the actual changed code, instructed to verify claims against current code rather than trust exec-record prose. Four findings, all actioned:

1. **Blocking - campaign-process metadata (Step ids, vault-document dates, "ruling N" citations, "this campaign") leaked into source comments, docstrings, and one assertion message** across `_profile_readiness_gate.py:87` (production) and four test files (`test_schema.py`, `test_services.py`, `test_preflight_reports_unassessed_axis.py`, `test_profile_readiness_gate.py`) - a direct violation of this project's source-hygiene rule (no process history in production identifiers, comments, or tests) that `src/cadrumo/tests/test_marker_integrity.py` exists specifically to catch. Fixed: every flagged docstring and comment rewritten to state the underlying fact without the process citation. Confirmed via two re-runs of the gate (first pass caught 9 of 10 occurrences; a second pass found and fixed one more the pattern matcher's context window missed on the first read) - `32 passed` on the final run.
2. **High - a production docstring still asserted the pre-P05.S16 state.** `ProfilePreflightService.report`'s docstring said "No shipped schema field currently declares a `modelo_` selector... false for every modelo today" - false since the schema now declares 32 such fields. Fixed: rewritten to state the current, narrower truth (Modelo 100 selects via `identity.tax_id`; Modelo 036/303's tokenised fields are all optional, so the flag stays false for them; every other modelo has no tokens at all).
3. **Medium - the same narrowing was undisclosed elsewhere.** Folded into the docstring fix above rather than a separate change, since the docstring is the one place a future reader of `report()` would look for exactly this caveat.
4. **Medium - P08.S35's Verification section overstated what its cited gate proves** (ref-string resolution against the catalogue/corpus, not semantic fitness for the field). Acting on that gap rather than only noting it, read the actual bundled corpus text for the most common carried citation (`orden-hac-1347-2024:art-4`) and found it is genuinely wrong for ~20 of the 24 fields P08.S35 touched - a real, corpus-verified, pre-existing defect on ~26 registry bindings that this Step's mechanical carry propagated onto the schema. Not fixed (human-reviewed legal-provenance work, explicitly out of this Step's scope); persisted as `.vault/audit/2026-08-09-profile-requirement-grounding-wrong-modulos-citation-on-identity-fields-audit.md` with full corpus evidence and a recommended remediation, and P08.S35's own execution record corrected in place to state the gap honestly rather than the overstated original claim.

Also fixed one cosmetic finding the reviewer flagged: the ADR's citation of `_profile_readiness_gate.py:60` for `_FILING_BASELINE_PROFILE_PATHS` was stale after this session's edits shifted the line to 64.

## Outcome

All four findings closed: three with direct code/docstring fixes verified by re-running the relevant gates, one with a properly persisted, corpus-grounded audit document and an honest correction to the record that understated its own evidence. Six items the reviewer specifically checked and ruled out as false alarms (the anti-regression test's real teeth, the locale translations, P07.S22/S23/S27's evidence, P06.S18/S19's landed state, exec-record verification quality, and no collateral breakage from the schema edit) required no action.

## Verification

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/tests/test_marker_integrity.py
32 passed in 35.42s
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/domain/user_profile/tests/ src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -m unit
634 passed, 72 deselected in 93.09s (0:01:33)
```

Corpus evidence for finding 4 is captured directly in the new audit document (article headers and text read from `orden-hac-1347-2024.html.extracted.md` and `orden-hac-277-2026.html.extracted.md`), not merely asserted.

## Notes

This Step is itself the campaign-close discipline's required gate: a fresh-context review ran against the full closure BEFORE declaring the plan complete, and every item it raised is closed with either a verified fix or a formally deferred, evidence-backed follow-up - never silently waved away. The reviewer's own diligence (reading actual corpus text rather than trusting a citation's mere presence) is the pattern finding 4's remediation recommendation asks future grounding-carry work to repeat.
