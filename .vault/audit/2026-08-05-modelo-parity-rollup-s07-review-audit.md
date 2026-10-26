---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:fd2857db706cac2affc51a8e2f6a6c0973f8497617a228c27d0720760a555822'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---

## Scope

Reviewed W01.P05.S07 against the accepted five-domain parity contract, the denominator research, and the execution plan. The review covered the construct evidence models and registry fold in the retired module, their public exports, and the real registry tests in the retired test. The delegated reviewer returned a checkpoint without a completed report, so the supervisor completed the bounded review.

## Findings

### consumer-projection | medium | Construct rows are not yet joined into conformance output

S07 now emits a registry-wide, revision-keyed construct evidence audit, but the existing conformance profile does not consume it. This is the intended phase boundary: S08 must keep revision evidence floors separate from construct-level and casilla-level provenance when composing the standard report. Until S08 lands, the new audit is a direct domain surface rather than a CLI/report claim.

### selector-inheritance | low | Selector evidence is explicitly inherited from its owning binding

Binding selectors have no independent legal/source fields in the schema. Each selector row therefore retains the binding id, copies only the binding's existing refs, and marks the status `inherited` with an explicit reason. It is not counted as independent selector evidence, and incomplete binding refs become `unresolved` or `unmeasured`.

### authority-and-denominator | low | The fold validates authority and enumerates the complete finite revision portfolio

The registry-wide function validates through `RegistryValidator`, builds authority-selected snapshots for every modelo revision, emits one row for each formula, parameter, binding, relation, and selector, and rejects duplicate `(kind, construct_id)` coordinates. It does not derive construct proof from revision floors or casilla membership.

## Recommendations

- Carry `consumer-projection` into W01.P05.S08 and preserve the explicit distinction between revision floors, construct rows, and casilla producer traces.
- Keep selector rows marked `inherited` until the schema gains selector-owned legal/source declarations; never present inherited binding refs as independent selector proof.
- Retain the duplicate-coordinate and incomplete-ref validators as the fail-closed shape for future construct additions.

## Verification

- the historical check â€” 3 passed.
- the historical check â€” 4 passed.
- the historical check â€” all checks passed.
- the historical check â€” 3 files already formatted.
- the historical check â€” 0 errors and 1 private-support warning in the real-registry test import.
- `git diff --check` on the S07-owned tracked files â€” clean.
