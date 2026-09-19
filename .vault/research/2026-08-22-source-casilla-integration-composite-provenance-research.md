---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:1219d5367c39808ca8920ffad7fcaffad760ef56c89e47cd9c150f422ed28999'
related:
  - "[[2026-08-22-source-casilla-integration-research]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `source-casilla-integration` research: `composite calculation-source provenance`

Composite resolvers expose a structural mismatch between calculation provenance and the connectivity authority: the provenance row identifies a contributing upstream object, while enrollment identifies the resolver-owned `BindingSourceKind`. The mismatch is observable in the foreign-assets and IVA-wallet resolvers and cannot be repaired reliably by treating a transient aggregate as a source object. The evidence favors retaining separate resolved-source and contributor-source axes and adding explicit lineage role and parentage, with a real, uniquely identified primary object wherever a composite source is asserted. The accepted ADR must be amended before implementation to settle the field contract, primary-identity rule, fingerprint rule, authority match, revision-id payload, and one-way replacement scope.

## Findings

### The current row has one source axis, but production asks it to answer two different questions

`CalculationSourceProvenance` records `resolver_id`, free-form `source_kind`, optional canonical `binding_source`, `source_ref`, and optional `fingerprint`; its validator requires `binding_source` to equal `source_kind` whenever the free-form token is a `BindingSourceKind`. `CalculationSourceRef` repeats that shape, and the application-to-domain projection copies it field for field. These fields can describe the object that contributed facts, or the binding source owned by the resolver, but not both when those identities differ. The source mesh separately declares resolver ownership through `owned_sources`, and the live ownership catalogue projects that declaration into the production route. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:680-719`, `src/cadrumo/application/aggregation/_source_mesh.py:829-857`, `src/cadrumo/application/aggregation/_source_mesh.py:1053-1073`, `src/cadrumo/domain/modelos/_calculation_revision.py:596-655`, `src/cadrumo/application/modelo/_calculation_actions.py:932-959`, `src/cadrumo/application/registry/_source_connectivity_authority.py:38-108`.

Composition preserves each child row's producing resolver rather than replacing it with the synthetic merge resolver. `CalculationSourceResolution` explicitly exempts the two reserved composite resolver ids from row-level resolver equality, and both exclusive and precedence merges append provenance unchanged. That behavior is useful: the calculation revision retains the real producer. It also means a merged envelope cannot supply the missing resolver-owned source identity after the fact. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:409-413`, `src/cadrumo/application/aggregation/_source_mesh.py:994-1003`, `src/cadrumo/application/aggregation/_source_mesh.py:1106-1113`, `src/cadrumo/application/aggregation/_source_mesh.py:1197-1209`, `src/cadrumo/application/aggregation/_source_mesh.py:1212-1257`.

### Foreign assets and the IVA wallet are the two concrete resolved-versus-contributor divergences

`ForeignAssetsAggregationSourceResolver` owns `FOREIGN_ASSET`, but every selected observation is restricted to one of four upstream carrier kinds: `LEDGER_TRANSACTION`, `PURCHASE_INVOICE_EVIDENCE`, `PAYABLE_INVOICE`, or `COLLECTIBLE_INVOICE`. Its provenance rows therefore name the carrier kind and carrier object id, carry no fingerprint, and never name the owned `FOREIGN_ASSET` source. The resolver can calculate M720 rows, yet its encrypted revision cannot contain the row that current connectivity authority seeks for a `FOREIGN_ASSET` connection. Evidence: `src/cadrumo/application/aggregation/_foreign_assets.py:47-55`, `src/cadrumo/application/aggregation/_foreign_assets.py:85-144`, `src/cadrumo/application/aggregation/_foreign_assets.py:295-352`.

`IvaWalletDecisionSourceResolver` owns `IVA_WALLET_DECISION`, but emits one non-binding row for each `aeat_wallet`, `local_recurrence`, filed-history, or `taxpayer_override` authority source. Every row repeats the SHA-256 of the whole reconciliation decision rather than fingerprinting its own contributor, and no row identifies the persisted wallet decision as the resolved primary object. The decision itself is independently persisted and replayed, so unlike a transient aggregation it is eligible to be the primary object once its canonical repository identity is projected. Evidence: `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py:81-148`, `src/cadrumo/domain/iva_compensation/_reconciliation.py:103-173`, `src/cadrumo/domain/iva_compensation/_reconciliation.py:575-620`, `src/cadrumo/application/calculations/_observations_repository.py:386-430`, `src/cadrumo/application/calculations/_observations_repository.py:705-771`.

### Primary identity must name a durable economic or decision object, not merely an aggregation pass

The IVA-wallet repository already has one latest-decision key per taxpayer and target period and an event identity that includes the target and decision instant. Those are available ingredients for a typed primary reference; the ADR still needs to choose which canonical repository identity crosses into calculation provenance. Evidence: `src/cadrumo/application/calculations/_observations_repository.py:386-430`, `src/cadrumo/application/calculations/_observations_repository.py:705-778`.

