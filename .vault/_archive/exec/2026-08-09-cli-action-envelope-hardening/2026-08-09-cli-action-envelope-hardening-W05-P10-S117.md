---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:bd910f9c3d1fe16f20a121163a55300c42726e075521342ba35d9de3ca1081bb'
step_id: 'S117'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Replace financial OFX optional-extra forwarding and notice consumers with typed machine facts and explicit no-recovery outcomes preserving capability classification without raw installation prose or wrapper compatibility

## Scope

- `src/cadrumo/adapters/inbound/financial/providers/_ofx.py`

## Description

- Add a typed optional-extra fact carrier to the shared provider validation result.
- Replace the OFX declining branch's rendered install command with the canonical extra identity triple.
- Delete the install-command prose from the OFX module and provider docstrings and from the tabular mapping lane's refusal rationale.
- Add a regression proving the declining probe carries facts and renders nothing.

## Outcome

- The OFX provider no longer reads `install_hint`; the financial adapters retain no consumer of it, so the prose fields are free to be deleted at their definition site under the ancillary core optional-extra step.
- `ProviderValidation` carries `unavailable_optional_extra` as the same `extra` / `import_name` / `importable` triple the provisioning probe and the evidence-reader refusal already use, so no second optional-extra vocabulary was introduced.
- Capability classification is preserved exactly: a source that clearly is OFX still raises the typed missing-extra error, and only a probe miss returns a declining validation.
- The declining branch now renders no operator prose at all; the downstream import reason falls through to its existing localized key rather than an English install command.
- No compatibility field, wrapper, or bridge was added, and the free-form warning channel shared with the other providers was left untouched as out of scope.
- The financial adapter suite passes 130 tests and the ledger import consumer selection passes 63, both run serially.

## Notes

- The anti-tautology argument for the new regression is structural rather than executed: restoring the previous branch inverts both assertions independently, because it repopulates the rendered warning tuple and leaves the fact carrier unset. A deliberate break-and-restore was not performed.
- The shared free-form `warnings` channel remains the prose surface for the CSV, XLSX, tabular-mapping and PDF providers. Migrating it is a larger boundary change than this step declares and is recorded here as a carry-forward rather than absorbed.
- The tabular mapping lane's docstring was corrected in the same commit because it described the same install-prose behaviour this step removes; its code path already re-raised the typed error and was not changed.
- S117 remains open for independent review.
