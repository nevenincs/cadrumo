---
tags:
  - '#research'
  - '#modelo-721-cripto-data-fidelity'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-720-prior-year-baseline-adr]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - "[[2026-05-27-m721-informativa-criptomonedas-research]]"
---



# `modelo-721-cripto-data-fidelity` research: `modelo 721 cripto-exterior data-fidelity twin of 720`

This research grounds the A5 mechanism for Modelo 721 (declaración informativa
sobre monedas virtuales situadas en el extranjero) within the multi-year-renta
authorization campaign. The headline finding: Modelo 721 is the **structural twin
of Modelo 720** — an annual informativa with no calculation engine, governed by the
same two-threshold obligation logic (>€50.000 initial; re-declare only if the
aggregate rose >€20.000 over the last-declared baseline). The A3 / 720 mechanism
therefore transfers to 721 essentially verbatim, with the asset-class axis replaced
by a per-custodian axis.

The research also surfaces a **critical, load-bearing data defect**: the in-repo
legal registry that a future 721 casilla author would trust is `review_status =
"reviewed"` but was authored against the **wrong BOE document**. Correcting it is the
mandatory first step of the mechanism, recorded here and decided in the sibling ADR.

Every assertion below was re-verified on 2026-06-02 against the in-repo registry, the
in-repo legal corpus, and the BOE itself; the prior vault research
(`2026-05-27-m721-informativa-criptomonedas-research`) is **superseded** because it
repeats the same three legal errors and overstates the declarable scope.

## Findings

### The critical legal-registry defect (mechanism step one)

`src/aeat/_data/registry/aeat/legal/monedas-virtuales.toml` is marked
`review_status = "reviewed"` (reviewed 2026-05-27) yet registers Modelo 721 under the
**wrong order and wrong BOE identifier**. Verified against the BOE:

- The file uses `orden-hfp-887-2023:art-1/2/3` with `document_id = "BOE-A-2023-18679"`.
- **Orden HFP/887/2023 is `BOE-A-2023-17430` and approves models 172 and 173**
  (custodian-side balances and operations), NOT Modelo 721.
- **Modelo 721 is approved by Orden HFP/886/2023 = `BOE-A-2023-17429`** (de 26 de
  julio; BOE núm. 180, 29-VII-2023).
- `BOE-A-2023-18679` is neither order — it is a spurious identifier.

Two further errors in the same file:

- `[legal."ley-11-2021:da-10"]` anchors the obligation to Ley 11/2021 DA-10. The
  obligation Ley 11/2021 created was the insertion of **letra d into the existing
  Disposición adicional decimoctava of Ley 58/2003 (LGT)** — the *same* DA-18 that
  grounds Modelo 720, a *different letra*. The canonical anchor is therefore
  `ley-58-2003:da-18` (letra d), consistent with 720's `ley-58-2003:da-18`. The
  `ley-11-2021:da-10` slug as written mis-states the legal home of the obligation.
- The `notes` on `orden-hfp-887-2023:art-3` and on `ley-11-2021:da-10` state the
  first declaration corresponds to **ejercicio 2022**. The BOE confirms Orden
  HFP/886/2023 was **first applicable to ejercicio 2023** (filed 1 Jan – 31 Mar
  2024). First ejercicio is **2023**, matching the existing empty scaffold's revision
  anchor `2023-y-siguientes`.

The one anchor that is correct is `rd-1065-2007:art-42-quater` (introduced by RD
249/2023), the reglamento base — though its `notes` repeat the DA-10 mis-anchor and
should be cleaned up.

**Why this is higher-risk than an empty file:** a casilla author building the 721
registry from this file would pull the fichero diseño de registro from the wrong
order's HTML (`corpus_path` and `source_url` on both `boe-modelo-721-2023-form` and
`boe-modelo-721-2023-layout` point at `orden-hfp-887-2023.html` /
`BOE-A-2023-18679`), producing a registry built against models 172/173's layout. A
`reviewed` stamp signals "trust me"; the cross-check that should have caught this
(does the document actually describe Modelo 721?) was not applied. This is precisely
the trust-but-verify failure the `fixture-provenance-declared-in-sidecar` discipline
exists to prevent, here at the legal-source layer.

