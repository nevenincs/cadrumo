---
tags:
  - '#audit'
  - '#tree-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6e96a53c30d0b98627561a9029474f4cc5085e7276ac02917ae82c23dc22ca76'
related:
  - "[[2026-08-13-registry-suite-red-at-head-audit]]"
---

# `tree-suite-red-at-head` audit: `Tree-wide unit suite red at HEAD: attribution and root-cause clustering`

## Scope

A serial, single-worker run of the unit lane at HEAD `3241d5a173` finished
`567 failed, 24553 passed, 4440 deselected` in 1h25m. This audit triages the
**410 failures outside `domain/calculations/registry/`**; the 157 registry
failures are resolved into nine root causes by the sibling registry audit and
are excluded here except where a non-registry cluster shares their cause.

Method, applied to the captured run rather than to new runs. Every one of the
567 tracebacks was parsed into a `test id | file:line | first assertion` record
and verified 1:1 against the short summary with zero order mismatches. Each
failure was then attributed by walking **every** first-party frame in its
traceback and testing each against the 158-path dirty-file inventory. A failure
whose traceback touches no dirty file cannot be caused by uncommitted work and
is committed breakage; a failure that touches one is an upper bound on
in-flight, not proof of it.

No production code, registry TOML, test or fixture was modified. This is a
diagnosis-only record.

**Coverage, stated so this audit cannot be read as complete.** All 62 meta-gate
failures in `src/cadrumo/tests` were individually reviewed. A first pass named
twelve root causes covering roughly 170 of the 348 non-registry, non-meta
failures. A second pass over the 178 residual (159 committed, 19 possibly
in-flight) root-caused about 40 more, recorded in the last three findings below.

**Roughly 140 remain not individually root-caused.** They are attributed
committed-versus-in-flight by the frame walk, but their causes are unresolved,
and the second pass established that they are a genuine long tail rather than a
hidden cluster: the largest remaining signature is seven failures and most are
one or two. Closing them will be per-failure work. Until that runs, the tree's
failure count is explained to roughly sixty percent, not fully.

## Findings

### attribution-split | high | 375 of 410 non-registry failures are committed breakage, not in-flight churn

Walking every first-party frame of all 567 tracebacks against the dirty
inventory gives 532 CLEAN and 35 DIRTY. Restricted to the 410 non-registry
failures: **375 CLEAN, 35 DIRTY**. All 157 registry failures are CLEAN,
independently corroborating the sibling audit's committed verdict. Of the 178
distinct failing test modules in the 410, only four are themselves modified.

The 35 DIRTY are an upper bound and mostly false positives on inspection: the
10 in `src/cadrumo/application/modelo/tests/test_export_output_paths.py` and 3
in `test_export_iva_wallet.py` route through the dirty
`src/cadrumo/application/modelo/_export.py`, but their cause is a committed
registry withdrawal (see the export-withdrawal finding), not the working-copy
edit. What is lost by not separating these: a closeout can blame peer WIP for
breakage that is already merged and will survive every agent going home.
Remediation: treat 375 as the committed floor, re-attribute the 35 individually
against their own root cause rather than against frame membership.

### meta-gate-verdict | high | no meta-gate is red because a rule was weakened; every red gate still has its teeth

The 62 failures in `src/cadrumo/tests` were reviewed first. None is red because
a detector was narrowed, an assertion was loosened, or a ratchet was relaxed.
The gates are red because the tree violates them, because a fixture went stale
against a deliberate contract change, or because the scan walked filesystem
residue. The two ratchet gates that regressed did so in the honest direction:
they report growth in debt and refuse it.

This is the one verdict that most needed to be false-negative-free, so it is
stated with its method: each red gate was opened at the asserting line, its
assertion compared against the property named in its own docstring, and the
implicated source checked for dirtiness and for the commit that moved it.

### taxonomy-detector-self-test-couples-to-live-data | medium | an anti-tautology proof fails for a reason unrelated to the property it pins

