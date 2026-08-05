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
