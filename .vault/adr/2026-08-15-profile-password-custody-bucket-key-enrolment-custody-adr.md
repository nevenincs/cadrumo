---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:04187174dd537cbd43621b7d6e8326846aeaf9bcafedc0ac5641359a510b52f2'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-15-profile-password-custody-bucket-key-schedule-custody-mismatch-adr]]"
---
# `profile-password-custody` adr: `bucket key enrolment custody` | (**status:** `accepted`)

## Problem Statement

A bucket is enrolled in exactly one custody, and this record settles which
one, so that the question stops being re-derived from whatever artefact a
reader happens to find on disk.

The row that opened this record asserted a defect: that a bucket counts as
registered purely because its capsule exists rather than by any stored
enrolment; that registration permanently refuses minting by tested design; and
that the only window to mint the wrapped bucket key therefore closes at capsule
publication behind a flag no production code passes true, leaving **no path
that creates a bucket the storage layer will open.**

**That premise does not survive measurement, and this record's first job is to
say so.** It is the second time this shape of claim has been raised and the
second time it has failed the same way. The rejected sibling record
`2026-08-15-profile-password-custody-bucket-key-schedule-custody-mismatch-adr`
already established the pattern: a probe created a profile and read a record
*without logging in*, observed the refusal registration deliberately installs,
and reported a routine lock as a missing key.

The corrected measurement runs the whole door and is recorded in the S110
execution record. Create through `register_profile_with_credentials`,
authenticate through `login_profile`, then read: the secure-object repository
for the active bucket returns the real namespaces, the namespace integrity
probe unwraps every profile row with zero unreadable, and the workflow state
record loads. A bucket created today opens.

A second, independent fact retires the premise's mechanism entirely. Every
symbol the row names is gone from the tree: `_master_key_bucket_dek.py`,
`bucket_key_schedule`, `load_or_mint_bucket_dek`, the `allow_bootstrap_mint`
flag, and the `BucketKeySchedule` enum. The retired keystore route was deleted
ahead of this row landing. There is no resolver left to mis-state a schedule
and no mint window left to close.

So the decision this record owns is not a repair. It is the ruling that fixes
the answer, and the pinning of the property in a regression that reaches an
actual record read through the sanctioned door — which is precisely the
measurement whose absence let the wrong claim be made twice.

## Considerations

- The corrected end-to-end measurement succeeds at every step; details and
  observed values are in the S110 execution record.
- The retired route's symbols are absent from the tree; the only surviving
  `key_schedule` field is the custody envelope's own
  `Literal["profile-password-dek-wrap/v1"]` in `storage/custody/_records.py`.
- A bucket created through the door today carries `custody/envelope.v1.json`,
  `data/dek.sentinel.v1.json`, `profile.commit.v1.json` and `db/cadrumo.db`,
  and carries **no** `manifest.toml` and **no** keystore entry.
- The live default store holds zero capsule-era buckets; its four buckets all
  predate the cutover. Re-measured read-only and reported under Consequences.
- The exposure argument that defeated minting a second wrapped copy never
  depended on the false premise, and is restated below because it is the
  durable half of the sibling record.

## Considered options

**A — the resolver reads stored custody (adopted, as the end state already
reached).** A bucket's enrolment is the custody material it actually carries,
never an inference from the existence of some other artefact. Every read
resolves the key through the capsule's own password custody. Adopted, with the
correction that the tree arrived here by deleting the competing route rather
than by teaching a resolver to choose between two — which is the stronger form
of the same answer, because a resolver that cannot be wrong beats a resolver
that reads correctly.

**B — mint a second wrapped copy of the DEK at creation (rejected).** Have the
creation door mint the wrapped bucket key before publishing the capsule, so
the retired route's artefact exists for every bucket and ordering becomes the
requirement. **Rejected on exposure, not on cost.** Minting that copy would
wrap the same DEK under a second, different key-encryption key, permanently,
for every profile. A keychain or master-key compromise would then yield the
bucket DEK **without the operator's passphrase**, defeating the exact property
the capsule cutover was undertaken to establish, and enrolling every bucket in
two schedules at once — the one thing a key schedule exists to make
unambiguous. This is the defeating argument, and it survives independently of
whether the defect was real.