`src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py:512` asserts
`{"db", "blobs", "audit"} <= set(entry.used)` and fails with actual
`{'blobs', 'db'}`. The test's name and docstring claim one property: that the
scan sees a dict literal's values and a tuple literal's elements, not only a
`/`-join chain. **That property still holds** — `db` was caught as a dict value
and `blobs` as a tuple element, from the same fixture
`TABLE = {"a": "db", "b": ("blobs", "audit")}`. Only `audit` is missed, because
the vocabulary is derived at runtime from `STORAGE_TAXONOMY`
(`src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py:151`) and
`"audit"` is no longer a member of `src/cadrumo/core/_storage_taxonomy_locations.py`
(clean, token absent).

What is lost: an anti-tautology proof whose fixture is coupled to live
production data stops being a proof of the detector and becomes a second,
undeclared assertion about the taxonomy's contents. A future reader seeing it
red will conclude the detector is broken and may "fix" the detector.
Remediation: make the self-test's fixture use tokens the test itself pins
against a locally declared vocabulary, so it fails only when the walk shape
regresses; assert taxonomy membership separately if it is wanted at all.

### bucket-validation-refusal-crashes | critical | four production refusal paths raise TypeError instead of the typed localised error

`src/cadrumo/application/user_profile/_repository.py:221`, `:240`, `:245` and
`:303` all raise `BucketValidationError(translated_message=..., context=...)`.
That constructor, at
`src/cadrumo/adapters/persistence/storage/bucket/_errors.py:25`, accepts only
`message` positionally plus keyword-only `context`, and hardcodes
`translated_message` itself. Every one of those four raises therefore dies with
`TypeError: BucketValidationError.__init__() got an unexpected keyword argument
'translated_message'` **instead of raising the refusal**. Three are observed in
the capture via
`src/cadrumo/application/user_profile/tests/test_repository.py:92`; the fourth
path is simply not exercised.

Both files are clean, so this is committed. What is lost: a blank `profile_id`
or `snapshot_id` produces an unhandled `TypeError` rather than the typed,
localised, context-carrying refusal, so it never reaches the CLI error envelope
and the operator gets a stack trace instead of an instructive message. The
guard is not merely unhelpful, it is absent — the validation branch cannot
complete. Remediation: pass the detail as `message` (or add the keyword to the
constructor deliberately), and add a regression asserting the raised type is
`BucketValidationError` and that its `context` names the blank field.

### vacuous-gate-self-reported | high | a localization gate was asserting nothing and its own guard caught it

`src/cadrumo/application/user_profile/tests/test_overview_localization.py:136`
fails on `assert exempt, "no exemption resolved; the gate above would be
asserting nothing new"` with actual `frozenset()`. This is precisely the
failure mode this campaign has produced three times: a test that mirrors the
implementation and passes vacuously. Here the author anticipated it and wrote
an anti-vacuity guard, and the guard is now firing — meaning the assertion it
protects has stopped exercising anything.

What is lost: until this is resolved the paired gate provides no coverage of
the identical-by-nature exemption, and had the guard not been written the
module would still be green. Remediation: restore a real exemption to the
fixture or delete the paired assertion; do not silence the guard. Treat the
guard's presence as the pattern to copy, not the thing to remove.

### export-layout-withdrawal-fanout | high | 42 failures from one deliberate, grounded registry decision

Forty-two non-registry failures share a single cause: the filing-grade
fixed-width export layouts were withdrawn from the registry. Every Modelo 303
revision and the Modelo 200 revision carry a `support_removal_decisions`
fragment, for example
`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2025/support_removal_decisions/0001-export-layout-support-removal.toml`
and the Modelo 200 equivalent, each `decision = "remove_from_filing_grade"`,
`reason = "unsupported_official_format"`, carrying `legal_refs` and
`source_refs`, with the stated rationale that the official record design
contains producer fields lacking canonical typed producer authority and that
"retaining a partial layout would permit silent under-declaration". Committed in
`df49c5206a` (303) and `b57cebf353` (200); the registry tree is clean.

