---
tags:
  - '#reference'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:5929bbf2effc41f8ea5a35d1baf463b96910142d233b4edc85fba288a62d0b47'
related:
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
---

# `justificante-identity-matching` reference: `Justificante identity matching: presentation_id namespace`

## Summary

Grounded against real AEAT-issued Modelo 303 justificante PDFs pulled by a live
authenticated session, loaded from encrypted storage, and run through the
production parser and predicate directly — not reasoned about.

## Empirical finding

`parse_justificante_bytes` parsed both captured PDFs cleanly. `modelo`,
`ejercicio`, `period` and `tax_id` all agreed with the register observation on
both. `presentation_id` was non-empty on both. `presentation_id ==
observation.expediente_id` was **false on both**, so
`Justificante.matches_filing_target` rejects every live-captured M303
justificante against its own filed observation.

## Two distinct AEAT identifier namespaces exist on one receipt

`Justificante` (`src/cadrumo/domain/justificante/_schema.py:76-80`) already
carries them as separate typed fields, and its own docstring states the
distinction:

- `csv` — *Código Seguro de Verificación*, the AEAT-assigned verification hash
  printed on the receipt (`JustificanteCsv`, `_schema.py:22-29`).
- `presentation_id` — AEAT's *"Número de justificante"*, extracted by
  `_extract_presentation_id` (`src/cadrumo/adapters/inbound/justificante/_extract.py:494-497`)
  via `_PRESENTATION_ID_RE` / `_PRESENTATION_ID_ANNUAL_RE`
  (`_extract.py:164-167`, `212-215`), both anchored on the literal label
  `"Número de justificante"` printed on the receipt body.

`expediente_id` is a **third, unrelated** AEAT identifier: the internal
case-file reference AEAT assigns to a row in *Consultar declaraciones
presentadas* (the register), captured by
`_parse_listbox` from the `"Expediente"` register column
(`src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py:146`,
`Declaracion.expediente_id`, `_declarations_schema.py:24`). It never appears on
the receipt PDF body at all — nothing in `_extract.py` reads or produces it.
It is the same value carried by `FiledDeclaracionObservation.expediente_id`
(`_schema.py:455`) and by `JustificanteCaptureSnapshot.expediente_id`
(`src/cadrumo/application/live/_justificante.py:116`), both sourced from the
same register/listing surface, not from the receipt.

`matches_filing_target` (`_schema.py:104-132`) accepts a `presentation_id`
keyword and, when the receipt carries a non-empty `presentation_id` of its
own, requires the caller's value to agree (case-insensitive). The predicate's
own contract is internally correct — it is a receipt-namespace comparison. The
defect is at every call site: all three pass a register-namespace
`expediente_id` into a parameter documented and implemented as
receipt-namespace `presentation_id`.

## Every caller conflates the two namespaces (systemic, not M303-local)

1. `_justificante_matches_filed_observation`
   (`src/cadrumo/application/live/_filed_observation_persistence.py:444-454`) —
   `presentation_id=observation.expediente_id`. Called from
   `_parse_matching_filed_justificante` (`:400-441`), itself called from both
   `persist_filed_justificante_metadata` (`:183`) and
   `enroll_filed_justificante_evidence` (`:222`) — the register-reconciliation
   path this campaign is grounding.
2. `_justificante_matches_capture_axis`
   (`src/cadrumo/application/live/_justificante.py:596-605`) —
   `presentation_id=snapshot.expediente_id`.
3. `register_capture_as_filing_evidence` (`_justificante.py:678-687`, via
   `_justificante_matches_filing_record`) — also
   `presentation_id=snapshot.expediente_id`.

No caller anywhere in the tree passes a genuinely receipt-namespace value
(neither `csv` nor a captured "Número de justificante") into
`matches_filing_target`'s `presentation_id` parameter. The unit test
`test_matches_filing_target_uses_one_normalised_axis_matrix`
(`src/cadrumo/domain/justificante/tests/test_filing_target.py:27,42-49`) bakes
the same false equivalence into its fixture (`"presentation_id": "EXP-2025-1T"`
reads as an expediente-shaped literal) — synthetic, and consistent with the
conflation rather than independent evidence for it.

## Two of the three sites already have a correct, independent CSV check alongside the broken one

