---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8d79c8aab20ab13268e0116b950296062d9a65b4a8c7c2a51f20586f234427e6'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-11-user-docs-search-consolidation-relevance-boost-band-containment-adr]]"
  - "[[2026-08-07-user-docs-search-consolidation-ranking-measurement-audit]]"
---

# `user-docs-search-consolidation` audit: `campaign close honesty review after the Rung-2 retirement ruling`

## Scope

The mandated fresh-context honesty review against the closure summary, taken after the operator's Rung-2 ruling landed and its plan consequences were executed. Read as if inheriting the campaign: what does the plan now claim, and does the tree support it?

The review covers the plan's 39 rows and their exec records, the amended consolidation ADR, the new band-containment ADR, the ranking-measurement audit's dispositions, and a full run of the docs and search gate set captured to disk.

## Findings

### CLOSE-001 | low | The retired rows state their retirement rather than wearing a delivered checkbox

The risk on any ruling-driven close is that retired scope and delivered scope wear the same mark. It was checked directly.

P02.S04 through P02.S07 are checked, and each row's action text now names the retirement and the ruling behind it rather than the delivery it once promised. A reader scanning the plan sees "retire the matrix compiler row", not "build the matrix compiler". Each exec record carries a dated retirement section stating what was not produced: no matrix was committed, no cosine tier composes into the ladder, no provenance stamp is gated, and no post-retirement baseline exists.

The standing recall statement survives this correctly. The `0.1875` pre-Rung-2 held-out miss rate is recorded as final rather than as a baseline awaiting improvement, which is the sentence a future reader is most likely to misread.

### CLOSE-002 | low | The two closed-narrower rows name what they dropped

P02.S31 and P02.S32 are checked on partial delivery, which is the second way a close can quietly overstate itself.

Both records name the retired half explicitly. S31 delivered the lexical browser capture across all 32 held-out queries and the result-id join fix that capture exposed, and its composed-ladder reconciliation against the semantic evaluator is retired with the tier. S32 delivered the versioned query/alias authority, now carrying two ratified entries and consumed by the live sweep, and its Rung-2 provenance binding, recompilation and remeasurement are retired.

S32's record previously stated the authority ships with zero entries. That statement is superseded by the tree and the record says so rather than being left to contradict it.

### CLOSE-003 | low | The scope-narrowing note carries what the standing goal still asks for

A campaign may not narrow its own completion criterion silently. ADR Update 12 states the exclusion beside the delivery: what the standing goal still asks for and this record excludes is open-vocabulary semantic recall for prose queries; what it delivers is the lexical ladder, the five record kinds, the exact structured route, and the recorded baseline. The gap is stated, not closed.

The multilingual authoring programme is recorded as a formally deferred carry-forward with its precondition order, so a future record reviving a semantic tier does not have to re-derive the evidence.

### CLOSE-004 | medium | Four rows remain open, each with a named owner and no green claim

The plan closes at 35 of 39 rows. The four open rows are open on purpose and none is presented as done.

P04.S12 and P04.S13 are deferred by operator decision: the AWS session is expired, re-authentication is an operator action, and the `es`, `ca` and `hu` roots return HTTP 404 today. That 404 evidence is preserved rather than explained away. No live claim is made anywhere in the closure.

P03.S08 is blocked on both halves for two separately owned reasons, each recorded. Its deployed half shares the deployment deferral; its built-site half is blocked by CLOSE-005.

P06.S27 is open because its gate cannot be re-run at HEAD, also per CLOSE-005. The decision it carries has landed and the source retains fail-closed resolution; the record deliberately does not close the row on the strength of a stale green run.

### CLOSE-005 | high | A peer campaign's null Spanish labels block this campaign's verification, and the owner is named

This is the dominant blocker and it is not this campaign's to fix.

