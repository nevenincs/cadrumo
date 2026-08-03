---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f18108b637f49eb6442aac9d39d9da62405fd5b57e6235759d9c25be07745eae'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-plan]]'
  - '[[2026-08-03-canonical-storage-management-closure-criterion-reference]]'
---

# `canonical-storage-management` audit: `canonical storage management honesty review`

## Scope

The fresh-context honesty review `aeat-campaign-close-honesty-review` requires before
closure may be declared. Judged against the closure-criterion reference: **every
production site that produces a file or directory resolves its destination through the
canonical accessor API**, with tests, operator-directed outputs, and bundled read-only
resources excluded.

Everything below was verified against **committed HEAD**, not the working tree. The
working tree currently carries peer WIP that makes the storage suite uncollectable
(`BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME` is present at HEAD and removed in an
uncommitted `_namespace_registry.py` edit), so all measurement ran against a
`git archive HEAD` snapshot in a scratch directory using the repository interpreter.
Gate runs were serial and single-SHA, so neither of the parallelism caveats the closure
reference records applies to any number here.

Method: two independent AST passes over every production module at HEAD (one over
file-producing call sites, one over path-composition expressions), targeted reading,
in-process resolution of the taxonomy against the settings model, a serial run of the
six storage gates, and a smoke of the delivered operator surface.

**Verdict when this review opened: the closure criterion was not met**, four findings
blocking. **Verdict at close: still not met, but for a different reason, and one of the
four is now closed by measurement.** The campaign's enforcement is green; its declared
work is not finished and part of it is still untracked. The closing measurement and the
revised standing of each blocker are in the final section.

## Findings

### two-campaign-gates-red-at-head | critical | Two gates this campaign authored fail at committed HEAD on unenrolled production sites

**Claimed:** the closure record triages a 21-failure full-tree run as 13 parallelism
phantoms, 2 stale, 1 real and routed, 5 under serial verification, and attaches the
caveat that parallel runs manufacture failures.