The fan-out is 13 `ModeloExportUnsupportedError`, 12 "no longer a shipped Modelo
200 export field" in
`src/cadrumo/application/filing/tests/test_export_implicit_decimal_slots.py`,
4 "revision has no exports", and 13 `IndexError: tuple index out of range` at
`src/cadrumo/application/storage/calc_sheets/tests/test_workbook_boe_consistency.py:74`,
where `provider.get_subview(modelo).export_layouts[0]` indexes an
now-empty tuple.

What is lost: the tests were not swept with the decision, so a deliberate and
well-grounded withdrawal now reads as 42 anonymous regressions, and the
`[0]`-indexing test crashes rather than reporting the withdrawal. Remediation:
sweep the affected tests to assert the withdrawal (a refusal naming the removal
decision) instead of the pre-withdrawal geometry, and replace the bare `[0]`
index with a guard that names the empty layout set.

### justificante-csv-fixture-drift | medium | 55 failures across nine modules from one grounded model constraint

`Justificante.csv` (`src/cadrumo/domain/justificante/_schema.py:33`) is pinned to
the canonical `AEAT_CSV_PATTERN` — one complete run of 8 to 32 uppercase
alphanumerics — declared at `src/cadrumo/core/_aeat_csv.py:23` and landed by
`29fa2ca07b`. Fixtures across nine modules seed hyphenated synthetic values such
as `JUST-322-A00000000`, for example at
`src/cadrumo/application/calculations/tests/_cross_period_clean_state_support.py:296`.
Every implicated file is clean, so all 55 are committed.

The code is right and deliberately so: the module docstring reasons explicitly
that a narrower local copy "silently rejects identifiers AEAT really issues, and
the artefact it refuses is filing evidence". The fixtures encode a CSV shape
AEAT never issues. What is lost: 55 red tests obscuring real signal, and a
fixture corpus that would not have caught a genuine widening of the pattern.
Remediation: re-seed the nine fixture modules with conforming synthetic CSVs and
add one negative case asserting a hyphenated value is refused.

### export-field-header-key-removed | medium | 17 failures from a test helper still passing a deleted model field

`src/cadrumo/adapters/outbound/aeat/export/tests/test_registry_record_renderer.py:60`
constructs `ExportFieldDefinition(... header_key=None ...)`. The field no longer
exists on the model (`src/cadrumo/domain/calculations/registry/_schema_surfaces.py`)
and the model is `extra="forbid"`, so every construction fails
`extra_forbidden` and takes all 17 tests in the module with it. The export
package is clean; committed. Remediation: drop `header_key` from the helper.
Note this module is the renderer's only offset/width/padding coverage, so all 17
fixed-width layout guarantees are currently unexercised.

### translated-message-prose-drift | medium | 33 refusal-matching tests pin prose that production no longer emits

Thirty-three failures are `pytest.raises(..., match=...)` misses where the
actual message is a bare translation key, for example at
`src/cadrumo/application/user_profile/tests/test_lifecycle.py:734`, expecting
`'declares no schema_version'` and receiving
`'errors.integrity.integrity_storage_envelope_version'`. This is intended
design, not a regression: `src/cadrumo/core/errors/__init__.py:140` sets
`text = message or translated_message`, and the docstring at `:111` states that
a `translated_message`-only construction deliberately carries the key as its
fallback text. Raisers migrated to key-only construction; the tests still pin
the old prose.

One member of this family is **not** settled and must not be swept with the
rest. `src/cadrumo/adapters/inbound/financial/providers/tests/test_tabular_extra_split.py`
asserts "the refusal must name the install that resolves it" and receives
`'errors.error.error_cadrumo_core'`. If the locale entry for that key does not
interpolate the `context` naming the missing extra, the operator receives a bare
"value invalid" refusal, which the architecture rule forbids. **This is not
proven wrong — I did not trace the envelope rendering to a rendered string.**
Remediation: verify by invoking that CLI path and reading the emitted envelope;
if the rendered notice omits the extra's name, that is a separate operator-facing
defect and the test is right.

