---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ec8c434c18dfe3ac1b17f7eb189eb4e9adf23dafc63c324ec5788b94d445f924'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ci-lane-deconflation` audit: `P05 S127 code review`

## Scope

Independent review of P05.S127 commit `10241923541384f1f1f2eb8a9ab16a39d5a840a9`, the approved CI-lane and execution-evidence ADRs, the plan and S127 execution record, and all nine committed paths. Reviewed direct crypto ownership, lifecycle delegation, persisted-session failure and zeroisation paths, public/private import shape, changed focused tests, module budget/baseline, and current `HEAD`. The reviewed source/test blobs matched the current worktree for focused execution.

## Findings

### P05 S127 code review | high | recorded pytest evidence conceals nine deselected custody tests

`.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S127.md` records the exact four-file pytest command as `pass (42 passed)`, without its runner summary, exit or deselection state. Re-running that exact command at current `HEAD` produces `42 passed, 9 deselected in 11.26s` and pytest's `PARTIAL RUN` warning because the default marker selection excludes nine tests. The record therefore conflicts with the accepted execution-evidence ADR and overstates its test coverage. Its ruff record is likewise only `pass`, and it supplies no formatter result. Amend the record with verbatim result lines, explicit zero-deselection selection where intended, exact exits, and a formatter command/result; then re-review the record-only repair.

### P05 S127 code review | high | repaired behavioural-pass entry still omits its executable node-id command

Record-only commit `628babde4229c300098d7865ccb962710abace4f` correctly adds six-path ruff check/format results, a full 51-test collect-only result with zero deselections, and the honestly failing all-marker run (`9 failed, 42 passed`) for the Windows credential-store cases. Its claimed behavioural green run, however, records only `pytest invocation over the 42 explicit collected non-os_keychain node IDs with -q -o "addopts="`; it neither gives an executable command nor names the 42 collected node IDs. A reviewer cannot reproduce the selection, confirm that it excludes only the stated nine OS-keychain cases, or verify its zero-deselection claim. The execution-evidence ADR requires the literal instrument, not this paraphrase. Replace this entry with the exact `uv run --no-sync pytest` command and all 42 node IDs (or a committed deterministic selection mechanism), plus its literal result summary and exit.

## Recommendations

- Rerun the focused test files using a command that deliberately includes the required marker lanes, record the literal collection and result summaries with no deselections, and add exact ruff format evidence.
- Replace the non-executable 42-node behavioural-pass prose with its full command and node-id selection, then re-review the evidence-only amendment.

The extraction itself is canonical: `acceleration_receipt_crypto.py` owns the public persisted-record, AAD, AEAD wrap/unwrap and wipeable rewrap contract; the lifecycle module imports it privately and no longer re-exports that contract. Direct consumers import the crypto owner. Session-key and unwrapped-DEK buffers remain zeroised in lifecycle and crypto finally blocks, and persisted-session refusal/deletion routes remain in the lifecycle owner. The selected focused run passes 42 tests; the target measures `1065 <= 1250`, the crypto sibling is 229 physical lines, and no size baseline changes. `git diff --check` reports only a new blank line at end of the Markdown execution record, a cosmetic documentation whitespace notice rather than a source or evidence integrity finding.

