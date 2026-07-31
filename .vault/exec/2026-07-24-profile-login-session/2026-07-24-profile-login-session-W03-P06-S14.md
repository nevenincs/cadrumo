---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:3d722b76e5860346c0fc02f1cbbe57795ef5567a1ccfc0fbb17cd13c518923f4'
step_id: 'S14'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Delete the switch command and config profile logout registrations and every removed spelling from the write-policy allowlist, error-registry default_suggestion fields, next_action builders, curated operator help, envelope identifiers, operator-harness documents, and MCP mirrors, verified by rg sweeps returning zero hits for the removed spellings plus the operator-harness drift gate green

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody.py`
- `src/cadrumo/entrypoints/cli/_config/__init__.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/entrypoints/cli/operator_surface/_help.py`
- `src/cadrumo/_data/agent`

## Description

- Delete the switch and profile-logout command registrations, their payload schemas, and their envelope identifiers.
- Delete the switch-only target resolver and pointer helper, and drop the resolver injection the registrar carried only for switch.
- Port the failed-target output-language pinning onto login so the behaviour moves with the door instead of being dropped.
- Sweep the surfaces the automated gates do not scan: error-registry suggestion fields, storage runtime and master-key and bucket refusals, the cross-period next-action builder, the curated operator help surface, and the sandbox, bundle, archive, and capabilities suggestions.
- Retarget the operator-surface risk table, mounted-family contract, identity gate, and bootstrap-exempt registry onto the new identifiers.
- Remove both retired verbs' locale keys and add the two new curated-help descriptions in all four catalogues through the locales CLI.
- Migrate every test invocation of the retired verbs onto the replacements.

## Outcome

Both retired verbs are gone from the command tree and both replacements resolve. Gates: 102 passed across locales, operator surface, identity gate, JSON-schema conformance, and documented-command conformance; 40 passed on the migrated config, inventory, and identity tests and 93 on the agent evaluation suite, both run serially. Ruff and ty are clean on every touched file.

## Notes

One regression was DELETED rather than retargeted, and needs owner confirmation: it asserted that switch reached a corrupt bucket database without the readiness relabelling. That contract has no subject verb left, because login authenticates and mints the session without opening the bucket database, and the only other candidate read verb deliberately owns the readiness pre-read the test asserts against. Retargeting it would have fitted the assertion to whichever verb happened to pass.

Three files carrying part of this sweep were left uncommitted because they are entangled with a peer's in-flight environment-override work: the bucket pointer reader, the bucket error module, and the custody profile lifecycle suite. The verb rename in those files still needs landing by whoever owns that change.

The runtime write-policy allowlist needed no edit. Neither retired verb was enrolled in it, and both replacements are bootstrap-exempt, which the policy short-circuits before the catalog is consulted, so there is no fail-open gap.

A parallel run of the migrated suites hit an xdist worker internal error. Re-running serially was green, so the failure was the worker crash and not the tests.
