---
generated: true
tags:
  - '#index'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:fbe5e874de1d1678bfa20a8cc67d01d4c5e5c0f15575890eb10dee4fdb230c5f'
related:
  - '[[2026-08-07-canonical-identifiers-W01-P01-S01]]'
  - '[[2026-08-07-canonical-identifiers-W01-P01-S02]]'
  - '[[2026-08-07-canonical-identifiers-W01-P01-S03]]'
  - '[[2026-08-07-canonical-identifiers-W01-P01-S04]]'
  - '[[2026-08-07-canonical-identifiers-W01-P01-S66]]'
  - '[[2026-08-07-canonical-identifiers-W01-P01-S68]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S05]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S06]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S07]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S08]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S09]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S10]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S11]]'
  - '[[2026-08-07-canonical-identifiers-W02-P02-S12]]'
  - '[[2026-08-07-canonical-identifiers-W03-P04-S64]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S29]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S30]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S31]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S32]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S33]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S34]]'
  - '[[2026-08-07-canonical-identifiers-W04-P06-S71]]'
  - '[[2026-08-07-canonical-identifiers-W05-P07-S35]]'
  - '[[2026-08-07-canonical-identifiers-W05-P07-S36]]'
  - '[[2026-08-07-canonical-identifiers-W05-P07-S37]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S38]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S39]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S40]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S41]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S42]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S43]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S44]]'
  - '[[2026-08-07-canonical-identifiers-W05-P08-S69]]'
  - '[[2026-08-07-canonical-identifiers-W06-P09-S45]]'
  - '[[2026-08-07-canonical-identifiers-W06-P09-S62]]'
  - '[[2026-08-07-canonical-identifiers-W06-P10-S46]]'
  - '[[2026-08-07-canonical-identifiers-W06-P10-S47]]'
  - '[[2026-08-07-canonical-identifiers-W06-P10-S63]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S48]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S49]]'
  - '[[2026-08-07-canonical-identifiers-W07-P11-S50]]'
  - '[[2026-08-07-canonical-identifiers-adr]]'
  - '[[2026-08-07-canonical-identifiers-plan]]'
  - '[[2026-08-07-canonical-identifiers-reference]]'
  - '[[2026-08-10-canonical-identifiers-expediente-provenance-adr]]'
  - '[[2026-08-10-canonical-identifiers-expediente-provenance-reference]]'
  - '[[2026-08-10-canonical-identifiers-revision-id-adjudication-reference]]'
  - '[[2026-08-13-canonical-identifiers-s10-provenance-roundtrip-audit]]'
  - '[[2026-08-13-canonical-identifiers-s11-contract-audit]]'
---

# `canonical-identifiers` feature index

Auto-generated index of all documents tagged with `#canonical-identifiers`.

## Documents

### adr

- `2026-08-07-canonical-identifiers-adr` - `canonical-identifiers` adr: `Canonical AEAT document-identifier taxonomy` | (**status:** `accepted`)
- `2026-08-10-canonical-identifiers-expediente-provenance-adr` - `canonical-identifiers` adr: `IVA compensation expediente provenance` | (**status:** `accepted`)

### audit

- `2026-08-13-canonical-identifiers-s10-provenance-roundtrip-audit` - `canonical-identifiers` audit: `s10 provenance roundtrip`
- `2026-08-13-canonical-identifiers-s11-contract-audit` - `canonical-identifiers` audit: `s11 contract`

### exec

