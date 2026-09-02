"""An undeclared fiscal residency must not be stamped as Spanish source.

contract: ``resolve_source_jurisdiction`` defaults ``--source-jurisdiction`` to
``ES`` only on a DECLARED residency. An undeclared residency resolves to
``None``.

The impatriado income aggregation documents the invariant this protects: a
``source_jurisdiction is None`` row "is NEVER silently coerced to ``ES``" — it is
segregated out of the base with a typed unresolved-jurisdiction issue, citing
``no-silent-under-declaration``. That behaviour is already gated in
``application/aggregation/tests/test_impatriado_income_ledger.py``, so it is
deliberately not re-tested here; what was missing is that the ``None`` ever
reached it. The CLI coerced to ``ES`` at the boundary first, and the stamp is
persisted on the transaction, so it outlived the profile later being completed.

These call the real resolver with real enum members; nothing is stubbed.
"""

from __future__ import annotations

import pytest
import typer

from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IrpfSpecialRegime
from .._ledger_support import resolve_source_jurisdiction

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_undeclared_residency_resolves_to_none_not_es() -> None:
    """The fix: absence stays absence, so the aggregation's guard can see it."""
    resolved = resolve_source_jurisdiction(None, fiscal_residency=None, irpf_special_regime=None)

    assert resolved is None, "an undeclared residency must not be stamped as Spanish source"


def test_a_declared_resident_still_defaults_to_es() -> None:
    """POSITIVE CONTROL: the default is retained where it is actually grounded.

    Without this, "stop stamping ES" could be satisfied by removing the default
    outright, which would drop the jurisdiction for every ordinary resident.
    """
    resolved = resolve_source_jurisdiction(
        None,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
        irpf_special_regime=None,
    )

    assert resolved == "ES"


def test_an_operator_supplied_value_wins_over_every_profile_signal() -> None:
    """An explicit flag is authoritative, including for an undeclared residency."""
    assert resolve_source_jurisdiction("PT", fiscal_residency=None, irpf_special_regime=None) == "PT"
    assert (
        resolve_source_jurisdiction(
            "DE",
            fiscal_residency=FiscalResidency.RESIDENT_IRPF,
            irpf_special_regime=None,
        )
        == "DE"
    )


def test_a_declared_non_resident_still_refuses() -> None:
    """The existing IRNR refusal is unchanged — a declared non-resident must state it."""
    with pytest.raises(typer.BadParameter):
        resolve_source_jurisdiction(
            None,
            fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
            irpf_special_regime=None,
        )


def test_a_declared_impatriado_still_refuses() -> None:
    """The existing Beckham refusal is unchanged."""
    with pytest.raises(typer.BadParameter):
        resolve_source_jurisdiction(
            None,
            fiscal_residency=None,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
        )


def test_the_impatriado_refusal_outranks_the_undeclared_residency_path() -> None:
    """A declared impatriado with undeclared residency must refuse, not resolve to None.

    Both conditions hold at once here, and the ordering matters: silently
    returning ``None`` for a profile that HAS declared the Beckham regime would
    replace an instructive refusal with a segregated row the operator never sees
    asked about.
    """
    with pytest.raises(typer.BadParameter):
        resolve_source_jurisdiction(
            None,
            fiscal_residency=None,
            irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
        )
