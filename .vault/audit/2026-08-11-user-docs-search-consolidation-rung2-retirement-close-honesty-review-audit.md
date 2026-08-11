---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e7b9e5dd985976c970683be83327a79c374a90442f356ac4517ebc2caf44e617'
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

## CLOSE-005 sharpened: the blocking set is 85 labels, and they are unauthored rather than unpropagated

Added after a second pass specifically aimed at reducing the blocker, because a close that reports a blocker without sizing it hands the next reader a search rather than a task.

**The blocking set is 85 labels, not 889.** The casilla projection reads only the latest revision of each modelo, so only `303/2026-y-siguientes` gates it: 85 of its 214 casilla labels are null. The other 804 nulls sit in superseded M303 revisions and block nothing today. Whoever picks this up needs those 85, and the first blocking id is `107`.

**They are unauthored, not merely unpropagated.** The obvious hypothesis was that the label text exists in the registry fragments and only the catalogue is stale, which would make this a mechanical propagation. It is not. The registry fragment declaring casilla `107` carries id, number, section, data type, semantic role, continuidad id, input kind and both reference lists, and no label text at all -- correctly, because the localization contract puts every casilla label ONLY in the four locale catalogues. The text has never existed anywhere in the tree.

So closing this needs the official AEAT Modelo 303 2026 form as the grounding source, then the Catalan and Hungarian values the parity gate and the honesty ratchet both require. That is grounded tax-authoring work owned by the M303 registry buildout. It was deliberately not attempted here: authoring 85 regulated Spanish labels without the official form would be inventing regulated content, and the untranslated escapes the scaffold offers are refused by shipped gates anyway.

**A narrowed-authority workaround was attempted and rejected.** The resolver takes an injectable authority explicitly so a test can drive a narrowed registry, and the Diseño fail-closed rule's subject is modelo 036, so excluding M303 looked like a legitimate way to re-prove P06.S27 at HEAD. It is not reachable honestly: the authority's modelo index is a private cache that a field-level copy does not rebuild, so narrowing it means reaching into internals, which makes the resulting authority a fake rather than a real one. Recorded so it is not re-attempted.

The surviving observation is still worth acting on later: the module-scoped resolver fixture projects every modelo, so a rule about one modelo is hostage to every other modelo's authoring state. Scoping that fixture to its subject is a real hardening, but it belongs with the gate owner and after the labels land, not as a way to make a red close look green.
