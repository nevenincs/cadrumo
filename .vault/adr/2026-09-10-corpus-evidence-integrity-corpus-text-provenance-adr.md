---
tags:
  - '#adr'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:959362638873e902750a5453f04b3eb3d654f6bdee64f3eed29145f6bbd72197'
related:
  - "[[2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research]]"
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-research]]'
  - '[[2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit]]'
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr]]'
---

# `corpus-evidence-integrity` adr: `Corpus text provenance is a third axis; corpus_tier does not and cannot carry it` | (**status:** `accepted`)

## Problem Statement

The registry can prove that a legal citation corresponds to the corpus file it names, and
that the file states an operative provision. It cannot prove that the file's text came from
BOE rather than from an author's keyboard. `2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research`
measures that gap: a small population of shipped corpus files carries no attribution of any
kind, and six citations rest on it — five claiming `legal_authority` evidence tier.

A decision is needed now because a neighbouring record has already been accepted on a
different axis, and the boundary between them must be stated before either is built.
`2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr` makes `corpus_tier`
mandatory for citations resolving under the normative corpus. That record is not wrong and
is not superseded here: it closes an unclassified-declaration gap this record does not
address.

It does not, however, reach the provenance hazard, and this record exists so that nobody
assumes it does. The trace in this record's grounding shows that a mandatory tier refuses
none of the measured hand-shaped population: `corpus_tier` answers whether a file is a whole
instrument or one provision, and every affected file either satisfies the filename heuristic
that ends the check early or passes the dispositive-content signal that was calibrated to
accept it. The two records are therefore complementary, with one sequencing dependency
recorded under Implementation.

## Considerations

- Provenance, excerpt-versus-full-text, and citation-to-text correspondence are three
  independent properties; `corpus_tier` owns the second and the evidence gate owns the third
  (`2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research`).
- A declared provenance claim is self-certifying in exactly the way `_validate_dispositive_content`
  already argues against in its own docstring: an author who types the wrong text will type
  the matching claim beside it.
- Provenance is a property of a corpus file, not of a citation. One file is cited up to 88
  times; per-citation declaration would multiply one fact across many declaration sites,
  which `aeat-registry-authority-flow` forbids.
- Two independent machine signals exist and neither is complete alone; their union covers
  the measured population but leaves a presumptive middle band.
- `no-silent-under-declaration` requires that unattributed text stay distinguishable from
  attested text through calculation and filing handoff, rather than collapsing to a boolean.
- The affected population is small enough to re-ground by hand, so a gate need not ship with
  a grandfathering ratchet.

## Considered options

**Mandate `corpus_tier` on every citation targeting the normative corpus.** Rejected *as
the remedy for provenance* — it refuses none of the measured hand-shaped population — while
being sound on its own terms as a classification-completeness contract, which is why
`2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr` accepts it for that
purpose. The risk this record guards against is the mandate being read as provenance
coverage it does not provide.

**Declare provenance per citation as a new typed field.** Rejected: multiplies one file-level
fact across many citation sites, and a hand-typed claim carries no more evidence than the
text it describes.

**Derive provenance from the corpus file at validation time, classify into three states, and
bind evidence tier to it.** Chosen. The classification reads the bytes, so it cannot be
satisfied by assertion; it is computed once per file regardless of citation count.

**Re-ground the six citations and add no gate.** Rejected as the whole answer: it clears the
present population but leaves the next hand-shaped file undetected. Adopted as a
precondition instead — see Implementation.

## Constraints

- The classification depends only on the bundled corpus and the standard library; no new
  dependency, no network access at validation time, and no frontier technology.
- It must run inside the existing registry validation path so that `ValidatedRegistryAuthority`
  publishes only a fully classified snapshot, per `aeat-registry-authority-flow`.
- It rests on no in-flight parent feature. `corpus_tier` is unchanged by this record and
  neither blocks nor is blocked by it.
- The `boe_presumptive` band is the known soft spot: structural markup is strong evidence but
  is typeable, so the classification's ceiling is "no author bypassed it accidentally", not
  "no author can bypass it".

