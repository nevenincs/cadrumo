---
tags:
  - '#plan'
  - '#verification-fixture-roles'
date: '2026-06-01'
modified: '2026-06-01'
tier: L2
related:
  - '[[2026-06-01-verification-fixture-roles-adr]]'
  - '[[2026-06-01-verification-fixture-roles-research]]'
---
# `verification-fixture-roles` `role-aware verification fixtures` plan

### Phase `P01` - sidecar provenance schema and stamp

Add explicit provenance (real_corpus|synthetic_generated) and role (parser_anchor|formula_verification) to the fixture sidecar, stamped automatically by the synthetic generator and the real sanitiser manifest writer.



- [x] `P01.S01` - Stamp provenance=synthetic_generated and role=formula_verification into the synthetic fixture sidecar writer _write_sidecar; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `P01.S02` - Real-fixture provenance is set at fixture-authoring time (the P02 backfill stamps committed real sidecars; `future real specimens are stamped when added) — the production PDF sanitiser is intentionally NOT modified, since a test-fixture role on a production frozen model violates the architecture-boundaries rule; the convention is captured by the codified rule; `src/aeat/adapters/inbound/sanitizer/_records.py`.

### Phase `P02` - backfill committed sidecars

Backfill provenance/role into every committed fixture sidecar: real_corpus/parser_anchor for the real specimens (M100, M111, M190, M390/2021), synthetic_generated/formula_verification for the rest.

- [x] `P02.S06` - Backfill provenance/role into every committed fixture sidecar under the justificantes tree: real_corpus/parser_anchor for the real specimens (M100, M111, M190, M390/2021), synthetic_generated/formula_verification for the rest; `regenerate synthetic sidecars via the generator and hand-stamp the real ones; `src/aeat/tests/fixtures/justificantes`.

### Phase `P03` - gate rewrite

Make the verification-source gate per-fixture: read each sidecar's declared provenance and cross-check it against the physical /Producer evidence; delete the _REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS allowlist.

- [x] `P03.S03` - Rewrite the verification-source gate to read each fixture's sidecar provenance and assert it agrees with the physical /Producer (synthetic must carry the signature, real must not); `delete _REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS; `src/aeat/domain/calculations/registry/test_verification_source_fixture_metadata.py`.

### Phase `P04` - verify and codify

Prove the M390 mixed pool passes allowlist-free with both the verification-source gate and the corpus-roundtrip test green, then promote the fixture-provenance-declared-in-sidecar rule.

- [x] `P04.S04` - Run the gate battery green allowlist-free: verification-source gate + corpus-sidecar roundtrip; `confirm the M390 mixed pool (real 2021 + synthetic 2022/2023) passes both; `src/aeat/domain/calculations/registry/test_verification_source_fixture_metadata.py`.
- [x] `P04.S05` - Codify the fixture-provenance-declared-in-sidecar rule via vaultspec-core spec rules add (provenance declared in sidecar; `gates read sidecar + cross-check physical evidence; no hardcoded per-fixture exception allowlists); `.vaultspec/rules/rules/project/fixture-provenance-declared-in-sidecar.md`.

## Description


Implements the accepted ADR's Option A: fixtures declare their provenance
(`real_corpus` | `synthetic_generated`) and role (`parser_anchor` |
`formula_verification`) in their `.json` sidecar, so the verification-source
honesty gate becomes per-fixture and the `W06.P16.S37` allowlist
`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` is deleted. The synthetic generator and
the real sanitiser each stamp the sidecar at write time; committed sidecars are
backfilled once; the gate reads each sidecar's declared provenance and
cross-checks it against the physical `/Producer` evidence (defence in depth). The
corpus-roundtrip test continues to consume the real M390 2021 anchor unchanged.
The parallel `_PERIOD_EQUALS_EJERCICIO` list is a documented out-of-scope
follow-up (it encodes layout, not provenance).

## Steps







## Parallelization


P01.S01 and P01.S02 are independent (synthetic generator vs real sanitiser) and
parallelisable. P02 (backfill) depends on P01 (the stamp fields must exist), and
P03 (gate rewrite) depends on P02 (sidecars must carry provenance before the gate
reads them). P04 verification gates the whole chain; P04.S05 (codify) runs only
after P04.S04 is green.

## Verification


Success criteria, each a verifiable check:

- `test_verification_source_fixture_metadata` passes with
  `_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS` deleted (grep confirms the symbol is
  gone).
- The M390 mixed pool (real `2021-0A` + synthetic `2022-0A`/`2023-0A`) passes the
  verification-source gate via sidecar-declared provenance.
- `test_corpus_sidecar_roundtrip` stays green (the real 2021 anchor is unchanged).
- A deliberately mis-stamped sidecar (claim `synthetic_generated` on the real
  2021 PDF) reds the gate via the `/Producer` cross-check — proving the honesty
  property survives.
- Every committed fixture sidecar carries a `provenance` field; the synthetic
  generator and real sanitiser stamp it automatically (re-running the generator
  is a no-op diff for unchanged fixtures).
- The `fixture-provenance-declared-in-sidecar` rule is registered (P04.S05).
