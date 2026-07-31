---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:78cc0d5f55199fefb29918c66ff80610841fbd70eed09442391d4a05eda37978'
step_id: 'S05'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Build the read-only censal reader in the sede adapter over the shared authenticated session and access gate

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede`

## Description

- Add the read-only censal reader to the sede adapter, following the sibling
  readers' session, access-gate and error taxonomy.
- Parse the consulta page into typed frozen records for the identity group and
  both address groups.
- Fail closed at runtime on any landing that is a censal modification surface.
- Resolve the dispatched host off the landed page instead of pinning a numbered
  sede host.
- Export the landing predicate so conformance gates exercise the real refusal.
- Test the parser against real sanitised markup with no test doubles.

## Outcome

The reader exposes a parse function over page HTML, a live read over an
authenticated session, a URL builder, and two landing predicates. Its result is a
typed frozen record carrying the identity group, the fiscal address and the
notification address, each field optional because AEAT renders a blank cell for
data it does not hold and a blank is a legitimate censal answer rather than a
parse failure. Dates and the two electronic-notification flags are typed;
`sexo` and `estado civil` are deliberately left as AEAT's Spanish prose rather
than coerced to Modelo 100 codes, for the reason recorded below.

The no-write posture has two walls and the record is explicit about which is
load-bearing. The PRIMARY wall is a runtime landing guard evaluated after the
redirect chain, against the host AEAT actually served rather than the URL
requested, because AEAT chooses where a session lands. It refuses any landing
carrying one of four declared markers: the Modelo 036 filing application prefix,
the `.zul` document extension, the domicilio-modification prefix, and the
procedure-launcher path prefix. Every marker is a prefix or family fragment
rather than a procedure code, so the domicilio marker catches both write siblings
and the launcher marker catches every procedure code in the family instead of the
one door that was found. The SECONDARY wall is the pre-existing static
source-scan gate over the sede package; it is retained, and labelled in the module
as the weaker of the two so a later reader does not delete the runtime half as
redundant. A static token check alone was proven insufficient: the token an
earlier draft of the proof forbade appears in none of the four real write paths,
and a test asserts that fact so the reasoning cannot be lost.

No numbered sede host is pinned. The numbered hosts are load-balanced per session,
some do not serve this route and others reject a session minted elsewhere, so the
reader enters through the host-agnostic access selector rooted at the unnumbered
origin, lets AEAT dispatch, and reads the resulting origin off the landed page
before re-asserting it through the read guard. A test asserts that no numbered
host is referenced in the module at all, and a parametrised test asserts the guard
admits every numbered host so none is privileged.

The proof is non-vacuous by construction. Alongside the refusal cases, tests
assert that the guard ADMITS the reader's own landing, that the captured page
genuinely carries the modification controls the guard exists to refuse, that the
declared marker set is non-empty and contains no empty string that would match
every landing, and that each declared marker refuses on its own so none is dead
weight. A further test asserts the exported predicate agrees with the raising
guard, so a conformance gate testing through the predicate cannot pass while the
reader refuses differently.

Closing measurement at `3f16615f6b`: 32 reader tests pass; 93 pass across the
reader, the sede write-surface gate, the fixture credential gate and the external
constants gate. Type checking and linting are clean, the generated API stubs are
conformant, and the sede package collects, which is what proves the package facade
and the module agree.

## Notes

THE READER HAS NO COMMIT OF ITS OWN. All eleven paths landed inside
`3f16615f6b`, whose message belongs to an unrelated campaign's vault work. A peer
agent's commit carrying no pathspec took the executor's files out of the shared
index in the interval between staging them and committing them. Nothing was lost
and all eleven landed together, so the tree stayed coherent; it was left as-is
rather than unbundled because every tool that could separate it is barred in this
worktree. This is recorded because it is not recoverable from history by any
other means: searching commits by author does not help either, since every agent
commits under one identity, so such a search returns a confidently wrong answer
rather than an empty one.

The staging incident produced a correction to the worktree's standing commit
guidance. The executor did run a verification that aborted rather than printed,
and it worked — it refused the commit because peer files were already staged in
the shared index. But a check of that shape protects the COMMIT, while the
exposure is the STAGED FILES, and verifying takes its own command. A correct
verification therefore widens the window it is guarding. The shapes that close it
are a pathspec commit that never stages, or a stage-and-commit with no separable
gap.

THE SELECTOR DISPATCH WAS UNTESTED AGAINST A LIVE SESSION AT THE TIME OF
WRITING, AND IS NOW CONFIRMED. The original caveat is kept below rather than
replaced, because what was believed and what settled it are both worth having.

As recorded at close: the parse layer was proven against real markup while the
dispatch layer was proven only by construction, because the executor was
instructed not to open a live session. A future live exercise was warned not to
read a successful pull as proof that dispatch worked, since the resolver falls
back to the unnumbered origin when the selector does not dispatch and that origin
may serve the route, making a green run consistent with the fallback having
fired. The discriminating evidence was specified as the log record naming the
dispatched host: its absence, or a landing on the unnumbered origin, would mean
the fallback ran and dispatch remained unproven. That caveat was recorded here
rather than in the module because process metadata does not belong in source and
such a comment would rot on first exercise.

Superseded on the day after close by a live run performed by a peer agent holding
an authenticated session. The resolver reported a numbered host, which the
fallback cannot produce, and the read completed against the censal consulta path.
Dispatch is confirmed in production and the construction-only qualification no
longer applies.

The same run exposed a defect in the instrument that the discriminator existed to
read, which is the part worth carrying forward. The dispatch wait and the check
that reported its outcome held two opinions about one condition, so a wait
expiring on a page that HAD landed correctly logged a dispatch failure — a
successful dispatch reporting itself as a failed one. A human reading that log
would have concluded the selector does not work. It was closed by making one
predicate the single reader of that condition, reducing the expiry record to a
statement about the wait alone, and logging the previously-silent fallback return
so that its absence is no longer ambiguous between the fallback firing and the
reader never running. Writing the discriminator down BEFORE it was needed is what
made the misreport visible rather than persuasive.

One correction to the original caveat's reasoning, from a peer's measurement on
the declarations surface: the assumption that the fallback origin "may serve the
route" is not universally safe. That unnumbered origin returns a genuine 404 for
at least one other sede route. So falling back is not a soft degradation
everywhere — on some routes it is a guaranteed failure. Whether it serves the
censal route specifically has not been measured, and should not be assumed in
either direction.

Three profile-field mappings were refused rather than guessed, and each remains
open work for whoever writes censal facts. The taxpayer sex field cannot be
written at all: the profile schema declares one closed value set while the runtime
enforces a different one and would raise on the schema's own values, and AEAT
supplies neither form, so any write satisfies one authority and violates the
other. AEAT's "not recorded" marital status has no corresponding code, and
defaulting it would silently change a taxpayer's mínimo. The combined
surnames-and-name field must not be split automatically, because the Spanish
two-surname convention does not hold for the foreign names this product serves —
the real capture was a three-token name on which a positional split is simply
wrong.

Several parsed fields have no home in the profile schema and are therefore read
but unwritable: nationality, birthplace, passport, the administering AEAT office,
both electronic-notification flags, and the whole notification address. Municipio
and provincia likewise have no direct field; deriving an autonomous community
from a province is an inference rather than a read and does not belong on a pull
path.
