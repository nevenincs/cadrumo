---
tags:
  - '#research'
  - '#modelo-145-reopen'
date: '2026-06-04'
modified: '2026-06-29'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]"
---

# modelo-145-reopen research: M145 registry authoring readiness

This research scopes Phase P03 (Steps S11 through S15) of the M145 reopen plan.
It inventories what is ready to author today in registry/aeat/modelos/145/ and
what still has to land before a registry TOML can be committed.

## Findings

### Official AEAT sources (status: corpus + catalogue already landed in P01)

The M145 source corpus and legal/modelo-145.toml catalogue entries were
deposited by P01.S01 through P01.S06. Cross-checked against disk:

- AEAT G603 procedure page as aeat-modelo-145-procedure (sha256 705c93ec,
  retrieved 2026-05-14, applies_from 2025-02-19).
- AEAT obligaciones-retenedor M145 page as
  aeat-modelo-145-obligaciones-retenedor (sha256 3bd409c2, applies_from
  2026-03-16).
- AEAT current form PDF as aeat-modelo-145-form (mod145_es_es.pdf,
  sha256 2061c003, 123230 bytes).
- AEAT record design as aeat-dr-145-v20 (dr145v20.pdf, sha256 fe29e8df,
  applies_from 2012-01-31). First record carries the T145010 model/page id.
- BOE approving resolution as boe-modelo-145-2011-approval plus
  resolucion-dgt-2011-01-03-modelo-145:aprobacion legal entry
  (BOE-A-2011-208, published 2011-01-05).
- BOE 2013 amendment as boe-modelo-145-2013-amendment (BOE-A-2014-59,
  effective 2014).
- BOE 2014 amendment as boe-modelo-145-2014-amendment (BOE-A-2014-13679,
  effective 2015).

BOE-A-2008-20487 is intentionally NOT catalogued (derogated; the ADR allows
it only as historical lineage commentary, never as a binding source).

### Legal grounding chain

The binding chain for the M145 surface:

- ley-35-2006:art-99 (LIRPF Art. 99, obligation to retain on rendimientos
  del trabajo). Present in legal/irpf.toml.
- ley-35-2006:art-88 (LIRPF Art. 88, communication of personal/family data
  governing the withholding rate). Present in legal/irpf.toml.
- rd-439-2007:art-88 (Reglamento IRPF Art. 88, the article AEAT
  mod145_es_es.pdf cites as the form regulatory anchor). Present in
  legal/irpf.toml with corpus_ref
  corpus/normatives/html/rd-439-2007-art-88.html#a88. Currentized
  2026-06-29: this is no longer a catalogue blocker for P03 casilla
  legal_refs.
- resolucion-dgt-2011-01-03-modelo-145:aprobacion (BOE-A-2011-208) plus
  the two amendment entries above. These establish the form itself and
  are ready to cite as modelo.legal_refs and revision.legal_refs.

### Closed-value axes M145 needs

From dr145v20.pdf field order and mod145_es_es.pdf form sections:

- Situacion familiar, three variants: 1 soltero/viudo/divorciado con hijos;
  2 casado con conyuge sin rentas superiores a 1.500 EUR; 3 otra. NOT the
  same enum as SituacionFamiliar in domain/contribuyente/_renta_codes.py
  (that one encodes Art. 82 conjunta eligibility). M145 axis is a payer
  communication trinary defined by Art. 81 LIRPF retencion brackets and
  MUST be a new closed enum, not a reuse.
- Descendientes count plus per-descendant discapacidad grade. The
  discapacidad axis is substitutable with RentaDisabilityGrade (also in
  _renta_codes.py): identical 5-value semantic surface from Art. 60
  LIRPF. Reuse.
- Ascendientes count plus per-ascendiente discapacidad grade. Same
  RentaDisabilityGrade reuse applies.
- Taxpayer disability grade. Same reuse.
- Pension compensatoria and anualidades por alimentos (boolean plus amount).
- Vivienda habitual housing payment (boolean plus fecha de adquisicion
  pre-2013, to determine deduccion transitoria eligibility).
- Movilidad geografica and prolongacion vida activa flags.

All axes are STATE authority (LIRPF/RIRPF). No CCAA-specific surfaces
appear on dr145v20.pdf. The form is fully state-scoped; no CCAA
discriminator required.

### Minimum casilla set for registry load and export validation

The dr145v20.pdf field layout maps to roughly 28-32 casillas grouped as:

- Section identificacion (4): NIF perceptor, apellidos y nombre, fecha de
  nacimiento, NIF representante legal (when applicable).
