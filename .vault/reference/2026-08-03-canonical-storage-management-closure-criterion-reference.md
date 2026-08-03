---
tags:
  - '#reference'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:3c55fba7a2c9e85e2f61bee67bea7db049ea22a8ed76b872b23aebfbb35c5a07'
related: []
---

# `canonical-storage-management` reference: `canonical storage management closure criterion`

Defines what "complete" means for the `canonical-storage-management` campaign, so
the honesty review has a checkable standard rather than a strength-of-momentum
judgement. Written to be read by someone who was not here, on the assumption
they will use it to try to prove the campaign incomplete.

The operator sharpened this criterion twice during the campaign. Both
sharpenings narrow scope; neither widens it. This document reflects the
current, narrowest state — read the two re-scopes below before trusting any
earlier framing ("every code site and API migrated") that may still be quoted
elsewhere in the vault.

## The criterion

The operator's own words, first cut: *"previously we didn't have a canonical
centralised settings home for declaring and interfacing with the storage via
the canonical api - if we can satisfy that all file producing sites are
enrolled we're done."*

Precisely: **every site in production code that produces a file or directory
— creates it, writes to it, moves it, or copies into it — resolves the
destination it acts on through the canonical accessor API** (`storage_path`,
`bucket_scoped_storage_path`, or a declared `ExternalPathRole` escape). Not
every reference to a path. Not every test literal. **Sites that produce files.**

**Second and currently governing re-scope, the operator's own words**: *"no,
tests are different - they create temp files that every test must clean up
after themselves."* Tests are excluded from the enrollment criterion
entirely — not merely their literals, their whole destination logic. A test's
scratch directory is not required to route through the taxonomy at all. What a
test owes instead is a different, separate standard, covered in its own
section below. Conflating the two is exactly what earlier phases of this plan
did, and it sent a lane at roughly 73 files of work that was not closure-
relevant under this criterion. This document exists partly to prevent the next
reader repeating that.

## What counts as a file-producing site (production only)

Any **production** call to: `write_bytes`, `write_text`, `open()` in a write
mode, `mkdir`, `os.makedirs`, `os.replace`, `shutil.copy*`, the `tempfile`
family used to materialise a persistent artefact (not a scratch buffer
discarded in the same function), archive writers (`zipfile`, `tarfile` write
modes), and any call into a library where this codebase hands it a destination
path or directory. Test code is out of scope for this section entirely — see
the test-hygiene standard below, not this one. Each production site classifies
into exactly one of:

- **ENROLLED** — the destination is `storage_path(category)`,
  `bucket_scoped_storage_path(category, bucket_id)`, a declared
  `StoragePathDefinition` grammar (below), or an explicitly declared escape,
  with no further unaccounted segment appended.
- **NESTED-UNGOVERNED** — the site starts from an enrolled category's resolved
  path but appends one or more segments the taxonomy never declared as their
  own member or grammar. R5 of the ADR requires these segments to be governed
  too; no gate currently enforces that requirement.
- **OPERATOR-DIRECTED** — the operator supplies the destination at the point of
  use (e.g. an export target the operator names on the command line). Not a
  taxonomy violation by construction — the application does not choose the
  location.
- **AD-HOC** — anything else: a literal, a module-local constant, a derived
  path with no traceable link to the taxonomy at all.

**A third declaration mechanism landed mid-campaign, and it resolved three of
the four families below faster than authoring plan Steps could keep up.**
`StoragePathDefinition`/`STORAGE_PATH_DEFINITIONS` (commit `3a6ce7475d`,
"extract the filesystem path-hierarchy contracts into a sibling module")
declares a `grammar` string with placeholders for **parameterised fan-out
shapes that cannot be enumerable `StorageCategory` members** — a content-hash
prefix, an outbound namespace, a per-run id — verified by a conformance test
that drives a real write through the real production path and asserts the
real resulting path matches a regex derived from the grammar, never the
grammar compared against itself. **A data-derived segment (a content digest,
a run id) is not "excluded" from governance** — declaring it as a taxonomy
*member* would be a category error, since you cannot enumerate members per
hash, but the grammar mechanism governs the *shape* with the data-derived
part as a bounded placeholder. This is a third disposition, distinct from
ENROLLED-by-membership and from an escape.

