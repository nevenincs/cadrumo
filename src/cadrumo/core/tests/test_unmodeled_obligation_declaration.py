"""Internal consistency of the recognized-but-unmodeled obligation declaration.

:data:`~cadrumo.core.UNMODELED_OBLIGATIONS` is the extensible edge of AEAT-wide
obligation enrollment: a member is an obligation AEAT expects that the registry
cannot yet scope, so the coverage reconciliation surfaces it as *advised*
(investigate) rather than leaving it invisible. Three ways a hand-edited entry
turns that promise into a silent omission, each gated here:

* an entry with a blank description, which surfaces an advisory the operator
  cannot act on;
* an entry that is ALSO declared out of scope, which the coverage builder
  resolves as out-of-scope because it tests that bucket first — the advisory the
  entry was added to raise never appears;
* an entry missing from :data:`~cadrumo.core.NON_REGISTRY_MODELOS`, which would
  let the registry-parity gate demand a registry definition that may not exist.

The declaration is EMPTY today, so asserting these properties over it is
vacuously true. That is what makes the second test load-bearing rather than
decorative: it runs the same checker over a deliberately inconsistent synthetic
declaration and proves the checker names every offender. The gate therefore
bites now, and keeps biting on the real declaration the moment an entry lands.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ..modelo import NON_REGISTRY_MODELOS, OUT_OF_SCOPE_OBLIGATIONS, UNMODELED_OBLIGATIONS, Modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _declaration_offenders(
    unmodeled: Mapping[Modelo, str],
    *,
    out_of_scope: Mapping[Modelo, str],
    non_registry: frozenset[Modelo],
) -> list[str]:
    """Return one diagnostic per way ``unmodeled`` contradicts its own contract."""
    offenders: list[str] = []
    for modelo, description in unmodeled.items():
        if not description.strip():
            offenders.append(f"{modelo}: no recorded description")
        if modelo in out_of_scope:
            offenders.append(f"{modelo}: declared unmodeled AND out of scope")
        if modelo not in non_registry:
            offenders.append(f"{modelo}: declared unmodeled but absent from NON_REGISTRY_MODELOS")
    return offenders


def test_the_unmodeled_declaration_is_internally_consistent() -> None:
    """Every declared unmodeled obligation can actually reach the operator as advised."""
    offenders = _declaration_offenders(
        UNMODELED_OBLIGATIONS,
        out_of_scope=OUT_OF_SCOPE_OBLIGATIONS,
        non_registry=NON_REGISTRY_MODELOS,
    )
    assert offenders == [], f"UNMODELED_OBLIGATIONS contradicts its own contract: {offenders}"


def test_the_consistency_check_names_every_offending_shape() -> None:
    """The checker bites, so the invariant above is not passing merely on emptiness.

    Each synthetic entry breaks exactly one clause, and the assertion demands the
    matching diagnostic — so a checker silently reduced to a no-op (or narrowed to
    one clause) fails here while the real declaration is still empty.
    """
    # Each probe is chosen to break ONE clause, so a diagnostic can only be
    # missing because the checker stopped emitting it.
    blank = Modelo.M037
    overlapping = next(modelo for modelo in OUT_OF_SCOPE_OBLIGATIONS if modelo in NON_REGISTRY_MODELOS)
    unlisted = next(
        modelo for modelo in Modelo if modelo not in NON_REGISTRY_MODELOS and modelo not in OUT_OF_SCOPE_OBLIGATIONS
    )
    assert len({blank, overlapping, unlisted}) == 3

    offenders = _declaration_offenders(
        {blank: "   ", overlapping: "recognized, but also declared out of scope", unlisted: "registry-backed"},
        out_of_scope=OUT_OF_SCOPE_OBLIGATIONS,
        non_registry=NON_REGISTRY_MODELOS,
    )

    assert f"{blank}: no recorded description" in offenders
    assert f"{overlapping}: declared unmodeled AND out of scope" in offenders
    assert f"{unlisted}: declared unmodeled but absent from NON_REGISTRY_MODELOS" in offenders
