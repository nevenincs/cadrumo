---
tags:
  - '#exec'
  - '#legal-corpus-vintage'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e07c13922af17e903344038f6a495a3e6cd29c6316b0c07eea2dbb30b820a4e4'
step_id: 'S06'
related:
  - "[[2026-08-10-legal-corpus-vintage-plan]]"
---

# Re-run the clause-level divergence measurement over the newly reachable entries and report the split, without proposing a remedy. The disconfirming observation: if the newly measured population's catch rate differs materially from the 3-of-72 already measured, the 104 comparable entries were not representative and the ADR's premise needs re-examining rather than extending

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Enumerate the newly reachable population programmatically from the catalogue
  and the corpus at HEAD, taking no published count as an input.
- Widen the existing screen rather than building a second instrument: separate
  the entries that cite their norm's whole consolidated file from the entries
  whose norm ships no consolidation at all, which were leaving the population
  before it was counted.
- Add the BOE article payload as a second oracle, reduced to the redaction in
  force through the acquirer that already owns that rule and its tie refusal.
- Correct the vintage rule, which read a norm's own enactment year as a declared
  historical vintage.
- Exclude BOE's per-redaction editorial annotation from the comparison.
- Report the split stratified by oracle kind and by identity confirmation, so
  the instrument fix and the newly reachable population can be told apart.
- Prove both mis-selections move real verdicts by rebinding the seams at run
  time from outside the repository, then restore.
- Correct the acquirer's measurably false claim about bilateral tax conventions.

## Outcome

### The population, measured rather than taken

628 to 633 catalogue entries were reported at various points in this campaign;
the live figure is 633, of which 630 cite an HTML corpus file. Those 630 divide
into 305 that cite their norm's whole consolidated document and 325 that cite a
single-unit excerpt. The 325 are the excerpt-backed population; the 305 are
excluded, and the exclusion is now counted and printed rather than performed
silently.

The screened population was 228 before this row. The missing 97 were not a
declared limit: an entry whose cited file has no shorter bundled prefix was
skipped as though it always meant "cites the whole consolidated norm, its own
current text". That is true for 305 of them and false for 97, because an excerpt
whose norm ships no consolidation looks identical at that test. This is the same
silent-drop defect the sibling row removed one step later in the pipeline, and
it was sitting at the population boundary.

Of the 97, **57 are newly reachable** through the acquired article payloads and
40 remain unmeasurable because BOE holds no consolidated record for their
document at all. That 40 is the residue of the acquisition step's refused class,
and it is now a printed verdict rather than an absence.

### Redaction-in-force selection

58 article payloads are bundled across 24 BOE documents, carrying between 1 and
12 redactions each. **All 58 reduced to exactly one redaction in force. Zero
refused on a tie.** Selection was delegated in full to the acquirer's own
assertion, which reads the maximum effective date and refuses rather than picks;
nothing here re-derives it. 23 distinct blocks are consumed by the 57 entries.

The committed sidecars for these payloads were NOT used. They fold every
redaction into a single unit, so an excerpt would have been compared against
repealed and current law at once. Reading the raw payload also excludes the
response envelope's status tokens by construction, which is stronger than
stripping them after the fact.

### The split

Over the 325 screened: 49 no oracle, 0 indeterminate, 0 unresolved, 1
misresolved, 93 matching, 15 vintaged, 18 gate fires, 149 gate green. 275
comparable; of 182 measured divergences the gate catches 18.

Stratified, which is the part that answers the row:

| population | comparable | diverging | gate fires | catch rate |
| --- | --- | --- | --- | --- |
| previously comparable, consolidated-norm oracle | 218 | 129 | 9 | 7.0 per cent |
| ... identity confirmed only | 210 | 123 | 8 | 6.5 per cent |
| newly reachable, article-redaction oracle | 57 | 53 | 9 | 17.0 per cent |
| ... identity confirmed only | 21 | 20 | 0 | 0.0 per cent |
| ... identity unconfirmed | 36 | 33 | 9 | 27.3 per cent |

The previously comparable subset reproduces the sibling row's corrected figures
exactly, entry for entry: 218 screened, 89 matching, 15 vintaged, 9 firing, 105
green. That is the control that the widening did not disturb the existing
measurement, and it is why the two effects can be separated at all.

### Separating the two effects, which is the row's actual question

The row asks whether a materially different catch rate in the newly measured
population means the previously comparable set was unrepresentative. Two things
could move the rate, and conflating them answers the wrong question.