**Verified:** a serial, single-SHA run of the six storage gates against a HEAD snapshot
gives **157 passed, 2 failed**. `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference`
and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`
both fail. Neither caveat applies: no parallelism, no moving tree.

Both fail for the same cause — one unlanded enrollment change; five production literals naming taxonomy-governed
locations: `entrypoints/cli/_app_live.py` carries `Path('var/cadrumo/live/iva-compensation-history')`,
`Path('var/cadrumo/live/iva-read-evidence')` and `Path('var/cadrumo/filed-declarations')`
twice; `entrypoints/cli/_overview_evidence.py` carries the last of these once. Those
same three categories then report their `consumer_module` claims unbacked, because the
claimed consumer reaches the location by literal instead of by member.

**Gap:** these are owner-surface failures under `full-tree-gate-must-distinguish-owner`
— the campaign's own gates, failing on the campaign's own subject matter — not
unrelated peer churn. A peer lane holds the fix uncommitted (the literals are gone from
both working copies), so this is in-flight rather than unowned; but at committed HEAD
the campaign's enforcement is red, and no closure record states that. This finding
resolves itself the moment that lane commits, and should be re-measured then rather
than treated as durable.

**Re-measured twice more, and the second re-measurement corrects the first — including
an error of my own in exactly the class this review exists to catch.**

The middle measurement in this section previously read "3 unbacked consumer claims became
13" and framed the campaign's enforcement as moving backwards. **That framing was wrong,
and the SHA it was attributed to was wrong.** The 13 was a real observation, but it was
not taken at the commit I labelled it with: the archive command ran `git archive HEAD`
and then printed `git log -1` *afterwards*, and in a worktree taking commits every few
minutes a commit landed in between. The measurement was of the parent commit; the label
came from the child. Confirmed after the fact by content rather than by timestamp: the
commit I named carries ten references to the extracted sibling module and the one before
it carries zero, so a 13-unbacked reading was only possible at the earlier one.

The lesson is worth more than the correction. `git archive HEAD` followed by a separate
`git rev-parse` is a race, and it produces the same defect as reading a dirty working
tree — a real number attached to a state it did not come from. The fix is to resolve the
SHA into a variable *first* and archive that literal object. Every measurement in this
section after this point does so.

**Measured at explicitly pinned `9fdca8d083`, serial, single SHA: 2 failed, 13 passed.**

- Liveness gate: **3** unbacked claims — `filed-declarations` claiming
  `entrypoints/cli/_overview_evidence.py`, and `iva-compensation-history` and
  `iva-read-evidence` both claiming `entrypoints/cli/_app_live.py`.
- Settings-lifecycle gate: the same **5** literals in those same two modules.

**The two gates have one shared cause, which is the finding that matters.** Both modules
still name `var/cadrumo/live/iva-*` and `var/cadrumo/filed-declarations` as literals at
HEAD. The lifecycle gate catches the literals directly; the liveness gate catches the
three members whose declared consumer does not reference their category or settings field
— because that consumer reaches the location by literal instead. One enrollment change
closes both.

So the honest arc of the liveness gate is 3 → 13 → 3: the path-hierarchy extraction
briefly orphaned ten bucket- and keystore-scoped claims, and the very next commit
re-pointed them. My snapshot landed inside that window. The campaign's enforcement did
not move backwards; a four-commit window did, and it has closed. What remains is the
enrollment three, unchanged since this review opened.

### nested-ungoverned-set-materially-larger | critical | The confirmed NESTED-UNGOVERNED set is four compositions in two modules; measurement finds roughly fourteen destinations across eight

**Claimed:** the closure reference records two confirmed NESTED-UNGOVERNED sites — the
`application/live/_iva_remote_state.py` pair under `cadrumo_audit_dir`, and the
`adapters/persistence/storage/_rotation.py` pair under `cadrumo_submissions_dir` — and
states that if a census finds more of this shape, the criterion is not met.

**Verified:** it finds more. Two AST passes over every production module at HEAD, plus
targeted reading of what they missed:

- `_rotation.py` also joins `'manifests'` onto `cadrumo_attachments_dir` — a third site
  in a module the reference already names, unrecorded.
- `adapters/persistence/storage/master_key/_master_key.py` joins `'keyring.lock'` onto
  `cadrumo_secret_store_dir`, and joins `'master.key'`, `'master.kdf'` and `'master.lock'`
  onto the same directory held as `self._store_dir`.
- `application/user_profile/_custody.py` joins `master.recovery.key` (a module constant)
  onto `cadrumo_secret_store_dir`.
- `domain/calculations/registry/_validate_evidence.py` and `_validate_verdict.py` join
  their cache filenames onto `cadrumo_corpus_text_cache_dir` and
  `cadrumo_validation_verdict_cache_dir`.
- `_iva_remote_state.py` carries two further segments (`'filed-history'`, `'wallet'`)
  beyond the pair recorded.
- `application/_journal_repository.py` joins `'.repository'` onto its root, alongside
  the `'buckets'` literal `S64` already tracks.

**Gap:** the taxonomy declares file leaves for the bucket layout (`BUCKET_MANIFEST`,
`BUCKET_LOCK`, `KEYSTORE_BUCKET_DEK`) but declares none for the secret store, so the
filenames of the master key, its KDF sidecar, its lock, the keyring lock and the
recovery wrap are all ungoverned segments — the most security-load-bearing filenames in
the product, and exactly the class `R10` moved core-ward for the bucket layout.

Two caveats, both against my own number. **Both passes undercount by construction**: the
first resolves only within a function, the second sees only inline literals and
module-level string constants. `_validate_evidence.py` was invisible to the second pass
(constant-named segment) and `_master_key.py`'s three `self._store_dir` joins were
invisible to it too (attribute-held base); `_validate_verdict.py` is invisible to both
(f-string segment). "Roughly fourteen across eight modules" is a floor, not a count.
And no gate can see any of them: `_is_root_access` in the provenance gate matches only
`STORAGE_ROOT_SETTINGS_FIELD`, so a join onto an already-resolved category is outside
what it watches — precisely as `R9` and the closure reference both state.

Mitigating, and worth stating so this is not read as worse than it is: **none of these
is reachable by `reclaim` today.** All eight directly-resolvable sites sit beneath
parents declared `unbounded_by_design`, which is not in `RECLAIMABLE_LIFECYCLES`. This
is a completeness gap against the criterion, not a live data-loss hazard.

### closure-blocking-work-has-no-plan-row | critical | The phase that owns nested-subpath governance contains zero Steps, as does the census the reference calls the closure evidence

**Claimed:** the plan tracks the campaign's work, and the production write-call census
"has been commissioned."

**Verified:** four phases carry a description and **no Steps at all**: `W02.P06`
("nested subpath governance beneath enrolled categories — closing the ungoverned depth
the research measured"), `W02.P07` (effective-storage-root call-site migration, "six
sites, one file per Step"), `W02.P08` (optional-root CLI resolver convergence), and
`W03.P11` (the peer-held lifecycle gate rewrite). Separately, `W05.P20` promises "gate
mutation proofs and the tree-wide completeness sweep" and carries one Step (`S80`,
the join-detector blind spot); the tree-wide sweep itself has no Step.

**Gap:** `W02.P06` owns the exact work the closure criterion names as the blocking
condition, and it cannot appear as outstanding in any completion figure because it has
no rows to be unchecked. The same is true of the census. "Commissioned" is recorded in
a reference document and a phase description; there is no Step, no owner, and no exec
record, which is a deferral with no owner in the sense the honesty-review rule exists
to surface. `W03.P11` is the inverse defect: `R4` and `R20` both assert the lifecycle
gate rewrite happened and I confirmed the retired dict is gone, so real load-bearing
work landed with no tracking row at all. `W04.P19` is a partial instance — its
description promises a justfile, packaging-manifest and documentation sweep plus a
manifest drift gate, and carries only the docs-stub Step.

### criterion-unmet-by-the-plans-own-rows | critical | Roughly fourteen open Steps are production enrollment, three of them naming production writers that still bypass the accessor

**Claimed:** the re-scoped criterion excludes tests, so the large remaining test-migration
Steps (`S76`, `S77`, `S78`) do not block; `S84`/`S85` are a separate hygiene standard.

**Verified:** that re-scope is correctly applied and I do not dispute it. But of the 25
open Steps, only five are test-surface or POSIX work. The rest are production: `S10`
(the `effective_storage_root` primitive — confirmed absent at HEAD), `S20`/`S21`
(`bucket_paths` and `keystore_path` onto the corrected scoped accessor), `S25`, `S26`,
`S64`, `S27`–`S30`, `S45`, `S46`, `S51`, `S52`, `S53`, `S55`, plus the `S83` and `S62`
gates.

Spot-checked at HEAD: `S51`'s target still reads
`load_settings().cadrumo_corpus_text_cache_dir / _CORPUS_TEXT_CACHE_FILENAME` and
`S52`'s still reads `load_settings().cadrumo_validation_verdict_cache_dir / f"..."`.
Both are production cache **writers** whose Step text says "re-point onto the accessor."

**Gap:** the criterion is "every production file-producing site resolves through the
canonical accessor." The plan itself carries open Steps saying that specific production
writers do not. Closure is unreachable while those rows are open, independent of every
gate, every census, and every finding above. This is the cheapest possible refutation
and it requires no measurement at all.

### settings-defaults-contradict-the-taxonomy | medium | Five settings-field defaults declare a subpath the taxonomy disagrees with, and no gate compares them

**Claimed:** the taxonomy is the single declaration of every application-chosen name,
and the binding gate asserts every `Path`-typed settings field is bound to a member or
a declared escape.

**Verified:** binding is asserted; **agreement is not.** Comparing every bound field's
default against its member's subpath in-process: 20 agree, 2 are opt-in with no default,
and 5 disagree — `cadrumo_registry_parity_store_dir` defaults to `var/audit/registry/parity`
against a declared `audit/registry/parity`, and `cadrumo_financial_txs_dir`,
`cadrumo_invoices_dir`, `cadrumo_attachments_dir`, `cadrumo_usage_ratios_path` each carry
a `var/`-prefixed default against an unprefixed declaration.

Resolved at runtime under an overridden root, the taxonomy wins in all five cases (the
derived-output validator sets the field from `location.relative_path()`), so the
defaults are dead. Dead but not harmless: they are a second declaration of a
taxonomy-governed name that has **already drifted**, which is the precise defect class
this campaign exists to remove, and nothing detects the disagreement. Mitigating: the
generated environment reference renders these as `(derived)` rather than the literal, so
no operator-facing document currently repeats the wrong value.

### r16-excluded-member-list-is-stale | medium | The ADR states eleven fingerprint-excluded members "verified at HEAD"; there are nine, and two it names no longer exist

**Claimed:** `R16` states "The declared set, once shipped, settled at eleven excluded
members" and enumerates them as verified at HEAD, including `STATUS_CACHE` and
`STORAGE_BACKUP`.

**Verified:** nine at HEAD. `S74`'s wire-or-delete decision deleted `status-cache`,
`storage-backup`, `inbox` and `inbox-pdf` outright — genuinely and correctly, along with
the `cadrumo_status_cache_ttl_s` companion field. The consequence is that two of the
eleven members `R16` enumerates as verified no longer exist.

**Gap:** a ruling that states a verified count and enumeration, and is contradicted by
the code, is exactly the shape a fresh reader is entitled to trust and would be misled
by. The correction is one sentence; the reason to record it is that the amendment log
claims the correction discipline was followed repeatedly, and this is one instance where
a later Step invalidated an earlier ruling's verification without the ruling being
re-stamped.

### five-exec-records-still-empty | medium | The backfill closed the seventeen it named; five other checked Steps still carry empty scaffolds

**Claimed:** `S82` backfilled "the seventeen `W01.P01`–`P03` exec records that were
checked complete but left as empty scaffolds," so `plan-closure-requires-exec-records`
holds for the whole plan.

**Verified:** checked Steps and exec records match exactly, 60 to 60, with no orphan in
either direction — genuinely clean bookkeeping. But stripping frontmatter and template
comments from all 60 and measuring the remaining prose: median 491 characters, and
**five records carry nothing at all** beyond the heading and the scope bullet —
`W01.P03.S22`, `W01.P03.S23`, `W01.P03.S24`, `W02.P05.S43`, `W02.P05.S48`. Description,
Outcome and Notes are empty in all five.

**Gap:** three of the five are in `W01.P03`, inside the very range `S82` named as swept.
The seventeen it enumerated were filled; three siblings in the same phase were not, and
two more sit outside the range entirely. The claim is true as stated and incomplete as
implied.

### containment-proof-cannot-see-undeclared-nesting | low | The reclaim containment proof quantifies over declared members, so the nesting it warns about is the only nesting it can detect

**Claimed:** `R21`'s containment proof is derived from the declared axes rather than
listing today's members, so a future member declared prunable at bucket scope cannot
silently join the accepted set.

**Verified:** the proof is genuinely well-built — it derives the accepted set by
invoking the real verb rather than restating its predicate, carries a non-vacuity floor,
asserts over three independent axes, and includes a positive control proving the
`is_relative_to` comparison can fire. That part of the claim holds.

**Gap:** `test_no_accepted_member_contains_a_refused_one` iterates `STORAGE_TAXONOMY` on
both sides, so it can only detect a **declared** protected member nested under an
accepted one. Its own docstring notes that reclaim "removes a category's whole subtree,
including nesting the taxonomy does not declare" — and that undeclared nesting is
exactly what it cannot enumerate. Today this is safe by accident rather than by
assertion: all the finding-two locations sit under `unbounded_by_design` parents. Should
a future member be declared `RETENTION` with undeclared nesting beneath it, this proof
would pass.

### plan-cites-wrong-path-for-a-gate | low | `S69` names a file that does not exist; the gate itself does

**Claimed:** `S69` lands the materialisation-parity gate at
`src/cadrumo/tests/test_storage_materialisation_parity.py`.

**Verified:** no such file at HEAD. The gate exists and passes, at
`src/cadrumo/core/tests/test_storage_materialisation_parity.py`. A path typo in the Step
text, not missing work — recorded only because it cost a verification cycle and would
cost the next reader the same.

### locale-value-constraint-class-is-ungated | high | The help-length regression is fixed at the boundary and nothing would catch its return

**Claimed:** three over-cap Spanish and Hungarian help descriptions broke the whole
`aeat config --help` surface in those locales, invisible in English; found and fixed
hours after shipping. The open question posed: does anything else this campaign put on
an operator-facing surface carry a constraint no gate checks?

**Verified — the fix, then the gap, then the margin.** Building the help document across
all four locales and all three surfaces at HEAD: 12 of 12 succeed, nothing over the cap.
The specific regression is genuinely closed.

The class is not. Both tests whose subject is the help surface —
`operator_surface/tests/test_contract.py` and `cli/tests/test_config_help_payload_contract.py`
— pin `cadrumo_output_language="en"`, and **English is the locale in which this defect is
invisible by construction.** No test anywhere in the tree builds the config-root help
document in Spanish, Catalan or Hungarian; the two non-English `--help` tests that exist
(`test_auth_round5_surface.py`, `test_overview_calendar_verb.py`) invoke *subcommands*,
and building one subcommand does not validate the root — which is the same reason
`config storage list` kept working while the root was broken.

Proven by mutation rather than by reading: lengthening one Catalan description by two
words in a scratch HEAD snapshot makes `build_help_document(CONFIG)` raise
`ValidationError` in Catalan while English still succeeds — the shipped failure exactly
reproduced. Against that broken catalogue the two dedicated help contract tests return
**20 passed**, and a wider run over the root-help, root-payload and locale suites returns
**103 passed** with the only failure an unrelated version-string artifact of running from
a snapshot. Nothing in the tree sees it. The locale parity and honesty gates do not
compare a value against the bound of the field that consumes it — as reported.

**Gap, and why this is high rather than medium:** the corrected strings landed *at the
boundary*. Of 464 constrained strings rendered across the four locales, one Hungarian
`config` description sits at exactly **80 of 80 characters — zero margin**, two Catalan at
79, and ten within ten characters. One of the 79s is this campaign's own
`config storage check`. The next re-wording of any of those — or a translator adding one
accented word — re-ships the identical operator-facing breakage, in a locale no test
exercises. The campaign did not create this gate gap, but it did add strings into its
blast radius and left them with the least headroom in the catalogue.

### size-budget-regeneration-is-sound-but-couples-campaigns | low | The anti-laundering guard holds mechanically; the property that actually raised the pin is different

**Claimed:** the tree-wide baseline regeneration in *"extract the filesystem
path-hierarchy contracts into a sibling module"* raised exactly one entry,
`entrypoints/cli/__init__.py` 1385 → 1414; the file never broke through its pin, so the
band scaled with legitimate growth; and the gate's failure text says a plain
`--write-baseline` will not lift a ceiling you broke through.

**Verified, independently, and the claim holds in every part.** The baseline diff across
that commit is 1 raised, 3 lowered, 1 dropped, 0 added on modules and no change on
callables — the ratchet net-tightened. The file measures 1346 lines at HEAD, under its
1385 pin, so it never broke through. The new pin reproduces arithmetically from the
measured size: `1346 + max(25, ceil(1346 × 0.05))` = 1414, exactly the observed value.
The baseline records a **derived band**, not a measured size.

The anti-laundering guard is mechanical, not merely prose. `build_limits` resolves
`ceiling if actual > ceiling else limit`, so a subject over its prior ceiling keeps that
ceiling and stays red; `dev/audit/size_budget.py` passes `previous=existing.modules` on
the real `--write-baseline` path, so the guard is not inert. Proven by construction with
a positive control: a subject at 1500 against a prior pin of 1385 regenerates to **1385**
(kept, stays red) with a plain regeneration, and to 1575 only with an explicit
`accept_growth`. A tree-wide regeneration is therefore **not** a laundering mechanism for
a campaign's overage.

**The property the check did not reach**, stated because it is the reason the number
moved at all: a regeneration re-bands every module that is *inside* its pin **upward**, to
`actual + ~5%`. That is not laundering — no ceiling was broken — but it is loosening, and
because the baseline is regenerated tree-wide, **one campaign's module split grants fresh
headroom to another campaign's unrelated file.** `cli/__init__.py` gained 29 lines of
allowance because a storage module was split. Downward the band self-corrects (the
staleness check forces a re-measure once slack exceeds `max(60, 10%)`); upward it does
not, so repeated regenerations can walk a module up in ~5% steps indefinitely provided it
never exceeds its current pin before the next regeneration. Nothing counts regenerations.
Low severity and not this campaign's defect — recorded so the next reader asking "why did
our file's pin rise?" finds the mechanism rather than re-deriving it.

### nested-ungoverned-enumeration | critical | 23 undeclared application-chosen names across 34 sites in 14 modules, and why a complete static enumeration is not achievable

**Claimed / asked:** the earlier figure of roughly fourteen destinations across eight
modules was given as a floor, and a floor cannot be closed against. Required: a method
that does not undercount by construction, with its blind spots named; the findings
grouped by declarable shape; and reclaim-reachability flagged.

**Why the first two passes undercounted, precisely.** Both matched an *expression shape*
— `base / "literal"`. A base held on an instance attribute, a segment that is an
f-string, a constant declared far from its use, and a composition assembled across a
function boundary all produce the same defect wearing a different shape.

**Pass three inverts the question and propagates taint instead of matching shape.** It
seeds on every expression that *is* a taxonomy root — a settings field bound to a member,
or an accessor call — then propagates through local assignments, `self` attributes, and
function returns to a fixed point within the module, and records every path composition
over a tainted base *regardless of what the appended segment looks like*, classifying the
segment rather than requiring it to be a literal. That the earlier passes were
shape-limited is now measured rather than asserted: of the appended segments found, only
19 are plain literals against 10 module constants, 5 f-strings and 7 dynamic expressions.

**Result: 34 undeclared compositions across 14 modules**, reducing to **23 distinct
application-chosen names** once repeated sites are collapsed. Four verified individually
against HEAD before reporting; one of those four (`workflow/_persistence.py:441`, a
`run_id` appended to the workflow-runs root) proved to be a **data-derived** segment and
is excluded — which is the distinction that matters for declaration and is applied
throughout below. R5 governs every *application-chosen* segment; a run id, a bucket id or
a content digest is data, and declaring it as a member would be a category error.

**Grouped by declarable shape, because the grouping is the design work:**

*Family 1 — fixed file leaves directly under a declared category (8 names, 14 sites).*
The secret store is five of them: `master.key`, `master.kdf`, `master.lock`,
`keyring.lock` (`master_key/_master_key.py`) and `master.recovery.key`
(`user_profile/_custody.py`). Then `cache/corpus-search/corpus.sqlite`,
`cache/corpus-text/cadrumo_corpus_text_cache.json`, and `logs/cadrumo.log`. **One grammar,
not eight members' worth of argument**: this is exactly the shape the bucket layout
already declares as `BUCKET_MANIFEST` / `BUCKET_LOCK` file-kind members. The secret store
is the conspicuous omission — the taxonomy declares file leaves for the bucket layout and
none for the directory holding the master key.

*Family 2 — fixed subdirectories under a declared category (7 names, 7 sites).*
`financial/attachments/manifests`; `submissions/amendment-results` and
`submissions/amendments`; and under `audit`, the intermediate `live` plus
`live/iva-wallet`, `live/iva-remote-state`, and the caller-rooted `filed-history` and
`wallet`. Ordinary missing directory members, declarable today with no model change.
Note the intermediate `audit/live` is itself undeclared, so declaring only the leaves
would leave a governed leaf under an ungoverned parent.

*Family 3 — instance-scoped file leaves (3 names). **Superseded: already declared.***
`runs/<run_id>/trace.json`, `envelope.json`, `events.jsonl`. The `<run_id>` is data; the
three filenames are application-chosen. I first recommended a `RUN_RELATIVE` scope axis
for these. **That was wrong** — all three are already declared as `StoragePathDefinition`
grammars and behaviourally pinned. See the grammar-mechanism finding below; this family
needs nothing.

*Family 4 — filename templates the model cannot currently express (5 patterns).*
`llm-usage/usage-{}.jsonl`, `llm-run-telemetry/run-telemetry-{}.jsonl`,
`tokens/{}-{}-auth.lock`, `cache/registry-verdict/{prefix}{digest}.json`, and
`llm-cache/<provider>/<model>/{}-{}.json`. `StorageLocation.subpath` cannot express a family of
files matching a pattern, so I first read this family as blocking on a model change or an
ADR ruling. **Both are unnecessary**: the `StoragePathDefinition.grammar` mechanism
already expresses parameterised shapes and pins them against real writes. Family 4 needs
grammar entries and a few vocabulary tokens. See the grammar-mechanism finding below.

**Reclaim-reachability — and this corrects my own earlier finding.** I previously reported
that none of the nested-ungoverned set was reachable by `reclaim`, on the eight
settings-field-rooted sites then known. On the fuller set that is **wrong**: **11 of the
34 sites sit under a reclaimable parent** — `runs` (7 sites), `llm-cache`,
`llm-usage`, `llm-run-telemetry` (retention) and `logs` (rotation). In every one of the
eleven, deletion is the *intended* behaviour: they are regenerable traces, caches and
telemetry whose whole purpose is to be pruned, and `reclaim logs` was observed retaining
an entry rather than clearing the tree. So the conclusion — no undeclared nested location
currently sits under a reclaimable parent where deletion would be wrong — survives, but it
survives on the merits of what happens to be declared today, it is asserted by nothing,
and my earlier blanket statement was too strong.

**Why a complete static enumeration is not achievable, stated rather than assumed away.**
Pass three is complete for compositions *within* a module. It cannot see four classes:
cross-module composition (a helper in module A returns a tainted directory and module B
appends to it); library-named files (a directory handed to a writer that picks the
filename); container-mediated flow (a tainted path stored in a dict, dataclass or list
and read back elsewhere); and fully dynamic roots. The first class is not hypothetical
and its surface is measurable.

**Correcting a number I previously reported as measured.** I first gave that surface as
"260 of 267 production filesystem-mutating call sites". **That was inflated roughly
2.6-fold by a defect in my own census**: it counted every `.replace(...)` attribute call
as `Path.replace`, so every ordinary `str.replace(old, new)` in the tree was scored as a
filesystem rename. The discriminator is arity — `Path.replace` takes one argument,
`str.replace` takes two — and applying it removes **166 false positives**. The corrected
figure is **101 production filesystem-mutating call sites in `src/cadrumo`, of which 96
receive their destination from a parameter, a call, or an attribute**; spot-checking the
survivors finds two more that are service-object `.rename()` methods rather than
filesystem renames, so the true figure is about **99**.

The ratio is essentially unchanged — 95% receive rather than construct, against the 97% I
first reported — so the qualitative conclusion stands. **The absolute number changes what
should be recommended, though, and in the useful direction.** At 267 sites, exhaustive
manual review is not a serious proposal and the residual has to be bounded statistically.
At about 100 it is an afternoon's work: a reviewer can read every production write site
in the tree and classify its destination by hand, which closes the cross-module class
completely rather than bounding it. Static analysis cannot close that class without
whole-program interprocedural dataflow; a human reading a hundred sites can.

**The tightest defensible bound, and the method that reaches it.** No single method
suffices, and the two available ones have *complementary* blind spots rather than
overlapping ones: static taint misses runtime values but sees every site whether or not
a test reaches it; runtime observation misses unexercised code but sees the **resolved
destination string**, so it has no expression-shape blind spot at all. The union is
therefore the non-undercounting method, and its residual is not an unknown — it is
exactly the set of production write sites that both receive their destination
cross-module *and* are never exercised, which is finite and enumerable by intersecting
the ~100 static sites against the frames the instrumented run observes.

So the bound to declare against is: **at least 23 distinct application-chosen undeclared
names, across 34 sites in 14 modules**, with the residual confined to a nameable list
rather than an open question. Declaration work can begin on Families 1 and 2 immediately
— 15 of the 23 names, no model change required — while Family 4 waits on the ruling it
needs and Family 3 waits on the scope axis.

### grammar-mechanism-already-covers-families-3-and-4 | high | Family 3 needs no scope axis and Family 4 needs no ruling; the fan-out grammar already expresses both, and one declared grammar is unpinnable

**Claimed / asked:** before adding a `filename_pattern` field to `StorageLocation` or a
`RUN_RELATIVE` scope axis, check whether `StoragePathDefinition.grammar` already covers
these shapes — and answer whether `grammar` (namespace registry) and `subpath`
(taxonomy) are reachable from one another, or whether using the grammar would mean
declaring a path definition for something that exists only as a taxonomy member.

**Verified: the mechanism exists, does exactly this, and the instinct to check first was
right on both families. I retract my Family 3 recommendation outright.**

`_storage_path_definitions.py` states the division of labour in its own docstring: it
carries "the parameterised fan-out SHAPES (a content-hash prefix, an outbound namespace,
a per-run id) that cannot be enumerable `StorageCategory` members." That is Families 3
and 4 described in advance.

*Family 3 is already done, and a scope axis would have been a second way to say one
thing.* `run_trace`, `run_events` and `run_envelope` are declared with grammars
`<root>/runs/<run_id>/trace.json`, `.../events.jsonl`, `.../envelope.json`; `<run_id>`
already has a regex fragment (16 lowercase hex, the shape the run-id minter produces);
and `test_run_trace_shape_conformance.py` drives the three **real** writers and matches
the **real** resulting paths against the declared grammar. Its docstring even names the
gap it closed: "the `<run_id>` fan-out beneath it was never promoted to a declared
shape." Proposing `RUN_RELATIVE` would have introduced the precise defect this campaign
exists to remove. My earlier recommendation was wrong.

*Family 4 fits, so it needs neither a model change nor a ruling.* The compiler
(`_storage_path_grammar.py`) substitutes `<token>` placeholders from a declared
vocabulary and — exactly as hoped — raises `AssertionError` naming an unrecognised token
rather than matching it silently. Family 4 needs grammar entries plus roughly four new
vocabulary tokens for the interpolated parts (a timestamp, a provider, a model, a verdict
prefix; the verdict digest may already be covered by the existing `sha256` fragment).
The second option — an ADR sentence that instance-keyed files are governed by their
directory — is not needed, because the mechanism can govern them directly and more
strongly, by pinning a real write against a declared shape.

**The coupling question, answered.** They are independent but composable, and nothing
forces the link. `StoragePathDefinition.segment` is optional and, where used, is
populated *from* the taxonomy (`segment=storage_location(...).subpath`) — so a path
definition can reference a member without requiring one. The grammar itself is a
hand-authored string that spells the whole path. Family 4's parent directories are
already taxonomy members, so adding grammars introduces no second authority over the
category.

**But the directory portion of every grammar is a hand-written literal that no gate binds
to the member it duplicates.** `<root>/runs/<run_id>/trace.json` spells `runs` as text
while `StorageCategory.RUNS` independently declares `runs` as its subpath, and no test
compares them. Renaming the member's subpath would leave every grammar silently
disagreeing. That is modest today and multiplies with each grammar a declaration campaign
adds, so it is worth a gate before the campaign rather than after.

**A latent gap found while checking the vocabulary, and it is the secret store again.**
Cross-checking every token used in a declared grammar against the declared fragments:
`secret_index` — `kind=FILE`, a real filesystem path — declares
`<cadrumo_secret_store_dir>/index.json`, and `cadrumo_secret_store_dir` **has no regex
fragment**. Any test pinning that key fails with the compiler's tooling error rather than
a conformance result, so the grammar is declared but unverifiable. (The other undeclared
token, `<object_key>`, belongs to `secure_objects_table`, whose kind is `LOGICAL_SQL` and
whose `db://` path is correctly outside this compiler's scope — not a defect.) The
loud-raise design is right; what is missing is a gate asserting that **every
filesystem-kind grammar compiles against the declared vocabulary**. That gate would have
caught this one, and it should land with the Family 4 entries rather than after them,
since each new grammar is another chance to declare a token nobody defined.

