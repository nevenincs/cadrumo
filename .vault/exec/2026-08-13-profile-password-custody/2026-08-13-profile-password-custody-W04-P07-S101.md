---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:19ecde3b70b29de266cd0c88ff8fc7898103620efef165bb7f290ad4dd6ece0c'
step_id: 'S101'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium close the custody path builder's runtime validation gap, which accepts a profile identifier only by type annotation and would silently create a custody directory named for a system sentinel if one reached it, the honest bound being that the boundary is type-blocked rather than runtime-blocked with no live path found and none exhaustively searched for

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_paths.py`

## Description

- Establish what the path builder actually accepts, against a throwaway root.
- Bind the identifier at runtime rather than by annotation, reusing the substrate's
  existing path-safety primitive instead of restating its rules.
- Express the discovery side's recognition test as the inverse of the builder, so the
  writer and the reader cannot spell canonicality differently.
- Prove the bound bites in both directions.

## Outcome

**What the builder accepted.**

Every value, of every type. The parameter carried a `UUID` annotation and the body
coerced it with `str(...)`, so the annotation bound callers and nothing else. A probe run
from outside the repository against a temporary storage root established the following,
each one observed rather than reasoned about:

- The two system-scoped bucket sentinels that actually exist in this tree — `"system"`
  and `"__unbound_session__"` — each composed a sibling capsule directory under the
  buckets root, and the directory was creatable there beside real capsules. The
  bucket-identity alias is documented as "profile UUID or a system-scoped sentinel", so a
  sentinel is not a hypothetical value; it is the other half of the type that identifies
  a bucket everywhere else in the system.
- The relative-path tokens escaped the buckets root. The parent token resolved onto the
  storage root itself, and a two-level token resolved entirely outside the storage root.
  This is worse than the row described and is stated plainly: the gap was not only a
  wrongly-named sibling directory, it was an unbounded path-composition boundary.
- The empty string collapsed the capsule directory away completely, leaving the commit
  marker addressed directly inside the buckets root.
- Non-canonical UUID spellings — uppercase, brace-wrapped, hyphen-stripped — each
  composed a directory the anchored discoverer can never recognise. A capsule published
  under one of those names would sit on disk, complete and unreadable, while the profile
  listing reported it absent.

The two resolution branches were not equally weak, which is worth recording. The settings
branch delegates to the shared bucket-scoped resolver, which at least refuses a blank
identifier; the explicit-root branch composed the name itself and refused nothing at all.
The branch used by every transaction-scoped custody operation was the unguarded one.

**How it is closed.**

At the boundary, on the value. `profile_custody_directory_name` is now the single place a
profile identity becomes a filesystem name, and it declares its parameter as `object`
because it does not trust its input — the same posture the wipe primitive in this package
already takes, and for the same reason: the damage of an unchecked value is silent. A
non-UUID value raises the substrate's registered path-containment failure, which is
already localised and already carried by the operator error envelope. No new error class
and no new locale key were introduced.

Shape rejection is delegated to the substrate's repository-id validator rather than
restated locally. That was a deliberate reuse call: a second separator-and-dot-token rule
living in the custody package could drift from the one every other
identifier-to-filename boundary uses, and a divergent path-safety rule is precisely the
defect class another row in this campaign exists for.

The composed builder keeps its `UUID` annotation, so callers keep the static help they
had. The runtime bound sits underneath it, where the value is actually consumed.

**The writer and the reader are now one rule.**

The discovery side already had its own canonicality test, spelled independently: parse
the directory name as a UUID and require it to re-render identically. That is the same
rule as the builder's, expressed twice. It is now expressed once — recognition is defined
as agreement with the builder's name function — because two spellings can disagree, and
the disagreement is silent in the worst direction. A capsule the writer publishes under a
name the reader rejects is invisible while its material sits on disk. This is not a
cosmetic tidy: it converts a defence-in-depth check into a functional invariant a
regression would have to break in both directions at once.

**Proof that it bites, both ways.**

Run from outside the repository, so no tracked file was mutated and a crashed run could
leave nothing behind for a peer sweep to capture.

Refusal direction: both system sentinels, five relative-path tokens, four non-canonical
UUID spellings, four wrong-typed values, and the canonical UUID *string* all refuse, and
the temporary root is empty afterwards — no residue from any refused identifier.

Acceptance direction: nine identifier shapes the system can actually mint — version 1, 3,
4 and 5 UUIDs, the all-zero and all-ones boundary values, and three constructed from
non-canonical input — all still build, all under exactly their canonical name, and the
anchored discoverer accepts every one. This half is the load-bearing half: a validator
that refused a real profile identifier would break custody outright, so it is asserted
rather than assumed.

Both directions are also carried permanently in the package's own test path rather than
left in scratch.

**The honest bound, which the row insisted on and which survives.**

No live path was found, and the search was not exhaustive. Stating both halves precisely:

What was searched. Every call site of the builder in the tree, by name: all of them live
in the custody capsule module and every one declares a UUID-typed profile identifier. The
symbol's reachability, which is wider than its call sites — it is exported from both the
custody package facade and the storage package facade, so any consumer inside or outside
this tree can reach it. The concrete sentinel values that exist, found by searching for
the bucket-identity alias's own documentation of them rather than by imagining what a
sentinel might look like. And the type checkers over the custody package, which are
clean, so no first-party caller passes a non-UUID value that static analysis can see.

What was not searched. Dynamic reach — reflection, attribute-name resolution, plugin or
protocol entry points that could reach the symbol by name — was not audited. Nor was the
upstream chain traced: the application layer has its own UUID-annotated parameters, and
whether any of them is fed a coerced string from operator input, from a model carrying
the bucket-identity alias, or from a persisted record was not established for every path.
So the correct characterisation is unchanged from the row's: a defence-in-depth gap at a
path-construction boundary that writes to the filesystem, now closed, with no live
exploit demonstrated and none proven absent.

**Verification.**

The custody package suite plus the three consumer modules that exercise this boundary —
the capsule lifecycle, the custody transactions, and the active-profile resolution — pass
sequentially in full: 186 passed, 0 failed. The new boundary module is 50 passing cases
on its own.

The wider storage, user-profile and workflow suites report 61 failures and 22 errors.
None is attributable here, and that is measured rather than asserted: the whole set was
re-run with this row's runtime check reverted in memory from outside the repository, and
the failure set is identical. No failure in either log names a symbol this row touched.

One further ambient artefact is recorded because it wastes time otherwise: the keyring
boundary case in the acceleration-receipt module fails under parallel execution and
passes sequentially. It contends over the real host credential store, so it is a
parallelism artefact, not a regression.

Linter, formatter and both type checkers are clean on every module changed here. The one
remaining type diagnostic in the package predates this row and concerns an unrelated
import-graph helper.

## Notes

The first shape of the check kept the UUID annotation on the validating helper, and the
type checker correctly called the runtime type test unnecessary — statically it is.
Silencing that with a suppression would have been the wrong answer: the honest expression
is that the parameter is untrusted, which this package already had a precedent for, so
the parameter became `object` and the diagnostic went away for the right reason rather
than being muted.

Delegating shape rejection to the shared repository-id validator is, on a UUID input,
unreachable in practice — a UUID always renders canonically. It is kept anyway, as
composition rather than as a claim that it fires: it is what keeps this boundary
answerable to the same rule as every other identifier-to-filename boundary if either side
of that rule ever changes.

The traversal escape found in the probe is the part of this finding that exceeded the
row's own description. It is recorded rather than quietly folded into the fix, because
"would create a directory named for a sentinel" and "would compose a path outside the
storage root" are different severities, and the row's honest bound was written against
the first.
