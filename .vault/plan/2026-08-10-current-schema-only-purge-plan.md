---
tags:
  - '#plan'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_hash: 'sha256:5fbec104f740e28fbecfc14e7554caccd12147d923c142dc4e66ed7fc5d286a2'
tier: L3
related:
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-06-10-zero-legacy-purge-research]]'
---

<!-- RETIRED: P02 -->

# `current-schema-only-purge` plan

## Description

Delete every confirmed read-tolerance, missing-marker default, and bare-payload
coercion that permits this pre-release application to hydrate or persist anything
other than its current schemas. The compatibility-lifecycle decision governs exact
current-version refusal and preservation of dormant forward-only lineage controls.
The secure-persistence decision governs fail-closed encrypted parsing and requires
schema mismatches to stop before key derivation or decryption.

This plan does not delete empty upgrader registries, regime gates, durability-floor
checks, or future-version refusal scaffolds because they read no obsolete shape. It
does not reinterpret AEAT regulatory revisions or external-source variability as
application legacy. Workflow action-detail compatibility remains exclusively owned by
the CLI action-envelope plan and is not duplicated here.

Version numbers appearing in this plan's Phase headings and Step rows are the
values this document ASSERTED when it was authored. They are a record of intent,
never an assertion about HEAD, and they must not be read as evidence that the
tree carries them. The profile phase is the worked example and it is worth
stating exactly: the plan says "version 4", the record's field defaulted to 1,
and the canonical user-profile schema in fact declares 5. All three numbers were
different, and the plan's was wrong when it was written -- not stale, wrong.

That is why every implementing change reads the current version from its schema
authority instead of inlining a literal at the call site. Had the remedy been
"set it to 4" the plan's own error would have been compiled into the code. A
literal 5 written today would be the same defect one revision later, and the
gate this plan installs found exactly that shape: hardcoded version literals in
seeded fixtures, refused the moment exact equality replaced the ceiling.

## Steps

## Wave `W01` - Pin domain records to current schema

Eliminate pre-current domain hydration and bare catalogue coercion before tightening
encrypted storage boundaries.

### Phase `W01.P01` - Require User Profile schema v4

Make live profile records and immutable snapshots accept exactly the canonical version
4 schema.

- [x] `W01.P01.S01` - Require exact schema id and schema version 4 for UserProfileRecord and UserProfileSnapshot; `src/cadrumo/domain/user_profile/_values.py`.
- [x] `W01.P01.S02` - Stamp newly created profile records explicitly with the canonical schema version; `src/cadrumo/application/user_profile/_lifecycle.py`.
- [x] `W01.P01.S03` - Prove current profile schema hydration and non-current marker refusal; `src/cadrumo/domain/user_profile/tests/test_payload_schema_identity.py`.
- [x] `W01.P01.S24` - Refuse a persisted profile payload that omits schema_version at both profile read boundaries, rather than making the field required. Required-ness was NOT taken because 229 of the 231 construction sites are in-memory test and harness constructions that are not the defect, while the defect is bytes hydrating as current. What required-ness would still buy, and what this row therefore does not deliver, is making the unstamped state unconstructable in memory as well as unreadable from disk; `src/cadrumo/application/user_profile/_repository.py at both the record load and the snapshot load, never in the shared SecureBoundRepository whose generic path serves other namespaces`.

### Phase `W01.P03` - Pin the active bucket pointer format

Require the exact current active-profile pointer marker at the TOML boundary.

- [x] `W01.P03.S04` - Define and require the exact current BucketPointer schema marker; `src/cadrumo/core/_bucket_pointer.py`.
- [x] `W01.P03.S05` - Prove current BucketPointer round trips and non-current marker refusal; `src/cadrumo/core/tests/test_bucket_pointer.py`.

### Phase `W01.P04` - Remove InvoiceCatalogue bare-payload coercion

Require the canonical invoices wrapper while preserving the explicit construction API.

- [x] `W01.P04.S06` - Delete mapping-without-invoices coercion from InvoiceCatalogue validation; `src/cadrumo/domain/invoices/_models.py`.
- [x] `W01.P04.S07` - Prove serialized catalogues require the canonical invoices wrapper; `src/cadrumo/domain/invoices/tests/test_catalogue.py`.

## Wave `W02` - Require cryptographic and persistence markers