This is the third distinct way the secret store has surfaced in this review: no file-leaf
members for `master.key` and its siblings, five ungoverned filename literals, and now its
one declared grammar unpinnable.

### manual-read-of-every-production-write-site | high | Four unpinned OS-temp destinations against six correctly pinned, and a class of site neither census can classify at all

**Context:** with the corrected count at ~100, reading every production
filesystem-mutating call site by hand became cheaper than bounding the residual
statistically. This records what the read found. It is not yet complete — the unexercised
remainder is prioritised against the containment log — but two results are already firm.

**Result one: a third of the sites are not classifiable at their own location, and that is
structural rather than a gap in the reading.** Roughly fifteen are *transport primitives*
whose destination is always the caller's: the four `core/atomic_write.py` entry points and
their tempfile siblings, `core/locks.py`, `observability/_sink.py`,
`sql/engine.py::_ensure_sqlite_parent`, the master-key throttle and session writers, and
the parity-tape writers. Each does `path.parent.mkdir(...)` on a path it was handed.

Classifying these as unenrolled would be wrong; classifying them as enrolled would be
equally wrong. **They are pass-through, and the enrollment question for them lives at
their call sites, not at the write.** This matters for the method: for a generic primitive
the *only* instrument that answers "where did this actually land" is the runtime log,
because the static answer is "wherever the caller said". It is the sharpest case for why
the union of the two methods is necessary rather than merely thorough.