889 Spanish casilla labels are declared with null values. Every one is M303, across five revisions, landed by the active M303 registry buildout on 2026-08-10 and 2026-08-11 -- after this campaign's P06 gates closed on 2026-08-06. Spanish is the mandatory source locale, so the casilla projection's hard refusal is correct behaviour. It must not be softened into a skip: the coverage census already models locale coverage as authored non-Spanish labels precisely because Spanish is assumed present, so a skip would hide a rule violation inside a coverage number.

The blast radius is the whole authoritative record projection, and through it 132 translation refusals across the terminology and docs-build gates, plus the relevance re-sweep.

This is a third failure shape for the recurring defect the ranking audit logged as RANK-007. That audit recorded 39 self-referencing scaffold placeholders; at HEAD there are none, and the blocking shape is a declared key with a null value, which the scaffold drift check reports as clean while the resolver correctly refuses it. The recurrence is therefore not a regression of the old shape but a new one that the existing drift gate cannot see -- worth stating, because the obvious remediation of re-running scaffold does not detect it.

### CLOSE-006 | medium | One of this campaign's own gates is red, and the sanctioned remedy is blocked

Honesty requires separating the peer blocker from this campaign's own open defect.

The target-vocabulary gate fails on a single row: the relevance mapping still keys `prorrata:aranyositas`, the corrupt Hungarian string corrected in the Handbook to `arányosítás` under RANK-006. The correct remediation is the re-sweep that audit named, and the re-sweep needs the authoritative record projection, which CLOSE-005 blocks.

The row was deliberately not hand-edited. Renaming its key would attach one query's score-derived drop statistics to a different query, fabricating provenance; deleting it would leave the corrected term with no mapping. Neither is better than an accurately-reported red gate.

### CLOSE-007 | low | The full-tree docs gate is red for reasons this campaign does not own, triaged rather than absorbed

A red repository-wide gate needs owner triage before any completeness claim. The captured run reports 259 passed, 34 failed and 48 errors.

Every failure outside this campaign's surface was attributed rather than patched: 23 modules without API stubs, all `_m303_*` plus a profile sync module and an IVA deduction schema, from peer campaigns that have not re-run the stub scaffold; a CLI reference conformance failure from CLI surface drift; an em-dash ratchet failure in an environment-overrides reference page; and six localization coverage failures reflecting the roughly 46 percent prose translation state the ranking audit already recorded as unowned.

None was patched. Editing them would be opportunistic work on active peer campaigns.

### CLOSE-008 | low | This campaign's own surface is green, and its gates were proven to bite

The converse claim, that the campaign's own work is sound, was tested rather than asserted.

The band-containment gate passes six tests, the ladder gate five, the alias-authority gate twelve, and the Pagefind injection gate seven. Ruff and the formatter pass; basedpyright reports 0 errors, 0 warnings and 0 notes on the changed modules.

Both new gates were proven to bite by restoring the original defect in memory from outside the repository, mutating no tracked file. Re-aliasing the legal class onto the user-documentation band fails the ladder assertions. Restoring the maximum fails band containment naming Ley 58/2003 art. 120 at 0.982968 outside its `[0.75, 0.8]` band and reaching the casilla class. The rejected clamp-to-base alternative fails the strict within-band ordering assertion, which is the inertness that ruled it out -- so the gate discriminates between the fix and the plausible wrong fix, not merely between fix and no fix.

The containment gate also carries a live-subject anchor: it first asserts the committed corpus contains boosts that would escape, so a future corpus with nothing to contain cannot let it pass vacuously. 55 of 90 boosted records carried a raw weight at or above their band ceiling.

### CLOSE-009 | low | A superseded rationale was corrected rather than left standing

The alias-authority module argued in its docstring that its schema id must be kept because renaming it would invalidate the file it names. That reasoning held while the tier was live. Nothing external pins the token: the file is committed in-repo, the loader pins it through a literal, and the browser validator that once checked it was deleted. The docstring is corrected rather than left asserting a rationale the ruling superseded, which is the failure mode of prose describing an old state as current.

## Recommendations

