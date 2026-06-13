---
tags:
  - '#adr'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-13-semantic-dedup-epic-audit]]"
  - '[[2026-06-13-semantic-dedup-epic-plan]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, or deprecated. A new ADR starts as proposed; it moves to
     accepted or rejected when the decision is made, and to deprecated
     when a later ADR supersedes it.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `semantic-dedup-epic` adr: `Semantic Deduplication Pass 1 — Canonical-Home Decisions` | (**status:** `accepted`)

## Problem Statement

The codebase semantic-deduplication epic requires, per the audit
`2026-06-13-semantic-dedup-epic-audit`, a recorded canonical-home decision for
each confirmed duplication cluster from discovery Pass 1. Three clusters
(F1 tax-id validation, F2 fichero-BOE money formatting, F3 repository bucket-id
resolution) reached the confirmation stage; each needs a decision before any
removal lands, because two of the three carry safety or behavioural risk that
forbids an autonomous merge. This ADR records those decisions so a later pass
does not re-litigate them.

## Considerations

The governing discipline is the substitutability pre-filter: a site is only
consolidated when the canonical site's constraint shape is a superset of the
candidate's. Two of the three clusters fail that test on close reading despite
strong lexical/semantic clustering — the false-positive pattern the pre-filter
exists to catch. The fichero-BOE surface additionally falls under the
safety-legal gates: it is the wire format for AEAT submission, so deleting a
roundtrip-tested encoder is not an autonomous call.

## Constraints

F2 depends on an external fact this pass cannot settle autonomously: whether the
dormant `_formats` encoder is superseded dead code or an intended-canonical
implementation mid-migration. That determination is owner-gated. F1 and F3 are
fully determinable from the source.

## Implementation

**F3 — accepted and implemented.** One canonical
`resolve_repository_bucket_id(bucket_id, *, error_type)` is added to the core
bucket-pointer module and exported through `aeat.core`. The three per-domain
runtime-repository resolvers (`domain.modelos`, `domain.filing`,
`application.filing`) delegate to it, passing their own domain error class. The
message key and reason contexts were already identical across the three copies,
so the change is behaviour-preserving; the public resolver names and signatures
are unchanged.

**F1 — keep both surfaces (no merge).** `core.identity._tax_id` (legacy-tolerant
CIF leader set, returns a normalised `str`) and `core.identity._documents`
(strict current-spec CIF catalogue, returns the typed `IdentityDocument` enum)
are an intentional divergence, documented in the source itself. They already
share the single `_NIF_LETTERS` table and `IdentityError`. The residual
overlap (a one-line `% 23` check-letter expression; near-identical NIF/NIE
validators that differ in return type and error construction) is below the
threshold at which a merge is safe, and the CIF leader-set divergence is
deliberate. No consolidation; the table-sharing already in place is the correct
single-source posture.

**F2 — canonical is the wired path; deletion of the dormant stack is
owner-gated.** The production export path is
`application.filing.export_draft` (`_format_money` + `_render_layout`) and the
verify path decodes through the registry export-parse module; the
`adapters.outbound.aeat.export._formats` encode/serialise/deserialise stack has
zero production consumers (verified tree-wide). The wired path is declared
canonical. Removal of the dormant `_formats` stack is slated but gated on owner
confirmation that no in-flight migration intends to adopt it, because it is a
roundtrip-tested encoder of the AEAT submission wire format.

## Rationale

Recording keep-both (F1) and defer-deletion (F2) as explicit decisions is the
honest outcome of source-level confirmation: the audit's first-pass HIGH/MEDIUM
severities reflected lexical clustering, and close reading under the
substitutability pre-filter downgraded two of three. Landing only F3 — the one
behaviour-preserving, safety-neutral consolidation — is the disciplined result.
Forcing F1 or F2 would have respectively broken an intentional legacy tolerance
and risked a safety-critical wire-format encoder.

## Consequences

The repository bucket-id resolution boilerplate is now single-sourced; future
domains call the shared helper. The campaign records two ruled-out/ gated
clusters so a later pass does not re-flag them. The open item is F2's
owner-gated deletion, tracked as an unchecked plan step. The broader epic
continues: Pass 1 covered 24 functional concepts; subsequent passes extend
coverage and append waves to the plan.

## Codification candidates

<!-- If this decision introduces a durable cross-session constraint
that should bind future agents (an obligation, a prohibition, a
discipline that survives this feature's lifecycle), name it here as
a candidate for promotion into a project rule under
`.vaultspec/rules/rules/` via the codify pipeline phase.

Each candidate names the proposed rule slug (kebab-case, naming the
constraint's subject) and a one-sentence statement of the rule.

Not every ADR produces a codification candidate. Decisions that are
local to one feature, or that describe rather than constrain, leave
this section empty. An empty Codification candidates section is a
positive signal, not a failure. -->

<!-- Example:

- **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