Foreign-asset ingestion has no equivalent primary identity. `source_object_id` identifies the upstream carrier, while `asset_external_id` is only a bounded string; the model has no uniqueness invariant over an economic asset across carrier kind, institution, country, or an aggregation pass. Consequently, neither field alone is evidence of a unique `FOREIGN_ASSET` primary. A composite-provenance contract should not mint an aggregate-level `foreign_asset` row until a real durable aggregate object exists, and should not relabel a carrier id as the asset id. The foreign-assets slice first needs a dedicated typed primary identity or a documented composite key with enforced uniqueness. Evidence: `src/cadrumo/application/aggregation/_foreign_assets.py:85-144`, `src/cadrumo/application/aggregation/_foreign_assets.py:147-203`, `src/cadrumo/application/aggregation/_foreign_assets.py:260-292`.

For a direct resolver, the resolved object and contributor may be the same object. Such a row can be a primary with no parent, with both axes equal. For a genuine composite, each contributor needs the exact primary reference it supports; otherwise two primary objects resolved in one pass cannot be separated during replay or review. This is an inference from the current multi-row foreign-asset surface and the one-row authority match and must be made normative only by the ADR. Evidence: `src/cadrumo/application/aggregation/_foreign_assets.py:321-351`, `src/cadrumo/application/registry/_source_connectivity_authority.py:290-312`.

### The current authority match is exact but assumes resolved identity and contributor identity are identical

`LiveSourceConnectivityProofAuthority.encrypted_revision_matches` selects exactly one row whose `binding_source` equals the connection's owned source and whose `source_ref` equals the asserted persisted identity; it then requires the resolver, source-kind token, and fingerprint to match. This is sound for direct sources but necessarily rejects both proven divergences because neither emits its owned source. Weakening the match to accept any contributor would incorrectly prove that an enrolled `FOREIGN_ASSET` or `IVA_WALLET_DECISION` object survived persistence when only an upstream carrier did. Evidence: `src/cadrumo/application/registry/_source_connectivity_authority.py:249-312`, `src/cadrumo/core/source_connectivity.py:200-206`, `src/cadrumo/core/source_connectivity.py:283-308`, `src/cadrumo/core/source_connectivity.py:464-482`.

Under a split-axis contract, connected authority can continue to require one exact row, but it should match the resolver-owned axis and a primary role, then verify primary identity and fingerprint. Contributor rows remain audit evidence and are joined through parentage; they do not independently satisfy enrollment. This preserves the accepted campaign's distinction between resolver enrollment, encrypted-revision survival, and operator reachability. The precise uniqueness cardinality—one primary per resolved object rather than one primary per resolution—is an ADR question because row-producing resolvers can resolve multiple economic objects in one pass. Evidence: `.vault/adr/2026-08-22-source-casilla-integration-adr.md:41-72`, `src/cadrumo/core/source_connectivity.py:217-260`, `src/cadrumo/core/source_connectivity.py:263-330`.

### Lineage fields and fingerprints must enter calculation-revision identity together

The calculation revision hashes an order-independent sorted tuple of resolver id, binding source, source kind, source ref, fingerprint, and dependency treatment. It does not currently encode role, parent, or a second source axis because none exists. Adding lineage without adding every new semantic axis to this payload would let two different source graphs produce the same revision id. Conversely, including the complete canonical graph makes a changed primary, contributor, parent edge, or content digest produce a distinct revision. Evidence: `src/cadrumo/domain/modelos/_calculation_revision.py:309-326`, `src/cadrumo/domain/modelos/_calculation_revision.py:417-542`, `src/cadrumo/domain/modelos/_calculation_revision.py:973-982`.

The wallet resolver's repeated whole-decision digest proves the decision content but not the content of each authority source independently. A role-aware model can place that digest on the wallet-decision primary; contributor fingerprints should be derived from each contributor's canonical content where such content is available, or carry an explicit absence posture if the ADR permits unfingerprinted external locators. Foreign-asset provenance currently has no digest at either level. The campaign's encrypted-proof model already requires a non-empty primary fingerprint, so leaving primary fingerprints optional would preserve a gap between generic revision validity and `connected` census admission. Evidence: `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py:133-147`, `src/cadrumo/application/aggregation/_foreign_assets.py:343-351`, `src/cadrumo/core/source_connectivity.py:283-308`.

### Four alternatives expose different correctness and migration costs

