---
generated: true
tags:
  - '#index'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:9afad90f417ce00942fb05b147f10ee1e17ca9b03f1e49af59c92477aa8d4e89'
related:
  - '[[2026-09-09-registry-edition-authoring-W01-P01-S01]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P01-S02]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P01-S03]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P01-S34]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S05]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S06]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S07]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S40]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S46]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S47]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S49]]'
  - '[[2026-09-09-registry-edition-authoring-W01-P02-S57]]'
  - '[[2026-09-09-registry-edition-authoring-W02-P03-S09]]'
  - '[[2026-09-09-registry-edition-authoring-W02-P03-S43]]'
  - '[[2026-09-09-registry-edition-authoring-W02-P03-S45]]'
  - '[[2026-09-09-registry-edition-authoring-adr]]'
  - '[[2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference]]'
  - '[[2026-09-09-registry-edition-authoring-edition-restatement-measurement-research]]'
  - '[[2026-09-09-registry-edition-authoring-plan]]'
  - '[[2026-09-09-registry-edition-authoring-registry-mechanics-audit-research]]'
---

# `registry-edition-authoring` feature index

Auto-generated index of all documents tagged with `#registry-edition-authoring`.

## Documents

### adr

- `2026-09-09-registry-edition-authoring-adr` - `registry-edition-authoring` adr: `edition-relative casilla authoring` | (**status:** `proposed`)

### exec

