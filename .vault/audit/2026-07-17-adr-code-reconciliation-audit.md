---
tags:
  - '#audit'
  - '#adr-code-reconciliation'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:d3e051b0ee96558081665887aeec85d1c4d2ce1d83b83f60ad15291fbfb447e3'
related:
  - "[[2026-07-04-autonomic-deduccion-framework-adr]]"
  - "[[2026-07-01-modelo-303-regimen-simplificado-adr]]"
  - "[[2026-07-09-cli-lazy-subcommand-mutation-adr]]"
  - "[[2026-07-09-m210-plazo-keying-adr]]"
---

# `adr-code-reconciliation` audit: `ADR and code reconciliation closure honesty review`

## Scope

This document was scaffolded empty on 2026-07-17 and left as a shell; it was
filled retroactively on 2026-07-21 as the audit-of-record for the two vault
sweep commits landed that day, which are the only surviving trace of the
reconciliation activity this audit was scaffolded to close:

- `ba2d7d494d` — "chore(vault): commit accumulated adr/archive/reference
  changes" — deleted 91 `.vault` files (73 active-tree ADRs and references, 18
  `_archive` files) and added consolidated archive material.
- `651bdcba9d` — "chore(vault): commit accumulated research/index/audit/plan
  working-tree changes" — deleted 160 `.vault` files (audits, plans, research,
  indexes), several of which were moves into `_archive` rather than losses.

Neither commit recorded a curation rationale, and no other vault document
explains the sweep. Both are catch-all captures of an accumulated working-tree
state, so the deletions carried no per-document disposition. The disposition
was reconstructed on 2026-07-21 by a per-document evidence pass: HEAD reference
counts across the vault, the rule corpus, and `.vaultspec`; plan-orphan status
via the feature lifecycle checker; `_archive` presence for suspected moves; and
content reads for every post-June deletion.

## Findings

### sweep-deleted-rule-cited-authorities | high | restored

The sweeps deleted accepted ADRs that standing project rules cite as their
source authorities, leaving the rule corpus pointing at nothing: the
released-data-durability ADR and the compatibility-lifecycle ADR (both cited by
the `no-legacy-compatibility` and `compatibility-lifecycle-checkpoint` rules),
plus their research documents, the release-checkpoint flip-checklist reference,
the compatibility-lifecycle plan, and its campaign-close honesty-review audit.
All restored byte-exact from the pre-sweep commits in `6390010ad6` (ADRs,
research, reference) and the 2026-07-21 follow-up restoration commit (plan,
audit).

### sweep-deleted-active-campaign-records | high | restored

Accepted decision records of live lineages were deleted while their sibling
documents survived at HEAD: the agent-harness shape ADR (2026-06-30) and its
content companion (2026-07-01), whose plans, research, and seven audits all
survive; the counterpart-source-provider design ADR, whose feature index
survived as an empty husk; the renta-region-deductibility design ADR, all of
whose seven related-link targets survive; and the mcp-hardening-conformance
campaign-close honesty-review audit (2026-07-09), whose plan and sibling ADRs
survive. Restored in `1602d99835`, `06933b402c`, `626421742e`, `1ed7d55dee`,
and the 2026-07-21 follow-up restoration commit.

### sweep-left-plan-orphans | medium | closed by retroactive authoring

Deleting the two thin "curation alignment" ADR stubs for
`aeat-cli-userdocs-hardening` and `aeat-user-docs-hardening` (their own problem
statements identify them as checker-silencing records, not decision records)
left both features' surviving plans without an ADR, and deleting the
agent-harness ADRs did the same for that feature. Closed on 2026-07-21 by two
substantive retroactive ADRs (`9a2d7ddae6`, `7f3040ee00`) and the agent-harness
restoration, returning `vault check all` to zero errors and zero warnings.

### bulk-deletion-of-closed-features | low | retired, recoverable

The large majority of the 251 deletions (the April/May corpus: cert-auth,
google-oauth's eight-ADR iteration chain, the secure-persistence-foundation
wave records, the cli-workflow-redesign shape ADRs, and roughly thirty one-off
campaign records with their plans, research, audits, and indexes) are records
of closed pre-refoundation campaigns whose decision surface was re-decided by
the June/July ADR corpus and the standing rule set. The mechanical pass
verified none leaves a surviving plan orphaned and none is cited by a standing
rule. They remain recoverable byte-exact from `ba2d7d494d^` / `651bdcba9d^` if
a live consumer surfaces; per-group supersession evidence is recorded in the
2026-07-21 disposition reports.

### archive-files-deleted | medium | breach noted, not restored

`ba2d7d494d` deleted 18 files from `.vault/_archive/` (the cert-auth /
live-cert-auth chain, two archived plans, two archive indexes). The archive
discipline treats `_archive` as permanent retirement inventory; deleting from
it contradicts that rule even when the content is dead. The content itself is
a fully closed and superseded auth chain, so it was not restored; git history
is now its archive of record. The breach is recorded here so the discipline
violation is not silently normalized.

### some-deletions-were-archive-moves | info | no action

Several apparent deletions were moves into `_archive` in the same sweep (the
cli-workflow-redesign epic plan, the aeat-cli-gap-closure plan, the
synthetic-filing-fixtures plan/research/audit trio). These are legitimate
archival and required no action.

## Recommendations

- A vault sweep that deletes documents MUST record its rationale — at minimum a
  commit message naming the disposition class per group, preferably a curation
  audit like this one authored alongside the sweep, not four days after it.
  A catch-all "commit accumulated changes" capture is not a disposition.
- Retirement of active-tree documents goes through `_archive` (the archive verb
  and its dry-run preview), never plain deletion; `_archive` itself is
  append-only retirement inventory and is not deleted from.
- Before deleting an ADR, check whether a standing rule cites it as source
  authority; a rule-cited ADR is active regardless of its age.
- The 2026-07-21 restoration set is the accepted disposition of these sweeps:
  seventeen documents restored (six in the first pass, eight plus three in the
  follow-ups, plus regenerated indexes), the remainder retired with the
  evidence recorded in the disposition reports. Future re-deletions of the
  restored set require an explicit operator ruling, given the concurrent
  staged vault-deletion activity observed in the shared worktree on
  2026-07-21.