**C — relax the never-mint-after-registration guard (rejected outright).**
Would let a registered bucket acquire a second key silently, which is the
state that guard exists to make impossible. It treats a symptom while leaving
the ambiguity in place, and it is a key-management weakening, which is
owner-gated rather than autonomous.

**D — act on the row as written and repair the defect (rejected as
unfounded).** Recorded so a future reader can see it was considered rather
than overlooked. Defeated by measurement: there is no unopenable bucket to
repair and no resolver left to correct. Acting here would have written a
change against a state the tree does not hold.

## Constraints

- Key-schedule and DEK-derivation changes are owner-gated under
  `no-legacy-compatibility`; this record enacts no such change.
- The never-mint guard must remain correct and unweakened. Option A satisfies
  it without modification, because a bucket under one custody never needs
  minting.
- The four pre-capsule buckets on the live store depend on surfaces the
  cutover retired. Their disposal is ordered behind `W05.P08.S24` and
  performed by `W05.P08.S25`; nothing here touches them.
- `no-legacy-compatibility` forbids a read-tolerance branch for the
  pre-current manifest shape, which is what a migration of those buckets would
  require.

## Implementation

Nothing is built here, because the code state this record rules on is already
the tree's state. What lands with this record is the proof.

The regression restores a test name the sibling record's rejection deleted —
the earlier version asserted a record read with no intervening login, encoding
the measurement error rather than a defect — and rebuilds it correctly around
the whole door. It lives beside the session substrate it exercises, under
`storage/master_key/tests/`, and it is three tests rather than one because a
single passing readback proves less than it appears to.

The first creates through the sanctioned door, authenticates, and then asserts
decryptability through the namespace integrity probe, which unwraps every row
under the session key and returns counts rather than plaintext. The second
asserts that the *same two calls* refuse before authentication, with the
shared not-ready refusal key: without it a door that never locked would
satisfy the first test equally, and it is what makes the login step
load-bearing rather than incidental. The third is the anti-tautology proof —
overwrite the persisted custody envelope and lose the login, so the readback
cannot be served by anything the create span left in process memory.

The refusal the third test pins names the current format rather than reaching
for an older one, which is the no-legacy posture stated as a test: a custody
envelope that does not parse as the current record is corruption now, not a
shape to tolerate.

## Consequences

**No failing regression is left behind, and that is a deliberate outcome
rather than a shortfall against the row.** The row asked for a failing
regression pinning the defect. There is no defect to pin. Landing a red test
here would assert a state the tree does not hold, which is exactly the error
the sibling record was rejected for, dressed as rigour. The regression is
green because the property is true, and the second and third tests are what
stop that green from being cheap.

**No migration question exists.** Re-measured read-only against the live
default store on 2026-08-15, unchanged from the sibling record's count: four
buckets, all pre-capsule, holding 6,250,496 bytes of `db/cadrumo.db`, each
carrying a retired `manifest.toml` and a retired keystore entry, with **no
capsule material of any kind** anywhere beneath the store. Zero capsule-era
buckets exist on real disk, so the population the row asked about — a profile
created through the sanctioned door and left unopenable — is empty. Nothing
was opened, minted, migrated, repaired or deleted to establish this.

Those four buckets are unreadable by the current tree, and now for a further
reason the sibling record could not yet state: the bucket manifest model and
its reader have since been retired as well, so there is no longer any code
that can parse their manifests at all. Their disposition is already owned by
`W05.P08.S25` and is untouched here. What changed is only that the question is
now closed rather than open — it was never a question about capsule-era
buckets, because there are none.

**The honest cost of option A is concentration.** A custody path used at
creation and login is now the path every record access depends on, with no
second route behind it. That is the price of not holding a second wrapped key,
and it should be weighed as such rather than assumed free — the exposure
argument buys single custody, and single custody buys a single point of
failure. It is the right trade, and it is a trade.

**A durable lesson, since this is the second occurrence.** A refusal observed
on a locked profile is not evidence about key material. Two records now rest
on that confusion, and the cheap discriminator was always available: run the
authentication step. The regression this record lands is that discriminator,
made permanent, in the one place a future probe would look first.
