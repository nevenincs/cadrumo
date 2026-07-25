---
tags:
  - '#adr'
  - '#bucket-manifest-durability'
date: '2026-07-25'
modified: '2026-07-26'
related:
  - "[[2026-07-25-code-dedup-sweep-adr]]"
  - "[[2026-07-25-compatibility-checkpoint-adr]]"
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
  - '[[2026-07-25-compatibility-checkpoint-research]]'
---

# `bucket-manifest-durability` adr: `the bucket manifest earns a forward version ceiling now and a tier floor at the checkpoint` | (**status:** `accepted`)

## Problem Statement

The bucket manifest is the plaintext TOML document at `<root>/buckets/<id>/manifest.toml`
that registers a bucket and names its key schedule. It carries a `schema_version` field, is
declared durable in the persisted-format inventory, and applies no version constraint on read
beyond the record model's lower bound. `read_manifest` in
`src/cadrumo/adapters/persistence/storage/bucket/_manifest_io.py` is the sole ingress for all
sixteen production consumers and gates nothing, so a manifest stamped by a newer application
loads, its key-schedule field reaches the branch that decides whether an existing data key is
unwrapped or a fresh one is minted, and five separate lifecycle writers preserve the foreign
version back to disk.

Two forces make the decision due now rather than at the checkpoint. First, the cost asymmetry
the parent record turns on, sharpened by a fact neither predecessor recorded: this format's
one and only version bump encoded a key-schedule change and landed inside a routing chore,
with nothing in the tree positioned to notice. Second, the tree has since acquired a gate that
makes the omission structural rather than latent. `2026-07-25-code-dedup-sweep-adr` carries
the gap forward under Consequences without ruling on it, and
`2026-07-25-compatibility-checkpoint-adr` holds the release checkpoint partly on it, naming as
a readiness condition that the manifest acquire a current-version constant, a durability
floor, and a tier lineage gate, or be reclassified with a recorded rationale. That alternative
is what this record closes, alongside the read gate neither predecessor addresses.

## Considerations

- The version is a bare local literal, not a constant. `manifest_schema_version = 2` at
  `src/cadrumo/application/user_profile/_profile_repository.py:330` is derived from nothing;
  no module-level current-version constant for this format exists anywhere in the tree. The
  record field is `Field(ge=1)` at `.../storage/bucket/_manifest.py:91`, and the aggregate
  carrying it (`.../user_profile/_aggregate.py:68`) repeats the same open shape.
- The bump history makes the axis concrete rather than hypothetical. The manifest was
  introduced at version 1 on 2026-05-21 (`7f2090c255`) and moved to
  `2 if key_schedule is BucketKeySchedule.BUCKET_DEK_V1 else 1` on 2026-05-26 in
  `78798a3f7a`, whose subject is `chore(storage): route profile repositories through
  runtime`. The conditional later collapsed to a bare `2` when the alternate schedule was
  deleted; the key-schedule enum now declares one member. So the only bump this format has
  taken changed the discriminator that selects the bucket's key handling, rode a commit that
  did not announce it, and no floor, gate, or test observed it.
- What the manifest actually decides at unlock, stated precisely because it is easy to
  overstate. `load_or_mint_bucket_dek` reads only `key_schedule` and branches on it: a
  recognised schedule unwraps the stored wrapped data key, an absent manifest is treated as an
  unregistered bucket (which on the bootstrap arm can MINT a fresh data key), and an
  unrecognised schedule refuses. The manifest's `kdf_params`, including its salt, have NO
  production consumer today — the `derive_kek` overload taking the manifest-side KDF record is
  called nowhere outside tests, and the master key derives from the separate `master.kdf`
  file, which carries its own version gate and its own typed refusal. So the manifest is the
  bucket's registration record and schedule discriminator, not the holder of the live unlock
  salt; any claim stronger than that is not supported by the tree.
- Read ingress is singular, which is what makes a gate cheap here. `model_validate` on the
  manifest record appears exactly once in production, at `_manifest_io.py:157`. Sixteen call
  sites reach it: three in `.../storage/master_key/_master_key_bucket_dek.py` (key schedule,
  idle window, absolute session cap), seven in `_profile_repository.py` (load, save, rename,
  delete, reactivate, complete_setup, label scan), one in `.../user_profile/_custody.py`,
  three in `.../application/workflow/_profile_bucket_scan.py`, and one each in
  `.../bucket_maintenance/_service.py` and `.../bucket_maintenance/_manifest_digest.py`.
  None applies a ceiling, a floor, or an equality.
