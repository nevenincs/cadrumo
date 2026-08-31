"""The settled profile presentation contract: what to show, and why.

This is the typed projection behind the guided `Overview -> Get data ->
Required -> Review -> Ready` interface, distinct from :mod:`overview`'s
schema-completeness projection: where `overview` answers "what does the
record hold and is it masked", this module answers the interface contract's
own presentation question -- classification (is this field
required, conditionally required with its applicability still unassessed,
optional, or not applicable), source class, and whether it currently blocks
filing readiness.

Every classification is read from application-owned facts already computed
elsewhere -- the schema's own `required` declaration, the conditional
completeness rules in :mod:`completeness`, the domain's Modelo-IVA claiming
rules, and the schema-declared `provenance.source` token on the effective
fact -- never guessed from locale or presentation state, per the interface
contract's explicit instruction. A conditionally required field whose
trigger fact is itself unanswered is `NEEDS_APPLICABILITY`, never silently
folded into `NOT_APPLICABLE`: that collapse is exactly the anti-pattern the
interface contract names
("Unknown applicability is displayed as unassessed, never silently treated
as ... not applicable").

Conditional-applicability triggers resolved here: the single-field triggers
in :data:`_CONDITIONAL_TRIGGERS` (`auth.clave_movil_route`, the legal-entity
fields, the IRNR fiscal-representative fields); the multi-field Modelo-IVA
block, resolved through the domain's own
:func:`~domain.deadlines.profile_claims_modelo_iva_block` and
:func:`~domain.deadlines.modelo_iva_profile_required_paths` rather than a
reimplemented claiming-path set; and the repeatable
`attribution_entity_socios` section's per-row country field, gated by that
row's own `participe_clave` (`completeness.PARTICIPE_CLAVE_BEARING_COUNTRY`).
Every other repeatable section reports its declared rows' fields by static
schema requiredness alone -- no conditional rule is currently declared for
them anywhere in this package, so `OPTIONAL` there is the correct answer,
not a narrowed one. `Review`'s unresolved-proposal/conflict row is not built
here: it belongs to whichever registered acquisition/reconciliation operation
proposes the divergence (censal review, previous-filing evidence), not to
this static per-field projection.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from ...core.i18n import tr
from ...core.identity import ProfileId
from ...core.json_contract import Notice, ResolvedNoticeAction
from ...core.presentation import NoticePresentation
from ...domain.deadlines.profiles import (
    MODELO_IVA_BLOCK_REQUIRED_PATHS,
    modelo_iva_profile_required_paths,
    profile_claims_modelo_iva_block,
)
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.schema import ProfileFieldType
from ...domain.user_profile.values import UserProfileRecord
from .completeness import (
    ATRIBUCION_SOCIOS_SECTION,
    AUTH_PROVIDER_PATH,
    CLAVE_MOVIL_ROUTE_PATH,
    ENTITY_TYPE_PATH,
    FISCAL_RESIDENCY_PATH,
    LEGAL_ENTITY_FORM_PATH,
    LEGAL_NAME_PATH,
    PARTICIPE_CLAVE_BEARING_COUNTRY,
    PARTICIPE_CLAVE_FIELD,
    REPRESENTANTE_FISCAL_NIF_PATH,
    REPRESENTANTE_FISCAL_NOMBRE_PATH,
    SOCIO_COUNTRY_FIELD,
    conditional_profile_required_paths,
    profile_value_is_present,
)
from .projections import EffectiveFact, record_to_effective_facts

if TYPE_CHECKING:
    from ...domain.user_profile.schema import ProfileSectionDefinition

_PRESENTATION_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

#: Every single-field-triggered conditionally required path this module
#: resolves applicability for, mapped to the trigger path whose answer
#: decides whether it applies at all.
_CONDITIONAL_TRIGGERS: dict[str, str] = {
    CLAVE_MOVIL_ROUTE_PATH: AUTH_PROVIDER_PATH,
    LEGAL_ENTITY_FORM_PATH: ENTITY_TYPE_PATH,
    LEGAL_NAME_PATH: ENTITY_TYPE_PATH,
    REPRESENTANTE_FISCAL_NIF_PATH: FISCAL_RESIDENCY_PATH,
    REPRESENTANTE_FISCAL_NOMBRE_PATH: FISCAL_RESIDENCY_PATH,
}

_MODELO_IVA_BLOCK_PATHS = frozenset(MODELO_IVA_BLOCK_REQUIRED_PATHS)


class ProfileFieldSourceClass(StrEnum):
    """Coarse origin class for a profile field's current value (the interface contract's source table).

    Derived from the schema-declared `provenance.source` token
    (`manual_cli`, `setup_wizard`, `modelo_036_import`, `aeat_censo_read`,
    `registry_inference`, `censo_artefact_g313`); never a free-form guess.
    """

    MANUAL_EDIT = "manual_edit"
    AEAT_CENSUS_ACQUISITION = "aeat_census_acquisition"
    PREVIOUS_FILING_HISTORY = "previous_filing_history"
    RECONCILED_DOCUMENT_TEXT = "reconciled_document_text"
    REGISTRY_INFERENCE = "registry_inference"


_SOURCE_TOKEN_CLASSES: dict[str, ProfileFieldSourceClass] = {
    "manual_cli": ProfileFieldSourceClass.MANUAL_EDIT,
    "setup_wizard": ProfileFieldSourceClass.MANUAL_EDIT,
    "modelo_036_import": ProfileFieldSourceClass.PREVIOUS_FILING_HISTORY,
    "aeat_censo_read": ProfileFieldSourceClass.AEAT_CENSUS_ACQUISITION,
    "registry_inference": ProfileFieldSourceClass.REGISTRY_INFERENCE,
    "censo_artefact_g313": ProfileFieldSourceClass.RECONCILED_DOCUMENT_TEXT,
}


def profile_field_source_class(source_token: str) -> ProfileFieldSourceClass:
    """Classify one schema-declared provenance token into the interface contract's coarse source class."""
    try:
        return _SOURCE_TOKEN_CLASSES[source_token]
    except KeyError:
        raise ValueError(f"unmapped provenance source token: {source_token!r}") from None


