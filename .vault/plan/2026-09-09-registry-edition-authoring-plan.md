---
tags:
  - '#plan'
  - '#registry-edition-authoring'
date: '2026-09-09'
tier: L3
related:
  - '[[2026-09-09-registry-edition-authoring-adr]]'
  - '[[2026-09-09-registry-edition-authoring-edition-restatement-measurement-research]]'
  - '[[2026-09-09-registry-edition-authoring-registry-mechanics-audit-research]]'
  - '[[2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference]]'
modified: '2026-09-11'
body_schema: body-v2
body_hash: 'sha256:cf99351721c6461e7bb5d101d08222245093f690fadd156e0247974ff605a380'
---

# `registry-edition-authoring` plan

## Description

Convert successor editions of each modelo from full copies to declarations of what differs,
under the decision recorded in `2026-09-09-registry-edition-authoring-adr`. The measurement
driving it is in `2026-09-09-registry-edition-authoring-edition-restatement-measurement-research`;
the code surface and its costs are in
`2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference`.

### The population

Fifty-eight modelos, one hundred and twenty-eight editions. **Twenty-five modelos have exactly one
edition** — no successor, nothing to delta-author. They remain in scope for the corpus-wide
restatement lifting, because their rows still restate their own edition, and out of scope for
everything in the migration wave. The real migration population is thirty-three modelos, of which
nine are named in their own steps and twenty-four fall to the batch.

Within the migration wave, four modelos are named as explicitly **not** delta-authored and get a
recorded disposition instead: one whose sparse successor withholds by design, one whose editions
are parallel scheme variants with no definable predecessor, one holding twelve rows across six
editions, and one already carrying an authored prose refusal.

### How to read a step

Every step opens with `[size | agent]`.

**Size** is the briefing unit, not a time estimate. `S` is one bounded change with an obvious
proof. `M` is a change plus its gate, or a sweep with a mechanical check. `L` needs judgement
about something the plan does not settle. `XL` may not be completable as specified and should
report back rather than improvise.

**Agent** is the dispatch target. `sonnet-high` takes mechanical, bounded work whose correctness
is checkable by a script: renames, per-modelo migrations once the tooling is proven, assertion
conversion. `opus-medium` takes work that changes a contract or requires a judgement call:
loader changes, gate design, adjudication, anything where the right answer is not determined by
the existing code.

A step is sized for one agent. Nothing here needs a team.

### How this work should be done

This is a data-manipulation campaign with a code change at its centre, and the data outnumbers
the code by orders of magnitude. The default execution mode is a **scratch script that rewrites
the corpus programmatically**, run from a scratch directory, never committed. Hand-editing
declaration files is the wrong tool at every step here, and a step that finds itself editing TOML
by hand has misread its own scope.

Blast radius is hit by sweeping, not by grepping once and trusting it. Before any rename or
rewrite, enumerate the full target set and write it down; after, re-run the same sweep and prove
it returns nothing. The counts in the reference document are reproducible sweeps and are the
starting point, not the answer.

Measure against the consuming code, not against the declarations. A census of what the corpus
*declares* is not a census of what the shipped product *reads*, and this campaign has already
produced four wrong numbers that way — each one a correct count over a population nothing
consumes. Trace to the consumer before reporting a figure.

The corpus is under concurrent change by other sessions in this worktree. Re-read before writing,
and check that the surface a step touches has not moved since the step was briefed.

### Hard orderings

These are not preferences and a step that violates one produces work that must be redone.

- The harness conversion precedes every gate this campaign adds, and precedes the promotion step
  absolutely. Promoting gates while assertions still require the corpus to be dirty installs a
  ratchet against ever cleaning it.
- Lineage precedes any delta authoring. Inheritance cannot key on a field that is absent.
- **Lineage also precedes the minimality screen.** The screen asks whether a stated row is
  identical to the row it would inherit, and without a chain there is no such row — it would fall
  back to bare-identifier matching, which is precisely what the lineage step is measuring and may
  find unreliable.
- The loader-caller audit precedes the materialiser, because the materialiser changes what every
  caller of the shared loader observes.
- The predecessor forest rule lands in the same change as the materialiser, or a silently missing
  predecessor compounds with silent inheritance. It also makes the minimality screen non-vacuous.
- The materialiser and the label-catalogue inheritance land together. An edition whose rows
  inherit while its labels do not raises on first read.
- **The governance stamp must state its own scope before the first modelo migrates.** After
  migration a reviewer signs a delta while the compiled edition carries inherited rows the
  reviewer never saw: the stamp stays literally true while what it covers shrinks, and nothing
  surfaces the difference. This is a precondition of the pilot rather than a follow-up, at the
  request of the lane that owns it — an attestation should name its own scope rather than depend
  on the reader knowing which model was in force when it was signed.
- The format and loader precede the restatement families, which precede migration.
- The legal-reference gate precedes modelo 100's migration, or its delta shows authoring drift as
  though it were legal change.
- The pilot precedes every other modelo, and its hardening step precedes the batch work.
- Cache fingerprints must key on the physical files read. Every later step depends on this
  silently.

### What this plan does not do

**It does not rename `revision` to `edition` on disk.** The decision settles the vocabulary, but
the rename is 92,616 table headers, 129 filenames and 58 directories against a small code surface,
and nothing in this campaign rewrites those files. It is deferred rather than scheduled, and the
decision's naming clause should be read as settling terms for future work, not as authorising a
migration here. The same applies to consolidating the modelo number type and renaming the export
family to wire.

It does not extend delta authoring beyond casilla declarations. The lineage field this depends on
exists nowhere else in the tree, and the two heaviest families by bytes show weak cross-edition
similarity for a structural reason — fixed-width offsets renumber whenever a record gains or loses
a field.

It does not touch the wire slot addressing union, the authoring lane, or the requirement column,
which are settled or in flight elsewhere. It does not improve completeness coverage, and no step
should be described as if it does.

## Steps

## Wave `W01` - Preconditions

Establish the baseline, convert the harness off corpus-floor assertions, and state casilla lineage. Nothing in later waves is provable until these land.

### Phase `W01.P01` - Baseline and harness

