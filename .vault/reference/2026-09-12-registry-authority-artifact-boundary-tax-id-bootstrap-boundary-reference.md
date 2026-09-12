---
tags:
  - '#reference'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:8234a5101b7effd3a818721948e90c24ff2d1bbb67c5de3bc90ffd45dfa6b10b'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
---
# `registry-authority-artifact-boundary` reference: `tax id bootstrap boundary`

This reference traces the current Spanish tax-identifier migration from authored
fact `0102` through development compilation, artifact decoding, runtime resolution,
and the low-level package-resource bootstrap. The semantic index was unavailable
because the installed client and service versions disagree, so the trace is grounded
in exact symbol searches, full-file reads, the live diff, and direct clean-process
imports.

## Summary

The live migration correctly moves the Spanish identifier width, prefix, leader,
NIF/NIE checksum, and CIF control declarations into the authored governed fact
`src/cadrumo/_data/registry/aeat/facts/0102-spanish-tax-identifier-format.toml`.
`src/cadrumo/domain/calculations/registry/tax_id_format.py` then resolves that mapping
from `bundled_authority()`. This removes the closed tables formerly held by
`src/cadrumo/core/identity/documents.py`, but it also makes a core validator depend on
the runtime registry it helps construct. Deferring the call inside
`_tax_id_format_declarations()` and exposing `SPANISH_TAX_ID_WIDTH` through module
`__getattr__` changes when the cycle closes; it does not establish a valid bootstrap
boundary.

The dependency path is concrete. `dev/registry/pipeline/cli.py` imports
`cadrumo.core.i18n.render`; `src/cadrumo/core/i18n/render.py` imports `config`,
`config_state_root`, and `product_identity`; `src/cadrumo/core/config_state_root.py`
imports `PRODUCT_IDENTITY`; `src/cadrumo/core/product_identity.py` imports
`SubjectTaxId`; `src/cadrumo/core/identity/tax_id.py` imports
`_tax_id_format_declarations`; that helper imports
`src/cadrumo/domain/calculations/registry/tax_id_format.py`; the query imports
`authority`; and `src/cadrumo/domain/calculations/registry/authority.py` imports
`core.resources.bundled_data`, which imports `PRODUCT_IDENTITY` again. A plain import
currently happens to complete because the registry edge is delayed until validation,
but any model validation or width access during authority construction re-enters the
same graph.

There are two distinct bootstrap defects behind that path:

- `src/cadrumo/core/product_identity.py` combines genuinely import-light product
  metadata with `AeatProductSoftwareIdentity`, whose `developer_tax_id` field is the
  checksum-bearing `SubjectTaxId`. Every package-resource lookup therefore imports the
  tax-ID validation stack even though `bundled_data.py` needs only
  `PRODUCT_IDENTITY.python_package` and `PRODUCT_IDENTITY.companion_namespace`.
- Registry schema construction itself is authority-recursive.
  `src/cadrumo/domain/calculations/registry/schema_scalars.py` imports
  `validate_spanish_tax_id` and binds it into `NifString`. The artifact decoder calls
  `RegistryCatalogues.model_validate` in
  `src/cadrumo/domain/calculations/registry/authority_artifact.py`, while the
  development compiler constructs the same typed schema graph. Validating a `nif`
  scalar at either boundary can query `bundled_authority()` before the candidate or
  artifact being validated has become an authority. In development this additionally
  validates a new candidate against the old published artifact, so changing fact
  `0102` cannot reliably govern the candidate that declares it.

The accepted architecture requires a staged, explicit dependency rather than a local
fallback or a lazily hidden global query. Stable representation belongs below the
registry; regulated membership and checksum declarations belong in the candidate or
published authority.

## Recommended architecture cut

### 1. Make the package-resource root genuinely import-light

Keep `ProductIdentity`, `PRODUCT_IDENTITY`, and
`normalise_product_identity_references` in the canonical public product-identity
module, with imports limited to the standard library. Relocate
`AeatProgramIdentifier`, `AeatProductSoftwareEvidence`, and
`AeatProductSoftwareIdentity` atomically to a separate public defining module and
update every direct consumer, including `dev/registry/pipeline/m390_auxiliary_envelope.py`.
Do not re-export them from `product_identity.py`: the architecture rules prohibit a
forwarding compatibility surface. After that split,
`src/cadrumo/core/resources/bundled_data.py` can import product metadata without
loading Pydantic, digest models, or tax-ID validation.

