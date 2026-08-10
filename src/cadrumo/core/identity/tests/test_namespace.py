"""Real-behavior tests for the AEAT document-identifier namespace taxonomy.

Covers :class:`~core.identity.IdentifierNamespace` and the three AEAT-issued
aliases it names (:data:`~core.identity.AeatExpedienteId`,
:data:`~core.identity.AeatClaveLiquidacion`,
:data:`~core.identity.AeatPresentationId`).

Two things are worth stating about what this suite proves, because a reader
could reasonably assume more.

*The expediente shape is pinned against a captured value, not a synthetic
one.* ``202310013522456T`` is the id the sede adapter's own module comment
records from the live capture, so the accept case is anchored to something
AEAT actually issued rather than to a string assembled to match the pattern
under test.

*The pattern is proven to be load-bearing over the length bound alone.*
``EXP000000000001`` is fifteen characters, so it satisfies the 12-32 window
and was silently accepted while the bound was the only constraint on a field
-- it was a real test fixture in this tree until this alias landed. Asserting
it now refuses is what distinguishes "the alias carries a pattern" from "the
alias carries a length", which no length-only assertion can tell apart.

What this suite does NOT prove: that the bound matches every shape AEAT
issues. The window is an OBSERVED range on external behaviour AEAT has never
published, deliberately wider than the captures on both sides. A refusal here
is evidence about this app's contract, never about AEAT's grammar.

See Also:
    :mod:`~core.identity._namespace`
        Taxonomy under test.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .. import (
    AeatClaveLiquidacion,
    AeatExpedienteId,
    AeatPresentationId,
    IdentifierNamespace,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Expediente = single_field_holder("expediente_id", AeatExpedienteId)
_Clave = single_field_holder("clave_liquidacion", AeatClaveLiquidacion)
_Presentation = single_field_holder("presentation_id", AeatPresentationId)

#: The expediente id the sede adapter records from the live capture.
_CAPTURED_EXPEDIENTE = "202310013522456T"

_AEAT_PREFIX = "aeat_"
_APP_PREFIX = "app_"


def test_expediente_accepts_the_captured_aeat_shape() -> None:
    assert _Expediente.value_of(_Expediente.build(_CAPTURED_EXPEDIENTE)) == _CAPTURED_EXPEDIENTE


@pytest.mark.parametrize(
    "expediente_id",
    (
        pytest.param("1", id="the-iva-compensation-divergence-value"),
        pytest.param("2023100135T", id="one-under-the-window"),
        pytest.param("2" * 33, id="one-over-the-window"),
        pytest.param("202310013522456t", id="lowercase-suffix"),
        pytest.param("202-10013522456T", id="separator"),
        pytest.param("A02310013522456T", id="no-leading-year-run"),
        pytest.param("202 10013522456T", id="embedded-space"),
        pytest.param("", id="empty"),
        pytest.param("            ", id="blank"),
    ),
)
def test_expediente_refuses_shapes_outside_the_observed_contract(expediente_id: str) -> None:
    with pytest.raises(ValidationError):
        _Expediente.build(expediente_id)


def test_expediente_pattern_refuses_a_value_the_length_bound_alone_admitted() -> None:
    """The pattern is load-bearing, not decorative.

    ``EXP000000000001`` is 15 characters, inside the 12-32 window, and was a
    live fixture value in this tree while each field carried only that window.
    A length-only constraint cannot tell it from a real expediente; the
    pattern can, and this asserts it does.
    """
    assert 12 <= len("EXP000000000001") <= 32
    with pytest.raises(ValidationError):
        _Expediente.build("EXP000000000001")


def test_clave_liquidacion_accepts_the_bound_the_debt_boundary_evidences() -> None:
    assert _Clave.value_of(_Clave.build("A" * 64)) == "A" * 64


@pytest.mark.parametrize(
    "clave",
    (
        pytest.param("", id="empty"),
        pytest.param("B" * 65, id="one-over-the-window"),
    ),
)
def test_clave_liquidacion_refuses_values_outside_its_window(clave: str) -> None:
    with pytest.raises(ValidationError):
        _Clave.build(clave)


def test_clave_liquidacion_admits_a_blank_so_its_boundary_guard_must_stay() -> None:
    """A whitespace-only clave passes this alias, by design.

    The alias constrains length only -- no clave de liquidación grammar has
    been observed across enough captures to assert a pattern. ``Deuda`` keeps
    a separate blank-rejecting validator for exactly this gap, and this test
    exists so that removing that validator on the grounds the field is "now
    typed" fails here rather than silently re-admitting the blank an empty
    listing cell parses to.
    """
    assert _Clave.value_of(_Clave.build("   ")) == "   "


def test_presentation_id_accepts_the_receipt_boundary_bound() -> None:
    assert _Presentation.value_of(_Presentation.build("C" * 64)) == "C" * 64


def test_presentation_id_refuses_a_value_over_its_window() -> None:
    with pytest.raises(ValidationError):
        _Presentation.build("D" * 65)


def test_presentation_id_admits_an_empty_value_so_its_absence_stays_modelled_as_none() -> None:
    """An empty presentation id PASSES this alias, by design and matching HEAD.

    The receipt boundary declared ``max_length=64`` with no minimum before
    this alias existed, and this alias carries that bound unchanged rather
    than tightening it in passing. Absence of a *número de justificante* is
    modelled by the field being optional, so a surface seeing ``""`` is
    seeing a parse artefact and owns its own guard.

    Asserted rather than left implicit so this gap reads as measured, not
    overlooked -- it is the same gap
    :func:`test_clave_liquidacion_admits_a_blank_so_its_boundary_guard_must_stay`
    records for the clave, and the two aliases are now documented to the same
    standard.
    """
    assert _Presentation.value_of(_Presentation.build("")) == ""


def test_every_namespace_member_declares_its_issuing_group() -> None:
    """The AEAT-issued / app-derived split is total, and keyed by the property.

    Asserted as a partition rather than against a member count, so adding a
    namespace does not require editing this test -- but adding one that
    belongs to neither group, or whose name and value disagree about which
    group it is in, fails here.
    """
    for member in IdentifierNamespace:
        assert member.value == member.name.lower(), member
        aeat = member.name.startswith("AEAT_")
        app = member.name.startswith("APP_")
        assert aeat != app, f"{member.name} belongs to neither group or to both"
        expected = _AEAT_PREFIX if aeat else _APP_PREFIX
        assert member.value.startswith(expected), member


def test_both_issuing_groups_are_populated() -> None:
    """Guards the partition test above from passing vacuously on one group."""
    groups = {member.name.split("_", 1)[0] for member in IdentifierNamespace}
    assert {"AEAT", "APP"} <= groups


def test_namespace_members_are_interchangeable_with_their_stored_token() -> None:
    """``StrEnum`` substitution is relied on wherever a namespace is persisted."""
    member = IdentifierNamespace.AEAT_EXPEDIENTE_ID
    assert member == "aeat_expediente_id"
    assert f"{member}" == "aeat_expediente_id"
    assert IdentifierNamespace("aeat_expediente_id") is member
