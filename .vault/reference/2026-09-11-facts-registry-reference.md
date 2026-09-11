---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:9c64d8234f3a14701ab0fea98388e3ee06b3a937f6156b530254ed5cdcecb9ba'
related: []
---

# `facts-registry` reference: retired global legal-parameter provider

The accepted governed-fact ADR, the active plan, the shared-catalogue loader,
its schema, and focused loader tests were examined after the last raw
`[parameters.*]` declaration was removed from the legal corpus.

## Summary

`RegistryCatalogues.parameters` is the retired global legal-parameter provider,
not the live `ModeloRevision.parameters` family. No production consumer remains
for the former, while the latter remains the modelo-owned schema described as
out of scope by the ADR.

The retired boundary consists of `LegalParameter`, the top-level catalogue
field, shared legal-fragment parsing and reference validation, and their
dedicated loader tests. Removing all of them makes `[parameters.*]` invalid
rather than silently accepted. The active fact migration gate remains required,
but its terminology should be renamed from legal-parameter migration to fact
retirement as part of the same deletion step.

The published authority artifact is CLI-owned. It must be regenerated after
the schema change; a stale artifact must fail validation, never be adapted or
accepted through a compatibility reader.
