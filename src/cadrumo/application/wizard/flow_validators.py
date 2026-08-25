"""Flow-scope construction validator for the paged setup flow.

The substrate never runs the answers model's own validation (raw pydantic
messages are library prose), so the review surface is the complete gate
for every construction-time cross-field invariant on the taxpayer
projection. Rather than restate one invariant per validator, this module
registers ONE flow-scope validator that re-runs the real
:func:`projection_for_taxpayer` constructor over the staged answer set and
maps each construction failure to a typed verdict.

The mapping carries catalogue KEYS and redacted context only — the raw
pydantic / :class:`DeadlineValidationError` message never enters a verdict,
because library prose is exactly the leak class the mapping eradicates.
Each construction invariant is routed to a stable ``check`` token from the
error's field signature; the model validators stay the single authority
for the invariants themselves.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from ...core import OBJECT_TUPLE_ADAPTER
from ...core.flows import REPEATING_INSTANCE_SEPARATOR
from ..flows.definition import FlowDefinition, FlowPage, FlowRepeatingGroup
from ..flows.validators import CrossFieldValidator, ValidationVerdict, register_cross_field_validator
from ..user_profile.projections import projection_for_taxpayer

TAXPAYER_PROJECTION_VALIDATOR_ID = "taxpayer-projection-constructs"
"""Registered id of the single flow-scope taxpayer-construction validator."""

# Generic, already-localized fallback verdict key for an unclassified
# construction failure (empty ``loc`` with no recognised field token).
_FALLBACK_MESSAGE_KEY = "errors.refused.refused_user_profile_validation"
_GENERIC_CHECK = "taxpayer_projection_invalid"

# Each named legal check carries its own localized verdict key. An
# unclassified failure still rides the generic fallback above.
_CHECK_MESSAGE_LOCALE_KEYS: dict[str, str] = {
    "impatriado_requires_start_date": "wizard.setup.verifier.impatriado_requires_start_date",
    "non_resident_requires_country": "wizard.setup.verifier.non_resident_requires_country",
    "non_resident_requires_representante": "wizard.setup.verifier.non_resident_requires_representante",
}

# Field-name token (a stable code identifier, never operator prose) → the
# stable ``check`` token that identifies the fired construction invariant.
# Matched against the caught error message internally; only the token and
# the field set below ever enter a verdict.
_FIELD_TOKEN_CHECKS: tuple[tuple[str, str], ...] = (
    ("special_regime_start_date", "impatriado_requires_start_date"),
    ("country_of_fiscal_residence", "non_resident_requires_country"),
    ("representante_fiscal", "non_resident_requires_representante"),
)

_CHECK_FIELDS: dict[str, tuple[str, ...]] = {
    "impatriado_requires_start_date": ("special_regime_start_date",),
    "non_resident_requires_country": ("country_of_fiscal_residence",),
    "non_resident_requires_representante": (
        "representante_fiscal_nif",
        "representante_fiscal_nombre",
    ),
}


def _iter_pages(definition: FlowDefinition) -> tuple[FlowPage, ...]:
    pages: list[FlowPage] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowRepeatingGroup):
                pages.extend(item.pages)
            else:
                pages.append(item)
    return tuple(pages)


def _classify_error(entry: Mapping[str, object]) -> tuple[str, tuple[str, ...]]:
    """Route one pydantic error entry to a stable check token and field set.

    Uses the error message internally to detect which construction
    invariant fired (all three are model-level validators reporting an
    empty ``loc``), then returns only the stable token and its field
    tuple — the message itself never propagates.
    """
    message = str(entry.get("msg", ""))
    for token, check in _FIELD_TOKEN_CHECKS:
        if token in message:
            return check, _CHECK_FIELDS[check]
    loc = entry.get("loc", ())
    fields = (
        tuple(str(part) for part in OBJECT_TUPLE_ADAPTER.validate_python(loc)) if isinstance(loc, (tuple, list)) else ()
    )
    return _GENERIC_CHECK, fields


def _verdicts_from_validation_error(error: ValidationError) -> tuple[ValidationVerdict, ...]:
    verdicts: list[ValidationVerdict] = []
    for entry in error.errors():
        check, fields = _classify_error(entry)
        message_key = _CHECK_MESSAGE_LOCALE_KEYS.get(check, _FALLBACK_MESSAGE_KEY)
        verdicts.append(
            ValidationVerdict.failed(message_key, check=check, fields=list(fields)),
        )
    if verdicts:
        return tuple(verdicts)
    return (ValidationVerdict.failed(_FALLBACK_MESSAGE_KEY, check=_GENERIC_CHECK, fields=[]),)


def build_taxpayer_projection_validator(
    page_domain_keys: Mapping[str, str | None],
) -> CrossFieldValidator:
    """Build the flow-scope validator over a page-id → domain-key mapping.

    The substrate hands cross-field validators the answer map keyed by
    page id; this closure maps those to the schema-path key space the
    persistence layer serialises to (``domain_key`` == ``profile_key`` ==
    schema path), then re-runs the real constructor. Instance-scoped
    repeating-group answers are excluded — they serialise through the
    descendant fact path, not the top-level taxpayer projection.
    """
    domain_keys = {page_id: key for page_id, key in page_domain_keys.items() if key}

    def _validate(answers: Mapping[str, str]) -> tuple[ValidationVerdict, ...]:
        mapping: dict[str, str] = {}
        for page_id, value in answers.items():
            if REPEATING_INSTANCE_SEPARATOR in page_id:
                continue
            key = domain_keys.get(page_id)
            if key is None or value == "":
                continue
            mapping[key] = value
        try:
            projection_for_taxpayer(mapping)
        except ValidationError as error:
            return _verdicts_from_validation_error(error)
        return (ValidationVerdict.passed(),)

    return _validate


def register_taxpayer_projection_validator(definition: FlowDefinition) -> None:
    """Register the taxpayer-projection validator for a concrete definition.

    Extracts the page-id → domain-key mapping from the definition and
    registers the closure under :data:`TAXPAYER_PROJECTION_VALIDATOR_ID`;
    the definition then names that id in its ``flow_validator_ids``.
    """
    page_domain_keys = {page.id: page.domain_key for page in _iter_pages(definition)}
    register_cross_field_validator(
        TAXPAYER_PROJECTION_VALIDATOR_ID,
        build_taxpayer_projection_validator(page_domain_keys),
    )


__all__ = [
    "TAXPAYER_PROJECTION_VALIDATOR_ID",
    "build_taxpayer_projection_validator",
    "register_taxpayer_projection_validator",
]
