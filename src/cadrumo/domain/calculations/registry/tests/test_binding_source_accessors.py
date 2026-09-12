"""The typed source accessors narrow the provider member and refuse a narrowing gap.

``binding_source_casilla_ids`` and ``binding_source_modelo`` used to chain on the
binding's kind and re-parse a dumped selector mapping per family, ending in a
bare ``()``/``None`` for anything unhandled. That fallback could not tell a
family that genuinely declares no source coordinate from one that declares a
coordinate the accessor had simply never been taught to read: both answered
"none", and a real source silently left the carry.

The accessors now match structurally over the constructed provider member, and
the registration states independently -- derived from the member's own fields --
whether the family names a source coordinate at all. A family that says it does
and that no branch narrows is refused.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, create_model

from .....core.aggregation import BindingSourceKind
from ..binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS, registration_for
from ..bindings import binding_source_casilla_ids, binding_source_modelo
from ..errors import RegistryValidationError
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _previous_filing_binding() -> BindingDefinition:
    """A previous-filing carry naming one source casilla in the singular shape."""
    return BindingDefinition.model_validate(
        {
            "id": "modelo-100-prior-year-base",
            "provider": {
                "kind": "previous_filing",
                "source_modelo": "100",
                "source_casilla_id": "0435",
                "temporal": {"kind": "filing_year_offset", "years": -1, "source_periods": ["0A"]},
            },
            "value": {"data_type": "money", "channel": "decimal"},
            "aggregation": {"op": "copy"},
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-modelo-100-manual",),
        },
    )


def _profile_binding() -> BindingDefinition:
    """A profile fact, which names no prior filing at all."""
    return BindingDefinition.model_validate(
        {
            "id": "renta-profile-taxpayer-ccaa",
            "provider": {"kind": "profile", "profile_key": "taxpayer.ccaa"},
            "value": {"data_type": "text", "channel": "text"},
            "aggregation": {"op": "copy"},
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-modelo-100-manual",),
        },
    )


def test_a_family_that_names_a_source_coordinate_returns_it() -> None:
    """The handled family answers from its own typed member."""
    binding = _previous_filing_binding()

    assert binding_source_casilla_ids(binding) == ("0435",)
    assert binding_source_modelo(binding) == "100"


def test_a_family_with_no_source_coordinate_answers_empty_and_says_so() -> None:
    """The empty answer is backed by the registration, not by falling off the end."""
    binding = _profile_binding()
    registration = registration_for(BindingSourceKind.PROFILE)

    assert binding_source_casilla_ids(binding) == ()
    assert binding_source_modelo(binding) is None
    assert registration.names_source_casilla is False
    assert registration.names_source_modelo is False


def test_every_family_declaring_a_source_casilla_is_one_the_accessor_narrows() -> None:
    """No live family reaches the refusal: the table and the accessors agree today.

    This is the invariant the refusal protects. If a future provider member adds
    a source coordinate without a branch, this assertion and the refusal fire on
    the same change rather than the carry going quietly missing.
    """
    declaring = {
        kind for kind, registration in BINDING_PROVIDER_REGISTRATIONS.items() if registration.names_source_casilla
    }

    assert declaring == {
        BindingSourceKind.PREVIOUS_FILING,
        BindingSourceKind.RELATION_PREFILL,
        BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
        BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY,
        BindingSourceKind.PRORRATA_REGULARIZACION,
    }


@pytest.mark.parametrize(
    ("fields", "names_casilla", "names_modelo"),
    [
        ({"source_casilla_id": (str, ...)}, True, False),
        ({"source_casilla_ids": (tuple[str, ...], ())}, True, False),
        ({"source_modelo": (str, ...)}, False, True),
        ({"profile_key": (str, ...)}, False, False),
    ],
    ids=["singular", "plural", "modelo_only", "neither"],
)
def test_the_registration_reads_the_source_facts_off_the_member(
    fields: dict[str, object],
    names_casilla: bool,
    names_modelo: bool,
) -> None:
    """The declared facts are derived from a fabricated member's own fields."""
    member: type[BaseModel] = create_model("_FabricatedProvider", **fields)
    profile = registration_for(BindingSourceKind.PROFILE)
    fabricated = type(profile)(
        kind=profile.kind,
        provider_model=member,
        validator=profile.validator,
        permitted_value_channels=profile.permitted_value_channels,
        permitted_aggregation_ops=profile.permitted_aggregation_ops,
        permitted_terminal_origins=profile.permitted_terminal_origins,
        output=profile.output,
        disposition=profile.disposition,
        route=profile.route,
        authoring=profile.authoring,
    )

    assert fabricated.names_source_casilla is names_casilla
    assert fabricated.names_source_modelo is names_modelo


def test_a_narrowing_gap_is_refused_rather_than_answered_empty() -> None:
    """The drift branch raises with the binding and the coordinate named."""
    from ..bindings import _refuse_undeclared_source_narrowing

    with pytest.raises(RegistryValidationError, match="does not narrow"):
        _refuse_undeclared_source_narrowing(_profile_binding(), "source casilla")
