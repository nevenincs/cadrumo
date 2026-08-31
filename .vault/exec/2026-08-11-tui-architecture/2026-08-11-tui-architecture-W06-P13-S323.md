---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:20a784670f39b059cd207e689270091a4d79db7eb625e5a3c74b1a9040a38193'
step_id: 'S323'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-mint the Workspace C2 dependency receipt against live source, and replace its hand-listed clean-commit scope with one DERIVED from the fingerprint's own inputs. CAUSE, proven empirically: recomputing the workspace schema fingerprint from live source reproduces the failing validator's value byte for byte, and the new ledger preflight issue-reason member is present in the fingerprinted schema, so the additive enum member IS the cause. An earlier attribution to the workspace-models tightening commit was WRONG and is recorded so nobody re-derives it: that diff is docstrings on enum MEMBERS, which Python stores nowhere and which cannot move a digest. The change is ADJUDICATED SOUND -- additive, nothing lost or loosened, and it surfaces a home-office row that would otherwise deduct nothing silently. THE STRUCTURAL DEFECT, measured: walking the projection's real model graph yields 69 model and enum types across 20 defining source files, of which exactly ONE is in the current clean-commit set. Nineteen fingerprint inputs sit outside the gate, which is why the drift was silent -- it entered through ledger preflight, nineteen files deep in the blind spot. DERIVE THE SCOPE, DO NOT HAND-LIST IT: a hand-maintained path inventory is the same construct as the conformance matrix that silently stopped covering seven definitions, and it will fall behind the fingerprint the same way -- at which point the receipt would attest cleanliness over a set that no longer matches what it fingerprints, which is worse than the gap it replaces. Walk the model graph at mint time and take the defining files from it. If derivation proves infeasible, say so explicitly and add a gate asserting the hand-listed set still equals the walked set, so drift fails loudly rather than silently. Then re-mint, prove reproduction of every field except the moving commit stamp, and scope the ancestry claim to those paths verified clean at mint time

## Scope

- `the workspace dependency receipt document`
- `its validator's clean-commit path derivation`
- `the transitive model-graph inputs to the workspace schema fingerprint`
- `and the reproduction proof`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`
- `M` `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt-reference.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py -m unit -n0` -> `pass`
- `verify:` `git status --porcelain -- <the 27 derived and named scope paths>` -> `pass`

## Notes

Derivation proved feasible, so the row's hand-list fallback and its equality
gate were not needed. The scope is walked at mint time from the two
fingerprinted roots to every model and enum they transitively reach, through
generic arguments and unions, taking each defining file. Measured at 71 types
across 21 files; the row's 69 and 20 predate intervening commits.

Of the eight paths the gate previously named, exactly one was an input to the
fingerprint it guards. Six paths remain named because they cannot be reached
by walking a model graph: the two entry-point modules the receipt cites as
read destinations, and the four vault records whose status headings and body
hashes it quotes. Total scope is 27.

The blind spot was closed against the specific file that drifted through it.
Appending a line to the ledger preflight module, which is reached
transitively and was absent from the old set, makes the clean-commit
assertion refuse. The old set therefore could not have caught the drift that
occasioned this Step.

The stored fingerprint had drifted from live source and the receipt was
re-minted over the corrected value. The fingerprint was recomputed at
stamping rather than carried: the head advanced between the derivation commit
and the mint, so a carried value would already have been stale.

The reproduction test was asserting against the superseded hand-named copy of
the receipt rather than the authoritative one. It and the module docstring
were repointed, which leaves the superseded copy with no consumer in source.

The superseded copy was NOT deleted. An unchecked Step in the interface plan
names it as the artefact it must verify, and closed records in this plan cite
it as what they created. Retiring it requires repointing that open row first,
which belongs to that plan's owner.

Discovery ran on grep and direct file reads rather than the semantic search
service, which was unavailable.