- The pass-through is wider than the parent record states. Beyond `save` at
  `_profile_repository.py:478`, the rename, delete, reactivate, and complete_setup writers
  all use `model_copy`, which preserves the version field verbatim. A foreign version
  therefore survives every lifecycle mutation, not one.
- Model strictness catches the wrong half. The shared strict config forbids extra fields, so
  a future manifest that adds a key is refused, but as an unknown-key validation error, which
  reads as corruption. A future manifest that only bumps the version, or changes what an
  existing field means, is accepted in full.
- A raising gate is not automatically operator-visible. The scan helper in
  `_profile_bucket_scan.py` swallows every manifest read failure and continues, so a refused
  bucket vanishes from the profile list. The paired diagnosis surface
  `list_profile_bucket_scan_issues` would classify it, since the manifest's own
  validation-error type is in its exception set, but it has no production consumer; its only
  caller is a crash-window test.
- The manifest is unencrypted and unauthenticated by design, deliberately carrying no secret
  bytes (the Argon2 salt is public). Its version stamp is therefore not a security control:
  an actor with disk write sets it freely. A gate here defends against version skew, not
  tampering.
- The sealed archive is not a skew ingress, contrary to the obvious inference. The import
  path gates the archive container version, validates a bundle payload, and re-provisions
  through the canonical create span, so an imported bucket receives a locally-stamped
  manifest; the exported manifest travels only as the AEAD-bound digest anchor and is
  explicitly not recomputed against the host manifest. The live skew vectors are an
  application downgrade, two installs sharing one storage root, and a file-level restore of
  a bucket directory.
- The declaration is five durable formats; the tier set admits three. Verified at HEAD against
  the declaration itself rather than a commit message: `PERSISTED_FORMATS` in
  `src/cadrumo/core/compatibility_lifecycle.py` declares `secure_object`, `bundle`, `archive`,
  `bucket_dek`, and `bucket_manifest` durable, and five further formats regenerable, while
  `_CANONICAL_FORMAT_KEYS` in `src/cadrumo/tests/test_compatibility_lifecycle_gate.py` is the
  three tier formats only. No manifest lineage gate exists: the tree carries four lineage
  gates and two schema-readability functions, none for this format.
- A peer has since made that omission enforceable. Commit `998449a95f`, `feat(core): require
  every durable format to carry a frozen floor`, added the `unfloored_durable_formats`
  predicate and the gate `test_every_durable_format_carries_a_frozen_floor`, which names every
  durable format a frozen-floor mapping fails to cover and refuses instructively with both
  remedies: enroll the format with its floor machinery, or reclassify it regenerable if its
  bytes are genuinely rebuildable. The commit landed no vault record; the concept was already
  named as a readiness item in `2026-07-25-compatibility-checkpoint-research`, so this record
  cites that rather than forking the fact.
- The two enrollment gates now contradict each other for this format, which is the sharpest
  new fact. `test_every_released_floor_key_names_a_live_format_tier` requires every frozen
  floor key to be in the three-key canonical set; `test_every_durable_format_carries_a_frozen_floor`
  requires all five durable formats to carry one. Enrolling the manifest fails the
  first; omitting it fails the second. Both are vacuously green today because the floors
  mapping is `None`, so this is a latent deadlock rather than a red suite — but no flip mapping
  can satisfy both until the canonical set widens or the format is reclassified. Widening the
  canonical set is therefore no longer an enabling nicety; it is a precondition of any flip at
  all.
- The manifest does not meet the regenerable definition, on the tree's own terms. That class
  is declared for operational state the application rebuilds on demand — a session, a throttle
  sidecar, a crash-recovery journal, a lock — where delete-and-refuse is correct because the
  next operation reconstructs the record. The manifest is a registration record: its
  `created_at` is a host lifecycle timestamp that nothing can reconstruct (the archive path
  documents that such timestamps legitimately differ per host, which is why the export digest
  is deliberately not recomputed against the imported manifest); its plaintext `status` is the
  tombstone mirror every live operator surface reads WITHOUT unlocking the bucket, which is the
  leak the delete write-ordering exists to close; and its absence is not inert, since
  `load_or_mint_bucket_dek` reads an absent manifest as an unregistered bucket and can take a
  minting arm. Discarding it on a version mismatch does not degrade to "rebuilt next time".

