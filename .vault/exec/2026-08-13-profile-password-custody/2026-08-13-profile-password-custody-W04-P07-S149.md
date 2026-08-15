---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:51129acf9bc40b174d5adb207c3cb9cc5949a47ee2f3751f07b68ec2aaaf878c'
step_id: 'S149'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium triage the forty-two persisted models whose schema version defaults to a bare literal rather than a named constant, since the binding gate discovers formats by constant name so a version that never gets a name is invisible to it entirely, and establish which of the forty-two are genuine persisted formats before naming any of them

## Scope

- `src/cadrumo/`

## Description

- Read the nested-persisted-format boundary ADR and the documented two-part
  test above `PersistedFormatClass` before touching the population.
- Re-derive the population of bare-literal-defaulted version fields by AST
  scan rather than trusting the row's stated count.
- Run the two already-landed gates covering this exact class
  (`test_persisted_version_single_declaration.py`,
  `test_persisted_format_enrolment_binding.py`) and read every entry in their
  standing tables against the code they classify, rather than the docstrings
  alone.
- Apply the boundary ADR's two-part test (independent grammar, durable
  readback) to every entry the landed gate calls "unnamed sole declaration",
  reading the actual write and read call sites for each.
- Verify the reverse direction: confirm no enrolled inventory key or bound
  version constant has outlived its implementation.

## Outcome

