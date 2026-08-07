---
tags:
  - '#reference'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e35a4230885062640034e818ddc44f10dff90a6dbedbb712b7cb88e2b04ab282'
related:
  - "[[2026-06-10-live-justificante-reconcile-adr]]"
  - "[[2026-05-04-live-filing-data-capture-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace justificante-identity-matching with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `justificante-identity-matching` reference: `Justificante identity matching: presentation_id namespace`

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

## Site 3 already has a correct, independent identity check alongside the broken one

`register_capture_as_filing_evidence` (`_justificante.py:672-687`) parses the
receipt and, **before** calling into `matches_filing_target`, already asserts
`justificante.csv.strip().upper() != snapshot.csv.strip().upper()` and raises
if they disagree (`:673-676`). That is a genuine receipt-namespace identity
check: the snapshot's own `csv` (captured at submission time, independent of
the parsed PDF) against the PDF's own parsed `csv`. The subsequent
`presentation_id=snapshot.expediente_id` argument passed into
`matches_filing_target` two lines later is redundant *and* wrong — it
re-compares in a namespace where no independently-known correct value exists
at that call site, using a value from a different namespace.

## No independently-known receipt-namespace identifier exists at the register-reconciliation call sites

At `_parse_matching_filed_justificante` (`_filed_observation_persistence.py:400-441`)
and `_justificante_matches_capture_axis`, the only inputs in scope are the
`FiledDeclaracionObservation` / `JustificanteCaptureSnapshot` (both carrying
only the register-sourced `expediente_id`, never a receipt-sourced `csv` or
`presentation_id`) and the artefact bytes being parsed. `Declaracion`
(`_declarations_schema.py:16-35`) — the register row model — has no `csv`
field; the CSV only becomes known by parsing the justificante PDF itself,
which is circular for a pre-parse expected-value check.

The artefact-to-observation pairing at these two call sites is nonetheless
structurally trustworthy independent of any content-level identifier
comparison: `FiledDeclaracionArtefact.storage_ref`
(`_schema.py:218-235`) is fetched via a download link scoped to that specific
register row's `expediente_id`
(`src/cadrumo/adapters/outbound/aeat/sede/_declarations.py:922-1036`,
`_row_locator_for_expediente`, `:1400-1403`), and the manifest byte-count and
sha256 are verified before parse
(`_filed_observation_persistence.py:417-422`). The PDF-content
`presentation_id` re-check that follows adds nothing beyond that structural
binding — it can only ever reject (since it compares mismatched namespaces),
never confirm.

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
