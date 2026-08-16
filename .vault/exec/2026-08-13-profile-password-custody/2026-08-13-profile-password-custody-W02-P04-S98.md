---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:43965dd98780ef2af8e38c94825fa029fa7354f50358a912de6f2a25692a05a0'
step_id: 'S98'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule who owns the Spanish default-output-language flip and repair the keychain-locked error test, which asserts English operator text with no language override anywhere in its conftest chain while the default at HEAD renders Spanish, so it cannot pass on this tree in any state and has been discounted from three separate suite counts tonight

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_errors.py`

## Description

- Establish whether the Spanish default output language is deliberate.
- Rule who owns it.
- Repair the test that asserts English with no override.

## Outcome

**Ruled: Spanish is the deliberate, gate-locked default, and the tests
asserting English prose with no override are the stale side.**

The evidence is unambiguous and was checked rather than assumed. The default
constant is pinned by its own test whose docstring states that locking the
value exists so accidental changes fail loudly, and the settings default is
asserted independently elsewhere. It is also what the project's naming rule
implies, the operator being a Spanish taxpayer filing Spanish forms. Nothing
had "flipped"; the default is the product's position.

So the repair is on the tests, not on the default. The canonical remedy already
existed in the tree: an autouse fixture that pins the rendered language and
clears the locale cache either side, which consuming modules import and
re-export. Applying it states the assumption a bare English literal was making
silently, and keeps the assertion readable without hardcoding Spanish prose
that the locale tooling owns and may legitimately re-word.

The keychain-locked error test that could not pass on this tree in any state
now passes.

## Notes

Three command-line modules were repaired the same way in the same pass. The
alternative — asserting the Spanish strings — was rejected because it couples a
transport test to catalogue prose maintained by a separate tool, so a
legitimate wording change would red tests that are not about wording.