- Do not declare the campaign structurally complete. It closes at 35 of 39 rows with four open, each carrying a named owner and a recorded carry-forward.
- Treat CLOSE-005 as the gating dependency. This campaign's remaining verification unblocks when the M303 Spanish casilla labels carry real values; nothing here should be re-attempted before that.
- Raise the null-valued locale leaf with the M303 campaign as a locale-contract violation, and note that the existing scaffold drift check does not detect this shape, so the obvious remediation will report clean.
- Re-run the built-site multilingual recall gate, the Diseño fail-closed gate and the relevance re-sweep once CLOSE-005 clears, in that order, and close P03.S08, P06.S27 and CLOSE-006 on their results.
- Re-authenticate and publish to close P04.S12 and P04.S13; preserve the current 404 evidence until real live checks replace it.
- Do not soften the casilla projection's refusal on a missing source-locale label. It is the only thing currently making the violation visible.

## 2026-08-12 fourth revision: the publish is no longer blocked by a defect, it is blocked by churn

Every named blocker from the previous revisions is now cleared, and the publish still cannot complete. The reason is structural rather than a fault, and it is the finding worth carrying forward.

**Cleared this session.** The credential was renewed. The peer merge was resolved. The strict build's translated roots were fixed. The calculate path was repaired: six advisory remedies embedded literal command prose in notice context, which the notice validator refuses, so `modelo work calculate` aborted with an internal fault for any filer whose calculation raised one of them -- an ordinary IRPF filer with children or with retenciones could not calculate at all. Three waves of newly-required profile facts were absorbed, the documented profile-create commands were given the flag the CLI had begun demanding, and Modelo 303's new filing-evidence precondition was satisfied by generating the document per run rather than committing a snapshot-bearing fixture that any registry change would invalidate.

**The remaining obstacle is arithmetic.** A full golden refresh takes about thirty minutes and a publish about forty. The tree took 33 commits in the ninety minutes spanning the last attempt, nine of them touching the registry, the domain or the entrypoints. A refresh that completed with zero problems was, forty minutes later, stale across seven pages -- the publish died on Modelo 720 binding-coverage diagnostics that did not exist when those goldens were taken.

So the cli-sequence gate cannot converge: it compares committed goldens against live execution, and the surface it records changes faster than one refresh-and-publish cycle runs. This is not an argument for weakening the gate. The gate is why a withdrawn export and a broken calculate path were caught before publication rather than after.

**Two shapes would fix it, and both belong to the deploy surface rather than this campaign.** Publish from a pinned revision rather than the live worktree, so the build reads one immutable state; the tree is 22 GB, so this wants a git-level pin rather than a copy. Or take a coordinated quiet window, which is what the shared-tree conventions already use for rule syncs.

**One editorial change made here, flagged for the docs owner.** Modelo 303's fichero-BOE layout is withdrawn by a recorded registry decision -- `remove_from_filing_grade`, because the official record design carries producer fields with no canonical typed producer authority and a partial layout would permit silent under-declaration. Two filing-spine sequences documented that export as a working step. They now document the refusal and its reason rather than teaching a dead end, because a filer meeting that refusal needs to know why. Someone owning the page should confirm the wording.

## 2026-08-12 third revision: the plan's own Verification list, checked item by item

Checkbox counts are not completeness. This pass tested the plan's Verification section directly, because that is what the campaign actually promised.

**Proven at HEAD.** The per-root deployment parity gate passes 26 tests, covering concept and casilla recall on each of the four language roots through the real browser path. The target-resolvability sweep passes, so the dead-target count at HEAD is zero, which is the numeric claim the legal record kind's row makes. The wheel-content claim holds through my own rename: 383 packaging tests pass, and no packaging module references either the old or the new terminology data path, so moving that file off the retired tier name cost the distribution nothing. The fresh-context honesty review exists and is this document.

**Not satisfied, deferred by operator decision.** Every live check. The roots were re-probed this session and the default root answers 200 while all four language roots and the casilla page answer 404.

