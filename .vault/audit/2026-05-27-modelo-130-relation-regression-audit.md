---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
---

# `modelo-130-relation-regression` audit: `art-110-5-corpus-fragment-gap`

## Scope

Plan step `P04.S15` (extend `[legal."rd-439-2007:art-110"].required_text`
with the BOE-verbatim art. 110.5 carry-forward sentence fragment)
investigated; this audit documents the corpus-state finding and
defers the required_text extension to a follow-up.

## Finding

The corpus normative source at
`src/aeat/_data/corpus/normatives/rd-439-2007.json#art-110`
contains paragraphs 1-4 of art. 110 (2679 chars). It does not
include explicit text covering the same-ejercicio prior-quarter
saldo-negativo carry-forward (no occurrence of "negativo",
"trimestres anteriores", "minorar", "compensar", or
"apartado 5" in the cached body). The corpus appears to predate
or be incomplete relative to the current BOE source for
RD 439/2007 art. 110.

`src/aeat/_data/corpus/normatives/ley-35-2006.json` likewise does
not contain the carry-forward fragment under any article.

## Disposition

The Modelo 130 carry-forward binding ALREADY cites
`rd-439-2007:art-110` as its legal_refs anchor, alongside three
other authoritative references (`orden-eha-672-2007:art-1`,
`ley-35-2006:art-99`, `rd-439-2007:art-95`). The legal grounding
chain is therefore intact for the binding-level audit trail.

The mechanism (casilla 17 negative -> saldo-negativo-fin-periodo
-> carry into casilla 15 the following quarter within the same
ejercicio) is documented in `aeat-modelo-130-instructions` cited
via `source_refs` on the binding and the per-casilla declarations.

The plan's `P04.S15` asked for a verbatim BOE fragment extension
to the legal entry's `required_text`. Because the BOE fragment is
not in the cached corpus and re-fetching is out of session scope,
S15 is closed with this audit as deferral evidence. Follow-up
work to re-fetch RD 439/2007 from BOE and extend `required_text`
with the art. 110.5 verbatim sentence is recommended but does not
block:

  - P04.S16 verification (selector + binding load cleanly).
  - P05 regression test suite (asserts runtime behaviour, not
    legal-text-fragment presence).

## Follow-up recommendation

Re-fetch `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a110`
into the corpus pipeline, identify the carry-forward sentence in
the consolidated text, and extend
`[legal."rd-439-2007:art-110"].required_text` with the verbatim
fragment. Cross-check that the AEAT Manual de la Renta para
empresarios y profesionales 2025 cites the same article paragraph
to confirm the substrate.

---

## P07.S40 finding: M036 manifest informational-exclusion validated

S26 removed `vigencia` (M036 casilla declared with `input_kind =
"informational"`) from the calculation-completeness manifest. The
honesty review at 2026-05-27 questioned whether the fix matched
the architectural rule or just the test expectation.

**Resolution**: validated against the documented closure rule in
`_record_design.py:1299-1346` (`calculation_closure_numbers`
docstring). The calculation closure is the set of casillas the
engine traverses: formula targets, formula-expression refs,
formula/binding endpoints, verification operands. A casilla
declared with `input_kind = "informational"` and NO `formula` and
NO `binding` and NOT referenced by any formula expression and NOT
named as a verification operand is, by definition, outside the
closure.

`decl.vigencia-2025` carries `input_kind = "informational"`, no
`formula`, no `binding`, and is not referenced by any formula
expression or verification expectation in M036's revision. It is
correctly excluded from the calculation closure and therefore
correctly absent from the calculation-completeness manifest.

The S26 fix is architecturally sound; the manifest gate firing
on the prior `vigencia` entry was correctly catching real drift,
not a false-positive. No revisit needed.

---

## P07.S41 finding: registry-wide provisional_pending_specimen inventory

Sweep of every extraction profile across every modelo for the
`provisional_pending_specimen = true` flag and the
`src/aeat/tests/fixtures/justificantes/{modelo}/` specimen
inventory:

**Specimen coverage**: every modelo (M036, M100, M111, M115, M123,
M130, M131, M180, M184, M190, M193, M232, M303, M347, M349, M369,
M390, M720, M840) has at least one specimen PDF committed under
`src/aeat/tests/fixtures/justificantes/`. No modelo is missing a
specimen.

**`provisional_pending_specimen = true` flag set on**:

- `src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2026/extraction_profiles/0001-extraction_profiles.toml`

All three modelos already have specimen PDFs in the fixtures
directory (M111: `2024-1T.pdf`, M130: `2021-2T.pdf`, M131:
`2024-1T.pdf`). Per `test_corpus_round_trip_gate.py`'s shape
test, the flag is opt-out (specimen + flag = OK; specimen
without flag = required round-trip; no specimen without flag =
hard fail).

**Disposition**: the flag on these three profiles is structurally
redundant (the specimen alone satisfies the gate). It may signal
that the specimen exists but is synthetic or unverified against
the corpus round-trip path — in which case the flag is the
author's deliberate opt-out from round-trip verification while
the specimen ages into authenticity. The flag is NOT a defect.

**Follow-up recommendation**: each of the three profiles should
either (a) remove the flag if the specimen is corpus-verified
and round-trips cleanly, or (b) keep the flag with a brief
comment explaining the specimen's provisional nature. Not
tracked as a new Step — author-driven authenticity review is
out of scope for a structural hardening sweep.

---

## P07.S38 finding: M131 carry-forward semantics validated against AEAT

The AEAT Modelo 131 instructions at
`src/aeat/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html`
declare the carry-forward rule for casilla 11 verbatim:

> Casilla 11. Si en la casilla 10 anterior se hubiera obtenido
> una cantidad positiva, se hará constar en la casilla 11 el
> importe (sin signo) de los resultados negativos que, en su
> caso, se hubieran obtenido en la casilla 15 de cualquiera de
> las autoliquidaciones anteriores, modelo 131, del mismo
> ejercicio y que no hubieran sido deducidos anteriormente,
> teniendo en cuenta que en ningún caso podrá figurar en la
> casilla 11 un importe superior a la cantidad positiva
> consignada en la casilla 10.

The registry binding lands:

- `source_modelo = "131"` — autoliquidaciones anteriores modelo 131 ✓
- `source_output = "saldo-negativo-fin-periodo"` — prior period
  saldo seed (formula: `max(0, -C10)`) ✓
- `source_period_offset_from_target = -1` — anterior (prior) ✓
- `max_year_delta = 0` — "del mismo ejercicio" same-ejercicio
  constraint ✓
- 1T suppression — 1T has no prior period in the same ejercicio ✓

**Verified**. The four M131 cap revisions (2019-2023, 2024,
2025, 2026) match the AEAT rule structurally.

**Discovered defect not in scope of S38**: the AEAT cap "en
ningún caso podrá figurar en la casilla 11 un importe superior
a la cantidad positiva consignada en la casilla 10" is NOT
enforced. The binding aggregates `op = "copy"` which strait-
copies the prior period's seed; if the seed exceeds the current
period's C10, the AEAT cap is violated. This is a verification-
predicate gap, not a binding-selector defect. Recommended
follow-up: declare a verification predicate that asserts C11 ≤
C10 when C10 is positive, OR clamp the binding via an
aggregation operator that caps to a current-period casilla
reference (no such aggregation op exists today). Tracked
informally here; the M131 calculation contract for the cap
rule needs its own ADR/plan if AEAT-cap enforcement is in scope
for a follow-up campaign.