- `2026-09-09-registry-edition-authoring-W01-P01-S01` - [S | sonnet-high] Record the baseline before any change: run the registry verify, dev-ci, dev-tooling and offline closure gates on current HEAD and capture exit codes and finding counts to a dated file. Proof: the file exists and names the commit it describes.
- `2026-09-09-registry-edition-authoring-W01-P01-S02` - [M | sonnet-high] Classify every assertion in the dev registry tests that requires findings to be non-empty or above a floor, as corpus-floor or detector-teeth, with file and line. Proof: a list whose counts reconcile with a fresh assertion sweep.
- `2026-09-09-registry-edition-authoring-W01-P01-S34` - [M | opus-medium] Decide the twelve population and ratio floors by asking of each the same question that governs the twelve guards: is the asserted population a defect we intend to repair, or a fact about the corpus we do not control? A frozen corpus count wearing a floor's clothing ratchets against this campaign and will fail the moment the delta lands, which is the worst possible time for a mystery failure. A floor asserting that the corpus exercises a code path at all is a different thing and should survive. Decide by that question, not by whether the assertion is spelled as a floor. Proof: each is kept with its reason, converted to a planted fixture, or deleted with a stated argument.
- `2026-09-09-registry-edition-authoring-W01-P02-S05` - [L | opus-medium] Write the lineage seeding tool as a scratch script over the corpus: chain casilla rows across editions by declared lineage, falling back to the bare identifier. Report coverage and the unchainable set per modelo. Proof: the unchainable rows are enumerated, not counted.
- `2026-09-09-registry-edition-authoring-W01-P02-S46` - [M | opus-medium] DONE. Adjudicated the two suspected correctness blockers. One was REFUTED: its box numbers did not move — a later edition introduced a dedicated printed-number field to carry what the earlier edition kept in the record-design metadata field, and the two agree exactly across every liquidation box, which is positive proof of identity. It seeds 71 chains with one row withheld pending two official designs. The other was CONFIRMED and is recoverable from evidence already in the corpus: an orden inserted six boxes at the head and shifted the tail by six, and the same official sentence quoted in both editions' citations names different boxes, which establishes the true correspondence. All eight of its bare matches are refused and seven true chains are declared instead.
- `2026-09-09-registry-edition-authoring-W01-P02-S47` - [L | opus-medium] DONE. All four modelos adjudicated one at a time, and each did fail differently. The label-derived one fell from 620 unchainable to 134 once the key was corrected and orphaned 21 rows. The reassignment one is CONFIRMED and larger than suspected — both the identifier and the concept behind the printed number moved, six boxes were inserted and the displaced concepts reappear six lower — giving 233 genuinely new rows, 124 recoverable, zero refusals, 115 held for one human pass and 1 withheld on a type flip. The wholly-new-edition one reproduces its 383 exactly and is NOT inflated, but only 110 rows are boxes AEAT added, zero are renumberings, and 248 were printed on the official form all along while the corpus's own thin extraction epoch never declared them. The shared-role one restates at 276: 243 genuinely new numbers proven absent from the predecessor design, and 33 that are a predecessor DECLARATION GAP rather than new boxes. Three things came out of it that outlive the four: the sha-pinned official record design is the strongest oracle where bundled and proves retirements as well as additions; a byte span alone must never chain; and a printed box number is unique per pagina, not per modelo. Proof met: every unchainable row per modelo is chained with evidence or declared new, and the two rows with no legal authority found are recorded as such rather than inferred.
- `2026-09-09-registry-edition-authoring-W01-P02-S49` - [M | opus-medium] DONE. The chaining tool was rewritten and the corpus restated: 2,509 unchainable rather than 2,734, and 273 contradicted chains rather than 345 or 260. Two corrections it surfaced must carry into the seeder. First, the box number must come from the dedicated printed-number field ONLY — falling back to the record-design metadata field when it holds a plain integer reintroduces the original error, because a one-byte wire campo declares exactly that, and it produced a false refusal. Second, the modelo-level tripwire must require a substantial predecessor set and bounded expansion, or it fires on ordinary growth where a small edition precedes a large one and wrongly holds every chain in four modelos.
- `2026-09-09-registry-edition-authoring-W01-P02-S57` - [S | opus-medium] Re-measure the corpus-wide unchainable population after the chaining tool is rewritten, before any per-modelo adjudication is scheduled on the old numbers. One modelo alone moved from 620 unmappable to 133, and the four-modelo concentration that shapes the whole lineage phase was derived from the same flawed key. If the true total is materially smaller, the phase is smaller and its ordering may be wrong. Proof: a restated per-modelo table, and an explicit statement of which earlier figures it supersedes.
- `2026-09-09-registry-edition-authoring-W02-P03-S43` - [M | opus-medium] Rule on the casilla-shaped rows that live OUTSIDE the casilla family. Roughly 4,821 of them sit in the completeness manifest across 93 files — more total rows than the casilla family itself carries. The decision's scope is drawn as a FAMILY boundary, but the row shape crosses it, so the materialiser and the minimality screen both need to know whether a manifest row is inherited, restated, or out of scope entirely. Decide it explicitly rather than discovering it during the pilot. Proof: the ruling is stated in the decision record and both the merge and the screen behave as it says on a fixture containing manifest rows.
- `2026-09-09-registry-edition-authoring-W02-P03-S45` - [L | opus-medium] Audit the thirty-six direct callers of the directory loader before the materialiser lands, because every one of them changes what it sees. Twenty-two are in the product tree and fourteen in development tooling, and three of those publish or validate generated trees — so whether a caller should observe declared or inherited rows is a real decision with a wrong answer. Classify each: correct with inherited rows, requires declared rows and needs a distinct accessor, or indifferent. Proof: every caller carries a verdict, and any that requires declared rows has one before the materialiser lands.
- `2026-09-09-registry-edition-authoring-W01-P01-S03` - [L | opus-medium] REPLACE, never delete. Each flagged line is the anti-vacuity guard for the assertion below it; removing it leaves that assertion passing vacuously on an empty finding set forever, which manufactures more of the defect this campaign removes. The population is TWELVE GUARDS IN TEN FILES, eight of the ten owned by the export lane. Triage each: a guard on a CORPUS DEFECT we intend to repair is converted to a planted-defect fixture asserting the same invariant; a guard on a PROPERTY OF THE PUBLISHED DOCUMENT stays untouched, because nothing here repairs what AEAT wrote. The triage splits five to convert, in four files, and seven to leave, in six of the export lane's files whose populations are read from AEAT's own record-design transcriptions. The owning lane signs off BOTH kinds of decision on its files — the replacement where one is made, and the decision to leave a guard where one is not — since leaving a guard is as much a ruling on their file as replacing it. A guard of the same class found outside the twelve is converted when the owning lane asks, not silently. Proof: each replacement fixture FAILS when the planted defect is removed from it — the collected count cannot detect this class and is not sufficient evidence — and every proof names the HEAD it was measured on, because a directed removal of git operations from the dev tooling will move the baseline.
- `2026-09-09-registry-edition-authoring-W01-P02-S06` - [M | sonnet-high] Seed lineage for the mechanical modelos, marking each seeded chain with an origin distinct from a grounded one. Admit a bare chain only when identifier, semantic role and data type all agree, and the box number agrees where both editions state one. COVERAGE AND IDENTITY ARE DIFFERENT QUESTIONS and must be answered from different fields: asking whether a row has a printed box at all, read both the dedicated printed-number field and the general one, because the shipped code does and a gate already asserts that both carry boxes today; asking whether two rows are the SAME box, admit the dedicated field only — the general field is heterogeneous by design, a one-byte wire campo declares a plain integer in it, and keying identity on it produced a false refusal. Conflating the two understates coverage roughly twentyfold in one modelo and fabricates chains in another. NEVER admit a chain on a byte span: a successor can keep record, campo ordinal, offset and width and put a different concept in the slot, and elsewhere 189 of 296 unchanged casillas moved their span across one boundary while every chain a span key offered was refuted by semantic role. Where the edition names a sha-pinned official record design, diff the bundled extract first — it is the strongest oracle available and it settles boundaries no in-registry field can, including proving that no box was retired. A row that chains to nothing must record WHICH kind of nothing: no predecessor existed, or the predecessor edition does not state one. Refuse and record rather than falling through to a weaker signal. Proof: zero contradicted chains written, no chain written on a span, no row written as new that the official design shows was already printed, every refusal recorded with its reason.
- `2026-09-09-registry-edition-authoring-W01-P02-S07` - [L | opus-medium] Adjudicate the modelo that renumbers boxes under stable identifiers, producing evolution records where the chain is real and an explicit refusal where it is not. This may not be mechanisable. Proof: every renumbered box is chained with evidence or refused by name.
- `2026-09-09-registry-edition-authoring-W01-P02-S40` - [M | opus-medium] Make the continuity gate READ the lineage origin marker and treat seeded and grounded chains differently. Writing the marker without a consumer leaves it decorative, and a seeded chain is inference written down rather than a statement — the gate must not accept one as evidence of the other. Proof: a seeded chain and a grounded chain with identical content produce different gate outcomes.
- `2026-09-09-registry-edition-authoring-W02-P03-S09` - [M | opus-medium] Add the predecessor key to the edition schema. An edition is delta-authored only when it declares one; the loader never infers it from absent rows. Proof: an edition without the key loads as a full-copy edition unchanged.

### plan

- `2026-09-09-registry-edition-authoring-plan` - `registry-edition-authoring` plan

### reference

- `2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference` - `registry-edition-authoring` reference: `code shape and blast radius`

### research

- `2026-09-09-registry-edition-authoring-edition-restatement-measurement-research` - `registry-edition-authoring` research: `edition restatement measurement`
- `2026-09-09-registry-edition-authoring-registry-mechanics-audit-research` - `registry-edition-authoring` research: `registry mechanics audit`
