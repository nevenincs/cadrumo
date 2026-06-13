---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-repo-health-triage-research]]'
---

# `repo-health-triage` audit: `Vault Health Curation Phase One`

## Scope

Vault-only curation pass for the `.vault` corpus after the user clarified that Phase
One is not code cleanup. The pass focused on vault health, semantic-search-backed
overlap mitigation, frontmatter/link validity, generated feature indexes, duplicate
stems, and template residue.

## Findings

- Mechanical vault health buckets were driven to zero for structure, frontmatter,
  annotations, links, dangling links, body links, orphans, references, and
  rename-integrity.
- RAG-backed searches identified and mitigated semantic overlap in the CLI
  testimonial, cross-campaign hardening, secure-storage, profile-lifecycle, docs,
  M210, and EU-locale clusters.
- The duplicate EU-locale execution stem was byte-identical in two restructure
  folders. Both records were preserved and renamed with parent-track context to avoid
  the stem collision.
- Feature indexes were regenerated for stale or missing features, including
  `repo-health-diagnostics` and `eu-locale`.
- The `repo-health-diagnostics` evidence is a diagnostic audit feature, not an
  approval of `aeat.diagnostics` as a production hexagonal module. The later
  repo-health code review explicitly rejected and removed that source package.
- The remaining schema errors were resolved by adding explicit plan-to-ADR and
  ADR-to-research frontmatter edges. Where no same-feature evidence node existed,
  retrospective research grounding notes were created and labeled as curation
  bridges, not new product decisions.
- Final validation for this pass reports zero errors and zero warnings across all
  vault checks. Feature lifecycle warnings were closed with explicit curation
  ADR/research bridges and regenerated feature indexes.

## Semantic conflict curation

- Resolved the profile-lifecycle supersession contradiction between the two
  2026-06-03 supersession ADRs. The active reading is now: the archived
  2026-05-18 cascade artifacts are historical/reference evidence only, the
  2026-05-16 profile-lifecycle plan is the surviving execution surface, and no
  successor sprint is active unless a later accepted authority re-enrols it.
- Added reader notes to the CLI workflow profile/init ADRs whose titles pointed
  only at the archived 2026-05-16 profile-lifecycle ADR. They now route readers
  to the active profile-lifecycle plan plus the 2026-06-03 supersession decision.
- Marked the old 2026-04-12 docs-rewrite plan as historical and superseded by
  the 2026-05-30 docs-architecture ADR/plan, matching the already-superseded
  docs-rewrite ADR.
- Re-ran RAG searches for registry reviewability, secure-object backlog drain,
  CLI testimonial, cross-campaign hardening, docs, domain-boundary,
  profile-lifecycle, M210, and Modelo 200 clusters. High-confidence
  contradictions were patched, and schema-critical missing ADR/research edges were
  closed with explicit retrospective curation records.

## Recommendations

- Treat the remaining feature lifecycle info diagnostics as Phase Two review
  inputs: classify each plan from the last week by status, enrolment, remaining
  percentage, and open steps before creating further authority documents.
- Continue using RAG search before resolving ADR/research relationships. Prefer
  existing persisted evidence links when the semantic match is clear; otherwise flag
  the gap instead of inventing a backlink.
- Keep shared-worktree safety explicit: no destructive git operations, no broad code
  cleanup, and no deletion of duplicate-looking vault records without owner approval.

## Codification candidates

No new codification candidate is proposed from this pass. The work reinforces
existing vaultspec curation, archive discipline, RAG, and shared-worktree safety
rules rather than revealing a new durable project constraint.
