---
tags:
  - '#audit'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:410bfcfbe1b9a4123b4cab012c6b2b8a4acd6c23700a9d96cd2b0635b84aec33'
related:
  - "[[2026-08-22-profile-registration-password-policy-canonical-credential-capability-adr]]"
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-registration-password-policy with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-registration-password-policy` audit: `formal campaign review`

## Scope

Independent formal review of the current profile-credential campaign against the
accepted canonical-credential ADR, its research and reference trace, the live plan,
and the original fourteen-scalar TUI crash. The review followed the current code from
the pure core assessment through custody, recovery supervision, application
registration/rotation/proof mapping, TUI and scripted CLI presentation, locale and
error registration, generated API documentation, regression tests, and the S13 gate
record.

Each review phase began with semantic code and ADR discovery and was narrowed with
exact symbol searches against the current HEAD. The reviewer also reran the focused
unit lane (67 passed, 82 deliberately deselected) and the real integration lane (104
passed, 5 deliberately deselected). Those runs independently reproduce the original
fourteen-scalar TUI refusal as a localized expected outcome and exercise real scripted
creation, exact accepted-password unlocks, mutation-free refusals, recovery proofs,
and all four locale catalogues.

## Findings

### live-tui-refusal-matrix | medium | Most invalid boundaries bypass the real Textual submission surface

- [ ] `src/cadrumo/adapters/inbound/tui/tests/test_registration_screen.py:47-81`
  labels its invalid-candidate matrix as submission coverage, but the test calls
  `attempt_registration` directly. Only the original fourteen-scalar case later drives
  `RegistrationApp` with a real Textual Pilot. Consequently the 257-scalar, 1,025-byte,
  high-surrogate, and low-surrogate cases do not prove live feedback, button submission,
  pinned-status rendering, focus behavior, worker containment, or absence of the
  generic INTERNAL path at the actual TUI boundary. The accepted ADR and S11 explicitly
  require live-TUI parity across scalar, byte, and surrogate boundaries. The shared
  assessor makes the production behavior plausible, and the independent runtime lane
  is green, but a direct presenter call is not evidence for that acceptance criterion.

### secure-input-channel-prose | low | Shared secure-input documentation contradicts the live creation channel order

- [ ] `src/cadrumo/entrypoints/cli/_config/_secure_input.py:1-6` says custody secrets use
  exactly three channels and never the process environment, while
  `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:12-22` and
  `resolve_creation_passphrase` deliberately retain `CADRUMO_SECRET_PASSPHRASE` as the
  unattended creation fallback. The creation module accurately documents its own
  behavior, but the shared security contract makes a broader false claim. In addition,
  `resolve_creation_passphrase` describes its order as console-first even though an
  explicitly requested `--secrets-stdin` channel is checked first. This is prose drift,
  not an observed secret leak; bounded `SecretStr` stdin validation and no-echo tests
  passed.

## Recommendations

- For `live-tui-refusal-matrix`, drive every transportable invalid boundary through the
  real `RegistrationApp` Pilot and assert live feedback plus submitted refusal, no
  worker error, localized pinned status, secret absence, and no persisted capsule.
  Exercise surrogate candidates through the widget's programmatic value boundary if
  Textual accepts them; otherwise retain the direct adapter case and record the widget
  transport limitation explicitly. Keep S14 open until this matrix is green.
- For `secure-input-channel-prose`, make the shared module description precise about
  which helpers it governs and correct the creation resolver's declared precedence.
  Do not change the accepted channel behavior as part of a documentation repair.
- After both findings are resolved, rerun the two focused lanes and the exact obsolete
  symbol and recovery-policy negative searches, then append an immutable resolution
  entry to this audit before closing S14. S15 must also preserve S13's honest statement
  that full-tree gates were not green on the mixed concurrent HEAD; focused success is
  not proof that those repository-wide commands passed.