**Result two: four production sites write to the OS temp directory with no `dir=` pin,
and the same codebase pins six others correctly.** That contrast is the finding — the
compliant shape exists and is used, so these four are an inconsistency rather than a
missing pattern.

The pinned six — `atomic_write.py` (three), `bucket_maintenance/_service.py`,
`modelo/_review_package.py`, `_modelo_review_package_cli.py` — all pass
`dir=<destination>.parent`, which is exactly the shape R11 requires: staged under a
taxonomy-governed location or the destination's own parent, never the OS temp directory.

The unpinned four:

- `blob_store/_materialisation.py:159` — `tempfile.mkstemp` with no `dir=`, the single
  path behind both `materialise_secret` and `export_to_temp_path`. It writes **decrypted
  secret payloads** to the OS temp directory for third-party consumers that demand a path
  rather than bytes (OAuth service-account credentials, Playwright `storage_state`,
  cert-based clients).
- `registry/_workbook_parity.py:493` and `:644` — LibreOffice conversion scratch for
  registry workbook fixtures.
- `entrypoints/cli/__init__.py:1318` — metadata state isolation.

**On the first of those, the careful reading matters and I want to state it precisely
rather than dramatically.** The pattern — decrypted bytes to a mode-0600 temp file,
promptly unlinked — is verbatim the "Bad" example in
`sensitive-financial-data-secure-storage-only`. But that rule's subject is financial
evidence: invoices, bank statements, supporting documents, and decrypted bytes derived
from them. This helper handles credentials and session state, a different class, and the
codebase already declares `cadrumo_certificate_path` an `OPERATOR_INPUT` escape. **So this
is not a breach of that rule**, and reporting it as one would be wrong.

What it *is*: an AD-HOC destination under the closure criterion — chosen by neither the
operator nor the taxonomy — and inconsistent with R11's own reasoning, which refused the
OS temp directory for staged artefacts on the grounds that it is a shared, unconfigured
location. That reasoning does not obviously stop at filing artefacts. The remedy is the
one the codebase already uses six times: pass `dir=`. Whether the anchor should be a
taxonomy member or the consumer's own directory is a small decision someone should take
rather than inherit.

**Reconciled against the earlier integrations finding, and the remedy changes: the
secret-tempfile bridge is dead code, so it should be deleted rather than pinned.**
Verified at HEAD — every reference to `materialise_secret` and `export_to_temp_path` is
the module's own definition, an `__all__` entry, a facade re-export, a docstring mention,
or its own test file. **Zero production callers**, and no dynamic reference either (no
`getattr`, no `import_module`, no string-keyed dispatch). The docstring names Google
service-account credentials, Playwright `storage_state` and cert-based clients as
motivating cases, which describes what a library *can* demand rather than what this
codebase routes through the helper.

The distinction worth keeping precise: **the `SecretStore` itself is very much live** — the
OAuth flow, the certificate backend, custody, login sessions and workflow persistence all
use it. It is only the *path-shaped bridge on top of it* that nothing calls. A reader who
checks "is the secret store used?" gets yes and stops; the question that matters is
narrower.

So this site should be **deleted, not pinned**, and deleting it removes one of the four
unpinned OS-temp destinations outright. Two project rules point the same way:
`aeat-source-hygiene` bars landing design-only shells, and `no-dormant-source-resolvers`
codifies exactly this shape for resolvers — merged capability is enrolled or deleted.

