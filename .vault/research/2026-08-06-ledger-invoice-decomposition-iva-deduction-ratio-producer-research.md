---
tags:
  - '#research'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:505b550f7f78a4502a33e38da5016e0859028056202fa07acc84076b06b8fc05'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# `ledger-invoice-decomposition` research: `iva_deduction_ratio producer design (open, unresolved)`

`RentaDeductibilityContext.iva_deduction_ratio` (introduced with the base+IVA
join fix) is `None` in every production path today — nothing populates it. This
document investigates what a producer would look like and finds two questions
that resolve to distinct, unresolved sub-decisions rather than to an
implementable answer: (1) whether a wholly-exempt taxpayer's zero-deduction-right
state can be derived at all, and (2) where the resulting new declared fact
should live. Neither is decided here. No implementation Step should open
against either half until an ADR settles them; the extraction named in Finding
C is its own prerequisite Step once ruled on, independent of this document.

## Findings

### A. `ProrrataRegister`'s shape supports a single scalar only for the non-sectorized taxpayer

`domain.prorrata_register.ProrrataRegister` keys entries on `(ejercicio,
sector_id)`; `sector_id=None` is the whole-entity entry, used whenever
`register.is_sectorized` is `False` (`__init__.py:415-423`). For that common
case a single `Decimal` ratio per ejercicio is a sufficient shape. A sectorized
register (LIVA arts. 9.1.c/101 differentiated sectors) carries a distinct
percentage per declared sector (`ProrrataRegisterEntry.sector_id`,
`__init__.py:147-211`), and nothing in the renta expense pipeline identifies
which sector a given expense belongs to.

### B. `RentaDeductibleExpenseFact.activity_key` does not correspond to a prorrata `sector_id` — a tracked gap, not a scoping note

`activity_key` (`application/aggregation/_renta_ledger.py:299,315-316`,
default `"default"`) is documented as "Activity identifier carried through to
the produced observations' provenance" — a renta-side labelling concept with no
declared relationship to the IVA `sector_id` axis (LIVA art. 9.1.c: distinct
CNAE groups, régimen especial membership, arrendamiento financiero, cesión de
créditos). No code maps one to the other. Both are colloquially "a sector" for
a multi-activity taxpayer, and nothing prevents a future reader from assuming
they correspond. **They do not correspond today, and no evidence found
suggests they are the same partition even conceptually** (renta activity_key
scopes M100/M130 casilla routing; IVA sector_id scopes a legally distinct
deduction-right partition per art. 9.1.c). A sectorized taxpayer is therefore
out of scope for any first producer design pending a resolved mapping between
the two axes — recorded here as a standing gap, not merely deferred.

### C. A wholly-exempt taxpayer generally has NO `ProrrataRegisterEntry` at all — the register cannot answer the motivating case

LIVA art. 102.Uno defines prorrata as applying when a taxpayer performs
operations WITH and WITHOUT the right to deduct TOGETHER
(`core/_prorrata_register.py:39-60` mirrors this: `ProrrataRegisterRegime`
members are `GENERAL`, `ESPECIAL`, `NINGUNA` — `NINGUNA` documented as "the
taxpayer performs only operations that grant the right to deduct", i.e. FULL
deduction, not zero). A taxpayer whose activity is wholly exempt under LIVA
art. 20 (e.g. the médico radiólogo of the AEAT Manual práctico Renta 2024
caso práctico grounding the #51 fix,
`corpus/manuals/renta/2024/part1/source.pdf.extracted.md:19810-19947`) performs
no operations with the right to deduct at all, so there is nothing to
register: no entry, of any regime, is expected to exist for that ejercicio.
Reading the register for this taxpayer resolves to "absent entry" —
indistinguishable, from the register alone, from "operator simply never
recorded a prorrata state because none was needed" for an ordinary
fully-taxable taxpayer. **The register structurally cannot represent
"activity has zero right to deduct, full stop"; it only represents "mixed" or
"fully entitled" states.** Confirmed no other domain surface fills this gap:
`domain.user_profile`, `domain.contribuyente` (`TaxResidenceProfile`), and the
censal certificate (`domain/censo/_certificado.py:56` — a bare
`epigrafe_iae: str`, no derived exemption classification) carry no per-activity
"wholly exempt from IVA" fact.

### D. M303's existing register consumer treats an absent/NINGUNA answer as "no restriction" — the opposite null convention from what #51 needs