Capture what green means today, then convert the assertions that require the corpus to stay dirty. Doing this after any gate lands would build a ratchet against cleaning.

- [x] `W01.P01.S01` - [S | sonnet-high] Record the baseline before any change: run the registry verify, dev-ci, dev-tooling and offline closure gates on current HEAD and capture exit codes and finding counts to a dated file. Proof: the file exists and names the commit it describes.; `justfile`.
- [x] `W01.P01.S02` - [M | sonnet-high] Classify every assertion in the dev registry tests that requires findings to be non-empty or above a floor, as corpus-floor or detector-teeth, with file and line. Proof: a list whose counts reconcile with a fresh assertion sweep.; `dev/registry/tests`.
- [x] `W01.P01.S03` - [L | opus-medium] REPLACE, never delete. Each flagged line is the anti-vacuity guard for the assertion below it; removing it leaves that assertion passing vacuously on an empty finding set forever, which manufactures more of the defect this campaign removes. The population is TWELVE GUARDS IN TEN FILES, eight of the ten owned by the export lane. Triage each: a guard on a CORPUS DEFECT we intend to repair is converted to a planted-defect fixture asserting the same invariant; a guard on a PROPERTY OF THE PUBLISHED DOCUMENT stays untouched, because nothing here repairs what AEAT wrote. The triage splits five to convert, in four files, and seven to leave, in six of the export lane's files whose populations are read from AEAT's own record-design transcriptions. The owning lane signs off BOTH kinds of decision on its files — the replacement where one is made, and the decision to leave a guard where one is not — since leaving a guard is as much a ruling on their file as replacing it. A guard of the same class found outside the twelve is converted when the owning lane asks, not silently. Proof: each replacement fixture FAILS when the planted defect is removed from it — the collected count cannot detect this class and is not sufficient evidence — and every proof names the HEAD it was measured on, because a directed removal of git operations from the dev tooling will move the baseline.; `dev/registry/tests`.
- [x] `W01.P01.S04` - [M | opus-medium] Add the delta-minimality screen in reporting mode only: no stated row is identical to the row it would inherit. SCOPE IT TO CASILLA ROWS ONLY. The completeness manifest does not inherit, so every migrated edition still restates its whole manifest — a screen spanning both families would report every migrated modelo as non-minimal forever, which is a permanently wrong answer rather than a noisy one. Proof: it names a modelo known to restate its casillas, and does not name a migrated modelo on manifest grounds.; `dev/registry/analysis`.
- [x] `W01.P01.S34` - [M | opus-medium] Decide the twelve population and ratio floors by asking of each the same question that governs the twelve guards: is the asserted population a defect we intend to repair, or a fact about the corpus we do not control? A frozen corpus count wearing a floor's clothing ratchets against this campaign and will fail the moment the delta lands, which is the worst possible time for a mystery failure. A floor asserting that the corpus exercises a code path at all is a different thing and should survive. Decide by that question, not by whether the assertion is spelled as a floor. Proof: each is kept with its reason, converted to a planted fixture, or deleted with a stated argument.; `dev/registry/tests`.

### Phase `W01.P02` - Lineage

State the casilla chain that inheritance keys on. Seeded chains are marked as seeded so the continuity gate can tell inference-written-down from a grounded statement.