**Dead makes it worse in one specific respect, not better.** An unexercised helper that
writes decrypted secrets to the OS temp directory sits in the public facade with an
inviting docstring, so the next author who needs a path-shaped secret will reach for it
and reasonably read its presence as sanction. That is the dormant-capability hazard rather
than a live one, and deletion closes it in a way that pinning `dir=` would not — pinning
would leave a sanctioned-looking route to a pattern nobody has needed.

That leaves **three** sites to pin with the shape already used six times: the two
`_workbook_parity.py` LibreOffice scratch directories and `cli/__init__.py:1318`.

**Why neither census could have found these.** `tempfile.mkstemp(prefix=..., suffix=...)`
contains no path expression at all, so the taint pass had nothing to seed on; and the
runtime pass sees a resolved OS-temp path but cannot know it *should* have been pinned —
and for the dead bridge it would see nothing at all, because nothing calls it. Only
reading the call, knowing R11 exists, and then checking the caller set produces the
finding and its correct remedy. That is the argument for the manual read stated as
evidence rather than as a preference.

**A gate belongs alongside this**, because the contrast is drift rather than a design gap:
six sites pin correctly and three will not until someone fixes them. An assertion that
every production `tempfile` call choosing an application destination passes `dir=` would
have caught all four. R11's existing review covered the *call* — stage briefly, then zip —
and not the *destination*, which is how these survived a policy that already existed.

### runtime-containment-result-and-the-residual | none | The containment check is clean for exercised paths, and the residual is eight sites in two modules

**The measurement the closure reference called the single highest-value unrun check has now
run.** Every filesystem-mutating primitive was wrapped — including `Path.mkdir`,
`os.makedirs` and `os.mkdir`, which the first pass deliberately left alone and whose
perturbation was accepted for this one — and each call recorded its **resolved
destination** plus the innermost *production* frame that caused it, so the log answers
"which production site wrote, and where did the bytes actually land" rather than only
"did anything escape".

Measured against snapshot HEAD `72b7b06ad3`, 39m53s, `-n 4`, four worker logs plus the
controller: **304,638 distinct (kind, destination, frame) records**, of which 246,648 were
production-framed across **36 distinct production modules**.

**Result — nothing escaped:**

| destination | production-framed writes |
| --- | --- |
| under a declared taxonomy subpath | 212,659 |
| pytest tmp, no declared segment | 33,989 |
| inside the checkout | 0 |
| under the real user home | **not measurable by this instrument -- see below** |
| anywhere else | 0 |

For the paths the suite exercises *and the writes this instrument can observe*, every
production write landed under a taxonomy-declared root or in test scaffolding.

**The user-home row originally read `0`, and that was wrong. It is corrected here rather
than quietly, because it was the strongest-looking line in the whole review and it was an
artefact of the instrument rather than a finding about the tree.**

There is a live leak the instrument could not see. The operator's real diagnostic log at
`<user-data>/cadrumo/storage/logs/cadrumo.log` measured **4,909,370 bytes**, up from
492,406 earlier the same day and last modified *after* the instrumented run had finished.
Every pytest invocation in this shared worktree appends to it, and under fleet load it
grew roughly ten-fold in hours. Verified independently: **zero records across all five
worker logs mention that path**, while the file grew by about 4.4 MB.

**Two compounding reasons, and the second is the more general one.**

*Ordering.* Logging binds its handler when the logging module is configured, ahead of the
pytest plugin's `pytest_configure` where the wrappers install. A handler already bound
writes through a descriptor the wrapper never wrapped.

*Granularity, which ordering does not explain and which perfect ordering would not fix.*
The handler is a `RotatingFileHandler`: it opens the file **once**, and every subsequent
record goes through the retained stream's `write`, never through `open()` or
`Path.write_text` again. Even if the wrapper had installed first it would have observed
exactly **one** event -- the handler's initial open -- and none of the millions of bytes
that followed. **Call-site wrapping cannot see append-through-a-retained-handle at all**,
and that generalises past logging to any long-lived writer: an open database connection,
a streaming export, a held file object.

**So "every primitive wrapped" does not imply "every write observed", and I stated the
first as though it entailed the second.** This is the fifth mechanism recorded earlier in
this document recurring in a third form -- the instrument was not broader than its name
this time but *narrower in time and in granularity*, and a real measurement again got the
wrong name attached to it. The guard is the same one: establish what the instrument can
structurally see before quoting what it did not find. **A zero is a claim about the
instrument until it is shown to be a claim about the world.**

The remedy is in flight: `core/logging.py` is modified in the working tree and uncommitted.

**A limitation of the method, not a footnote on one row.** The blind spot above is a
property of containment-by-primitive-wrapping and should be read as bounding every such
census, including this one: **a long-lived writer that holds its handle is invisible after
its first open.** A log handler, an open database connection, a streaming export, any
retained file object — the wrapper sees the `open()` and then nothing, however many bytes
follow. Any future containment run must either instrument at the descriptor level or
enumerate the retained-handle writers separately and measure them by file size. The
general form: **a zero is a claim about the instrument until it is shown to be a claim
about the world.**

**The open question is answered, and the answer is the reassuring one.** The materialised
tree under the operator's real root is empty shells. Verified directly: **`secrets/`
contains nothing** — no credentials, no key material, no taxpayer data — and the whole
21-directory tree holds five files, all of them derived caches plus the log. The uniform
12:53 stamp is bootstrap creating every declared directory whether or not anything writes
to it, which is why they share one timestamp. Recording it as a question rather than a
finding was the right call, and the question was worth asking.

**The logging leak is fixed at the root and the fix is committed** — two premature
`get_logger` calls in a package documented as import-light, retired; `core/logging.py` is
clean in the working tree. A 640-test slice measured a **0-byte** log delta.

**Two residues, both measured here rather than inherited, and the first is an active rate
rather than a stale delta.** Successive readings of the log: **4,911,417 bytes** as first
reported, **4,911,619 at 19:30**, **4,912,669 at 19:33** — roughly **350 bytes a minute,
still climbing**, with the fix committed at 19:22. That is not a pre-fix process draining;
it is ongoing writing. Against the earlier ~4.4 MB runaway it is a reduction of orders of
magnitude and the fix plainly worked on the path it targeted — but the leak is **reduced,
not closed**, and a single 640-test slice reading zero is consistent with that rather than
evidence against it. The remaining writer is unidentified.

Second, the derived caches under the real root are being written **now**, not historically:
at a baseline pinned to `6ce5a3d4dc` the corpus-text cache is stamped 19:26, a registry
pickle 19:28, the verdict file 19:26 — all within ten minutes of the reading. Five files,
**82,150,682 bytes** total. These are regenerable caches, and `cache/` under the storage
root is a correct location for genuine operator use, so this is not a data-safety finding;
it is evidence that test or fleet activity currently lands there, which is exactly what
`S45`, `S51` and `S52` address. A full-suite measurement at a named object after those land
settles both residues in one run.

**A baseline is recorded above precisely so that measurement is a comparison rather than a
recollection.** Object `6ce5a3d4dc`, wall clock 19:34, five files, 82,150,682 bytes, log at
4,912,669.

**Writes observed in the window; NOT attributable to the command.** I first recorded this
as "reproduced on demand" and that claim was wrong. Corrected here.

What I measured: baseline the real log, run one test file, measure again.

```
pytest src/cadrumo/core/tests/test_storage_taxonomy.py             delta     0 bytes
pytest src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py   delta   258 bytes
```

Two records appeared inside the second window, naming `cadrumo.core.wizard_catalogue` and
`cadrumo.core.setup_answers`. I read that as my command causing them. **A before/after
delta on this machine cannot support that reading.** Eight agents run pytest here
continuously — eighteen Python processes were live while I wrote this paragraph — so the
window belongs to the box, not to the command. The delta establishes only that *something*
wrote during it.

Refuted directly: five sequential launches of that same file produced a cumulative **0
bytes**, and a timestamp mark showed the last log line *predating* the mark, so those runs
emitted no line at all. Of that evidence the **timestamp check is the load-bearing half**
— an absence of lines in a window is sound whoever was running — while a cumulative-zero
across five runs is subject to the same shared-box noise in the opposite direction.

**And attribution is structurally impossible with the current record format.** Verified:
`"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` — timestamp, level, logger name,
message. **No PID, no process identifier of any kind.** Two agents running the same CLI
test emit byte-identical records, so neither content nor content-plus-timing can separate
them retroactively. Any future attempt needs the format to carry a PID first, or the fleet
quiesced.

**The eighth mechanism, and the one this document ends on.** Pinning an object fixes
*when* a measurement refers to. On a shared machine you must also fix **who**, and a size
delta carries no attribution whatsoever. My earlier —350 bytes/minute was a real
observation of the box; it was never an observation of any command, including my own.

**What survives, and it is the part that matters.** The leak is real — the log contains
`_parse_bool: unrecognised token 'banana'` and `FileNotFoundError` under a
`cli-sequence-*` temp root, which are test data and test scaffolding, so peer test runs
are writing to the operator's real diagnostic log. Both parties were wrong about *who*,
not about *whether*. And the structural conclusion is untouched, because it never rested
on a delta: the redirect probe — set `CADRUMO_LOCAL_STORAGE_ROOT` before importing the
package tree, observe **0 bytes** to the real root and the log created under the
redirected root instead — is a **positive result about a redirect working**, not a
negative one about an absence. Nothing a peer process does can manufacture that, which is
why it is the load-bearing evidence for **"collection-time isolation does not cover the
logging path"** rather than "three more modules hold a logger".

