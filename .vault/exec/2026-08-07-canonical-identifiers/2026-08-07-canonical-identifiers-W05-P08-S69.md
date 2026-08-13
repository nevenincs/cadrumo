---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1c5537ba39f324eae577c344ea8d40d278e4e4d45b1ed8524fca1b9e2dc30c35'
step_id: 'S69'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# adjudicate `CasillaDefinition.number` as its own identifier population, separate from `AeatBoxNumber`

## Scope

- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py`

## Description

- Re-measured the population directly against the live registry TOML tree
  rather than trusting the row's own "12,771" figure, per this campaign's
  standing discipline: a flat `number = "..."` grep across
  `_data/registry/aeat/modelos` returns 21,183 raw occurrences (every
  revision year counted separately), of which 6,124 are distinct values.
  The row's figure is a different, unexplained count over the same field;
  neither number is authoritative here, only the shape distribution is —
  re-derived from scratch by walking every `[[revisions."<year>".casillas]]`
  stanza (15,824 of them) and every `completeness_manifest` fragment (4,383
  more) rather than a flat grep, so a value could be attributed to its own
  casilla's `internal_only` flag.
- Classified every value by shape and cross-tabulated against the owning
  stanza's `internal_only` flag, since the row's own hypothesis (the
  `###` marker, asterisk forms, ranges and slugs "may be several concepts")
  needed a real discriminator, not just a shape count. Result, stanza-level,
  non-`internal_only` casillas (15,824 total; `internal_only=true` casillas
  are a separate, tiny, uniform 28-stanza population, 27 slug + 1 other,
  and not this row's concern):
  - **15,222 (96.2%) plain digits** — `"1"`, `"01"`, `"0611"`, `"611"`,
    variable width, no consistent padding. This is the exact shape
    `AeatBoxNumber` (`core/identity/_namespace.py`) already models, and the
    exact shape three sibling fields already alias successfully:
    `CasillaDefinition.form_number`, `_renta_web_open_oracle`'s own
    `display_number`, and `core/observability/_models.py`'s
    `FormFillPayload.display_number`.
  - **~492 (3.1%) descriptive slugs** (`slug_fallback` 225 + `dotted_slug`
    181 + `other` 86) — NOT box numbers at all. Two distinct sub-cases
    confirmed by reading samples: form-metadata header fields with no
    printed box (`"ejercicio"`, `"tipo-declaracion"`, `"vigencia"` on
    Modelo 036/038 declaration-header casillas), and internal computed
    sub-total identifiers reusing dotted semantic-role-shaped paths
    (`"iva.repercutido.general"`, `"iva.autorepercutido.intracomunitaria"`,
    `"impatriado.base-liquidable-general"`) on casillas that are genuine
    calculation targets (hence NOT `internal_only`) but have no AEAT-printed
    box to report.
  - **58 (0.4%) asterisk-prefixed** (`"*01"`, `"*76"`, `"*92"`, ...) — all on
    Modelo 100's personal-identification header casillas
    (`cDNIASDLG.toml`, `cAPENOMDLG.toml`, `cFNACDLG.toml` and siblings). A
    real, distinct AEAT print convention (the datos-del-declarante header
    section numbers its boxes with a leading asterisk to separate them from
    the main numbered casilla sequence), not app-internal and not a
    fallback — but shape-incompatible with `AeatBoxNumber`'s existing
    `^\d+$` pattern.
  - **22 (0.1%) range notations** (`"136-144"`, `"76-77"`, `"*06-09"`) — a
    casilla whose printed representation spans a contiguous run of boxes,
    structurally a pair or interval, never a single scalar number.
  - **1 the literal `###` internal marker, 1 space-separated multi-box
    (`"*68 *69"`)** — both confirmed present, both genuinely singular
    outliers, neither a box number.
  - The `completeness_manifest` fragments (a SEPARATE TOML section,
    `CasillaCompletenessManifestEntry.number`, cross-checked against the
    referenced casilla by the registry's own build validator) carry the
    identical shape mix at a comparable non-digit rate (3944 plain / 439
    non-digit of 4383), confirming the mixing is not confined to
    `CasillaDefinition` — it reaches its manifest counterpart too, because
    the manifest's own scope (formula targets, formula operands, binding
    endpoints, verification operands) legitimately includes the internal
    computed sub-totals that carry dotted-slug `number` values.
- Traced the three named live sites
  (`application/storage/calc_sheets/_parity_comparison.py`'s
  `CasillaParity.display_number`,
  `adapters/outbound/google/_calc_sheets_pull.py`'s `OperatorEdit
  .display_number`, and `application/storage/calc_sheets/_records.py`'s
  `SheetProvenanceRow.display_number`) to their assignment sites
  (`display_number=casilla.number` in `_parity_comparison.py` and
  `_engine.py`; the Sheets pull round-trip in `_calc_sheets_pull.py`,
  itself populated from the same export). All three receive the FULL,
  unfiltered population — every casilla rendered onto a workbook row, not
  only the numbered ones — which is exactly why `W05.P08.S42`'s retype
  attempt on these sites broke against a real test fixture: the population
  they carry is provably not `AeatBoxNumber`-shaped.

## Outcome

ADJUDICATED, no code changed — this row's own gate asks for a decision,
not a retype, and the decision is: **`CasillaDefinition.number` stays
deliberately bare (`str`), and so do its three downstream projections.**
It is at minimum four distinct concepts sharing one field — a true AEAT
box number (96.2%, already `AeatBoxNumber`-shaped and already aliased
wherever a sibling field carries ONLY that subset), a descriptive
metadata/internal-computed-target slug, an asterisk-prefixed
personal-data-header box number, and a multi-box range or list. No single
alias is a valid narrowing: `AeatBoxNumber`'s `^\d+$` pattern is not a
superset of the slug, asterisk or range shapes, so retyping `number`
itself onto it would either reject 3.6% of live registry data outright (a
registry-load-breaking change, not a narrowing) or force widening
`AeatBoxNumber` to admit non-digit shapes — which would let a genuinely
malformed digits-only box number field elsewhere in the codebase (three
sibling fields depend on the current digits-only guarantee) silently admit
a slug or asterisk value it was never meant to. Splitting the registry
schema into separate typed fields (a numeric `AeatBoxNumber | None` plus a
separate reference-slug field) is the only sound long-term fix, but it is
a registry-authoring-tree migration touching 12,697 casilla files across
every modelo and revision, not a mechanical retype this row's scope or gate
covers — recorded here as the concrete next step for a future row, not
executed.

The three live sites (`CasillaParity.display_number`, `OperatorEdit
.display_number`, `SheetProvenanceRow.display_number`) stay bare `str` for
the identical reason, confirming `W05.P08.S42`'s revert was correct rather
than merely cautious: they carry the same full mixed population by
construction (every rendered casilla, not a numbered subset), so no
narrower alias could ever have been correct at those three sites without
first narrowing the source field itself.

No regression risk from this adjudication: nothing was retyped, so no test
suite was run against a code change. Verified only the measurement
commands themselves are reproducible (re-ran the stanza walk twice,
identical counts both times).

## Notes

The row's own "12,771" occurrence count and this row's re-derived 21,183
raw / 15,824 casilla-stanza / 4,383 manifest-stanza figures do not
reconcile to one number, and this row does not attempt to reconcile them —
per this campaign's own recorded instrument defects, a flat grep count and
a stanza-scoped count answer different questions, and chasing the count to
one true number would not change the shape-mixing verdict, which is the
only thing this row's gate depends on. The asterisk-prefixed and
range-notation findings are new information beyond what the row's own text
anticipated (it named the `###` marker and slug fallbacks but not the
asterisk-header convention's shape-incompatibility with `AeatBoxNumber` or
the range/multi-box outliers) — surfaced only by classifying every value
rather than sampling.
