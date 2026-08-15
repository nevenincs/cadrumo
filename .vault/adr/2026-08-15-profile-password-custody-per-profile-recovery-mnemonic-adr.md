---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8f0503ff7ec25f3899f9178836afb8178edbab2d35e7fa477576071879a6b34b'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` adr: `per profile recovery mnemonic` | (**status:** `accepted`)

## Problem Statement

The BIP-39 mnemonic codec and its bundled 2048-word canonical wordlist in
`src/cadrumo/adapters/persistence/storage/master_key/_recovery.py` have no
consumer anywhere in the tree. The originating row framed the choice as
split-them-out or delete-both-halves, and asked for the product question to be
ruled first: will per-profile recovery adopt the mnemonic at all.

The question is load-bearing rather than housekeeping. The operator
documentation for data access was rewritten in this same campaign to delete its
recovery-key creation, verification, rotation and forgotten-passphrase sections,
because that page described a recovery key operators do not hold. The corrected
page states the truth: the password is the only key, no command changes it, and
none recovers without it. The product therefore currently offers no recovery
route whatsoever, and this record decides whether that becomes permanent.

## Considerations

- The codec has zero consumers. Confirmed by name search over every exported
  symbol, by meaning-led semantic search, and by a negative sweep excluding the
  owning package and the storage facade: the only references are the two facade
  re-export surfaces, the module's own tests, and a wheel-packaging assertion.
- The "wheel pin" is not a third-party dependency. It is a package-data include
  in the build configuration shipping the bundled wordlist so it resolves at
  runtime in installed wheels. No external package is pulled in by the wordlist,
  so deleting it would remove roughly 13 KB of public-domain word data and no
  dependency at all. The row's premise overstated this cost.
- Nothing in the module is reachable from a live unwrap path. No production code
  path calls the wrapping half, and no code path anywhere writes the
  `master.recovery.key` file the wrapping half reads, so the wrapping guards no
  material this build can have produced.
- Per-profile recovery already exists at the substrate. The custody package owns
  a complete mechanism: an enrollment that wraps a profile's DEK under
  supervised Argon2id parameters against a generation-bound associated-data
  domain, an explicit recovery-only unlock door, and a portable
  export/import/prove artifact guarded behind current-password authentication.
  All of it is tested; none of it has an application or CLI consumer yet.
- That existing mechanism takes its recovery secret as an opaque string, and
  every artifact export carries a mandatory operator warning naming offline
  guessing exposure. That warning is the direct symptom of a human-chosen
  recovery secret: once the artifact leaves the machine, the only barrier is the
  KDF cost applied to whatever entropy the human supplied.
- The shared-master custody surface is on a declared retirement track. An
  application-layer absence gate names the provider family, the ambient
  activation seam, and the global recovery facade's begin and complete verbs as
  retired custody names, and reports every reach from the application layer into
  the master-key package regardless of symbol.
- Credential rotation is a separate missing capability, tracked by its own
  deliberately-failing assertion. This record does not decide rotation.

## Considered options

- **Delete both halves with the wordlist and the packaging include.** Cheap,
  closes the row, and satisfies a naive reading of unused-code hygiene.
  Rejected: it destroys the only component of a recovery mechanism that is
  expensive to rebuild, in service of a question the row explicitly asked to be
  decided second.
- **Preserve the whole module unchanged and rule nothing.** Rejected: it leaves
  source prose asserting an operator recovery workflow that does not exist, and
  leaves the next agent to re-litigate the same deletion.
- **Preserve the codec, rule the product question, and specify its target
  home.** Adopted.
- **Adopt a human-chosen recovery secret instead of a mnemonic.** Rejected on
  the exposure axis: it is precisely the configuration the existing artifact
  export already warns against.

## Constraints

- The codec cannot be rehomed inside the master-key package and then consumed by
  custody. The application-layer absence gate reports every reach into that
  package, so a custody consumer reaching there for its secret generator would
  register as a reach into a retiring surface. The target home must sit outside
  the retiring package.
- The generated API reference lists private modules explicitly, so introducing a
  new private module requires a regenerated stub landed in the same change. That
  surface is not owned by this record's author, which is one reason the physical
  relocation is specified here rather than performed here.
- Relocations in this codebase are atomic and land with their consuming change.
  A relocation with no consumer would be moved again when the consumer arrives.

## Implementation

**No code relocation is performed by this record.** The ruling and its target
specification are the deliverable; the move lands with the row that wires the
recovery artifact export and import, so the symbol is relocated once, into its
final home, alongside its first real caller.