**The population has already been reduced by prior rows in this campaign,
and re-deriving it lands at twenty-three, not forty-two.** The forty-two
figure was accurate when the row was written; `S158` (bundle) and `S159`
(the five fincas records) each converted a bare-literal field to either a
required field with no default or a named constant, and `S161` named and
enrolled three more nested candidates (legal hold, filing retention, custody
hold evidence). Separately, a mechanical detector already landed on this
tree — `src/cadrumo/core/tests/test_persisted_version_single_declaration.py`
— which AST-scans every production `ClassDef` for a `schema_version` or
`*_schema_version` field whose default is a bare literal (a bare assignment,
`Field(default=...)`, or `mapped_column(default=...)`), and its
`STANDING_LITERAL_VERSION_DECLARATIONS` table is the exact mechanical census
this row's population question needs. Running it (`pytest
src/cadrumo/core/tests/test_persisted_version_single_declaration.py
src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py
src/cadrumo/tests/test_persisted_version_literal_inventory.py`) at current
HEAD passes all twenty-two tests, confirming the standing table is
up to date: no new offending site exists outside it, and no stale entry
remains that no longer names a live site. The table currently holds
twenty-three entries (I counted them against the live file at
`src/cadrumo/core/tests/test_persisted_version_single_declaration.py:102-237`).
That gate already classifies each site into three shapes — a dead second
declaration beside an existing constant, an unnamed sole declaration, or a
response-contract version — which is the mechanical half of this row's
three-bucket ask. My contribution is reading every one of the twenty-three
against the actual write/read call graph to confirm or correct that
classification, per the boundary ADR's two-part test, since the landed
gate's own docstring says its classification is "the judgement" and states it
does not itself verify durable readback.

**Bucket (a): GENUINE PERSISTED FORMAT — ten entries, evidenced by a real
write site and a `model_validate_json` (or equivalent) read site under the
field's own grammar.** (Four entries the landed gate placed in "unnamed sole
declaration" are re-classified OUT of this bucket below, listed here only to
show the reasoning that moved them.)

- `RemoteMirrorNamespaceManifest.manifest_schema_version`
  (`src/cadrumo/adapters/outbound/storage/_records.py:138`) — DOUBLE
  DECLARATION. Already enrolled by name as `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION`
  in `CONSTANTS_AWAITING_CLASSIFICATION`; this model field restates the same
  number as a dead second literal nothing compares. Direct input for S160's
  detector class.
- `ProfileCustodyOwnerReceipt.schema_version`
  (`src/cadrumo/application/user_profile/_custody_transactions.py:389`) —
  DOUBLE DECLARATION. Already enrolled as `CUSTODY_RECEIPT_SCHEMA_VERSION` in
  `CONSTANTS_AWAITING_CLASSIFICATION`; the two sibling records in the same
  module already bind the constant, this one is the odd literal out. Direct
  input for S160.
- `_OperationLeaseRecord.schema_version`
  (`src/cadrumo/adapters/persistence/operations/_lease.py:33`) — durably
  written via `OperationLeaseStorage._write` and read back via
  `_OperationLeaseRecord.model_validate_json` at `_lease.py:120`. Unnamed;
  needs a constant and a durability class.
- `ProfileCustodyDeletionMarker.schema_version`
  (`src/cadrumo/adapters/persistence/storage/custody/_capsule_records.py:285`)
  — read back via `ProfileCustodyDeletionMarker.model_validate_json` at
  `_capsule_records.py:406`. Unnamed; needs its own constant, distinct from
  the capsule commit constant its module already declares for a different
  record.
- `ProfileLabelHead.schema_version`
  (`.../custody/_label_head_models.py:75`) and
  `ProfileLabelHeadPendingAdvance.schema_version` (same file, line 168) —
  both durably written and read back through `model_validate_json` in
  `_label_head_repository.py:136,153`, each to its own file
  (`head_path` / `pending_path`). Unnamed; each needs its own constant since
  the two heads can version independently.
- `BucketDeletionFingerprint.schema_version`
  (`src/cadrumo/application/_bucket_deletion_contracts.py:28`) is the ONE
  entry I re-classify out of this bucket into NESTED SHAPE below — see that
  section.
- `OperationPersistedSnapshot.schema_version`
  (`src/cadrumo/application/operations/_journal.py:47`) — constructed in
  production at `_supervisor.py:143` and read back via
  `OperationPersistedSnapshot.model_validate_json` on the production
  persistence-integration and lease read paths. Unnamed; already sits at
  version 3 with no name ever attached to the number.
- `OperationLeaseObservation.schema_version` and
  `OperationLeaseResult.schema_version` (`.../operations/_leases.py:99,157`)
  — I re-classify these OUT of this bucket; see NOT A PERSISTED FORMAT below.
  Flagging here only to record that the landed gate's own bucket label
  ("unnamed sole declaration") undersells the finding: these are not
  merely unnamed, they are never durably read back at all.
- `ProfileCustodyHoldEvidence.schema_version`
  (`src/cadrumo/application/user_profile/_custody_hold_models.py:73`) —
  already ruled by the boundary ADR (`2026-08-15-profile-password-custody-nested-persisted-format-boundary-adr.md`):
  both parts of the test hold, pre-flagged `REGENERABLE` because
  `refresh()` unconditionally recomputes and overwrites the file every time
  rather than ever trusting a read. Still carries only the bare `Literal[1] = 1`
  default at `_custody_hold_models.py:73` — the naming and enrollment this ADR
  unblocked has not yet landed in `PERSISTED_FORMATS` or
  `CONSTANTS_AWAITING_CLASSIFICATION`.
- `_ProfileLoginHandoverJournal.schema_version`
  (`src/cadrumo/application/user_profile/_login_session.py:167`) — durably
  written to its own file (`_HANDOVER_JOURNAL_FILENAME =
  "profile-login-handover.v1.json"`) and read back via
  `_ProfileLoginHandoverJournal.model_validate_json` at `_login_session.py:386`.
  Unnamed.
- `M303FilingEnvelopeDefinition.schema_version`
  (`src/cadrumo/domain/calculations/registry/_schema_exports.py:133`) — I
  re-classify this OUT of this bucket; see NOT A PERSISTED FORMAT below.
- `TaxResidenceProfile.schema_version` and
  `RentaFamilyProfile.schema_version` (`domain/contribuyente/__init__.py:142`,
  `domain/contribuyente/_family_profile.py:50`) — I re-classify BOTH out of
  this bucket; see NOT A PERSISTED FORMAT below.
- **`RepairRemediationDecision.schema_version`
  (`src/cadrumo/application/repair_integrity.py:457`) — MISCLASSIFIED by the
  landed gate as a response contract. It is a genuine persisted format.**
  `RepairRemediationDecisionRepository.save_decision` writes
  `decision.model_dump_json()` as an encrypted AUDIT-class secure-object row
  (`repair_integrity.py:533-541`), and `load_decision` reads it back through
  `RepairRemediationDecision.model_validate_json(record.payload)`
  (`repair_integrity.py:560`). Its `schema_version` field is a SEPARATE axis
  from the namespace-level `REPAIR_DECISION_STORAGE_NAMESPACE.schema_version`
  passed to the secure-object envelope call — the same separation the
  boundary ADR already draws for `profile_record` against `secure_object`:
  the envelope governs how the row decrypts, this field governs whether the
  decision inside it can still be parsed. It clears both parts of the
  two-part test (independent grammar: never compared to the namespace
  token; durable readback: real bytes, real `model_validate_json` call) and
  is entirely unenrolled today — absent from `PERSISTED_FORMATS`, absent
  from `VERSIONED_FORMAT_IMPLEMENTATIONS`, and misplaced in
  `STANDING_LITERAL_VERSION_DECLARATIONS` under the `_RESPONSE_CONTRACT`
  reason, which is factually wrong for this one entry. I checked the other
  seven entries carrying that same reason and did not find the same defect
  repeated (see below); this is not a pattern of the shape being
  systematically misapplied to the whole bucket.

**Bucket (b): NOT A PERSISTED FORMAT — twelve entries (seven original
response-contract entries plus five re-classified in from "unnamed sole
declaration" above), each with no durable bytes of its own ever written and
read back under its own grammar.**

- `PerModeloAggregationContract.schema_version`
  (`application/aggregation/_service.py:133`) — built fresh from static
  registered providers on every call (`_service.py:295`), logged, returned;
  never serialized to disk or read back.
- `M145CommunicationServiceContract.schema_version`
  (`application/modelo/_m145_communication.py:63`), and the sibling
  `M145CommunicationValidationResult.schema_version` /
  `M145CommunicationExportResult.schema_version`
  (`application/modelo/_m145_communication_records.py:160,178`) — all three
  are `model_validate`d only inside test fixtures, never on a production
  read path; the export result's own docstring calls its byte-length and
  digest fields "a RECEIPT for payload", i.e. facts that get copied into a
  durably-persisted communication EVENT rather than this model's own bytes
  surviving.
- `OperatorSurfaceContract.schema_version`
  (`application/operator_surface/_models.py`) — built by
  `build_operator_surface_contract` for CLI adapters at call time; not
  written to disk.
- `CensoModeloFoundationContract.schema_version`
  (`domain/calculations/registry/_censo_modelos.py:98`) — same
  built-per-call service-contract shape, no persistence, no
  `model_validate_json` production call site found.
- `InventoryListRowPayload.schema_version`
  (`entrypoints/cli/_ledger_business_payloads.py:118`) — a CLI envelope
  `OutputSchema` row emitted over stdout for one command invocation, never
  durably stored.
- `OperationLeaseObservation.schema_version` and
  `OperationLeaseResult.schema_version` (`application/operations/_leases.py:99,157`)
  — returned by `inspect`/`acquire`/`compare_and_swap`/`release` on the lease
  port; the durable bytes on disk are `_OperationLeaseRecord`, which wraps
  the narrower `OperationOwnerLease`, never these two evidence/result shapes.
  No production `model_validate_json` call site for either exists; only
  tests construct them from JSON. The landed gate bucketed these as "unnamed
  sole declaration" (implying format-hood, only missing a name); I disagree
  with that placement — they fail durable readback outright and belong here.
- `M303FilingEnvelopeDefinition.schema_version`
  (`domain/calculations/registry/_schema_exports.py:133`) — a
  `RegistryModel`, i.e. bundled-registry-authored content compiled from the
  TOML authoring tree and shipped with the code release, not bytes the
  application durably writes for a taxpayer and promises to keep reading
  across future app versions. This is the same class already excluded via
  `SIDECAR_SCHEMA_VERSION` / `MANUAL_CORPUS_TEXT_SCHEMA_VERSION` in
  `CONSTANTS_OUTSIDE_THE_INVENTORY` — versioned with the code, replaced
  wholesale on upgrade. The landed gate's own comment on this entry already
  flags the same doubt ("whether it is a persisted format at all is part of
  the open question"); I resolve that doubt as "not one", on durable-readback
  grounds rather than proximity.
- `TaxResidenceProfile.schema_version`
  (`domain/contribuyente/__init__.py:142`) and
  `RentaFamilyProfile.schema_version`
  (`domain/contribuyente/_family_profile.py:50`) — neither class is ever
  constructed in production outside its own module and the registry-selector
  metadata that names it as a `profile_model` string alias. `RentaFamilyProfile`
  is rebuilt fresh on every resolution from primitive already-durable profile
  facts (`application/modelo/_profile_binding.py:347`, reading individual
  `renta_family.descendiente.N.*` keys out of a `fact_index`) and is never
  itself written to bytes. `TaxResidenceProfile` has no production
  construction site at all — grepped across `application/`, `entrypoints/`,
  and `adapters/` and found none; only the class definition, the
  `TaxResidenceProfileError` it can raise, and the `"TaxResidenceProfile.ccaa"`
  alias string used as a fact-index KEY NAME, not an instantiation. Both fail
  durable readback outright: no bytes of their own are ever written, so
  there is nothing on disk to guarantee readable under this grammar.

**Bucket (c): NESTED SHAPE — one entry, resolved by the boundary ADR's part
one (independent grammar).**

- `BucketDeletionFingerprint.schema_version`
  (`application/_bucket_deletion_contracts.py:28`) rides inside
  `ConfigResetTarget.fingerprint` as a nested pydantic field
  (`application/_config_reset_models.py:132`), and `ConfigResetTarget` is a
  member of `ConfigResetOperation.targets` — the already-enrolled
  `config_reset_journal` format (`CONFIG_RESET_SCHEMA_VERSION`,
  `REGENERABLE`). The whole `ConfigResetOperation` document is written and
  read as ONE JSON blob; `BucketDeletionFingerprint`'s own `schema_version`
  is never independently read, compared, or bound to anything — it rides
  inside the container's bytes under the container's version. Its only
  other use, in `application/bucket_maintenance/_contracts.py:47`, is nested
  inside a read-only, never-persisted assessment response. Fails part one
  (no independent grammar ever exercised): NOT a distinct format, fully
  covered by `config_reset_journal`. Do not name it.

**What I recommend naming versus leaving unnamed.** Name and enrol the twelve
entries in bucket (a) that are not yet named (all but the two
double-declarations, which already have names and instead need their model
defaults struck the way `S158`/`S159` struck theirs) — each is a real format
with its own durable bytes and its own read path, so a name is the enabling
move the boundary ADR argues for. Do NOT name any of the seven bucket-(b)
entries: naming a response contract or a bundled-registry grammar would
enrol a non-format into the durability inventory, which is the exact harm
this row exists to prevent. Do NOT give `BucketDeletionFingerprint` its own
entry; its container already covers it.

**Reverse-direction check (an enrolled name outliving its implementation).**
`test_every_bound_constant_still_exists_in_the_tree` and
`test_no_exclusion_outlives_the_constant_it_excuses` in
`test_persisted_format_enrolment_binding.py`, plus
`test_every_standing_entry_names_a_live_site` in
`test_persisted_version_single_declaration.py`, mechanically enforce exactly
this direction, and all three pass at current HEAD. I did not find any
enrolled `PERSISTED_FORMATS` key, bound version constant, or standing
literal-declaration entry that no longer resolves to a live class or
constant in the tree.

**Double-declaration input for S160.** Two direct hits for the mechanical
double-declaration detector: `RemoteMirrorNamespaceManifest.manifest_schema_version`
(constant `REMOTE_MIRROR_MANIFEST_SCHEMA_VERSION`, sibling module) and
`ProfileCustodyOwnerReceipt.schema_version` (constant
`CUSTODY_RECEIPT_SCHEMA_VERSION`, same module, sibling records already bind
it). Both are already named in `test_persisted_version_single_declaration.py`'s
`STANDING_LITERAL_VERSION_DECLARATIONS` table under the
`_DEAD_SECOND_DECLARATION` reason, so the detection and the paper trail
already exist; what remains is striking each model field's own literal
default the way `S158` struck the bundle's and `S159` struck the fincas
rows'.

## Notes

I did not edit any source file; per ownership, this row is read-only
triage plus this execution record. The concrete downstream actions this
triage unblocks — naming twelve constants and arguing a durability class for
each, striking two dead literal defaults, and correcting the
`RepairRemediationDecision` misclassification in the landed gate's standing
table — belong to whichever row or agent owns
`src/cadrumo/core/tests/test_persisted_version_single_declaration.py`,
`src/cadrumo/core/compatibility_lifecycle.py`, and
`src/cadrumo/application/repair_integrity.py`, none of which are in this
row's ownership grant.

All three gate modules covering this class
(`test_persisted_version_single_declaration.py`,
`test_persisted_format_enrolment_binding.py`,
`test_persisted_version_literal_inventory.py`) pass at twenty-two total
tests at current HEAD, confirming the population and standing tables I read
were not stale at the moment of this triage. Per the standing orchestration
guidance, this was re-confirmed at report time rather than trusted from the
first read.

Not checking the plan row, per instruction; that decision belongs to the
team lead.
