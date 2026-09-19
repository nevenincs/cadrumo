---
tags:
  - '#reference'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:d26da9445ce2a86db228ae2c3ad569e95a889a8c60b17e63063a2b9b8f8a0470'
related:
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---

# `registry-edition-authoring` reference: `maintained tooling boundary`

## Summary

The compiler, conformance, registry health, publication and generated-target checks remain the maintained correctness path. They do not import the raw delta/chain campaign reports. The reports and their root/coverage ledgers were a separate campaign worklist, not authority validation.

Dependency tracing found one maintained helper inside `edition_delta_status`: `edition_token_in_identifier`, used by `bindings.audit`. It moves without behavioral changes to `dev/registry/identifier_edition.py`. The report's other reusable caller was the retired identifier-rename campaign itself, so its supported-year helper does not need another home.

The binding provider-shape converter and row-set fixer target rejected legacy schema shapes. Their dedicated tests and commands retire; the current provider-registration corpus gate stays and obtains its root from `bundled_path`. The identifier-rename campaign has no maintained runtime/tool callers. Two independent official-design provenance tests move out before its test suite and oracle fixture retire.

The result-disposition fragment writer hardcodes campaign ownership of Modelos 303 and 390 and bulk rewrites authored fragments. It retires with its commands and dedicated test; `derive_result_dispositions` and official-design parsing remain.

`strip_restated_bindings`, `lift_family_source_defaults`, `corpus_write`, the current-schema compaction/proof tools, scaffold tooling, the lineage adjudication workflow and real validation gates remain. These accept current declarations or enforce current correctness; lacking a production import does not by itself make an authoring tool obsolete.

All deletions have exact backups and hashes in `.logs/audit-runs/2026-09-14/registry-tooling-retirement-backup.json`. Active command wiring and generated import-load metadata change with the modules. Historical vault records remain historical rather than being rewritten to pretend the tools never existed.
