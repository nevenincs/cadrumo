---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:45f154f1aadb25e443597380343847b2f61207f307d0d1885c2c2ac08a558f14'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `registry-campaign-sequencing` audit: `Gate-loosening sweep of today's working tree`

## Scope

The complete uncommitted working-tree diff at HEAD on 2026-08-14 (204 changed
paths: 134 modified, 10 double-modified, 55 untracked, 4 deleted, 1 staged
added), swept for the six loosening shapes named in the assignment: relaxed
assertions, extended allowlists/baselines, added skip/xfail/try-except
guards, filing-subject tests reclassified to a lower grade tier, softened
refusal messages, and deleted tests whose coverage did not move. Method:
`git diff`/`git status` on every changed path, systematic pattern greps
across the full tracked-file diff for each loosening shape, then a manual
read of every hit and every production (non-test) file's diff in full.
Nothing was accepted on a docstring's word alone — every claim below was
checked against the actual diff content, and several files' diffs (the
production/non-test cluster, the Modelo 303 census file, every deleted or
newly added test) were read in their entirety rather than sampled.

## Findings

### Gate-loosening sweep of today's working tree | critical | AMENDS the verdict below: a detection gap, not a wrong verdict — three call-swaps to a differently-named sibling, missed by every pattern this sweep searched for

Team-lead independently flagged two changes another agent had self-reported
hours before this sweep ran, neither of which appears anywhere below. Both
are real, both are in today's work, and neither is a syntactic pattern my
original sweep could have caught, for two compounding reasons:

**Reason one — scope.** My original sweep scoped itself to "the uncommitted
working tree," following the assignment's own framing that nothing was
committed today. That framing was stale by the time I ran the sweep: both
flagged changes are committed (`8e7c1fe93d`, `2026-08-14 20:47:06`, and
`a16b0b8ffd`, `2026-08-14 20:44:16`), and a broader check found a third
instance of the same pattern in an earlier commit
(`fd8f0d1322`, `2026-08-14 10:21:14`). I did not re-verify the "nothing is
committed" premise against `git log --since` before scoping the sweep to
the working tree alone, and should have.

**Reason two — pattern shape.** All three are single-line call-site swaps
to a differently-named function from the same module, with no skip, no
`try`/`except`, no removed `assert`, and no `grade=` change — the exact six
shapes this sweep's patterns searched for. The loosening lives entirely in
*which function is called*, which is invisible to a syntactic grep and only
visible by opening both functions and comparing what each one checks.

**The class, swept properly this time.** Diffed the full production-code
tree (excluding `tests/` and `dev/`) between 2026-08-13 23:57:55 (the last
commit before today) and the current state — 248 commits plus the
uncommitted tree — and wrote a script that, per diff hunk, finds identifiers
present only on removed lines and only on added lines and flags pairs that
are textually related but not identical (one contains the other, or they
share an 8+ character prefix). This produced 1598 raw candidate pairs
across the whole diff, almost all noise from busy hunks with several
unrelated identifiers in play (confirmed by spot-checking: e.g.
`_collect_snapshot_ref_ids` -> `collect_snapshot_ref_ids` reads like a
private-to-public promotion but `git log -S"def collect_snapshot_ref_ids"`
finds no such definition anywhere in history — the detector matched two
unrelated names that happened to co-occur in the same hunk). Filtering to
pairs where either name contains a review/verification-semantic keyword
(`verify`, `valid`, `check`, `grade`, `ground`, `inspect`, `snapshot`,
`filing`, `strict`, `review`, and siblings) narrowed this to 248 pairs, and
reading every one against the module boundary it crosses found exactly
three genuine instances of the class — no fourth, and no instance pointing
the other direction (a laxer function swapped IN for a stricter one at a
site that still needs the stricter one).

**The three, each read independently rather than trusted from team-lead's
ruling:**

1. `src/cadrumo/domain/iva/_grounding.py` — `verify_legal_reference` swapped
   for `verify_legal_reference_grounding` when checking an IVA rate table
   row's citations. Read both functions in `_legal.py`:
   `verify_legal_reference` is `if review_status is not OPERATOR_REVIEWED:
   raise; then verify_legal_reference_grounding(...)` — the grounding
   variant is a strict SUBSET (corpus required/forbidden-text presence,
   known-bad-citation check) that drops only the review-status gate.
   `verify_legal_reference_grounding`'s own docstring states "Production
   consumers call `verify_legal_reference`", which reads like a warning
   this call site should NOT be an exception — but tracing the actual
   consumer settles it: `legal_ref_failures` here gates
   `load_iva_rate_table()`, the EU member-state (26 jurisdictions) VAT rate
   table LOADER, consumed by the calculation engine for rate lookups, never
   by `export_draft` directly. Demanding operator review of every cited
   provision across 26 jurisdictions' VAT law before the rate table can even
   load would be a far broader gate than this campaign's filing-attestation
   scope, and the actual filing boundary (`_check_snapshot_legal_review_status`
   in `_snapshot.py`) re-verifies whatever legal refs the SELECTED filing
   snapshot's own casillas/bindings/formulas cite, independently of this
   loader. **My verdict: justified**, on the same "load is not thereby file"
   distinction the codebase's `RegistryAuthorityGrade` ladder already
   formalizes elsewhere. **Caveat originally left open here, since resolved
   by concrete trace — see the finding immediately below this one:** whether
   the SAME IVA-rate legal refs are guaranteed to also appear in a filing
   snapshot's own derived slice when a rate value actually reaches an
   exported casilla. They are, for the traced case (Spain's own rates, the
   highest-volume consumer, checked live on Modelo 390's real export layout
   and on Modelo 303's numbered casillas); a foreign-rate case is not yet
   traceable at all since its only real consumer (Modelo 369) has no export
   layout today.
2. `src/cadrumo/application/_foreign_asset_thresholds.py` — production code,
   `authority.snapshot(...)` (filing-grade) swapped for
   `authority.inspect_revision(...)` (non-filing) in
   `foreign_asset_declaration_thresholds()`, the function answering "is this
   taxpayer OBLIGED to declare Modelo 720/721 foreign assets." Read the
   full diff: the new code does not merely drop the review-status
   requirement, it also THREADS `revision_review_status` through to the
   result and adds an `is_operator_attested` property on the returned type
   — the caller can still tell whether the underlying revision is
   operator-reviewed, it is just no longer forced to refuse outright when it
   is not. **My verdict: justified**, and for a reason with real weight:
   Modelo 720 non-declaration carries statutory penalties, so an app that
   cannot answer "must I declare" — because it demands a filing-readiness
   certification for a question that is not a filing act — creates a worse
   failure than a merely-unfilable modelo: an unanswerable legal duty.
   Traced both production callers (`aggregation/_foreign_assets.py`,
   `calculations/_foreign_asset_redeclaration.py`); neither feeds
   `export_draft` or any byte-emission path with this data, both produce
   calculation/advisory output only.
3. `src/cadrumo/domain/calculations/registry/_validate.py` —
   `verify_legal_catalogue` swapped for `verify_legal_catalogue_grounding`
   inside `RegistryValidator._validate_catalogues()`, part of the core
   registry-build validation every modelo load runs. Not previously flagged
   by team-lead; found independently while sweeping the class. Read the
   introducing commit's own message in full: this commit (`fd8f0d1322`) is
   the ORIGIN of the entire typed `LegalReviewStatus` (pending/agent/operator)
   system — "Legal references gain typed review state... so filing-grade
   verification accepts only operator review instead of inferring approval
   from reviewer prose, and eligibility is checked against the
   legal-reference slice a requested snapshot selects rather than the whole
   corpus backlog." Before this commit there was no operator-review concept
   to loosen at this call site at all; the commit deliberately placed the
   new review-status requirement at the snapshot (filing) boundary rather
   than at whole-catalogue load time, matching CONTINUITY.md's own recorded
   ruling ("Refusal fires at the filing boundary, not at load... Operator
   chose this explicitly"). **My verdict: justified**, and this instance
   argues FOR the pattern's soundness rather than against it: demanding
   operator-review of the WHOLE legal catalogue at load time (633 entries,
   220 currently attested) would make the registry fail to load at all
   today, which contradicts the standing ruling that load and file are
   different claims.

**No fourth instance found**, and the two remaining candidate `.inspect_revision(`
additions in the whole diff are both accounted for above: one is the
`_foreign_asset_thresholds.py` call itself, the other is
`bundled_authority().inspect_revision(...)` inside the definition of
`bundled_revision_inspection()` — the pre-existing, already-sanctioned public
facade helper (its own docstring: "source-design inspection is not a filing
operation and must not be represented as one"), which this session's own
earlier reconciliation work called directly and is not a new site.

### Gate-loosening sweep of today's working tree | high | RESOLVES finding 1's open caveat: traced concretely — the rate-establishing provision IS independently re-verified at the filing boundary, on a live-exporting modelo, today

Team-lead asked this be chased concretely rather than reasoned about: pick
one of the 26 jurisdictions' rates, follow it to a casilla that exports, and
read whether that casilla's `legal_refs` name the rate's own provision or
only the framework article. Traced Spain's (`EUMemberState.ES`) super-reducido
and general rates specifically, since Spain is itself one of the 27 states
in the same rate table `_grounding.py` gates, not only a foreign-rate
concern, and because `_classification.py`'s `classify_iva` resolves EVERY
domestic invoice's rate tier through exactly this table
(`member_state = EUMemberState.ES; lookup_rate(member_state, tier, ...)`) —
the highest-volume real consumer, not an edge case.

**First pass, incomplete, and I want that on the record rather than smoothed
over:** checked one M303 binding
(`modelo-303-iva-repercutido-super-reducido-cuota`) and the one "semantic"
casilla it feeds (`iva.repercutido.super-reducido`) — neither cites
`ley-37-1992:art-91`, the LIVA provision that actually sets the 4%/10%/21%
rates (arts. 90/91; the binding cites only art. 88, the repercusión
MECHANISM article, a framework citation in exactly the shape the assignment
warned about). That looked like the second, bad branch.

**Reading the complete casilla file corrected it.** The same TOML file also
declares the OFFICIALLY-NUMBERED casillas (`01`, `04`, `07`, `150`–`170`,
etc.) — the ones whose `number` field is the real AEAT box and which, once
S20 lands, are what the export layout actually addresses — and EVERY one of
them carries `legal_refs = [..., "ley-37-1992:art-90", "ley-37-1992:art-91",
...]` directly. `_collect_snapshot_ref_ids` (re-read to confirm) unions
`legal_refs` across EVERY casilla declared on the revision unconditionally,
not scoped to whichever casilla a specific value happens to route through —
so as long as any numbered casilla in the revision cites art-91, that
citation enters the filing-boundary's checked set for every filing of that
revision.

**Then found the same pattern live today, not just future-M303.** Modelo
390 — one of the 7 modelos that already exports real bytes — carries the
identical structure and is checkable right now rather than only once S20
lands:
`modelos/390/revisions/2025/casillas/civa.anual.repercutido.tipo-21.base__....toml`
declares casilla `modelo-390-page-02-casilla-tipo-21-cuota` with
`legal_refs = ["ley-37-1992:art-88", "ley-37-1992:art-90",
"ley-37-1992:art-91", "rd-1624-1992:art-71", "orden-eha-3111-2009:art-1"]`
AND `export_refs = ["modelo-390-page-02-casilla-tipo-21-cuota"]` — a
casilla that is simultaneously grounded in the exact rate-setting article
and addressed by the live export layout. Both `ley-37-1992:art-90` and
`ley-37-1992:art-91` are `operator_reviewed` in the legal catalogue today
(checked directly).

**Answer to team-lead's precise question: branch one.** The relaxation is
airtight for the case traced — the rate-establishing provision is
independently re-verified at the filing boundary via the exported casilla's
own `legal_refs`, completely redundant with and independent of whatever
`_grounding.py`'s relaxed grounding-only check does for the separate
`IvaRateRecord` loader. This is not a coincidence of one lucky casilla: the
pattern (every numbered casilla in the construct citing the same backbone
framework + rate articles) repeats across dozens of casillas in both files
checked, reading as a deliberate authoring convention rather than an
accident.

**What this does NOT close, stated precisely rather than generalized to
"safe":** traced Spain's own rates on M390 (live) and M303 (once S20
lands) — the highest-volume, most consequential case, and the one
`classify_iva`'s own default-Spain branch makes structurally the most
likely to matter. Did not trace a FOREIGN (non-ES) member state's rate
citation through to an export, because none of the 7 currently
layout-capable modelos is the OSS/IOSS-specific one (Modelo 369, the actual
cross-border consumer of foreign rates in `_oss_ioss.py`) — Modelo 369 has
no export layout today, so a foreign-rate gap is very likely moot right
now, but "very likely moot because nothing exports it yet" is a narrower
claim than "verified closed," and should be re-checked the day Modelo 369
(or any other foreign-rate consumer) gains a layout.

### Gate-loosening sweep of today's working tree | info | RETIRED (see amendment above) — Verdict: zero loosenings found across a full sweep

Every one of the six loosening shapes was searched for explicitly across the
tracked-file diff (skip/xfail/pragma/TODO, removed `assert`, removed
`pytest.raises`, newly added `try`/`except`, every `grade=` opt-down, and a
`def test_` add/remove balance check), and every hit was individually
traced to its context rather than counted as a finding on the pattern alone.
Nothing found rises to a loosening. The individual clusters below record
what was checked and why each is safe, so a later reviewer does not have to
re-derive the same conclusion from a bare "clean."

This verdict is superseded by the amendment above: it was accurate against
the six syntactic shapes it searched for, over the scope it searched (the
uncommitted tree), and is retained for what it still correctly rules out —
the clusters below remain a true account of everything they cover. It was
never a complete verdict on "loosening," because a call-site swap to a
differently-named sibling is invisible to every pattern it used, and the
scope excluded work already committed earlier the same day.

### Gate-loosening sweep of today's working tree | info | Production (non-test) file cluster — all mechanical or explicitly justified, none loosens a gate

Read in full: `_cross_period_clean_state.py`, `_per_grupo_member_keys.py`,
`_autonomic_deduccion_advisory.py` + `_profile_binding.py`,
`_export_amendment_evidence.py`, `_help.py` + `_risk_table.py`,
`_orden_anual_html.py`.

- `_cross_period_clean_state.py` / `_per_grupo_member_keys.py`: a pure
  signature refactor (`RegistrySnapshot` parameter replaced with
  `ModeloRevision` + `filing_year` + `period`). No logic changed.
- `_autonomic_deduccion_advisory.py` / `_profile_binding.py`: promotes a
  private `_MADRID_AUTONOMIC_DEDUCCION_FILING_YEAR` constant to a public,
  single-owner export — this is exactly what
  `registry-temporal-coverage-plan` row `W01.P03.S37` (an authorized plan
  row, not an ad hoc change) asks for: collapsing a duplicated regulatory
  constant into one declaration.
- `_export_amendment_evidence.py`: whitespace/parenthesization only; the
  boolean condition is byte-identical in meaning before and after.
- `_help.py` / `_risk_table.py`: deletes help entries and
  `CommandRiskDeclaration(destructive=True)` rows for `config recover`,
  `config passphrase change`, and the `config recovery *` family.
  **Checked, not assumed:** grepped the entire `entrypoints/` tree for these
  command registrations — none exist. `git log` on the owning command module
  (`_custody.py`) shows the commands were removed by an **already-committed**
  commit, `7aa7aef75a "refactor(custody): retire the recovery-phrase
  surface, fail closed on keychain loss"` — a security-positive change made
  before today, not part of today's diff. Today's edit only removes now-dead
  help text and risk-table rows for commands that no longer exist; it does
  not strip a confirmation gate from a live destructive command.
- `_orden_anual_html.py`: moves the `bs4` import behind `TYPE_CHECKING` /
  local imports for load-time cost, with an explicit comment naming why
  (avoids paying import cost in the supervised key-derivation child process,
  which never parses HTML). Pure performance lazy-import, matches the
  project's own sanctioned lazy-resolution pattern; no behavior change.

### Gate-loosening sweep of today's working tree | info | Ledger test-fixture consolidation (~48 files) — homogeneous DRY refactor, no assertions touched

`src/cadrumo/application/ledger/tests/` accounts for the bulk of the diff (78
insertions, 282 deletions across 48 files). Sampled across the full spread —
pure-deletion files, net-positive-line files, and files touching real fixture
usage sites — and every sample shows the same pattern: real per-file
`isolated_runtime_profile`/`pytest.fixture` boilerplate replaced by calling
a new shared `bucket_scoped_runtime_profile_fixture` helper (backed by new
untracked support modules `_confirmation_profile_fixture.py`,
`_ledger_value_fixtures.py`). Real key provider, real SQLite, no mocks
introduced anywhere in the sample. No test assertion, `pytest.raises`, or
fixture *behavior* changed in any sampled file — only where the boilerplate
lives. Three files (`test_classify_stamps_derived_business_pct_from_operator_declared_facts`
and two siblings, outside the `ledger/` tree but the same pattern) also
correct a previously-wrong `runtime: None` type annotation to
`runtime: TestRuntimeProfile` with no other change.

### Gate-loosening sweep of today's working tree | info | Ten "MM" (staged+unstaged) files — zero net diff, not a real change

`src/cadrumo/application/aggregation/tests/_secure_objects_fixtures.py`,
`test_sectoral_hint_activity_declaration.py`, `test_source_mesh_profile_live.py`,
and seven files under `src/cadrumo/application/modelo/tests/` (advisory
tests) show `MM` status, which is the signal most worth suspecting of
back-and-forth loosening-then-hiding. Ran `git diff HEAD` against every one
of the ten individually: **all ten show zero lines of difference from
HEAD.** This is line-ending normalization noise (a CRLF warning fires on one
of them), not a content change. Nothing to review.

### Gate-loosening sweep of today's working tree | info | New `RegistryAuthorityGrade.CALCULATION` opt-downs (8 occurrences) — all genuinely non-filing, all individually justified

This is the single pattern closest to the exact hazard team-lead named
("a test moved to a lower grade tier whose true subject IS filing"), so it
was checked exhaustively rather than sampled: every `grade=` occurrence in
the entire diff was located (8 total, all `RegistryAuthorityGrade.CALCULATION`,
none `INSPECTION`/`APPLICABILITY`/`SCHEDULING`), all inside one cluster —
`dev`-adjacent formula-runtime test support
(`domain/calculations/registry/tests/_formula_runtime_support.py`,
`conftest.py`, `test_formula_runtime_validation.py`,
`test_m100_rental_reduccion_art23_2.py`,
`test_modelo_100_cripto_1812_propagation.py`). Read every one of these five
files' diffs in full. Every fixture using `CALCULATION` grade feeds only
`calculate_registry_snapshot(...)` — formula-runtime arithmetic assertions
(dependency-order evaluation, constraint violations, signed intermediate
results, settlement-chain arithmetic, 1812/1811 identity-copy propagation) —
**never** `export_draft`, `build_filing_producer_snapshot`, or any
byte-emission path. Every fixture carries an explicit docstring stating the
reason ("a formula-runtime calculation claim, never a filing one"). The
default on the shared `registry_snapshot` fixture in
`domain/calculations/registry/tests/conftest.py` stays `RegistryAuthorityGrade.FILING`
— callers must opt DOWN explicitly and in typed, greppable form; nothing
silently inherits a weaker grade. This is the legitimate move team-lead's
own framing describes, applied consistently and documented at every site.

### Gate-loosening sweep of today's working tree | info | `bundled_authority()` → `load_registry_tree()` swap in the M303 census tooling — legitimate compile-tier verification, not a filing bypass

`dev/registry/m303_semantic_census.py` and
`dev/registry/tests/test_modelo_303_semantic_maps.py` both replace
`bundled_authority()` / `bundled_revision_inspection()` calls with
`load_registry_tree()` + `RegistryRevisionInspection.from_revision(...)`.
`bundled_authority()` is the filing-grade authority, which now refuses at
load per the operator's own standing gate (deliberately, per CONTINUITY.md
and the operator directive this whole campaign implements). These two files
are semantic-MAP authoring/verification tooling — proving a map bijects
against the parsed design — which is a compile-tier question, not a filing
claim, and the new inline comment states this explicitly: asking the filing
authority to load here "would make map verification wait on an operator
attestation it has no bearing on." The revision-identity check this swap
sits inside is preserved, not dropped: `assert inspection.revision_id ==
revision.id` becomes `assert str(inspection.revision_id) == str(revision.id)`
— a type-coercion change (a bare grep for a removed `assert` line flagged
this as a false positive; the replacement assert is one line below the
removed one and equivalent). Not a loosening: it is the same pattern applied
correctly, in the same shape and for the same stated reason, as the grade
opt-downs above.

