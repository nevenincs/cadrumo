---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---



# `cli-workflow-redesign` Code Review



S1834-001 | MEDIUM | Citation article misses bypass registry structured error logging
`show_registry_citation` only wraps `find_reference` in the structured warning block, then calls `find_articulo` outside that block. A missing or invalid `--articulo` therefore raises `NormativeNotFoundError` without the S1834 registry service log fields such as `registry_service`, `registry_normative_id`, and `registry_articulo`, even though a missing normative id does emit them. This leaves one operator-facing citation lookup failure path outside the central registry logging contract.

S1834-002 | MEDIUM | Unsupported locale raises without registry error context or log fields
`_registry_topic_locale` raises `RegistryApplicationInputError` for an unsupported locale without `context` and without a structured registry warning. The new tests only assert that the exception type/message is raised, while the central envelope test constructs a different error manually with context. As implemented, the real locale refusal produces `REFUSED_APPLICATION_REGISTRY_INPUT` but loses registry service fields in the central error envelope and emits no registry log event, which is contrary to S1834's requirement to record registry service errors and log fields through the central drivers.

S1834-003 | LOW | Unsupported locale structured logging remains unguarded by tests
The patched `_registry_topic_locale` implementation now emits a structured warning with `registry_service`, `registry_locale`, and `registry_allowed_locales`, and the real raised error now carries central envelope context. However, `test_topic_projection_rejects_unknown_locale_with_application_error` only asserts the envelope fields. It would still pass if the `_LOGGER.warning` block were removed or if its structured `extra` fields drifted, unlike `test_citation_missing_article_uses_structured_registry_logging`, which directly guards the citation remediation with `caplog`. Add a locale refusal `caplog` assertion so both prior S1834 logging remediations are regression-protected.

S1834-RESOLUTION | INFO | S1834 review findings remediated
S1834-001 is remediated by wrapping citation article lookup in the same structured warning path as reference lookup and by adding a real-loader missing-article test that asserts `registry_service`, `registry_normative_id`, and `registry_articulo`. S1834-002 is remediated by adding context and structured warning fields to unsupported locale refusals. S1834-003 is remediated by adding `caplog` assertions for unsupported locale logging. Verification passed with ruff, ty, locale audit, the focused registry corpus suite, and the broader registry/error boundary slice.