**Two censuses landed and were then superseded by a third, more complete
one.** An earlier version of this document called the census "commissioned
but had not landed" — stale. A static write-call sweep (`S102`) and a
runtime instrumented-suite sweep (`S103`) landed first; a fresh-context
honesty review then ran a third pass — taint propagation from every
taxonomy root through local assignments, `self` attributes, and function
returns to a fixed point, rather than matching a fixed expression shape —
and it is the authoritative number, because it measured why the first two
undercount: of the appended segments found, only 19 of 34 are plain
literals; 10 are module constants, 5 are f-strings, 7 are fully dynamic
expressions the shape-matching passes cannot see at all.

**Result: 34 undeclared compositions across 14 modules, reducing to 23
distinct application-chosen names once repeated sites collapse** (one
candidate, a `run_id` segment in `workflow/_persistence.py`, was excluded as
data-derived on individual verification — the same exclusion this document
applies throughout). Grouped by declarable shape, tracked as plan Steps, with
three of the four families **already closed by the grammar mechanism**:

- **Blob-store hash-prefix fan-out** (`S86`, **done**): `blob_content_plaintext`/`blob_content_ciphertext`
  grammars, gated by `test_blob_content_shape_conformance.py`.
- **Local storage provider namespace fan-out** (`S87`, **done**):
  `local_provider_object`/`local_provider_object_sidecar` grammars, gated by
  `test_local_provider_object_shape_conformance.py`.
- **Family 3 — instance-scoped file leaves** (3 names, `S88`, **done**):
  `run_trace`/`run_events`/`run_envelope` grammars beneath `runs/<run_id>/`,
  gated by `test_run_trace_shape_conformance.py`. The originally-proposed
  `RUN_RELATIVE` scope axis (precedented by R13's
  `KEYSTORE_RELATIVE`/`KEYSTORE_ROOT`) was withdrawn once the grammar
  mechanism was found to already cover the shape — both the original
  recommendation and its retraction were verified against landed code before
  either was trusted.
- **Family 1 — fixed file leaves directly under a declared category** (8
  names, 14 sites, `S89`, **closed**): the secret store's five files
  (`SECRETS_MASTER_KEY`, `SECRETS_MASTER_KDF`, `SECRETS_MASTER_LOCK`,
  `SECRETS_KEYRING_LOCK`, `SECRETS_MASTER_RECOVERY_KEY`) plus the three
  cache/log files (`LOG_FILE`, `CORPUS_TEXT_CACHE_FILE`,
  `CORPUS_SEARCH_INDEX`) are declared `StorageCategory` members, confirmed
  present at pinned HEAD `b6287cd8f5`. Declared as direct taxonomy members
  rather than `StoragePathDefinition` grammars (the mechanism `S89`'s Step
  text originally named) — `SECRETS` is `OPERATOR_OVERRIDABLE`, so composing
  root+subpath through the grammar mechanism would silently disagree with a
  real operator override; the five secret files stay resolved through their
  own settings field, cross-referencing only the bare filename. `secret_index`
  remains the one member of this family that genuinely uses the grammar
  mechanism, since its parent (`secrets/`) does not carry the same
  override-policy hazard for that specific file.
- **Family 2 — fixed subdirectories under a declared category** (7 names, 7
  sites, `S90`/`S91`, **closed**): all seven members, plus the intermediate
  `audit/live` parent (`AUDIT_LIVE`) itself, are declared and confirmed
  consumed — not merely declared — at pinned HEAD `b6287cd8f5`:
  `application/live/_iva_remote_state.py` resolves `AUDIT_LIVE`,
  `AUDIT_LIVE_IVA_WALLET`, `AUDIT_LIVE_IVA_REMOTE_STATE`,
  `AUDIT_LIVE_IVA_REMOTE_STATE_FILED_HISTORY`, and
  `AUDIT_LIVE_IVA_REMOTE_STATE_WALLET` through the accessor rather than a
  literal, and `adapters/persistence/storage/_rotation.py` does the same for
  `SUBMISSIONS_AMENDMENT_RESULTS`, `SUBMISSIONS_AMENDMENTS`, and
  `ATTACHMENTS_MANIFESTS`. Plain membership, not `StoragePathDefinition` —
  correct, since none of these segments is data-derived.
