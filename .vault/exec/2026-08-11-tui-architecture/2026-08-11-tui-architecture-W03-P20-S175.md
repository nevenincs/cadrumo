---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:4827514e2096415b7ae5366d9c1e3bc3ba2c5c690e045f3a37308ae828526ba7'
step_id: 'S175'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Registry facade family census and disposition scheduling

## Scope

- `dev/quality/registry_facade_family_census.py`
- `dev/quality/registry_facade_family_census.v1.json`
- `dev/tests/test_registry_facade_family_census.py`
- `.vault/audit/2026-08-26-tui-architecture-registry-facade-family-census-audit.md`
- `.vault/plan/2026-08-11-tui-architecture-plan.md`

## Description

- Derive the fixed 78-pair c941 denominator from the historic rename delta.
- Bind all reviewed source and consumer evidence to immutable Git commit `aef1e903cebe8e463c5ac1c3192b30f2b4f3e8c8`, never the dirty working tree.
- Resolve relative imports, TypeAlias nodes, exact package attributes, and literal/nonliteral dynamic imports; retain structured per-row owner, competitor, substitutability, and terminal evidence.
- Add the Sol HIGH correction: a resolved relative-import candidate contributes its evidence source to both the direct-module graph and the appropriate production, test, fixture, documentation, or tooling category.
- Persist actual `vaultspec-rag` code-query/result records only for R01 and R55, with their request IDs and selected ranges; retain immutable AST locators exclusively as source evidence.
- Keep the reviewed 54/9/13/2 disposition inventory and one future Step per row.
- Add a separate current-terminal observer so future H/P/D path disappearance is valid without a compatibility surface.

## Outcome

The matrix is deterministic, schema-versioned, immutable-evidence-bound, and bound to canonical plan Steps. The S175 check fails closed for changed historical pairs, an evidence-commit mismatch, stale consumer/measurement/dynamic-import evidence, missing source/import or terminal locators, unresolved or grouped rows, invalid terminal state, wrong disposition count, duplicate mapping, absent plan Step, or a final gate that does not depend on every disposition Step.

The direct relative-only import in `src/cadrumo/adapters/inbound/declaracion/_parser.py` is now recorded as an `_authority.py` production consumer, not merely a transitive one. R01 carries the executed `AEAT remote read host authority canonical hostname only:prod` RAG query under request `eec115fcf1ae4225b7e9209afc205b2b`, selecting `aeat_hosts.py:19-51`; R55 carries the executed `ENCODING_ALIAS_MAP registry schema export value policy only:prod` query under request `f8cff429a3cd4d8fa1dc335774db9e47`, selecting `schema_exports.py:1-41`. The checked schema accepts their genuine structured result fields and rejects an AST-locator-shaped substitute. The other 76 rows retain null RAG fields rather than an unperformed-query claim.

Sol independently failed frozen `976d47eb75` because its evidence was current-worktree-derived and incomplete. This remediation replaces that approach with Git-object evidence, direct relative categorization, genuine semantic discovery anchors, and future-safe terminal checking. Integrated-main follow-up traced the transient `_schema_verification.py` mismatch to 28 externally dirty reviewed owner/prose rows, not generator drift; fresh checks from both worktrees passed. Symbol/locator/site ordering is now total and a fresh-interpreter foreign-CWD regression binds that invariant.

The final independent Sol review passed at isolated commits `9f23e2c83fa15533745a95750b165826fae60878` and `9192817886bbda187d4827d585ec476a45c9494c`. The reviewed result was integrated into main through `019fc412c8a4a1808f8990246ff37aa72c2fe7d0`, `fefbc8ff46a91491b4f6ad4b8cccd8b6e8060cbc`, and `426fdf9e68c7bb2302238b6aab03203b830c9655`. Competing WIP remains recoverable on `preserve/s175-shared-wip-20260826` and `preserve/s175-owner-evidence-wip-20260826`; faux/current-tree Vaultspec-RAG refresh processes were stopped before final review. The isolated and integrated reviewed source/matrix bytes were proven identical. S175 is closed after this independent review; S173 and affected registry work remain gated by the individual disposition Steps.

## Validation

- Final integrated `uv run --no-sync python dev/quality/registry_facade_family_census.py --check` (immutable evidence): passed.
- Final integrated `uv run --no-sync python dev/quality/registry_facade_family_census.py --check-current-terminal`: passed; 78 open disposition Steps, 77 ordinary open proofs, and R01's future defining-owner destination pending its hard-move Step.
- Focused serial `uv run --no-sync pytest -q -n 0 dev/tests/test_registry_facade_family_census.py`: 17 passed in 166.92 seconds.
- Ruff format/check and `ty check dev/quality/registry_facade_family_census.py dev/tests/test_registry_facade_family_census.py`: passed.
- `vault check exec-mapping --feature tui-architecture`: passed.
- `vault check all --feature tui-architecture`: no S175 errors; 18 pre-existing feature-wide warnings remain outside this Step's owned documents.
- Byte-identity proof across the isolated and integrated reviewed source/matrix objects: passed.
- `git diff --check`: passed.

## Notes

No production registry module, package facade, re-export, shim, alias, or disposition implementation was changed; no shim or re-export was added. This isolated remediation branch began at frozen baseline `976d47eb759dcbc65b01cc3aa1f5dd8ef43c2268`, has its earlier immutable-evidence remediation at `24268390b819df50c01e7ccc9809d8198adc276a`, and reached final independent PASS at `9f23e2c83fa15533745a95750b165826fae60878` and `9192817886bbda187d4827d585ec476a45c9494c`. The reviewed commits were integrated into main at `019fc412c8a4a1808f8990246ff37aa72c2fe7d0`, `fefbc8ff46a91491b4f6ad4b8cccd8b6e8060cbc`, and `426fdf9e68c7bb2302238b6aab03203b830c9655`; competing WIP remains recoverable on `preserve/s175-shared-wip-20260826` and `preserve/s175-owner-evidence-wip-20260826`. Faux/current-tree Vaultspec-RAG refresh processes were stopped before final review. The final integrated immutable and terminal checks passed, with the focused serial census tests green as recorded above.
