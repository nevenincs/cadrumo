---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f3ea296ed478574af9b928fd27161041f578dd1d23d9c26c478a6104e0afc99e'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S08 independent review`

## Scope

Independent final-snapshot review of `W02.P03.S08` against the accepted
official-binary and semantic-map authority split, the real Modelo 200 record
design, fragment reviewability gates, architecture boundaries, and strict
loader roundtrip expectations.

## Findings

### real-target-completeness | high | The renderer cannot generate the real Modelo 200 target

The hash-pinned `aeat-dr-200-2025` intermediate contains 77 sheets and 6,808
fields. Every sheet lacks a declared total, and 5,676 of 5,996 numeric fields
lack content metadata. `dev/registry/_export_tree.py` refuses both missing
declared totals and numeric fields without content, so the implementation
cannot render the complete real target required by S08. The focused synthetic
suite does not exercise this authority boundary.

### stable-partitioning | high | Record-only partitioning exceeds the repository TOML cap

The renderer emits one TOML fragment per record. The real `DP200019` sheet has
245 fields; an exact `rtoml` probe using the emitted filler schema produces
3,197 lines. That exceeds the 1,500-line hard gate and the below-1,400 baseline
in `test_registry_reviewability.py`. The loader already supports deterministic
same-record field-fragment merging, so one-file-per-record does not satisfy the
Step's stable-partitioning contract.

### literal-authority | high | Same-width incorrect constants are accepted

Literal normalization validates encoded width but does not compare the reviewed
literal with the official parser content. An official `Constante "<T"` slot
accepted and emitted the same-width semantic value `ZZ`. This can generate
filing bytes that disagree with the official design while all current S08 tests
pass.

### architecture-boundary | medium | The renderer crosses a private production boundary

`dev/registry/_export_tree.py` imports `ENCODING_ALIAS_MAP` from the private
`cadrumo.domain.calculations.registry._record_spec` module instead of the owning
public facade. The test likewise imports the private loader although
`load_modelo_directory` is publicly exported.

### roundtrip-proof | medium | The loader proof asserts only partial projections

The real-loader test checks selected record and field attributes rather than
strict equality between the rendered layout and the loader-materialised layout.
A direct probe currently reaches equality, but the committed assertion would
not detect dropped layout metadata, record settings, or first-record fields.

## Recommendations

- Keep S08 open and resolve the real-target authority gap before treating the
  synthetic renderer as complete. If the official binary does not contain the
  missing facts, amend the ADR to name a separate reviewed authority rather than
  infer from legacy trees.
- Partition records into deterministic ordered field chunks below the current
  reviewability baseline and prove byte-identical double generation plus strict
  loader equality on an oversized real-shaped record.
- Require literal agreement with parsed official constant content, not only
  encoded width, and add the same-width wrong-value refusal test.
- Route encoding and loader APIs through the registry facade and strengthen the
  real-loader roundtrip to strict model equality.