- `2026-08-07-canonical-identifiers-W01-P01-S01` - Re-read domain/modelos/_ids.py against current HEAD to confirm the four ids and the duplicate pattern are still declared as described here, then alias WorkUnitId, CalculationRevisionId, FilingRecordId and VerificationReportId from core.identity.Hex64Str, deleting the duplicate pattern declaration. HEAD re-read is DONE as of 2026-08-10: all four aliases and the module-local _HEX_64_PATTERN are still declared verbatim, so the duplication this row exists to close is still live. The aliasing itself does not land as its own commit -- it is inseparable from the relocation in S02, so each symbol's alias-and-move share one index per the relocation-atomicity rule
- `2026-08-07-canonical-identifiers-W01-P01-S02` - Relocate the four aliased ids into core/identity/ and update every consumer import in the same commit per the relocation-atomicity rule. FOUR COMMITS, one per symbol, tagged relocation:<symbol> -- the standing rule is one Step equals one symbol equals one atomic commit, and this row batches four. Ascending blast radius measured against HEAD: VerificationReportId 5 consumer files, FilingRecordId 10, CalculationRevisionId 20, WorkUnitId 27, with exactly ONE dirty consumer across all of them. THIS ROW OMITTED THREE THINGS a compliant execution must still do, rowed here rather than done silently: domain/modelos/_ids.py holds ONLY these four aliases and their __all__, so the LAST of the four commits EMPTIES it and must DELETE the module, because an empty module left standing is a bridge by another name. That deletion orphans docs/api/cadrumo.domain.modelos._ids.rst, which hard-crashes autodoc on the next nitpicky build, so the stub removal rides in the SAME commit and is generated by apidocs scaffold rather than hand-edited. And the module docstring names all four identities by name, so each departure makes it progressively false and the intermediate commits must trim it
- `2026-08-07-canonical-identifiers-W01-P01-S03` - Re-read domain/invoices/_ids.py against current HEAD, alias InvoiceId from core.identity.Hex64Str, and relocate it with its consumer imports updated in the same commit
- `2026-08-07-canonical-identifiers-W01-P01-S66` - Collapse the THREE hand-rolled hex-64 declarations this Wave's premise did not count, each re-declaring the exact literal pattern that core/_hex.py's own docstring names as the thing every such concept must alias instead. The Wave was planned against a reference measurement of TWO duplicates. Measured against the finished tree after all five relocations landed, the real count is SIX. Three are now closed -- the two the reference named plus one found inside domain/modelos/_verification_report.py during the relocation and absorbed there. Three remain and had no row anywhere in this plan, so closing the Wave on its original rows would have left its own stated goal unmet with a checkbox saying otherwise. Rowed as ONE row rather than three because it is one concept at three sites with an identical remedy, and three rows invite three partial closures. TERRITORY, since two fall outside this campaign's modules and the implementation may be routed elsewhere -- application/evidence/_ids.py declares BundleId and EvidenceId, domain/attachments/_ids.py declares AttachmentId, and application/modelo/_m145_communication_records.py declares a record id inline rather than in an ids module. The remedy for each is the one this Wave already proved five times over: alias from the canonical primitive, delete the local pattern constant, and repoint every consumer in the same commit. The release condition is a tree-wide collect with zero ERROR lines, not a checker pass, because a cross-package importer is invisible to both a symbol grep and a type checker and that blind spot is what made this Wave ship a P0 twice
- `2026-08-07-canonical-identifiers-W02-P02-S05` - declare `IdentifierNamespace` as a closed StrEnum split into AEAT-issued and app-derived groups, each member documented with the concept it names
- `2026-08-07-canonical-identifiers-W02-P02-S06` - declare `AeatExpedienteId` at the sede-schema bound and `AeatClaveLiquidacion` and `AeatPresentationId` at their current field bounds
- `2026-08-07-canonical-identifiers-W02-P02-S07` - Retype every expediente_id model field onto AeatExpedienteId, removing the per-field repeated bound and the duplicated shape validator
- `2026-08-07-canonical-identifiers-W02-P02-S08` - Retype Deuda.clave_liquidacion onto AeatClaveLiquidacion, and retype the second bare-str clave_liquidacion on the operator-facing wire payload in the same change
- `2026-08-07-canonical-identifiers-W04-P06-S33` - retype every classified bucket_event_id/event_id pydantic model field onto the existing BucketEventId alias at the sites not already using it
- `2026-08-07-canonical-identifiers-W07-P11-S48` - document the three free-text sub-populations as a code comment on IdentifierNamespace naming representative fields for each, explicitly stating none are namespace members
- `2026-08-07-canonical-identifiers-W07-P11-S49` - author and run dev/identifier_noun_census.py, an AST sweep matching field docstrings against a noun-vocabulary heuristic independent of the original suffix heuristic
- `2026-08-07-canonical-identifiers-W07-P11-S50` - triage the second-pass sweep's findings into the existing namespace set, a new namespace, or an explicit non-identifier exclusion, recording the disposition of each
- `2026-08-07-canonical-identifiers-W01-P01-S04` - run the full persistence and pydantic-model roundtrip suite to confirm the relocation changed no shape
- `2026-08-07-canonical-identifiers-W01-P01-S68` - Retype M303ProductSoftwareEvidence.digest onto the canonical ContentDigest alias, closing the SEVENTH hex-64 redeclaration site. This site existed in NO row of this plan, including S66's widened count. The Wave was planned against two duplicates, S66 re-measured six, and the true figure at HEAD is seven. A peer campaign landed this inline pattern at 2026-08-12 11:11, AFTER this campaign's own redeclaration gate landed at 2026-08-10 16:35, so the gate was green and is now red on a site no row names. Rowed rather than folded silently into S04 because S04 is a verification row and a fix carried inside a verification row is invisible to review. The remedy is the one this Wave proved five times over and the primitive's own docstring prescribes. The value is a payload digest, so it takes ContentDigest rather than a bare Hex64Str or a newly minted per-concept alias, and the module already imports from core.identity so no new import path is created. NOTE that the gate deliberately scans at HEAD rather than the working tree, so this row cannot be verified green until its commit lands. The working-tree proof is a census_sources run over the edited source.
- `2026-08-07-canonical-identifiers-W05-P07-S35` - adjudicate each of the twelve bare `revision_id` sites against its actual producer (registry `ModeloRevision.id` versus the hex-64 `CalculationRevisionId`), recording the per-site decision in the Step record before retyping any of them
- `2026-08-07-canonical-identifiers-W05-P07-S36` - retype every site adjudicated in `W05.P07.S35` onto `CalculationRevisionId` or the canonical `RevisionId` per its recorded disposition. DO NOT MINT `RegistryRevisionId`. This row previously instructed creating it and that instruction was superseded on 2026-08-11: the concept already has a canonical home as `type RevisionId` in the registry ids module, exported from the registry facade and carrying 16 users at HEAD, so minting a second alias beside it fragments a canonical type and is precisely the criticality this campaign exists to close. It would also have shipped green, because a faithfully-implemented wrong specification passes every gate and produces an honest exec record. Substitutability is measured and constrains the retype: `RevisionId` carries min_length, max_length and a pattern where a bare `str` carries none, so every retype NARROWS its site and is correct ONLY where the adjudication recorded a genuine registry revision slug
- `2026-08-07-canonical-identifiers-W02-P02-S09` - Discriminate IVA-compensation provenance from AEAT register status
- `2026-08-07-canonical-identifiers-W02-P02-S10` - Add the strict roundtrip and anti-tautology proof for the discriminated pair. Populate every defaultable field on IvaCompensationPeriodState non-default, push it through the real encrypted repository and assert strict model equality on load. For the anti-tautology proof delete the persisted provenance field from the on-disk payload, reload through the real production read path, and assert refusal rather than a silent re-default. Add a companion case proving the cross-field validator refuses both impossible pairs, an operator-seeded row carrying an expediente and an AEAT-capture row carrying none
- `2026-08-07-canonical-identifiers-W02-P02-S11` - retype `ExpedienteDeclarationPayload.expediente_id` from unconstrained bare `str` onto `AeatExpedienteId`, closing the fourth (loosest) divergence sighted on the operator-facing wire contract
- `2026-08-07-canonical-identifiers-W02-P02-S12` - add a golden-schema pinning test capturing `ExpedienteDeclarationPayload`'s advertised `model_json_schema()` before and after `W02.P02.S11`, so the CLI/MCP contract change is a visible reviewed diff rather than a silent constraint shift
- `2026-08-07-canonical-identifiers-W03-P04-S64` - Decide whether resolve_identifier_namespace is enrolled or dropped, and record the outcome before S24 executes. Search production for a site holding an AEAT identifier value whose namespace is UNKNOWN at the point of use. A semantic sweep run for the 2026-08-10 ADR amendment found none, returning only the enum's own module, its own test and an in-flight census tool. The disconfirming observation that decides this row: a genuine consumer holds a value whose namespace cannot be read off its own field type. If every candidate turns out to hold a value whose namespace is already fixed by its field type, record that the resolver is DROPPED and retire IdentifierNamespace with it rather than leaving an exported concept nothing uses. Do not manufacture a caller to justify the symbol
- `2026-08-07-canonical-identifiers-W04-P06-S29` - retype classified transaction-id pydantic model fields onto `TransactionId` in `application/ledger/`
- `2026-08-07-canonical-identifiers-W04-P06-S30` - retype classified transaction-id pydantic model fields onto `TransactionId` in `application/aggregation/`
- `2026-08-07-canonical-identifiers-W04-P06-S31` - adjudicate `bucket_id` in `adapters/persistence/profile/` — zero model fields, row's premise does not survive contact
- `2026-08-07-canonical-identifiers-W04-P06-S32` - retype classified invoice-id pydantic model fields onto `InvoiceId` in the invoices packages
- `2026-08-07-canonical-identifiers-W04-P06-S34` - verify the four W04 adoptions changed no wire shape for already-valid values
- `2026-08-07-canonical-identifiers-W04-P06-S71` - scope `bucket_id`'s real 81-site population — report only, do not open
- `2026-08-07-canonical-identifiers-W05-P07-S37` - retype `short_work_unit_id` and `short_calculation_revision_id` onto the existing `core.Hex16Str` primitive rather than the full-length aliases
- `2026-08-07-canonical-identifiers-W05-P08-S38` - declare `RegistrySnapshotId` as a new `IdentifierNamespace.APP_REGISTRY_SNAPSHOT_ID` member and alias for the composite `modelo:revision_id:filing_year:period` string, explicitly distinct from `core.identity.SnapshotId`
- `2026-08-07-canonical-identifiers-W05-P08-S39` - declare `RegistryRevisionId` as a new `IdentifierNamespace.APP_REGISTRY_REVISION_ID` member and alias for the human-authored registry version tag
- `2026-08-07-canonical-identifiers-W05-P08-S40` - retype the three `registry_snapshot_id` sites and the `registry_revision_id` sites onto the two new aliases
- `2026-08-07-canonical-identifiers-W05-P08-S41` - declare `AeatCertificadoId` as a new `IdentifierNamespace.AEAT_CERTIFICADO_ID` member and alias at the 13-digit-or-longer bound its docstring already states, and retype `RemoteNotification.certificado_id` onto it
- `2026-08-07-canonical-identifiers-W05-P08-S42` - declare `AeatBoxNumber` as a new `IdentifierNamespace.AEAT_BOX_NUMBER` member and alias, distinct from the registry's own `CasillaId`, and retype `display_number`, `form_number`, `from_number`, and `to_number` onto it
- `2026-08-07-canonical-identifiers-W05-P08-S43` - check whether M210's `official_tipo_renta_code` catalogue is already enumerated in registry TOML
- `2026-08-07-canonical-identifiers-W05-P08-S44` - declare `M720OperationKindCode` and `M720AssetClassCode` as `StrEnum`s in `core/` sourced from registry TOML if enumerated there, and retype `operation_kind_code` / `asset_class_code` onto them, explicitly NOT as `IdentifierNamespace` members
- `2026-08-07-canonical-identifiers-W05-P08-S69` - adjudicate `CasillaDefinition.number` as its own identifier population, separate from `AeatBoxNumber`
- `2026-08-07-canonical-identifiers-W06-P09-S45` - self and profile-owned tax identity: `tax_id`, `spouse_tax_id`, `profile_tax_id` onto `SubjectTaxId`
- `2026-08-07-canonical-identifiers-W06-P09-S62` - cross-field tax-identity consistency audit for every model `W06.P09.S45` retyped
- `2026-08-07-canonical-identifiers-W06-P10-S46` - counterparty-facing tax identity: `supplier_tax_id`, `customer_tax_id`, `party_tax_id`, `donor_tax_id` onto `TaxIdIdentityToken`
- `2026-08-07-canonical-identifiers-W06-P10-S47` - a roundtrip regression proving a non-Spanish-shaped counterparty tax id validates under `TaxIdIdentityToken`
- `2026-08-07-canonical-identifiers-W06-P10-S63` - cross-field tax-identity consistency audit for every model `W06.P10.S46` retyped

### plan

- `2026-08-07-canonical-identifiers-plan` - `canonical-identifiers` plan

### reference

- `2026-08-07-canonical-identifiers-reference` - `canonical-identifiers` reference: `AEAT identifier taxonomy census`
- `2026-08-10-canonical-identifiers-expediente-provenance-reference` - `canonical-identifiers` reference: `IVA compensation expediente provenance sites`
- `2026-08-10-canonical-identifiers-revision-id-adjudication-reference` - `canonical-identifiers` reference: revision_id adjudication