class ProfileFieldClassification(StrEnum):
    """The interface contract's classification table, minus the two rows this module never emits.

    `ADVISORY_NOTICE` and `UNRESOLVED_CONFLICT` are envelope-level and
    operation-proposal-level facts respectively, never a static per-field
    schema/completeness classification; they are composed alongside this
    projection by their owning producer, not emitted here.
    """

    APPLICABLE_REQUIRED_MISSING = "applicable_required_missing"
    NEEDS_APPLICABILITY = "needs_applicability"
    APPLICABLE_REQUIRED_PRESENT = "applicable_required_present"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


_BLOCKING_CLASSIFICATIONS = frozenset(
    {
        ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING,
        ProfileFieldClassification.NEEDS_APPLICABILITY,
    }
)


class ProfileFieldPresentationV1(BaseModel):
    """One field's settled presentation state: classification, source, readiness effect."""

    model_config = _PRESENTATION_CONFIG

    path: str
    classification: ProfileFieldClassification
    present: bool
    applicability_assessed: bool
    source: ProfileFieldSourceClass | None
    blocks_ready: bool

    @model_validator(mode="after")
    def _validate_presentation(self) -> ProfileFieldPresentationV1:
        if self.present and self.source is None:
            raise ValueError("a present field must carry a source class")
        if not self.present and self.source is not None:
            raise ValueError("a blank field cannot carry a source class")
        needs_applicability = self.classification is ProfileFieldClassification.NEEDS_APPLICABILITY
        if needs_applicability != (not self.applicability_assessed):
            raise ValueError("needs_applicability and applicability_assessed=False must agree exactly")
        if self.blocks_ready != (self.classification in _BLOCKING_CLASSIFICATIONS):
            raise ValueError("blocks_ready must match the classification's declared readiness effect")
        return self