## Considered options

- **A forward ceiling only.** Refuse a manifest above a named current-version constant and
  leave the floor and tier machinery alone. Cheap, lands today, arms the skew tripwire.
  Rejected as the whole answer: it leaves the format uncovered by the new durable-implies-floor
  gate and unenrollable by the canonical-key gate, so the checkpoint stays deadlocked.
- **Floor and tier enrollment only.** Add a floor constant, widen the canonical key set, land
  a lineage gate. Clears the deadlock. Rejected as the whole answer: the floor machinery is
  dormant until the flip, so this unblocks a checkpoint while leaving the read path exactly as
  permissive as it is today.
- **Reclassify the format regenerable.** The second remedy the peer's gate names, and the
  cheapest available: a regenerable format carries no floor, needs no lineage gate, and the
  deadlock dissolves. Rejected on evidence rather than instinct — the format fails the
  regenerable definition on three counts recorded above (an unreconstructible `created_at`, the
  plaintext tombstone mirror that gates every live surface without unlocking the bucket, and an
  absent manifest reading as an unregistered bucket on a path that can mint fresh key
  material). Delete-and-refuse, which is what the classification licenses, is the wrong policy
  for this file.
- **Enroll with the floor machinery AND add the forward ceiling (chosen).** One named
  current-version constant replaces the bare literal and feeds both a read-side range gate and
  a durability floor sourced from the regime policy; the canonical key set widens so the
  enrollment is admissible. Under the pre-release regime the floor equals current, so the range
  gate is an equality today and widens to a genuine range post-flip without a second edit.
- **Ship an upgrader registry alongside the gate.** Rejected as forbidden rather than merely
  premature: nothing has written a shape needing one, so both the registry and any fixture
  would be fabricated.

## Constraints

- No upgrader, no old-shape fixture, no read-tolerance branch. `no-legacy-compatibility`
  governs in full under the pre-release regime and permits only the refusal half. The upgrade
  machinery for this format ships absent; the first genuine post-flip bump pays for it.
- The floor must be sourced from the regime policy's expected-floor predicate, never pinned
  as a literal. That is what makes one gate correct in both regimes, and it is the shape the
  archive tier already proves.
- Widening the canonical format-key set is mandatory, not incidental. With the
  durable-implies-floor gate in the tree, leaving that set at three formats makes every
  possible flip mapping fail one gate or the other. Any implementation that adds a floor
  without widening the set has moved the deadlock rather than closed it.
- The refusal must be diagnosable, not merely raised. Because the bucket-scan path swallows
  read failures and continues, this decision is incomplete without an operator-reachable
  surface for the skew reason. A version refusal that silently removes a profile from the
  list trades one silent failure for a worse one, so wiring the existing scan-issues surface
  is part of the work rather than a follow-on.
- The refusal reason must be distinct from corruption. The existing manifest errors read as
  cannot-be-read or missing-lifecycle-status; reusing either misdirects the operator toward
  repair when the correct action is to upgrade the application. This is a new refusal reason
  and does therefore need a locale entry, unlike the parent record's sweep.
- The below-floor arm is a refusal, not tolerance, and may strand a locally-held version-1
  bucket. Under delete-not-migrate that is the correct posture, but it is a real cost and
  belongs in the change rather than in the discovery.
- This record depends on a proposed, not accepted, parent. If the checkpoint is instead
  resolved by flipping the regime, the read-gate half stands unchanged and the enrollment
  half becomes urgent rather than sequenced.
- Whether any installation outside the operator's own machines already holds a persisted
  manifest was not established, here or in the checkpoint research. If one does, the
  below-floor refusal acquires a blast radius this record has not sized.
- Every coordinate here was established by direct file read and targeted search against HEAD,
  including the five-versus-three declaration, which was read from the declaration table rather
  than taken from the peer commit message. Line numbers drift; a reader re-verifying should
  read both sides of each site as this pass did.

## Implementation

We will keep the bucket manifest classified durable, enroll it in the floor machinery rather
than reclassify it, and give it the same two-sided version contract the sealed-archive tier
already carries.

The bare literal at the create site is replaced by a named current-version constant declared
beside the manifest record in the storage bucket package, paired with a durability-floor
constant derived from the regime policy. The create site reads the constant; the save and
copy-based writers are unchanged, because the gate belongs on the read side, where a foreign
version actually enters.

