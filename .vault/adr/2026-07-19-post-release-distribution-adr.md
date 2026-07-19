---
tags:
  - '#adr'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
related:
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-16-distribution-harness-identity-adr]]"
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `post-release-distribution` adr: `post-release distribution defers the external-access tail of the parent distribution ADRs` | (**status:** `accepted`)

## Problem Statement

The distribution-installation-readiness campaign built and locally proved every generated distribution artifact (the cohort manifest, the Python wheel and sdist lanes, the Scoop and Homebrew generators, the plugin, marketplace, and MCPB artifacts, and the release-readiness evidence schema). A tail of that campaign cannot be completed from the development worktree because it requires real external access: multi-operating-system CI runners, real public registries, real Claude clients, the operator's held publish approval, and post-publication public reacquisition. That tail needs its own lifecycle home so the parent plan can close its local scope without falsely completing work only the post-release environment can prove, and so the steps already satisfied against real external evidence can carry execution records. This ADR is that home; it records no new architectural decision.

## Considerations

- Two accepted parent ADRs already govern the substance of this work: the distribution-installation-readiness decision and the distribution-harness-identity decision. This feature inherits both and adds nothing to them.
- Publication is HELD by the operator until the worktree is declared settled; no agent may lift that gate.
- The second gate is real external access (public registries, multi-OS runners, real clients) that the worktree cannot satisfy.
- Honesty is the closing rule: a step closes only against real external evidence, never against intent or partial capture.

## Considered options

1. Leave the external-access tail in the parent distribution plan. Rejected: it either blocks the parent from closing its completed local scope or invites falsely marking externally-provable steps done.
2. Carry the tail into a dedicated continuation plan governed by this formalizing ADR. Accepted: the parent closes its local scope honestly, the deferred work has a durable home, and the lifecycle permits execution records for the steps proven against real evidence.
3. Keep a continuation plan with no ADR. Rejected: the research -> ADR -> plan -> exec lifecycle refuses execution records for a feature with no ADR, so the satisfied steps could never carry their evidence.

## Constraints

- Depends on the two parent distribution ADRs remaining accepted; this ADR is purely derivative of them.
- Blocked on the operator's held publish approval and on external registry, client, and multi-OS CI access; those gates are outside the worktree.

## Implementation

This feature holds the steps lifted verbatim from the parent distribution plan, each recording its originating identifier. A step closes only when its acceptance criteria are met against real external evidence: a green CI run identity, a retained installed-behavior or reacquisition evidence document, or an accepted resolving ADR. Steps that still require missing external access remain open. Execution records reconstruct each satisfied step's evidence (commit identities, CI run identities, evidence document locations) from the campaign landings.

## Rationale

The decision formalizes the rationale the continuation plan already states; it introduces no architecture. The substantive decisions live in the two parent ADRs. This ADR exists so the continuation plan is lifecycle-complete and its satisfied steps can be honestly recorded, while the deferred majority stays open until the post-release environment exists.

## Consequences

- The parent distribution plan can close its completed local scope without falsely completing external work.
- The steps already proven against real evidence gain execution records; the vault stops reporting them as checked-without-record.
- The open steps remain an honest, visible deferral gated on operator publish approval and external access; the plan completes only when every step closes against real external evidence and a fresh-context honesty review runs against the closure summary.