- [x] `W01.P02.S05` - [L | opus-medium] Write the lineage seeding tool as a scratch script over the corpus: chain casilla rows across editions by declared lineage, falling back to the bare identifier. Report coverage and the unchainable set per modelo. Proof: the unchainable rows are enumerated, not counted.; `dev/registry/analysis`.
- [x] `W01.P02.S06` - [M | sonnet-high] Seed lineage for the mechanical modelos, marking each seeded chain with an origin distinct from a grounded one. Admit a bare chain only when identifier, semantic role and data type all agree, and the box number agrees where both editions state one. COVERAGE AND IDENTITY ARE DIFFERENT QUESTIONS and must be answered from different fields: asking whether a row has a printed box at all, read both the dedicated printed-number field and the general one, because the shipped code does and a gate already asserts that both carry boxes today; asking whether two rows are the SAME box, admit the dedicated field only — the general field is heterogeneous by design, a one-byte wire campo declares a plain integer in it, and keying identity on it produced a false refusal. Conflating the two understates coverage roughly twentyfold in one modelo and fabricates chains in another. NEVER admit a chain on a byte span: a successor can keep record, campo ordinal, offset and width and put a different concept in the slot, and elsewhere 189 of 296 unchanged casillas moved their span across one boundary while every chain a span key offered was refuted by semantic role. Where the edition names a sha-pinned official record design, diff the bundled extract first — it is the strongest oracle available and it settles boundaries no in-registry field can, including proving that no box was retired. A row that chains to nothing must record WHICH kind of nothing: no predecessor existed, or the predecessor edition does not state one. Refuse and record rather than falling through to a weaker signal. Proof: zero contradicted chains written, no chain written on a span, no row written as new that the official design shows was already printed, every refusal recorded with its reason.; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W01.P02.S07` - [L | opus-medium] Adjudicate the modelo that renumbers boxes under stable identifiers, producing evolution records where the chain is real and an explicit refusal where it is not. This may not be mechanisable. Proof: every renumbered box is chained with evidence or refused by name.; `src/cadrumo/_data/registry/aeat/modelos/309`.
- [x] `W01.P02.S08` - [M | opus-medium] Add the lineage totality gate, failing closed: a successor-edition row must carry lineage or declare itself new. A row carries lineage when its chain id is also carried by the edition immediately before it, or when it declares an origin (which S40's gate then enforces); an absence origin declares its kind of none; anything else is unresolved — including a row whose id only starts its chain in its own edition. Totality is a completeness property of the authoring corpus, NOT a load-time validity condition: the product must keep loading a registry whose lineage is partial, and one modelo will stay partial for a long campaign. So the RULE is a pure function in the registry package taking the exception set as a parameter, and the GATE that enforces it runs in the dev lane, fed from the seeding ledger, and fails the lane on any unlisted unresolved row. Unresolved rows pass only as per-row, classified ledger entries — never a modelo, prefix or count exemption. Modelos not yet examined are enumerated row by row as not-examined with their reason: the list is closed, so a new row added later is caught and an entry whose row gains lineage fails as stale, which a modelo-wide carve-out would never do. Proof: a planted row with neither is refused; a stale exception is refused; a row with a resolved id or an absence origin passes; the corpus passes with every unresolved row accounted for.; `src/cadrumo/domain/calculations/registry`.
- [x] `W01.P02.S40` - [M | opus-medium] Make the continuity gate READ the lineage origin marker and treat seeded and grounded chains differently. Writing the marker without a consumer leaves it decorative, and a seeded chain is inference written down rather than a statement — the gate must not accept one as evidence of the other. Proof: a seeded chain and a grounded chain with identical content produce different gate outcomes.; `src/cadrumo/domain/calculations/registry`.
- [x] `W01.P02.S46` - [M | opus-medium] DONE. Adjudicated the two suspected correctness blockers. One was REFUTED: its box numbers did not move — a later edition introduced a dedicated printed-number field to carry what the earlier edition kept in the record-design metadata field, and the two agree exactly across every liquidation box, which is positive proof of identity. It seeds 71 chains with one row withheld pending two official designs. The other was CONFIRMED and is recoverable from evidence already in the corpus: an orden inserted six boxes at the head and shifted the tail by six, and the same official sentence quoted in both editions' citations names different boxes, which establishes the true correspondence. All eight of its bare matches are refused and seven true chains are declared instead.; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W01.P02.S47` - [L | opus-medium] DONE. All four modelos adjudicated one at a time, and each did fail differently. The label-derived one fell from 620 unchainable to 134 once the key was corrected and orphaned 21 rows. The reassignment one is CONFIRMED and larger than suspected — both the identifier and the concept behind the printed number moved, six boxes were inserted and the displaced concepts reappear six lower — giving 233 genuinely new rows, 124 recoverable, zero refusals, 115 held for one human pass and 1 withheld on a type flip. The wholly-new-edition one reproduces its 383 exactly and is NOT inflated, but only 110 rows are boxes AEAT added, zero are renumberings, and 248 were printed on the official form all along while the corpus's own thin extraction epoch never declared them. The shared-role one restates at 276: 243 genuinely new numbers proven absent from the predecessor design, and 33 that are a predecessor DECLARATION GAP rather than new boxes. Three things came out of it that outlive the four: the sha-pinned official record design is the strongest oracle where bundled and proves retirements as well as additions; a byte span alone must never chain; and a printed box number is unique per pagina, not per modelo. Proof met: every unchainable row per modelo is chained with evidence or declared new, and the two rows with no legal authority found are recorded as such rather than inferred.; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W01.P02.S49` - [M | opus-medium] DONE. The chaining tool was rewritten and the corpus restated: 2,509 unchainable rather than 2,734, and 273 contradicted chains rather than 345 or 260. Two corrections it surfaced must carry into the seeder. First, the box number must come from the dedicated printed-number field ONLY — falling back to the record-design metadata field when it holds a plain integer reintroduces the original error, because a one-byte wire campo declares exactly that, and it produced a false refusal. Second, the modelo-level tripwire must require a substantial predecessor set and bounded expansion, or it fires on ordinary growth where a small edition precedes a large one and wrongly holds every chain in four modelos.; `dev/registry/analysis`.
- [x] `W01.P02.S57` - [S | opus-medium] Re-measure the corpus-wide unchainable population after the chaining tool is rewritten, before any per-modelo adjudication is scheduled on the old numbers. One modelo alone moved from 620 unmappable to 133, and the four-modelo concentration that shapes the whole lineage phase was derived from the same flawed key. If the true total is materially smaller, the phase is smaller and its ordering may be wrong. Proof: a restated per-modelo table, and an explicit statement of which earlier figures it supersedes.; `dev/registry/analysis`.

## Wave `W02` - Mechanism

Build the one format and the one reader: an explicit predecessor key, the loader materialiser, and the three restatement families handled by their own rules. Corpus-wide, once.

### Phase `W02.P03` - Format and loader

One format with an explicit predecessor, one reader, and the proof obligations that make a migration acceptable.