### import-hygiene-ratchet-regressed | medium | test-only private reaches grew 94 to 104, all in clean files

`src/cadrumo/tests/test_import_hygiene_gate.py:354` reports `104 current > 94
documented`, and `:379` names nine undocumented sites, among them
`src/cadrumo/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py:125`
and `:126`,
`src/cadrumo/application/calculations/tests/test_row_set_assembly.py:468` and
`:505`, and
`src/cadrumo/entrypoints/cli/tests/test_ledger_filer_precondition_projection.py:8`
through `:10`. All five owning test files are clean, so the debt landed in
commits, not in working copies. What is lost: the ratchet's contract is that a
new site is added to `dev/quality/import_hygiene_test_debt.json` **in the same
commit**; ten arrived without that, so the documented set no longer describes the
tree. Remediation: for each of the nine, promote the symbol to the owning
package's facade and rewrite the import, or add a reasoned entry; prefer
promotion.

### ecb-provider-branches-on-pytest | high | HEAD~1 landed production code that gates behaviour on the test-runner opt-in

`src/cadrumo/tests/test_marker_integrity.py:1129` refuses production modules
that gate live reads on the pytest opt-in, and names exactly one violator:
`src/cadrumo/adapters/outbound/fx/_ecb_provider.py`, which at `:229` evaluates
`_pytest_is_driving_this_call() and not settings.live_tests_enabled`. The file is
clean and the token was introduced by `4b98e1dc09 fix(fx): refuse a
pytest-driven live ECB lookup without explicit opt-in` — the second-most-recent
commit on the branch.

The gate is right and the code is wrong. The safety rule sanctions
`CADRUMO_LIVE_TESTS_ENABLED` as a **test-harness** opt-in; it does not sanction
production branching on whether pytest is the caller. What is lost: production
behaviour now differs by execution context, so the path exercised under test is
not the path that runs for an operator — which is the precise condition that
makes a green suite stop being evidence. The intent behind the commit (do not
perform a live ECB lookup during tests) is legitimate; the mechanism is not.
Remediation: invert it so the provider takes its network policy from injected
configuration and the test harness supplies a refusing policy, leaving the
provider ignorant of pytest.

### environmental-residue | low | two meta-gates are red on filesystem residue and would be green on a clean checkout

`src/cadrumo/tests/test_application_verification_dead_surface.py:22` asserts
`not package.exists()` and fails, but
`src/cadrumo/application/verification` contains **zero files** — only two empty
directories git cannot track. Its sibling assertion that no source, stub or
config still names the dead module **passes**, so the deletion is genuinely
complete; only empty directories survive.

`src/cadrumo/tests/test_every_test_module_is_collectable.py:169` reports 26
uncollectable modules, every one of them under
`tmp/real-optional-overview-proof/pytest-anthropic/.../head/dev/`, a peer's
scratch extraction of the repository. `tmp/` is gitignored at `.gitignore:310`
and the gate walks it regardless.

What is lost: two red gates that carry no information about the tree, plus a
real scan-scoping defect — a gate that walks ignored directories will be red or
green according to what other agents leave lying around. Remediation: remove the
two empty directories (untracked, no tracked path involved); and make the
collectability scan honour ignore rules rather than walking the worktree
verbatim.

### mandatory-regime-composition-fanout | medium | one new fail-closed profile fact reddens two packages

`src/cadrumo/domain/deadlines/_profiles.py:329` raises
`ProfileError("iva.m303_regime_composition must be explicitly declared for
Modelo IVA")` whenever an IVA block is present but the composition is not
declared. Landed by `f644d84b32 feat(m303): close DP30301 scalar authorities`;
the file is clean. It accounts for five `application/user_profile` failures and
is the shape behind the twelve `WizardMissingFlagError` failures in
`application/wizard`, where `--quiet` runs now lack a newly mandatory flag.

