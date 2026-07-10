---
tags:
  - '#adr'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
related:
  - "[[2026-07-10-censo-g313-launcher-fix-adr]]"
  - "[[2026-07-10-censo-g313-launcher-fix-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
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

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `censo-operator-manual-enrolment` adr: `censal facts are operator-manual; retire the live censo scrape` | (**status:** `accepted`)

## Problem Statement

The live censo (Modelo 036 / "Mis Datos Censales") read is broken and cannot be
safely fixed. A 2026-07-10 authenticated live investigation proved the
configured launcher `/wlpl/BUGC-JDIT/MdcAcceso` returns HTTP 404, and that AEAT
exposes NO read-only "Mis datos censales" projection: the real census data lives
only inside the multi-step "Censos WEB" ZKoss (`.zul`) MODIFICATION tool
(`BU36-ASIS/M036/index.zul`), behind a representation gate and a prefilled-036
modification form. Reading census data therefore requires operating a write
tool. This ADR decides the direction and supersedes
`2026-07-10-censo-g313-launcher-fix-adr` (whose chosen option — drive/wait — is
rejected). Decided by an authorized Fable architecture pass on operator
delegation.

## Considerations

- `aeat-safety-legal-gates` prohibits live AEAT mutation paths and mandates
  guarding every external write surface. "Censos WEB" IS a write surface (Baja /
  Modificación de datos).
- ZKoss multiplexes reads, panel-opens, and submits over one session-rekeyed
  `zkau` AU-engine POST channel, so a "never-submit" guard cannot be structural —
  it degrades to heuristics over button captions and generated component ids. The
  P02.S04 capture already saw that heuristic surface misbehave (a "Modificación
  de datos" click that silently did nothing).
- The consuming surface already degrades honestly: the overview calendar warns
  `censo.enrolment_unverified` for modelos 100/130/303/390 and refuses strict
  projection when censo is unverified (`no-silent-under-declaration` satisfied
  today). The operator-manual profile path (`config profile edit`) already
  exists.

## Considered options

1. **Drive the Censos-WEB modification tool read-only.** Rejected: a read path
   "one accidental submit away from mutating AEAT census state" is a live-write
   path with extra steps — the category `aeat-safety-legal-gates` prohibits — and
   the guard cannot be made structural on a ZKoss AU channel. Also
   disproportionately fragile (multi-step SPA AEAT reshapes freely, validatable
   only by operator-run live pulls).
2. **Hunt for a true read-only consulta endpoint elsewhere on the sede.**
   Rejected as a workstream: P01 swept the censal hub and found none; P02.S04
   concluded no read-only projection exists. If AEAT ever ships one, a new ADR
   revives the live read — a note, not a plan.
3. **Operator-manual censo enrolment; retire the scrape (chosen).** Censal facts
   are operator-supplied via the profile; the calendar keeps its unverified
   posture. Cheapest, safest, rule-aligned; loses automated censo pull.

## Constraints

- Revival condition: a genuine AEAT consulta-only "datos censales" endpoint
  (rendering data without the modification tool) would justify a new ADR to
  restore an automated read. Absent that, no live censo read ships.
- The retirement is a delete-not-stub change (`no-legacy-compatibility`,
  no-dormant-surface): the dead scrape chain is removed, not left inert.
- Operator-entered censal facts MUST stay a non-official evidence tier — never
  stamped AEAT-verified — mirroring
  `local-filed-observations-are-non-official-evidence`.

## Implementation

Retire the live censo scrape chain in one atomic explicit-path change: the
`censo_g313_launcher` constant (`core/external_constants.toml`), the launcher
drive in `adapters/outbound/aeat/sede/_censo_live.py`, and the
`parse_g313_html` / `_G313_LABELS` parser in `_censo.py`, plus the
`config profile censo pull` verb. Because a live snapshot is the second operand
of `censo compare`/`apply`, default to retiring the whole `censo pull/compare/apply`
family onto `config profile edit` (one path, no parallel write route, per
`composition-service-no-parallel-write-path`); re-seat compare/apply over an
operator-entered fact set only if a real workflow needs the diff (decided in the
retirement plan). Sweep the verb-removal blast radius the
`aeat-cli-pull-and-file-standard` rule enumerates: locale keys (via the locales
CLI), how-to docs, the documented-command conformance gate, the storage
write-policy allowlist, and that rule's own source (it cites `censo pull` as a
worked example) via `vaultspec-core sync`. Censo enrolment facts flow only from
`config profile edit` onto the encrypted profile, driving obligation derivation
at the operator-declared (non-official) tier; the calendar continues to emit the
unverified advisory (optionally refined to a distinct
`censo.enrolment_operator_declared` info `Notice`).

## Rationale

The safety rule was written for exactly this moment: when the only way to read is
to operate the write tool, the correct engineering answer is to stop reading.
Option 4 degrades nothing that is load-bearing — safety, honesty, and the
hexagonal boundary are all preserved; only automated convenience is lost — and it
is ~90% already built (the calendar's unverified posture and `config profile
edit`). Options 1 and 2 spend engineering to buy, respectively, a prohibited
mutation risk and an endpoint we have positive evidence does not exist. Grounded
in `2026-07-10-censo-g313-launcher-fix-P01-S01`,
`2026-07-10-censo-g313-launcher-fix-P02-S04`, and the fork in
`2026-07-10-censo-g313-launcher-fix-adr`.

## Consequences

- Gains: no fragile safety-critical SPA driver; the census read stops brushing a
  mutation surface; one enrolment path (`config profile edit`), no parallel write
  route.
- Honestly: automated censo pull is lost permanently until AEAT ships a
  consulta-only endpoint. Census drift (the taxpayer's real AEAT census diverging
  from the profile) becomes undetectable by the app; the standing
  `censo.enrolment_unverified` advisory is the mitigation and the disclosure.
- Operator-entered censal facts can be wrong and propagate into obligation
  derivation; mitigated by the non-official evidence tier and the calendar's
  refusal to project strictly on unverified censo.
- Guard/test requirements the retirement plan must carry: a regression pinning
  the calendar unverified-posture (warning present + strict refusal) so the
  honest default cannot rot; a regression pinning that operator-entered censal
  facts are never stamped AEAT-verified; docs/CLI conformance gates green after
  the verb removal.
- Opens: a low-cost revival path (watch for a real AEAT consulta endpoint; new
  ADR restores the automated read if one appears).
