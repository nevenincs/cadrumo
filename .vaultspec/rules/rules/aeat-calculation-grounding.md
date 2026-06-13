---
name: aeat-calculation-grounding
---

# AEAT calculation grounding

Carry regulatory grounding through every domain boundary. Every casilla observation, calculation revision, filing draft, export record, and CLI emit MUST preserve its legal_refs, source_refs, and formula_id provenance from the registry source to the operator-facing surface.

Persist typed envelopes, not flat scalar mappings. RegistryFilingObservation, CasillaObservation, CalculationRevision.observations, and equivalent typed records are canonical. Do not collapse them to dict[str, Decimal] for downstream consumers. Expose a derived mapping as a property if a flat view is needed.

Emit every casilla in engine_result.values, not only computed entries. Input and bound casillas MUST produce CasillaObservation rows pulled from the registry casilla definition (legal_refs, source_refs). Pull the same fields for computed casillas from the matching engine entry. Never drop a casilla on the way to the persisted revision.

Surface legal_refs and source_refs on every operator-facing CLI JSON payload. Wrap typed observations in a parallel JSON list alongside any flat casilla_values mapping. The flat view is for human readability; the typed list is the contract.

Validate referential integrity at snapshot build. Every typed-ID reference must point at an existing entity on the snapshot. Every per-source binding selector must satisfy its typed selector model. Every cross-domain routing table (renta first-slice expense, registry capabilities, etc.) must reference real casillas in the modelo revision.

Treat type-system escapes as boundary leaks. cast(...) calls, dict[str, Any] returns, and bare str(...) coercion of typed aliases are documentation debt or design escapes. Document third-party API boundaries inline. Remove them everywhere else.