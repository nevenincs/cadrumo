---
generated: true
tags:
  - '#index'
  - '#cross-campaign-hardening'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-05-21-cross-campaign-hardening-P01-S02]]'
  - '[[2026-05-21-cross-campaign-hardening-P01-S03]]'
  - '[[2026-05-21-cross-campaign-hardening-P01-S04]]'
  - '[[2026-05-21-cross-campaign-hardening-P01-S05]]'
  - '[[2026-05-21-cross-campaign-hardening-P02-S08]]'
  - '[[2026-05-21-cross-campaign-hardening-P02-S09]]'
  - '[[2026-05-21-cross-campaign-hardening-P03-S10]]'
  - '[[2026-05-21-cross-campaign-hardening-P03-S11]]'
  - '[[2026-05-21-cross-campaign-hardening-P03-S12]]'
  - '[[2026-05-21-cross-campaign-hardening-P03-S13]]'
  - '[[2026-05-21-cross-campaign-hardening-P03-S14]]'
  - '[[2026-05-21-cross-campaign-hardening-P04-S15]]'
  - '[[2026-05-21-cross-campaign-hardening-P04-S16]]'
  - '[[2026-05-21-cross-campaign-hardening-P05-S17]]'
  - '[[2026-05-21-cross-campaign-hardening-P05-S18]]'
  - '[[2026-05-21-cross-campaign-hardening-P05-S19]]'
  - '[[2026-05-21-cross-campaign-hardening-P05-S24]]'
  - '[[2026-05-21-cross-campaign-hardening-P06-S25]]'
  - '[[2026-05-21-cross-campaign-hardening-P06-S26]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S27]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S28]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S29]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S30]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S31]]'
  - '[[2026-05-21-cross-campaign-hardening-P07-S32]]'
  - '[[2026-05-21-cross-campaign-hardening-P08-S33]]'
  - '[[2026-05-21-cross-campaign-hardening-P08-S34]]'
  - '[[2026-05-21-cross-campaign-hardening-P08-S35]]'
  - '[[2026-05-21-cross-campaign-hardening-P08-S36]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S37]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S38]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S39]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S40]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S41]]'
  - '[[2026-05-21-cross-campaign-hardening-P09-S42]]'
  - '[[2026-05-21-cross-campaign-hardening-P10-S43]]'
  - '[[2026-05-21-cross-campaign-hardening-P10-S44]]'
  - '[[2026-05-21-cross-campaign-hardening-P10-S45]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
  - '[[2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit]]'
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-06-04-cross-campaign-hardening-adr]]'
  - '[[2026-06-04-cross-campaign-hardening-research]]'
---

# `cross-campaign-hardening` feature index

Auto-generated index of all documents tagged with `#cross-campaign-hardening`.

## Documents

### adr

- `2026-06-04-cross-campaign-hardening-adr` - `cross-campaign-hardening` adr: `retrospective authority alignment` | (**status:** `accepted`)  ## Problem Statement  The linked plan records had implementation or audit history but no explicit ADR authority edge. That made schema validation fail and left semantic search without a clear decision source for developer briefings.  ## Considerations  This ADR is a vault-curation alignment record. It does not reopen the implementation, change runtime behavior, or supersede the original plan evidence. Its purpose is to make the existing authority chain explicit and navigable.  ## Constraints  The cleanup is restricted to the vault. Body wiki-links are avoided; frontmatter related fields carry the navigation edges required by the vault checks and by semantic discovery.  ## Implementation  Treat the linked plan records as historical execution sources and the linked research records as the evidence bridge for this retrospective authority alignment. Future work should brief from the current linked ADR and research pair before acting on older plan details.  ## Rationale  Adding an explicit ADR edge prevents plans from briefing developers without a decision source. Keeping the record retrospective prevents the cleanup itself from inventing a new architectural mandate.  ## Consequences  Schema validation can resolve plan-to-ADR authority, and semantic search can find the current decision edge. If a later ADR supersedes this alignment record, it must update frontmatter links on the associated plans and research notes.  ## Codification candidates  No project rule is promoted from this retrospective alignment alone.

### audit

- `2026-05-21-cross-campaign-hardening-audit` - `cross-campaign-hardening` audit: `cross-campaign-swarm-audit`
- `2026-05-21-cross-campaign-hardening-persona-testimonial-re-audit` - Cross-campaign hardening persona-testimonial re-audit

### exec