### closing-measurement | none | Both gates green at a pinned object; two blockers remain and one is unchanged

**Measured by me, pinned by construction** — SHA resolved into a variable first, that
literal object archived, extracted, run serially with no marker filter:

```
pinned  471ad349d6e6b7ae48d2021dbf950543e56a9595
result  164 passed, 0 failed
gates   settings-lifecycle, liveness, provenance, binding,
        materialisation-parity, taxonomy, storage-management service
```

This is an independent confirmation of the campaign's own report at `c16bb9a0ae`, taken
at a different object by a different party. **The first blocker is closed.** The
enrollment change landed, and with it both the five literals and the three unbacked
consumer claims that shared its cause.

**The other three, re-checked at the same pinned object rather than assumed:**

- *Nested-ungoverned set larger than recorded* — **substantially reduced, not closed.**
  The secret store's five file leaves are declared, its grammar re-anchored, the
  active-profile pointer enrolled, and the dead tempfile bridge deleted rather than
  pinned. The Families 1 and 2 remainder and all of Family 4 are still to land.
- *Closure-blocking work has no plan row* — **RESOLVED after this review closed.**
  Verified at two named objects, `13f28dafa0` and a later `30c10823fe`, with a parse that
  touches no shell: **23 phases, 114 Steps, 75 checked, 39 open, and zero phases carrying
  no Steps.** `W02.P06` now holds 11 Steps of which 5 are checked, `W02.P07` holds 6 with 2,
  and `W03.P11` is complete. The rows that existed only in the working tree when this review
  first measured them have been committed, so the finding closes against the artefact a
  reader can fetch rather than against a promise.

  *As it stood when the review measured it, retained because the sequence is the lesson:*
  unchanged at every committed object — `72b7b06ad3`, the pinned `471ad349d6` and a
  later `9f6969150e` all read 22 phases, 82 Steps, 54 checked, 28 open, with four phases
  carrying zero Steps. The 114/69/45 figures reported against it at the time were the
  working tree's and matched no committed object. The production write-call census remains
  a partial exception: **the artefact exists** — it is in this document, static and
  runtime both — while its tracking row did not, so the evidence was no longer missing
  while the accountability was.

- *Criterion unmet by the plan's own open Steps* — **unchanged in kind, larger in count.**
  28 open Steps against 25 when this review opened. That rise is healthy rather than
  worrying: it is the enumeration and the gate work being written down.

**So the reason closure is blocked has changed, and the change is worth naming.** It was
"the campaign's own enforcement is red at HEAD" — an integrity problem. It is now "the
declared work is not finished, and one phase of it is still untracked" — an ordinary
completion problem. The first kind should stop a closure claim outright; the second is a
burndown with a known end.

### the-site-gate-b-found-that-i-missed | medium | My enumeration missed a tracked site, and the reason is procedural as well as technical

**Reported to me:** a gate built on my enumeration surfaced
`application/_config_reset_repository.py`'s `reset-operations` — a duplicate constant
joined onto the raw storage root, bypassing `storage_path()` — which my census did not
find.

**Verified, and the diagnosis has three parts.**

*Technically, it falls in two residual classes I had declared.* The join is not a single
expression: `root = storage_root or resolved_settings.cadrumo_local_storage_root` and the
dirname travels separately as a keyword argument into a constructor, where the composition
happens. That is cross-boundary composition plus container-mediated flow — two of the four
classes I named as unseeable. Finding an instance of a predicted class validates the bound
rather than refuting it.

*But there is a real seed-set gap that is mine.* My taint pass seeds on settings fields
that are **taxonomy members**, and the storage root deliberately is not one — it is the
container. I excluded it on the reasoning that the provenance gate already covers root
joins. The two instruments therefore shared a blind spot neither owner would notice from
their own side: the provenance gate sees a *direct* root join, my pass sees *member*
joins, and a root passed as a parameter and joined behind a constructor is invisible to
both. Seeding on the root as well would have cost nothing.

*And the procedural gap matters more than either.* **This site is already tracked as plan
Step `S25`**, open, naming the exact file and the exact defect — "collapse the twin
reset-journal directory-name declaration onto the taxonomy member". I enumerated from the
code and from the closure reference and never cross-referenced the plan's own open Steps,
several of which name production enrollment sites directly. That is a cheap source I did
not use, and it would have caught this one for free.

So the honest accounting: it is a genuine miss in my enumeration; it is not a new unknown
for the campaign, which has tracked it since the plan was authored; and the count does not
grow by one, because `S25` was already inside the open-Step total I reported as blocking.

### s81-mode-bits-evaluated-on-posix | none | The root-permission assertion holds on a real POSIX host, umask-independently, with its control firing

**The Step:** `W05.P21.S81` — execute the root-permission-drift finding and the mode-bit
assertion on a real POSIX host. Open because Windows has no meaningful mode bits, so the
assertion sits behind `if os.name != "nt"` and is unevaluable on the machine this campaign
normally measures from. The instrument, in that case, is the platform itself.

**Host.** `gergelys-macbook-neo` was offered and is reachable over Tailscale
(`100.111.203.66`, active, direct), but **SSH refused both available keys**
(`publickey,password,keyboard-interactive`) and Tailscale SSH is not serving there. I did
not attempt passwords and did not touch that machine's authentication — the standing
instruction is to report blocked rather than route around an auth boundary. Measured
instead on the WSL2 Ubuntu guest of this workstation: **Linux 5.15.167.4, python 3.14.4,
`os.name == 'posix'`, euid 1001** — a genuine POSIX host with a native ext4 root, and no
root privilege required.

**Object measured.** `63a969556a`. Two facts compose the assertion, and each is established
on the platform that can see it:

*The hardening call is unconditional* — verified statically at that object.
`ensure_storage_tree` materialises the tree, then executes `root.chmod(STORAGE_ROOT_MODE)`
with `STORAGE_ROOT_MODE = 0o700`, outside any platform branch and after the mkdir loop, so
it is last-writer.

*That call's effect on POSIX* — measured, replicating the exact sequence with stdlib only:

```
                created   assertion_holds   after chmod 0o755   control_fires
umask 0o000      0o700         True               0o755             True
umask 0o022      0o700         True               0o755             True
umask 0o077      0o700         True               0o755             True
```

**The assertion holds, and its positive control fires.** The umask sweep is the part worth
keeping: `chmod` is not umask-masked while `mkdir(mode=...)` is, so a hardening that lands
exactly `0o700` under a hostile `0o077` and a permissive `0o000` alike is demonstrably the
former. A DrvFs (`/mnt/c`) run behaved identically, which is a mild surprise worth
recording rather than a finding.

**What was NOT evaluated, precisely.** The literal pytest function was not executed on
POSIX. Doing so needs the project's dependency set installed into the operator's WSL, and
installing into their machine is not something to do unasked. What is therefore unproven
is only the *composition through pytest's fixtures* — the two facts above cover the
mechanism the Step exists to check, but a reader wanting the test itself green on POSIX
should know it has not been run, and that closing the Step on this evidence is a judgement
rather than an execution.

**One observation the measurement surfaced**, promoted to its own finding below {D} and
corrected there, because my first statement of it overstated the exposure.

**Artefacts left in place** under `/tmp` and `/mnt/c/.../Temp` on the WSL guest, per the
standing no-delete rule. Nothing installed, nothing configured, nothing removed.

### root-mode-hardening-is-best-effort | low | The chmod failure is swallowed at debug level, but the resulting condition is detectable by an operator verb

**Reported first, and overstated.** I told the lead this failure was "announced only in a
debug log nobody reads". **That is wrong, and writing the finding up carefully is what
showed it.** The corrected version is narrower and worth less alarm.

**What is true.** `core/config.py:1405-1407`, at object `e65c592b07`:

```python
try:
    root.chmod(STORAGE_ROOT_MODE)                      # 0o700, config.py:1330
except (OSError, NotImplementedError):                 # pragma: no cover
    _LOGGER.debug("could not restrict permissions on %s; relying on filesystem ACLs", root)
```

The hardening is best-effort and its failure is recorded at **debug** level at the point of
failure. The storage root holds encrypted records, the key material that opens them, and
the audit trail over both, so a refused `chmod` leaves that tree at whatever mode it
inherited.

**What I missed, and it is the mitigating half.** The resulting *condition* is not
undetected. `application/storage_management/_service.py:196-205` compares
`root.stat().st_mode & 0o777` against `_EXPECTED_ROOT_MODE` and raises a
`ROOT_PERMISSIONS_DRIFTED` issue with the observed and expected modes, surfaced through
the shipped `config storage check` verb. Two details make it better than a spot check:
`_EXPECTED_ROOT_MODE` is **bound to the materialiser's own constant** rather than
restating `0o700`, so the check cannot keep passing against a mode the materialiser no
longer requests; and `_root_mode_is_enforceable()` declares the check **unenforced** on
Windows and reports `root_mode_enforced` in the payload, rather than passing vacuously
where mode bits mean nothing. That is the same non-vacuity discipline this campaign's
better gates show elsewhere.

**So the accurate residual is narrow: the failure is detectable on demand, not
self-announcing.** Nothing above debug fires when the `chmod` is refused, and nothing
re-checks at write time — so an operator learns only if they run `config storage check`.
Whether that is worth changing is a judgement for whoever owns the surface: an argument
for raising the log level, and an argument that a verb built precisely to report this
condition is the right place for it and a warning on every bootstrap would be noise.