**Effect one, the instrument.** The derivation fix moved the published rate from
3-of-72 to 9-of-129 on the pre-acquisition corpus. That movement is entirely a
statement about the instrument: it recovered 32 entries the old derivation
mis-resolved or dropped, and corrected a denominator. It says nothing about
representativeness, and the corrected 9-of-129 is the only honest baseline to
compare a new population against. Comparing against 3-of-72 would be measuring
the instrument twice.

**Effect two, the new population.** Against that baseline the newly reachable 57
come out at 9 of 53, or 17.0 per cent, roughly two and a half times the
baseline's 7.0 per cent. Taken at face value that is a material difference and
would support the row's disconfirming reading.

**It does not survive stratification, and the stratification is not a choice
made to rescue the premise.** The screen already carries an identity flag that
predates this row: it records whether the excerpt's own structural heading could
be cross-checked against the provision reached. An excerpt carrying a structural
heading is a faithful per-article copy; an excerpt carrying a curated prose title
is a catalogue snippet, ABRIDGED by design. Divergence from full current text is
expected for an abridged snippet and is not evidence of staleness.

The two populations differ sharply on exactly that axis. The previously
comparable set is 210 of 218 identity confirmed. The newly reachable set is 21
of 57. Split on it:

- Newly reachable AND identity confirmed: 21 entries, 20 diverging, **gate
  catches 0**. That is a catch rate of zero against a baseline of 6.5 per cent
  on the comparable identity-confirmed set. Lower, not higher.
- Newly reachable AND identity unconfirmed: 36 entries, 33 diverging, gate
  catches 9, 27.3 per cent. Every one of the nine firing entries is in this
  stratum.

So the headline 17.0 per cent is not a property of the newly reachable law. It
is a property of excerpt SHAPE: the newly reachable population is dominated by
curated multi-article catalogue snippets whose declared phrases quote the
snippet's own framing prose, so the phrase test fires for a reason that has
nothing to do with supersession.

**Verdict on representativeness: the disconfirming observation does not fire.**
On the like-for-like comparison the newly reachable population is not
more-caught than the previously comparable one; it is less-caught, at zero of
twenty. The ADR's premise that the gate rarely notices divergence is
strengthened by this population rather than challenged by it, and the argument
the ADR actually rests on -- that a presence-only grammar cannot express "this
repealed clause must be absent" -- is untouched. The 104 comparable entries were
not shown to be unrepresentative. What moved the published number was the
instrument, twice: once in the sibling row's derivation fix and once here in the
vintage rule and the editorial-note exclusion.

Stated as a limit rather than buried: 36 of the 57 newly reachable entries carry
an identity that could not be cross-checked, so their individual verdicts are
weaker than the rest. That weakness is why the stratified figure, not the pooled
one, is the answer.

### Two measurement defects found and corrected inside this row

**A norm's own year was being read as a declared vintage.** The rule tested the
excerpt stem's trailing segment for a year. Every stem in the old population
ended in a citation token, so it never mattered; the moment the population
widened, 29 bare-norm excerpts were called vintaged. This is the worst available
direction of error: vintaged asserts that divergence from current text is
CORRECT by design, so a wrong one excuses real staleness under an approving
label. A vintage year must follow a citation token; a norm year does not.

**BOE's per-redaction editorial annotation was being counted as legal text.**
223 such annotations ride in the payloads. They are provenance, not clauses, and
an excerpt sliced from the whole-document view carries a differently-worded note
or none, so counting them reports a divergence about the annotation. Excluding
them changed clause counts materially and moved one verdict, which is itself a
finding recorded rather than smoothed: one of the three phrases declared for
ley-19-1991 article 30 is present ONLY in BOE's modification note and never in
article 30's operative text, so that phrase gates on an annotation.

### The 22 disagreeing-anchor rows

Measured under the fixed derivation the count is **30, not 22**, over the 57
entries reached this way, and the two figures are not in conflict: the
acquisition step measured over the 58 acquired rows, this row measures over the
entries that consume them. More useful is the split the acquisition step could
not make. **13 of the 30 name a genuinely DIFFERENT block** -- the three Belgian
convention articles, the United Kingdom article, the Moroccan article whose
BOE block is one lower than its number, the three Netherlands articles at
positional blocks, the Wealth Tax article-4 apartado citation, and four
sub-article citations in the non-resident income tax text. The other 17 are the
same provision spelled two ways. None was repointed: repointing an anchor is
adjudication, and this phase is measurement. The screen prints both lists.

