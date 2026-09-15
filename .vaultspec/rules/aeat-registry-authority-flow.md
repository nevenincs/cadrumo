# AEAT registry authority flow

## Source, candidate and runtime boundaries

- Authored source is the registry data physically stored on disk. A staged candidate is an isolated proposed replacement; it is not installed source or published authority.
- Development authoring uses the canonical compiler, parser and hydrator. `inspect_authoring_candidate()` exposes typed candidate components, source/evidence fingerprints and validation findings; those components are not a `ValidatedRegistryAuthority`. This path is available when inspecting unpublished edits, including before the first publication.
- `compile_validated_authority()` establishes full candidate validation. Successful compilation is not publication. Product runtime consumes the published authority through the canonical reader; it must not compile mutable source or fall back to raw TOML.
- Raw-file comparisons may measure authored structure and duplication. Claims about hydrated meaning use canonical typed loading; claims about runtime behavior use the published generation. Never invent a second loader to cross these boundaries.

## Delta authoring and hydration

- Store a baseline plus genuine field/value differences, new members, explicit removals and required ordering/scope metadata. Do not repeat a whole row or family merely because one field or evidence reference changes.
- An omitted override inherits; an explicit removal deletes. Empty values, false, zero, sequence order and revision-specific assertions retain their typed meaning. A changed default must not silently change inherited provenance.
- Storage selectors and baselines address payload, not legal identity. Missing `continuidad_id`, a lower capability grade or a changed physical representation is not by itself a prohibition on lossless storage reuse.
- Preserve real continuity, review and capability claims with their original scope. Do not invent evidence, advance a review date or promote capability because payload is shared. A failed migration is a tool diagnostic, not a new legal no-predecessor declaration.
- Conversion is modelo-independent and discovers authored revisions and dependencies from canonical metadata. Existing delta chains still undergo remaining-family conversion and redundant-override assessment; they are not automatically complete.

## Temporal selection

- A projected edition supplies a missing temporal coordinate from the nearest eligible authored source through the canonical resolver, backward or forward and across internal gaps. It creates no copied source edition and asserts no new target-year review.
- Resolve applicability branches, periods, ties and explicit divergences through the same typed selection contract for loaders, facts, runtime and support reporting. Do not select by lexical filenames or a consumer-specific newest-year fallback.
- The registry's canonical support declaration owns the temporal envelope. Consumers must not introduce separate floor/ceiling constants or ranges. Historical sources outside the request envelope may remain required storage baselines.
- Available projected data and eligibility for a particular operation are separate results. Preserve capability limitations without falsely treating an un-authored but resolvable edition as missing data.

## Application, publication and completion

- Prove source replacement with effective typed equivalence, independent minimality, complete assessment scope, idempotence and stable input receipts. Intentional semantic corrections need their own grounded change evidence rather than a claim of unchanged meaning.
- Report unchanged publication-readiness defects separately from defects introduced by a representation rewrite. Unrelated unchanged defects do not automatically forbid a proven source-only replacement; full publication validation remains mandatory.
- Installing source means the actual authoring tree matches the accepted candidate. Publishing means the active descriptor references the accepted content-addressed artifact. A temporary database, retained lock sidecar or passing compile is neither of those outcomes.
- Publication verifies current source/evidence/compiler receipts and never exposes an incomplete generation. Runtime and packaging checks must identify the generation they actually consume; caches invalidate on relevant input or generation changes.
- State completion separately for candidate validation, installed source, published authority and runtime/package adoption. Do not mark overall rollout complete while a required boundary remains unverified.
