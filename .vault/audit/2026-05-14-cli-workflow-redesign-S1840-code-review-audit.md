---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---



# `cli-workflow-redesign` Code Review

S1840-001 | MEDIUM | Citation CLI tests lock the current CLI-local payload instead of the application report contract
`test_citations_list_emits_json_payload_through_root_format` and `test_citations_show_emits_text_and_json_payloads_through_root_format` exercise the cached root CLI with a real temporary normative corpus, but their JSON assertions only cover fields already produced by the current direct-domain implementation in `_registry_corpus.py`. They do not assert backend-owned topic-backed fields such as `topic_count`, `topics`, `topic_slugs`, or `related_topics`, so the tests still pass while the CLI bypasses `aeat.application.registry` entirely. The `citations show` assertion is more constraining: it requires a top-level `cite`, while the typed `RegistryCitationShowReport` places citation text on `articulo.cite` and exposes `related_topics`. That makes the S1840 test suite a weak guard against backend disconnection and can force S1841 either to preserve a CLI-local compatibility shape or to fail these tests when the handler is correctly reduced to a thin adapter over the application service.