This is the correct fail-closed direction and matches the project's refuse-do-not-
tolerate posture. What is lost is only that the fixture and scripted-wizard
corpora were not swept with the new requirement. Remediation: add the fact to
the profile fixtures and the `--quiet` argument sets; keep the refusal.

### filing-impact-verdict | high | no cluster is proven to produce a wrong number; the two with filing weight fail safe

Tracing the production paths rather than reading the error text: **none of the
410 is demonstrated to alter a declared figure.** The clusters with genuine
filing weight refuse rather than miscompute.

The export-layout withdrawal removes the ability to emit the Modelo 303 and
Modelo 200 fichero BOE at all. That is a **capability regression, not a
correctness regression** — the app produces no file rather than a wrong one, and
the withdrawal exists specifically to prevent a partial layout under-declaring.
The mandatory regime-composition fact and the `Justificante` CSV constraint both
tighten refusals. The `BucketValidationError` defect degrades a refusal into a
crash, which is structural.

Stated precisely, and deliberately not overclaimed: this is **not proven wrong**
rather than **proven right**. Two limits bound it. First, the 157 registry
failures are excluded here and calculation grounding lives in that surface, so a
numeric defect could sit there. Second, the 17 dead renderer tests mean the
fixed-width offset, width and padding guarantees are currently unexercised — the
absence of a failing numeric test is not evidence of numeric correctness when the
tests that would fail cannot run. The honest verdict is: no wrong number is
demonstrated, and the fixed-width numeric surface is currently unguarded.

**Amended by the second pass.** The verdict stands — still no wrong number — but
one committed defect now has demonstrated operator-facing consequence rather than
only test-suite consequence: the absent-numeric refusal below blocks a legitimate
Modelo 145 export outright. That is a capability regression in the
**over-refusing** direction. It reinforces the verdict rather than weakening it:
every filing-weighted defect found in this triage refuses, and none writes a
figure AEAT did not receive.

### absent-numeric-refuses-the-whole-record | high | an optional blank numeric slot hard-refuses a fixed-width export that should render it blank

Second-pass finding against the residual. Nine failures across the Modelo 145
communication surface share one committed production defect in the shared
fixed-width codec. At
`src/cadrumo/domain/calculations/registry/_fixed_width_codec.py:226` an absent
casilla is defaulted to the empty string:
`raw_value = field_values.get(field.casilla_id, "")`. The text branch tolerates
that — `_render_text` at `:381` returns `""` for `None` and passes any `str`
through. The numeric branches do not: `_render_integer` at `:419` calls
`_coerce_numeric`, which delegates to `coerce_fixed_width_decimal` at
`src/cadrumo/core/decimal/_fixed_width.py:31`, whose canonical-decimal regex does
not match `""`. The empty string therefore raises, and because the failure is
raised per record rather than per field, **one absent optional numeric casilla
refuses the entire export record**. Observed as
`export field 'modelo-145-dr-16-descendiente-1-anio-nacimiento' has an invalid
numeric value` — the birth year of a descendant a taxpayer may simply not have.

All three implicated files are clean, so this is committed. The code is wrong and
the tests are right to fail: the export contract holds that optional
operator-input casillas the taxpayer legitimately lacks are not required and a
blank slot is a valid absence, so refusing them contradicts the very rule the
completeness gate is written against. What is lost: a Modelo 145 communication
cannot be exported at all for the ordinary case of a taxpayer without
descendants or ascendants, and because the codec is shared, every other
fixed-width modelo carrying an optional numeric slot is exposed to the same
refusal.

Direction matters here and cuts against the usual worry. This is an
**over-refusal**, not an under-declaration — the surface this project's gates
mostly watch is the opposite one. Remediation: give the numeric render paths the
same absent-value handling the text path already has, rendering a blank or
zero-padded slot per the field's declared padding, and add a regression that
exports a record with an optional numeric casilla omitted. Do not fix it by
seeding a placeholder value upstream; that would write a number AEAT did not
receive.

