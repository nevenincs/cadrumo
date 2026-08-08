---
tags:
  - '#adr'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ce2820f6a118ab1139827e9fec30de8d462c5633c9bfb85c221ee091e325f7c7'
related:
  - "[[2026-08-08-m200-export-envelope-tag-reference]]"
---

# `m200-export-envelope-tag` adr: `reconstruct the M200 fichero-BOE envelope open/close tags` | (**status:** `accepted`)

## Problem Statement

Every Modelo 200 fichero-BOE export this application has ever produced carries
no opening envelope tag, no `<AUX>`/`</AUX>` markers, and no closing envelope
tag — AEAT's own diseño de registro requires all three
(`m200-export-envelope-tag-reference`, "What AEAT's own spec says"). The
registry collapsed the entire 17-byte open-tag composite into a single bare
`filing_year` draft field, and declares no record at all for the 18-byte close
tag (`m200-export-envelope-tag-reference`, "What the current M200 registry
declares"). This is larger than the sibling NIF-misbinding defect
(`2026-08-07-m200-export-nif-misbinding-adr`): that defect corrupted one
field's content; this one omits six required literal/tag components across the
whole file, for every filer, on every export produced today. It requires a
decision now for the same reason: every day of delay ships another
structurally malformed official filing.

## Considerations

- AEAT's diseño (`m200-export-envelope-tag-reference`, "What AEAT's own spec
  says") is unambiguous: row 1 (open, 17 bytes) and row 13 (close, 18 bytes)
  are both `Constante` fields with explicit byte-level example content. This
  is not inferred by analogy with Modelo 111 — the M200-specific sheet states
  it directly.
- Modelo 111's existing six-field open-tag composition plus its separate
  `envelope_footer` record (`m200-export-envelope-tag-reference`, "Modelo
  111's sibling composition") is a working, already-shipping precedent for
  exactly this shape, differing from M200 only by one inserted one-character
  discriminante component.
- `_computed_field_value`'s existing `envelope_closing_tag` template already
  renders the byte-identical close-tag shape AEAT's M200 spec shows, including
  the hardcoded discriminante default of `"0"`
  (`m200-export-envelope-tag-reference`, "Row 13's example"). No application
  code changes are required to produce M200's closing tag; only a new export
  record needs to invoke the existing computed key.
- The discriminante (entity accounts-regime code) is a genuinely new concept —
  no casilla, binding, or profile field for it exists anywhere in the domain
  model (`m200-export-envelope-tag-reference`, "The discriminante is a new,
  currently-unmodeled concept"). `aeat-architecture-boundaries` requires a
  closed value set to be a typed `StrEnum`/`Literal`, which this application
  cannot yet populate from any profile fact, since it only ever built the
  Normal/Abreviado/PYMES casilla set.
- `aeat-registry-authority-flow` and `aeat-calculation-grounding` require
  production values to route through the registry authority and cite the
  binding provision; `_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS` is the registry-build
  gate that would have caught this defect class at authoring time, and its
  `filing_year` abstention states this exact divergence as its reason,
  explicitly conditioned on a restructuring decision landing first
  (`domain/calculations/registry/_validate_exports.py:86-97`).
- `modelo-export-mirrors-official-structure` and `no-silent-under-declaration`
  both bear: a structural divergence from AEAT's layout is a hard failure, not
  a warning, and the current state ships silently wrong bytes with a
  byte-shaped, validly-digested file — no signal reaches the operator today.

## Considered options

**Open-tag restructuring.** (A, chosen) Replace the single 17-character
`filing_year` draft field with the six-component composite Modelo 111 already
uses, adapted for M200's inserted discriminante: literal `<T`, literal `200`,
literal `0` (discriminante, see below), draft `filing_year`, draft
`period_code`, literal `0000>`. (B, rejected) Widen the existing single field
to a computed key producing the whole 17-byte string in one shot — rejected:
it would hide the composite's sub-fields from field-level provenance
(`legal_refs`/`source_refs` per sub-component) and diverge from how M111
already models the identical shape, creating two conventions for one pattern.

**Close-tag record.** (A, chosen) Add a new `envelope_footer` record reusing
the existing `computed_key = "envelope_closing_tag"`, ordered immediately
after `did` — a pure TOML addition, zero code change, mirroring M111's
`0030-record-envelope-footer.toml` exactly. (B, rejected) Author a new
computed key specific to M200 — rejected: the existing template already
renders M200's exact required bytes; a second computed key for the same
output is a duplicate mechanism `aeat-calculation-aggregation`'s "one
canonical mechanism per type" principle would forbid by the same logic applied
elsewhere in this registry.

**`<AUX>` / program metadata fields.** (A, chosen) Promote the four `filler`
fields at offsets 18, 93, 97, 101 to `literal`/`header` per AEAT's spec
(`<AUX>`, `program_version`, reserved, `presenter_nif`-equivalent NIF empresa
desarrollo), matching M111's already-shipping declarations at the identical
byte positions. (B, rejected) Leave them as filler — rejected: `<AUX>`/`</AUX>`
are AEAT `Constante` markers, not reserved space; leaving them blank is the
same defect class as the missing envelope tags, just smaller, and the fix
costs nothing extra once the record is already being edited.

**Discriminante value.** (A, chosen) Hardcode literal `"0"` (Normal/Abreviado/
PYMES) at both the open-tag literal and via the close tag's existing
hardcoded default, with the limitation stated plainly: any filer under one of
the four other regimes (Aseguradoras, Entidades de crédito, Inversión
colectiva, Garantía recíproca) gets a wrong discriminante byte until that
regime is separately modeled. (B, rejected) Invent a `discriminante` draft
attribute and profile concept now — rejected: no such profile fact, casilla,
or regime-selection UI exists anywhere in this application today; inventing
one under this fix's pressure is exactly the unreviewed-domain-modeling risk
`2026-08-07-m200-export-nif-misbinding-adr` already declined for the grupo
mercantil block, and this application currently has no path to produce a
draft for any regime other than Normal/Abreviado/PYMES, so `"0"` is correct
for every filer it can serve today, not an arbitrary placeholder. (C,
rejected) Block M200 export entirely until discriminante is modeled —
rejected: it would regress every filer this application already correctly
serves to fix a byte that, for all of them, is already correct.

**Discriminante guard.** (A, chosen) A closed-set registry/domain-model scan
asserting no accounts-regime concept (a symbol or field naming any of
Aseguradoras, Entidades de crédito, Inversión colectiva, Garantía recíproca,
or "estado de cuentas") exists outside an explicit allowlist — a value
correct only because a concept is absent must fail the moment that concept
appears, not silently keep rendering `"0"`, the same failure shape as the
defect this ADR fixes. The gate has nothing to enumerate today, so it starts
vacuously green and turns red the first time a future change introduces the
concept, forcing that change to revisit both hardcoded `"0"` sites (the
open-tag literal and `_computed_field_value`'s template) together rather than
one being missed. (B, rejected) No guard, rely on the "Cost / pitfall"
paragraph below being read — rejected: `aeat-quality-gates` requires gates
over vigilance for anything reaching an official filing, and a consequences
paragraph is exactly the kind of prose a future editor skims past. (C,
rejected) A runtime assertion refusing export whenever a regime signal is
present — rejected: no such signal exists anywhere to check today, so the
assertion would have nothing to test against and would read as dead code; the
build-time closed-set scan is the sanctioned no-signal-yet form, mirroring how
`_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS` is already kept total over its declarable
attributes in this same module.

**Gate abstention replacement.** (A, chosen) Once the open tag no longer binds
`filing_year` to a 17-byte slot, flip
`_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS["filing_year"]` from `None` to `4`, closing
the abstention the divergence forced; also flip `["period_code"]` from `None`
to `2` on the newly-read evidence (`m200-export-envelope-tag-reference`,
"Draft-attribute canonical widths") — the abstention's stated reason ("width
not established against the published diseños") no longer holds once this
ADR's grounding reads it. (B, rejected) Gate `filing_year` without fixing the
declaration first — explicitly the trap the dispatch brief named: it would
refuse the registry build with no restructuring path yet landed.

**Severity and urgency framing.** (A, chosen) Treat this as the more severe of
the two live M200 export defects and land it with the same urgency as the NIF
misbinding — every M200 fichero-BOE produced today is missing required AEAT
constants, not merely carrying a wrong-width padded field. (B, rejected) Treat
it as a lower-severity width issue — rejected by the grounding: AEAT's spec
confirms an envelope tag is required, so the current state is a structural
omission, not a cosmetic width mismatch.

## Constraints

- **Registry-only, additive to the M111 pattern.** No new `draft_attribute`,
  `computed_key`, or field `kind` is required; every kind used (`literal`,
  `draft`, `header`, `computed`, `filler`) is already declared and validated
  by `_validate_field_kind` (`_schema_surfaces.py:708-720`).
- **Byte geometry is fixed by AEAT, not chosen.** Offsets 1, 18, 23, 93, 97,
  101, 110, 323 in `page_000`, and the close tag's position immediately after
  all page content, come directly from `DP200000` and must not be
  re-derived or approximated.
- **The discriminante literal is a documented, scoped limitation, not a
  silent gap.** Any future work modeling Aseguradoras / Entidades de crédito /
  Inversión colectiva / Garantía recíproca regimes must revisit both the
  open-tag literal and the close tag's hardcoded `"0"` in
  `_computed_field_value` together — they are the same value rendered twice
  and must not be fixed independently. The closed-set guard test is the
  mechanical enforcement of this constraint: it must fail, not silently
  pass, the moment either site's assumption stops holding.
- **Depends on `2026-07-01-fichero-boe-parity-gate-adr` staying stable**, the
  same registry-build validation surface this ADR's gate-abstention flip
  extends, per the sibling NIF-misbinding ADR's identical constraint.
- **The typed-source-width gate (`_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS`) is a
  shared surface with the NIF-misbinding ADR's follow-up sweep.** This ADR's
  flip of `filing_year` and `period_code` must not weaken or revert that
  ADR's `profile_tax_id` gate or its open follow-up rows.
- **This ADR does not perform the broader diseño cross-check sweep** (every
  other modelo's envelope/header record against its own bundled diseño). It
  is scoped to M200's page-000/close-tag defect only, confirmed against the
  bundled `DP200000` sheet; whether any other modelo has a comparable
  collapsed-composite defect is unswept and opened as a follow-up.

## Implementation

Restructure
`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`,
record `modelo-200-page-000`: replace the single offset-1/length-17 draft
field with six fields — literal `<T` (offset 1, len 2), literal `200` (offset
3, len 3), literal `0` (offset 6, len 1, discriminante), draft `filing_year`
(offset 7, len 4), draft `period_code` (offset 11, len 2), literal `0000>`
(offset 13, len 5) — preserving every field's existing `legal_refs`/
`source_refs`. Promote the offset-18 filler to `literal` `<AUX>` (len 5),
offset-93 filler to `header` `program_version` (len 4, `required = false`),
offset-101 filler to `header` `presenter_nif` (len 9, `required = false`,
matching M111's header key name for the same NIF-empresa-desarrollo concept),
and offset-323 filler to `literal` `</AUX>` (len 6). Offsets 23, 97, 110 stay
`filler` (AEAT-reserved blanks).

Add a new export fragment (numbered after `0077-modelo-200-did.toml`) declaring
record `modelo-200-envelope-footer`, `record_type = "envelope_footer"`, `order
= 77`, one field: offset 1, length 18, `kind = "computed"`, `computed_key =
"envelope_closing_tag"` — the exact shape of M111's
`0030-record-envelope-footer.toml`.

Flip `_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS` in
`src/cadrumo/domain/calculations/registry/_validate_exports.py`:
`"filing_year": 4` and `"period_code": 2`, rewriting both comments to state
what is now established rather than what is abstained, and removing the
`filing_year` comment's forward reference to "this ADR" once it lands.

A byte-level test drives `export_draft` (or `_render_layout`) for a Modelo 200
draft and asserts the first 17 bytes of the `page_000` record equal
`f"<T200{discriminante}{year}{period}0000>"` for a known filing year/period,
and that the fichero's final 18 bytes equal
`f"</T200{discriminante}{year}{period}0000>"` — proof the specific defect is
closed at both ends, test-first: written and confirmed red against current
output before the registry TOML changes, then confirmed green after. A
mutation-proof reverts either restructured field and confirms the assertion
flips red.

A closed-set guard test scans registry TOML symbol names, casilla/binding
ids, and domain-model field names for tokens indicating an accounts-regime
concept (`aseguradora`, `entidad_credito`, `inversion_colectiva`,
`garantia_reciproca`, `estado_cuentas`, `discriminante`, `accounts_regime`)
against an explicit allowlist covering only the two known hardcoded `"0"`
sites; today the scan finds nothing beyond the allowlist and passes
vacuously. A fixture-anchor test proves the guard actually fires: add a
scratch symbol matching one of the tokens outside the allowlist and assert
the guard test fails; remove it.

## Rationale

The chosen restructuring is the minimal change that makes every M200
fichero-BOE export byte-correct against AEAT's own published diseño, using
exclusively field kinds and a computed key this registry already validates and
already renders identically for Modelo 111 — no new schema surface, no new
code path, and (for the close tag) no code change at all. Hardcoding the
discriminante to `"0"` rather than inventing a new domain concept mirrors the
sibling NIF-misbinding ADR's discipline: fix the live defect within the
concepts this application already models, and state the remaining gap
(non-Normal accounts regimes) honestly as a scoped-out follow-up rather than
either blocking the urgent fix or silently under-modeling a regime this
application cannot currently serve anyway. Flipping the two gate abstentions
now, rather than leaving them open, is the direct payoff of finally reading
the diseño the abstention comments named as missing: `filing_year` at 4 and
`period_code` at 2 are no longer unestablished once this reference exists, and
leaving them abstained after fixing the divergence they cite would let the
same defect recur silently.

## Consequences

- **This is a live defect affecting filings produced today, and it is the
  more severe of the two known M200 export defects.** Every Modelo 200
  fichero-BOE ever produced by this application is missing its required open
  envelope tag content, `<AUX>`/`</AUX>` markers, and close envelope tag.
  After this fix, every M200 export carries AEAT's exact required bytes for
  filers under the Normal/Abreviado/PYMES regime — the only regime this
  application can currently produce a draft for.
- **Scope confirmed:** the M200 `DP200000` page-000 diseño, read directly,
  confirms both tags are required and confirms their exact byte composition;
  this is not an inference from a sibling modelo.
- **Scope NOT confirmed / unswept:** whether any other modelo has a comparable
  collapsed-composite or missing-envelope defect. This ADR fixes M200 only and
  opens the broader sweep as a follow-up, consistent with the sibling
  NIF-misbinding ADR's identical honesty discipline.
- **Gain:** closes a structural, whole-file correctness defect with a
  registry-only change plus one code-free record addition, closes two
  registry-build gate abstentions that were explicitly conditioned on this
  fix landing, and adds a closed-set guard so the hardcoded discriminante
  cannot silently outlive the concept-absence that currently justifies it.
- **Cost / pitfall:** any filer under a non-Normal accounts regime
  (Aseguradoras, Entidades de crédito, Inversión colectiva, Garantía
  recíproca) still receives an incorrect discriminante byte at both tag
  positions after this fix — the same limitation the underlying computed
  template already carried, now also present in the open tag, and not closed
  by this ADR. The guard test bounds this cost to "known and gated" rather
  than "known and silently drifting": it fails loudly the day a regime
  concept is introduced, rather than letting the wrong byte persist
  unnoticed past that point.
- **Pathway:** modeling accounts-regime as a typed profile concept is the
  natural next investment once a regime-selection surface exists; the broader
  per-modelo diseño cross-check sweep is the natural next investment for
  finding comparable defects elsewhere.

## Codification candidates

- **Rule note (not a new rule):** the worked lesson — a diseño sheet can exist
  in the bundled corpus under a name a prior sweep did not think to check
  (`DP200000`, not `DP200001`) — belongs beside `aeat-calculation-grounding`'s
  existing "verify against the bundled corpus" guidance if this recurs on
  another modelo; not promoted here per `no-codification`.
