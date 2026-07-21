---
tags:
  - '#research'
  - '#google-optional-adapter-boundary'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-14-google-oauth-audit]]"
  - "[[2026-07-14-google-optional-adapter-boundary-reference]]"
---

# `google-optional-adapter-boundary` research: `legacy Google scope reconciliation`

This research decides whether the open Google master-plan rows are missing
product work or residue from superseded architecture. Vaultspec RAG located the
governing ADRs and implementation; the sibling Reference confirms exact symbols
and absence claims against the audited working tree.

## Findings

### The underlying conflict is one authority error

The local encrypted bucket, calculation registry, custody service, evidence
store, and canonical application writers are already the authorities for their
domains. Google is an opt-in interoperability adapter. The May ADR series
nevertheless assigned Google independent recovery, watched ingestion, export
taxonomy, reverse merge, and persisted calculation mutation responsibilities.
The 2026-07-14 master-plan audit already identified those contradictions; the
code Reference confirms they are not hidden implementations.

### Existing mechanisms cover the genuine goals

- Off-machine observation is supplied by ciphertext push plus remote manifest
  inspection; Drive is not a local write authority.
- Complete cross-host recovery is supplied by the provider-neutral sealed
  full-custody archive and recovery wrap.
- Drive document acquisition is supplied by explicit `doclink` and selected
  folder pull, both of which reuse encrypted attachment custody.
- Calculation review is supplied by the shared workbook plan, Google export,
  parity verification, typed readback, and non-persistent shared-engine compute.
- Ledger correction is supplied by the canonical ledger lifecycle and its
  `update` writer.

No product goal requires a Google-specific duplicate of those mechanisms.

### Options

1. **Complete every open legacy phase.** Rejected. It would add a second recovery
   architecture, a second ingestion coordinator, and parallel mutation paths
   because the plan treats historical mechanism choices as mandates.
2. **Edit only the plan while leaving all old ADRs accepted.** Rejected. The
   architecture corpus would continue to require mutually incompatible designs,
   so the same false backlog would return.
3. **Adopt one optional-adapter authority boundary and supersede the conflicting
   ADRs.** Chosen. One decision resolves the shared cause while preserving the
   shipped subsets through their current canonical owners.
4. **Write separate replacement ADRs for recovery, inbound, ledger, and
   calculation mutation.** Rejected. Those records would imply four new product
   decisions where the evidence supports one scope reconciliation.

### Recommended decision

Google integrations remain explicit optional adapters. Under this decision they
do not own key custody, restore semantics, calculation truth, or direct persisted
domain mutation. The local encrypted bucket, registry, full-custody archive, and
canonical application services retain authority.

The remote mirror may read remote objects and manifests for integrity
observation but may not restore them into local state. Evidence commands may
write encrypted evidence only by delegating to the canonical attachment and
ledger services. Calculation Sheets may export, verify, return typed edits, and
compute through the shared engine, but neither pull nor compute persists a work
unit or calculation revision. Any future Sheet-adoption path requires a separate
decision and must call the canonical writer.

The watched Drive inbox, Google KEK escrow, Google-owned ledger reverse merge,
CSV correction namespaces, and Sheet-to-calculation mutation are retired from
the Google master plan. Provider-neutral versions are neither approved nor
rejected by this decision.

### Supersession set

The successor ADR should supersede these records in whole because each mixes a
surviving user outcome with an obsolete Google-owned authority or implementation
contract:

- `2026-05-13-google-oauth-snapshot-adr`
- `2026-05-13-google-oauth-inbound-adr`
- `2026-05-13-google-oauth-taxonomy-adr`
- `2026-05-13-google-oauth-calc-sheets-adr`
- `2026-05-13-google-oauth-twoway-adr`
- `2026-05-14-google-oauth-adr`

The accepted remote-manifest, sealed-custody, evidence-byte, workbook-parity,
binding-vocabulary, and CLI operator-surface decisions remain the canonical
owners of the shipped behavior.

### Plan effect and no-code conclusion

P04 and the watched-inbound P05 should be retired with explicit supersession
records, not implemented. P06 and P08 work that concerns provider-neutral domain
features must leave the Google plan; this ADR does not decide whether it belongs
in another campaign. P07 and P09 should reconcile to the current shared workbook
plan, online renderer, parity harness, typed pull, and non-persistent compute.

The decision requires documentation and plan reconciliation only. It authorizes
no production-code addition, compatibility shim, duplicate repository, or new
write path.

### Sources

- `file:.vault/audit/2026-07-14-google-oauth-audit.md:11-88`
- `file:.vault/adr/2026-07-12-google-oauth-adr.md:15-185`
- `file:.vault/adr/2026-06-30-bucket-custody-completeness-adr.md:186-277`
- `file:.vault/adr/2026-06-10-ledger-evidence-enforcement-adr.md:83-168`
- `file:.vault/adr/2026-06-26-binding-vocabulary-cli-cohesion-adr.md:169-215`
- `file:.vault/adr/2026-06-03-modelo-export-workbook-parity-adr.md:13-111`
- `file:.vault/reference/2026-07-14-google-optional-adapter-boundary-reference.md`