- `2026-05-21-cross-campaign-hardening-P01-S02` - `cross-campaign-hardening` `P01.S02`
- `2026-05-21-cross-campaign-hardening-P01-S03` - `cross-campaign-hardening` `P01.S03`
- `2026-05-21-cross-campaign-hardening-P01-S04` - `cross-campaign-hardening` `P01.S04`
- `2026-05-21-cross-campaign-hardening-P01-S05` - `cross-campaign-hardening` `P01.S05`
- `2026-05-21-cross-campaign-hardening-P02-S08` - `cross-campaign-hardening` `P02.S08`
- `2026-05-21-cross-campaign-hardening-P02-S09` - `cross-campaign-hardening` `P02.S09`
- `2026-05-21-cross-campaign-hardening-P03-S10` - `cross-campaign-hardening` `P03.S10`
- `2026-05-21-cross-campaign-hardening-P03-S11` - `cross-campaign-hardening` `P03.S11`
- `2026-05-21-cross-campaign-hardening-P03-S12` - `cross-campaign-hardening` `P03.S12`
- `2026-05-21-cross-campaign-hardening-P03-S13` - `cross-campaign-hardening` `P03.S13`
- `2026-05-21-cross-campaign-hardening-P03-S14` - `cross-campaign-hardening` `P03.S14`
- `2026-05-21-cross-campaign-hardening-P04-S15` - `cross-campaign-hardening` `P04.S15`
- `2026-05-21-cross-campaign-hardening-P04-S16` - `cross-campaign-hardening` `P04.S16`
- `2026-05-21-cross-campaign-hardening-P05-S17` - `cross-campaign-hardening` `P05.S17`
- `2026-05-21-cross-campaign-hardening-P05-S18` - `cross-campaign-hardening` `P05.S18`
- `2026-05-21-cross-campaign-hardening-P05-S19` - `cross-campaign-hardening` `P05.S19`
- `2026-05-21-cross-campaign-hardening-P05-S24` - `cross-campaign-hardening` `P05.S24`
- `2026-05-21-cross-campaign-hardening-P06-S25` - `cross-campaign-hardening` `P06.S25`
- `2026-05-21-cross-campaign-hardening-P06-S26` - `cross-campaign-hardening` `P06.S26`
- `2026-05-21-cross-campaign-hardening-P07-S27` - `cross-campaign-hardening` `P07.S27`
- `2026-05-21-cross-campaign-hardening-P07-S28` - `cross-campaign-hardening` `P07.S28`
- `2026-05-21-cross-campaign-hardening-P07-S29` - `cross-campaign-hardening` `P07.S29`
- `2026-05-21-cross-campaign-hardening-P07-S30` - `cross-campaign-hardening` `P07.S30`
- `2026-05-21-cross-campaign-hardening-P07-S31` - `cross-campaign-hardening` `P07.S31`
- `2026-05-21-cross-campaign-hardening-P07-S32` - `cross-campaign-hardening` `P07.S32`
- `2026-05-21-cross-campaign-hardening-P08-S33` - `cross-campaign-hardening` `P08.S33`
- `2026-05-21-cross-campaign-hardening-P08-S34` - `cross-campaign-hardening` `P08.S34`
- `2026-05-21-cross-campaign-hardening-P08-S35` - `cross-campaign-hardening` `P08.S35`
- `2026-05-21-cross-campaign-hardening-P08-S36` - `cross-campaign-hardening` `P08.S36`
- `2026-05-21-cross-campaign-hardening-P09-S37` - `cross-campaign-hardening` `P09.S37`
- `2026-05-21-cross-campaign-hardening-P09-S38` - `cross-campaign-hardening` `P09.S38`
- `2026-05-21-cross-campaign-hardening-P09-S39` - `cross-campaign-hardening` `P09.S39`
- `2026-05-21-cross-campaign-hardening-P09-S40` - `cross-campaign-hardening` `P09.S40`
- `2026-05-21-cross-campaign-hardening-P09-S41` - `cross-campaign-hardening` `P09.S41`
- `2026-05-21-cross-campaign-hardening-P09-S42` - `cross-campaign-hardening` `P09.S42`
- `2026-05-21-cross-campaign-hardening-P10-S43` - `cross-campaign-hardening` `P10.S43`
- `2026-05-21-cross-campaign-hardening-P10-S44` - `cross-campaign-hardening` `P10.S44`
- `2026-05-21-cross-campaign-hardening-P10-S45` - `cross-campaign-hardening` `P10.S45`

### plan

- `2026-05-21-cross-campaign-hardening-plan` - `cross-campaign-hardening` cross-campaign hardening rollout

### research

- `2026-06-04-cross-campaign-hardening-research` - `cross-campaign-hardening` research: `retrospective research grounding`  ## Question  Which existing vault decision records need an explicit research node so schema validation, semantic search, and future developer briefings have a stable evidence path?  ## Findings  This note is a retrospective vault-curation grounding record. It does not introduce a new product behavior, architectural direction, or implementation mandate.  The linked ADR records in frontmatter are the decision sources that lacked an explicit research reference during the 2026-06-04 schema cleanup. The surrounding vault corpus for this feature already held the plan, audit, execution, or prior research trail; this document makes that grounding discoverable through the required research document edge.  The curation pass used semantic vault search and frontmatter linkage review. Body wiki-links are intentionally avoided so the body-link hygiene gate remains clean; authoritative navigation lives in frontmatter.  ## Recommendation  Keep this document as the research bridge for the linked ADR records until a deeper feature-specific research note supersedes it. Any future supersession must update the frontmatter related fields on the affected ADRs and on this document so semantic search points to the current source.
