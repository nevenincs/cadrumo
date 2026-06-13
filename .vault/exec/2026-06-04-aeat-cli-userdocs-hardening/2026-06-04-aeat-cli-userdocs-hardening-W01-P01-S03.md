---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W01.P01.S03` execution

Scope: Compare generated CLI reference command count and paths with the live CLI leaf tree.

## Description

- Collect the live CLI leaf paths through the project CLI reference helper.
- Compare the live count with the generated reference count observed in `docs/cli/index.rst`.
- Run the CLI reference generator against `docs` to confirm the generated output can refresh to the live tree.
- Verify the five previously missing leaves appear in the refreshed generated output.

## Outcome

Completed. The live CLI reports 193 leaf commands. The refreshed generated reference includes `ledger.doclink`, `ledger.providers`, `modelo.m036.alta`, `modelo.m036.modificacion`, and `modelo.m036.baja`.

## Notes

`docs/cli/` is ignored by git and not tracked in HEAD. The generator updated local ignored files, so the durable tracked mitigation is the plan finding and the follow-up decision about whether generated CLI reference output should remain ignored build output.