Both remaining call sites that populate `presentation_id` sit downstream of an
already-present, genuinely independent receipt-namespace comparison — this
corrects an earlier draft of this reference, which treated only one of the two
as guarded without checking the other's actual caller:

- `register_capture_as_filing_evidence` (`_justificante.py:672-687`) parses
  the receipt and, **before** calling into `matches_filing_target`, already
  asserts `justificante.csv.strip().upper() != snapshot.csv.strip().upper()`
  and raises if they disagree (`:673-676`).
- `register_capture_justificante_metadata` (`_justificante.py:545-557`), the
  actual caller of `_justificante_matches_capture_axis` (`:596-605`), runs the
  identical check one function up: `justificante.csv.strip().upper() !=
  snapshot.csv.strip().upper()` (`:549-552`), before calling
  `_justificante_matches_capture_axis` at `:553`.

Both compare the snapshot's own `csv` (captured at submission time via the
cotejo flow, independent of the parsed PDF) against the PDF's own parsed
`csv`. Both then also pass `presentation_id=snapshot.expediente_id` into
`matches_filing_target`, which is redundant *and* wrong-namespace given the
CSV check that already ran. Dropping that argument at both sites is strictly
subtractive: it removes a comparison that never validly ran, next to one that
already does the real job.

## The third site's CSV is independently resolved during capture and then discarded — it is recoverable without a schema change

`_parse_matching_filed_justificante` (`_filed_observation_persistence.py:400-441`,
called from `persist_filed_justificante_metadata` and
`enroll_filed_justificante_evidence`) is the one site with no adjacent CSV
check. `FiledDeclaracionObservation` and `Declaracion` (register row) both
carry no `csv` field, and `FiledDeclaracionArtefact`
(`_schema.py:218-235`) also has no `csv` field.

But the `justificante_pdf` artefact this function parses is fetched by
`_capture_row_pdf_artefact`
(`src/cadrumo/adapters/outbound/aeat/sede/_declarations_fetch.py:226-284`),
which **already resolves the receipt's CSV independently of the PDF body**:
it navigates to the row's cotejo popup, extracts
`csv = _extract_csv_from_url(cotejo_url)` (`:262`) using the canonical
`extract_csv_from_url` helper (`_declarations_remote.py:31-46`, exported
`__all__` at `:69-73` — "shared more widely, by `_declarations.py` and
`_parse.py`", per its module docstring), then builds
`pdf_url = _cotejo_document_url(_origin_of(cotejo_url), csv)` — literally
`f"{origin}{_COTEJO_DOCUMENT_PATH}?CSV={csv}"` (`_declarations_fetch.py:154-156`)
— and stores that exact URL as `FiledDeclaracionArtefact.source_url`
(`:275-283`). `extract_csv_from_url` (`_declarations_remote.py:31-46`) reads
the `CSV` query parameter via `urlsplit`/`parse_qs` with no path check, so it
recovers the identical CSV from `artefact.source_url` just as reliably as it
did from the cotejo popup URL that produced it.

This means the register-reconciliation site does NOT lack an
independently-sourced identifier — it computes one, uses it to fetch the exact
bytes being parsed, and then discards it without persisting it anywhere.
`extract_csv_from_url(artefact.source_url)` recovers it at comparison time
with **no new persisted field and no persistence-boundary change**: `source_url`
is an existing `AnyHttpUrl` field already round-tripped through
`FiledDeclaracionArtefact` today.

`extract_csv_from_url` is not currently re-exported through the sede
package's public facade (`src/cadrumo/adapters/outbound/aeat/sede/__init__.py`
does not list it); per `aeat-architecture-boundaries`, promoting it into that
`__all__` is a precondition of consuming it from `application/live/`, not a
follow-up. It raises `SedeParseError` on a malformed or missing `CSV` query,
which the consuming site must catch alongside the artefact's other swallowed
failure modes (see Observability gap, below).