This is the smallest import-graph cut, but it is not sufficient by itself. It prevents
resource discovery from closing the circle; it does not make candidate compilation or
artifact decoding independent of a pre-existing runtime authority.

### 2. Separate syntax mechanics from authority-owned declarations

Define one immutable, bootstrap-safe tax-ID format value in the core identity package.
Its Python type may declare field names and structural invariants, but no field value:
width, country prefix, leader sets, substitution digits, checksum-letter table, and CIF
control partitions remain data supplied by fact `spanish-tax-identifier-format`.
Place the normalization and checksum arithmetic in pure functions that take this
typed format explicitly. They must perform no registry import, file access, cache
lookup, or implicit provider registration.

Retain only stable lexical construction below the authority boundary: canonical
string normalization and a syntax-only identifier value must not claim that a token is
a currently valid Spanish NIF/NIE/CIF. A checksum-valid subject type or validation
operation must receive the typed format explicitly, or live at an authority-aware
domain/application boundary. Do not restore the removed constants, embed a default
format in Python, or make a missing format silently fall back to the 2025 values.

The current `core.identity.documents -> domain.calculations.registry.tax_id_format`
dependency must disappear. A core module cannot reach upward into the registry, even
through a function-local import. `tax_id_format.py` may remain the runtime query seam,
but it should adapt a fully loaded `ValidatedRegistryAuthority` result into the pure
core format value and invoke the pure kernel, not be called by that kernel.

### 3. Bootstrap candidates and artifacts in two explicit stages

Development publication must compile the authored fact catalogue first, select
`spanish-tax-identifier-format` for the candidate's effective coordinate, validate its
mapping into the typed format value, and then pass that value explicitly while loading
Modelo schema values. The compiler must never consult `bundled_authority()` for this
step. The central loader/model-construction seam is the correct injection point; avoid
ambient mutable globals or a process-wide callback because concurrent candidate
validation would otherwise cross-contaminate authorities.

Artifact reading needs the corresponding two-stage decode. First verify the envelope
and digest and decode the governed-fact catalogue independently. Resolve and validate
the embedded tax-ID format. Then validate/reconstruct Modelo definitions and the rest
of `RegistryCatalogues` with that explicit format in Pydantic validation context (or
through an equivalent explicit decoder parameter). Only after the complete typed graph
passes may `ValidatedRegistryAuthority` be constructed and cached. A missing,
ambiguous, temporally inapplicable, or malformed tax-ID format makes the artifact
unreadable; it must not trigger source compilation or reuse a previously cached
format.

`src/cadrumo/domain/calculations/registry/schema_scalars.py` is the immediate consumer
to change: `_validate_nif_string` must read the explicitly supplied candidate/decode
context and call the pure validation kernel. Calling `bundled_authority()` from that
validator is recursive by construction. Runtime business validation can resolve the
format from an already loaded authority at its composition boundary, but schema
reconstruction and development compilation cannot.

### 4. Preserve one authority after bootstrap

`src/cadrumo/domain/calculations/registry/tax_id_format.py` should expose authority
queries over an authority instance or an already established bundled authority. Its
result must be the same typed format used by the compiler and decoder. Fact `0102` is
the sole owner of operative values, and the generated authority artifact is their sole
runtime carrier. `SPANISH_TAX_ID_WIDTH` cannot remain a context-free module constant
or module `__getattr__`: callers such as
`dev/registry/conformance/tests/test_registry_schema_part1.py` must derive width from
the candidate authority/format they are testing.

## Implementation map

- Split the software-envelope models out of `src/cadrumo/core/product_identity.py` and
  update their direct imports. Keep `src/cadrumo/core/resources/bundled_data.py` on the
  lightweight metadata module.
- Introduce the immutable format value and pure validation kernel beside
  `src/cadrumo/core/identity/documents.py`; remove `_tax_id_format_declarations`, the
  domain import, and the module-level width indirection from the core identity layer.
- Change `src/cadrumo/core/identity/tax_id.py` so syntax normalization remains
  bootstrap-safe and checksum validation receives a format/authority at the owning
  boundary. Migrate `SubjectTaxId` users atomically according to whether they require
  only canonical identity syntax or an authority-backed Spanish checksum claim.
- Adapt `src/cadrumo/domain/calculations/registry/tax_id_format.py` to project fact
  `0102` into the typed format and to provide explicit authority-backed validation for
  ordinary runtime workflows.
- Compile fact `0102` before Modelo loading in `dev/registry/compiler/` and thread its
  typed projection through the central loader into
  `schema_scalars._validate_nif_string`.
