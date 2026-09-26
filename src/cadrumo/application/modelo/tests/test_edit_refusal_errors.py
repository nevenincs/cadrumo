"""Every edit refusal family settles under its own registered refusal code."""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.i18n.render import tr
from ..action_errors import (
    ModeloEditBaselineStaleError,
    ModeloEditContractIncompatibleError,
    ModeloEditIntentUnsupportedError,
    ModeloEditRefusedError,
    modelo_edit_refusal_error,
)
from ..edit_models import (
    ModeloEditCompatibilityRefusalV1,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditRefusalV1,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditUnsupportedIntentReason,
    ModeloEditUnsupportedIntentRefusalV1,
    ModeloEditVersionRefusalV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OWNER = "modelo.edit"
_DETAIL = "casilla-0042-private-detail"

_FAMILIES: tuple[tuple[ModeloEditRefusalV1, type[ModeloEditRefusedError], str], ...] = (
    (
        ModeloEditStaleBaselineRefusalV1(
            baseline_id="a" * 64,
            mismatching_coordinates=("current_calculation_revision_id",),
            responsible_owner=_OWNER,
            reconsideration_condition=_DETAIL,
        ),
        ModeloEditBaselineStaleError,
        "REFUSED_MODELO_EDIT_BASELINE_STALE",
    ),
    (
        ModeloEditUnsupportedIntentRefusalV1(
            reason=ModeloEditUnsupportedIntentReason.RECALCULATE_NOT_YET_WIRED,
            responsible_owner=_OWNER,
            reconsideration_condition=_DETAIL,
        ),
        ModeloEditIntentUnsupportedError,
        "REFUSED_MODELO_EDIT_INTENT_UNSUPPORTED",
    ),
    (
        ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.DISALLOWED_INTENT,
            facts=(_DETAIL,),
            responsible_owner=_OWNER,
            reconsideration_condition=_DETAIL,
        ),
        ModeloEditRefusedError,
        "REFUSED_MODELO_EDIT_REFUSED",
    ),
    (
        ModeloEditDomainRefusalV1(
            code=ModeloEditRefusalCode.PARSE_FAILED,
            responsible_owner=_OWNER,
            reconsideration_condition=_DETAIL,
        ),
        ModeloEditRefusedError,
        "REFUSED_MODELO_EDIT_REFUSED",
    ),
    (
        ModeloEditVersionRefusalV1(requested_version=2),
        ModeloEditContractIncompatibleError,
        "REFUSED_MODELO_EDIT_CONTRACT_INCOMPATIBLE",
    ),
    (
        ModeloEditCompatibilityRefusalV1(
            requested_axis="request_schema",
            responsible_owner=_OWNER,
            reconsideration_condition=_DETAIL,
        ),
        ModeloEditContractIncompatibleError,
        "REFUSED_MODELO_EDIT_CONTRACT_INCOMPATIBLE",
    ),
)


@pytest.mark.parametrize(
    ("refusal", "error_type", "code"),
    _FAMILIES,
    ids=["stale-baseline", "unsupported-intent", "disallowed-intent", "parse-failed", "version", "compatibility"],
)
def test_each_refusal_family_raises_its_registered_refusal(
    refusal: ModeloEditRefusalV1,
    error_type: type[ModeloEditRefusedError],
    code: str,
) -> None:
    """The family, never the refusal's detail, decides the settled code and message."""
    error = modelo_edit_refusal_error(refusal)
    registered = get_registered_error_code(error)
    message = resolve_error_message(error)

    assert type(error) is error_type
    assert registered.code == code
    assert registered.category is ErrorCategory.REFUSED
    assert registered.public_message_from_registry
    assert message == tr(registered.message_key)
    assert message.strip() and message != registered.message_key
    assert _DETAIL not in message
    assert _DETAIL not in repr(error.args)
    assert not error.context


def test_each_refusal_family_has_a_distinct_code() -> None:
    """Different families stay distinguishable to the operator."""
    by_type = {error_type: code for _refusal, error_type, code in _FAMILIES}

    assert len(set(by_type.values())) == len(by_type) == 4
