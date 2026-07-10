---
tags:
  - '#adr'
  - '#release-readiness-gate'
date: '2026-07-04'
modified: '2026-07-08'
related:
  - '[[2026-07-06-release-readiness-gate-research]]'
status: accepted
---
# `release-readiness-gate` adr: `release readiness gate: audit-state gate, RC soak, rollback` | (**status:** `accepted`)

## Problem Statement

GitHub issue #415 (EPIC #392, iteration 23) asks for a release process that
gives Kent confidence: every non-hotfix release soaks on a pre-release
channel for 48-72h, an audit-state gate confirms the repository is
release-ready before the tag lands, and a documented rollback path exists if
a regression is discovered. At the time of this ADR, `aeat-cli` is pre-1.0,
has not shipped a PyPI release yet, and the release process is entirely
LOCAL-ONLY and human-gated (`RELEASING.md`, ADR
`2026-04-12-release-please-adr`). Nothing in the repository implements a
soak window, an audit-state gate, or a rollback procedure; a prior triage of
this issue (recorded in the issue's own comment thread) confirmed the
premise as genuinely unbuilt.

## Considerations

- The project's release surface is deliberately LOCAL-ONLY and human-gated:
  no GitHub Actions release automation, no automatic tag/push/publish. Any
  new gate or procedure must preserve that invariant absolutely.
- `aeat-cli` has not shipped a first PyPI release, so a real `aeat-cli-beta`
  PyPI project (a genuine pre-release channel end users can opt into) is
  premature infrastructure; there is no user base yet to protect with a
  beta channel.
- The issue's full scope (compatibility matrix, release signing, weekly
  version-check, standalone verifier) is broader than a single P2/effort:M
  chore can responsibly deliver; the safety mandate for this task is to
  build gate LOGIC and documentation, never to touch the actual
  release/publish surface.
- `just release-apply` already refuses on a dirty tree / wrong branch,
  giving a natural home for a pre-check gate.
- `gh` (read-only issue queries) is already a project dependency for the
  release-please dry-run recipe, so an audit-state check that queries open
  `priority:P0-blocker` issues is consistent with existing tooling.

## Considered options

- **A: Build a real `aeat-cli-beta` PyPI project now, matching the issue
  literally.** Rejected: there is no first stable release yet: a beta
  channel with nothing to be a beta OF is premature and would require
  provisioning PyPI infrastructure this task cannot safely commit to.
- **B: Build only documentation (no executable gate).** Rejected: a
  checklist nobody enforces is exactly the failure mode the issue exists to
  prevent (release hygiene degrading silently); an executable, tested gate
  is worth more than prose alone.
- **C (chosen): Build a deterministic, read-only audit-state gate
  (`dev/release/readiness.py`) wired into `just release-apply`, a
  machine-validated checklist (`docs/_release_checklist.yaml`) documenting
  the RC-soak and rollback procedures, and a print-only `just
  release-rollback` recipe; document the soak vehicle as a LOCAL pre-release
  build (not a hosted beta channel) until the first stable release ships.**
  This delivers a real, testable gate and a documented, followable process
  today without inventing infrastructure the project isn't ready for, and
  without touching the actual release/publish surface at all.

## Constraints

- Every new surface must perform zero outward action: no tag, no push, no
  publish, no PyPI yank. `dev/release/readiness.py` only reads local files
  and (best-effort) queries `gh issue list` (read-only). `just
  release-rollback` only prints; it never executes `git`/`gh`/`uv publish`.
- The `no-open-release-blockers` check depends on live external state
  (`gh` availability, network reachability), which is legitimately absent
  in an offline or fresh-checkout environment; it must degrade to an
  advisory rather than hard-failing the gate in that case, while a genuine
  open `priority:P0-blocker` issue remains a hard release blocker.
- No mocks/stubs permitted in the gate's own tests per project convention;
  the `gh`-backed check is exercised via a real subprocess call to a real,
  explicit-path stub executable (bypassing Windows PATH/PATHEXT resolution
  quirks discovered during implementation), not a patched Python object.

## Implementation

`dev/release/readiness.py` exposes per-check functions
(`check_version_surfaces_agree`, `check_changelog_is_ready`,
`check_no_open_release_blockers`, `check_latest_packaging_smoke_evidence`)
each returning a typed `ReadinessCheck` (name, severity, passed, detail);
`build_report` aggregates them into a `ReadinessReport` whose `ok` property
is true only when every `blocking`-severity check passes. `main()` exposes a
`python -m dev.release.readiness` CLI with `--json` and `--skip-network`.
`justfile` wires `release-readiness` / `release-readiness-json` as
standalone recipes and calls the gate as the first step of `release-apply`
on both Unix and Windows, refusing to proceed on a blocking failure.
`docs/_release_checklist.yaml` is a machine-validated (pydantic-parsed in
`src/aeat/tests/test_release_config.py`) data file recording the RC-soak
window (48-72h), versioning discipline, hotfix cycle times, and rollback
triggers; `docs/_release_notes_template.md` is the GitHub Release body
template. `RELEASING.md` gains "Release-candidate soak" and "Rollback
procedure" sections describing the human-run sequence; `just
release-rollback <version>` prints the same procedure for a given version.

## Rationale

A deterministic, tested, read-only gate wired into the existing
human-gated `release-apply` recipe delivers the audit-state-gate half of
the issue immediately and verifiably (confirmed live against this
repository: the gate correctly reports BLOCKED because issue #116 is a
genuinely open `priority:P0-blocker`). The RC-soak and rollback halves are
delivered as followable, machine-validated documentation rather than
speculative infrastructure (a real beta PyPI channel, automated rollback
execution) that the project is not yet ready to operate safely — building
that now would violate the no-outward-release-action safety mandate and
would be infrastructure with no real release to exercise it against.

## Consequences

- The audit-state gate is real and enforced today: `just release-apply`
  will refuse to proceed while `priority:P0-blocker` issues are open (as
  they currently are — issue #116), which is the intended, honest
  behavior.
- The RC-soak procedure is manual (a human tags a local pre-release, runs
  the packaging-smoke matrix, and holds for 48-72h) rather than automated;
  this is appropriate for a LOCAL-ONLY, human-gated release process and
  matches the project's existing `release` / `release-apply` split.
- Promoting the local pre-release soak vehicle to a real `aeat-cli-beta`
  PyPI project is explicitly deferred to a follow-up once the first stable
  release ships and there is a real user base to protect with it.
- The `no-open-release-blockers` check is best-effort and network-dependent;
  an operator without `gh` configured loses that one signal (reported as an
  advisory) but every other check remains deterministic and blocking.