- **Family 4 — filename templates** (5 patterns, `S107`, **closed**):
  `llm_usage_record`, `llm_run_telemetry_record`, `auth_acquisition_lock`,
  `validation_verdict_cache_entry`, and `llm_cache_entry` are all declared as
  `StoragePathDefinition` grammars, confirmed at pinned HEAD `b6287cd8f5`. The
  open question this family originally posed — does the model need a new
  field, or does an ADR ruling need to state instance-keyed files are
  governed by their directory alone — was answered by the same evidence that
  closed `S86`–`S88`: the grammar mechanism already handles a parameterised
  filename with no model change and no ruling, and the five grammars are now
  declared, not merely confirmed declarable.

**Reclaim-reachability, corrected on the fuller set.** An earlier pass found
no nested-ungoverned site reachable by `reclaim`. On the full 34-site set that
is wrong: 11 sit under a reclaimable parent (`runs`, `llm-cache`,
`llm-run-telemetry`, `llm-usage`, `logs`). In every one, deletion is the
intended behaviour — regenerable traces, caches, and telemetry — so the
conclusion (no undeclared nesting sits where deletion would be wrong)
survives, but on the merits of what happens to be declared today, asserted by
nothing. `S106` tracks the containment-proof gap this depends on.

**Why a complete static enumeration is not achievable, stated rather than
assumed away.** Cross-module composition (a helper returns a tainted
directory, a different module appends to it), library-named files, and
container-mediated flow (a tainted path stored in a dict/dataclass/list and
read back elsewhere) are all invisible to single-module taint analysis. **Of
roughly 99 production filesystem-mutating call sites** (corrected from an
earlier "267" — that count matched every `.replace(...)` attribute call as
`Path.replace`, so an ordinary `str.replace(old, new)` scored as a filesystem
rename; the arity discriminator, `Path.replace` takes one argument and
`str.replace` two, removes 166 false positives), **about 96 receive their
destination from a parameter, call, or attribute rather than constructing it
locally** — the ratio (95%, against 97% first reported) is essentially
unchanged, so the qualitative conclusion survives the correction, but the
absolute number changes what's actionable: at 267 sites exhaustive manual
review was not a serious proposal; at about 100 it is an afternoon's work,
closing the cross-module class completely rather than only bounding it
statistically. The tightest defensible bound still comes from combining
static taint (misses runtime values, sees every site regardless of test
coverage) with runtime observation (misses unexercised code, sees the actual
resolved string with no expression-shape blind spot) — their blind spots are
complementary, not overlapping, so their union, not either alone, is the
closest approach to a non-undercounting method, and now a tractable one.

## What the criterion deliberately excludes — stated so nobody widens it back in

**Test code is not in scope for the enrollment criterion at all**, per the
second re-scope above — not "test literals are a lesser priority," but
excluded outright. A test's temp/scratch directory does not need to resolve
through `storage_path`. What a test owes is cleanup, not enrollment; see the
next section.

**Operator-directed outputs are not file-producing sites in the sense that
matters here.** The operator names the destination on purpose; the application
does not choose it. `cadrumo_wallet_diagnostic_dump_dir`
(`OPERATOR_DIRECTED_OUTPUT`) is the shipped example.

**Bundled read-only package resources are not file-producing sites.** The
application never writes to `aeat_manuals_root`, `aeat_normatives_root`, or
`cadrumo_iva_catalogue_root` — it only reads from them.

The six currently declared `ExternalPathRole` escapes, verified at HEAD
(`EXTERNAL_PATH_SETTINGS_FIELDS` in `_storage_taxonomy.py`):

| settings field | role |
| --- | --- |
| `aeat_manuals_root` | `BUNDLED_RESOURCE` |
| `aeat_normatives_root` | `BUNDLED_RESOURCE` |
| `cadrumo_iva_catalogue_root` | `BUNDLED_RESOURCE` |
| `cadrumo_certificate_path` | `OPERATOR_INPUT` |
| `cadrumo_libreoffice_executable` | `EXTERNAL_EXECUTABLE` |
| `cadrumo_wallet_diagnostic_dump_dir` | `OPERATOR_DIRECTED_OUTPUT` |

Note for precision: the `ExternalPathRole` enum itself declares five members
(a `THIRD_PARTY_CACHE` role exists and is pinned by a closed-set test, but has
zero field users today — the Playwright browser-binaries escape this role was
written for is still an open Step, not yet declared). "Six declared escapes"
is a count of fields, drawn from five possible roles; a skeptic checking this
table against the enum definition should not read the mismatch as an error.

