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
  - '[[2026-05-14-cli-workflow-redesign-s1840-code-review-audit]]'
---



# `cli-workflow-redesign` Code Review

No findings.

Reviewed the combined S1840/S1841 remediation against the registry corpus ADRs and plan rows. The prior S1840 concern about locking a top-level `payload["cite"]` shape is remediated: the CLI assertions now target the typed application report shape with `articulo.cite`, `related_topics`, and reference `topic_slugs`. The registry corpus CLI delegates to application registry commands and services, uses `_emit`, and keeps only option parsing plus local text-line rendering in the entrypoint layer. Focused verification passed with `uv run pytest src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/application/registry/test_corpus.py`.