**Not satisfied, one row, judged.** The relevance vocabulary gate fails on `prorrata:aranyositas` alone. Reasoning recorded in the revision above; it belongs with a re-measurement.

**Not satisfied, peer-owned.** Nine docs-gate failures, each attributed: 23 modules without API stubs and the full-scope nitpicky build that fails downstream of them, an em-dash ratchet on a file last touched by a WIP commit, and six localization coverage failures reflecting the long-recorded translation gap.

**Two packaging failures, also peer-owned, and one of them is instructive.** The distribution-identity digest has drifted because CLI verbs landed after it was last pinned in early August. It cannot be re-pinned now and this campaign must not try: the gate's own instruction is to re-pin only from a tree whose description sources are clean against HEAD, and those sources currently carry live peer WIP in the ledger import CLI and in all four locale catalogues. Re-pinning here would bake another agent's uncommitted work into a committed gate, which is the exact failure the instruction names. The second failure is an undeclared `pydantic_core` import in a peer LLM test.

**One environmental fact worth recording.** The RAG index reports new job identifiers on every check, so it is continuously re-indexing under the tree's ongoing commit traffic. Any procedure that waits for a settled index may wait indefinitely in a shared worktree this active. That is a constraint on the re-sweep, not a transient to sit out.

## 2026-08-12 second revision: a stale-call-site pattern, and why the re-sweep is not being forced

**CLOSE-006 stays open, and the reason is now a judgement rather than a blocker.** The re-sweep is mechanically possible: the projection works and a targeted sweep produces the corrected Hungarian row. Two things argue against forcing it at closeout.

The RAG index is mid-rebuild -- its code and vault generations both report running -- which is why the sweep cannot confirm a reindex and honestly stamps its output as swept against an unconfirmed index. That is transient.

The durable objection is proportionality. A full re-sweep regenerates the whole committed mapping, which is the input the 0.1875 held-out miss rate was measured from and which ADR Update 12 records as the project's final honest recall statement. Regenerating it would move a ratified figure and demand a fresh measurement and an amendment -- to retire one dead row for one concept in a corpus of 112 queries and 8,507 records. A targeted sweep avoids that but mixes one concept's rows, swept against an unconfirmed index, into a corpus-wide artifact carrying a single provenance note.

So the row is left as the recorded carry-forward it already was, now with its cost stated: it belongs with a re-measurement, not with a close.

**A pattern worth more than any of its instances: three stale call sites in the docs gates, all in shared helpers whose signatures moved.** The deployment parity gate never passed the sequence-check argument its environment helper had gained; the same file treated the source language as a localized root because the deploy language set already contains it; and the CLI reference conformance gate never passed the language argument its param-table helper had gained, dying on a TypeError before asserting anything.

Each is trivial alone. Together they say something: `dev/docs` production helpers gained parameters and the `dev/docs/tests` call sites were not swept with them. Every one was invisible while the gates were red for unrelated reasons, which is the real lesson -- a blocker that hides a gate hides that gate's own rot, and clearing the blocker is what exposes it. Expect more of this class as the remaining peer-owned failures clear.

## 2026-08-12 revision: CLOSE-005 cleared, and a correction to this audit

**CLOSE-005's central factual claim was wrong, and the error changed what looked possible.** This audit stated the label text "has never existed in the tree". It does. It is absent from the registry fragments -- correctly, since casilla labels live only in the locale catalogues -- but the bundled official AEAT diseño de registro for `303/2026-y-siguientes`, the exact source those fragments cite, carries it. All 85 blocking casillas resolve there to exactly one field-definition row each. What this audit recorded as unreachable grounded authoring was grounded extraction from a source already in the repository.

The labels are authored and the blocker is cleared. The casilla projection materialises 6,517 records. Across the docs and search gate set the count moved from 34 failures and 48 errors to 16 failures and no errors; the residue is the peer-owned set CLOSE-007 already attributed.