| Alternative | What it represents | Evidence-backed benefit | Residual risk / cost |
| --- | --- | --- | --- |
| A. Two explicit resolved/contributor axes, no role or parent | Every row names the resolver-owned binding source separately from the contributing kind/ref | Repairs authority matching with the smallest conceptual addition and preserves contributor taxonomy | Cannot distinguish the authoritative resolved object from evidence rows, cannot bind contributors to one of several primaries, and leaves primary cardinality implicit |
| B. `PRIMARY`/`CONTRIBUTOR` role plus parent, with `binding_source` redefined as the primary source | Role and edge establish a source graph; primary rows can satisfy authority | Makes lineage and primary cardinality testable | Overloads or loses the contributor's canonical `BindingSourceKind`; redefining the existing field makes contributor queries ambiguous and still requires a second carrier-kind field in the two proven divergences |
| C. Two axes plus role and parent | Each row names the resolved source; primary rows identify resolved objects; contributor rows retain their own kind/ref and point to the primary | Represents direct and composite resolvers without conflation, gives authority an exact primary predicate, and lets revision identity cover the complete graph | Broadest strict schema replacement and constructor/test sweep; requires a real primary identity before foreign assets can claim connected provenance |
| D. Synthetic primary aggregate rows / status quo contributors | Add one resolver-owned aggregate row while leaving current contributor rows unchanged | Small local resolver changes; a durable aggregate such as the persisted wallet decision can legitimately act as primary | Fabricates identity for in-pass aggregates, cannot associate contributors with multiple primaries, and encourages authority-only rows that do not correspond to durable source objects |

The evidence favors C because it is the only option that answers ownership, object identity, and lineage independently. A is viable only if the project accepts that composite resolution can never contain multiple primaries; B is viable only if contributor binding taxonomy is intentionally discarded or moved elsewhere; D is valid for a real persisted aggregate object but not as a general foreign-assets pattern. These are research conclusions, not an architectural decision.

### The one-way replacement is broad but mechanically bounded

The schema change crosses the application provenance model, domain persisted ref, projection boundary, revision-id canonicalization, encrypted calculation-revision fixtures, connectivity authority, direct and composite resolver constructors, merge tests, replay/review/export assertions that inspect provenance, and docs that describe the trace. At commit `d87b574d14`, `rg -n "CalculationSourceProvenance\\(" src/cadrumo/application src/cadrumo/adapters` finds 38 construction sites; most direct resolvers can set equal resolved and contributor axes mechanically, while the two divergences need explicit design work. Evidence: `src/cadrumo/application/aggregation/_source_mesh.py:680-719`, `src/cadrumo/domain/modelos/_calculation_revision.py:309-326`, `src/cadrumo/domain/modelos/_calculation_revision.py:596-655`, `src/cadrumo/application/modelo/_calculation_actions.py:932-959`, `src/cadrumo/application/registry/_source_connectivity_authority.py:290-312`, commit `d87b574d14`.

The repository's pre-release compatibility posture requires replacement rather than tolerant migration: remove the old persisted shape, aliases, defaulted lineage, and legacy readers; update all producers and strict fixtures atomically. That raises the immediate blast radius but avoids two provenance meanings coexisting indefinitely. Evidence: `.codex/rules/no-legacy-compatibility.md:1-39`, `src/cadrumo/domain/modelos/_calculation_revision.py:917-982`.

This research did not adjudicate official tax mappings, design a foreign-asset primary-id algorithm, or inspect every resolver's business semantics. Those belong to the ADR amendment and bounded implementation research; the present evidence is sufficient to establish the shared provenance-shape problem and the two known exceptional resolvers.

## Sources

- `.vault/adr/2026-08-22-source-casilla-integration-adr.md:41-72`
- `.vault/adr/2026-06-10-calculation-aggregation-taxonomy-adr.md`
- `.codex/rules/aeat-calculation-aggregation.md`
- `.codex/rules/no-legacy-compatibility.md:1-39`
- `src/cadrumo/application/aggregation/_source_mesh.py:409-413`
- `src/cadrumo/application/aggregation/_source_mesh.py:680-719`
- `src/cadrumo/application/aggregation/_source_mesh.py:829-857`
- `src/cadrumo/application/aggregation/_source_mesh.py:994-1003`
- `src/cadrumo/application/aggregation/_source_mesh.py:1053-1073`
- `src/cadrumo/application/aggregation/_source_mesh.py:1106-1113`
- `src/cadrumo/application/aggregation/_source_mesh.py:1197-1257`
- `src/cadrumo/application/aggregation/_foreign_assets.py:47-55`
- `src/cadrumo/application/aggregation/_foreign_assets.py:85-203`
- `src/cadrumo/application/aggregation/_foreign_assets.py:260-352`
- `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py:81-148`
- `src/cadrumo/domain/iva_compensation/_reconciliation.py:103-173`
- `src/cadrumo/domain/iva_compensation/_reconciliation.py:575-620`
- `src/cadrumo/application/calculations/_observations_repository.py:386-430`
- `src/cadrumo/application/calculations/_observations_repository.py:705-778`
- `src/cadrumo/application/modelo/_calculation_actions.py:932-959`
- `src/cadrumo/domain/modelos/_calculation_revision.py:309-326`
- `src/cadrumo/domain/modelos/_calculation_revision.py:417-542`
- `src/cadrumo/domain/modelos/_calculation_revision.py:596-655`
- `src/cadrumo/domain/modelos/_calculation_revision.py:917-982`
- `src/cadrumo/core/source_connectivity.py:200-330`
- `src/cadrumo/core/source_connectivity.py:464-482`
- `src/cadrumo/application/registry/_source_connectivity_authority.py:38-108`
- `src/cadrumo/application/registry/_source_connectivity_authority.py:249-312`
- commit `d87b574d14`