- Section situacion_familiar: 1 selector plus 3 conditional NIF/fecha fields.
- Section descendientes: count plus up to N child rows; each row carries
  fecha nacimiento/adopcion, discapacidad, computo-entero flag.
- Section ascendientes: count plus per-row fecha nacimiento, discapacidad,
  convivencia.
- Section discapacidad_perceptor: grade plus movilidad-reducida flag.
- Section pensiones: pension_compensatoria_amount and
  anualidades_alimentos_amount.
- Section vivienda_habitual: boolean plus fecha_adquisicion.
- Section firma: fecha plus firma perceptor.

Every casilla can be input_kind = manual (the form is a manual data
communication; nothing is computed). export_refs MUST point at
dr145v20.pdf fixed-position field ids (T145010 plus per-section fixed
offsets the record design specifies). legal_refs cite the BOE-A-2011-208
primero clause plus the LIRPF/RIRPF article governing the specific
reduction the field unlocks.

### Reusable enums and schemas

- RentaDisabilityGrade (src/aeat/domain/contribuyente/_renta_codes.py:37):
  exact 5-value match for every M145 discapacidad field. Reuse.
- Registry InputKind (registry/_schema.py:96): every M145 casilla is
  MANUAL. Reuse.
- Registry ApplicationLinkSurface: P02.S08 already added communication
  and payer_delivery surfaces (_schema.py:1143-1144). M145 application
  links MUST use these and MUST NOT cite filing, deadline, live, or portal
  per P02.S09 validator rules.
- Registry cadence Literal (_schema.py:2436): five values (monthly,
  quarterly, annual, ad_hoc, profile_based). No communication cadence
  exists; ad_hoc is the cleanest fit for M145 (per the prior research
  Design Implication).
- Per-revision authoring shape: modelos/130/revisions/2019-y-siguientes/
  is the cleanest reference. Per-revision directory split into casillas/,
  bindings/, formulas/, export_layouts/, verification_expectations/,
  completeness_manifest/, application_links/, extraction_profiles/. M145
  OMITS bindings/ (no ledger-derived values), formulas/ (no computed
  casillas), deadline_windows/, live_cross_references/, and
  workbook_parity_refs/ (no calc workbook).
- SituacionFamiliar in _renta_codes.py is NOT reusable for M145
  (different semantic axis: Art. 82 conjunta vs. Art. 81 retencion
  brackets).

## Design Implications

P03 can author registry/aeat/modelos/145/manifest.toml plus a single
revision directory 2015-y-siguientes/ (the 2014 BOE-A-2014-13679 amendment
is the last substantive change). The revision uses cadence = ad_hoc, a
year-only period_selector, and casillas all input_kind = manual with
export_refs keyed to dr145v20.pdf field positions. The application_links
directory MUST declare only communication and payer_delivery surfaces.
The earlier rd-439-2007:art-88 legal-catalogue blocker is closed as of
2026-06-29.

## Recommended Decision

P03 (S11 through S15) is ready to author. The previous legal-catalogue gap
for rd-439-2007:art-88 is closed: the legal entry is present in
legal/irpf.toml, points at the bundled RIRPF article 88 corpus excerpt, and
can be cited directly by M145 casilla legal_refs.

A new SituacionFamiliarM145 StrEnum (3 values) must be added under
domain/contribuyente/ (or under a new M145-specific module) before any
casilla cites it as a value-domain constraint.

## Concrete Implementation Scope

- Cite legal "rd-439-2007:art-88" from M145 casillas where the AEAT form's
  Reglamento IRPF anchor applies.
- Author domain/contribuyente/_m145_codes.py (or extend _renta_codes.py)
  with SituacionFamiliarM145 StrEnum (3 values per Art. 81 LIRPF).
- Author _data/registry/aeat/modelos/145/manifest.toml.
- Author _data/registry/aeat/modelos/145/revisions/2015-y-siguientes/
  tree with revision.toml, casillas/0001-casillas.toml,
  export_layouts/0001-export_layouts.toml,
  application_links/0001-application_links.toml,
  completeness_manifest/0001-completeness_manifest.toml,
  verification_expectations/0001-verification_expectations.toml.
  OMIT bindings/, formulas/, deadline_windows/,
  live_cross_references/, workbook_parity_refs/.
- Add test_modelo_145_registry.py covering: load, source grounding,
  communication and payer_delivery surfaces only, NO filing/deadline/
  live/portal surfaces, every casilla legal_refs resolves to the
  catalogue, every export_refs resolves to dr145v20.pdf positions.