- Decode facts before NIF-bearing schema members in
  `src/cadrumo/domain/calculations/registry/authority_artifact.py`, supplying the same
  explicit context during typed reconstruction. Keep digest verification and
  `runtime.require_complete()` fail-closed behavior unchanged.
- Remove every candidate/compiler use of `SPANISH_TAX_ID_WIDTH`; derive it from the
  candidate format. Search all `SubjectTaxId`, `validate_spanish_tax_id`,
  `validate_identity`, and `nif_check_letter` consumers and classify their required
  authority explicitly rather than preserving an implicit runtime singleton.

## Verification blueprint

- Add a clean-process import test for `dev.registry.pipeline.cli` with
  `cadrumo.domain.calculations.registry.authority` and the artifact reader made
  unreachable. Import and Typer command construction must succeed, proving publisher
  startup needs no runtime authority.
- Add a resource-bootstrap test importing `core.resources.bundled_data` and resolving
  the artifact path while asserting that `core.identity.tax_id`, registry authority,
  and registry schema modules were not imported.
- Extend `dev/registry/tests/test_authority_publication.py` with an isolated candidate
  whose fact `0102` differs from the installed artifact. A NIF accepted only by the
  candidate mapping must validate and publish; one accepted only by the old artifact
  must be refused. This proves candidate ownership rather than mere successful lookup.
- Extend `dev/registry/tests/test_authority_artifact_round_trip.py` and
  `src/cadrumo/domain/calculations/registry/tests/test_authority_artifact.py` with a
  self-contained artifact carrying its own tax-ID format and a NIF-bearing schema
  value. Decode it with `bundled_authority()` unavailable. Mutating or removing a
  required declaration, with the digest recomputed through the canonical writer, must
  fail typed decoding rather than recurse or fall back.
- Extend
  `src/cadrumo/domain/calculations/registry/tests/test_bundled_authority_artifact_runtime.py`
  to prove missing/corrupt tax-ID declarations refuse on every call and never reach
  authoring inputs. Preserve the existing missing/corrupt artifact and no-source-
  fallback probes.
- Refactor `src/cadrumo/core/identity/tests/test_documents.py`,
  `src/cadrumo/core/identity/tests/test_tax_id.py`, and
  `src/cadrumo/domain/calculations/registry/tests/test_nif_data_type.py` so fixtures
  inject the typed format. Include NIF, prefixed NIF, NIE, digit-only CIF,
  letter-only CIF, mixed CIF, width, prefix stripping, missing-key, malformed-table,
  and checksum-refusal cases.
- Add an anti-fallback test that changes every table/leader value from the familiar
  Spanish literals and proves the pure kernel follows the supplied format. A test that
  uses only the current values cannot detect a hidden Python fallback.
- Run import-boundary tests, the full core identity suite, registry schema tests,
  publication tests, artifact round-trip/runtime tests, and an installed artifact-only
  CLI workflow. The final installed test must remove authoring TOML and still validate
  tax IDs from the artifact, while the development publisher test must start with the
  runtime artifact absent.

## Current-state risks

The tracked source fact contains the complete declaration set in the live diff, but a
successful source compile or a successful import does not prove the boundary. The
current lazy lookup can read a stale artifact while compiling a changed candidate, and
artifact reconstruction can recursively request the authority it is constructing.
The current published artifact and source fact carry the same fourteen declaration
keys, so the immediate defect is not a missing projection. The source citation requires
only a generic NIF-identification phrase, however; it does not substantiate
the detailed widths, leader partitions, prefix substitutions, or checksum tables.
Those operative values still need evidence at the exact granularity claimed before the
migration can be treated as filing-grade grounding.

The current artifact decoder validates `modelos` before `catalogues`. No NIF-bearing
artifact member is known to trigger the recursive validator during ordinary decoding
today; the observed immediate re-entry is software-identity construction. The proposed
catalogue-first/context-aware decoder is nevertheless required before a NIF-bearing
schema field can safely participate in artifact reconstruction and is the durable
boundary the compiler and reader should share.

The module `__getattr__` for `SPANISH_TAX_ID_WIDTH` also preserves a context-free API
for a context-dependent authority fact and introduces a package-level dynamic lookup,
which conflicts with the repository's canonical-definition and inert-surface rules.

No production edit should be made from this reference alone without preserving the
concurrent work already present in the identity, publisher, source-fact, and authority
surfaces.