- [x] `W02.P03.S09` - [M | opus-medium] Add the predecessor key to the edition schema. An edition is delta-authored only when it declares one; the loader never infers it from absent rows. Proof: an edition without the key loads as a full-copy edition unchanged.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S10` - [L | opus-medium] Build the materialiser between raw fragment assembly and typed construction, producing the same merged mapping typed construction already consumes. The construction signature and everything above it are untouched. Proof: consumers observe no change on an unmigrated corpus.; `src/cadrumo/domain/calculations/registry/_loader_internals.py`.
- [x] `W02.P03.S11` - [M | opus-medium] Add the cache-teeth test: fingerprints follow the physical edition files read, never the expanded output. Proof: editing a delta file invalidates; a materialisation difference with identical files does not.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S12` - [M | opus-medium] Add the round-trip gate: a materialised edition equals its pre-migration materialisation by typed equality, and its export bytes are unchanged. This gate is what makes each migration step acceptable and is retired after the last modelo. Proof: it passes on the unmigrated corpus before any modelo moves.; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `W02.P03.S35` - [M | opus-medium] Add the predecessor forest validator: every edition of a modelo declares a predecessor except exactly one, and the graph must be a single tree rooted at that one with no cycle, no unknown or self target, and every edition reachable. The unique root positively identifies a first edition, and a successor that omits its predecessor becomes a second root and is refused naming both. Mark the field manifest-only so a section fragment cannot declare it. Proof: a three-edition fixture whose third omits the key is refused as two roots; restoring it loads.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S36` - [M | opus-medium] Refuse a declared predecessor where the successor withholds by design — a lower authority grade than its predecessor, or a header-only edition refusing to state figures it cannot ground. Inheriting there would silently materialise withheld rows. This must be a load-time refusal keyed on the declared grades because the minimality screen is structurally blind to it: an edition stating two rows matches nothing inherited and reports clean. Proof: the modelo declaring nearly two thousand rows then two is refused if a predecessor is declared, and loads unchanged without one.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S37` - [M | opus-medium] Position the materialiser inside typed construction immediately after the raw editions resolve and BEFORE per-edition localization enrolment, AND make the label catalogue inherit alongside the declarations in the same change. Locale keys are edition-scoped, so an inherited row enrolled before localization takes the successor's key — the right shape — but has no successor-keyed catalogue entry, and the lookup raises rather than falling back. Rows inheriting while labels do not is not a complete edition. Reuse the shipped locale cascade, which already resolves base, override and exact on this same lineage field. Proof: a migrated edition's locale keys match its pre-migration keys AND every casilla still yields a non-empty label under the historical-epoch sweep that already asserts exactly that.; `src/cadrumo/domain/calculations/registry/_loader_internals.py`.
- [x] `W02.P03.S41` - [S | sonnet-high] Check every enumeration this campaign introduces against the proposed registry enum-canonicalisation ruling — one named enum per closed vocabulary, no inline unions, no allowlist — and reconcile or record the divergence. That ruling is proposed rather than accepted, so this is a compatibility check and not an obligation to obey it. Proof: each new enumeration is either conformant or carries a stated reason.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S43` - [M | opus-medium] Rule on the casilla-shaped rows that live OUTSIDE the casilla family. Roughly 4,821 of them sit in the completeness manifest across 93 files — more total rows than the casilla family itself carries. The decision's scope is drawn as a FAMILY boundary, but the row shape crosses it, so the materialiser and the minimality screen both need to know whether a manifest row is inherited, restated, or out of scope entirely. Decide it explicitly rather than discovering it during the pilot. Proof: the ruling is stated in the decision record and both the merge and the screen behave as it says on a fixture containing manifest rows.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S45` - [L | opus-medium] Audit the thirty-six direct callers of the directory loader before the materialiser lands, because every one of them changes what it sees. Twenty-two are in the product tree and fourteen in development tooling, and three of those publish or validate generated trees — so whether a caller should observe declared or inherited rows is a real decision with a wrong answer. Classify each: correct with inherited rows, requires declared rows and needs a distinct accessor, or indifferent. Proof: every caller carries a verdict, and any that requires declared rows has one before the materialiser lands.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S48` - [S | opus-medium] Give the predecessor key an explicit value meaning no predecessor exists, distinct from the key being absent. One modelo has three editions sharing a single validity date whose own declarations each assert they have no earlier sibling; without an explicit value it would be forced into a false sequence, and with the key merely absent it would be indistinguishable from a forgotten declaration. Proof: that modelo loads with all three editions declared parallel, and the forest rule accepts it without inventing an order.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S55` - [S | sonnet-high] Make the materialiser's exclusion of non-casilla families explicit and tested, rather than relying on it merging only what it was told to. The completeness manifest is a revision section merged by the same fragment machinery as the casillas, so a materialiser written against the raw revision mapping picks it up by default; and its casilla collection is an append array whose duplicate-identifier validator would then refuse the load with an error naming a duplicate rather than naming inheritance. Loud but misattributed is still expensive. Proof: a planted delta whose predecessor has manifest rows materialises with the successor's own manifest untouched, and the duplicate-identifier path is never reached.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P03.S61` - [S | opus-medium] Add the declared-predecessor date-agreement rule: where an edition names a predecessor and the two editions do not overlap in validity, the predecessor must be the earlier one; overlapping editions are exempt, and that exemption is exactly the parallel-variant case. Also make the lineage totality rule follow a named predecessor edge instead of the adjacent edition. Both land before the first modelo migrates. Proof: a successor naming a later non-overlapping edition is refused naming both; an overlapping pair loads; a totality fixture with a named non-adjacent predecessor resolves against the named edition.; `src/cadrumo/domain/calculations/registry`.

### Phase `W02.P04` - Restatement families

Move source references to the edition, make export references derived, and stop formula and binding identifiers embedding an edition key.

- [x] `W02.P04.S51` - [M | opus-medium] Decide where an inherited row's generated export references are written, because publication refuses without an answer. The real declared-versus-generated comparison is not in any loader caller — it sits one call deeper, where the generated layout's addressed casillas are differenced against the identifiers read from the raw declaration files on disk. Under delta authoring a layout addressing an INHERITED casilla finds no file to write into, and publication fails loudly. That is the right failure mode, but it needs a decision rather than a discovery. Coordinate with the generator lane, which owns that module and has offered to retire it. Proof: a migrated modelo publishes, or refuses for a stated reason that is not this one.; `dev/registry/pipeline`.
- [x] `W02.P04.S14` - [L | opus-medium] Make export references a derived field: the loader computes them from the edition layout's own back-pointer and refuses an authored value. Delete the pipeline module that currently writes them onto casilla declarations. Proof: an authored value is refused; computed values match today's declarations byte for byte.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P04.S13` - [M | opus-medium] Declare source references and orden references once on the edition, inherited by rows that state none. Proof: a row stating its own overrides; a row stating none inherits; the materialised row is unchanged from today.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P04.S16` - [M | opus-medium] Resolve inherited formula and binding references through lineage against the successor edition's own declaration; an unresolvable reference is a validation failure, never an inherited pointer. Proof: a planted dangling reference is refused.; `src/cadrumo/domain/calculations/registry`.
- [x] `W02.P04.S15` - [M | sonnet-high] Remove the edition key from formula and binding identifiers by programmatic rewrite, with every reference updated in the same pass. Bounded rename, but references must not break. Proof: no identifier in these two families contains an edition key, and registry validation is clean.; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W02.P04.S52` - [M | opus-medium] Fix candidate staging, which copies a predecessor's raw casilla directory wholesale and would therefore copy a DELTA rather than an edition once the predecessor is migrated. It also walks the continuity-evolution chain rather than the edition-inheritance chain, so under this decision it follows the wrong relationship. Proof: staging a candidate from a migrated predecessor produces a complete edition, and the chain it walks is the declared predecessor chain.; `dev/registry/pipeline/candidate_staging.py`.
- [x] `W02.P04.S56` - [M | opus-medium] Fix isolated staging, which deletes exactly what a delta edition needs. The publication path stages a single edition by copying the modelo and removing every sibling directory, so staging a migrated successor deletes its predecessor: the staged tree then declares a predecessor that does not exist, and either the forest rule refuses it or it materialises to only its stated rows and presents a partial edition as complete. The function exists to create isolation, and isolation is precisely what an inheriting edition cannot survive. Two options: keep the ancestor chain when staging, or materialise before staging. The owning lane prefers materialise-before-staging and the reason is sound — it makes the staged thing a complete edition by construction, rather than depending on every downstream check knowing it is looking at a fragment. Proof: a migrated multi-edition modelo stages and validates in isolation, and a staged delta whose predecessor was removed is refused rather than silently thinned.; `dev/registry/pipeline/cli.py`.