`application/aggregation/_iva_ledger.py`'s `_active_prorrata_apportionment`
(:826-868) and `_sector_scoped_apportionment` (:871-897) load the register via
`ProrrataRegisterRepository(bucket_id).load()` and return `None` when the
entry is absent, its regime is `NINGUNA`, or no percentage resolves; callers
of that `None` (`_apply_general_apportionment` area, :640-661) treat it as "no
apportionment restricts the deducible cuota" — i.e. full deduction assumed.
That is the correct reading for M303, where "no register state" legitimately
means "nothing restricts this taxpayer's deduction" for the vast majority of
fully-taxable filers. It is the WRONG reading for `iva_deduction_ratio`, whose
contract (established with #51) is `None` = not evaluated, never silently
coerced to `Decimal("1")`. Reusing `_active_prorrata_apportionment`'s return
value directly would launder this exact category error into the renta path.
Any producer must consume the SAME underlying register data through the SAME
regime-interpretation logic, but keep its OWN, distinct null semantics on top
— reuse at the data/logic layer, not the return-value layer. The
regime-interpretation logic itself is private to `_iva_ledger.py` today; a
second, independent reimplementation of "what does NINGUNA/GENERAL/ESPECIAL
mean" in a new renta module would create the exact two-producers-of-one-legal-
question shape this campaign has already found and rejected elsewhere
(same-named predicates answering one legal question to different standards).
`application.prorrata_register` (`__init__.py`, currently `_seed.py` and
`_sector_lifecycle.py`) is the existing shared package that could host a
promoted, public version of this interpretation for both `_iva_ledger.py` and
a future renta producer to call — an extraction that is itself a prerequisite
Step, verified for behavioural equivalence on `_iva_ledger.py` before any
renta-side wiring lands on top of it. Not scoped or opened here.

### E. The register's percentage is annual and two-valued (provisional/definitive); M100 and M130 sit at different points in that lifecycle

`ProrrataRegisterEntry` carries both a `provisional_percentage` (in force
during the year's liquidations, LIVA art. 105.Uno/Dos/Tres) and a
`definitive_percentage` (settled at year-end regularización, art. 105.Cuatro;
`__init__.py:171-190`). M130 (`application/aggregation/_renta_ledger.py:300,
317-318` — `modelo: str = Modelo.M100.value` also accepts `"130"`) is filed
quarterly, intra-year, when only the provisional percentage can exist — the
same value M303's own quarterly liquidations use. M100 is filed the following
year, by which point the ejercicio's regularización (`application/calculations
/_prorrata_regularizacion.py`) should have settled the definitive percentage.
A producer that always read provisional would understate M100's ratio
relative to the settled truth; one that required definitive would return
`None` for every M130 filing during the year it covers. Not investigated:
what a design should do for an M100 filed before its ejercicio's
regularización has actually run (a real ordering hazard, since nothing
enforces regularización-before-M100 sequencing today) — named as an open
question for whichever ADR settles this, not answered here.

### F. Two sub-decisions must be ruled by an ADR before any Step opens; neither is decided in this document

1. **Can "wholly exempt, zero right to deduct" be derived, or must it be a
   new declared taxpayer fact?** Finding C found no derivable signal anywhere
   in the domain layer. This campaign's own precedent for VIES registration
   state and permanent establishment is to record a legal fact only when the
   operator declares it, never infer it. This document does not decide
   whether the same posture applies here, only that no evidence supports
   deriving it.
2. **Where would such a fact live?** A schema-surface decision (`TaxpayerProfile`
   vs. `TaxResidenceProfile` vs. a new per-activity model) that this document
   explicitly declines to make — it carries a blast radius across the profile
   schema and belongs alongside the other declared-fact questions this
   campaign has accumulated (VIES verification state, permanent establishment,
   `total_amount` semantics), ruled together rather than piecemeal.

## Sources

- `src/cadrumo/domain/prorrata_register/__init__.py:147-211,415-423` — `ProrrataRegisterEntry`, `ProrrataRegister.is_sectorized`.
- `src/cadrumo/core/_prorrata_register.py:39-60` — `ProrrataRegisterRegime` members and their documented meaning.
- `src/cadrumo/application/aggregation/_iva_ledger.py:640-661,826-868,871-897` — `_active_prorrata_apportionment`, `_sector_scoped_apportionment`, and the `None`-means-full-deduction consumer.
- `src/cadrumo/application/aggregation/_renta_ledger.py:299,300,315-318` — `activity_key` and the `modelo` parameter selecting M100 vs M130 deductibility rules.
- `src/cadrumo/application/calculations/_prorrata_regularizacion.py` — the annual settlement path producing `definitive_percentage`.
- `src/cadrumo/domain/censo/_certificado.py:56` — the bare `epigrafe_iae: str`, no derived IVA-exemption classification.
- `src/cadrumo/domain/renta/_ledger_expenses.py` — `RentaDeductibilityContext.iva_deduction_ratio` and its `None`-means-not-evaluated contract, established alongside the #51 fix this document follows up on.
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:19810-19947` — AEAT Manual práctico Renta 2024 médico radiólogo caso práctico, the wholly-exempt worked example motivating Finding C.
