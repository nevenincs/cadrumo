---
tags:
  - '#adr'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-18'
body_hash: 'sha256:6b8da08c2ad01270b3347659b904d4c18bc2975df4fd7e774c2e3aef781f7133'
related:
  - "[[2026-07-18-cli-authority-quality-backlog-research]]"
---

# `cli-authority-quality-backlog` adr: `S27 clave-diagnostics namespace authority: storage registry is canonical` | (**status:** `accepted`)

## Problem Statement

Plan step `P03.S27` flagged the clave-diagnostics secure-storage namespace values
as split across incompatible authorities. The dotted namespace string
`"cadrumo.outbound.aeat.auth.clave_movil.diagnostics"` (and its `.clave_permanente.`
sibling), plus the `SessitivityClass.SESSION` classification and `schema_version=1`,
are declared at four tiers: a `Final[str]` in `core/external_constants.py`; the
`SecureObjectNamespaceDefinition`s in the adapters storage
`_namespace_registry.py` whose `.namespace` strings raw-duplicate core; a raw
literal in `_clave_permanente_support.py` with no core symbol at all; and raw
`SESSION`/`1` literals in `_clave_movil_page_flow.py` duplicating the registry
def's `.sensitivity`/`.schema_version`. The step required deciding the single
authority and single-sourcing every consumer. The decision was blocked on an open
layering question (may an `adapters.outbound` module import a namespace def from
`adapters.persistence.storage`?).

## Considerations

The grounding research resolved the layering question decisively: the edge is
intra-layer (both are `cadrumo.adapters`), no `.importlinter` contract forbids it,
and it is the established production pattern for every other secure-object
namespace (the LLM usage/cache/telemetry stores, the AEAT session store, the sede
observation store). The file carrying the raw literals already imports the
secure-object repository from `persistence.storage`, so no new coupling is
introduced and there is no circular-import risk. A secure-storage namespace is
storage-structural metadata, not an AEAT regulatory value, so it does not belong
in the modelo registry TOML nor on the regulatory `external_constants` surface.
The application-layer sibling already sources namespace, sensitivity, and
schema_version from the registry def.

## Considered options

- **Option 1 (chosen): the storage registry `_namespace_registry.py` is the single
  authority.** The `SecureObjectNamespaceDefinition` is canonical for namespace,
  sensitivity, and schema_version; auth consumers import the def from the storage
  package facade; the core symbol is deleted. Pros: matches all sibling
  secure-object precedent and the app-layer consumer, unifies three co-varying
  values in one typed record, no layer violation. Con: introduces a
  same-layer import into two currently core-sourcing support modules (trivially
  precedented).
- **Option 2 (rejected): core is authority, the registry def sources its
  `.namespace` from core.** Inverts the natural ownership of storage-structural
  metadata, still leaves sensitivity/schema split between core and the registry
  def (does not fully single-source), and contradicts the S06-S08 direction.
- **Option 3 (rejected): a new core `StrEnum` for namespaces.** Over-engineered
  for a free-form dotted string that the CLI never renders as a choice, and still
  would not home sensitivity/schema.

## Constraints

Execution touches `core/external_constants.py` (delete the symbol) and the
clave-diagnostics consumers (`_clave_movil_support.py`, `_clave_movil_page_flow.py`,
`_clave_movil.py`, `_clave_permanente_support.py`, `auth/__init__.py`) plus their
tests, and lands as one atomic explicit-path commit. A working-tree check at
adjudication time confirmed all seven files are clean: the operator's active P04
door is the CUSTODY/master-key surface (`user_profile/_custody.py`,
`_config/_custody_secret.py`, `_config_payloads.py`, `_config/_secure_input.py`,
`storage/master_key/_master_key.py`) — a different subsystem from the
clave-diagnostics files. The earlier deferral assumption (that the clave files
were the door surface) was incorrect; execution therefore proceeds without door
collision, guarded by a per-file git-diff gate that aborts if a peer edit lands.

## Implementation

Under Option 1 the storage registry def is already canonical and needs no change.
The auth support modules stop importing the core string and instead read
`.namespace` off `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` /
`CLAVE_PERMANENTE_DIAGNOSTICS_NAMESPACE` obtained from the storage package's public
facade; the page-flow reads `.sensitivity`/`.schema_version` off the def instead
of raw literals; the core `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` symbol and its
re-exports are deleted (delete-not-alias). A parity assertion that each auth
consumer resolves to the registry def's declared values guards against
regression, mirroring the write-path binding test landed for the filed-observation
store in S08.

## Rationale

Option 1 is not a novel ruling but the completion of a decision the phase already
made: S06-S08 (task #68) established the storage registry as the sole metadata
authority and bound the profile, calculation, aggregation, and filed-observation
repositories to it. The clave-diagnostics case is the last consumer still sourcing
from core. Choosing the registry keeps namespace, sensitivity, and schema_version
in one typed record, matches every sibling secure-object store, and — with the
layering objection disproven — carries no architectural cost.

## Consequences

Gains: a single typed authority for the clave-diagnostics namespace metadata; the
four-tier duplication (including the raw `SESSION`/`schema_version` literals) is
eliminated; the auth consumers converge on the same pattern as the rest of the
codebase. Deferred: execution waits for the P04 door, so S27 remains
decision-complete but execution-pending until the auth zone quiesces. Surfaced
follow-up: the `clave_permanente` diagnostic namespace appears to have no
`.save()` consumer (a possibly-dormant declaration), which the execution sweep
should confirm and either wire or remove.