**Not campaign-caused and not in scope.** Recorded so it survives outside an S81 record
about something else, per the request — and recorded at its true severity rather than
the one I first gave it.

### rotation-guard-conflates-two-states | low | Two rotation-path existence guards cannot distinguish "never provisioned" from "vanished", and no downstream check recovers the distinction

Surfaced by the out-of-plan `default_blob_store_roots` doubled-path fix (commit
`5fbd329fd0`), independent of `S81`. **Not paired with the `chmod` finding above** — that
finding's initial framing was itself an overstatement the lead corrected after verifying
`ROOT_PERMISSIONS_DRIFTED` at `application/storage_management/_service.py:196-205`
detects the condition on demand; pairing this finding beside it on shape alone, before
confirming a downstream detector is equally absent here, would be the same error repeated.
It was not repeated: the absence claim below was checked by reading the consuming code,
not inferred from the shape resembling the `chmod` case.

**Where.** Two guard sites, identical shape, both in
`adapters/persistence/storage/_rotation.py`:

- `default_blob_store_roots` (line 579, the fixed version): `if not setting_path.exists():
  continue` — a candidate blob-store root that does not exist is silently dropped from
  the returned tuple before rotation ever sees it.
- `rotate_blob_stores` (line 522): `if not root.exists(): continue` — the same check
  again, one call deeper, for a root that reached the function some other way (an
  operator-extended tuple, a caller that skipped the default helper).

The identical shape exists a third time, for the other rotation surface, at
`_iter_envelope_files` (line 209, `if not entry.store_dir.exists(): continue`), which
`rotate_master_key` walks for the `*.envelope.json` consumers `default_rotation_plan`
enumerates. All three are the same deliberate, stated design: `test_skips_missing_directories`
records the rationale explicitly — a pre-provision installation whose consumer directory
was never created has nothing to rotate, and reporting that as a clean `(0, 0, 0)` rather
than an `OSError` is correct, not a bug.

**Why it is nonetheless a finding.** `Path.exists()` answers one boolean question and the
guard treats every `False` the same way, but two genuinely different states produce it:
a directory that was **never created** (a consumer type never used — nothing to rotate,
benign) and a directory that **existed and became unavailable** at the moment rotation ran
(an unmounted volume, a permissions change, a transient filesystem fault — real content
that rotation silently failed to reach). Master-key rotation exists specifically so the
old key can be safely retired; a root that silently drops out of the walk for the second
reason means whatever ciphertext lives under it keeps its old-key wrapping while the
`RotationSummary` reports the same clean shape a genuinely-empty pre-provision root would
— `errors == 0`, not merely `rotated == 0`. The operator has no signal to distinguish "there
was nothing here" from "something was here and I could not see it."

**Why it matters specifically for rotation and not for the file-envelope path the same
guard shape also covers.** The stakes are asymmetric. A missed `RotationPlanEntry` walk
(`_iter_envelope_files`) leaves an envelope file re-encryptable on the NEXT rotation run,
because `rotate_master_key`'s own resume-idempotency contract (decrypt-under-new-key-first,
fall back to old-key) means a still-old-key file is simply picked up and rotated correctly
whenever the directory becomes reachable again — nothing is lost, only delayed. Blob-store
rotation carries the same resume contract in principle
(`EncryptedBlobStore.rotate_master_key` also tries the new key first), so a rotation run
that missed a transiently-unavailable root is likewise recoverable **on its own** by a
later run over the same root — the asymmetry is not that blob rotation is unrecoverable
where envelope rotation is resumable; both resume correctly if run again. The asymmetry is
operational: nothing in either path currently signals that a supposedly-covered root was
skipped for a reason other than "this consumer was never provisioned," so an operator (or
an automated rotation job) that treats a clean `RotationSummary` as "the old key is now
safe to retire" has no way to tell the two `False` states apart from the summary alone.
Retiring the old key on that belief is exactly the hazard `rotate_blob_stores`'s own
docstring warns about for a missed blob: "the blob is unrecoverable" once the old key is
gone — and unlike the file-envelope path's later-run recovery, once the old key material
itself is destroyed, a root that reappears afterward cannot be rotated at all.

**What would detect this, named concretely, and confirmed absent by reading the code
rather than by its absence from memory.** The `chmod` finding's mitigating half is a real
downstream consumer: `ROOT_PERMISSIONS_DRIFTED`, a persisted-condition check independent
of the moment the `chmod` failed, reachable through a shipped operator verb
(`config storage check`). The equivalent shape here would be a consumer that reads a
`RotationSummary` (or the root tuple `default_blob_store_roots` returned) and cross-checks
it against an independent expectation — for instance, comparing the roots actually walked
against the declared root-scoped `StorageCategory` members the taxonomy already enumerates,
the way the campaign's materialisation-parity gate cross-checks the materialised tree
against the declared member set. Grepped the whole tree for every symbol that shape would
need to consume — `RotationSummary`, `rotate_blob_stores`, `rotate_master_key`,
`default_blob_store_roots`, `default_rotation_plan` — and every hit outside
`adapters/persistence/storage/_rotation.py` itself is either the package's own `__init__.py`
re-export or a test file; none of `test_storage_liveness_gate.py`,
`test_storage_binding_gate.py`, `test_storage_provenance_gate.py`, or
`test_storage_materialisation_parity.py` mentions rotation at all. There is no operator
verb, no application-layer consumer, and no campaign gate standing behind either rotation
surface. The absence is not inferred from the shape of the finding; it is what the grep
returned.

**Severity, stated explicitly.** `low`, not `medium`, and the reason is reachability, not
consequence: `rotate_blob_stores` / `default_blob_store_roots` have **zero production
callers**, so no operator or automated job can trigger this today. The consequence *if* it
fires is severe (an operator retiring an old master key on a false-clean summary), which is
why it is recorded rather than dropped; the low label reflects only that nothing reaches
the code path yet.

**Not campaign-caused, not fixed here, and correctly left alone.** The doubled-path fix
corrected which root the guard is applied to; it did not (and should not have, unasked)
change what the guard does with a `False`. The guard's current behaviour is a deliberate,
consistently-applied, module-wide design choice with a stated rationale and passing test
coverage — reversing it inside an unrelated bug fix would be scope creep, and the right
owner is whoever designs the eventual operator-facing rotation verb (today there is none).
Recorded here so it survives outside the Step record that happened to surface it.

### s109-and-s111-independently-verified | none | Both hold; the S109 plan row suggested a tautology and the implementer correctly declined it

Verify-or-refute on two rows claimed landed by the lanes that did them. **Both hold.**
Pinned object `6286744492` throughout; every claim below read with `git show <sha>:<file>`
and every gate run from an archive of that object.

**`S109` — the compatibility-lifecycle gate was updated, not tautologised.** The
parametrised cases feed synthetic `floors` mappings and assert
`unfloored_durable_formats(floors, PERSISTED_FORMATS) == expected` against **literal
hand-written tuples**
(`tests/test_compatibility_lifecycle_gate.py:177-210`). The expectation is independent
data, not predicate output, so a wrong classification in `PERSISTED_FORMATS` still reds
it. A companion, `test_the_enrollment_predicate_accepts_a_complete_freeze`, supplies the
other half of non-vacuity by proving the predicate is not simply always-failing. **17
passed.** The classification the update depends on carries real reasoning rather than a
paste: `core/compatibility_lifecycle.py:100-105` argues `bucket_database_file` is DURABLE
because the rows inside are already DURABLE under `secure_object` and the file carrying
them is the same obligation at the container level.

**The notable part is what the implementer refused to do.** The plan row for `S109` itself
suggests *"deriving the expectation from the declared formats rather than restating it by
hand, since a hardcoded census of uncovered formats is the gate shape this project forbids
elsewhere."* **Following that suggestion would have gutted the gate.** Deriving the
expectation from `PERSISTED_FORMATS` — the same table the predicate reads — makes the
assertion compare the code against itself, which is R14's failed-migration shape and R20's
reason for keeping an independent pinning oracle alive. The hand-maintained tuple *is* the
oracle, and the maintenance cost of updating three of them when a durable format is added
is what buys the independence. The row's instinct (hardcoded censuses are usually a smell)
is a good general prior applied to the one case where it inverts. Recorded because the
row's text survives in the exec record's scope bullets without noting it was declined, so
the next reader meets the suggestion and not the reasoning against it.

**`S111` — the anchor field landed and both tests are non-vacuous.** `StoragePathAnchor`
(`_namespace_taxonomy.py:78`) declares `STORAGE_ROOT` and `BLOB_STORE_ROOT`; the `anchor`
field carries a `model_validator` that guards **both** directions
(`_storage_path_definitions.py:108-121`) — a `LOGICAL_SQL` `db://` entry must *not*
declare an anchor, every other kind *must*. The exclusion test asserts **set equality**
against the three named blob keys, so an empty set and a full set both fail: exactly the
non-vacuity property its name claims. Its sibling reproduces the original false positive
and, better, asserts the coincidence still exists as an explicit *fixture assumption*, so
the test announces itself if it ever stops demonstrating anything. **34 passed.**

