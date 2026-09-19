---
tags:
  - '#reference'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:33419c5bf68bef68b04a7e87cedb5d5cf5f022b9aa8b2fe5fd6beb089844fb3d'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# `facts-registry` reference: `Facts registry legal-parameter consumer migration reference`

## Summary

The current legal-parameter adapter is not a valid temporal fact authority:
it projects static strings with an unbounded filing-period window. It must not
be used to migrate a filing-grade consumer. The accepted destination is the
flat one-fact-per-file catalogue under `aeat/facts`; its existing
`authored-facts` provider is the sole resolution lane once a fact is moved.
The adapter must cease publishing that fact at the same time, because catalogue
construction refuses duplicate fact identities.

Each migrated fragment needs an explicit filing-period window, exact legal
redaction evidence, a hash-pinned bounded source reference, and required-text
citation. A consolidated source with an unbounded applicability range does
not prove that a historical value held throughout a claimed window. The facts
validator must therefore prove source coverage of every variant window, while
the resolver continues to refuse a date, axis, or selector that has no exact
match.

`_objective_estimation_advisory.py` reads four scalar thresholds, compares them
against declared profile values, and emits advisory findings. Its filing year
is the appropriate fact coordinate; the migrated result must preserve the
resolved legal references and the existing 2016--2026 advisory limit.

`retencion_parameters.py` builds frozen domain records for RIRPF art. 95 and
LIRPF art. 101. The public records and their decimal fields remain, but their
values and legal references resolve from scalar fact results at a filing-period
coordinate. Resolution occurs in its loaders, never during module import, to
avoid a registry-to-domain import cycle.

`tipo_actividad_partitions.py` resolves the four RIRPF art. 95 entity sets and
the three RIRPF arts. 109 and 110 entity sets through the facts authority.
Each retains typed Modelo 036 token validation. No legal-parameter fallback is
permitted: an unknown, absent, malformed, or unresolved selector must refuse
rather than become an empty partition.

Focused tests live beside the facts authority, objective-estimation advisory,
and transaction domain. They must retain normal parity, inclusive temporal
boundaries, pre-window and post-window refusal, malformed value or token
refusal, source and legal provenance propagation, and evidence-window mutation
rejection. No migration may turn a registry load or resolution failure into a
missing rate, zero, or a completed filing-grade result.
