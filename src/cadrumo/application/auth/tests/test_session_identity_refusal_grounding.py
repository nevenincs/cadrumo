"""Live-auth identity refusals read their field name from the schema.

Both refusals name a profile field the operator has to go and fill in before
authentication can proceed. They used to spell the field's dotted path into
their sentence, which is not what the profile editor shows and could not be
kept in step with a schema rename.
"""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ...user_profile.preflight import build_profile_preflight_requirement
from ..sessions import (
    _PROFILE_TAX_ID_PATH,
    _grounded_profile_identity_requirement,
    _profile_field_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The selector token for the same field. Checked alongside the path because a
#: refusal could name either, and a path-only assertion would miss the token.
_TAX_ID_SELECTOR = "tax.id"


def _label() -> str:
    return build_profile_preflight_requirement(
        _PROFILE_TAX_ID_PATH,
        schema=resources().user_profile_schema.singleton,
    ).label


def test_the_field_label_differs_from_both_its_path_and_its_selector_token() -> None:
    """Anchor: the assertions below are vacuous if any of the three coincide."""
    label = _label()

    assert label != _PROFILE_TAX_ID_PATH
    assert label != _TAX_ID_SELECTOR


def test_the_refusal_text_names_the_field_by_its_operator_label() -> None:
    assert _label() in _grounded_profile_identity_requirement()


def test_the_refusal_text_carries_no_raw_identifier_for_the_field() -> None:
    rendered = _grounded_profile_identity_requirement()

    assert _PROFILE_TAX_ID_PATH not in rendered
    assert _TAX_ID_SELECTOR not in rendered


_CLAVE_FIELD_PATHS = (
    "auth.dni_nie",
    "auth.numero_soporte",
    "auth.fecha_validez",
)


@pytest.mark.parametrize("path", _CLAVE_FIELD_PATHS)
def test_each_clave_credential_field_label_differs_from_its_path(path: str) -> None:
    """Anchor: the assertion below is vacuous for any field where they match."""
    assert _profile_field_label(path) != path


@pytest.mark.parametrize("path", _CLAVE_FIELD_PATHS)
def test_no_clave_credential_rendering_leaks_its_storage_path(path: str) -> None:
    """These fields declare no selector, so the label is resolved from the path.

    The rendering must therefore neither be the path nor contain it, which is
    what distinguishes a resolved label from the builder's documented fallback
    of returning the argument unchanged.
    """
    rendered = _profile_field_label(path)

    assert rendered
    assert path not in rendered
