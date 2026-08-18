---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:ea12512cc66e0699b89221cec53cddbe2dd7fcbf0ed91c01556b54febb264233'
step_id: 'S164'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh collapse the storage layer's two live custody packages to one canonical home, since a forty-three module master_key package and a thirty-seven module custody package coexist at HEAD with production runtime and blob-store and crypto and envelope all importing the former, establishing first from the code whether this is a relocation that moved part of a package and stopped or an old-and-new split the cutover has not collapsed, and then landing the completed relocation atomically with every consumer in one commit rather than leaving the split documented and standing

## Scope

- `src/cadrumo/adapters/persistence/storage/`

## Description

- Enumerate both packages at HEAD: `master_key/` holds 16 production modules, a
  conftest and 24 test modules; `custody/` holds 28 production modules and 8 test
  modules.
- Build the production consumer map for `storage.master_key` and read both package
  facades in full.
- Search by meaning for a duplicate key-derivation implementation carrying a
  different name, rather than relying on a name-stem sweep.
- Read the governing decisions and the shipped absence gates.
- Classify every surviving `master_key/` module against the row's three categories.
- Conclude that the specified collapse must NOT be landed, and land no relocation.
- Repair one pre-existing red test inside the owned tree.

## Outcome

**The row's premise is wrong in both directions it offers, and the correction is
the deliverable.**

*It is not a relocation that moved part of a package and stopped.* `master_key/`
was created by the package-root rename to Cadrumo and predates the campaign
entirely; `custody/` was created later by `feat(profile): establish password
custody envelope` as a new feature package. Neither was ever a rename of the
other. The earlier step's relocation of the acceleration receipt, zeroise and the
base64 codec moved genuinely per-profile material into its correct home; it did
not begin a package rename that stalled.

*It is also not simply an old-and-new split the cutover "has not" collapsed.* The
collapse is ordered and blocked, by this campaign's own sequencing rather than by
neglect. The rejected bucket-key-schedule record establishes that the live default
store holds four pre-capsule buckets carrying roughly 6.25 MB of operator
ciphertext, that they depend on both retired surfaces, that migrating them is
closed off because reading their manifests is exactly the read-tolerance the
no-legacy rule forbids, and therefore that the retired route "may be deleted after
that step has run, and not before". The gating rows `W05.P08.S24` and
`W05.P08.S25` are both still open. A collapse landed now would delete a route the
campaign has explicitly ordered to survive until a destructive reset disposes of
that store.

**The classification the row asked for.** `master_key/` is not homogeneous, and
that non-homogeneity is why every reader keeps concluding the storage layer has
two custody packages.

*(a) Live session substrate that is current infrastructure, not legacy.* The
active-session module is the column-level encrypt path's session boundary, and it
documents the bucket session as the only legitimate owner of unlocked KEK and DEK
bytes. It, the bucket session, the live-session registry, the idle timeout, the
provider-session teardown, the reentrancy error, the bucket identity, the KDF
parameters and derivation primitives, the failed-login throttle and the tax-id
guard are all consumed on the live path: the storage runtime, the SQL secure
objects, the encrypted columns, the blob store, the profile-custody application
layer, the bundle encryption and the Google OAuth flow. This population is
misfiled under a `master_key` name; it is not retired.

*(b) Retired shared-master surface whose deletion is ordered but blocked.* The
provider family, the master-key IO and record modules, and the global BIP-39
recovery pair. The recovery pair is the documented recovery door for the four
stranded buckets, and the same record warns that removing it converts recovery
into reconstructing deleted code from history.

*(c) Genuine duplicates of something custody already implements: none.* The one
apparent overlap is Argon2id derivation, and it is constraint-shape-divergent
rather than duplicated. The custody worker varies both output length and Argon2
version per stored parameters; the master-key primitive fixes output length to
the key size and carries no version axis, so its constraint shape is not a
superset and the custody site is not promotable onto it. A shipped gate
independently forbids the supervised derivation child from importing the
`master_key` package at all.

**Why the collapse is refused rather than deferred for size.** Merging the two
would move a retired custody lifecycle into the package the accepted decision
names sole authority for current-format custody. That coexistence is precisely
what the hard-cutover absence gate exists to prevent, and it would breach the
worker import-graph gate in the same change. The correct end state is reached by
the opposite ordering and far more cheaply: once the ordered deletion removes
population (b), what remains in the package IS population (a), and the package
can simply be renamed to what it actually is. Splitting it now would do the work
twice and open a merge surface against the pending deletion.

**Landed:** no relocation, and no deletion. One repair inside the owned tree: the
locked-keychain error test asserted an English operator-category prefix without
pinning the output language, while the catalogue default is Spanish, so it
rendered "Bloqueado." and failed. It now pins the language through the
established override-and-flush pattern, which keeps the property under test
intact and makes it deterministic.

**Verified:** tree-wide collection at 25722 collected, 0 errors. Both package
suites plus the hard-cutover absence gate: 298 passed, 1 failed. The repaired test
passes; its pre-repair failure is itself the proof the assertion still bites.

## Notes

- The remaining red is pre-existing and outside this row's ownership: the
  hard-cutover gate's own anti-tautology proof, which asserts that a fixture
  naming no retired symbol is caught by the module net alone. The fixture now also
  trips the name net on `get_master_key`, so the proof no longer isolates the two
  nets. The gate's substantive absence assertions all pass; only its isolation
  proof is broken. It was red before this run touched anything and needs its own
  row.
- A keyring probe-budget test failed once under parallel execution and passed both
  in isolation and on an identical repeat run. Treated as a cross-test
  contamination flake, not a regression, on that evidence.
- The test repair was written to the working tree and then captured by a peer's
  broad commit under a docs subject before it could be committed under this row.
  The committed content was inspected and is exactly the intended change; no
  history was rewritten to re-attribute it. Nothing remained for this row to
  commit.
- No cryptographic parameter was changed, no derivation branch removed and no
  key-schedule code touched. The key-management confirmation the contract requires
  before removing a derivation branch does NOT hold today, which is an independent
  reason the retired surface was left standing.

- 2026-08-18 re-verification at HEAD: the ruling stands and its terminal state has arrived. The hard-cutover absence gate passes 12/12; the master_key facade documents the shared-master providers, backend resolver and passphrase-callback alias as deleted (the ordered population-(b) deletion has landed); the custody facade still declares current-format profile-scoped custody. The package split is the intended end state, structurally enforced — the row is closed as confirmed-ruling, no code change.
