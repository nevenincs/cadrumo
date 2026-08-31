---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b34a3f8b56cae02c8ac88dc751b8d10db1375175b791f97540f1150acdfdaa88'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S122 code review`

## Scope

Independent review of P05.S122 at `fdac6d837897909c03888b75131b515a39a4965f`: the extraction of the Sheets presentation and validation request builders from `calc_sheets_apply.py` into `_calc_sheets_apply_formatting.py`, every changed consumer and test, the S122 execution record, the size baseline, and the current descendant HEAD `e2017090f05189f01ae30e1d29d9562690cfa09b`.

## Findings

### stale-cap-inventory | high | Relocation leaves the strict canonical-definition inventory red

S122 relocated `_condition_for_constraint` from `calc_sheets_apply.py` to `_calc_sheets_apply_formatting.py`, but omitted the matching move in the cap-term inventory. The current `test_every_discovered_cap_site_is_enrolled` reports the new `(adapters/outbound/google/_calc_sheets_apply_formatting.py, _condition_for_constraint)` site as unenrolled, and `test_no_enrolment_outlives_its_site` reports the old `(adapters/outbound/google/_calc_sheets_apply.py, _condition_for_constraint)` exemption as stale. `uv run --no-sync pytest -n0 -q src/cadrumo/tests/test_regulatory_cap_term_dominance.py` failed both test IDs. The output also contains six pairs from unrelated relocations; this finding is only the S122 pair. The source extraction is otherwise a direct private-sibling import with no facade or re-export, and the size baseline was not changed.

### non-reproducible-exec-evidence | high | The S122 record does not name the passing test selections

The S122 execution record claims two passing pytest checks using `<five focused real Modelo-plan builder modules>` and `<apply/preview/clear-order consumer modules>` in place of concrete node IDs or paths. Those placeholders cannot reproduce or assess the asserted evidence, contrary to the plan's execution-evidence criterion. It also describes a 1,172-line source-specific measurement although the committed target is 1,028 physical lines, below the 1,250 default; the record must state the actual measured command and result.

### repair-verification | low | Both S122 high findings are resolved by the repair commit

Review of `15e6518f1c5abf568125954aaf445570a7b76c3d` confirms that the exemption now names only `(adapters/outbound/google/_calc_sheets_apply_formatting.py, _condition_for_constraint)`. The cap-term command still fails its two test IDs, but its output now contains exactly six non-S122 source/legacy-path relocation pairs and neither the new Google Sheets path nor the old path. The execution record now gives concrete pytest and ruff commands. Direct budget measurement reports 1,172 physical lines; the recorded PowerShell nonblank-line command reports 1,028, and both are under the 1,250 default. No baseline change was introduced.

## Recommendations

- For `stale-cap-inventory`, update the one S122-owned exemption to the canonical sibling path and prove both named cap-term inventory tests pass; do not absorb the six unrelated inventory failures.
- For `non-reproducible-exec-evidence`, amend the scaffolded S122 execution record through the owning vault verb with the exact pytest selections, exact size measurement command and actual result, then rerun and record those checks.
