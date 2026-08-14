---
tags:
  - '#adr'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:8d265f0dbb06316e55b3bc60df83ed1d99f5e6df385160c1991eb5c140ddceee'
related:
  - "[[2026-08-14-registry-temporal-coverage-research]]"
  - "[[2026-08-14-registry-corpus-structure-hardening-reference]]"
  - "[[2026-08-14-registry-corpus-structure-hardening-audit]]"
---

# `registry-temporal-coverage` adr: `filing-grade legal review and year-scoped registry authority` | (**status:** `accepted`)

## Problem Statement

The registry needs one honest answer to three inseparable filing-authority
questions: whether the law-selected revision has received human operator review,
whether every selected legal provision has received human legal review, and
whether that revision, provision, and source design apply to the requested filing
year. A corpus entry can be textually grounded without being operator-approved,
while an operator-approved provision can still be selected through an unreviewed
or over-broad revision outside the year it governs. Treating any one fact as
sufficient would turn inspectable evidence into filing authority.

The `2026-08-14-registry-corpus-structure-hardening-audit` exposed the review
provenance ambiguity, and `2026-08-14-registry-temporal-coverage-research`
established that open revision ranges conflate reviewed support with
extrapolation. This record decides the production boundary and the ordering
between machine-executable temporal repair and human legal attestation.

## Considerations

- Corpus grounding and filing eligibility answer different questions; the
  compiler must retain the former for repair work without granting the latter
  (`2026-08-14-registry-corpus-structure-hardening-reference`).
- Review provenance is declared evidence, never a derivable status or a fact an
  agent may assert for a person (`2026-07-27-conformance-cli-adr`).
- Revision signoff and legal-reference signoff are independent declarations. A
  reviewed legal slice cannot promote a pending revision, and a reviewed revision
  cannot promote agent-reviewed legal evidence.
- A revision is law-selected from modelo, filing year, and period; a stored or
  operator-supplied revision id may only confirm that result
  (`2026-06-10-period-revision-resolution-adr`).
- Open-ended selectors need an explicit evidence horizon rather than an
  assumption that an old form design and every nested legal reference remain
  authoritative forever (`2026-08-14-registry-temporal-coverage-research`).
- The validated authority and immutable snapshot remain the sole production
  orchestration boundary (`2026-05-20-registry-authority-flow-adr`).

## Considered options

- **Keep one `reviewed` token and trust reviewer prose.** Rejected: free text
  cannot distinguish agent preparation from human attestation and made the
  backlog look filing-ready.
- **Require every catalogue entry to be operator-reviewed before the registry
  loads.** Rejected: unrelated legal debt would disable inspection and repair of
  the whole authority instead of refusing only the filing slice that consumes
  it.
- **Accept agent review for filing when corpus checks pass.** Rejected: phrase
  presence, identity, applicability, and interpretation are distinct claims;
  automated grounding cannot impersonate the human legal decision.
- **Keep broad revisions and filter legal references ad hoc by effective date at
  snapshot time.** Rejected: record families, source designs, parameters, and
  legal references are one revision authority. Filtering only the final legal
  map leaves wrong-year schema and values selected upstream.
- **Typed review provenance plus year-scoped revision authority, with a
  snapshot-local human gate (chosen).** The compiler admits honest backlog for
  inspection; filing snapshots admit only an operator-reviewed, source-grounded
  revision whose complete selected legal slice is also operator-reviewed for that
  exact filing context.

## Constraints

- `pending_review`, `agent_reviewed`, and `operator_reviewed` are the complete
  legal-reference and revision-review vocabulary. Pending records carry no
  reviewer or date; reviewed records carry both. Reviewer attribution must contain
  a non-whitespace auditable identity, and the review date must fall within the
  fixed signoff sanity horizon used by revision governance.
- No agent, migration, generator, bulk command, inference from legacy prose, or
  conformance CLI may write `operator_reviewed` for either a legal reference or a
  revision. Only the operator who performed the relevant review may record that
  attestation.
- Operator review is per legal reference. It verifies identity, cited provision,
  corpus anchor, required presence clauses, forbidden absence clauses,
  applicability dates, and any amount or rate against live official authority.
  A failed check causes correction, repointing, scoping, or retirement before
  attestation; it is never overridden by a status flip.
- Existing exact operator attestations may migrate without claiming a new
  review. Every other legacy `reviewed` entry becomes no stronger than
  `agent_reviewed` until the ceremony occurs.
- Revision review is one revision at a time and independently verifies the
  selected schema, source membership, applicability window, legal membership,
  and continuity claims. It is not inferred from successful compilation,
  generated equality, or completed legal-reference review.
- A target snapshot whose revision or nested records select a provision outside
  a source-grounded filing-year authority must be repaired before that
  provision is presented for operator review. Human attestation cannot bless an
  incorrect selection topology.
- The accepted resolver and authority-flow parents are stable and remain in
  force. This record narrows the evidence admitted by those boundaries; it does
  not create a second selector, loader, or snapshot service.

## Implementation

