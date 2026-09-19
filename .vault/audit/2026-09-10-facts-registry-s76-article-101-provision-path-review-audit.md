---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:68848057a386978ad02d20515419d8cf195c2d36ca42f6b1fae1428f787584dc'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` audit: `s76 article 101 provision path review`

## Scope

Reviewed the six exact BOE Article 101 redactions and their six source
declarations that claim `provision_excerpt`. The audit checked the canonical
filename signal, source-path alignment, retained byte count and SHA-256 pins,
and absence of a retired on-disk alias. The fact identities, source IDs,
citations, legal reference, text, temporal windows, and legal effects were
excluded because this is a path-only evidence repair.

## Findings

No critical, high, or medium findings. Each source now names a provision-suffixed
`-art-101-` capture. `verify_source_file` accepted all six registered sources,
including the declared corpus-tier check and the recorded hash and byte pins.
No `-a101-` capture remains on disk.

### cross-domain-receipt | low | The full catalogue gate did not produce a terminal receipt

`dev/registry/tests/test_catalogue_verification_catalogues.py` was invoked but
could not return a terminal result while the shared host was saturated by other
Python work. The completed direct validator is the production code that checks
the repaired source declarations, but it is narrower than the cross-domain
authority proof. The plan step remains open.

## Recommendations

Re-run the full catalogue/authority proof after the shared host can return a
terminal test receipt, then close S76 only if that broader validation passes.