`read_manifest` gains a range check between the floor and the current version, raising the
manifest's existing validation-error type with a new translated reason that names version
skew and distinguishes the above-current case, meaning upgrade the application, from the
below-floor case, meaning this bucket predates the guarantee. Keeping the existing exception
class is load-bearing rather than incidental: it is already in the bucket-scan exception set,
so the scan surfaces continue to classify the failure instead of propagating it raw.

The diagnosis path is closed in the same change. The scan-issues surface that already
captures this exception class is wired to an operator-reachable output, so a skewed bucket
announces itself rather than disappearing from the profile list.

For the checkpoint: the canonical format-key set in the central compatibility gate widens to
admit this format, which the deadlock makes a precondition rather than a convenience, and a
tier lineage gate lands beside the archive and bundle gates, asserting that the floor does not
exceed current, that it equals the regime-expected floor, that every version from floor to
current is readable, and that the next version above current is refused with the expected
translated key and context. No upgrader registry and no fixture ship: the format sits at its
floor and there is no old shape to read.

Held deliberately outside this record: `bucket_dek`, the other durable format the canonical
set omits and the second half of the checkpoint's readiness condition. Confirmed unfloored at
HEAD by the same reading, but it is a heavier and different decision — a wrapped key that
unlocks every byte in a bucket, whose schedule cannot be deleted or re-derived without owner
authorisation — and its strict single-value version field already refuses every direction of
drift, so its gap is enrollment rather than a read gate. Ruling on it here would bundle an
owner-gated key decision into a manifest decision. It needs its own record and its own owner.

One adjacent defect was found and is not ruled on here: the save writer reconstructs the
manifest and carries the idle-lock minutes forward but omits the absolute session minutes, so
every save silently resets that field. It is field loss on the same format, not a version
question, and belongs to whoever owns the session-lifetime surface.

## Rationale

The knockout criterion is that this format's version axis has already moved once, and moved on
the field that selects the bucket's key handling. Version 2 meant that the bucket is enrolled
in the per-bucket data-key schedule. A future version 3 is most plausibly the same class of
change, because that is the only class this format has ever needed to express. Today such a
manifest loads and its schedule field reaches the unwrap-or-mint branch with no signal, which
is the failure the project treats as most serious under `no-silent-under-declaration`: an
ambiguous payload reaching a consequential surface with nothing operator-visible.

Enrollment beats reclassification because the regenerable class is a promise about
reconstructibility, and this file is not reconstructible. The classification is not a
bookkeeping choice with a cheap side: it licenses delete-and-refuse, and applying that to the
registration record whose absence reads as an unregistered bucket is a materially worse
outcome than the version skew it would be dodging. The peer's gate offers both remedies
neutrally and correctly; the evidence decides between them, and it decides against the cheap
one.

The regime argues for acting rather than waiting, on the same asymmetry the parent record
turns on but with a sharper edge. A ceiling refusing a future shape is explicitly the blessed
category in both the no-legacy rule and the lifecycle rule: it reads no old shape and migrates
nothing. The below-floor arm is nearly free today only because the floor equals current under
the pre-release regime, so the gate is an equality and there is no released version beneath it
to strand. After the flip the floor freezes, the same gate becomes a genuine range, and adding
it then means arguing a new refusal against manifests a taxpayer's installation already holds.

Taking both halves rather than either is what makes the record whole, and the new gate makes
that sharper than it was. The ceiling has teeth today and none at the flip; the enrollment has
none today and is now a hard checkpoint blocker rather than a soft one, because the two
enrollment gates cannot both be satisfied for this format until it is either enrolled or
reclassified. They share one constant, one floor, and one gate, so splitting them would mean
touching the same sites twice.

The honest limit is the threat model. This is a plaintext, unauthenticated file, so the gate
buys nothing against an actor who can write to disk. It buys correct behaviour under ordinary
version skew, meaning a downgrade, a shared storage root, or a restored backup, and a correct
diagnosis in place of a misleading one. That is a modest claim, and this record should not be
read as making a larger one.

## Consequences

- Good: the format acquires a named version constant, so its next bump becomes a visible edit
  to a declared authority rather than a digit inside an unrelated commit, which is exactly how
  the last one landed.
- Good: the checkpoint deadlock is closed for this format. With the durable-implies-floor gate
  in the tree, a flip mapping that omits the manifest fails one gate and one that includes it
  fails the other; enrolling it and widening the canonical set makes a passing flip mapping
  possible. `bucket_dek` still blocks, so this does not by itself unblock the flip.