**CLOSE-004 and CLOSE-006 revise as follows.** P06.S27 is CLOSED: its gate re-ran green at HEAD, so the row closes on a fresh run rather than a stale one. P03.S08's built-site half is PROVEN -- 26 passed, concept and casilla recall on each of the four language roots through the real browser path -- and the row stays open only on its deployed-root re-probe, which is the deployment deferral. P04.S12 and P04.S13 are unchanged. The plan stands at 36 of 39.

CLOSE-006 is unchanged: the relevance mapping still keys the corrected Hungarian term by its corrupt spelling. A targeted re-sweep now runs and produces the corrected row, but the service could not confirm a reindex, so the output carries an unconfirmed-index note. Merging one concept's rows swept against an unconfirmed index into a corpus-wide artifact would degrade its provenance for a one-row fix, so it was not merged.

**Three findings this pass added, each worth more than the row that surfaced it.**

First, the recurring locale defect has a fourth shape: a key that is ABSENT rather than null or self-referencing. The módulo 4 to 7 unit-count keys were in this class, and unlike the null shape the scaffold drift check does report it.

Second, and most important: **`scaffold` deleted 17 live Spanish values.** They are referenced through a mapping in the live CLI rather than a literal `tr()` call, so the scanner cannot see them and read them as stale. They were restored and the key set now matches HEAD exactly, but the next scaffold run will delete them again. This is a standing trap for anyone running the sanctioned command, and it is why a scaffold run should be diffed for removals rather than assumed additive.

Third, this campaign's own deployment-parity gate carried three defects behind one root cause -- the deploy language set already carries the source language, so English was driven through the localized-root paths. They were invisible while the projection blocker masked the whole file. A blocker that hides a gate hides that gate's own bugs too.

## CLOSE-005 sharpened: the blocking set is 85 labels, and they are unauthored rather than unpropagated

Added after a second pass specifically aimed at reducing the blocker, because a close that reports a blocker without sizing it hands the next reader a search rather than a task.

**The blocking set is 85 labels, not 889.** The casilla projection reads only the latest revision of each modelo, so only `303/2026-y-siguientes` gates it: 85 of its 214 casilla labels are null. The other 804 nulls sit in superseded M303 revisions and block nothing today. Whoever picks this up needs those 85, and the first blocking id is `107`.

**They are unauthored, not merely unpropagated.** The obvious hypothesis was that the label text exists in the registry fragments and only the catalogue is stale, which would make this a mechanical propagation. It is not. The registry fragment declaring casilla `107` carries id, number, section, data type, semantic role, continuidad id, input kind and both reference lists, and no label text at all -- correctly, because the localization contract puts every casilla label ONLY in the four locale catalogues. The text has never existed anywhere in the tree.

So closing this needs the official AEAT Modelo 303 2026 form as the grounding source, then the Catalan and Hungarian values the parity gate and the honesty ratchet both require. That is grounded tax-authoring work owned by the M303 registry buildout. It was deliberately not attempted here: authoring 85 regulated Spanish labels without the official form would be inventing regulated content, and the untranslated escapes the scaffold offers are refused by shipped gates anyway.

**A narrowed-authority workaround was attempted and rejected.** The resolver takes an injectable authority explicitly so a test can drive a narrowed registry, and the Diseño fail-closed rule's subject is modelo 036, so excluding M303 looked like a legitimate way to re-prove P06.S27 at HEAD. It is not reachable honestly: the authority's modelo index is a private cache that a field-level copy does not rebuild, so narrowing it means reaching into internals, which makes the resulting authority a fake rather than a real one. Recorded so it is not re-attempted.

The surviving observation is still worth acting on later: the module-scoped resolver fixture projects every modelo, so a rule about one modelo is hostage to every other modelo's authoring state. Scoping that fixture to its subject is a real hardening, but it belongs with the gate owner and after the labels land, not as a way to make a red close look green.

## The remaining three rows have one provable dependency, and it is not churn

