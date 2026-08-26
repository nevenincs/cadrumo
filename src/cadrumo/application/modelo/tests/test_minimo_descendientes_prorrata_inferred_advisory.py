"""The Art. 61 norma 1ª prorrata advisory, which the chosen default direction depends on.

This advisory is not a nice-to-have diagnostic. The engine applies the
prorrata where profile signals indicate a second entitled filer, rather than
claim the full amount, on the strength of this advisory existing:
erring toward under-claiming is acceptable *because the operator is told and can
correct it*. An advisory that never fires does not merely lose a message — it
converts a deliberate, disclosed under-claim into a silent one and removes the
stated reason for picking that direction over the alternative.

It had no test of any kind: not the collector, not the wiring, not the source
kind. Nothing anywhere drove it.

Both directions are covered, and the silent half matters as much as the firing
half for the same reason it did on the rentas advisory: an advisory that also
fires when the operator DID answer is a blanket advisory, and the chosen default
is only defensible if the message means something when it appears.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ....core import CasillaId, Modelo
from ....core.resources import resources
from ....domain.contribuyente import DescendantInfo, RentaMaritalStatus, descendant_facts_from_list
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from ...aggregation import CalculationSourceDiagnostic
from .._minimo_descendientes_advisory import collect_minimo_descendientes_prorrata_inferred_diagnostics
from ._advisory_bucket_fixture import _bucket  # noqa: F401
from ._advisory_bucket_fixture import operator_text as _operator_text

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
    "renta_filing.declaration_type": "1",
}


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _write(*descendants: DescendantInfo, **profile_facts: str) -> None:
    facts = [UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))]
    facts.extend(UserProfileFact(path=path, value=value) for path, value in profile_facts.items())
    set_active_test_profile_facts(tuple(facts))


def _write_household(*descendants: DescendantInfo, signals: dict[str, str] | None = None) -> None:
    _write(*descendants, **(_INFERRED_SECOND_FILER if signals is None else signals))


def _collect(casilla_values: dict[CasillaId, Decimal] | None = None) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_minimo_descendientes_prorrata_inferred_diagnostics(
        _revision(),
        _CLAIMED if casilla_values is None else casilla_values,
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )


def _child(*, custodia_compartida: bool = False, prorrata_minimo: bool | None = None) -> DescendantInfo:
    return DescendantInfo(
        birth_date=date(_FILING_YEAR - 10, 5, 1),
        custodia_compartida=custodia_compartida,
        prorrata_minimo=prorrata_minimo,
    )


# ---------------------------------------------------------------------------
# Fires: the inference actually decided the factor.
# ---------------------------------------------------------------------------


def test_fires_when_the_prorrata_was_inferred_rather_than_answered() -> None:
    """A partnered filer declaring individually, with no explicit answer on record."""
    _write_household(_child())
    diagnostics = _collect()
    assert len(diagnostics) == 1
    assert diagnostics[0].source_kind == _KIND
    assert diagnostics[0].casilla_id == _ESTATAL_CASILLA


def test_the_advisory_grounds_from_the_casilla_it_addresses() -> None:
    """Casilla-derived, not advisory-asserted: norma 1ª has no finer catalogue entry.

    The whole-article ``ley-35-2006:art-61`` entry already grounds the norma 1ª
    prorrateo clause at exactly this granularity (its own required_text targets
    that sentence), which is what casilla 0513 already references -- nothing
    finer exists to mint on ``asserted_legal_refs``.
    """
    _write_household(_child())
    diagnostic = _collect()[0]
    assert diagnostic.legal_refs == ("ley-35-2006:art-56", "ley-35-2006:art-58", "ley-35-2006:art-61")
    assert diagnostic.asserted_legal_refs == ()


def test_the_message_names_the_descendant_and_both_corrections() -> None:
    """The chosen default is only defensible if the operator can act on the message.

    Under-claiming is disclosed rather than silent ONLY if the advisory says
    which descendant was inferred and how to state the answer in either
    direction. A message naming one direction would push every correction the
    same way.
    """
    _write_household(_child())
    message = _operator_text(_collect()[0])
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
            "renta_filing.declaration_type": "1",
        },
    )
    assert _collect() == ()


def test_silent_for_a_married_conjunta_return() -> None:
    """Both progenitores inside one unit, so no prorrata is applied to disclose."""
    _write_household(
        _child(),
        signals={
            "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
            "renta_filing.declaration_type": "2",
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
    message = _collect()[0].message
    assert "renta_family.descendiente.1" in message
    assert "renta_family.descendiente.0" not in message
    assert "renta_family.descendiente.2" not in message


def test_the_conjunta_branch_is_pinned_on_the_codes_the_schema_can_store() -> None:
    """Art. 82.1's two modalities, on the ONLY values this field can hold.

    ``renta_taxpayer.marital_status`` is constrained to the ECIVIL enum, so a
    code is what a real profile carries. Every earlier test of this branch
    passed a ``SituacionFamiliar`` WORD form straight to the injector, which the
    write door refuses — so the branch was exercised only on a value production
    can never produce, and dropping the pareja-de-hecho CODE from the partnered
    set regressed every real filer while failing nothing.

    These facts go through the real write path, so a value the schema would
    reject cannot reach the assertion.
    """
    from ..profile_binding import second_entitled_filer_indicated

    unmarried = {
        "renta_taxpayer.marital_status": RentaMaritalStatus.PAREJA_HECHO.value,
        "renta_filing.declaration_type": "2",
    }
    married = {
        "renta_taxpayer.marital_status": RentaMaritalStatus.CASADO.value,
        "renta_filing.declaration_type": "2",
    }
    # Art. 82.1.2a: no marriage bond, so the unit is one progenitor plus the
    # minor children and the other progenitor stays separately entitled.
    assert second_entitled_filer_indicated(unmarried) is True
    # Art. 82.1.1a: both progenitores inside the one unit, nothing to share.
    assert second_entitled_filer_indicated(married) is False

    # And the same codes survive the write door, which is what makes them the
    # values production actually sees.
    _write_household(_child(), signals=unmarried)
    assert len(_collect()) == 1
    _write_household(_child(), signals=married)
    assert _collect() == ()


def test_the_partnered_tokens_carry_no_foreign_vocabulary() -> None:
    """The token sets must hold only values this field can store.

    A word form here is not merely dead: it gives a test a way to match on a
    branch no real filer takes, which is exactly how a dropped code went
    unnoticed. Deriving the sets from the enum makes that unrepresentable, and
    this asserts the derivation rather than the current contents.
    """
    from ..profile_binding import (
        _MARRIED_STATUS_TOKENS,
        _PARTNERED_STATUS_TOKENS,
        _UNMARRIED_STATUS_TOKENS,
    )

    storable = {member.value for member in RentaMaritalStatus}
    for name, tokens in (
        ("married", _MARRIED_STATUS_TOKENS),
        ("partnered", _PARTNERED_STATUS_TOKENS),
        ("unmarried", _UNMARRIED_STATUS_TOKENS),
    ):
        assert tokens <= storable, f"{name} set carries tokens the schema cannot store: {sorted(tokens - storable)}"
    # Married and unmarried partition the enum: no code is both, none is neither.
    assert storable == _MARRIED_STATUS_TOKENS | _UNMARRIED_STATUS_TOKENS
    assert not _MARRIED_STATUS_TOKENS & _UNMARRIED_STATUS_TOKENS


def test_the_message_stays_inside_its_length_bound_for_a_large_household() -> None:
    """The sibling advisory's message overflowed its bound on a large household.

    That defect turned an advisory into a hard ValidationError for the filer
    with the most children at stake. This collector shares the bound, so it
    gets the same case.
    """
    _write_household(*[_child() for _ in range(12)])
    diagnostics = _collect()
    assert len(diagnostics) == 1
    assert len(diagnostics[0].message) <= 512
