"""The wizard status refusal reads its field name from the schema, not prose.

The refusal used to name the required field by writing its selector token into
the sentence itself. That token appears nowhere in the profile editor, and it
could not stay in step with the schema, since a rename would have had to be
chased through four locale catalogues.

The export no-profile refusal had the same defect and is covered in the modelo
package, where the code it exercises lives.
"""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ...user_profile.preflight import build_profile_preflight_requirement
from .._status import _TAX_ID_PATH, _grounded_tax_id_requirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The token the wizard refusal used to print. It is the field's declared
#: selector, not its path, so it would survive a naive path-based check.
_LEGACY_TAX_ID_SELECTOR = "tax.id"


def _label(path: str) -> str:
    return build_profile_preflight_requirement(
        path,
        schema=resources().user_profile_schema.singleton,
    ).label


def test_the_tax_id_field_label_differs_from_both_its_path_and_its_token() -> None:
    """Anchor: the assertions below are vacuous if any of the three coincide."""
    label = _label(_TAX_ID_PATH)

    assert label != _TAX_ID_PATH
    assert label != _LEGACY_TAX_ID_SELECTOR


def test_the_wizard_refusal_names_the_tax_identifier_by_its_operator_label() -> None:
    rendered = _grounded_tax_id_requirement()

    assert _label(_TAX_ID_PATH) in rendered


def test_the_wizard_refusal_carries_no_raw_identifier_for_the_field() -> None:
    """Neither the dotted path nor the selector token may reach the operator."""
    rendered = _grounded_tax_id_requirement()

    assert _TAX_ID_PATH not in rendered
    assert _LEGACY_TAX_ID_SELECTOR not in rendered