Added after the publish was attempted again and failed. Earlier passes attributed the failure to tree churn and to a dead `.git/index.lock`. Both were real conditions but neither was the cause, and recording the wrong cause is what made this row look unownable across several attempts.

**The working tree cannot load the registry at all.** `bundled_authority()` raises `RegistryLoadError` at `modelos/130/revisions/2019-y-siguientes/bindings/0002-bindings.toml`: the fragment declares no `[revisions.<id>]` table. The file has been reduced to a comment block describing its own migration. Behind it sits a second defect -- `modelo-130-previous-year-economic-activity-net-income` is declared as both a casilla and a formula -- so removing the stub alone does not restore the load. A third piece, `_validate_previous_filing_year_coverage.py`, is UNTRACKED: a new build-time year-coverage validator that exists only in the working tree.

The three pieces are coherent as a design. The M130 to M100 prior-year carry retires from a `previous_filing` binding into four `cross_model_output` relations, which is what the calculation-aggregation-taxonomy ADR requires of a cross-modelo fold-in, and the new validator's own allowance table documents the retirement in prose. What is wrong is only that the change is landing in halves, which is the failure mode `aeat-architecture-boundaries` names: a relocation lands in one commit or the tree is red between them. It is peer WIP and was not touched.

**Committed HEAD is green.** Verified directly rather than assumed: HEAD's `src` extracted whole to a scratch tree and imported with `PYTHONPATH` ahead of the editable install, `bundled_authority()` returns 73 modelos. An earlier pass in this session claimed main was red; that claim was wrong, and its error is worth recording because it is easy to repeat -- HEAD's registry DATA had been tested against the working tree's CODE, and the code included the untracked validator. Pin both sides or neither.

**Pinning to HEAD does not rescue the publish, and the reason is a contract, not an obstacle.** A pinned snapshot was built -- HEAD whole, with this campaign's three uncommitted deliverable groups layered on (the `docs/_sequences` contracts and goldens, `dev/docs/sequences/_runner.py`, and the four locale catalogues carrying the authored M303 labels). It resolves cleanly and its registry loads. The cli-sequence check against it returns 51 divergences, and their shape is the finding: `result.observations[].casilla_id`, `legal_refs`, `source_refs`, `operand_values`, `result.rows[].label` and `value`, across thousands of rows. The `registry:referential-integrity` error that dominated the working-tree run is gone.

That is the proof. The goldens are a contract recorded against the tree's registry; the only registry that loads is HEAD's; fourteen registry files are dirty between them. Refreshing the goldens to HEAD would resolve the divergence and would be the wrong act -- it would overwrite the contract with a snapshot of a registry state the peers are actively moving off, and land golden churn inside their in-flight migration.

So P03.S08's deployed half, P04.S12 and P04.S13 carry a genuine ordering dependency: the M130 migration lands (or its author reverts their own half), the goldens are refreshed ONCE against the settled tree, and the publish runs against that. The deferral recorded earlier stands, but it is no longer a deferral for lack of a quiet window. It is a deferral for a registry contract that cannot honestly be satisfied from either side while the migration is mid-flight.

Two ordinary blockers remain alongside it and should not be confused with it: the AEAT deploy credentials expire on their own schedule and were expired again at this pass, and `.git/index.lock` has been frozen for over three hours with a dead holder, which blocks committing this campaign's finished work but blocks no build. Neither is on the critical path; the registry contract is.

## The ordering dependency cleared, and the refresh found two product regressions behind it

Added after the M130 migration landed. The registry now loads in the working tree (73 modelos), so the golden refresh this campaign was waiting on could finally run. It went from 94 divergences to 15 across 34 pages. What the remaining failures turned out to be is worth more than the refresh.

**Twelve pages failed for four separate reasons, and only two were this campaign's own.** The `iva-year-2025` seed drove four Modelo 303 calculations without the typed filing-evidence document the CLI now requires, so the fixture generator was extended to the 2025 quarters and the seed carries the argument; and the documented `profile create` invocations had fallen behind a profile schema that gained five required IVA facts. Both were this campaign's surface catching up, both are fixed, both verified green.