## Wave `W03` - Migration

Convert each modelo to delta authoring, ordered by measured similarity. One modelo per step, each proved independently before the next begins.

### Phase `W03.P05` - Pilot

One modelo end to end, on the richest instrumentation, before any other modelo moves.

- [x] `W03.P05.S31` - [M | opus-medium] Give the materialised edition a reader, so a person can see a complete edition without reconstructing it mentally from a delta. Without this the tree is harder to work with, not easier. Proof: the reader renders a migrated edition identically to its pre-migration files.; `src/cadrumo/entrypoints/cli`.
- [x] `W03.P05.S62` - [M | opus-medium] Implement the amended materialiser contract before the live pilot: (1) the round-trip gate's order assertion compares against the full copy rearranged into the merge order (inherited in predecessor order, superseders in place, new rows appended), with content still element-wise; (2) a row may state source references in addition to the edition's casilla_source_refs, materialising as default followed by additions that inherit with the row, while a full source_refs still replaces (name the additions key canonically); (3) continuidad_origin and continuidad_evidence are never inherited — an inherited row materialises with both unset; (4) the delta-minimality screen judges stated rows only, via a statement-origin marker, not inherited ones. Then re-run the migration script's 303 dry run. Proof: all five 303 successor editions migrate exactly in the dry run, the round-trip gate passes on them, delta-minimality is clean for 303, and the unmigrated corpus is byte-identical.; `src/cadrumo/domain/calculations/registry`.
- [x] `W03.P05.S64` - [M | opus-medium] Translate the continuity-key locale entries that copy the Spanish source text, before the live pilot. The 303 dry run showed inherited rows resolving a predecessor's real translation where the full copy fell through to a continuity-key entry holding untranslated Spanish in ca, en and hu (84 casillas per 303 edition). A copied source string does not satisfy locale coverage, so this is a catalogue defect that inheritance exposes, not a migration error. Through the canonical locale workflow only, give each affected continuity key a real translation in every supported locale, grounded in the lineage's existing translations, and add a locale-coverage check that fails when a continuity-key entry equals its Spanish source in a non-Spanish locale unless it is classified as untranslatable. Proof: the round-trip gate's locale identity passes on the migrated 303 dry run; the new check fails on a planted copied entry.; `src/cadrumo/locales`.
- [x] `W03.P05.S17` - [L | opus-medium] Migrate modelo 303 end to end as the pilot: lift its restatement, author its successor editions as deltas, and prove it. Richest instrumentation in the corpus, so a mistake is cheapest to see here. Proof: round-trip equality, export bytes unchanged, delta-minimality clean for 303.; `src/cadrumo/_data/registry/aeat/modelos/303`.
- [ ] `W03.P05.S18` - [M | opus-medium] Harden the migration script against what the pilot exposed, and fix the proof obligations that turned out to be weak. Everything after this step depends on the script rather than on judgement. Proof: re-running the pilot from a clean checkout reproduces it exactly.; `dev/registry`.
- [x] `W03.P05.S63` - [M | opus-medium] Unblock the successor edges that fail for missing lineage rather than order: of 67 successor edges, 33 are blocked because a predecessor row carries no continuidad_id, 2 by a lineage withdrawn without a retirement record, and 1 by a lower authority grade (that one correctly stays full-copy). For each lineage-blocked edge, seed or ground the missing predecessor-row lineage through the existing seeder and rulings (seeded marked apart from grounded, no identity from a byte span or box number alone), and declare each real withdrawal as a retirement evolution grounded in the official design. Rows that cannot be grounded stay unresolved in the lineage ledger, never guessed. Proof: the migration script reports each unblocked edge as migratable, the lineage totality gate stays at zero uncovered and zero stale, and every edge still blocked is listed with its reason.; `src/cadrumo/_data/registry/aeat/modelos`.
- [x] `W03.P05.S42` - [S | sonnet-high] Verify during the pilot that the temporal-coverage design-authority refusal pin still passes untouched. The decision asserts it does not weaken that refusal; the assertion is cheap to check and expensive to be wrong about, since a live test carries it. Proof: the pin passes before and after the pilot migration, quoted with its result.; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `W03.P05.S50` - [S | sonnet-high] During the pilot, check the two consumers the caller audit flagged as reachable but untraced. One resolves generic numeric tokens by unique left-pad against the declared identity set, so a larger inherited set can turn a previously unique resolution ambiguous — permissive in direction but not in effect. The other compares a casilla's export references against what the layout carries; the decision makes those references derived rather than inherited, which should neutralise it, so confirm that rather than assume it. Proof: both checked against the migrated pilot, with the finding count before and after.; `dev/registry`.
- [x] `W03.P05.S54` - [S | sonnet-high] Use the existing cross-revision drift assertion as the pilot's free retirement detector. It already asserts a specific casilla is absent from a later edition of modelo 100, backed four lines on by that edition's own retirement declaration. If the materialiser fails to honour retirement, that casilla is resurrected and the assertion fails without anything new being written. Note also that most callers classified indifferent are indifferent only because their fixtures declare a single edition, so they will not detect a materialiser defect either — indifference is not coverage, and the pilot's gates must not lean on them.; `src/cadrumo/domain/calculations/registry/tests`.

### Phase `W03.P06` - High-similarity modelos

The modelos measured at 93 percent or better once restatement is removed. Mechanical once the pilot proves the tooling.

