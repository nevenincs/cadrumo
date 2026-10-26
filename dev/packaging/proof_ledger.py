"""Run-scoped record of which packaging proofs actually executed.

Each form runs as its own process, so this is per-process state by
construction: a claim reaches a smoke manifest only if the assertion backing it
recorded itself here while running.

The ledger is one half of a two-sided mechanism, and neither half is sufficient
alone. Deriving the manifest from the ledger makes an over-claim impossible — a
form cannot write a claim nothing recorded. Checking the ledger against a
DECLARED contract catches the inverse: a form that quietly stops running
something it promised would otherwise just write a shorter, still-truthful
manifest and stay green.

This lives in its own module rather than in the shared smoke core because
``python_cohort`` records the install-level cohort invariant it proves, and the
shared smoke core already imports ``python_cohort`` — putting the ledger there
would close an import cycle.

**Why the number of ``record_proof`` call sites is worth watching.** It is not
redundant hygiene beside the contract gate; it is the only instrument pointed at
that gate's blind spot. Drop a ``record_proof`` while its claim is still
declared and the gate is loud: ``write_smoke_manifest`` computes the unperformed
set and raises before writing anything. The silent case is a declaration and its
recording removed *together* — the site count falls while every test stays green
and every manifest stays truthful, because a smaller honest contract is still an
honest contract. That is a scope reduction wearing the shape of a cleanup, and
only a reader comparing counts across revisions will see it.

**The mechanism degrades to one-sided wherever the two literals share a source.**
A form that both records and declares from the same expression compares a set
against itself, so the runtime check cannot fail and the static gate — which
reads string constants — sees nothing.

It has NO live instance today. The one it had was ``smoke_docker``, whose
per-variant claims were recorded and declared from a single ``variant_claims``
tuple because the assertions ran inside a container and could not reach this
ledger across the process boundary; what was unbacked there was the GRANULARITY
of the claims rather than whether the work ran. That lane has since been
retired, and no surviving form records and declares from one expression. The
degradation is documented here because the shape returns whenever a proof runs
across a process boundary: the fix is to have the out-of-process probe report
which claims it performed and record that, so the record derives from behaviour
again rather than from the declaration beside it.
"""

from __future__ import annotations

__all__ = ["ProofContractError", "record_proof", "recorded_proofs", "reset_proof_ledger"]


class ProofContractError(RuntimeError):
    """A form declared a proof it did not perform."""


_PROOF_LEDGER: list[str] = []


def record_proof(claim: str) -> None:
    """Record that the assertion backing ``claim`` executed in this run.

    Called by the assertion itself, on success, so the record cannot drift from
    the behaviour: there is no second place to keep in step.
    """
    if claim not in _PROOF_LEDGER:
        _PROOF_LEDGER.append(claim)


def recorded_proofs() -> tuple[str, ...]:
    """Return the claims whose assertions executed, in execution order."""
    return tuple(_PROOF_LEDGER)


def reset_proof_ledger() -> None:
    """Clear the ledger. For tests, which exercise several forms in one process."""
    _PROOF_LEDGER.clear()
