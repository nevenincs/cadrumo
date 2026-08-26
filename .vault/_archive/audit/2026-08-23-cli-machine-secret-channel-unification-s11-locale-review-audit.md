---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:515246cf2f2bc1d0d697deb9626b966ba84289f60bfea7ce2b063f22f87c7052'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-W02-P05-S11]]"
---

# `cli-machine-secret-channel-unification` audit: `S11 locale alignment review`

## Scope

Reviewed S11 commit `b9471d41a2` against the accepted machine-secret channel ADR,
the implementation plan and S11 execution record. The review covered the four
runtime locale catalogues, the focused locale-resolution test, generator ownership,
semantic fidelity, descriptor-zero guidance, obsolete environment guidance, scoped
diff containment, and the reported broader catalogue drift. Discovery began with
semantic code and ADR search and was pinned to exact keys and consumers with `rg`.

## Findings

### remaining-stdin-only-recovery-copy | medium | Two shared refusals still advertise only stdin

The S11 catalogue sweep left `echo_suppression_unavailable` and
`non_interactive_secret_required` unchanged in `src/cadrumo/locales/en/cli.yml`
at lines 1637-1643, with equivalent stale wording in the Spanish, Catalan and
Hungarian catalogues. Both tell an operator to use only `--secrets-stdin` even
though the accepted global contract makes `--secrets-fd` equally applicable and
the latter refusal is exercised by the closed machine-secret command inventory.
That is not globally uniform operator guidance and leaves the descriptor route
undiscoverable precisely when the prompt path refuses.

### semantic-locale-contract-untested | medium | The added test proves key existence but not the corrected contract

The additions in `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`
only assert that each key resolves and has more than ten characters. They would
pass if all four catalogues again claimed descriptor zero was reserved, reverted
to channel-specific malformed-payload copy, restored the passphrase environment
fallback, or mistranslated descriptors 1 and 2. Because fd0 acceptance and removal
of the CLI environment route are explicit ADR acceptance conditions and the heart
of S11, the focused test does not prevent regression of the behavior this Step
claims to close.

## Recommendations

- Update both remaining stdin-only recovery diagnostics through
  `python -m dev.locales set` in all four catalogues so they present both canonical
  channels without implying precedence.
- Add a compact four-locale semantic contract test covering the affected keys:
  both flags in absent/prompt-refusal guidance, no `CADRUMO_SECRET_PASSPHRASE`,
  descriptor 0 accepted, only descriptors 1 and 2 reserved, and channel-neutral
  malformed/size copy. Keep translation honesty and parity as complementary gates.
- Restore the current uncommitted S11 execution-record hint deletion from HEAD
  before S12 is committed. The annotation fix stripped scaffold-owned template
  comments and only refreshed the body hash; it is unrelated peer spillover, not
  a legitimate S11 or S12 semantic change.

## Resolution

Both medium findings are resolved. The four catalogues now name both canonical
flags in the echo-suppression and non-interactive refusals. A dedicated semantic
catalogue test loads every shipped locale through the locale manager and proves
both flags are present without the retired environment route, descriptor zero is
presented as accepted while descriptors 1 and 2 are reserved, and malformed,
missing-field, and oversize diagnostics are identical across stdin and descriptor
channels without naming either flag. The focused remediation suite passed 20 tests
and Ruff completed cleanly.
