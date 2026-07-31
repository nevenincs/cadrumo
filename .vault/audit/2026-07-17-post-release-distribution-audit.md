---
tags:
  - '#audit'
  - '#post-release-distribution'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:a0a2ca2ccaf84b47f8d1c8ebcb32a79aa5c2fac1d5acfdbc40963d00b103f01d'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# `post-release-distribution` audit: `distribution post-release deferral split`

## Scope

This audit records the honest deferral of the post-release tail of the
distribution-installation-readiness campaign. Twenty-five open steps that cannot be
completed from the development worktree were lifted verbatim into the
post-release-distribution plan, each row recording its originating step identifier. This
document names every deferred step and the gate that blocks it so the
distribution-installation-readiness plan can close its completable local remainder
honestly, per the plan-closure-requires-exec-records discipline: an unlanded step is
either closed with evidence or formally deferred with a named blocker, never silently
dropped or falsely checked.

Two gates block the deferred work. Gate A is operator publish-workflow approval, which is
currently held until the worktree is declared settled; only the operator can lift it. Gate
B is real public-registry and multi-operating-system access - Windows Sandbox, multi-OS
acquisition-gate runners, real Claude Code, Claude Desktop, and Cowork client installs, and
credentialled reacquisition from PyPI, the GitHub release, the public Scoop bucket, the
public Homebrew tap, the Claude marketplace, and the MCPB clients - none of which this
worktree can provide.

## Findings

### deferred-local-channel-proof | deferred | Real-environment channel proofs need multi-OS runners and a publisher identity

Originating `W02.P04.S19` (Windows Sandbox Scoop install) and `W02.P04.S20` (clean Scoop
acquisition gate on the Windows release row) are blocked by Gate B: Windows Sandbox and a
multi-OS acquisition runner. `W02.P05.S24` (Homebrew acquisition gate on every claimed
macOS and Linux row) is blocked by Gate B: macOS and Linux runners. `W02.P06.S29` (bind
MCPB signing identity and bootstrap to the immutable cohort) is blocked by Gate B in its
publisher-identity form: a real MCPB signing identity. These are now
post-release-distribution `P01.S01` through `P01.S04`.

### deferred-support-matrix | deferred | Platform and client oracles need multi-OS CI and real Claude clients

Originating `W03.P08.S34`, `S35`, and `S36` (installed tax oracle on the claimed Linux,
Windows, and macOS Python rows) are blocked by Gate B: multi-OS CI runners. `W03.P08.S37`
(Homebrew installation and both oracles on the claimed Linux row) is blocked by Gate B.
`W03.P08.S38`, `S39`, and `S40` (cohort plugin or MCPB install and tax-work tool call in
Claude Code, Claude Desktop, and Cowork) and `W03.P08.S69` (capture each real Claude
client harness inventory and MCP product descriptions) are blocked by Gate B: real
Claude-client installs. These are now post-release-distribution `P02.S05` through
`P02.S12`.

### deferred-promote-reacquire | deferred | Promotion is held and reacquisition needs live public registries

Originating `W04.P09.S41` (promote stored cohort bytes through protected manual OIDC
publication) is blocked by Gate A: the held operator publish approval. `W04.P10.S45`
through `S50` and `S70` (reacquire from PyPI, the GitHub release, the public Scoop bucket,
the public Homebrew tap, the Claude marketplace, the MCPB clients, and re-verify the public
Claude artifacts) are blocked by Gate B: they require the promoted cohort to exist on those
public registries first. These are now post-release-distribution `P03.S13` through
`P03.S20`.

### deferred-availability-docs-and-audit | deferred | Availability language and the claim audit need post-public evidence

Originating `W05.P11.S52`, `S53`, `S54`, and `S55` (publish proven acquisition commands,
document clean install and removal for Python, Scoop, and Homebrew, document Claude
acquisition, and publish the measured support matrix) are blocked by Gate B: the
documentation may name only channels with passing post-public evidence, which does not yet
exist. `W05.P12.S59` (audit every artifact claim against retained installed-behavior and
public-reacquisition evidence) is blocked by Gate B: the reacquisition evidence does not
yet exist. These are now post-release-distribution `P04.S21` through `P04.S25`.

### retained-local-remainder | informational | Seven completable steps stay in the parent plan

The distribution-installation-readiness plan retains the local completable remainder for
the distribution peer to finish from this worktree: `W02.P06.S67` and `S68` (harness
identifier and MCP-description verification via the local verify script), `W04.P09.S44`
(the publish-workflow structural gate), and `W05.P12.S57`, `S58`, `S60`, and `S71` (the
path-scoped tests, the safety and quality review, the execution records and index rebuild,
and the brand-parity audit). The two emptied phases - the support matrix and the
public-reacquisition phase - were removed from the parent plan after their steps moved.

## Recommendations

Close the distribution-installation-readiness plan against its seven retained local steps
only, treating the twenty-five deferred steps above as formally deferred to the
post-release-distribution plan rather than incomplete work on the parent. Do not check any
deferred step in either plan until it lands against real external evidence. Begin the
post-release-distribution plan only after the operator lifts the publish hold (Gate A) and
the public-registry and multi-OS access (Gate B) becomes available; its own phases are
ordered by the release lifecycle and cannot start earlier.
