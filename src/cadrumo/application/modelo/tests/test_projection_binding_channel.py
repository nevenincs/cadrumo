"""The projection ``--binding`` split is decided by the registry, not by parse success.

The projection previously chose a caller override's channel by trying
:class:`~decimal.Decimal` on the value and treating failure as "this must be an
enum". That inverted the test: a decimal binding whose value did not parse was
silently reclassified as an enum string, so a Spanish-convention operator's
``1.234,56`` was accepted as literal text on the enum channel rather than
refused. The calculate path never had this defect — it reads
:func:`enum_consumed_binding_ids` from the revision and only then parses — and
the projection now shares that one resolution shape.

These exercise the real Modelo 100 registry revision rather than a constructed
one, so the enum and decimal ids under test are the revision's own declarations.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        The grammar the decimal channel enforces.
    :class:`~domain.calculations.registry.RegistrySnapshot`
        The snapshot whose revision declares each binding's channel.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
from .._calculate_input import ModeloCalculateBindingInputError, ModeloCalculateDecimalInputError
from .._projection import _parse_projection_binding_overrides

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2024
_ENUM_BINDING = "renta-2024-profile-tax-residence-ccaa"
_DECIMAL_BINDING = "renta-2024-certificado-trabajo-retenciones"
_DATE_BINDING = "renta-2024-profile-taxpayer-birth-date"


@pytest.fixture(scope="module")
def revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _refusal_context(
    error: ModeloCalculateBindingInputError | ModeloCalculateDecimalInputError,
) -> Mapping[str, object]:
    """Return the refusal's context, failing loudly when it carries none.

    A refusal whose context is empty cannot name the offending flag or value to
    the operator, so an absent context is itself a defect rather than something
    to navigate around with a bare subscript.
    """
    assert error.context is not None, f"{type(error).__name__} must carry an operator-facing context"
    return error.context


def test_the_fixture_ids_are_the_revisions_own_channel_declarations(revision: ModeloRevision) -> None:
    """Anchor the ids against the registry so a renamed binding fails loudly here.

    Without this the other tests could pass vacuously against ids that no longer
    carry the channel they are named for.
    """
    enum_ids = enum_consumed_binding_ids(revision)
    date_ids = revision_date_binding_ids(revision)
    declared = {binding.id for binding in revision.bindings}

    assert _ENUM_BINDING in enum_ids
    assert _DATE_BINDING in date_ids
    assert _DECIMAL_BINDING in declared
    assert _DECIMAL_BINDING not in enum_ids
    assert _DECIMAL_BINDING not in date_ids


def test_a_decimal_binding_refuses_the_spanish_thousands_form(revision: ModeloRevision) -> None:
    """``1.234,56`` on a decimal binding REFUSES instead of becoming an enum string.

    This is the defect itself. Before the registry-declared split it landed in
    the enum channel verbatim, so the calculation consumed the literal text
    ``"1.234,56"`` and no refusal ever reached the operator.
    """
    with pytest.raises(ModeloCalculateDecimalInputError) as excinfo:
        _parse_projection_binding_overrides({_DECIMAL_BINDING: "1.234,56"}, revision)

    context = _refusal_context(excinfo.value)
    assert context["key"] == _DECIMAL_BINDING
    assert context["value"] == "1.234,56"


@pytest.mark.parametrize("raw", ["1.234,56", "1e3", "+140000", "1_000", "NaN", "Infinity", "not-decimal"])
def test_a_malformed_decimal_never_reaches_the_enum_channel(revision: ModeloRevision, raw: str) -> None:
    """No malformed decimal value may be silently reclassified, for any form.

    Asserting the refusal alone would not catch a regression that reintroduced
    the fallback for a subset of forms, so this pins that the enum channel is
    never the destination for a decimal binding.
    """
    with pytest.raises(ModeloCalculateDecimalInputError):
        _parse_projection_binding_overrides({_DECIMAL_BINDING: raw}, revision)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1234.56", Decimal("1234.56")), ("0", Decimal("0")), ("140000", Decimal("140000"))],
)
def test_a_decimal_binding_still_accepts_a_canonical_amount(
    revision: ModeloRevision,
    raw: str,
    expected: Decimal,
) -> None:
    decimals, enums = _parse_projection_binding_overrides({_DECIMAL_BINDING: raw}, revision)

    assert decimals == {_DECIMAL_BINDING: expected}
    assert enums == {}


def test_a_decimal_binding_carries_sub_cent_precision(revision: ModeloRevision) -> None:
    """Sub-cent precision is legitimate: the export encoder rounds it ROUND_HALF_UP.

    What the channel refuses is a Spanish thousands lookalike, not precision --
    so a sub-cent value passes at any number of fractional digits provided its
    lead group cannot open a grouping run. ``0.335`` qualifies because a leading
    zero never starts one.
    """
    decimals, enums = _parse_projection_binding_overrides({_DECIMAL_BINDING: "0.335"}, revision)

    assert decimals == {_DECIMAL_BINDING: Decimal("0.335")}
    assert enums == {}


def test_a_decimal_binding_refuses_a_spanish_thousands_lookalike(revision: ModeloRevision) -> None:
    """``2.345`` on a money binding is undecidable, so it refuses rather than guessing.

    This test replaced an assertion that the channel kept an "uncapped sub-cent
    posture" and accepted this very token. That posture was retired
    deliberately: the binding under test declares ``data_type = "money"``, and a
    taxpayer typing ``2.345`` euros may mean two thousand three hundred
    forty-five. A parser that can detect the ambiguity and answers anyway is
    guessing at a thousandfold error.
    """
    with pytest.raises(ModeloCalculateDecimalInputError):
        _parse_projection_binding_overrides({_DECIMAL_BINDING: "2.345"}, revision)


def test_a_genuine_enum_binding_still_carries_its_string_verbatim(revision: ModeloRevision) -> None:
    """The registry-declared enum channel is unaffected by the decimal tightening."""
    decimals, enums = _parse_projection_binding_overrides({_ENUM_BINDING: "andalucia"}, revision)

    assert enums == {_ENUM_BINDING: "andalucia"}
    assert decimals == {}


def test_an_enum_binding_accepts_a_numeric_looking_string_on_the_enum_channel(revision: ModeloRevision) -> None:
    """A parseable value on an enum binding must NOT be pulled onto the decimal channel.

    The inverse of the headline defect: routing by parse success also misrouted
    this direction, so an enum key that happens to look numeric stayed text only
    by accident.
    """
    decimals, enums = _parse_projection_binding_overrides({_ENUM_BINDING: "2024"}, revision)

    assert enums == {_ENUM_BINDING: "2024"}
    assert decimals == {}


def test_both_channels_resolve_together_in_one_call(revision: ModeloRevision) -> None:
    decimals, enums = _parse_projection_binding_overrides(
        {_DECIMAL_BINDING: "1234.56", _ENUM_BINDING: "andalucia"},
        revision,
    )

    assert decimals == {_DECIMAL_BINDING: Decimal("1234.56")}
    assert enums == {_ENUM_BINDING: "andalucia"}


def test_a_date_sourced_binding_refuses_rather_than_coercing(revision: ModeloRevision) -> None:
    """A profile date fact cannot ride the --binding flag, matching the calculate path."""
    with pytest.raises(ModeloCalculateBindingInputError) as excinfo:
        _parse_projection_binding_overrides({_DATE_BINDING: "1980-01-01"}, revision)

    assert excinfo.value.translated_message == "application.modelo.errors.calculate_binding_is_date_sourced"


def test_an_unknown_binding_id_refuses_naming_the_accepted_set(revision: ModeloRevision) -> None:
    """An undeclared id refuses instead of flowing to the engine as an enum string."""
    with pytest.raises(ModeloCalculateBindingInputError) as excinfo:
        _parse_projection_binding_overrides({"renta-2024-not-a-real-binding": "1"}, revision)

    assert excinfo.value.translated_message == "application.modelo.errors.calculate_binding_unknown"
    accepted = _refusal_context(excinfo.value)["accepted"]
    assert isinstance(accepted, str), "the refusal must render the accepted set as operator-readable text"
    assert _DECIMAL_BINDING in accepted


def test_no_overrides_returns_two_empty_channels(revision: ModeloRevision) -> None:
    assert _parse_projection_binding_overrides(None, revision) == ({}, {})
    assert _parse_projection_binding_overrides({}, revision) == ({}, {})
