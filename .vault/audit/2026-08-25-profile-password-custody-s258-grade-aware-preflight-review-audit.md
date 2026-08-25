---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:be2e16248a736358426ab1a70ece8063e00dff99fc4a11bffcc4680530335621'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S258 grade-aware preflight review`

## Scope

Reviewed `W06.P12.S258` at current HEAD with provenance through commit
`963bc7ef12`. The review traced `probe_registry_referential_integrity`, declared
authority-grade forwarding, representative-context coverage, ungraded refusal,
dangling-reference detection, the healthy preflight row, and the typed
`config check` projection. Production code was not modified.

## Findings

### simulated-preflight-proofs | high | The new regression directions use forbidden monkeypatches and a stub authority

The mixed-grade test replaces `ValidatedRegistryAuthority.snapshot` with a
tracking function; the dangling-reference test replaces the registry module's
`bundled_authority`; and the ungraded test supplies a hand-written
`UngradedAuthority` stub and replaces the same facade. The always-on quality
gate prohibits mocks, stubs, and monkeypatches for behavior proofs. These tests
therefore do not establish the shipped composition boundary through real
loading and can remain green while production authority construction or routing
diverges from the substituted objects.

The production change itself has the correct local shape: every representative
revision snapshot now receives `revision.effective_authority_grade`; snapshot
validation retains full reference checks; an absent declared grade remains a
fail-closed condition in the snapshot authority gate; and the existing healthy
row plus typed `config check` projection remain intact. The blocker is the
required proof quality, not an identified defect in the one-line forwarding
implementation.

Disposition: **resolved**. Production now owns `_probe_registry_authority`, and
the public probe delegates to that exact loop after loading. The adverse tests
pass real `ValidatedRegistryAuthority` values through the production seam: a
dataclass-replaced authority with its legal catalogue removed for dangling
references, and a real-model authority with an ungraded revision and rebuilt
identity/cache maps for the fail-closed case. No monkeypatch, mock, or stub
remains in these directions.

### exact-grade-observation | medium | The replacement mixed-grade test no longer observes the grade passed to snapshot

The test computes an `expected` mapping from each real revision to its declared
grade, runs the probe, then asserts only that the precomputed mapping contains
all enum members. It never compares an observed snapshot invocation with that
mapping. It would remain green if the production loop hardcoded
`RegistryAuthorityGrade.APPLICABILITY` for every revision, because requesting a
lower floor still permits calculation- and filing-grade revisions. The test name
and Step require exact per-revision forwarding, but the replacement assertion
proves only that mixed grades exist in the input registry and that some grade
choice yields a healthy row.

Re-review disposition: **still open** after adding flattened production grade
counts. Those counts are incremented from `requested_grade` before the snapshot
call and therefore report the intended value, not the value actually passed.
Changing only `grade=requested_grade` to a hardcoded applicability floor leaves
every emitted count and assertion unchanged. The new evidence remains
self-reported beside the behavior it is meant to constrain and does not make the
gate bite on the exact regression.

Final disposition: **resolved**. A non-mock AST gate now requires exactly one
`requested_grade` assignment, requires its value to be
`revision.effective_authority_grade`, requires exactly one snapshot call in the
production seam, and requires that call's `grade` keyword to be the same
`requested_grade` name. Combined with the independently enumerated real-registry
grade counts, this gate reds if the call is hardcoded to the permissive floor.
The full preflight module passed 21 tests, the real `config check` integration
row passed, and Ruff and ty passed after the remediation.

## Recommendations

- Re-author the three directions through real production authority loading. Use
  a copied registry resource tree or a production-owned explicit authority seam
  rather than replacing functions or classes. Prove the mixed-grade population
  reaches applicability, calculation, and filing snapshots; remove a real
  referenced catalogue entry and require a red row; and load an actually
  ungraded revision and require fail-closed behavior.
- Retain the current healthy bundled-authority row and real `config check`
  projection as the positive directions, and ensure the adverse fixtures fail
  for the intended reason rather than at an earlier parse boundary.
- Add a non-substituted production observation or structural anti-tautology that
  binds every snapshot invocation to its `(modelo, revision, requested grade)`
  tuple and compare it with the declared-grade mapping. The gate must red if the
  production grade argument is hardcoded to the permissive applicability floor.
  A focused AST structural gate proving that the snapshot `grade` keyword is the
  same local bound directly from `revision.effective_authority_grade` is suitable
  when the called API exposes no requested-floor observation.

All recommendations are satisfied. No CRITICAL, HIGH, MEDIUM, or LOW finding
remains unresolved.
