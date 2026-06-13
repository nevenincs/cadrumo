---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-03-untangle-transactions-repo-public-exec]]"
---

# 2026-04-30-aeat-restructure step-04 tier-2 paths guardrail

## status

Step 4 — Tier-2 security-audit prep (HARD GATE before Step 7 layout-move PR can merge). Authors a comprehensive guardrail unit test for `resolve_record_json_path` (the security-critical boundary cited in the path-handling-safety audit and the secure-persistence-foundation final security audit).

## scope

- New test file `src/aeat/_test_paths.py` covering all rejected/accepted shapes for `resolve_record_json_path` and `resolve_relative_subpath`.
- The test file will move with `aeat.core.paths` → `aeat.core.paths` in Step 7's keystone PR. Tier-2 inline-updates of the two cited audit docs to reference the new location ride in the same Step 7 PR per the ADR.

## test coverage

28 test cases, all passing:

- 5 accepted record-id shapes: alphanumeric, alphanumeric-with-digits, snake-case + alpha, dash + version-suffix, max-length 128 chars.
- 17 rejected shapes: parent traversal (`../escape`), forward slash (`subdir/file`), backslash (`subdir\file`), leading dot (`.dotfile`), leading dash (`-dashfirst`), empty, space (`a b`), semicolon (shell), dollar (shell), glob asterisk, newline, null byte, colon (Windows drive), 129-char overlong, bare dot, parent (`..`), absolute-looking (`/abs`).
- Context-label propagation: error message names the caller's context arg.
- Relative-root containment: still works when caller supplies a non-resolved relative root.
- 4 `resolve_relative_subpath` cases: backslash rejection, parent rejection, absolute rejection, nested-forward-slash acceptance.

## relationship to step 7 hard gate

Per ADR Vault-corpus supersession Tier-2 treatment + Operational Contract Acceptance criteria:

> "Revalidated" means an explicit guardrail unit test passes against the new path AND the audit document is inline-updated to reference the new location. Both conditions must hold.

This PR satisfies the **test** half; the **inline-update** half rides in Step 7's keystone PR (modifying the two audit docs to reference `aeat.core.paths` after the move). Both halves are required for the layout-move PR to clear the HARD GATE.

## verification

`uv run --no-sync python -m pytest src/aeat/_test_paths.py -v` reports `28 passed`.

## next step

Step 5 — Tooling prep (multi-day net-new build): rebase script + import-linter contracts + smoke test + type-checker config + packaging tests + shim-verifier. Each artefact is independently runnable and CI-gating before Step 6's freeze trigger fires.