**Two corrections to the report, neither material to the verdict.** The registry holds
**29** path definitions, not 28 — 25 `STORAGE_ROOT`, 3 `BLOB_STORE_ROOT`, and 1
`LOGICAL_SQL` correctly carrying no anchor. And the `anchor` field is **conditionally**
required rather than required; the conditional form is the better design and is worth
describing accurately rather than simplified.

**One small real defect.** `StoragePathAnchor`'s own docstring
(`_namespace_taxonomy.py:81-83`) states *"Sixteen of the nineteen `<root>`-anchored
filesystem entries mean the top-level storage root"*. The live figures are **25 of 28**.
The prose describes the data declared directly beneath it and no longer matches — the
same class as R16's stale excluded-member enumeration, cheap to correct, and the kind of
count a future reader would reasonably trust.

### real-log-writers-are-cli-not-pytest | none | Isolation holds; the operator's log is being written by live CLI invocations, which is correct behaviour

**Question.** The operator's real log was growing at roughly 8 KB/min, twenty times the
earlier rate, and the dominant loggers had changed from import-time registration to
runtime work — `core.locks`, `keyring.backend`, `workflow._persistence`, `sql.engine`,
`master_key`. Pytest leakage and legitimate CLI use have opposite remedies, and the logger
names cannot discriminate: they *look* like real bucket operations, which is precisely the
shape that invites a guess.

**Anchored at `da05945b76`, fleet condition stated: 40 live Python processes, 8 of them
pytest, two of them `aeat config profile edit` CLI invocations alive since 22:28:45.**

**Discriminator, built to avoid the logger names entirely: compare *where* records land.**

*Isolation demonstrably works, at scale.* 1,300 per-process isolated roots exist under the
platform temp directory, and **146 of them carry `workflow._persistence` records** — the
very logger dominating the real log. Pytest's writes are landing where the isolation
intends. The same roots carry the rest of the mix: `core.locks`, `sql.engine`,
`master_key`, `blob_store`.

*Controlled negative.* Running 100 tests of the workflow package — exercising exactly
that dominant logger — produced:

```
real log delta        0 bytes
isolated roots     1292 -> 1300
```

*The residual traffic correlates with the CLI.* The real log's repeating tail is
`persisted revision-aware workflow state update`, and two `aeat config profile edit`
processes span the whole heavy-write window.

**The `setdefault` hazard is not firing, and it is deliberate rather than a bug.**
`conftest.py:66` uses `os.environ.setdefault`, whose own docstring states the semantics
exist to respect a real ambient environment. `CADRUMO_LOCAL_STORAGE_ROOT` is not set
ambiently here, so the no-op case does not arise.

**Conclusion: not pytest. A real CLI invocation writing to the operator's real diagnostic
log is correct behaviour, and there is nothing here to fix.**

**One genuine residual.** The real log carries one line each from `wizard_catalogue` and
`setup_answers` — import-time registration records that reach the real root when a
process imports them before the root conftest's `setdefault` runs. The same 258-byte
signature appears in some isolated roots, so most processes order it correctly. The root
fix has landed; a few stragglers remain. This is also the honest explanation for the
258-byte delta recorded earlier in this document and retracted as unattributable: that
signature is real and reproducible in kind, but which process produced any given instance
of it remains unattributable.

**Limits, because this is a positive control rather than direct attribution.** No record
carries a PID, so no individual line can be attributed to a process. What the controlled
test establishes is that the isolation mechanism works for a fresh process exercising the
dominant logger; it inverts the burden of proof rather than closing the question. A
definitive answer still needs either a PID in the format or a quiesced box.

**A refinement that changes what the census needs.** Since pytest writes land in isolated
roots, **the real storage root is not being polluted by test leakage** — it is being
written by real CLI use. So "quiet" for census purposes means **no live `aeat` CLI
invocations**, not merely no pytest. That is a different gate, and it means the census is
currently blocked by other campaigns' legitimate activity rather than by any defect.

### verified-sound | none | What the record claims and the code supports

Stated because a clean result is a result, and because several of these were the
likeliest places to find a problem.

`R20` holds exactly as written: `_STATE_ROOT_DERIVED_DIRS` is absent from every file at
HEAD, not merely unblocked. `S73`/`S74` genuinely landed — all four dormant categories
and the companion TTL field are deleted, and no member declares a `dormant_reason`
today. `R7`'s operator surface is real and works: `config storage list` enumerates 26
resolvable locations of 41 declared members, `check` reports healthy on a fresh tree,
`reclaim logs` succeeds and `reclaim secrets` refuses with a localised message naming the
lifecycle class, the entry count and the path.

Gate construction quality is high and above what this codebase's rules require. The
binding gate carries a non-empty-discovery floor and detector-fires controls in both
directions; the materialisation-parity gate asserts both sets non-degenerate before
comparing them, and proves its unexplained-directory detector can fire; the containment
proof derives from the real verb rather than a copied predicate. I looked specifically
for a gate whose subject is empty or whose positive control is missing and did not find
one beyond the two already confessed (`S18`'s fixed-not-overridable assertion, true by
absence, and the provenance gate's narrowed scope, which its own module docstring
states accurately).

The self-reported weaknesses I was asked to verify rather than rediscover all check out
as described: the provenance gate's census does undercount by construction;
`cadrumo_database_url` is a `str` and invisible to the `Path`-typed binding machinery;
`S83`, `S10` and `S81` are genuinely open and honestly recorded as such; the criterion
re-scope excluding tests is correctly and consistently applied. I found no third
unaccountable checkbox, though I cannot verify checkbox authorship — one shared git
identity — so absence of evidence is the most I can offer there.

## Recommendations

Blocking, in the order that makes the next measurement cheapest:

1. Land the enrollment change in `_app_live.py` and `_overview_evidence.py`. **Both
   blocking gates trace to that single unlanded diff** — the lifecycle gate on its five
   literals, the liveness gate on the three members whose declared consumer reaches the
   location by literal instead of by member. It is the campaign's last actionable
   blocker and it is sitting unowned in the working tree. Re-measure serially against an
   explicitly pinned SHA afterwards; do not declare closure while a campaign-owned gate
   is red at HEAD.
2. Author Steps into `W02.P06` for every nested-ungoverned destination, using the list
   in finding two as a starting inventory rather than a complete one. The secret-store
   file leaves (`master.key`, `master.kdf`, `master.lock`, `keyring.lock`,
   `master.recovery.key`) should be declared members with `FIXED` override policy for
   the same reason `R10` moved the bucket layout core-ward; a follow-on ADR ruling is
   needed only if any of them is judged to belong outside the taxonomy.
3. Author a Step for the production write-call census in `W05.P20`, or strike the
   sentence in the closure reference that calls it commissioned. Either resolves the
   ownerless deferral; leaving it as prose does not.
4. Close, or explicitly re-scope with a stated reason, the open production-enrollment
   Steps — `S51`, `S52`, `S53` at minimum, since their own text asserts the criterion is
   unmet for the sites they name.
5. Read all ~100 production filesystem-mutating call sites by hand and classify each
   destination. This is now the cheapest way to close the enumeration completely rather
   than bound it: the count is small enough for exhaustive review, which is the only
   method that closes the cross-module composition class outright. Then declare
   Families 1 and 2 of the enumeration — 15 names, no model change needed — as
   `StorageCategory` members. Declare Family 4 as `StoragePathDefinition` grammars plus
   the handful of vocabulary tokens they need; no model change and no ruling is required,
   the mechanism already exists. Family 3 needs nothing: it is already declared and
   pinned. Land two gates alongside: every filesystem-kind grammar must compile against
   the declared token vocabulary (which would have caught `secret_index`), and every
   grammar's directory portion must agree with the taxonomy subpath it spells out.

Non-blocking:

6. Parametrise the two help-surface contract tests over all four locales, or add one
   test that builds every `HelpSurface` in every locale. It is the cheapest possible
   gate for the class, and without it the corrected strings sit one edit from
   re-shipping. Separately, give the ten near-cap strings real headroom rather than
   leaving the tightest at zero.
7. Add a gate asserting every bound settings field's default equals its member's
   `relative_path()`, and correct the five `var/`-prefixed defaults. A dead literal that
   already disagrees with the authority is the campaign's own subject matter.
8. Re-stamp `R16` with the current count of nine and remove the two deleted members from
   its enumeration.
9. Backfill the five empty exec records, and prefer a content check over a filename
   check when asserting `plan-closure-requires-exec-records` in future.
10. Extend the containment proof with an assertion over the *resolved subtree* rather
   than the declared set. The cheaper form is stronger than it looks: assert that no
   reclaimable category has any undeclared child. That is true today and is precisely
   the property the enumeration shows is currently unasserted.
11. Correct `S69`'s cited path.

One methodological note for whoever runs the next pass. Every finding above that matters
came from executing something — a serial gate run, an in-process comparison of the
taxonomy against the settings model, an AST pass, a CLI smoke — and the two findings I
would have got wrong by reading alone were the settings-default drift (invisible in
source, because the validator overwrites it) and the reclaim reachability of the
nested-ungoverned set — where reading alone gave me a blanket "none is reachable" that
the fuller enumeration then contradicted, eleven of thirty-four sites sitting under a
reclaimable parent. That correction is the clearest argument in this document for
measuring twice: the first answer was mine, confident, and wrong in the safe direction. The closure reference
is right that a runtime containment check is the stronger method, and it remains the
single highest-value unrun measurement in this campaign.
