---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:19cf47c51157feec77272068071d4cf040f1c0a522dbe3443730ae9d13c47cb5'
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

**Verdict: the closure criterion is not met.** Four findings block; seven do not,
of which one (the ungated locale value-constraint class) is high and should not wait. The
verdict is not close — it is established three independent ways, and the campaign's own
open Steps establish it before any independent measurement is considered.

## Findings

### two-campaign-gates-red-at-head | critical | Two gates this campaign authored fail at committed HEAD on unenrolled production sites

**Claimed:** the closure record triages a 21-failure full-tree run as 13 parallelism
phantoms, 2 stale, 1 real and routed, 5 under serial verification, and attaches the
caveat that parallel runs manufacture failures.

**Verified:** a serial, single-SHA run of the six storage gates against a HEAD snapshot
gives **157 passed, 2 failed**. `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference`
and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`
both fail. Neither caveat applies: no parallelism, no moving tree.

Both fail for the same cause — five production literals naming taxonomy-governed
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

**Re-measured at a later HEAD, and the situation moved backwards rather than forwards.**
The first measurement was at HEAD `72b7b06ad3`. Re-run against a fresh archive of HEAD
`1b4cecc31f`, fifteen commits later, serial and single-SHA: **2 failed, 13 passed**, the
same two gates.

- The settings-lifecycle gate is **still red**, on the identical five literals. The fix
  remains uncommitted peer WIP: both modules are still `M` in the working tree with the
  literals present at HEAD and absent only from the working copies. `git diff` over both
  gate modules and `_storage_taxonomy.py` across those fifteen commits is empty, so the
  gates themselves did not move — only the surrounding tree did. A campaign report that
  this gate "has since gone green" is a working-tree reading, not a HEAD fact.
- The liveness gate went from **3 unbacked consumer claims to 13**. The ten new ones are
  every bucket- and keystore-scoped member — `bucket.db`, `bucket.blobs`, `bucket.audit`,
  `bucket.manifest`, `bucket.lock`, `bucket.output-language-hint`, `bucket.keystore`,
  `keystore.bucket-dek`, `keystore.profile-session`, `keystore.login-throttle` — all
  still claiming `_namespace_registry.py` after the path-hierarchy extraction moved their
  consumers into a sibling module. That is R10's entire core-ward migration reporting its
  consumption unbacked.

The diagnosis of the ten is understood and the remediation is described as routed. The
distinction worth keeping is that routed describes intent and the gate describes state:
at HEAD the campaign's own enforcement is failing on more claims than when this review
opened, which is the opposite direction from the closure narrative.

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

*Family 3 — instance-scoped file leaves that need a new scope axis (3 names).*
`runs/<run_id>/trace.json`, `envelope.json`, `events.jsonl`. The `<run_id>` is data; the
three filenames are application-chosen. Declaring these needs a `RUN_RELATIVE` scope
anchored on the runs root, structurally identical to the `KEYSTORE_RELATIVE` /
`KEYSTORE_ROOT` pair R13 added — which is precedent, not new design.

*Family 4 — filename templates the model cannot currently express (5 patterns).*
`llm-usage/usage-{}.jsonl`, `llm-run-telemetry/run-telemetry-{}.jsonl`,
`tokens/{}-{}-auth.lock`, `cache/registry-verdict/{prefix}{digest}.json`, and
`llm-cache/<provider>/<model>/{}-{}.json`. **This family is the one that blocks a
declaration campaign rather than merely feeding it.** `StorageLocation.subpath` is a
single string plus a `node_kind`; it has no way to express *a family of files matching a
pattern* inside a declared directory. Whoever declares these needs a ruling first: either
the model gains a filename-pattern field, or the ADR states explicitly that
instance-keyed files inside a declared directory are governed by the directory alone.
The second is probably right and is cheap — but it must be *stated*, because today the
silence is indistinguishable from an oversight.

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
and its surface is measurable: of **267** production filesystem-mutating call sites,
**260 receive their destination from a parameter, a call, or an attribute** rather than
constructing it locally. Static analysis cannot close that without whole-program
interprocedural dataflow, which would carry its own unsoundness in a codebase this
dynamic.

**The tightest defensible bound, and the method that reaches it.** No single method
suffices, and the two available ones have *complementary* blind spots rather than
overlapping ones: static taint misses runtime values but sees every site whether or not
a test reaches it; runtime observation misses unexercised code but sees the **resolved
destination string**, so it has no expression-shape blind spot at all. The union is
therefore the non-undercounting method, and its residual is not an unknown — it is
exactly the set of production write sites that both receive their destination
cross-module *and* are never exercised, which is finite and enumerable by intersecting
the 267 static sites against the frames the instrumented run observes.

So the bound to declare against is: **at least 23 distinct application-chosen undeclared
names, across 34 sites in 14 modules**, with the residual confined to a nameable list
rather than an open question. Declaration work can begin on Families 1 and 2 immediately
— 15 of the 23 names, no model change required — while Family 4 waits on the ruling it
needs and Family 3 waits on the scope axis.

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

1. Re-run the six storage gates serially against committed HEAD once the peer lane
   holding the `_app_live.py` / `_overview_evidence.py` fix commits, and record the
   result. Do not declare closure while a campaign-owned gate is red at HEAD.
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
5. Declare Families 1 and 2 of the enumeration — 15 names, no model change needed — and
   open the ruling Family 4 requires *before* anyone attempts to declare a filename
   template, because `StorageLocation` cannot express one and a declarer who discovers
   that mid-sweep will either invent a field or quietly skip the family. Family 3 needs
   the run-relative scope axis first, on the `KEYSTORE_ROOT` precedent.

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
