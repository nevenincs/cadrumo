---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e5f19e92620fd0ca131baac4376b087b3d5a8c9bfb70c453f70c208683c7ec41'
step_id: 'S60'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Replace the passive filing-export proof catalogue with a live fail-closed authority that re-hashes canonical manifest, semantic-map, render-profile, loader-semantic, generated-output, and emitted-payload evidence and verifies production export_draft offsets and execution at composition time, with fabricated and stale catalogue mutation regressions including Modelo 111

## Scope

- `src/cadrumo/application/registry/`
- `dev/registry/`
- `src/cadrumo/application/filing/tests/`

## Description

- Remove the passive `FilingExportProofCatalogue` from the shipped application-registry API.
- Add `LiveFilingExportProofAuthority` under the development registry owner and derive every canonical manifest, semantic-map, render-profile, generated-output, registry, and source path from the exact modelo/revision coordinate.
- Rebuild the current record-design join and drive `verify_export_fragment_provenance_manifest` against the law-selected loader layout before accepting generation evidence.
- Execute production `export_draft` into an isolated temporary artifact, re-read its bytes, reconcile the receipt digest and extent, and require recorded payload digest, byte extent, and generator-grounded official-offset probes to agree.
- Distinguish a live proof identity conflict from stale evidence in the closure composer.
- Add fabricated Modelo 111, identity-conflict, stale semantic-map/render-profile/loader/output, emitted-payload, offset, and generator-green/export-red mutation regressions.

## Outcome

Filing-export closure no longer has a shipped adapter that can promote caller-authored
hash strings and counters into a satisfied limb. The only concrete proof authority now
recomputes both canonical generator evidence and production emission evidence during
composition. Modelo 111 has no canonical generation manifest and remains a visible
`stale_evidence` refusal even when supplied a structurally valid invented entry.

No success entry was authored. Modelo 200's current manifest, semantic map, render
profile, loader semantics, and generated output all verify, but the real production
writer refuses `m200-2025.dp200001.f0009` because the four-digit-year field receives an
invalid value. The live authority preserves that refusal rather than converting the
generator proof into a filing claim.

Focused verification passed:

- `uv run --no-sync ruff check` over the S60 application and development surfaces.
- `uv run --no-sync pytest -n 0 -q dev/registry/tests/test_filing_export_live_proof.py src/cadrumo/application/registry/tests/test_filing_export_coverage.py`: 16 passed.
- `git diff --check` over `src/cadrumo/application/registry` and `dev/registry`.

## Notes

The emitted-byte acceptance catalogue remains empty because no observed revision
completed both proof stages. The production M200 refusal is the bounded live blocker;
it is evidence that the new authority fails closed, not a reason to invent an expected
payload. The temporary failed-export artifact used during grounding was removed.