`LegalReference.review_status` uses the core legal-review enum. Legal and revision
schema validation enforces coherent reviewer metadata, non-whitespace attribution,
and fixed review-date sanity bounds. Catalogue compilation validates identity and
corpus grounding for every entry without treating that pass as production
eligibility. Filing snapshot construction first requires the law-selected revision
to be `operator_reviewed`, then collects the complete legal-reference union from
the selected modelo, revision, and every nested record and refuses unless every
selected reference is `operator_reviewed`. The snapshot projects exactly that
checked slice.

`RegistrySnapshot` is filing-grade by definition and is never constructed without
those two human gates. Static authoring, audit, semantic-map work, and deterministic
generation instead consume a separately typed non-filing inspection projection
obtained through `ValidatedRegistryAuthority`. That projection uses the same
canonical `select_revision` and full registry validation while deliberately omitting
filing eligibility. It is not a `RegistrySnapshot`, cannot enter calculation,
filing-instance rendering, or handoff APIs, and cannot be replaced by raw-loader
output or a test-owned hand-built snapshot. This is a second projection of the one
authority, not a second selector, loader, or snapshot service.

Revision selection additionally requires an evidence-backed coverage boundary for
the requested schema family and filing context. A revision that combines different
annual form designs or time-bounded substantive provisions is split into the
smallest source-grounded epochs needed for unambiguous selection. Modelo 390 is the
first mandatory repair: its mixed `2010-y-siguientes` revision is replaced, on the
currently enrolled evidence, by disjoint 2022, 2023, 2024, and 2025 filing-year
epochs. Each epoch selects only its own record design; the 2025 source is capped at
2025-12-31; and the time-bounded RDL 4/2024 provision appears only in the 2024
slice. Filing years 2010-2021 and 2026 refuse as unsupported until their own source
authority is enrolled. The repair preserves canonical casilla identity and
continuity where meaning persists; it does not copy a later design backward or
retain the open revision as a compatibility fallback.

The operator-review campaign consumes a generated worklist but records decisions
one reference at a time. Each row names the official provision and corpus anchor,
the presence and absence assertions, applicability claim, affected filing
snapshots, and a falsifier. An agent may prepare that packet and run grounding
checks. The operator reads the cited authority, resolves any discrepancy, and
personally records `operator_reviewed`, reviewer identity, and review date in the
same atomic change. After each coherent batch, the legal grounding gates and exact
affected snapshots must pass. Population counts are audit observations, not a
baseline that authorizes mechanical promotion. After the Modelo 390 split, the
target worklist is an exact, exhaustive, pairwise-disjoint partition: nine
references shared by Modelo 303 and Modelo 390, nine used only by Modelo 303,
and two used only by Modelo 390. The campaign gate derives the selected unions
again and requires the `9 + 9 + 2 = 20` partition before and after review; a
changed union refuses and requires readjudication rather than silently expanding
a batch.

Execution distinguishes inspection work from filing work. S86 owns only the typed
inspection boundary and static generator contract. S67-S71 may consume that
inspection projection without depending on S88-S90. S87 owns the agent-executable
Modelo 390 temporal/source split. S88, S89, and S90 depend on S87 and carry the
human operator review of the exact shared-nine, Modelo-303-only-nine, and
Modelo-390-only-two partitions respectively, one attestation at a time. S91 depends
on S87-S90, carries one-at-a-time operator review of every target revision, proves
the real filing-grade snapshot matrix, and owns the filing-instance render proof
removed from S86. Static Modelo 390 generation may follow S87 through inspection;
filing rendering and final publication depend on S91. The Modelo 390 annual-summary
handoff S84 depends on S91 and therefore transitively on the split and every human
gate; it may never consume the inspection projection.

## Rationale

The chosen option is the only one that makes all three claims independently
falsifiable. Typed provenance prevents an agent-prepared entry or revision from
masquerading as human-reviewed. Snapshot-local enforcement prevents unrelated
review backlog from disabling the compiler. Year-scoped revision authority
prevents a genuine human signature from laundering a provision selected for the
wrong filing year. The distinct inspection type lets static repair proceed without
weakening the filing-grade meaning of `RegistrySnapshot`.

## Consequences

- Filing paths fail closed on the exact unfinished legal slice they consume;
  catalogue audit and repair remain available.
- The conservative migration exposes a large genuine human-work backlog. That
  backlog blocks affected filing features by design and cannot be burned down by
  automation.
- Modelo 390 temporal repair is a structural prerequisite, not part of the human
  ceremony. It may change revision membership and source selection while
  preserving proven continuity identities.
- Static generator and mapping work may proceed through the typed inspection
  projection after their structural prerequisites close. Filing-instance rendering
  and handoff work require exact real snapshots after revision and legal-reference
  operator review; focused unit success or catalogue-wide grounding is insufficient
  readiness evidence.
- Future modelos with open selectors need explicit evidence horizons or bounded
  epochs before new-year filing support can be claimed. The broader coverage
  manifest and revision-governance rollout remains follow-on work grounded by
  `2026-08-14-registry-temporal-coverage-research`.
