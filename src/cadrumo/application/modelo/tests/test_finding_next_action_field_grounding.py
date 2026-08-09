"""A finding's next_action must name a profile field the operator can actually find.

These three messages told the operator to go and set a profile fact, and they
named it by a dotted path under a ``profile`` section. No such section exists:
both fields live under ``taxpayer_type``. So the instruction did not merely read
as internal jargon -- it pointed at a path that cannot be found, which is worse
than an unfriendly identifier because it looks actionable and is not.

The assertions are deliberately written in two halves. Asserting the operator
LABEL is present proves the schema-derived rendering ran; asserting the raw
dotted path is ABSENT proves the old prose is gone rather than merely having
something appended to it. A test carrying only the first half passes against a
message that names the field both ways.

The expected label is resolved from the schema rather than typed in, so a label
rename moves this test with it instead of failing it. What is pinned as a
literal is the DEFECT -- the nonexistent path -- because that string must never
come back.

See Also:
    :func:`~application.user_profile.format_profile_selector_requirements`
        The renderer these messages route their field names through.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from ....core.resources import resources
from ...user_profile import format_profile_selector_requirements
from .._m210_rate import _fiscal_residence_requirement
from .._verification_predicates import _resolve_predicate_next_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The paths these messages used to spell. Pinned as literals because they are
#: the defect: no ``profile`` section exists in the schema, so an operator
#: following either one is sent nowhere.
_NONEXISTENT_PATHS = (
    "profile.country_of_fiscal_residence",
    "profile.representante_fiscal_nif",
)


def _label_for(selector: str) -> str:
    """Return the operator label the schema renders for one model selector."""
    rendered = format_profile_selector_requirements(
        (selector,),
        schema=resources().user_profile_schema.singleton,
    )
    assert rendered, f"the schema resolves no requirement for {selector!r}"
    return rendered[0]


def test_the_selectors_these_messages_name_resolve_to_real_fields() -> None:
    """Anti-vacuity: without this, a label that silently stopped resolving would
    make every assertion below pass against its own bare selector token."""
    for selector in ("taxpayer.country_of_fiscal_residence", "taxpayer.representante_fiscal_nif"):
        label = _label_for(selector)
        assert label != selector, f"{selector!r} no longer resolves to a field label"
        assert "(" in label, f"{selector!r} resolves to a label carrying no legal grounding"


def test_the_deferred_baseline_finding_names_the_field_by_label() -> None:
    """The M210 baseline-deferred next_action points at a findable field."""
    message = tr(
        "application.modelo.findings.m210_baseline_tipo_deferred.next_action",
        tipo_renta="rendimientos-trabajo",
        requirements=_fiscal_residence_requirement(),
    )

    assert _label_for("taxpayer.country_of_fiscal_residence") in message
    for path in _NONEXISTENT_PATHS:
        assert path not in message


def test_the_missing_convenio_finding_names_the_field_by_label() -> None:
    """The M210 convenio-missing next_action points at a findable field."""
    message = tr(
        "application.modelo.findings.m210_convenio_rate_missing.next_action",
        cc="DE",
        tipo_renta="rendimientos-trabajo",
        requirements=_fiscal_residence_requirement(),
    )

    assert _label_for("taxpayer.country_of_fiscal_residence") in message
    for path in _NONEXISTENT_PATHS:
        assert path not in message


def test_the_representante_fiscal_finding_names_the_field_by_label() -> None:
    """The representante-fiscal next_action is built through the predicate dispatch.

    Driven through ``_resolve_predicate_next_action`` rather than by calling
    ``tr`` directly, so the assertion covers the wiring as well as the string:
    a dispatch that stopped passing the requirement would render an unsubstituted
    placeholder, and this would catch it.
    """
    message = _resolve_predicate_next_action("m210-representante-fiscal-required")

    assert message is not None
    assert _label_for("taxpayer.representante_fiscal_nif") in message
    assert "{requirements}" not in message
    for path in _NONEXISTENT_PATHS:
        assert path not in message