**The other two are product regressions, each a hardening gate merged ahead of the surface that can satisfy it.** They are the same failure shape twice in one in-flight campaign, and the cli-sequence goldens surfaced both within hours of the break.

The first: `aeat app modelo export` refuses for every modelo. `_require_export_identity` landed 2026-08-12 and refuses unless `presenter` and `taxpayer_identity` are set; all three production construction sites -- the export CLI, `_quickfile.py` stage 5, and `_modelo_review_package_cli.py` -- leave both at their `None` default, and no CLI option supplies either. For Modelo 130 and 303 the withdrawn-layout refusal fires first and masks it; Modelo 349, which still holds a layout, shows it plainly at exit 5. Its golden expects exit 0 and a 1500-byte file, so this worked when that golden was recorded.

The second is the more serious. **Modelo 303 drops every input-IVA deduction created through the CLI.** `_iva_ledger.py` now refuses any `SOPORTADO` transaction lacking both `deduction_fact_kind` and `deduction_provenance`; nothing under `entrypoints/` sets either field, and the only explicit assignment outside internal aggregation is in a test module. The documented worked example -- income cuota 210, deductible purchase cuota 105 -- moved from casilla 71 = 105.00 to 210.00, with casillas 28, 29 and 45 all falling to zero. The taxpayer overpays by the entire deduction.

The safety apparatus behaved correctly and that is the part to keep: a `source_advisory` warning fires, naming the exact cause. So this is NOT a silent under-declaration. But the advisory is non-blocking, `calculate` still emits a draft carrying zero deductions, and the direction of the error is over-payment -- precisely the direction `no-silent-under-declaration` records as unwatched, producing valid output, no refusal, and no signal to the taxpayer.

**A refresh is not a verification, and this pass proves why.** `refresh` executes frames and rewrites goldens; it does NOT evaluate the `@expect` value assertions authored in the `.seq` contracts. A page can therefore refresh at exit 0 and fail `check` immediately afterwards on the same tree, which is exactly what happened. Anyone reading a clean refresh as a green gate will publish wrong numbers.

That is the live hazard this pass leaves behind: **the refreshed goldens now carry 210.00 and zeroed deduction casillas across the Modelo 303, IVA-lifecycle and filing-spine pages. They are wrong documentation and must not be committed.** They are uncommitted, and the dead index lock prevents any commit, so the exposure is contained -- but the containment is accidental, not designed. Restoring them from HEAD was rejected: those files also carry this campaign's own earlier uncommitted work, so a HEAD restore would destroy real authored content to undo a mechanical refresh.

Two documentation corrections DID land and are sound independent of the above, because they document typed, intentional refusals rather than defects. Fichero-BOE export is withdrawn for modelos 111, 115, 123, 130, 200, 202, 232, 303 and 390 (`decision = "remove_from_filing_grade"`, reasoned as a partial layout permitting silent under-declaration), and nine sequences across eight how-to pages were still teaching readers to run it and asserting exact byte sizes. Those now document the refusal with `work file` as the supported ending, and the quickstart's prose was rewritten to match: enter the calculated values at the portal rather than upload a file the tool cannot produce.

One further defect was fixed at its own seam. Host-conditional rows masked their rendered `detail` sentence but not the `facts` it was rendered from, so `free_memory_bytes` and `free_vram_bytes` stayed pinned in a golden that its own author's next run would red. Host-conditional rows now mask `*_bytes` fact VALUES while keeping the KEYS under exact comparison, so a reader that stops reporting a quantity still fails. Five tests, proven to bite against the pre-fix behaviour through an out-of-repo pytest plugin, so nothing tracked was mutated to run the proof. The global `GOLDEN_MASK_FIELDS` was deliberately left alone -- its docstring names widening it a standing honesty hazard, and this belongs in the sequence-local layer.