- Good: a skewed bucket produces a specific, actionable refusal instead of either silent
  acceptance or silent disappearance, and a diagnosis surface that already existed stops being
  dead code.
- Accepted cost: a new refusal reason with its locale entry, a fifth lineage gate, and two new
  constants in a substrate that already carries several per-tier version pairs. The uniformity
  is the point, but the constant count grows.
- Accepted cost, and the sharpest one: a below-floor manifest is refused rather than read.
  Under the pre-release regime the floor equals current, so any version-1 bucket still on a
  developer's disk is refused with no path back other than recreating the profile. That is
  delete-not-migrate applied honestly, and it is cheaper now than at any later point.
- Accepted cost: choosing enrollment over reclassification takes on a permanent obligation. At
  the flip this format's floor freezes, and every later bump owes a one-hop reader and a
  committed pre-bump fixture. Reclassifying would have cost nothing and promised nothing; the
  evidence says the nothing it promised was the wrong promise.
- Bad, and deliberately accepted: the gate cannot be proven against a real future manifest,
  only against a synthetic one stamped above current. That is the same vacuity the parent
  record accepts for the inner-envelope tightening, and it becomes substantive on the first
  genuine bump.
- Neutral: no write path changes shape and no persisted bytes move, so a bucket already at the
  current version is unaffected on every surface.
- Open: this record rules on the manifest only. `bucket_dek` remains durable, unfloored, and
  outside the canonical set, and is now the single remaining format holding the enrollment
  deadlock open. The undeclared blob manifest the checkpoint record also names remains
  unowned. The durable-implies-floor predicate that record asked for has since landed and is
  no longer open.


### Ruling

Ruled `accepted` on the chosen option — enrollment with the floor machinery plus
the forward ceiling — by the agent that carried this gap forward. It closes S06
of `2026-07-25-code-dedup-sweep-plan`, which asked for exactly this: the
bucket-manifest version gap ruled in its own record under the durability framing,
rather than left in a parent record's out-of-scope note where it would rot.

The reasoning holds and the evidence is stronger than the record that surfaced
the gap. Two things decide it. Enrollment beats reclassification on evidence
rather than preference: the format fails the regenerable definition on three
independent counts, and that class licenses delete-and-refuse, which applied to a
registration record whose absence reads as an unregistered bucket — on a path
that can mint fresh key material — is worse than the skew it would dodge. And the
cost asymmetry is sharper here than in the parent: this format's only bump encoded
a key-schedule change and rode a routing chore, so the axis has already moved once
unobserved on the field that selects key handling.

The two-sided shape is also the one my own parent ruling identified as correct.
That record named the sealed-archive tier's ceiling-paired-with-floor as the
canonical shape and placed it out of scope only because it guards a different
layer. Bringing the manifest onto that same shape makes the substrate uniform
rather than adding a fourth convention.

Three caveats are accepted rather than waved through, because the record raises
them itself and a ruling that ignored them would be worth less than the record.

The unsized blast radius is real but bounded by the regime, not by luck. The
record correctly declines to claim that no installation outside the operator's
machines holds a persisted manifest. Under `PRE_RELEASE` there is no released
data by definition, so the below-floor arm's practical reach today is a
developer's own disk — and the record already states that cost plainly. If the
regime flips before this lands, the below-floor arm must be re-sized before the
gate ships, because the same refusal then meets manifests a taxpayer's install
already holds. That sequencing is a condition of this acceptance, not a footnote.

The proposed-parent dependency does not block acceptance, because the record is
robust to either resolution: the read-gate half stands unchanged whichever way the
checkpoint goes, and the enrollment half merely changes from sequenced to urgent.
An acceptance that waited on the parent would hold a ceiling hostage to a
decision it does not depend on.

The threat-model limit is stated correctly and should survive into the commit
message. This is a plaintext unauthenticated file; the gate buys correct behaviour
under ordinary version skew and a correct diagnosis, and nothing against an actor
with disk write. A later reader who mistakes it for a security control will draw
the wrong conclusion about what else needs protecting.

Two items the record holds outside itself are endorsed as held rather than
deferred by omission: `bucket_dek` genuinely needs its own owner-gated record
rather than being bundled into a manifest decision, and the save-writer field loss
on absolute session minutes is a different defect on the same format and belongs
to the session-lifetime surface. Both are named here so neither is lost.
