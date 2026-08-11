"""The export declarant-identity refusal names fields, not dotted paths.

Export is a filing-grade surface: an operator refused here has to go and fill
the field in, so the refusal names it the way the profile editor does rather
than by the internal path the export composer reads.
"""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ...user_profile import build_profile_preflight_requirement, format_profile_path_requirements

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SURNAMES_PATH = "identity.surnames"
_NAME_PATH = "identity.name"
_LEGAL_NAME_PATH = "identity.legal_name"


def _label(path: str) -> str:
    return build_profile_preflight_requirement(
        path,
        schema=resources().user_profile_schema.singleton,
    ).label


def _render(paths: list[str]) -> str:
    return ", ".join(
        format_profile_path_requirements(
            paths,
            schema=resources().user_profile_schema.singleton,
        ),
    )


def test_the_identity_fields_have_labels_that_differ_from_their_paths() -> None:
    """Anchor: the assertions below are vacuous if label and path coincide."""
    for path in (_SURNAMES_PATH, _NAME_PATH, _LEGAL_NAME_PATH):
        assert _label(path) != path


def test_a_single_missing_identity_field_renders_as_its_label() -> None:
    rendered = _render([_LEGAL_NAME_PATH])

    assert _label(_LEGAL_NAME_PATH) in rendered
    assert _LEGAL_NAME_PATH not in rendered


def test_several_missing_identity_fields_all_appear() -> None:
    """A natural person missing both name parts is told about both."""
    rendered = _render([_SURNAMES_PATH, _NAME_PATH])

    assert _label(_SURNAMES_PATH) in rendered
    assert _label(_NAME_PATH) in rendered


def test_the_rendering_carries_no_python_container_punctuation() -> None:
    """The refusal interpolates this directly into operator-facing text.

    The previous behaviour passed a list, so the message rendered Python's own
    bracket and quote punctuation around the paths.
    """
    rendered = _render([_SURNAMES_PATH, _NAME_PATH])

    for glyph in ("[", "]", "'"):
        assert glyph not in rendered


def test_the_no_profile_refusal_names_both_identity_fields_by_label() -> None:
    """The cold-start export refusal used to hard-code two paths into its prose.

    It names fields the operator must supply, so it is a field-naming refusal
    even though no profile exists to read them from, and the names must come
    from the schema like every other one.
    """
    rendered = _render([_SURNAMES_PATH, _NAME_PATH])

    assert _label(_SURNAMES_PATH) in rendered
    assert _label(_NAME_PATH) in rendered


def test_the_no_profile_refusal_carries_no_raw_dotted_path() -> None:
    rendered = _render([_SURNAMES_PATH, _NAME_PATH])

    assert _SURNAMES_PATH not in rendered
    assert _NAME_PATH not in rendered