## Test hygiene — a separate standard, with its own evidence, not a closure blocker

This is a genuinely different requirement from enrollment, and the two must
not be re-merged. **The standard: nothing a test creates should survive the
test.** Not "nothing a test creates should survive outside an isolated root"
— residue inside an isolated root is still residue, and the standard is
stated without that qualification on purpose.

**Evidence is empirical, not structural**, because reading test source cannot
tell you what actually lands on disk — a helper three calls deep can leak
regardless of what the calling test looks like. Method: snapshot the
repository tree and the platform user-data root before and after a full suite
run, then diff both. A file that appears and does not disappear is a leak,
full stop, whether it sits inside an isolated root or outside one entirely.
This census has been commissioned and had not landed as of this writing.

**What this explicitly is not**: it is not the enrollment criterion, it does
not require a test to call `storage_path`, and it is not on the closure path
for "are all file-producing sites enrolled." A campaign could satisfy this
standard fully and still not meet the enrollment criterion, and vice versa.

**The bulk test-migration phases are real work, re-scoped out of the closure
path, not deleted or retired.** Re-pointing a test literal at the accessor
(`W03.P14`–`P16` of the plan, Steps `S76` "remaining tier-two isolation fixture
sites," `S77` "pins-by-design re-expression" — the six master-key/keystore
tests, now re-expressible against a correct declaration since the keystore fix
landed — and `S78` "bulk literal burndown across roughly 108 files / 350
sites") is genuine drift reduction and may be worth doing later. **It does not
block closure under this criterion**, and a reader should not read the plan's
raw completion percentage as gated on these Steps finishing. A new phase,
`W03.P23` (Steps `S84`, `S85`), carries the actual test-cleanup census and its
follow-up fixes — separate from the migration Steps, because cleanup and
enrollment are separate questions even within the test surface.

**A consequence worth stating plainly rather than leaving to discovery: the
plan's completion percentage will read as higher, going forward, partly
because work moved out of the closure path rather than because it got done.**
S76, S77, and S78 together represent the single largest remaining body of
work in this plan by file count. Under the original "every code site and API
migrated" framing they were closure-blocking; under the current criterion they
are not. Closing them still raises the plan's raw checked-Step percentage as
ordinary progress, which is legitimate — but a reader assessing "how close to
closure" should discount them from that question entirely, both now and if
they later show as closed. A percentage that improves because the target moved
is exactly the kind of thing a closure review should be told about rather than
left to infer from a checked box.

## The four existing censuses are proxies, not the criterion — and they do not sum

Each measures a different, narrower property. None of them, singly or
combined, answers "are all production file-producing sites enrolled."

| Mechanism | What it actually measures | Scope |
| --- | --- | --- |
| Provenance gate (`test_storage_provenance_gate.py`) | Joins onto the storage root outside a declared producer | Production and tests, but only sites that literally join onto `cadrumo_local_storage_root` — not sites that join onto an already-resolved category path |
| Settings-lifecycle gate | Hardcoded taxonomy-governed literal names | Production modules only |
| Binding gate | Every `Path`-typed `Settings` field bound to a member or a declared escape | Settings fields only — a bare literal appended in a function body, never assigned to a settings field, is invisible to it |
| Test-override-kwargs migration inventory (`W03.P16`) | Test fixtures/overrides re-pointed to the accessor | Test-only, not closure-relevant under the current criterion (see above), and its own count is unreconciled (below) |

**None of the four can see a NESTED-UNGOVERNED site.** The provenance gate
only fires on a join onto the root itself; once a site has legitimately
resolved `storage_path(StorageCategory.AUDIT)`, anything appended after that
is outside what the gate watches. The binding gate only watches `Settings`
fields. The lifecycle gate watches production literals against a name list,
not structural nesting. This is exactly why the direct write-call census above
is necessary rather than an aggregation of what already exists.

### Confirmed NESTED-UNGOVERNED sites (nine, across nine modules, not caught by any existing gate)

**Superseded by the fuller breakdown above** ("What counts as a file-producing
site" — the 23-name/34-site/14-module taint-based enumeration and its four
families). This subsection originally listed nine modules found by an earlier,
shape-matching pass; kept here only as a pointer so a reader following an old
link lands somewhere, not duplicated, since two different site counts in one
document is exactly the kind of drift this document exists to prevent.

### The test-migration inventory number is unreconciled — do not cite any single figure as authoritative

Not a closure question under the current criterion, but cited often enough
elsewhere that a skeptic will ask. Three different counts exist and disagree,
and the provenance gap is itself worth recording precisely.

- **"~108 files / ~350 hand-rolled sites"** — the plan/ADR-of-record figure
  (`W03.P16` Step text; ADR R15 "roughly 350+ call sites"), the only one of
  the three actually committed to `.vault/`.
- **The coordinator's shard-dispatch figures** — real, but living in
  `storage-root-ledger/04-tests-tooling.md` and `11-bulk-shard-briefs.md`
  under a session scratchpad directory (`C:\Users\hello\AppData\Local\Temp\claude\...\scratchpad\`),
  **not `.vault/`, and not durable** — the directory is session-ephemeral and
  unverified against committed HEAD. The shard-brief table there reads:
  targets 73 files / 246 sites, carve-out (gates, not migration work) 9 files
  / 55 sites, blocked (`master_key/tests/`, pending the keystore-scope fix
  that has since landed) 4 files / 21 sites, leaving 61 files / 169 sites as
  actual dispatched work (34 files / 79 sites mechanical, 27 files / 90 sites
  judgement). 73 + 9 = 82 files, which is very likely the source of the
  "82 files" figure cited in coordination, though the sites arithmetic does
  not reduce cleanly to "281" from these tables as given — another reason not
  to cite a single number from this source without re-deriving it. The
  ledger's own nine-file carve-out list is real and is reproduced in the
  honesty-review section below.
- **A fresh measurement taken for this document**: `rg -l
  "override_settings\("` across `src/cadrumo` test files returns 204 files /
  591 occurrences (scoped to `test_*.py`/`*_test.py`); unscoped across all
  `.py` files, 232 files / 634 occurrences. This was run against the working
  tree at time of writing, which carries uncommitted peer WIP, not committed
  HEAD — re-measure against HEAD before citing.

The three numbers likely differ by methodology (call sites vs. individual
overridden fields vs. raw pattern occurrences) as much as by drift over time.
A skeptic citing any one of these three figures as settled fact should be
corrected, not agreed with — but per the re-scope above, none of them bear on
whether the campaign is closed.

**The test-surface census has no durable home, and that absence is itself a
finding.** Real dispatch decisions were made from the scratchpad ledger's
numbers, and the only record of the methodology behind them lives in a
directory that disappears with the session. Nothing in this document should
be read as blaming that choice — the same ledgers record real, careful work
(the nine-file carve-out prohibition, the pins-by-design classification
table) — but a future reader who goes looking for the test-surface inventory
in `.vault/` will not find it, and should not conclude it was never done.

## Falsifiability — what a skeptic should run, not just what we already ran

If the answer to "how would you catch a site our census missed" is "re-run our
own census," the census is circular. Three shapes the static write-call
enumeration cannot see, named so the gap is explicit rather than assumed away:

1. **Dynamic destinations** — a path built at runtime from data the AST cannot
   resolve statically (a taxpayer id, a computed suffix). The census can flag
   the call site but cannot verify what it resolves to without running it.
2. **Paths assembled across function boundaries** — a helper returns a bare
   directory; a caller two modules away appends a literal segment before
   writing. A single-function AST walk does not see the composition.
3. **Library calls where we hand a directory and the library names the file**
   — an archive or export library that receives a directory and picks its own
   filename inside it. The write call is inside a dependency this codebase
   does not control or scan.

A stronger falsification method than a second static census: a runtime
containment check — instrument `open`/`Path.write_*`/`os.replace` for the
duration of a full test-suite or a scripted live-flow run, and assert every
actual destination resolves under a taxonomy-declared root or a declared
escape. This catches all three shapes above because it observes the resolved
path, not the source expression that produced it. It has not been run. A
skeptic proving the campaign incomplete should reach for this before trusting
any static census, including the commissioned one. The test-cleanup snapshot-
diff method above is a variant of this same instinct — observe what actually
happened on disk — applied to a different question.

### What a passing runtime check would and would not prove

This is now commissioned and merged with the test-cleanup census into one
measurement (instrumenting the same suite run answers both "where did
production writes land" and "what did tests leave behind"), so its limit
belongs here before results arrive, not after.

**It would prove**: every destination actually written to during the
instrumented run resolved under a taxonomy-declared root or a declared
escape, for the code paths the run actually exercised.

**It would not prove**: that every production file-producing site is
enrolled. **It only covers paths the suite actually exercises.** A
file-producing branch with no test coverage — an error-handling path, a rare
configuration combination, a feature gated behind a flag the suite never
flips — writes nothing during the run and is invisible to this method,
exactly as it would be invisible to code coverage for the same reason. A
clean runtime-check result is evidence of no violation *on the exercised
paths*, not a proof of universal enrollment. It should be read alongside the
static write-call census (which sees every call site regardless of whether a
test reaches it, at the cost of not knowing what a dynamic destination
resolves to) rather than in place of it — the two methods have complementary
blind spots, static misses runtime values, runtime misses uncovered code, and
neither alone closes the criterion.

## What the honesty review should independently check — known-fragile spots

Per `aeat-campaign-close-honesty-review`, the reviewer needs fresh context, so
this section names where the bodies are likely buried rather than presenting a
clean face.

- **The criterion itself was re-scoped twice during execution, most recently
  to exclude tests entirely.** A reviewer working from an earlier framing of
  "done" (documents, chat history, an earlier version of this reference) will
  reach a different, wrong verdict. Confirm which criterion version a source
  is using before trusting its completion claim.
- **Two unaccountable-checkbox incidents.** Plan Steps `S42` and `S54` flipped
  to `checked` mid-session with no exec record and no action from the plan's
  sole writer. Both were independently verified genuinely done before being
  recorded. The pattern occurred twice in one session; check for a third rather
  than assuming it stopped.
- **Seventeen exec records were checked-complete with empty required sections**
  since the campaign's earliest reconciliation pass (`W01.P01` S01–S07,
  `W01.P02` S08/S09/S11–S16, `W01.P03` S18/S19). All were backfilled from the
  actual landing commits, and three genuine divergences between what the Step
  claimed and what actually shipped were surfaced rather than smoothed over
  (S02's fifth `ExternalPathRole` role shipped from the first commit, not a
  later correction as the ADR narrative implies; S07's export uses an eager
  import where the Step text claims the deferred-attribute pattern; S18's gate
  is structural-only, proving absence of a settings field rather than a
  behavioural refusal). A reviewer should independently re-check a sample
  rather than trust the backfill at face value.
- **The `FIXED`-override guarantee (R10) is enforced by absence, not by a
  guard**, and is still open. The taxonomy model permits a `FIXED` member to
  carry a `settings_field`; nothing refuses that combination today. `S83` tracks
  a declaration-time validator; it is not built. This is a live gap, not a
  historical one.
- **The keystore-scope defect is the sharpest worked example in this campaign
  of what a green suite can hide.** The taxonomy's scoped accessor resolved a
  bucket's keystore nested under `buckets/<id>/keystore/`, contradicting
  `validate_keystore_separation`'s requirement of a sibling `keystore/<id>/` —
  and an earlier revision of the accessor's own test pinned the wrong nested
  shape as its expected value, making a real security-boundary defect read as
  a passing, well-tested feature. Found on ADR review, fixed the same
  execution day, with a corrected test and a positive control that the
  separation validator still refuses a nested path. Its two consumers
  (`bucket_paths`, `keystore_path` in `_layout.py`/`_keystore_paths.py`) have
  not yet been re-pointed onto the corrected accessor (`S20`, `S21`, open) —
  the fix is real but not yet fully consumed.
- **The provenance gate's own scope is narrower than its ADR ruling first
  claimed** (R9, amended): it proves join-production, not universal
  readership, and does not cover a name hardcoded in a test at all — that is a
  different gate's job, and the two do not overlap. A reviewer reading "the
  provenance gate is green" as "storage access is fully governed" is reading
  more into it than the gate asserts.
- **The "nine carve-out files" figure exists and is real — correcting an
  earlier version of this document, which reported it unsubstantiated after
  searching only `.vault/`.** It lives in the session scratchpad ledger
  `storage-root-ledger/11-bulk-shard-briefs.md`, not in `.vault/`, under an
  explicit prohibition, quoted verbatim because it is the single most
  dangerous instruction in the whole bulk-migration bundle — migrating those
  nine would convert sixty sites of *gate* into the taxonomy agreeing with
  itself, green, with nothing left to catch it: *"You must not migrate, edit,
  or 'tidy' any of these, and you must not touch a tenth file you decide
  looks similar. If your list above and this list ever disagree, this list
  wins."*
  `core/tests/test_output_dir_state_root.py`,
  `core/tests/test_storage_taxonomy.py`,
  `core/tests/test_storage_liveness_gate.py`,
  `core/tests/test_storage_fingerprint_participation_gate.py`,
  `core/tests/test_storage_default_parity.py`,
  `core/tests/test_config_state_root.py`, `core/tests/test_config_override.py`,
  `tests/test_storage_scope.py`, `tests/test_config.py` (all under
  `src/cadrumo/`). These are the oracles and gates for the taxonomy; their
  literals are the independent check, and re-pointing any of them at the
  accessor would make the taxonomy assert against itself while the suite
  stayed green. A prior verification pass searched only `.vault/`, found
  nothing, and reported the figure unsubstantiated — correct given where it
  looked, wrong about whether the underlying work existed. The lesson for a
  reviewer: an absence from `.vault/` is evidence the record isn't durable,
  not evidence the work wasn't done.

- **A checked Step in this campaign has, three times, not corresponded to
  landed code** (`S42`, `S54` — both unaccountable-checkbox flips, verified
  genuinely done; `S24` — checked, then found genuinely not done). Treat plan
  Step state as a claim requiring verification against HEAD, not as evidence.
  This is a stated reliability limit on the plan itself, not a one-off.

- **A self-duplication audit found the campaign shipped three new duplicate
  authorities while removing four** (`021c3bae46`, "the campaign did not meet
  its own standard, and the gap is not a technicality"): a `<root>` grammar
  token meaning two different directories across one declaration table (the
  blob-store grammars anchor at `root_dir`, sixteen others mean the storage
  root — `S111`), a Windows worst-case path-length constant disagreeing with
  its own campaign's grammar by 19 characters with the anti-tautology test
  reproducing the omission (`S26`, reworded, was a trap as originally
  written), and a file-versus-directory enum now declared in two layers with
  nothing relating them (`S112`). Plus a compatibility re-export bridge the
  project's own relocation rule forbids, shipped deliberately with a comment
  explaining why (`S113`).
- **The pattern is narrower than "the campaign duplicated things" and is
  the campaign's own lesson turned on itself: twice it chose to pin a
  duplicate rather than eliminate it**, and in the grammar case the pin is
  what created the trap — a gate that asserts two spellings agree is a
  weaker guarantee than one spelling, and it costs a reader more than the
  duplication it was meant to catch. The audit's own remedy is demonstrated
  two lines away in the same file: `segment=` interpolates
  `storage_location(...).subpath` while `grammar` hand-types the same name
  (`S114`, optional, lower priority — the gate holds today for the
  storage-root-anchored entries).
- **A closed finding does not mean re-verification stops.** `R16`'s excluded-
  member count was amended a third time by this same audit, and the audit
  identified why the first two corrections didn't hold: the ruling conflated
  excluded taxonomy *members* with excluded settings *fields*, two different
  cardinalities by construction. Restated in the ADR with both counts and
  the structural reason they can diverge again, rather than a fourth single
  number.

## Bottom line for closure

**The closure criterion is not met.** This is a settled verdict now, not a
pending measurement, and it is established three independent ways — the
weakest of which alone would already be sufficient.

1. **Two of this campaign's own gates are red at committed HEAD, and got worse
on re-measurement.** `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference`
and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`
both fail at HEAD, serial and single-SHA — neither the parallelism nor the
moving-tree caveat above applies. Cause: five production literals in
`entrypoints/cli/_app_live.py` and `_overview_evidence.py` naming
taxonomy-governed locations directly, and ten bucket/keystore
`consumer_module` claims still naming `_namespace_registry.py` after the
path-hierarchy extraction moved their real consumers to a sibling module
(R10's own core-ward migration reporting its consumption unbacked). A peer
lane holds the literal fix uncommitted; re-measured fifteen commits later the
liveness gate's unbacked-claim count rose from 3 to 13, the opposite direction
from what a closure narrative would need. **This is the cheapest and most
urgent evidence: it needs no census, just running the gates.** `S104` tracks
the fix.
2. **The cheapest possible refutation among the plan's own open Steps.**
`S51`, `S52`, `S53` still read `load_settings().cadrumo_*_cache_dir` directly
at their cited file:lines. `S24`, checked complete until this review, is not:
`core/_bucket_pointer_io.py`'s `pointer_path()` still builds the path from a
bare local constant. Unchecked and corrected as part of this pass.
3. **34 confirmed NESTED-UNGOVERNED sites across 14 modules at the time the
census ran** (detailed above), found by a taint-based census that measured
its own predecessors' undercounting rather than assuming completeness, none
caught by any of the four proxy gates. All four families have since closed:
Family 3 (3 names, `S88`) via a grammar mechanism that landed independently
mid-campaign; blob-store and local-provider fan-out, found separately before
the census ran, closed the same way (`S86`, `S87`); Family 1 (8 names/14
sites, `S89`), Family 2 (7 names/7 sites, `S90`/`S91`), and Family 4 (5
names, `S107`) all confirmed declared and consumed at pinned HEAD
`b6287cd8f5` — none of this census's named families remain open. An earlier
version of this line, reconciled after `S89` had already closed but before
`S90`/`S91`/`S107` were re-checked against a fresh HEAD, understated this by
counting Family 1 as still open; corrected in the same pass that closed the
other two.

Closure under this criterion is reached when: the two red gates pass at a
fresh HEAD measurement (`S104`); `S51`–`S53` and `S24` are re-pointed onto the
accessor; the four families in `S86`–`S91`/`S107` are each declared, ruled, or
explicitly excluded with a stated reason; the five settings-defaults
contradicting the taxonomy are corrected (`S105`); and the properly-bounded
enumeration's own stated residual (cross-module composition, library-named
files, container-mediated flow) is closed by manual review of the
corrected ~99 static write sites (an afternoon's work at the real count,
not the statistical bound "267" would have required), checked against what
the runtime census actually exercised. `W02.P07`/`W02.P08`
(`S93`–`S100`, the effective-storage-root and optional-root-resolver
convergence) are real drift, judged separately, and worth resolving before
declaring the tree fully governed — not confirmed to gate closure the way the
above does. Not when the four proxy gates are green in isolation, not when
the test-migration or test-cleanup phases finish (both out of scope for this
criterion), and not when the plan's Step-completion percentage crosses a
round number.

## A methodological caveat on full-tree suite results, applying to every green claim this campaign has cited

Two independent lanes in this shared worktree hit the same failure mode
within one session, from different directions, and it bears on any "the tree
is green" statement anywhere in this closure record, not only storage work.

**Parallel runs on a loaded machine produce false failures.** A full-tree run
under `-n 4` on a box carrying 130+ Python processes reported 21 failed / 18631
passed. Serial re-run at the same HEAD showed 13 of the 21 were phantom: the
`test_config_reset_recovery` / `test_config_reset_repository` cluster passes
13/13 serially, and only raced and timed out under parallel contention. One
earlier lane lost its failure names entirely to a crashed xdist worker;
this run instead produced misleading names that looked like real failures.

**A long full-tree run against a tree receiving concurrent commits measures
no single state.** The run above took 62 minutes in a worktree other lanes
were actively landing commits into throughout. 2 more of the 21 (`test_factory`,
`test_cross_module_imports_resolve`) now pass at the HEAD current when the
results were read, not because anything was fixed during the run, but because
HEAD moved past whatever made them fail at the run's start.

Net triage of the 21: 13 phantom (parallel-race), 2 resolved by HEAD moving
during the run, 1 real and campaign-caused (the enrollment gate correctly
refusing three newly-declared observability formats — `run_envelope`,
`run_events`, `run_trace` — that only just became visible to it; routed), 5
remaining under serial verification as of this writing.

**The general rule for reading any full-tree result cited in this or any
other closure record**: attach both caveats — parallelism can manufacture a
failure that serial re-run erases, and a long run against a moving tree
measures an average of states that never coexisted, not one true snapshot.
Neither caveat means "ignore the number"; both mean a raw pass/fail count from
a parallel or long-duration run is weaker evidence than the same count from a
serial run pinned to one committed SHA, and should be presented as such rather
than as an unqualified "the tree is green."
