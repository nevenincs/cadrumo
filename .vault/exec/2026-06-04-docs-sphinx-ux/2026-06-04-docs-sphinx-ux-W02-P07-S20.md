---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:005e3c6cac2f40ac65db59b180c8514aa2de27b1cb7100c4c0df688d2a710223'
step_id: 'S20'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# prepare the route and reference review packet from a fresh local site build (docs/_build/html is a gitignored, re-derivable artifact, not a persisted deliverable)

## Scope

- `docs/_build/html`

## Description

- Build the documentation site fresh at HEAD with the canonical builder
  (`python -m dev.docs.build docs/conf.py`), after the curated API overview,
  the header-nav retarget, and the docstring cross-reference fix landed.
- Capture rendered evidence in a real browser session at desktop and mobile
  viewports across landing, CLI reference (dark theme), and the curated API
  overview.
- Assemble the consolidated review packet covering all three human approval
  gates (brand direction, navigation readability, rendered experience) with
  the captured screenshots, the green machine-gate summary, and an explicit
  per-gate decision request; publish it as a private page for the operator.

## Outcome

- Packet prepared and delivered to the operator; the build it documents is
  re-derived from a gitignored local site build per the Step's own note, not
  a persisted artifact.
- The packet consolidates this gate with the sibling packet Step so the
  operator's three approvals happen in one sitting; approval verdicts and any
  requested changes will be recorded on the corresponding approval and
  feedback-incorporation Steps.

## Notes

- The reference half of the packet shows the curated API overview and the
  operator/schema route split that earlier packet attempts had nothing to
  show for; both landed before this packet was assembled.
