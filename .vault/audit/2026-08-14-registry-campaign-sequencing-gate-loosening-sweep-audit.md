---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:9d2e742f9b7589dec4fee42d42c8c008333414974811e28d403d4f571f49723e'
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

### Gate-loosening sweep of today's working tree | info | Verdict: zero loosenings found across a full sweep

Every one of the six loosening shapes was searched for explicitly across the
tracked-file diff (skip/xfail/pragma/TODO, removed `assert`, removed
`pytest.raises`, newly added `try`/`except`, every `grade=` opt-down, and a
`def test_` add/remove balance check), and every hit was individually
traced to its context rather than counted as a finding on the pattern alone.
Nothing found rises to a loosening. The individual clusters below record
what was checked and why each is safe, so a later reviewer does not have to
re-derive the same conclusion from a bare "clean."

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

No remediation needed — no loosening was found. Record this sweep's method
as the standing bar for the next one: pattern-grep the six named shapes
across the full diff, then read every hit's actual context rather than
counting matches, and read every production (non-test) file's diff in full
rather than sampling it. The `grade=` opt-down and the
`bundled_authority()`-swap patterns are likely to recur as more of the
registry campaign's tooling adapts to the new fail-closed-at-load gate; the
bar for each future instance is the same one applied here — genuinely
non-filing subject matter, default stays strict, and an explicit inline
reason at the call site, not a bare parameter change.

If a future sweep finds a `grade=` opt-down whose fixture is consumed by a
test that also calls `export_draft`, `build_filing_producer_snapshot`, or
any byte-emission path, that is the loosening this sweep was built to catch
and was not found today — treat it as critical regardless of how well
documented the opt-down is, since a documented bypass of a filing claim is
still a bypass.