Require every current storage discriminator at parsing time and before cryptographic
use without changing forward-only lineage machinery.

### Phase `W02.P05` - Harden encrypted wrapper markers

Make all encrypted wrapper format claims explicit and exact before key access.

- [x] `W02.P05.S08` - Require and explicitly write the exact current CipherEnvelope marker; `src/cadrumo/adapters/persistence/storage/envelope/_envelope.py`.
- [x] `W02.P05.S09` - Prove CipherEnvelope marker refusal occurs before master-key access; `src/cadrumo/adapters/persistence/storage/envelope/tests/test_cipher_envelope_version_gate.py`.
- [x] `W02.P05.S10` - Require and preflight the exact current WrappedMasterKey marker before decryption; `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`.
- [x] `W02.P05.S11` - Prove wrapped-master-key marker refusal precedes real unwrap; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`.
- [x] `W02.P05.S12` - Require explicit current encrypted-bundle envelope payload and KDF markers; `src/cadrumo/application/user_profile/_bundle_encryption.py`.
- [x] `W02.P05.S13` - Prove encrypted-bundle marker refusal and current passphrase round trip; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [x] `W02.P05.S25` - Gate the encrypted-bundle kdf_version marker against the current Argon2 version, promoting that version onto the master-key package facade as the precondition; `src/cadrumo/application/user_profile/_bundle_encryption.py and the master-key package facade that must export the Argon2 version constant`.

### Phase `W02.P06` - Harden local custody metadata

Require current index KDF and key-schedule markers on every local custody read and
write.

- [x] `W02.P06.S14` - Require and explicitly write the exact current SecretIndex marker; `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`.
- [x] `W02.P06.S15` - Prove missing and non-current secret-index markers refuse real store operations; `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`.
- [ ] `W02.P06.S16` - Require the exact current KdfParameters version marker; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`.
- [ ] `W02.P06.S17` - Stamp current KDF markers during key mint and recovery; `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`.
- [ ] `W02.P06.S18` - Prove file-fallback key loading refuses missing and non-current KDF markers; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`.
- [ ] `W02.P06.S19` - Make BucketManifest key_schedule mandatory; `src/cadrumo/adapters/persistence/storage/bucket/_manifest.py`.
- [ ] `W02.P06.S20` - Prove real manifest reads require and preserve the current key schedule; `src/cadrumo/adapters/persistence/storage/bucket/tests/test_manifest_io.py`.
- [x] `W02.P06.S26` - Make the master-key KDF preflight model require a real version, replacing the optional-and-defaulting-to-absent field that lets a marker-less file pass the check the preflight exists to perform; `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py preflight model and its single read call site, with no writer or derivation path touched`.

## Wave `W03` - Close the Modelo 303 observation write boundary

Prevent any official Modelo 303 observation from persisting without its resolved typed
result disposition.

### Phase `W03.P07` - Require disposition before persistence

Fail official Modelo 303 observation writes before repository mutation when
`result_disposition` is absent.

- [ ] `W03.P07.S21` - REOPENED AFTER REVERT, AND ITS HOLE FEEDS A LIVE DEFECT. Refuse an official Modelo 303 observation persisted with no resolved result disposition, at a boundary where the legitimate and under-declaring populations can actually be told apart. Two attempts at the envelope boundary both over-refused because the carry-casilla condition collapses to is-an-M303-observation and the legitimate population carries no header either. THIS ROW AND THE WALLET-GATE ROW ARE ONE HOLE FROM TWO ENDS: this end lets a non-canonical envelope be written because the normalise flag defaults off, and that end converts the resulting unreadable envelope into a proven first-period zero. The hole was rated a future-bypass risk and is in fact feeding a live laundering path; `boundary to be determined, NOT prepare_observation_envelope which has been tried twice and reverted. The static caller-side gate is now justified as cutting supply to a live defect rather than as closing a future bypass`.
- [x] `W03.P07.S22` - Require Modelo 303 result_disposition before any filing persistence write. Cause of the two failures standing against this row is now established and it is NOT this row. Both frames come from one pre-existing red test that calls persist_filed_revision directly, passing an observation repository and no disposition, so the guard in its ORIGINAL downstream position refused it identically. The hoist moved only where the refusal is raised, from after five repository writes to before them, which is what the row asked for and which improves that test's failure rather than causing it; `src/cadrumo/application/modelo/_revision_persistence.py and the extracted guard in _filed_revision_observation.py`.
- [ ] `W03.P07.S23` - Prove under-declared Modelo 303 observations are refused and current dispositions round trip; `src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py`.
- [ ] `W03.P07.S27` - Resolve the red prorrata settlement-writeback test, which calls persist_filed_revision directly with an observation repository and no disposition. BLOCKED ON the ADR amendment: it is red for the same root cause the amendment exists to decide, a filing-boundary requirement sitting on a caller that is not filing, and a local repair here would paper over exactly that question; `src/cadrumo/application/calculations/tests/test_prorrata_regularizacion.py and whatever the amendment rules the filing requirement should key on`.
- [x] `W03.P07.S28` - Establish what the M303 carry normalisation path actually is, given that production READERS call it directly and are then required to supply a fact only a filing produces. The iva compensation history module, the annual partition loader and the iva wallet gate all call the normalise or validate functions without the door opt-in, so the gated ingress is not a filing boundary either and the remedy of moving the screen inside it is not available; `src/cadrumo/application/calculations/_m303_carry_ingress.py and its direct callers in _iva_compensation_history.py, _iva_compensation_annual_partition.py and modelo/_iva_wallet_gate.py`.
- [x] `W03.P07.S29` - SEVERE AND LIVE, ESTABLISHED NOT INFERRED. An operator CLI verb records a Modelo 303 local observation with no modelo restriction and without the normalise flag, which defaults off, so the envelope is non-canonical by construction. The wallet gate loads by modelo and period with NO source-kind filter, hits the fixed-point assertion, swallows the refusal, and returns nothing. Its single consumer does not branch and passes that nothing through alongside an activity-start first-period proof, so an uninterpretable envelope becomes a proven first-period zero on a compensacion. THE FIX IS ADDITIVE AND DELIBERATELY NARROW. It cuts the one link that cannot over-scope, which is the swallowed refusal being indistinguishable from a genuine absence at the consumer, and it leaves a genuine absence still proving first period because that is the population an additive change must not touch. IT DOES NOT CLOSE THE OTHER FIVE MOUTHS of the same collapse and must not be read as the resolution of them, which is a separate row on the shared return type. The two prior reverts in this campaign were both RESTRICTIVE changes at shared boundaries whose legitimate population nobody had counted, and additive is what structurally cannot repeat that. The measurement that makes the containment real: the resolver has exactly one caller and the activity-start predicate exactly two, all three inside this one module, so no shared signature and no consumer sweep is involved. Correct in the same commit the production comment at the flag consumer which asserts that only the genuinely-absent case is mapped to zero, because that sentence is precisely what the code does not do. THIS ROW AND THE REVERTED DISPOSITION-SCREEN ROW ARE ONE HOLE FROM TWO ENDS: that end leaves the write side open, this end launders the consequence. The reverted screen would NOT have caught this path anyway because it scoped to official sources and this write stamps OPERATOR_MANUAL, so the write side currently has no guard at all for any source kind and the eventual static gate must be scoped by what a caller writes into a shared persistence door rather than by source-kind officialness. The close condition includes proving a genuine absence still proves first period; `src/cadrumo/application/modelo/_iva_wallet_gate.py at the swallow and its single consumer, and the false only-the-genuinely-absent-case comment in _iva_wallet_reconciliation.py`.
- [ ] `W03.P07.S30` - Decide where the Modelo 303 filing-disposition requirement belongs, then land it there as a STATIC author-facing gate. Both runtime candidates are measured out by the 2026-08-10 ADR amendment and neither may be re-proposed. The wide persistence door is a shared primitive with 14 direct call sites, and the gated ingress is a shared normalisation path that two writers, three readers and a gate all traverse. The mechanism is static because the discriminating fact, is this a filing path, is available at the CALL SITE and was never available in the payload, so the gate constrains authors rather than payloads and costs the test corpus nothing. Write the PROPERTY, that a production caller of the shared door either does not write official-source-kind observations or passes the ingress, and let Modelo 303 fall out of it rather than naming the modelo. The disconfirming observation that decides this row: if the property cannot be expressed without naming Modelo 303, that is evidence the requirement is not about the door at all and the row must stop and report rather than encode the name. State a control proving every legitimate caller still passes, and do not close on the refusal firing; `src/cadrumo/application/calculations/, src/cadrumo/tests/`.
- [ ] `W03.P07.S31` - Own the carry-ingress refusal swallow at the IVA wallet gate. ITS CONSEQUENCE CHANGED WHEN THE LAUNDERING ROW LANDED and the row must be re-read against that, not against its original framing. The swallow no longer produces a proven zero, because a stored-but-unusable observation now blocks. What it produces instead is a refusal that cannot distinguish we found no prior period from we found one and could not read it, and that distinction is now OPERATOR-FACING rather than internal. The reason it is operator-facing: the seeded-history refusal text instructs the operator to seed the opening balance with amount zero and confirm, which is correct guidance for a genuine first filing and is the reconstruction of the exact under-declaration the laundering row closed when the prior period existed but was unreadable. So a fix that only blocks moves the wrong number from being computed silently to being typed in on instruction. MEASURE BEFORE ASSERTING which refusal a taxpayer in this state actually reaches, because two candidates exist, the not-seeded message and the generic blocked message carrying a divergence and reason, and they differ in exactly whether the zero-seed instruction is shown. The disconfirming observation that decides this row: if the unreadable-envelope case provably reaches the generic blocked refusal and never the zero-seed instruction, the operator hazard does not exist and this row is an internal-quality question again rather than a safety one; `src/cadrumo/application/modelo/_iva_wallet_gate.py at the swallow and the three refusal sites, and the seeded-history refusal text carried in the locale catalogues`.
- [ ] `W03.P07.S32` - Decide whether the filing-grade Modelo 303 carry gate should admit an OPERATOR_MANUAL observation at all. The load is keyed by modelo and period with no source-kind filter, so an operator-recorded row is admitted into a gate whose own normalisation accepts only official AEAT or app_filing provenance and therefore refuses it a moment later. The standing position is that operator-manual sources are non-official and remain blocking, which makes admitting them questionable independent of whether they can be read. THIS IS A RESTRICTIVE CHANGE WITH AN UNCOUNTED POPULATION and it is deliberately NOT folded into the live-defect row, because changing what the gate loads has the same shape as the two changes this campaign already over-scoped and reverted. Measure the admitted population before proposing a filter. The disconfirming observation that decides this row: if any legitimate flow depends on this gate reading a non-official observation, a source-kind filter is the wrong remedy and the row must report that rather than land one; `src/cadrumo/application/modelo/_iva_wallet_gate.py at the load call and the requirement resolution above it`.
- [ ] `W03.P07.S33` - Establish which onboarding paths set the profile activity-start date and whether any completed onboarding can produce a profile without it. This is the code-answerable half of a question that was asked as a frequency and correctly refused as one, because how many real profiles carry the field is about taxpayer data rather than about branches. If every path sets it then ordinary-for-a-genuine-new-filer follows structurally with no real profile needed, and if some path leaves it unset that is a second finding about onboarding rather than a frequency estimate. Do not block the live-defect row on this and do not convert the answer into a severity label. The disconfirming observation that decides this row: if the field can be set after the fact by an ordinary profile edit rather than only at onboarding, enumerating onboarding paths does not answer the question at all and the row must say so; `the profile creation and censo application paths that write the activity-start field, read only`.

## Parallelization

Waves remain ordered. Within W01, the profile, pointer, and invoice Phases are
file-disjoint and may execute in parallel. Within W02, each encrypted format may be
implemented independently, but every production Step precedes its paired real-behavior
test and KDF record validation precedes KDF minting. W03 waits for the current-schema
domain and storage boundaries so its final integration proof measures the completed
state. No worker may touch workflow action compatibility or dormant lineage machinery.

## Verification

- Parse current serialized records through production loaders and reject missing,
  pre-current, and future markers without coercion.
- Prove cryptographic marker refusal occurs before key derivation or decryption and
  retain real current-format positive round trips.
- Prove an under-declared Modelo 303 write leaves repositories unchanged, followed by
  a successful disposition-bearing round trip.
- Use production imports and real storage adapters; no fakes, mocks, stubs, patches,
  monkeypatches, skips, or expected failures.
- Run focused pytest, path-scoped Ruff and strict BasedPyright, plan and Vault checks,
  and a final semantic plus lexical sweep showing no listed compatibility branch or
  default remains.
- Complete a fresh-context code review before closing the campaign.