- [ ] `W03.P06.S19` - [M | opus-medium] Modelo 490 is ADJUDICATED; migrate it on the ruling rather than re-measuring. The 'full similarity' figure was measured on its first boundary only, where the two editions are identical at 153/153; the modelo runs 153/153/353/386 and belongs with the divergent ones. Its 357 unchainable rows split into 233 genuinely new and 124 with a recoverable predecessor, the two sets complementary with no residue, and it carries ZERO refused chains — a coverage problem, never a correctness one. Seed as none: the 33 rows of the last boundary, provable by a 68-line diff of two sha-pinned designs where reserved cells become a new territory's fields, and the 200 new rows of the middle boundary. Seed 8 proven chains, each carrying a second independent witness. HOLD 115 pending one human pass: a plain letter shift across seven repeating stems needs label normalisation, and which repeating block a row belongs to is positional convention the record design cannot answer. WITHHOLD 1 where the label matches but the declared type flips. Never key a chain on the byte span here: the successor keeps record, campo, offset and width and puts a different concept in the slot. Proof: no chain written on a span, the held and withheld rows enumerated rather than counted.; `src/cadrumo/_data/registry/aeat/modelos/490`.
- [ ] `W03.P06.S20` - [M | sonnet-high] Migrate modelo 714. Every one of its cross-edition differences was a single reissued orden reference, so the delta should be near-empty. A large delta here means the restatement lifting is wrong. Proof: the pilot's three checks, plus a delta small enough to read.; `src/cadrumo/_data/registry/aeat/modelos/714`.
- [ ] `W03.P06.S21` - [M | sonnet-high] Migrate modelo 322. It carries both authoring lanes across its editions, so it is the case that proves the delta is independent of how a layout was authored. Proof: the pilot's three checks, on both lanes.; `src/cadrumo/_data/registry/aeat/modelos/322`.
- [ ] `W03.P06.S22` - [L | opus-medium] Migrate modelo 200 — and NOT before the export lane's binding repair (their S76) has closed. The modelo's shipped layout binds 96 of its 137 casilla-bound export fields to the right printed number on the wrong sheet, because its box numbers are unique per pagina and not per modelo. Those split 33 and 63: in 33 the correct-sheet casilla is already declared and the field can be rebound; in 63 the correct-sheet casilla is not declared at all and must be authored before anything can point at it. Neither half is mechanical, since the wrong bindings copied the wrong box's legal references along with its identifier, so every rebinding needs its authority chosen by a person. The repair republishes, which writes export references into the casilla files this step migrates; migrating first would carry the wrong bindings forward into a delta, and migrating DURING it would race another session's edits. So this step waits for S76, then re-measures 200 against the post-repair tree before migrating, because the edition-restatement figures were taken on the pre-repair one. Its lineage is also not what this step originally assumed: 276 rows chain to nothing, of which 243 are proven new boxes and 33 are a declaration gap in the predecessor edition, and it carries no declared lineage on either edition. Proof: the pilot's three checks for 200, run after S76 closes, on a baseline taken after it.; `src/cadrumo/_data/registry/aeat/modelos/200`.
- [ ] `W03.P06.S23` - [M | sonnet-high] Migrate modelo 390. It has a stub first edition and a dictionary-format layout, and its export trees are under concurrent change; re-read before starting. Proof: the pilot's three checks, for 390.; `src/cadrumo/_data/registry/aeat/modelos/390`.
- [ ] `W03.P06.S44` - [S | opus-medium] Handle the six modelos whose first edition is a stub of one or two rows before the real edition arrives. For these the delta is the entire successor edition, so the migration yields no relief AND the minimality screen reports trivially clean — a false success that reads exactly like a well-migrated modelo. Mark them so the screen distinguishes no-relief-by-shape from migrated-and-minimal, and decide whether migrating them is worth doing at all. Proof: a stub-first modelo is reported as such rather than as clean.; `src/cadrumo/_data/registry/aeat/modelos`.

### Phase `W03.P07` - Divergent modelos

The two modelos whose differences are real: legal change in one, renumbering under stable identifiers in the other.

- [x] `W03.P07.S24` - [M | opus-medium] Add the legal-reference period-correctness gate: a casilla's citations must resolve to the dated reference rows governing its own edition window. This refuses the residual authoring drift and must land before modelo 100 migrates, or its delta will show drift as though it were law. Proof: the known drifting rows are refused by name and the rest of the corpus passes.; `src/cadrumo/domain/calculations/registry`.
- [ ] `W03.P07.S25` - [L | opus-medium] Migrate modelo 100. Three quarters of its citation changes are genuine legal change rather than restatement, so its delta is legitimately large and must not be compressed to look small. It also holds four fifths of all casilla files. Proof: the pilot's three checks, and a delta whose size is explained by the legal gate's classification.; `src/cadrumo/_data/registry/aeat/modelos/100`.
- [ ] `W03.P07.S26` - [XL | opus-medium] Migrate modelo 309, which renumbers boxes while keeping identifiers stable. Its lineage adjudication must be complete first, and its delta is genuinely large. If this modelo cannot be migrated the decision still stands for the rest. Proof: the pilot's three checks, and every renumbered box traceable to its adjudicated chain.; `src/cadrumo/_data/registry/aeat/modelos/309`.
- [ ] `W03.P07.S39` - [S | sonnet-high] Modelo 151 is RE-SEQUENCED late and small, not into the divergent phase. Re-measurement with a usable key took it from 620 unchainable to 134, of which 123 are genuinely new rows needing only a no-predecessor value. It is now fifth by volume and its residue is four contested rows, a record-correspondence table to confirm, three retired summary boxes to re-examine, and a glance at six weak matches. Note that the automated key wrongly chains two of the four contested rows, because it matches on label where the declared widths say the opposite — those must be read on width. Proof: the residue resolved, and the two width-contradicted rows refused rather than chained.; `src/cadrumo/_data/registry/aeat/modelos/151`.
- [ ] `W03.P07.S58` - [M | opus-medium] Adjudicate the four contested rows and three retired summary boxes that mechanical chaining cannot settle for the posted-workers modelo. The contested rows transpose municipality and province against their own declared widths, so label order and byte width disagree and only the two ordenes' campo tables settle it — on width, not label. Separately, three summary boxes appear to retire with no successor, one of them a result box: a result box that vanishes is more likely relocated than deleted, and that deserves a second look before it is recorded as a retirement. Proof: each of the seven resolved against the official campo tables or explicitly escalated.; `src/cadrumo/_data/registry/aeat/modelos/151`.
- [ ] `W03.P07.S60` - [XL | opus-medium] Modelo 100 IS the lineage phase and must be treated as its own campaign, not one modelo among four. It carries 993 of the 2,509 unchainable rows and 94% of all refused chains, and it has no oracle of any kind — no export surface, no wire record, no byte spans, no dedicated printed-number field, and a semantic role that labels a grid column rather than a box. Nothing here may be seeded mechanically. Its 250 refusals are not renamings either: 201 are disjoint role changes, which is real box reassignment under stable identifiers at scale. This needs the official record designs read edition by edition, and it may not be completable in one pass — report back rather than improvise. Proof: every row chained with cited evidence or declared new; no chain written on identifier agreement alone.; `src/cadrumo/_data/registry/aeat/modelos/100`.