### The mislabelled excerpt carried forward

The single misresolved entry remains ley-31-2022 article 39, reported with both
headings, unchanged and unsmoothed. It is a tax review: the excerpt is titled as
a modification of the corporate income tax law while the consolidated norm's
article 39 governs pension revalorisation. Not resolved here.

### The acquirer's false claim, corrected

The acquisition step measured that the module docstring's assertion that BOE
holds no consolidated text for bilateral tax conventions "at all" is false. That
was independently re-verified here against the bundled corpus rather than taken
on report: of the nine conventions the catalogue cites, eight carry consolidated
article payloads acquired from the consolidated-legislation endpoint -- Belgium,
Germany, France, the United Kingdom, Morocco, the Netherlands, Portugal and the
United States -- and only the Argentina 1992 convention does not. The docstring
now states the measured position, names the eight, and records the reading error
that produced the claim: a bundled excerpt whose permalink points at the
single-document view evidences how that excerpt was acquired, never that BOE
holds no consolidated text. That misreading is what left eight conventions
unmeasurable.

## Notes

**No remedy was proposed and none was applied.** No catalogue entry, corpus_ref,
required_text, effective_from or corpus file was touched, and no
forbidden-text clause was authored. The commit changes measurement code only.

**No second instrument was built.** The existing maintainer screen was widened
in place, its tests extended, and its totals still reconcile by construction --
the summary refuses to print a split that does not add up, and that property was
re-proved under every fault injected below.

**The anti-tautology proof, run from outside the repository.** Three seams were
rebound at run time in one process so nothing tracked was edited. Reading the
OLDEST redaction rather than the one in force moves ten verdicts and turns
ley-19-1991 article 30 into a false "matches" -- a full false clean verdict on a
provision whose scale has been rewritten repeatedly. Reading every redaction at
once, which is the committed sidecar's shape, moves four verdicts and reports
three gates as blind that in fact fire. Forcing the acquirer to refuse every
payload lands all 57 in an explicit indeterminate verdict with the population
unchanged at 325, rather than losing them. All three restored; the baseline
verdicts return identically. The load-bearing half is that the totals reconcile
in every fault state, so a mis-selection shows as a moved verdict and never as a
vanished entry. The oldest-redaction case is additionally pinned as a permanent
corpus-anchored control, and the tie refusal as a unit test over a two-redaction
payload.

**A shared primitive was promoted rather than copied.** Both sides of the
comparison must be rendered by one renderer or the screen measures the renderer
instead of the law. The project's single BOE-markup-to-prose rendering lived as
a private helper of the extractor and is now public on its package facade, its
four call sites rewritten in the same change.

**Full-tree collection is clean**: 25378 tests collected, zero errors. The peer
overview-rendering collection error named at dispatch is no longer present.

**Gate state, triaged.** The screen's own tests, the corpus acquisition tests,
the HTML extractor tests and the corpus sidecar freshness sweep all pass, as do
the legal-catalogue grounding, corpus catalogue companion, corpus round-trip and
required-text-reaches-the-provision gates. Formatting and lint are clean on the
changed modules. Five other failures were triaged and none is this surface:

- The RAG preprocess rule declares extractor version 1.1 while the extractor
  constant reads 1.3. Both inputs to that assertion are byte-identical to HEAD
  -- the constant was not touched here and the rule file is not modified in the
  working tree -- so the mismatch predates this change. Left deliberately: the
  correction invalidates the resident dev index for the whole corpus and would
  force a reindex on every agent currently depending on it, and the surface
  belongs to the documentation-search campaign.
- Three import-hygiene test-debt failures name twelve reaches, every one under
  the shipped package and none under the development tooling. The hygiene
  scanner module itself is uncommitted peer work in this tree.
- The layering dimension reports the import-linter run aborted on stale ignore
  entries naming a persistence module a peer is relocating. Its own message says
  this is a stale configuration rather than a layering violation.
- The unverified-anchor ratchet sits at 90 against an 89 ceiling, the
  pre-existing peer regression the acquisition step already settled with a
  control. This change touches no catalogue entry and no corpus file, so it is
  neutral on it by construction.
- Six repository-wide scanner failures under the core tests name only peer
  files and generated sequence fixtures.

**Code review has not been run on this change** and is outstanding.
