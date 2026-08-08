---
tags:
  - '#plan'
  - '#m303-carry-reconciliation'
date: '2026-08-07'
modified: '2026-08-08'
body_hash: 'sha256:b97d5eca2b297ae2e1d5248151dbdf151af5e418e80f32427c7fb7ea31d4b4e7'
tier: L1
related:
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
---

# `m303-carry-reconciliation` plan

Close the two reach-and-duplication findings a code review raised against the
refunded-aware carry fix, without touching its arithmetic.

## Description

The review of the Modelo 303 refunded-aware carry fix returned REVISION
REQUIRED on two grounds, neither of them about the figures. The money
arithmetic, the legal grounding and the absent-posterior reading all checked
out under execution: the identity `available == posterior + generated` holds on
every branch, and the governing ADR says verbatim what the fix claims, with
RD 1624/1992 art. 30 and Ley 37/1992 art. 116 both present. This plan does not
reopen any of that.

The first finding is that the repaired drift gate watches a hand-listed tuple
of three modules. The gate's own stated reasoning for replacing an import
inventory was that an inventory asserts something the code is free to change,
and that reasoning applies verbatim to its own subject list. Nine twin
declarations of the compensation vocabulary survive outside the watched set,
three of them in the module that sits on the live local filing path. Rename the
end-of-period available casilla in a later revision and the watched modules get
rebound while that module keeps resolving its stale literal, so the refunded
rewrite silently stops finding the row it must re-stamp and a refunded period
carries its full generated credit into the next quarter with no gate red. That
is the exact drift the gate is named for, one module over. Step `S01` replaces
the subject list with discovery and rebinds the twins.

The second finding is that the same live local filing module encodes the
refunded rule by hand rather than through the derivation this fix made
canonical, so a regulatory change lands in one place and not the other. It also
rewrites only the value, leaving the formula id, operand refs and operand
values intact, so a refunded local observation asserts the provenance
`87 + generada` beside a posterior-only figure. The sede path does the
deliberate opposite and refuses when refs and formula disagree, so two paths
handle one case incompatibly and the local one ships a provenance claim its own
figure contradicts. Step `S02` routes it through the canonical derivation and
drops the contradicted provenance.

Step `S03` removes an algebraically vacuous assertion in the derivation's own
disposition test, where `generated` is defined as `available - posterior` on the
resultado basis and the identity therefore cannot fail. Step `S04` records four
deferred findings as follow-up rows without implementing them.

One correction the plan carries forward: the existing compensation tests are
NOT grounded parity. Their fixtures are synthetic hand-built observed-casilla
rows with authored figures; what is real is the shape, the canonical casilla ids
and the source locators naming the official boxes. They are legitimate wiring
and invariant coverage, but they would not fail if the AEAT formula were wrong.
No Step here may describe them as grounded, and no new test may manufacture
decimal expectations and call itself parity.

## Steps

