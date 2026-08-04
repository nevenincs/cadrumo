"""The Art. 61 norma 1ª prorrata advisory, which the ADR's chosen default rests on.

This advisory is not a nice-to-have diagnostic. The ADR chose to APPLY the
prorrata where profile signals indicate a second entitled filer, rather than
claim the full amount, and justified that choice on this advisory existing:
erring toward under-claiming is acceptable *because the operator is told and can
correct it*. An advisory that never fires does not merely lose a message — it
converts a deliberate, disclosed under-claim into a silent one and removes the
ADR's stated reason for picking that direction over the alternative.

It had no test of any kind: not the collector, not the wiring, not the source
kind. Nothing anywhere drove it.

Both directions are covered, and the silent half matters as much as the firing
half for the same reason it did on the rentas advisory: an advisory that also
fires when the operator DID answer is a blanket advisory, and the ADR's default
is only defensible if the message means something when it appears.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, ModeloRevision
from ....domain.contribuyente import DescendantInfo, RentaMaritalStatus, descendant_facts_from_list
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import profile_create_storage_span, set_active_fields
from ...workflow import workflow_state_repository
from .._minimo_descendientes_advisory import collect_minimo_descendientes_prorrata_inferred_diagnostics

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "3d3d3d3d-3d3d-4d3d-8d3d-3d3d3d3d3d3d"
_FILING_YEAR = 2024
_ESTATAL_CASILLA: CasillaId = "0513"
_KIND = "minimo_descendientes_prorrata_inferred"

_CLAIMED = {_ESTATAL_CASILLA: Decimal("1200")}
_NOTHING_CLAIMED = {_ESTATAL_CASILLA: Decimal("0")}

#: The signals that make the engine INFER a second entitled contribuyente: a
#: partnered filer declaring individually. Exactly the ordinary two-parent
#: household the derivation exists to correct.
#:
#: The CODE is used rather than the word token the derivation also accepts,
#: because the profile schema constrains marital_status to the numeric enum --
#: so a code is what a real profile can hold, and these facts go through the
#: real write path.
_INFERRED_SECOND_FILER = {
    "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
    "filing_export.declaration_type": "1",
}


@pytest.fixture(autouse=True)
def _bucket(tmp_path: Path) -> Iterator[None]:
    from ... import wizard as _wizard

    assert _wizard.WIZARD_FLOWS
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_BUCKET_ID):
        workflow_state_repository().update(lambda s: register_minimal_profile(s, profile_id=_BUCKET_ID))
        yield


def _revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _write(*descendants: DescendantInfo, **profile_facts: str) -> None:
    facts = [UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))]
    facts.extend(UserProfileFact(path=path, value=value) for path, value in profile_facts.items())
    workflow_state_repository().update(lambda s: set_active_fields(s, tuple(facts)))


def _write_household(*descendants: DescendantInfo, signals: dict[str, str] | None = None) -> None:
    _write(*descendants, **(_INFERRED_SECOND_FILER if signals is None else signals))


def _collect(casilla_values: dict[CasillaId, Decimal] | None = None) -> tuple[object, ...]:
    return collect_minimo_descendientes_prorrata_inferred_diagnostics(
        _revision(),
        _CLAIMED if casilla_values is None else casilla_values,
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )


def _child(**overrides: object) -> DescendantInfo:
    return DescendantInfo(birth_date=date(_FILING_YEAR - 10, 5, 1), **overrides)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fires: the inference actually decided the factor.
# ---------------------------------------------------------------------------


def test_fires_when_the_prorrata_was_inferred_rather_than_answered() -> None:
    """A partnered filer declaring individually, with no explicit answer on record."""
    _write_household(_child())
    diagnostics = _collect()
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == _KIND  # type: ignore[attr-defined]
    assert diagnostics[0].casilla_id == _ESTATAL_CASILLA  # type: ignore[attr-defined]


def test_the_message_names_the_descendant_and_both_corrections() -> None:
    """The ADR's default is only defensible if the operator can act on the message.

    Under-claiming is disclosed rather than silent ONLY if the advisory says
    which descendant was inferred and how to state the answer in either
    direction. A message naming one direction would push every correction the
    same way.
    """
    _write_household(_child())
    message = _collect()[0].message  # type: ignore[attr-defined]
    assert "renta_family.descendiente.0" in message
    assert "PRORRATA=false" in message
    assert "PRORRATA=true" in message


# ---------------------------------------------------------------------------
# Silent: nothing was inferred, so there is nothing to disclose.
# ---------------------------------------------------------------------------


def test_silent_when_the_operator_answered_explicitly() -> None:
    """An explicit answer is not an inference, in either direction."""
    _write_household(_child(prorrata_minimo=True))
    assert _collect() == ()

    _write_household(_child(prorrata_minimo=False))
    assert _collect() == ()


def test_silent_when_shared_custody_decided_it() -> None:
    """Custodia compartida is a declared fact, not an inference from marital status."""
    _write_household(_child(custodia_compartida=True))
    assert _collect() == ()


def test_silent_when_no_second_filer_is_indicated() -> None:
    """An unpartnered filer takes the full mínimo; nothing was inferred away."""
    _write_household(
        _child(),
        signals={
            "renta_taxpayer.marital_status": RentaMaritalStatus.SOLTERO.value,
            "filing_export.declaration_type": "1",
        },
    )
    assert _collect() == ()


def test_silent_for_a_married_conjunta_return() -> None:
    """Both progenitores inside one unit, so no prorrata is applied to disclose."""
    _write_household(
        _child(),
        signals={
            "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
            "filing_export.declaration_type": "2",
        },
    )
    assert _collect() == ()


def test_silent_when_nothing_is_being_claimed() -> None:
    _write_household(_child())
    assert _collect(_NOTHING_CLAIMED) == ()


def test_silent_for_another_modelo() -> None:
    _write_household(_child())
    assert (
        collect_minimo_descendientes_prorrata_inferred_diagnostics(
            _revision(),
            _CLAIMED,
            modelo="303",
            bucket_id=_BUCKET_ID,
        )
        == ()
    )


def test_names_only_the_descendants_whose_factor_was_inferred() -> None:
    """A mixed household discloses the inference and not the declared answers."""
    _write_household(_child(prorrata_minimo=False), _child(), _child(custodia_compartida=True))
    message = _collect()[0].message  # type: ignore[attr-defined]
    assert "renta_family.descendiente.1" in message
    assert "renta_family.descendiente.0" not in message
    assert "renta_family.descendiente.2" not in message


def test_the_message_stays_inside_its_length_bound_for_a_large_household() -> None:
    """The sibling advisory's message overflowed its bound on a large household.

    That defect turned an advisory into a hard ValidationError for the filer
    with the most children at stake. This collector shares the bound, so it
    gets the same case.
    """
    _write_household(*[_child() for _ in range(12)])
    diagnostics = _collect()
    assert len(diagnostics) == 1
    assert len(diagnostics[0].message) <= 512  # type: ignore[attr-defined]
