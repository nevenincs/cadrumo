---
tags:
  - '#adr'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e36fb60a4665b2048cb743e84613c7e5958024309aab26216869b51aa18e3f33'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-reference]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace m200-export-nif-misbinding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Amend vs supersede: refinements and concretization rewrite the accepted
     record's body in place (modified: carries the revision); a new ADR with
     supersession is only for a major pivot. One accepted record per
     decision.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `m200-export-nif-misbinding` adr: `stop binding the filer's own NIF into the grupo mercantil foreign-TIN slot` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Every Modelo 200 fichero-BOE export written today writes the filer's own
9-character Spanish NIF, right-padded to 15, into the byte slot AEAT's
published diseño de registro reserves for the mercantile group's ultimate
parent company's foreign tax identification number (`m200-export-nif-misbinding-reference`,
"The two declarations at issue" / "What AEAT's own spec says"). The record
carrying it renders unconditionally — no disposition, group-membership, or
other predicate suppresses it (`m200-export-nif-misbinding-reference`, "The
record renders unconditionally") — so this is not a conditional edge case, it
is every export, today. This is a live filing-correctness defect, not part of
any in-flight campaign, and requires a decision now because every day of
delay ships another wrong official filing.

## Considerations

- The misbound field's declared `length = 15` is itself AEAT-correct for that
  byte position; only the `draft_attribute` binding is wrong
  (`m200-export-nif-misbinding-reference`, "The two declarations at issue").
  Shrinking the field to 9 would corrupt a legitimate AEAT field shape.
- The entire surrounding grupo mercantil / grupo fiscal block (positions
  13-158) is otherwise unwired filler; no casilla, binding, or profile
  concept for "sociedad matriz última" (parent company identity, its foreign
  TIN, razón social, group name, country of residence) exists anywhere in the
  domain model today (`m200-export-nif-misbinding-reference`, "The adjacent
  grupo mercantil / grupo fiscal block is otherwise unwired").
- `no-silent-under-declaration` and `sensitive-financial-data-secure-storage-only`
  bear on the choice only indirectly here: the live defect is *affirmatively
  wrong* data (a real taxpayer's NIF asserted as a foreign entity's TIN), not
  an absence — worse than blank, and worth fixing without waiting for the
  larger feature that would fill the block correctly.
- `aeat-registry-authority-flow` requires production code to read regulatory
  values through the registry authority; no code path may re-derive AEAT
  layout facts, so any gate closing this class must be TOML-authored and
  registry-build-enforced, not a runtime heuristic.
- No existing gate checks `draft_attribute`-to-slot semantics
  (`m200-export-nif-misbinding-reference`, "Nothing validates draft-attribute-
  to-slot semantics"); `.vault/adr/2026-07-01-fichero-boe-parity-gate-adr.md`
  covers manifest-casilla *presence*, a different axis, and this ADR extends
  that lineage rather than duplicating it (`m200-export-nif-misbinding-reference`,
  "Prior governing ADR").
- A corpus-wide sweep of every `draft_attribute = "profile_tax_id"`
  declaration (28 sites, all modelos and revisions) found exactly one
  non-9-length occurrence — this one
  (`m200-export-nif-misbinding-reference`, "Corpus-wide width-anomaly sweep").
  The sweep does not clear the broader defect class (a width-consistent
  slot-semantic mismatch, or the same class on a different `draft_attribute`,
  `casilla_id`, or `binding` field, on M200 or any other modelo) — that
  remains genuinely unswept.

## Considerations

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

**Misbound-field fix.** (A, chosen) Re-declare offset 141 as `kind = "filler"`,
stopping the false write immediately, with no new domain concept required. (B,
rejected) Shrink `length` to 9 and keep `draft_attribute = "profile_tax_id"` —
explicitly barred: AEAT's field is genuinely 15 bytes wide for a different
entity's TIN, so narrowing it corrupts a legitimate AEAT field shape while
still writing the wrong entity's identifier. (C, rejected) Leave the field
bound and only add an advisory `Notice` for group filers — rejected: a
Notice does not stop a materially wrong byte from reaching an official filing;
`aeat-cli-contract` reserves notices for non-blocking diagnostics, not for
tolerating known-wrong bytes on disk.

**Grupo mercantil block scope.** (A, chosen) Fix only the misbound field now;
explicitly declare the rest of the block (parent NIF, razón social, group
name, country code, foreign TIN once correctly modeled) out of scope for this
ADR, and state the consequence plainly: a taxpayer that IS part of a grupo
mercantil still ships that block blank after this fix, which is a distinct,
pre-existing, lower-severity gap (absence, not false data) requiring new
domain concepts (parent-company identity, group-membership profile facts,
new casilla/binding wiring) this ADR does not invent. (B, rejected) Wire the
full block in this same change — rejected: no profile concept for group
membership or foreign parent identity exists yet; inventing one under
urgent-fix pressure risks exactly the kind of unreviewed domain modeling this
project's architecture rules gate against, and blocks the urgent fix on a
much larger feature.

**Suppression predicate for the block.** (A, chosen) None needed once the
misbound field is filler — a filler field renders blank regardless of
disposition, so there is nothing to conditionally suppress; suppression only
matters for a page that would otherwise assert something false or
inapplicable (the DID refund page's precedent). (B, rejected) Add a
group-membership predicate now — rejected: there is no group-membership
signal in the current domain model to predicate on, and the block is already
uniformly blank for every filer once the fix lands, so a predicate would
guard nothing yet.

**Gate to close the defect class.** (A, chosen) A registry-build validator
asserting that any `draft_attribute` resolving to a typed, fixed-width
domain source (`profile_tax_id` -> `SubjectTaxId`, 9 characters; extensible to
`filing_year`, `period_code`, etc. as each gains a canonical width) declares a
matching `length` — mechanical, cheap, catches this exact defect class
(a draft attribute's width silently drifting from its source) build-wide, no
AEAT-document parsing required at build time. (B, considered, deferred as
pathway) Full automated cross-check: fetch and parse each modelo's bundled or
live AEAT diseño de registro `.xls` and diff every declared field's
offset/length/description against the registry TOML — the strongest possible
gate, but a materially larger investment (corpus bundling, per-modelo sheet
parsing, description-to-`draft_attribute`/`casilla_id` semantic mapping) that
this ADR does not block the urgent fix on; recorded as the natural next step
once a bundled diseño corpus exists. (C, rejected) No new gate, rely on
manual review — rejected: manual review is exactly what missed this for
however long it has shipped; `aeat-quality-gates` requires gates over
vigilance for anything that reaches an official filing.

**Scope of other modelos.** (A, chosen) State the corpus-wide
`profile_tax_id` width sweep's result plainly (isolated to this one field)
and open the broader semantic-mismatch sweep (other draft attributes, other
field kinds, other modelos) as an explicit unswept follow-up row rather than
either declaring it clear or silently deferring it. (B, rejected) Declare the
defect M200-only without stating the sweep's actual boundary — rejected: it
would misrepresent a partial (width-only, one-attribute) sweep as a complete
one, exactly the false-completeness failure `aeat-worktree-safety` and
`no-silent-under-declaration` guard against elsewhere in this codebase.

## Constraints

- **Registry-only fix, no code path change for the misbound field itself.**
  Re-declaring `kind = "filler"` on the existing field id is a pure TOML edit;
  it must not touch `offset`/`length` (both already AEAT-correct) and must
  drop `draft_attribute` per the schema's own-kind validation
  (`_validate_field_kind`, which requires `FILLER` to declare `length` and
  forbids stray companion fields for the wrong kind — verify against the live
  schema before editing).
- **Depends on `2026-07-01-fichero-boe-parity-gate-adr` staying stable.** The
  new slot-semantics gate is a sibling check inside the same registry-build
  validation surface that ADR's completeness gate already occupies
  (`domain/calculations/registry/_export.py` /
  `application/filing/_export_parity.py`); it must not weaken or duplicate
  that gate's `required_applicable ⊆ rendered` assertion.
- **The typed-source-width gate needs a canonical width source per
  `draft_attribute`.** Only `profile_tax_id` has a clearly typed fixed-width
  source (`SubjectTaxId`, 9 chars) confirmed in this investigation; `modelo`,
  `period`, `filing_year`, `period_code` need their canonical widths
  established (or explicitly marked width-variable / not-yet-gated) before
  the gate can assert on them without false-firing.
- **Grupo mercantil wiring is out of scope and NOT started here.** No new
  casilla, binding, or profile field is authored by this ADR. A future ADR
  building that feature must independently establish AEAT's casilla numbers
  (if any apply to this block — the diseño excerpt above shows no bracketed
  `[000xx]` casilla code on positions 20/29/44/59/99/139/141, suggesting these
  may be pure export-record fields with no calculation-engine casilla
  counterpart) and the domain concept for "grupo mercantil membership" before
  any binding can be authored.
- **The broader semantic sweep (other draft attributes / field kinds / other
  modelos) is explicitly NOT performed by this ADR.** It is opened as a
  follow-up row in the plan, not resolved here.

## Implementation

Re-declare field `modelo-200-page-001b-draft-profile_tax_id-pos-141` in
`0003-modelo-200-page-001b.toml` as `kind = "filler"` (dropping
`draft_attribute`), keeping `offset = 141` and `length = 15` unchanged, so the
byte slot AEAT reserves for the parent's foreign TIN renders as spaces
instead of the filer's own NIF. A targeted test drives `export_draft` (or the
lower-level `_render_layout`) for a Modelo 200 draft with a populated
`profile_tax_id` and asserts the byte range `[140:155]` (0-based) of the
rendered `page_001b` record is blank/space-padded, not the draft's NIF —
proof the specific defect is closed, and a mutation-proof: reverting the
field to `draft`/`profile_tax_id` must flip that assertion red.

Add a registry-build validator alongside the existing per-family export
validators (`domain/calculations/registry/_export.py` /
`_schema_surfaces.py`) that, for every `kind = "draft"` field whose
`draft_attribute` has an established canonical width (starting with
`profile_tax_id` -> 9), asserts the declared `length` matches. A fixture-
anchor test proves the new validator actually fires: mutate a scratch
declaration's `profile_tax_id` field to a wrong length and assert
`RegistryValidationError`; restore. Extend the existing `_record_field_ranges`
/ `_reject_overlapping_ranges` module doc to name the new check as the
slot-width sibling of the overlap check, so future readers find both in one
place.

Open, but do not implement, two follow-up rows: (1) modeling grupo mercantil
membership and the parent-company identity block as its own domain concept
and registry wiring, once a casilla or export-only field basis is confirmed
against AEAT's casilla catalogue; (2) the broader semantic cross-check sweep
(other `draft_attribute`s, `casilla_id` and `binding` fields, other modelos)
against AEAT's published diseños, scoped as its own audit pass rather than
folded into this urgent fix.

## Rationale

The chosen fix is the minimal change that stops today's filing-correctness
defect without inventing unreviewed domain modeling under time pressure: it
touches one field's `kind`, preserves AEAT's byte geometry exactly, and
requires no new casilla, binding, or profile concept. Declaring the rest of
the grupo mercantil block out of scope, with the consequence stated plainly
(group filers still ship that block blank), is honest about what this ADR
does and does not fix — better than either silently expanding scope past an
urgent fix or silently implying the block is now complete. The typed-source-
width gate is the smallest mechanical check that would have caught this exact
defect at registry-build time (a `profile_tax_id` binding at `length = 15`
against a 9-character typed source is a build-time-detectable contradiction
independent of any AEAT document), chosen over the heavier full diseño-parsing
gate so the fix and its regression lock land together; the heavier gate is
recorded as the natural next investment rather than abandoned. Stating the
width-sweep's actual boundary (isolated to one field, for one draft
attribute) rather than a broader "M200-only" claim keeps the ADR's own
completeness claim honest, consistent with how this codebase treats every
other completeness claim.

## Rationale

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

- **This is a live defect affecting filings produced today.** Every Modelo
  200 fichero-BOE export written before this fix lands carries the filer's
  own NIF in AEAT's grupo-mercantil ultimate-parent foreign-TIN slot,
  unconditionally, for every filer. After the fix, that slot renders blank
  for every filer until the follow-up wiring feature lands.
- **Scope confirmed:** a corpus-wide sweep of all 28 `draft_attribute =
  "profile_tax_id"` declarations across every modelo and revision found this
  is the only one at a non-9 length — this defect, as specifically
  characterized (a `profile_tax_id` binding at an inconsistent width), is
  known to affect exactly one modelo (M200) and one field.
- **Scope NOT confirmed / unswept:** whether any *other* field (a different
  draft attribute, a `casilla_id`, or a `binding` field) is bound to a
  semantically wrong AEAT slot, on M200 or any other modelo, at a
  width-consistent length that the sweep above cannot detect. This is opened
  as a follow-up row rather than resolved or assumed clear.
- **Gain:** closes the immediate false-data defect with a minimal, reviewable
  registry-only change, and adds a mechanical build-time gate (typed-source-
  width) that would have caught this specific defect had it existed at
  authoring time.
- **Cost / pitfall:** the grupo mercantil block remains functionally
  incomplete for filers who are part of a group — this ADR trades an
  affirmatively-wrong value for an honest absence, which is a real
  improvement but not full correctness; the follow-up wiring feature is
  required to close that remaining gap and is not scheduled by this ADR.
- **Pathway:** the typed-source-width gate is the first instance of a
  slot-semantics gate family; the deferred full diseño-cross-check option (B
  under "Gate to close the defect class") is the natural next investment once
  a bundled AEAT diseño corpus exists, and the deferred grupo-mercantil
  domain modeling is the natural next investment once AEAT's casilla
  catalogue for that block is confirmed.
