---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b64950c773136bd8f8283c657bf4073692269fed0a37aa55e3e040da7f1b779f'
step_id: 'S57'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Require canonical generator provenance, exact semantic-map and render-profile identities, generated-fragment integrity, and successful emitted-byte evidence before filing-export closure can satisfy, with a Modelo 111 refusal regression

## Scope

- `src/cadrumo/application/registry/`
- `dev/registry/`
- `src/cadrumo/application/filing/tests/`

## Description

- Add a strict filing-export proof boundary carrying exact modelo, revision, and loaded-layout identities.
- Require the canonical generator verifier identity, provenance-manifest digest, semantic-map digest, render-profile digest, loader-semantic digest, and sorted generated-fragment digests.
- Require successful production `export_draft` evidence with a payload digest, positive emitted-byte extent, and at least one checked official offset.
- Promote the existing canonical provenance verifier through the development pipeline facade so the recorded authority name resolves exactly.
- Make filing-export coverage refuse when proof is absent, stale, conflicting, or incomplete, while preserving official layout-source byte verification.
- Add structural mutation bites and a real bundled Modelo 111 regression proving a loadable fixed-width layout cannot imply fileability.
- Regenerate the application-registry API reference through the repository-owned scaffold.

## Outcome

Filing-export closure no longer promotes a filing-grade revision from layout shape and
official-source rehashing alone. Satisfaction now requires one exact proof from both
independent authorities: canonical generator-provenance verification and successful
production byte emission. The proof catalogue is empty by default and carries no
invented success. Modelo 111 revision `2019-y-siguientes` remains visible as an owned
`missing_evidence` refusal despite its fixed-width layout.

Focused verification passed:

- `uv run --no-sync ruff check` over the four application-registry implementation and test files.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/registry/tests/test_filing_export_coverage.py`: 7 passed.
- Direct facade import check resolved both `verify_export_fragment_provenance_manifest` and `export_draft`.

## Notes

The existing emitted-byte acceptance module explicitly stops in an unfinished
`NotImplementedError` and covers only Modelos 303 and 390. It is not successful proof
for any revision, so this Step does not add a development adapter or a success row that
would convert test intent into evidence. A caller may populate the strict catalogue only
from a real proof runner that has completed both named authority stages.

The first focused fixture run encountered concurrent `source_root` signature threading
in the registry validator before S57 code executed. After the owning S58 work corrected
the temporary call mismatch, the required sequential rerun passed. No S58 registry-build
or embedded-envelope surface was modified.