### Gate-loosening sweep of today's working tree | info | M303 2025/2026 census expectation changes — a correction that TIGHTENS grounding, not a loosening

`dev/registry/m303_semantic_census.py` changes the 2025 epoch's expected
`casilla` count from 111 to 113 and `literal` from 42 to 40 (2026: 112 to
114, 42 to 40 — the same shift). The accompanying comment in
`test_modelo_303_semantic_maps.py`'s retired-homes table explains why:
casillas 154 and 166 were previously demoted to hardcoded `literal` zero
constants (the comment being replaced said they "become a fixed mandated
zero"); the new comment states they "keep their casilla homes precisely
because they DO have one," narrowing the literal-only exception to casilla
17 alone, which is justified as having "no formula and no dated parameter,
so no computed authority stands behind the slot." This moves TWO casillas
FROM a hardcoded literal TO a real casilla-backed authority — the opposite
direction of a loosening. A hardcoded literal zero is a stronger risk of
silent under- or over-declaration than a value read from a grounded casilla;
this change removes two instances of it.

### Gate-loosening sweep of today's working tree | info | Deleted test — exact 1:1 coverage move, matches the "nothing is withdrawn" terminology purge

`src/cadrumo/application/filing/tests/test_withdrawn_export_refusal.py` was
deleted. Read both the deleted file (via `git show HEAD:<path>`) and its
replacement, the new untracked
`test_unbuilt_layout_export_refusal.py`, in full. The two are functionally
identical: same fixture construction, same `pytest.raises(FilingExportError,
match="no complete export_layouts definition")`, same
`assert not output.exists()`. Only the test name, docstring, and a local
output-file name changed, replacing "withdrawn" framing with "unbuilt" —
consistent with the operator's explicit "nothing is withdrawn" directive.
Coverage did not move away; it moved to the new file unchanged.

### Gate-loosening sweep of today's working tree | info | New acceptance/security tests — real, substantive, deliberately red where appropriate

Two new tests read in full and confirmed not to be stubs or vacuous passes:

- `test_filing_emitted_byte_acceptance.py` (270 lines, new): the campaign's
  own emitted-byte acceptance proof, described in its own docstring as
  "expected to fail today, for two separate reasons it reports separately"
  (no Modelo 303 layout; no operator-reviewed revision). No skip or xfail
  marker anywhere in the file — it is meant to be red until the real
  capability lands, and is.
- `test_handover_leaves_no_resumable_session_material_for_the_retired_profile`
  (new, in a profile-custody test module): a genuinely new security test
  proving a retired profile's session-acceleration receipt cannot still
  yield its encryption key. Carries its own anti-tautology proof (asserts
  the receipt IS resumable while the profile is live, before proving it is
  NOT after retirement) and wraps setup in `try`/`finally` purely for
  `_close_live_login()` cleanup — not a swallowed exception.

### Gate-loosening sweep of today's working tree | info | Auto-generated docs and duplicate-path artifacts checked, both benign

`docs/api/*.rst` changes (the largest raw file count in the diff) are the
CLI-owned generated API reference; spot-checked one deletion
(`cadrumo.domain.contribuyente.family.rst`) against the source tree and
confirmed `family.py` was genuinely split into `_family_profile.py` /
`_family_types.py`, with matching new stubs generated for both — a real
relocation, not an orphaned coverage drop. `src/cadrumo/tests/_bucket_id_fixture.py`
shows both `D` (staged delete) and `??` (untracked) status at the identical
path; diffed the pre-deletion committed content against the current
untracked content and they are byte-identical — a git-index artifact, not a
content change.

## Recommendations

**The detection gap, stated plainly for whoever runs the next sweep.** This
sweep's patterns catch SYNTACTIC weakening — a skip added, an assert
removed, a grade parameter changed. They do not catch SEMANTIC weakening —
a call site swapped from one function to a differently-named sibling that
checks less. The three real instances found today were all recovered only
by first re-deriving the "what changed" scope honestly (checking `git log
--since` rather than trusting a stated "nothing is committed") and then
running a dedicated identifier-diff detector across hunks, not by any
pattern in the original six. A future sweep MUST run both checks
separately: pattern-grep for the six syntactic shapes, AND a hunk-level
identifier-diff pass (remove/add identifier sets per hunk, flag textually
related but non-identical pairs) filtered to review/verification-semantic
keywords, then read every flagged pair against the module boundary it
crosses. Treat "zero loosenings" from the syntactic pass alone as an
incomplete answer, not a clean bill of health.

**Re-verify "nothing is committed" before scoping to the uncommitted tree**,
every time. It was false today by the time this sweep started, and the
false premise is exactly why two of today's three real instances sat
outside the diff this sweep first read.

No remediation needed on the three found instances — all three are
independently verdicted justified above, each for a documented, traceable
reason distinct from "team-lead said so." Record this sweep's method as the
standing bar for the next one: pattern-grep the six named shapes across the
full diff, run the identifier-diff class sweep separately, read every hit's
actual context rather than counting matches, and read every production
(non-test) file's diff in full rather than sampling it. The `grade=`
opt-down, the `bundled_authority()`-swap, and the `verify_*` /
`verify_*_grounding` sibling-swap patterns are all likely to recur as more
of the registry campaign's tooling adapts to the new fail-closed-at-load
gate; the bar for each future instance is the same one applied here —
genuinely non-filing subject matter, default stays strict, and an explicit
inline reason at the call site, not a bare parameter or callee change.

If a future sweep finds a `grade=` opt-down OR a `verify_*_grounding`-class
swap whose fixture or call site is consumed by a path that also calls
`export_draft`, `build_filing_producer_snapshot`, or any byte-emission
path, that is the loosening this sweep exists to catch and did not find
today — treat it as critical regardless of how well documented the change
is, since a documented bypass of a filing claim is still a bypass.

**The caveat from finding 1 is resolved, not carried forward** — traced
concretely on Modelo 390's live export (see the dedicated finding above):
Spain's own rate-establishing provisions ARE independently re-verified at
the filing boundary via the exported casillas' own `legal_refs`, redundant
with the relaxed loader check. What remains genuinely untraced, precisely
scoped rather than left as a blanket unknown: a FOREIGN member state's rate
citation reaching an export, which has no real consumer among the 7
currently layout-capable modelos today (Modelo 369, the OSS/IOSS consumer
of foreign rates, has no export layout). Re-trace this specific gap the day
Modelo 369 or any other foreign-rate consumer gains one — do not assume the
Spain-rate finding generalizes to a jurisdiction it was never checked
against.