class ProfilePresentationV1(BaseModel):
    """The settled presentation projection for one profile's declared fields."""

    model_config = _PRESENTATION_CONFIG

    profile_id: ProfileId
    fields: tuple[ProfileFieldPresentationV1, ...]

    @property
    def ready(self) -> bool:
        """Whether no field currently blocks filing readiness."""
        return not any(field.blocks_ready for field in self.fields)

    @property
    def blocking_fields(self) -> tuple[ProfileFieldPresentationV1, ...]:
        """Every field currently blocking readiness, in declaration order."""
        return tuple(field for field in self.fields if field.blocks_ready)

    def fields_by_classification(
        self, classification: ProfileFieldClassification
    ) -> tuple[ProfileFieldPresentationV1, ...]:
        """Every field carrying exactly the supplied classification, in declaration order.

        A pure filter over already-classified fields -- it introduces no new
        requirement policy, only groups what :func:`build_profile_presentation`
        already decided.
        """
        return tuple(field for field in self.fields if field.classification is classification)


def build_profile_presentation(record: UserProfileRecord) -> ProfilePresentationV1:
    """Build the settled presentation projection from one profile record.

    Reads only application-owned facts: the schema's own `required`
    declaration, :func:`completeness.conditional_profile_required_paths`,
    the domain's Modelo-IVA claiming rules, and the effective fact's own
    declared source -- never infers a classification from a value's shape
    or a locale string.
    """
    schema = load_user_profile_schema()
    effective = record_to_effective_facts(record)
    values = {path: fact.value for path, fact in effective.items()}
    conditional_required = frozenset(conditional_profile_required_paths(values))
    iva_claimed = profile_claims_modelo_iva_block(values)
    iva_required = frozenset(modelo_iva_profile_required_paths(values))

    rows: list[ProfileFieldPresentationV1] = []
    for section in schema.sections:
        if section.repeatable:
            rows.extend(_repeatable_section_rows(section, effective=effective))
            continue
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            classification, applicability_assessed = _classify_static_or_conditional(
                path=path,
                required=field.required,
                present=_path_answered(effective, path),
                effective=effective,
                conditional_required=conditional_required,
                iva_claimed=iva_claimed,
                iva_required=iva_required,
            )
            rows.append(_row(path, classification, applicability_assessed, effective))
    return ProfilePresentationV1(profile_id=record.profile_id, fields=tuple(rows))


def _classify_static_or_conditional(
    *,
    path: str,
    required: bool,
    present: bool,
    effective: dict[str, EffectiveFact],
    conditional_required: frozenset[str],
    iva_claimed: bool,
    iva_required: frozenset[str],
) -> tuple[ProfileFieldClassification, bool]:
    if required:
        return _required_classification(present), True
    if path in _MODELO_IVA_BLOCK_PATHS:
        if not iva_claimed:
            return ProfileFieldClassification.NEEDS_APPLICABILITY, False
        if path in iva_required:
            return _required_classification(present), True
        return ProfileFieldClassification.NOT_APPLICABLE, True
    trigger = _CONDITIONAL_TRIGGERS.get(path)
    if trigger is not None:
        if not _path_answered(effective, trigger):
            return ProfileFieldClassification.NEEDS_APPLICABILITY, False
        if path in conditional_required:
            return _required_classification(present), True
        return ProfileFieldClassification.NOT_APPLICABLE, True
    if path in conditional_required:
        return _required_classification(present), True
    return ProfileFieldClassification.OPTIONAL, True


