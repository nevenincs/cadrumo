---
name: 2026-04-17-modelo-inventory-remediation-phase2-setup-parity
description: Phase 2 execution record — setup and profile-authoring parity for modelo inventory remediation
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-modelo-inventory-remediation-plan]]"
  - "[[2026-04-17-modelo-inventory-remediation-adr]]"
  - "[[2026-04-17-modelo-inventory-remediation-research]]"
---

# `modelo-inventory` `phase2` `setup-parity`

Extended the setup and profile-authoring surface so generated profile JSON can express the same traits the deadline engine now consumes.

- Modified: `src/aeat/application/setup/_models.py`
- Modified: `src/aeat/application/setup/_wizard.py`
- Modified: `src/aeat/application/setup/_env_writer.py`
- Modified: `src/aeat/application/setup/test_cli.py`
- Modified: `src/aeat/application/setup/test_env_writer.py`
- Modified: `src/aeat/application/setup/test_models.py`
- Modified: `src/aeat/application/setup/test_verifier.py`
- Modified: `src/aeat/application/setup/test_wizard.py`

## Description

The setup flow previously collapsed multiple legal traits into a smaller profile shape, which would have reintroduced the audited parity gaps by emitting under-specified profile JSON.

- `SetupAnswers` now carries the professional-retention, `130` exception, and `347` threshold fields with safe `False` defaults for backward compatibility.
- The interactive wizard now prompts for those additional booleans instead of collapsing them into the old `has_employees` question.
- `write_profile_file` now writes the expanded `AutonomoProfile` so `aeat deadlines` and `aeat modelos year-plan` consume the same contract that the remediation tests enforce.

## Tests

The widened setup surface passed together with the affected integration consumers:

- `uv run pytest src/aeat/setup src/aeat/entrypoints/cli/deadlines/test_cli.py src/aeat/application/workflow/test_engine.py -q`
- Result: `62 passed`