The correct registration (the W06 coder's edit, mandated by the ADR):

- Replace `orden-hfp-887-2023:art-1/2/3` with `orden-hfp-886-2023:art-1/2/3`, all
  `document_id = "BOE-A-2023-17429"`, permalinks/corpus_refs re-pointed at
  `BOE-A-2023-17429`.
- Re-anchor the statutory obligation to `ley-58-2003:da-18` (letra d); retire or
  correct the `ley-11-2021:da-10` slug.
- Fix the first-ejercicio notes from 2022 to 2023.
- Re-point the two `sources` (`boe-modelo-721-2023-form`, `-layout`) and re-register
  the fichero layout source (`aeat-dr-721` analogous to `aeat-dr-720`) against the
  correct order before any casilla offsets are authored.

### 721 is a data-fidelity twin of 720 (no calculation engine)

Modelo 720 declares **zero formulas** — it is a pure informativa: manifest, revision,
casillas (declarante section + per-asset detail), a €50.000 threshold parameter, the
`foreign_asset` row bindings, and the prior-year baseline / advisory mechanism from
the A3 ADR. Modelo 721 carries the identical shape. RD 1065/2007 **art. 42-quater**
mirrors the 42-bis / 42-ter / 54-bis structure of 720: a >€50.000 aggregate initial
obligation and a re-declaration obligation only when the aggregate at 31-December rose
more than €20.000 over the last-declared value.

The 721 registry must be built from scratch (only empty directories exist today under
`modelos/721/revisions/2023-y-siguientes/`), mirroring 720: `manifest.toml`
(`tax_domain = "informative"`, `cadence = "annual"`), `revision.toml`
(`period_selector = { year_from = 2023, periods = ["0A"] }`, anchor
`2023-y-siguientes`), the casilla set from the HFP/886/2023 fichero diseño,
two threshold parameters, the per-custodian baseline bindings, and the advisory
predicate.

### Scope nuance: only third-party-custodied crypto abroad is declarable

The prior research overstated scope: its "Section C — self-custody wallets" is **not
declarable** under Modelo 721. The declarable population is **virtual currencies held
abroad through a third party that custodies the private keys** (foreign exchanges,
custodial-wallet providers). Self-custody / cold-wallet holdings where the taxpayer
holds the keys exclusively are **out of scope** (they fall under the domestic
172/173 custodian regime or are not 721-declarable). The 721 per-record key is
therefore **custodian + token**, not asset-class + country as in 720.

### The A3 mechanism transfers verbatim (with the per-custodian axis)

- **Initial threshold (€50.000):** mirror 720's `modelo-720-asset-declaration-threshold-eur`
  parameter as `modelo-721-asset-declaration-threshold-eur` (value 50000.00), grounded
  on `rd-1065-2007:art-42-quater`. (720 holds this as a registry parameter, not the
  `external_constants.py` constant; 721 follows the same registry-parameter pattern.)
- **Re-declaration increment (€20.000):** add `modelo-721-redeclaration-increment-threshold-eur`
  (value 20000.00). 720 does not yet carry an explicit €20.000 parameter (the A3 ADR
  adds it as a core constant); 721 authors it as a registry parameter from the outset,
  keeping the threshold a single authoritative registry value the oracle asserts
  against.
- **Prior-year per-custodian baseline binding:** a `previous_filing` binding with
  `source_modelo = "721"`, `filing_year_delta = -1`, `period = "0A"`, singular
  `source_output` naming the per-custodian prior-year aggregate, `aggregation =
  { op = "copy" }`. This is the verified A3 shape — `_PreviousModeloSelector` supports
  `filing_year_delta = -1` and the singular `source_output` + `op = "copy"` copy
  shape, and forbids any `grouping` key (so the per-custodian fan-out is authored as
  the closed-set-of-custodians-on-the-filing rows, not a dynamic grouping kind, exactly
  as 720's three fixed per-category bindings replace a dynamic per-class grouping).
- **ADVISORY re-declaration predicate:** identical posture to the A3 / M200 advisory —
  fire a non-blocking finding when a custodian's prior-year baseline is present, its
  current aggregate exceeds the baseline by more than €20.000, and the custodian is
  absent from the current declaration. Never BLOCKING (growth ≤ €20.000 legitimately
  need not re-declare). As with A3, no existing predicate operator expresses the
  cross-year-baseline delta, so the ADR inherits A3's open design point: one new
  ADVISORY operator vs a derived-casilla formulation, registered against
  `KNOWN_VERIFICATION_PREDICATE_OPERATORS` so a typo cannot silently pass.

### Corrected legal references for the 721 registry

The manifest/revision `legal_refs` (after the corpus correction lands):
`["ley-58-2003:da-18", "rd-1065-2007:art-42-quater", "orden-hfp-886-2023:art-1",
"orden-hfp-886-2023:art-2", "orden-hfp-886-2023:art-3", "ley-58-2003:art-93"]`.
First ejercicio 2023, revision `2023-y-siguientes`. `source_refs` need the corrected
`aeat-dr-721` fichero-layout source and `boe-modelo-721-2023-form` re-pointed at
`BOE-A-2023-17429`, plus the existing `aeat-modelo-721-procedure` instructions source.

### Two-year enrollment scenario (statute-grounded oracle)

Cloning the real-adapter pattern of `test_modelo_130_carry_forward_continuity.py`
(real SQLite, real `ValidatedRegistryAuthority`, real previous-filing resolver, no
mocks):

- **Year N:** declare one custodian holding €60.000 of crypto abroad (> €50.000 →
  obligated).
- **Year N+1, firing leg:** the same custodian now €85.000 (+€25.000 > €20.000 →
  re-declaration required); assert the advisory fires.
- **Year N+1, control leg:** a custodian that grew ≤ €20.000 (e.g. €65.000 from
  €55.000); assert the advisory does NOT fire.

Invariants: the per-custodian baseline auto-resolves N→N+1 via `filing_year_delta =
-1`; the advisory fires for the >€20.000 custodian and not the control. The
€50.000 / €20.000 thresholds are statute-checkable, so the oracle is genuine
threshold logic, not a tautological structure check, and the recorder observes two
distinct renta years to satisfy the foundational gate's un-fakeable two-year contract.

### Sequencing within W06

721 is pure TOML authoring plus the A3-pattern binding — no engine. The hard
prerequisite is the legal-corpus correction: register `BOE-A-2023-17429` /
Orden HFP/886/2023 (and the `aeat-dr-721` fichero source) **before** any casilla
offsets are authored, or the registry will be built against the wrong document. This
makes the corpus correction the literal first step of the mechanism.