def _repeatable_section_rows(
    section: ProfileSectionDefinition, *, effective: dict[str, EffectiveFact]
) -> list[ProfileFieldPresentationV1]:
    """Presentation rows for every declared instance of one repeatable section.

    A repeatable section with no declared rows contributes nothing -- a
    taxpayer with no attribution entities is not incomplete for lacking
    one, the same rule :mod:`overview` applies.
    """
    prefix = f"{section.key}."
    indices: dict[str, None] = {}
    for existing_path in effective:
        if not existing_path.startswith(prefix):
            continue
        index = existing_path[len(prefix) :].split(".", 1)[0]
        if index.isdigit():
            indices.setdefault(index, None)

    rows: list[ProfileFieldPresentationV1] = []
    for index in indices:
        clave_path = f"{section.key}.{index}.{PARTICIPE_CLAVE_FIELD}"
        clave_answered = _path_answered(effective, clave_path)
        clave_value = effective[clave_path].value if clave_answered else None
        for field in section.fields:
            path = f"{section.key}.{index}.{field.key}"
            present = _path_answered(effective, path)
            if section.key == ATRIBUCION_SOCIOS_SECTION and field.key == SOCIO_COUNTRY_FIELD and not field.required:
                if not clave_answered:
                    classification, applicability_assessed = ProfileFieldClassification.NEEDS_APPLICABILITY, False
                elif clave_value == PARTICIPE_CLAVE_BEARING_COUNTRY:
                    classification, applicability_assessed = _required_classification(present), True
                else:
                    classification, applicability_assessed = ProfileFieldClassification.NOT_APPLICABLE, True
            elif field.required:
                classification, applicability_assessed = _required_classification(present), True
            else:
                classification, applicability_assessed = ProfileFieldClassification.OPTIONAL, True
            rows.append(_row(path, classification, applicability_assessed, effective))
    return rows


def _row(
    path: str,
    classification: ProfileFieldClassification,
    applicability_assessed: bool,
    effective: dict[str, EffectiveFact],
) -> ProfileFieldPresentationV1:
    fact = effective.get(path)
    present = fact is not None and profile_value_is_present(fact.value)
    source = profile_field_source_class(fact.source) if present and fact is not None else None
    return ProfileFieldPresentationV1(
        path=path,
        classification=classification,
        present=present,
        applicability_assessed=applicability_assessed,
        source=source,
        blocks_ready=classification in _BLOCKING_CLASSIFICATIONS,
    )


def _required_classification(present: bool) -> ProfileFieldClassification:
    return (
        ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT
        if present
        else ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING
    )


def _path_answered(effective: dict[str, EffectiveFact], path: str) -> bool:
    fact = effective.get(path)
    return fact is not None and profile_value_is_present(fact.value)


def profile_field_shape_hint(field_type: ProfileFieldType) -> str:
    """Return the localized accepted-shape hint for a typed profile field."""
    match field_type:
        case ProfileFieldType.DATE:
            return tr("flows.manager.edit.shape.date")
        case ProfileFieldType.EMAIL:
            return tr("flows.manager.edit.shape.email")
        case ProfileFieldType.INTEGER:
            return tr("flows.manager.edit.shape.integer")
        case ProfileFieldType.DECIMAL:
            return tr("flows.manager.edit.shape.decimal")
        case ProfileFieldType.MONEY:
            return tr("flows.manager.edit.shape.money")
        case _:
            return ""


def notice_presentation(notice: Notice) -> NoticePresentation:
    """Project one resolved notice into the inert cross-entrypoint shape."""
    action = notice.action
    action_target = None
    if isinstance(action, ResolvedNoticeAction) and action.action.cli_path is not None and not action.argument_bindings:
        action_target = "aeat " + " ".join(action.action.cli_path)
    return NoticePresentation(
        severity=notice.severity.value,
        message=notice.message,
        action_target=action_target,
    )


__all__ = [
    "ProfileFieldClassification",
    "ProfileFieldPresentationV1",
    "ProfileFieldSourceClass",
    "ProfilePresentationV1",
    "build_profile_presentation",
    "notice_presentation",
    "profile_field_shape_hint",
    "profile_field_source_class",
]
