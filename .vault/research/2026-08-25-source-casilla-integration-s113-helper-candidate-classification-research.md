---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e916b523bb2feeb5eb1d93cf962393ebcd0aeb559113b92f8d3f100e0720ea9e'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` research: `s113 helper candidate classification`

The S112 helper drift added `revision_selection_coordinates` and
`portal_integrity_error` to the structural helper inventory. Neither has the
source fact, grain, registry destination, source kind, secure owner, resolver,
or persistence lifecycle needed to become a source-connectivity candidate. The
accepted connectivity ADR already governs the resulting closed-vocabulary
classification; this research therefore does not create a second ADR or alter
the census.

## Findings

### The temporal helper enumerates declared coverage coordinates, not facts

`revision_selection_coordinates` reads only one already-loaded
`ModeloRevision.period_selector` and the caller-supplied registry coverage
horizon. It returns `(filing_year, declared_period_token)` pairs; it neither
loads observations nor identifies a binding source, casilla semantic role,
source reference, resolver, or secure repository. It was introduced by the
registry temporal-coverage change in commit `915a66a5bc`.

Its three production use-sites repeat validated selection coverage: the
registry model-law and construct-evidence ledgers, the temporal coverage
projection, and the filing-export coverage projection. The latter passes the
coordinates into law-selected snapshots to verify a revision's official layout
coverage; it does not derive a source value from them. Treating this helper as
a source candidate would confuse a selector-denominator proof with a source
domain and create a fabricated fact-to-destination relationship.

### The portal helper constructs a safety refusal, not an input carrier

`portal_integrity_error` builds a `PortalIntegrityError` carrying a closed
portal invariant and application-state safety classification. Its accepted
facts are portal identifiers, counts, boolean invariant results, a modelo
identifier, revision identifier, or an exception type. None is a taxpayer or
filing value, and the factory has no binding source, casilla destination,
source reference, resolver, encrypted repository, provenance, replay, or
export path. Commit `395b83a8a9` introduced that terminal-refusal authority.

The generic helper detector finds the factory only because the portal package
re-exports it and its `Mapping[str, str | int | bool]` annotation appears in
the syntax walk as `BitOr`. That detector evidence is deliberately structural;
it is not proof that the function performs an economic calculation or owns a
source.

Every production caller in the portal registry raises it when assembling or
cross-checking portal catalogue metadata: duplicate or missing entries,
invalid replacement pointers, consumer enum/id mismatch, or an unavailable
registry application-link lookup. The application-link lookup is an integrity
guard around navigation metadata, not a binding/value resolver. A candidate
based on its mention of a modelo or revision would therefore substitute
operator-surface failure facts for a source lifecycle.

### Existing connectivity governance is sufficient

The accepted source-connectivity ADR requires a candidate to have official
evidence for modelo/revision, target semantic role, source fact, aggregation,
grain, and full production lifecycle; it expressly rejects lexical or
structural discovery as an authority to author a binding. Neither identity
meets that entry predicate. The existing closed disposition vocabulary already
contains `not_applicable`; no new architectural choice or ADR is needed.

The evidence supports handing both identities to S115 as `not_applicable`
structural helpers. S115, not this research, owns any later explicit census row
and selector-digest update. This inquiry intentionally did not investigate
individual portal endpoints or modelo casillas because neither helper carries a
source fact to map to either surface.

## Sources

- `2026-08-22-source-casilla-integration-adr.md`
- `2026-08-22-source-casilla-integration-W06-P20-S112.md`
- `src/cadrumo/domain/calculations/registry/_temporal.py:32`
- `src/cadrumo/domain/calculations/registry/_coverage.py:379`
- `src/cadrumo/application/registry/_temporal_coverage.py:207`
- `src/cadrumo/application/registry/_filing_export_coverage.py:107`
- `src/cadrumo/domain/portals/_errors.py:148`
- `src/cadrumo/domain/portals/_registry.py:134`
- `src/cadrumo/domain/portals/__init__.py:51`
- `src/cadrumo/domain/portals/tests/test_terminal_preconditions.py:42`
- `src/cadrumo/application/registry/source_connectivity.py:68`
- `dev/source_connectivity/discovery.py:548`
- commit `915a66a5bc`
- commit `395b83a8a9`