The specified home is a substrate-level module directly beneath the persistence
storage package, sibling to both the retiring master-key package and the custody
package that will consume it. Its public surface is exactly four names: the
wipeable recovery-key container, the mint function, and the encode and decode
functions. The bundled wordlist travels with it, and the packaging include is
repointed in the same change. The master-key package's wrapping half stays where
it is and is not this record's to retire; it follows the shared-master surface
whenever that surface is retired.

When the wiring row builds the recovery enrollment, the recovery secret it
enrolls is the minted mnemonic, not an operator-typed string. The custody
enrollment signature already accepts an opaque string, so no cryptographic
parameter, key derivation, or associated-data domain changes: the codec supplies
a stronger value into an existing slot.

The one source change made under this record is corrective prose. The module
docstring described a live operator workflow — print the mnemonic at provision
time, recover with it after a lost passphrase — that the product does not
implement. That is the same class of false assurance the operator documentation
rewrite removed, standing in source instead. It now states what each half is,
that neither has a consumer, that no path writes the wrapping file, and why the
codec is retained deliberately rather than by oversight.

## Rationale

**The verdict: per-profile recovery should adopt the mnemonic, and the codec is
preserved. Deletion is refused.**

The decisive point is that the second-door question is already settled, and not
by this record. A per-profile recovery envelope, an explicit recovery-only
unlock door, and a guarded portable artifact all exist and are tested. The
architecture has already accepted that a profile's DEK may be wrapped a second
time under a secret that is not the login password. This record therefore does
not decide whether to open a second door; it decides what lock goes on a door
already built.

Framed that way, the exposure argument inverts. The instinct that recovery
widens exposure, and that the sibling record rejected an option on exactly that
ground, does not transfer: that rejection was of minting a second wrapped copy
where none was called for. Here the wrapped copy is already the accepted design,
and the mandatory offline-guessing warning on every export is an admission that
its current secret is the weak part. A 256-bit mnemonic makes offline guessing
against an exported artifact infeasible regardless of KDF cost, where a
human-chosen string does not. The mnemonic strictly reduces the exposure the
existing design already carries. Choosing the weaker secret would be the
exposure-widening option.

Against that, the honest cost: a mnemonic is a bearer secret. It converts
"forgot the password, lost everything" into "wrote 24 words down, and whoever
finds them holds the profile". For a taxpayer's financial records that is a real
and permanent transfer of risk, not a free win, and it is why the artifact's
store-separately and retained-copy warnings must survive verbatim. The
secure-storage mandate is not violated: the mandate governs where financial data
lives, and the data stays in the encrypted store throughout — what leaves is
wrapped key material, which is the shape the artifact export was already
designed and guarded for.

Deletion fails on its own terms independently of all this. The unused-legacy
mandate does not compel it: that mandate governs code reading what an older
version of this application wrote, and an unused forward capability is not
legacy. The cost of keeping is 13 KB of public-domain data and roughly a hundred
lines with no dependency; the cost of rebuilding a checksummed codec and
re-establishing a canonical wordlist is far higher. Deleting a working mechanism
to close a row is the failure this decision exists to avoid.

**What remains genuinely above this record's authority**, stated plainly rather
than absorbed: whether recovery ships at all is an operator decision, because
only the operator can weigh permanent loss of a taxpayer's records against a
transcribed bearer phrase in a drawer. The recommendation is that it ships, with
the mnemonic as its secret, enrollment optional and explicitly opt-in at profile
creation, and the existing export warnings preserved. The engineering ruling —
preserve the codec, do not delete, adopt it if recovery ships — holds under
either operator answer, because a decision to ship no recovery has not been made
and deleting in anticipation of it would foreclose the choice.

## Consequences

- The codec survives the shared-master retirement instead of being swept away
  with the wrapping half it happens to share a file with. That was the concrete
  risk the originating row identified, and the corrected docstring plus this
  record are what defuse it.
- The wiring row inherits a specified target home and a settled answer on which
  secret to enroll, rather than an open question at implementation time.
- Until that row lands, the product still has no recovery route. This record
  does not change what an operator can do today, and no documentation may claim
  otherwise.
- The operator documentation must not be rewritten to describe mnemonic recovery
  on the strength of this record. It may say only that recovery is planned and
  optional, and it may describe the mechanism as available only once the wiring
  row ships. Describing an unshipped recovery route is the exact failure the
  documentation rewrite corrected.
- Rotation stays open and untouched. A recovery route does not give an operator
  a way to change a password, and the failing assertion holding that gap visible
  remains correct.
- If the operator rules against recovery entirely, the deletion becomes a single
  clean change: the codec, the wordlist, the packaging include, the wipeable-
  material tests covering the codec, and the corrected docstring. This record
  should then be superseded rather than quietly ignored.