## Implementation

Provenance becomes a derived, three-valued classification of each file under the normative
corpus, computed during registry validation and carried into the resolved citation.

`boe_attested` is a file carrying a first-party BOE attribution in its own bytes — the
consolidated-excerpt header or a BOE document identifier. `boe_presumptive` is a file
carrying BOE's structural markup but no identifier. `authored` is everything else: text with
no attribution of any kind.

The binding rule is the decision's teeth. A citation declaring `legal_authority` evidence
tier must resolve to `boe_attested` text; validation refuses otherwise. `boe_presumptive`
text is accepted for `legal_authority` only through an explicit, per-file, reviewable
exception carrying a reason — narrowly keyed as `no-silent-under-declaration` requires, never
a prefix or count-based exemption. `authored` text cannot back a filing-grade citation at
all; it may back an explicitly advisory one, and that classification travels into the
resolved result and explanation rather than being flattened away.

The classification is derived, never declared. No new field appears in the registry TOML for
the normal case; the only authored artefact is the exception list, which exists to be read.

One sequencing dependency binds this record to
`2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr`: that record's bounded
migration must classify the same hand-shaped files this record refuses as filing-grade. They
are re-grounded first, under this record's preconditions, so the migration classifies real
BOE text rather than assigning a tier to a paraphrase.

Two preconditions land before the refusal is armed, so the gate is not born red. The six
citations resting on authored text are re-grounded against real BOE text — a
`aeat-calculation-grounding` exercise needing the official sources, not a corpus sweep — and
the editorial gloss appended to the `ley-35-2006` article 48 excerpt is moved into the legal
entry's `notes`, following the remediation shape
`2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit` already judged the
more faithful. Detector teeth are proved on an isolated fixture tree per `aeat-quality-gates`,
not by mutating the bundled corpus.

The stale coverage docstring on the `corpus_tier` validator is corrected in the same change,
since it misstates that check's live reach.

## Rationale

The knockout is measured, not argued: a mandatory tier refuses zero of the hand-shaped
population, while the chosen classification separates that population cleanly on the first
pass. Both figures come from the grounding research. This is a statement about what each
mechanism can detect, not a criticism of the tier mandate, which is answering a different
question.

Deriving rather than declaring is what makes this different from the field it replaces.
`corpus_tier` is verified when declared and invisible when not, so its coverage is whatever
authors happened to opt into — nineteen entries against several hundred candidates. A
derived classification has no opt-out, which is the property the evidence gate needs and the
reason a second declarable field would repeat the first one's fate.

Binding to `evidence_tier` rather than refusing authored text outright preserves the
distinction `no-silent-under-declaration` protects. Authored text is not worthless; it is
not filing-grade. Collapsing those two statements is the failure this record exists to
prevent, and it is the failure a boolean "is the text OK" check would reintroduce.

## Consequences

The registry gains a property it currently asserts by convention: every filing-grade legal
citation resolves to text that attributes itself to BOE, checked rather than trusted. The
check costs one pass over the bundled corpus at validation time and adds no declaration
burden to the common case.

The honest difficulty is the presumptive band. Structural markup is evidence, not proof, and
an author who slices from a BOE page and edits the text keeps the markup. This decision
narrows the surface from "any text at all" to "text carrying BOE's own structure", and does
not claim to close it. Detecting substantive infidelity in text that looks authentic is a
different problem requiring the official sources, and is out of scope here.

The exception list is the pressure point to watch. It is designed to be small and read, and
it will be under pressure to grow whenever a re-grounding is inconvenient. If it grows past
a handful of entries the classification has stopped being a gate and become paperwork; that
is the signal to revisit this record rather than widen the list.

Two pathways open. The classification gives the corpus a per-file provenance fact that a
future freshness or re-download workflow can key on, and the same three-state shape extends
to the `corpus/aeat_official/` tree — calendars, record designs, manuals — which this record
deliberately leaves unclassified.
