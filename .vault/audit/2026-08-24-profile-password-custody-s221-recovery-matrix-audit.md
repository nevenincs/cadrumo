---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:095e1b324a29233daa416ffff00465dcb0c3dd019c0e547b362174d59ee306e7'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
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

# `profile-password-custody` audit: `S221 recovery matrix review`

## Scope

Review the S221 rerun of the complete S206 mandatory recovery-at-creation matrix across application/storage, scripted leaf channels, terminal/TUI, Windows and POSIX subprocess transports, and harness provisioning. Verify that the two test-infrastructure fixes preserve real protocol behavior and that unrelated residuals are not absorbed.

## Findings

### recovery-matrix-review | LOW | Complete matrix and test-support repairs preserve the real protocol

No CRITICAL, HIGH, or MEDIUM finding remains. The shared CLI helper creates two distinct anonymous pipes, gives the real scripted create leaf only the handoff writer and verification reader, drains the bounded handoff in a supervisor, returns the exact emitted strict-JSON proof through the separate verification writer, wipes its mutable payload, closes both supervisor ends in `finally`, closes both CLI ends after invocation, and refuses test completion if the supervisor does not terminate. It therefore exercises the production descriptor parser and application comparison rather than supplying a bypass callback or a synthetic `None` result.

The TUI readiness change waits for the mounted mnemonic and confirmation-button nodes before returning the recovery screen. The test still reads the real rendered 24-word mnemonic, supplies that complete value to the password-masked `field-recovery-verification` input, clicks the real confirmation action, joins the registration worker, and proves publication only afterward. Wrong re-entry, cancellation, and shutdown continue to prove no committed capsule. The readiness predicate only removes a composition race; it does not weaken exact possession verification. An independent rerun of the four real TUI registration tests passed.

The persisted evidence accounts for every required lane without double-counting: 45 application, storage/login-independence, codec, and scripted refusal/success cases; 8 terminal and TUI cases; 3 passing leaf/platform subprocess cases plus the expected POSIX platform skip on Windows; and 2 harness delivery cases, for 58 passed and one platform skip. The Windows inherited-HANDLE case ran on the host, while the POSIX `pass_fds` counterpart is explicitly retained as the mutually exclusive platform test. The broader taxpayer-type module independently reproduces three failures only after the repaired helper completes recovery and creates or edits the profile: incomplete legal-form creation, setup-completion routing for IRNR, and legal-to-natural surnames expectations. Those assertions concern taxpayer completeness and next-action semantics, not recovery transport, possession proof, or publication atomicity.

## Recommendations

Accept S221. Retain the paired-pipe helper, mounted-widget readiness check, exact re-entry and rollback assertions, and mutually exclusive Windows/POSIX subprocess tests as the recovery closure matrix. Route the three taxpayer-type expectation updates to their owning completeness and next-action work; they do not block custody recovery closure.
