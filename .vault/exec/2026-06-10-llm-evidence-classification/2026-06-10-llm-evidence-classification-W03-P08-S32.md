---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S32'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Pass the nitpicky Sphinx docs-build gate

## Scope

- `dev/docs/tests/test_docs_build.py`

## Description

- Regenerate API stubs (`python -m dev.docs.apidocs scaffold`) to add the two missing peer-module stubs (`_dt12_advisory`, `_calendar_models`); `scaffold --check` then clean.
- Pin `sphinx>=8.1,<9` in `pyproject.toml` and relock (`uv lock --upgrade-package sphinx`, 9.1.0 → 8.2.3): `sphinx-hoverxref` 1.4.2 (its latest release) crashes on Sphinx 9's `_Opt` config representation at `config-inited`, which had blocked the build entirely.
- Fix two genuine docstring nitpicks: demote `:attr:`original_exception`` to an inline literal in `transactions/_errors.py` and `user_profile/_errors.py`; split the malformed multi-name `discarded_at, discarded_by, discard_reason` Attributes line in `modelos/_calculation_revision.py` into three single entries.
- Enroll the bare-referenced PEP 695 `type` aliases (the 24 `*Id` family minus the two real `*Id` StrEnum classes, plus 18 non-`Id` aliases) in `docs/conf.py` `nitpick_ignore_regex`, per the conf's documented policy for undocumented aliases referenced by docstrings.

## Outcome

- The nitpicky `-n -W` Sphinx docs-build gate (`dev/docs/tests/test_docs_build.py`) passes. The Sphinx-toolchain crash and the latent typed-alias nitpicks (all unmasked for the first time once the crash was fixed) are resolved.

## Notes

- The Sphinx/hoverxref incompatibility and the ~24 latent nitpicks were repo-wide pre-existing debt, not this feature's surface — the build had never run to completion before (the crash masked every content warning). Fixing the toolchain unblocked docs builds for the whole repo. The alias suppressions are enumerated/lookahead-guarded so they cannot mask a real class (`ManualId`, `RegistryManualId` excluded).