### preempted-guard-shape | medium | a recurring shape where an earlier refusal fires first and the guard under test is never reached

Three residual clusters share one shape rather than one cause: the test drives a
path expecting to reach a specific guard, and a newly-earlier precondition
refuses first, so the guard the test exists to prove is never exercised. Eight
failures at `src/cadrumo/application/auth/_sessions.py:682`
(`clave_route_missing`) preempt
`src/cadrumo/application/auth/tests/test_blank_profile_identity_refusal.py:110`,
whose stated purpose is proving no provider binds a session against a blank
profile identity. Six at
`src/cadrumo/application/modelo/_amendment_actions.py:145`
(`AmendmentEvidenceMissingError`) preempt the rectificativa-kind refusal asserted
at `src/cadrumo/application/modelo/tests/test_amend_kind_resolution.py:236`. Six
at `src/cadrumo/application/flows/_scripted.py:115`
(`scripted_answer_rejected`) preempt the descendant-door lifecycle assertions.

Attribution differs across the three and must not be collapsed:
`_sessions.py` and `_scripted.py` are clean, so those fourteen are committed;
`_amendment_actions.py` is **dirty**, so those six are plausibly in-flight peer
work and should not be counted as committed breakage.

What is lost is subtler than a red test. Each of these guards may still be
correct, but none of them is currently *proven* — the assertion that would catch
a regression in the blank-identity refusal cannot run, and a red test is
indistinguishable from a removed one at the level of coverage. This is the same
family as the vacuous-gate finding above, in its honest form: here the tests fail
loudly rather than passing empty. Remediation: for each, satisfy the newly-earlier
precondition in the fixture so the intended guard is reached again, rather than
re-pointing the assertion at the preempting error — the latter silently converts
a security or lifecycle test into a configuration test.

### residual-coverage | medium | the second pass closed roughly a quarter of the residual; the remainder is a genuine long tail

The 178 failures left unexplained by the first pass split 159 committed and 19
possibly in-flight by the same frame walk. The second pass root-caused about 40
of them across the two findings above. The remainder is a true long tail rather
than a hidden cluster: after removing the named causes, the largest remaining
signature accounts for seven failures and most account for one or two, spread
across `application/modelo`, `user_profile`, `wizard`, `auth`, `domain/iva`,
`setup`, `filing`, `cli/_config`, `storage`, `core` and `aggregation`. That
distribution is itself the finding — there is no third large lever, so closing
the tree will be per-failure work rather than another few bulk sweeps.

## Recommendations

Order the remediation by what is silently costing coverage rather than by
failure count. First the `BucketValidationError` constructor mismatch, which is
a live production defect that four call sites can reach and no test currently
passes through successfully. Second the vacuous localization gate, because a
guard that fired is the cheapest true finding available and the pattern should be
propagated, not removed. Third the 17 renderer tests, because they are the only
coverage of fixed-width field geometry and every one of them is currently dead
behind a single stale keyword.

Sweep the three stale-fixture clusters as bulk work once the above are closed:
the 55 `Justificante` CSV fixtures, the 42 export-withdrawal assertions, and the
33 prose-matching refusal tests. Each is one mechanical change per cluster, and
each should gain one negative assertion so the swept tests would fail if the
contract widened back.

Two items need a decision rather than an edit. The ECB provider's pytest-aware
branch needs its network policy injected rather than sniffed, and that is a small
design decision about where the provider's policy comes from. The
`test_tabular_extra_split` refusal needs its rendered envelope inspected before
anyone decides whether the test or the message is wrong; if the rendered notice
omits the missing extra's name, that is a separate operator-facing defect and
should be raised as its own finding rather than swept with the prose-drift
cluster.

Finally, two hygiene items that will otherwise keep re-reddening the tree for
unrelated reasons: scope the collectability scan to ignore-respecting paths so a
peer's scratch directory cannot fail it, and decouple the taxonomy detector's
anti-tautology fixture from the live taxonomy so the proof fails only when the
detector regresses.