**This structural binding is the PRIMARY protection, not a secondary one.**
`_capture_row_pdf_artefact` locates its target row via
`_row_locator_for_expediente` (`_declarations.py:1400-1404`), a Playwright
locator scoped to the ONE row matching `declaration.expediente_id` and
re-resolved fresh from the live grid per declaration. AEAT's own server
decides which cotejo popup and CSV that click opens; the `(observation,
artefact)` pairing is fixed at construction, before any `Justificante` model
or predicate runs, and every downstream consumer iterates strictly
`observation.artefacts`. The `presentation_id`/`expediente_id` comparison
never performed this binding — it only ever re-checked PDF content in a
namespace that could never agree. The added CSV check is SECONDARY
defense-in-depth against a different bug class: a downstream storage,
caching, or selection-layer defect re-associating a correctly-fetched
artefact with the wrong observation after capture. The manifest byte-count
and sha256 verified before parse (`_filed_observation_persistence.py:417-422`,
via `load_artefact`) is self-referential — it proves the decrypted bytes were
not corrupted after being written under that digest-derived key, and says
nothing about which filing the bytes belong to — so the CSV check is the
first content-level identity check performed after storage, distinct from
both the row-scoped fetch and the digest check.

`_row_locator_for_expediente` currently filters via Playwright
`has_text=expediente_id`, a **substring** match (`.z-listcell`, filtered on
text containment, not exact equality). AEAT expediente ids are 12-32
character tracking numbers with no known reachable substring collision, so
this is not evidence of a live defect — but once the wrong-namespace
predicate re-check is removed, this locator becomes the SOLE mechanism
preventing a cross-filing mis-pairing, which raises its own correctness bar
enough to justify hardening it to an exact match.

## No caller has a valid reason to populate `presentation_id`

Once all three sites are corrected to perform their own CSV equality check
(two already do; the third gains one via `extract_csv_from_url`), none of them
has any remaining reason to pass a value into `matches_filing_target`'s
`presentation_id` parameter — the receipt-namespace verification is fully
covered by the CSV check each caller now performs itself, uniformly. A
parameter no caller can ever correctly populate, and that every actual
populating caller populated wrong, is a defect in the predicate's signature,
not only in its callers.

## `elsewhere-modelo` scope of the receipt label

`_PRESENTATION_ID_RE` / `_PRESENTATION_ID_ANNUAL_RE` are shared across every
modelo family's receipt (both anchor on `"Número de justificante"`, one
requiring `[0-9A-Z]{10,40}` and the annual variant `[0-9]{10,40}`). Nothing in
`_extract.py` special-cases M303, and no modelo's receipt format embeds the
register's `expediente_id` — the label AEAT prints is uniformly its own
justificante number, distinct from the register's case-file id. The defect is
general to every modelo reachable through these three call sites, not an
M303-only quirk; the two captured fixtures happen to be M303 because that is
what the live pull retrieved.

## A canonical CSV shape type already exists in `core`, narrower than the domain alias

`cadrumo.core._aeat_csv` (`src/cadrumo/core/_aeat_csv.py:1-45`, exported
`is_aeat_csv` / `AEAT_CSV_PATTERN` / min/max length constants) states in its
own module docstring that the CSV contract "lives in `cadrumo.core` because
every layer meets a CSV and none of them owns it," and constrains it to 8-32
uppercase alphanumeric characters. `JustificanteCsv`
(`src/cadrumo/domain/justificante/_schema.py:22-29`) is a separate, narrower
`Annotated[str, StringConstraints(min_length=4, max_length=64)]` alias that
does not reuse `core`'s pattern and is looser at the low end (4 vs 8) and
looser at the high end (64 vs 32). This is exactly the kind of fragmented
free-form identifier population the operator's parallel canonical
typed-identifier-system effort is inventorying; this record does not resolve
it — reconciling `JustificanteCsv` onto `core`'s canonical CSV contract is
adjacent scope for that effort, not this one, and is out of scope here.

## Observability gap

`_parse_matching_filed_justificante` swallows three distinct failure modes —
unreadable artefact (`:410-416`), manifest mismatch (`:417-422`), unparsable
PDF (`:423-431`) — and outright predicate rejection (`:432-440`) into an
identical shape: a `logger.warning` plus `return None`. No field on
`FiledJustificanteEnrollmentResult`
(`_filed_observation_persistence.py:85-90`, carrying only
`justificante_csvs` / `filing_record_ids` / `conflicting_filing_record_ids`)
or the CLI report distinguishes "no justificante artefact present" from
"artefact present but rejected by the identity predicate" from "artefact
present but unparsable." The project's `Notice` channel
(`cadrumo.core.json_contract.Notice`) is the sanctioned surface for this kind
of non-blocking diagnostic per the CLI-contract rule; no code path here emits
one today.
