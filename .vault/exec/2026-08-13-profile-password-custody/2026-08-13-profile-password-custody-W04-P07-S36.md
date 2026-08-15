---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:73d75e9d3b3125332918d83baaa22ee18722785244c23aec5b4f614c402b1308'
step_id: 'S36'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-15-profile-password-custody-per-profile-recovery-mnemonic-adr]]"
---

# Have Sol Medium first rule whether per-profile recovery will adopt the mnemonic at all, since the codec and its canonical wordlist currently have no consumer anywhere, then either split them out as their own home or delete both halves with the wordlist and its wheel pin, rather than preserving a survivor with nobody to serve

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`

## Description

- Read the recovery module and the bundled wordlist whole; confirm the
  no-consumer claim by exported-symbol search, meaning-led semantic search, and
  a negative sweep excluding the owning package and the storage facade.
- Establish what the packaging entry the Step calls a wheel pin actually is.
- Establish the relationship between the mnemonic codec and the per-profile
  recovery artifact and envelope the custody package already owns.
- Confirm no live unwrap path reaches the module before considering any removal.
- Author the decision record ruling the product question.
- Correct the module docstring, which described an operator recovery workflow
  the product does not implement.

## Outcome

**The verdict: per-profile recovery should adopt the mnemonic, the codec is
preserved, and deletion is refused.** The full reasoning is in the sibling
decision record; the essentials follow, together with the two places the Step's
own premises turned out to be wrong.

**The no-consumer claim is confirmed, and it is stronger than stated.** Every
exported symbol of the module — the container, the mint, the encode and decode
functions, the wrapping model, both wrap and unwrap, the load, save and
verified-install helpers — and the sibling on-disk envelope record have no
caller anywhere outside the owning package, its own tests, and the two facade
re-export surfaces. A meaning-led search returned only the module itself. One
exported helper is not even reachable through the package facade. Nothing is
reachable from a live unwrap path, and no path anywhere writes the wrapping
file the unwrap reads, so the wrapping half guards no material this build can
have produced.

**Two Step premises are corrected.** First, there is no wheel pin. The
packaging entry is a package-data include shipping the bundled wordlist so it
resolves at runtime in installed wheels; no third-party dependency is involved.
Deleting the wordlist would remove about 13 KB of public-domain word data and no
dependency, so the stated cost of keeping it was overstated. Second, the module
is not one thing. The mnemonic codec is a pure codec over high-entropy bytes,
bound to no custody architecture, file layout or key schedule. The master-key
wrapping is bound to the shared-master surface an application-layer absence gate
already names as retiring. They share a file and nothing else, and conflating
them is what made deletion look like a single tidy action.

**The decisive finding is that the question the Step poses is narrower than it
appears.** Per-profile recovery already exists at the substrate: an enrollment
wrapping a profile's DEK under supervised Argon2id parameters against a
generation-bound associated-data domain, an explicit recovery-only unlock door,
and a guarded portable export, import and prove artifact. All tested; none wired
to any application or CLI consumer. So the architecture has already accepted a
second wrapped copy of the DEK under a non-password secret. The open question is
not whether to open a second door but what lock goes on a door already built.

That inverts the exposure argument. The enrollment takes its recovery secret as
an opaque string, and every artifact export carries a mandatory operator warning
naming offline guessing exposure — which is exactly the symptom of a
human-chosen secret, since once the artifact leaves the machine the only barrier
is KDF cost over whatever entropy the human supplied. A 256-bit mnemonic makes
that attack infeasible regardless of KDF cost. The mnemonic reduces the exposure
the accepted design already carries; choosing the weaker secret would be the
exposure-widening option. The sibling record's rejection of minting a second
wrapped copy does not transfer, because there the wrapped copy was not called
for and here it is already the design.

The honest cost is stated rather than buried: a mnemonic is a bearer secret,
converting permanent loss into a transcribed phrase whoever finds it can use.
The store-separately and retained-copy warnings must survive verbatim. The
secure-storage mandate is not violated — financial data stays in the encrypted
store, and what leaves is wrapped key material in the shape the export was
already designed and guarded for.

**What is above this row's authority, stated rather than absorbed:** whether
recovery ships at all is an operator decision, because only the operator can
weigh permanent loss of a taxpayer's records against a bearer phrase in a
drawer. The recommendation is that it ships, optional and opt-in at profile
creation, with the mnemonic as its secret and the export warnings preserved. The
engineering ruling holds under either operator answer, because no decision to
ship no recovery has been made and deleting in anticipation would foreclose it.

**No relocation was performed, and that is a deliberate departure from the
Step's "split them out as their own home" branch.** The codec cannot be rehomed
inside the master-key package and then consumed by custody: the absence gate
reports every reach from the application layer into that package, so the
consumer would register as a reach into a retiring surface. The correct home is
a substrate-level module beneath the persistence storage package, sibling to
both. Two things make performing that move here wrong rather than merely
optional. The generated API reference lists private modules explicitly, so a new
private module needs a regenerated stub in the same change, and that surface is
held by another agent. And relocations in this codebase are atomic and land with
their consuming change — a move with no consumer would simply be moved again
when the wiring row arrives. The decision record therefore specifies the target
home and its exact four-name public surface, and the move lands once, with its
first real caller.

**One source change was made: corrective prose.** The module docstring described
a live operator workflow — print the mnemonic at provision time, recover with it
after a lost passphrase — that the product does not implement. That is the same
class of false assurance the campaign's operator-documentation rewrite removed,
standing in source instead of on a page. It now states what each half is, that
neither has a consumer, that no path writes the wrapping file, and why the codec
is retained deliberately rather than by oversight.

## Notes

**A peer commit captured this row's working-tree change.** The docstring edit was
swept into a broad registry-sweep commit by another worker before this record
was written. No git write of any kind was issued from this row — no add, commit,
stash, reset or checkout. The change is intact and correct in the tree; it is
simply attributed to a commit this row did not author. Recording it because
silent capture in a shared worktree is precisely the hazard that is invisible
afterwards.

**Nothing cryptographic was touched.** No key derivation, no KDF parameter, no
associated-data domain, no key schedule, no wordlist content. No file was
deleted. The refusal to delete was reached before the confirmation that no live
unwrap path exists, and that confirmation would not have licensed deletion on its
own.

**The deliberately-failing rotation assertion was not touched.** Rotation and
recovery are adjacent and distinct; this row decides recovery only, and a
recovery route gives an operator no way to change a password.

**Documentation constraint carried forward.** The operator page must not be
rewritten to describe mnemonic recovery on the strength of this ruling. Until
the wiring row ships, the product still has no recovery route, and the page may
say only that recovery is planned and optional.

## Verification

- Master-key and custody suites run together with the marker selection widened
  to unit or integration, full output captured to a file and read back from
  disk: `1 failed, 302 passed`.
- The single failure is ambient and not this row's. It is a wall-clock budget
  assertion on keyring backend probe latency, measured at 0.62 to 0.81 seconds
  against a 0.5 second bound. It fails identically with the parallel runner
  disabled, so it is not a concurrency artefact; it is a real-time assertion
  against a slow network-backed worktree share. Its module imports only the
  errors module and the master-key provider module, never the recovery module,
  so a docstring change cannot reach it. Attribution was established by reading
  the module's imports rather than assumed from the failure's subject.
- The wipeable-material tests covering the codec — mint, wipe, idempotent wipe,
  context-manager wipe, decode-returns-a-wipeable-buffer, and the anti-tautology
  proof that the wipe primitive genuinely refuses immutable shapes — all pass,
  which is what makes the preserved codec a working mechanism rather than an
  assumed one.
- The no-consumer claim was verified three independent ways rather than by a
  single sweep, because a name-stem search alone cannot see a consumer under a
  different name.
- No claim is made here about tree-wide gates, the docs build, or any suite
  beyond the two named; none were run.
