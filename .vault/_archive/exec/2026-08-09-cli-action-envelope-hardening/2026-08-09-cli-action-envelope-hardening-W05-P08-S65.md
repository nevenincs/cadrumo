---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d4a4c432d3f17ff719f7162c90f7fc88b0b1900cdb8e5f93c29cc7cf0efb19bd'
step_id: 'S65'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# After the atomic S33/S89 producer-consumer cutover and every S41, S38, S94, S114, and S117 consumer is proven removed, normalize ancillary core optional-extra and external-constants failures to locale keys and machine facts then delete raw install and repair prose plus install_hint with no application import or compatibility alias

## Scope

- `src/cadrumo/core/_optional_extras.py`
- `src/cadrumo/core/external_constants.py`
- `dev/quality/cli_action_census_dispositions.toml`

## Description

- Delete the optional-extra install-command property, its error attribute, and the English refusal message.
- Construct the missing-extra refusal from the registered error code's translation key and machine facts.
- Normalize the malformed Pre303 configuration refusal to section identity, a validity fact, and the failing error's type.
- Drop the now-unreachable install attribute from the CLI exception-view scrub.
- Sweep every consumer in one change: three test surfaces, two packaging harness modules, the browser doctor, and the census dispositions.

## Outcome

- The optional-extra refusal carries no rendered install command anywhere in the tree; the only remaining occurrences are other steps' census rows, one stale test function name, and the guard asserting the prose is absent.
- The refusal's operator text is now the registered error code's own translation key, so it renders through the same catalogue every other registered error uses and no new locale leaf was required in any of the four catalogues.
- Definition and CLI scrub now agree: the constructor emits exactly what the exception-view previously had to substitute, so that projection became idempotent rather than corrective.
- The malformed Pre303 refusal no longer copies the validation message; it carries section identity, a false validity fact, and the error type, matching the shape its consumer already projected.
- The packaging harness anchors on the extra's identity rather than its install string, so the lane still fails closed if the registry drifts.
- Both step-owned census dispositions were removed because the sites they described no longer exist.
- The step-owned gates pass 43 tests serially, and the affected modules are lint-clean.

## Notes

- One consumer test asserted the install command WAS present in operator output. It now asserts the extra's identity is named and the install prose is absent. This is a deliberate behavioural change this step mandates, not a weakened assertion.
- A separate stale assertion on the deleted suggestion envelope field was raising rather than checking; it was absorbed here and now asserts the resolved action projection.
- Execution was interrupted by an unrelated repository-wide merge that left 142 unmerged paths and broke collection for every campaign. One core facade conflict was resolved additively after confirming the symbol was defined, exported, already present in the facade's export list, and consumed by two modules. The remaining conflicts were resolved by their owners; no other campaign's conflict was touched.
- The census disposition gate remains red on stale owners belonging to the censo parser, inventory, live and modelo export surfaces. Those are other steps' migrations and are recorded here as unrelated peer churn rather than absorbed.
- The MCP agent-extra refusal is a separate hand-rolled path outside this step's declared scope and was left unchanged; its test function name still mentions the deleted concept.
- S65 remains open for independent review.