### Phase `W03.P08` - Remainder

Every modelo not named above, in file-count order, plus the one whose classification is unknown.

- [ ] `W03.P08.S27` - [L | sonnet-high] Migrate the remaining multi-edition modelos, sorted by SUCCESSOR ROW COUNT rather than file count — file count misplaces a modelo with 1,987 rows in 48 files behind modelos of four rows. The population is 24 modelos, not 49: twenty-five of the fifty-eight have a single edition and are out of scope for delta authoring entirely, though they are still covered by the corpus-wide restatement lifting. Stop and escalate any modelo whose delta exceeds its measured difference. Proof: the standard checks per modelo, and one table of deltas against measured differences.; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W03.P08.S28` - [L | sonnet-high] Migrate the remaining modelos in file-count order, smallest first, batching those whose similarity is above the high-similarity threshold. Stop and escalate any modelo whose delta exceeds its measured difference. Proof: the pilot's three checks per modelo, and a single table of deltas against measured differences.; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W03.P08.S38` - [M | opus-medium] Author explicit dispositions for the four modelos that must not be delta-authored, each with its reason recorded in data rather than in a plan: the modelo whose sparse successor withholds by design, the modelo whose three editions are parallel scheme variants with no definable predecessor, the modelo whose six editions hold twelve rows in total and would save nothing, and the modelo already carrying an authored prose refusal that should be lifted to data. Proof: each is marked remains-full-copy and the minimality screen reports them as such rather than as unmigrated.; `src/cadrumo/_data/registry/aeat/modelos`.
- [ ] `W03.P08.S59` - [S | sonnet-high] Report the identifier truncation as a generator defect in its own right. One modelo's identifiers are cut by two different length caps under two different rules, and the older rule elides from the middle so the identifier is not even a prefix of the label it came from and cannot be reconstructed from it. A sweep of all 58 modelos found no other cap signature, so this is confined rather than systemic. It does not block chaining, because the official label sits in the declaration comment beside every affected row — which is precisely why it is worth reporting: the corpus retained what the generator destroyed, and only by accident.; `dev/registry/pipeline`.

## Wave `W04` - Closeout

Restate the screens that measured what is now stated, give the materialised view a reader, and decide what moves onto the per-push path.

### Phase `W04.P09` - Screens and tooling

Restate the screens that inferred what is now stated, retire the two that become automatic, and give the materialised edition a reader.

- [ ] `W04.P09.S29` - [M | opus-medium] Restate the six screens that measured cross-edition state by inference so they read the stated chain instead. Proof: each reports the same findings as before the migration, or an explained difference.; `dev/registry/analysis`.
- [ ] `W04.P09.S30` - [S | opus-medium] Retire the two screens whose question the stated lineage now answers directly, rather than leaving them measuring what the data asserts. Proof: their invariants are covered by the lineage gates.; `dev/registry/analysis`.
- [ ] `W04.P09.S32` - [M | opus-medium] Promote the delta-minimality screen from reporting to gating, now that every modelo is migrated and it reports clean. Proof: a planted restated row is refused.; `dev/registry/analysis`.
- [x] `W04.P09.S53` - [S | opus-medium] Rule on what a governance review stamp covers once editions inherit. The stamp writes declared scalars into the declaring file and is therefore still literally true after migration — but a reviewer signs off on a delta while the compiled edition carries inherited rows the reviewer never saw, so the stamp's SCOPE shrinks silently while its wording does not. Either the stamp states what it covers, or review is defined over the materialised edition. Silence here converts an honest attestation into a misleading one without anyone changing it. The same shape has already been confirmed once on a neighbouring gate: the type-column gate reads derivation records out of a generation manifest, so a hand-authored revision's 1,220 shipped fields are not explained, not pinned and not failing — they are invisible, and the gate covers 32 of 94 shipped revisions while reading as clean. Delta authoring produces stated rather than generated editions, so any gate keyed on manifest presence will read a migrated edition as absent rather than as unchecked. Rule on that too, or migration silently widens the blind spot. Proof: a migrated edition is distinguishable from an unreviewed one by what the stamp says, not by what a reader infers.; `dev/registry/conformance/_stamp.py`.

### Phase `W04.P10` - Promotion

Decide what moves onto the per-push path, under the standing time budget.

- [ ] `W04.P10.S33` - [S | opus-medium] Measure the runtime of the gates this campaign added and propose which belong on the per-push path under the standing time budget. This is a decision for the operator, not an engineering step; the output is the measurement and a recommendation, not a workflow change.; `.github/workflows`.

## Parallelization

The waves are serial. Within them, most of the work is not.

**`W01` runs as two independent tracks.** The harness phase (`P01`) and the lineage phase (`P02`)
share no files and can be briefed to two agents at once. Inside `P01`, the baseline step must
finish before the classification step; the screen step is independent of both. Inside `P02` the
steps are strictly serial — each consumes the previous one's output.

**`W02` is mostly serial**, because each step changes the contract the next one builds on. The
exception is the identifier rename (`S15`), which touches only declaration data and can run
concurrently with the loader work, provided it lands before the reference-resolution step.

**`W03` is where parallelism pays.** The pilot and its hardening step are strictly serial and
strictly first. After that, the five high-similarity modelos in `P06` are independent of one
another and can be briefed simultaneously to as many agents as you want to run — they share the
migration script and touch disjoint directories. The two divergent modelos in `P07` are
independent of each other but each needs its own reasoning, so brief them separately rather than
batching. The remainder phase batches by design.