- [x] `S01` - Discover token-naming modules by AST scan instead of a hand-listed tuple, and rebind the nine surviving twin declarations to the authority; `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py src/cadrumo/application/calculations/__init__.py src/cadrumo/application/calculations/_iva_compensation_annual_partition.py src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/_iva_wallet_gate.py`.
- [x] `S09` - Rebind the four further twin literals discovery found in the registry binding validator, which a hand-listed inventory of nine had also missed; `src/cadrumo/domain/iva_compensation/_filed_derivation.py src/cadrumo/domain/iva_compensation/__init__.py src/cadrumo/domain/calculations/registry/_bindings.py src/cadrumo/application/calculations/_iva_compensation_casillas.py`.
- [x] `S02` - Route the local filing path refunded rewrite through the canonical derivation and drop the contradicted formula provenance to match the sede path; `src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/tests`.
- [x] `S03` - Replace the algebraically vacuous available equals posterior plus generated assertion on the resultado basis with an independent check; `src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py`.
- [x] `S04` - Record the four deferred review findings as follow-up rows without implementing them; `.vault/plan/2026-08-07-m303-carry-reconciliation-plan.md`.
- [ ] `S05` - DEFERRED - report a refunded basis rather than resultado once disposition recovery from the justificante Tipo de declaracion makes the branch reachable; `src/cadrumo/domain/iva_compensation/_filed_derivation.py`.
- [ ] `S06` - DEFERRED - assert the disposition-blind available reconstruction in the annual partition instead of relying on a transitive upstream rewrite in another package; `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py`.
- [ ] `S07` - DEFERRED - refuse a persisted compensation pair where a directly filed disponible casilla overwrites available without generated following it; `src/cadrumo/application/calculations/_iva_compensation_history.py`.
- [ ] `S08` - DEFERRED - feed the recovered refund disposition into the IVA wallet gate, the fourth unimplemented implementation bullet of the governing decision record; `src/cadrumo/application/modelo/_iva_wallet_gate.py`.
- [x] `S10` - Add a standing real-site regression restoring an actual twin at every discovered module and confirming the verdict names it; `src/cadrumo/application/calculations/tests/test_iva_compensation_casillas.py`.
- [x] `S11` - Establish a sound channel for recovering the filed result disposition before S05 through S08 are attempted, and record the two mis-readings that would otherwise satisfy their precondition falsely. FIRST trap. The persisted source metadata key aeat_tipo_solicitud is NOT the disposition. Its own docstring states it distinguishes an original filing from an amendment, so it is the original-versus-complementaria axis. The Spanish nouns tipo de solicitud and tipo de declaracion are near-identical and that confusion is the likely failure. SECOND trap. The justificante parser extracts only the two printed amounts, total_a_ingresar and total_a_devolver, and carries no disposition code at all. A present devolver amount identifies DEVOLUCION, but COMPENSACION and NEGATIVA both present with neither amount, and suppressing compensacion carry-forward turns on exactly that distinction, so an amounts-based inference cannot decide the case the refund gate exists to decide. Gate. The row names the channel that actually carries the code, or records that none does and that parsing the printed Tipo de declaracion is required, and a test proves COMPENSACION and NEGATIVA stay distinguishable through whichever channel is chosen rather than collapsing to one reading; `src/cadrumo/adapters/inbound/justificante/_extract.py, src/cadrumo/domain/justificante/_schema.py, src/cadrumo/core/_result_disposition.py`.
- [ ] `S12` - Add casillas 72 and 73 to the modelo 303 revision, the compensacion and devolucion election amounts, each grounded with legal_refs citing the provision that establishes the election and backed by bundled corpus text. PRECONDITION, blocks S05 through S08. Loaded through the registry authority the revision carries 129 casillas including 70, 71, 74, 109 and 111 and neither 72 nor 73, so the declaracion extraction profile has nothing to target and the two label patterns cannot be added until these exist. Modelo localization keys for both casillas need real values in all four catalogues. Validate against a temporary registry root, never the shared bundled path, because installing a half-built revision reds the tree for every other agent; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/, src/cadrumo/locales`.
- [ ] `S13` - Add the two election label patterns to the modelo 303 declaracion extraction profile, targeting casillas 72 and 73 by named_label against the printed compensacion and devolucion sections, and blocked on S12. RECOVERY KEYS ON WHICH SLOT CARRIES A VALUE, NEVER ON A PRINTED LETTER. The C, I and D letters beside those sections are pre-printed form furniture present on all four bundled AEAT facsimiles including the two that elected ingreso, so a pattern matching the letter reports the same disposition for every filing while appearing to read the form. The discriminating signal is a populated amount casilla, measured as box 72 populated on exactly the two negative-resultado quarters and empty on the two positive ones. Cover all seven ResultDisposition members or state per member which are unreachable from this channel and why, since the two cuenta-corriente codes and domiciliacion have no printed amount slot of their own. Carry the NEGATIVA limit forward unchanged: sin actividad occupies a distinct numbered position so the shape is proven, but no bundled specimen filed one so the value stays unproven until a sin-actividad specimen exists; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`.

## Parallelization

`S01` and `S02` both edit the local filing observation module and carry a hard
ordering: `S01` rebinds its casilla constants to the authority and `S02` then
consumes the canonical derivation that names those same constants, so `S01`
lands first. `S03` touches only the domain disposition test and is independent
of both. `S04` is documentation-only and independent.

Each of `S01` and `S02` is one atomic commit. Within `S01` the gate and the
rebinding cannot be split: the gate reds until the twins are rebound, so both
halves must be present in the working tree simultaneously and land together.

## Verification

The plan is complete when every Step is closed and each of the following holds.

The drift gate names no module list and no module count: its subjects are
discovered from the source tree, and adding a tenth twin in a module no one
edited today reds it. The gate's per-module non-vacuity guard survives, so a
module naming nothing cannot pass silently. The documented CPython
short-literal interning limitation stays recorded honestly, because a twin of
the bare-numeric token is the same object and identity cannot discriminate
there.

No production module outside the declaring authority holds its own object for a
compensation casilla token. The nine surviving twins are rebound, and every
cross-package consumer imports through the owning package's public facade
rather than a private module.

The local filing refunded rewrite calls the canonical derivation rather than
re-deriving the rule, and a refunded row carries no formula id and no operand
refs, matching the sede path that refuses a refs-versus-formula disagreement. A
test asserts the local and sede paths agree on the provenance shape for the same
refunded case.

Every gate added here is proven to bite: where the defect is live the assertion
is written first and observed to red against unmodified code, and where a
mutation is required it is delivered as a pytest plugin loaded from outside the
repository with `-n0` passed explicitly, since the project's addopts inject
`-n auto` and a mutation applied in the controlling session never reaches xdist
workers.

The touched modules pass in isolation with owner triage recorded against the
pre-existing unrelated reds on this tree, which are not remediated here.
