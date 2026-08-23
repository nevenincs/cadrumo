---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2d4b0b63bba99c76442948ecbc2d5fc01df1461100bdfca9391269febd650157'
step_id: 'S22'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-machine-secret-channel-unification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-08-23-cli-machine-secret-channel-unification-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and align all four locales and focused behavior tests for root applicability, parse precedence, session refusal reasons, collisions, self-authenticating exemptions, cleanup, leakage, and Windows descriptor bootstrap semantics and ## Scope

- `CLI locale sources root profile-authentication tests and platform bootstrap` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and align all four locales and focused behavior tests for root applicability, parse precedence, session refusal reasons, collisions, self-authenticating exemptions, cleanup, leakage, and Windows descriptor bootstrap semantics

## Scope

- `CLI locale sources root profile-authentication tests and platform bootstrap`

## Description

- Ground the settled root-authentication grammar and its S21 review findings through semantic discovery, exact source searches, and current-HEAD inspection.
- Preserve exact root/leaf selection, callback, and requested-leaf types through a type-only protocol seam without introducing a runtime import cycle.
- Deliver the keychain-free non-persistence warning through one invocation-scoped typed Notice queue consumed by both success and error envelopes.
- Localize root-specific help, applicability, collision, unused-source, missing-target, parser, descriptor, and repeated-authentication diagnostics in all four catalogues through `dev.locales`.
- Add an explicit Windows inherited-HANDLE bootstrap that converts one caller-allowlisted handle into the canonical descriptor route without claiming POSIX numeric-fd inheritance.
- Exercise all typed resume reasons, cross-scope collisions, self-authentication posture, four-locale rendering, Notice one-shot delivery, a real keychain-free Argon2 login followed by a leaf refusal, and platform-specific bootstrap behavior.

## Outcome

The two S21 MED findings are closed. Root and leaf selections remain statically exact at the neutral session gate, and a successful keychain-free login can no longer lose its promised warning when the requested handler later refuses or raises. Root help and every reachable diagnostic now distinguish profile authentication from leaf secrets in English, Spanish, Catalan, and Hungarian. Windows supervisors have a concrete HANDLE-to-CRT bootstrap while stdin remains the portable route.

Focused root-contract, locale, Ruff, and type gates pass. Forty-four focused unit cases pass on Windows, and the real keychain-free post-login refusal integration case passes separately. The later S13/S14 rows retain ownership of the full real subprocess success/refusal matrix.

## Notes

- The shared worktree advanced during execution and a peer cohort commit carried part of the Notice and typed-gate implementation before this scoped close; current HEAD and diffs were re-read and only the remaining S22 delta is committed here.
- Locale serialization also normalized wrapping/order of pre-existing inventory strings in the same four CLI shards; values are unchanged.
- `dev.locales scaffold --check` remains broadly red because concurrent registry work currently reports hundreds of unrelated missing and extra keys. The four catalogues have equal S22 keys and the focused locale semantic gate passes.
- The repository import-linter retains its established application-to-adapter boundary debt; the S22 modules add no reported edge.
- Vault scaffolding reported unrelated invalid UTF-8 in the in-flight website ADR and research documents; neither file is in this Step's scope.
