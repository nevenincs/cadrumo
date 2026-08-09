---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9450b24f37e6b948420dd2fa228050ac12bb44ab66545ac759318b84befffa97'
step_id: 'S35'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add the 24 registry-grounded legal_refs to their schema.toml fields identified by S25, format-preserving and refusing on any target field not found, since each citation already exists and was corpus-verified on its registry binding and this is carrying it to the field, not new legal research

## Scope

- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`

## Description

- Wrote a format-preserving `tomlkit` mutation script that re-derives the 24 target keys' live `legal_refs` from `build_profile_grounding_index(authority)` (never from the P08.S25 document's static prose), refusing if a key no longer carries live registry refs, if the schema field is not found, or if the schema field already carries non-empty `legal_refs` (would silently overwrite instead of only filling a genuine gap).
- Ran the mutation: all 24 fields changed, values matching S25's recorded findings exactly.
- Caught and fixed a formatting defect the first pass introduced: building the array via `tomlkit.array(str(list(refs)))` round-tripped Python's single-quoted repr instead of the file's double-quoted TOML convention every other array in the file uses (`model_selectors = ["a", "b"]`). Ran a corrective pass rebuilding each of the 24 arrays element-by-element via `tomlkit.array()` + `.append()`, matching the file's existing style, with no change to the underlying values - caught by re-reading the diff, not by a test (a quoting style difference does not change parsed TOML semantics, so no test would have caught it).
- Verified the schema and the registry authority both reload cleanly, and spot-read four of the twenty-four mutated fields to confirm exact value match against the live registry union.

## Outcome

24 `schema.toml` fields now carry the `legal_refs` their consuming registry binding already cited. `identity.tax_id`, `identity.name`, `identity.surnames`, `censo.status`, `tax_residence.state_attribution_ratio`, and 19 `renta_family`/`renta_spouse`/`renta_taxpayer`/`filing_export` fields are affected - see P08.S25's reference document for the complete per-field table.

## Verification

```
uv run --no-sync python -c "from cadrumo.core.resources import resources; schema = resources().user_profile_schema.singleton; print(schema.field('identity.tax_id').legal_refs)"
('orden-hac-1347-2024:art-4', 'orden-hac-277-2026:art-3')
```

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/domain/user_profile/tests/ src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -m unit
633 passed, 72 deselected in 93.45s (0:01:33)
```

This run includes `test_committed_user_profile_schema_legal_refs_resolve_against_catalogue_and_corpus` (`domain/user_profile/tests/test_schema.py`) - an EXISTING gate, not written for this Step, that re-verifies every schema-declared `legal_refs` entry (the 24 new ones included) resolves against the registry legal catalogue AND the bundled corpus via `verify_legal_catalogue`. Its pass is real independent grounding evidence for these 24 additions, beyond "the value matches what S25 recorded."

```
uv run --no-sync pytest -p no:cacheprovider -n 0 src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py -m integration
22 passed in 30.16s
```

## Notes

No new pytest regression was authored for this Step's specific 24 values beyond confirming the existing catalogue/corpus gate covers them - adding a hand-written test asserting `schema.field(x).legal_refs == (...)` for each of 24 fields would duplicate what the mutation script's own live-registry-derived refusal already guards (the script refuses if the live union ever diverges from what it is about to write), and would itself be exactly the kind of hardcoded-literal test this project's quality-gates rule discourages when a structural, always-running gate already covers the same ground.

**Correction, added during the mandatory fresh-context honesty review.** This record's Verification section characterized `test_committed_user_profile_schema_legal_refs_resolve_against_catalogue_and_corpus` as "real independent grounding evidence" for the 24 additions. That overstates what the gate proves: it confirms each ref STRING resolves against the legal catalogue and the bundled corpus - it does not confirm the ref is semantically apt for the FIELD it is attached to. Those are different questions, and the gate only answers the narrower one.

Acting on that gap, a direct corpus read surfaced a real, pre-existing defect this Step's mechanical carry propagated rather than introduced: `orden-hac-1347-2024:art-4` (the annual IRPF/IVA modulos-approval order) is wrongly cited on roughly 20 of this Step's 24 fields (`identity.tax_id`, `identity.name`, `identity.surnames`, most `renta_taxpayer.*`/`renta_spouse.*` fields) - it grounds objective-estimation modulos tables, not declarant identity or family facts. The defect originates on the underlying registry bindings (~26 Modelo 100 2024 `source=profile` bindings), predating this campaign; this Step's carry doubled its surface area onto the schema. Recorded in full, with corpus evidence and a recommended (not actioned) remediation, in `.vault/audit/2026-08-09-profile-requirement-grounding-wrong-modulos-citation-on-identity-fields-audit.md`. Not fixed here: correcting ~26 registry bindings and ~20 schema fields' citations is human-reviewed legal-provenance work outside this Step's and this campaign's remaining scope.
