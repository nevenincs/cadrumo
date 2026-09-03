---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:a87ff9e2086cc9914d00c4c07d69dd6508f98387b59701396b5852ca26c17a31'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
## Scope

Reviewed the S398 immutable installed-workbench snapshot assembly, root-service injection, authoritative-return refresh, launcher composition boundary, and focused proof suite.

## Findings

### missing-installed-provider | high | The production child still has no authority that can build the installed root generation

Open. The launcher now accepts one immutable `InstalledWorkbenchRootInputsV1`
generation and correctly assembles search through the application-owned door,
but the actual `python -m cadrumo.entrypoints.tui` child has no production
provider. A bare child starts an honest uncomposed shell rather than claiming a
known-empty index, so `aeat --tui` no longer exits before mounting; it still
cannot expose real Home, destinations, or search. The missing producer cannot
be assembled from current public APIs: there is no declarations-lifecycle
producer, AEAT fact loader, Home input adapter, or bulk Modelo workspace loader.
Those application composition gaps must be filled before S384 can inject the
root provider and S398 can be credited as installed.

### stale-search-after-refresh-failure | high | A failed refresh must retain the last known-good generation and disclose no diagnostics

Resolved. A refresh exception leaves the exact last-good service installed and
sets only `workbench.search.refresh_unavailable`; protected exception text is
not retained or displayed. A successful later refresh atomically replaces the
service and clears the refusal.

### incomplete-search-denominator | high | Ledger evidence and Modelo were absent from the installed snapshot proof

Resolved. Sealed-revision Ledger drift now projects as the source-native stale
Ledger-evidence family, and the comprehensive input test includes a nonempty
Modelo projection. The document sequence covers Ledger entry/evidence,
declaration, calculation revision, filing, lifecycle history, reconciliation,
notification, and Modelo.

### pickleable-identity-seeds | high | Snapshot pickling could bypass field-level serialization exclusions

Resolved. `InstalledWorkbenchSearchSnapshotV1` is explicitly memory-only and
refuses Python pickle serialization. JSON/model serialization continues to
exclude every private identity basis, bucket coordinate, lifecycle fact ID,
and AEAT notification selection seed.

### installed-provider-source | medium | The subsequent installed-session composition must supply the required current-projection provider

The root join validates search/navigation admission parity and refreshes only
from the injected public-generation provider. This is the correct composition
shape, but not the installed producer itself. S398 remains **NO-CLOSE** until
the prerequisite application assemblers exist and S384 supplies the child-owned
provider.

## Recommendations

- Add the missing frontend-neutral projection assemblers before S384; do not
  construct raw cross-domain joins in the launcher.
- S384 should then supply one coherent child-owned provider at initial
  composition and authoritative child return.
- Preserve the honest uncomposed shell until that source exists; do not replace
  it with fixtures, inferred facts, or an empty index.

Final result: **NO-CLOSE**. The in-memory assembly and lifecycle contract are
sound, but the installed executable is not yet connected to a real current
root/search generation.
