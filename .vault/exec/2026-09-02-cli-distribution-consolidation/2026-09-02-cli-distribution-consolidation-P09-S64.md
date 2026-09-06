---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:e6e79d9f00d920a4013d71dac0075968dc4f7d94ffa494a4d7b7550d7dc7a135'
step_id: 'S64'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Make the installed payload attestation find the distribution it just installed

## Scope

- `dev/packaging/_installed_wheel_binding.py`

## Changes

- `M` `dev/packaging/_installed_wheel_binding.py`
- `A` `dev/packaging/tests/test_installed_interpreter_binding.py`

## Notes

The attestation resolved the console script's interpreter through its
symbolic links. On this operating system a virtual environment's interpreter
is a real copy, so resolving it changes nothing; on the others it is a link to
the base interpreter, so resolving it walked out of the very environment the
attestation exists to describe. The check then asked a interpreter that had
never seen the installed distribution, and reported it missing.

That asymmetry is why the path passed on this workstation for hours while
failing on both other platforms, and why the failure looked platform-specific
when it was one dereference.

The install was correct and the link is deliberate: a copied interpreter loses
the relative reference to its own runtime library and aborts on one platform,
which the smoke helpers already document. So the check was wrong, not the
install, and pointing it at the environment it attests strengthens rather than
relaxes it.

Running the pre-change code against a real environment on another platform
surfaced a second break from the same cause: the console entry-point assertion
looked for the launcher beside the resolved interpreter, in the managed
runtime's own directory. That path had never worked anywhere.

## Scope

- `dev/packaging/_installed_wheel_binding.py`

## Changes