One coordination constraint: modelo 390's export trees are under concurrent change by another
session. Its migration step should not be briefed while that work is open.

**`W04` is independent of `W03`'s tail.** The screen restatement can begin as soon as the pilot
proves the stated chain is readable; it does not need every modelo migrated. The promotion step
is last and is a decision rather than an implementation.

### Concurrency hazards

Steps that write to the same declaration directory must not run concurrently, and the per-modelo
steps are scoped precisely so that they do not. Steps that add a gate must not run concurrently
with steps that migrate a modelo, because a gate landing mid-migration produces a failure that is
ambiguous between the two. When in doubt, land gates between modelos rather than during one.

## Verification

Proof is per step and proportionate. This campaign does not want a validation suite around every
edit; it wants a small number of checks that cannot pass if the change is wrong.

### The checks that carry a migration

Every per-modelo step proves these, and nothing more:

1. **Round-trip equality** — the materialised edition equals its pre-migration materialisation,
   compared element-wise over the whole edition. Not as a set, not through an identifier-keyed
   map, not with either side sorted: those are the lossy equalities that would pass the exact
   defect the gate exists to catch. Row order is asserted separately so an ordering failure
   reports distinctly from a content failure.
2. **Export bytes unchanged** — **where the modelo has an export surface at all.** Eleven modelos
   have none on any edition, and several change lane mid-chain, so a step must record this proof
   as not-applicable rather than satisfied where there are no bytes to compare. Reporting three
   checks green having proved two is the failure this clause exists to prevent.
3. **Delta minimality** — no stated row identical to the row it would inherit.

Compare against the shipped bytes rather than regenerated output. Note that the earlier rationale
for this — that most generated trees were pinned as non-reproducible — is no longer true: a
concurrent republish retired most of those pins and the majority now reproduce. The reason to
compare against shipped bytes is simply that shipped bytes are what a filer receives.

### Green means the count matches too

A suite is green only when its collected count matches the **pinned baseline** recorded in the
first step, not when it matches the previous run. A deletion and a green run that happen together
will pass a run-over-run comparison while the suite silently shrinks — this has already happened
once in this worktree, thirty-four tests lost and two green runs reported before anyone compared
counts. The anchor must sit outside the run.

**The count is necessary and not sufficient, and the gap is exactly where this campaign works.**
Removing an anti-vacuity guard from *inside* a surviving test leaves the collected count
unchanged and the suite green, while the test now proves nothing on an empty result set. Two
further files feed several gates through plain loops rather than parametrize, so a deletion there
removes cases without moving the count either. A count check catches a suite that shrank; it is
blind to a suite that hollowed out.

The check with teeth for that class is the detector rule applied to every replacement: **a
planted-defect fixture must fail when the defect is removed from it.** A guard converted to a
fixture that still passes with nothing planted has not been converted, it has been deleted with
extra steps.

Before editing any test file, check it for parametrize decorators and module-scoped fixtures.
Several of the files this campaign touches carry them, and removing one assertion can remove many
cases.

### Gates this campaign adds, each with teeth

Each is proved by a planted defect on an isolated fixture, never by asserting something about the
live corpus:

- predecessor forest — a successor omitting its predecessor is refused as a second root;
- withholding refusal — a predecessor declared on a lower-grade successor is refused;
- lineage totality — a successor row with neither lineage nor a new declaration is refused;
- precedence — a stated row superseding by lineage takes the inherited position; an identifier
  collision across different lineage is refused naming both;
- cache teeth — editing a delta file invalidates; a materialisation difference over identical
  files does not;
- derived export references — an authored value is refused;
- reference resolution — a dangling formula or binding reference is refused;
- legal-reference period correctness — a citation outside its edition's window is refused;
- delta minimality — a planted restated row is refused, once promoted from reporting to gating.

### What not to build

No test asserts a count of findings in the live corpus. That is the ratchet this campaign's first
phase removes, and reintroducing it anywhere is a regression regardless of how useful the number
looks. This does **not** extend to the anti-vacuity floors, which assert a gate examined a
non-empty population rather than that a defect persists — those are a separate decision.

No test regenerates a tree to compare against. No per-modelo test file: the checks are one
parameterised gate over whichever modelos have been migrated, and the round-trip check is retired
once the last modelo lands.

### Baseline

**The baseline is red, and it was captured before any change.** Measured against commit
`295e7b81`:

| Gate | Exit | Result |
| --- | --- | --- |
| registry verify + parity audit | 0 | 58 modelos, zero parity failures |
| per-push dev lane | 1 | 1199 collected; 24 failed, 1170 passed, 5 errors |
| offline closure | 0 | 128 revisions, 57 satisfied, 71 refused, release not eligible |
| dispatch-only dev tooling | 1 | 3696 collected; 96 failed, 3579 passed, 48 errors |

**There is no green to return to, so no step may claim it.** Every proof in this campaign is *no
new failure against these numbers*, never *the suite is green*. A step reporting green has either
not run the lane or has misread it.

The failures are not ours. The dev-lane twenty-four sit in continuous-integration, documentation,
packaging and release tests; the five errors are fixture setup in a benchmark. None is caused by
this campaign and none is this campaign's to fix — but they must not be inherited silently either,
so a step that finds a *different* failure count has found something and must say so.

**One count does not reconcile and is therefore not an anchor.** The dispatch-only lane reports
96 + 3579 + 48 = 3723 against 3696 collected, twenty-seven unexplained. Recorded as measured
rather than smoothed. Do not use that lane's collected count as a pinned anchor until it
reconciles. The narrower `dev/registry/tests` count of 1325 is a different scope and remains
usable.

**The baseline is soft, and honesty requires saying so.** The commit held steady across the run,
but the working tree moved from 19 to 23 modified files during the fifty minutes the gates took —
and the files that changed include modelo-applicability, application-modelo and generator-pipeline
sources, squarely inside this campaign's blast radius. So three of the four gates measured a
moving tree. The numbers are real; they are not all attributable to one state. Re-baseline once
the worktree settles, and re-measure rather than trust these figures for any step that turns on a
small delta in them.
