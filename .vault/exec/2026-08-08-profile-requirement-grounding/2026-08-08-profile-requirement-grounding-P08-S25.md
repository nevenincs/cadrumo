---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:01e2a7ba8b7863ce45471da39cd2cb84ff21bc636c9f22e746abb3579ec43dab'
step_id: 'S25'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Sweep every modelo registry TOML under _data/registry/aeat/modelos/ for source=profile bindings and compare each binding's legal_refs against the corresponding schema.toml field's legal_refs

## Scope

- `record every field where one side carries grounding the other lacks, across the full registry not a sample; persist as a dated reference document, no code changes in this step`
- `src/cadrumo/_data/registry/aeat/modelos/`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `.vault/reference/`

## Description

- Reused `build_profile_grounding_index(authority)` (the canonical full-registry `source=profile` binding sweep, memoised since P06.S18) rather than hand-walking modelo TOML directories - it already unions every modelo's every revision's every binding's `legal_refs` per profile key, which is the exact sweep this Step asks for, computed by production code rather than reimplemented.
- For each of the 53 grounded profile keys, compared the registry-side unioned `legal_refs` against `schema.field(key).legal_refs` when the key resolves to a real typed field (32 keys; the other 21 are P05.S15's confirmed derived-selector keys with no schema field to compare against).
- Classified every one of the 32 comparable keys into exactly one bucket: agree-non-empty (6), schema-has-refs-registry-lacks (0), registry-has-refs-schema-lacks (24), both-have-refs-but-differ (2).
- For the 2 differing cases, read both ref sets and recorded a plausible non-adjudicating explanation (procedural-vs-substantive scope for `iva.autoconsumo_promotor_base`; broad-field-enum-scope vs narrow-formula-scope for `taxpayer_type.irpf_income_categories`) without asserting a verdict - this Step is a no-code-changes inventory, and a legal-provenance judgment on which scope is correct needs bundled-corpus cross-checking this Step did not perform.

## Outcome

`.vault/reference/2026-08-09-profile-requirement-grounding-registry-schema-legal-refs-drift-reference.md` persisted with the complete measured comparison across all 53 grounded keys (32 comparable + 21 structurally-excluded derived). No code changed. The 24-field "registry has refs, schema field has none" list is flagged as the highest-value, lowest-risk P08.S26 fan-out candidate (mechanical citation-carrying, no new legal research); the 2 differing cases are flagged as needing a human legal-provenance judgment call, explicitly not mechanical.

## Verification

No test-affecting change; verification is the grounded computation itself, reproduced live against the real registry authority and the real loaded schema (uv run, 2026-08-09) - full output captured in the persisted reference document's Findings section, not summarized away here.

## Notes

None. Reusing the already-memoised `build_profile_grounding_index` (landed in P06.S18) made this sweep a single fast in-process computation rather than a hand-authored TOML walk - a concrete payoff of that earlier Step's work inside this same campaign.
