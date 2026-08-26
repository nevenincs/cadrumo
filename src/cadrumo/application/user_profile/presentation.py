"""The settled profile presentation contract: what to show, and why.

This is the typed projection behind the guided `Overview -> Get data ->
Required -> Review -> Ready` interface (`2026-08-11-tui-interface-adr` D6),
distinct from :mod:`overview`'s schema-completeness projection: where
`overview` answers "what does the record hold and is it masked", this module
answers the presentation question D6 poses -- classification (is this field
required, conditionally required with its applicability still unassessed,
optional, or not applicable), source class, and whether it currently blocks
filing readiness.

Every classification is read from application-owned facts already computed
elsewhere -- the schema's own `required` declaration, the conditional
completeness rules in :mod:`completeness`, and the schema-declared
`provenance.source` token on the effective fact -- never guessed from locale
or presentation state, per D6's explicit instruction. A conditionally
required field whose trigger fact is itself unanswered is `NEEDS_APPLICABILITY`,
never silently folded into `NOT_APPLICABLE`: that collapse is exactly the
anti-pattern D6 names ("Unknown applicability is displayed as unassessed,
never silently treated as ... not applicable").

Scope for this pass: conditional-requirement triggers are resolved only for
the known named trigger paths in :data:`_CONDITIONAL_TRIGGERS`
(`auth.clave_movil_route`, the legal-entity fields, and the IRNR
fiscal-representative fields); the IVA-regime conditional block and every
repeatable section are presented as `OPTIONAL` rather than assessed for
conditional applicability, since their trigger conditions are multi-field and
out of this Step's bounded scope. `Review`'s unresolved-proposal/conflict row
is not built here: it belongs to whichever registered acquisition/reconciliation
operation proposes the divergence (censal review, previous-filing evidence),
not to this static per-field projection.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ...core.identity import ProfileId
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.values import UserProfileRecord
from .completeness import (
    AUTH_PROVIDER_PATH,
    CLAVE_MOVIL_ROUTE_PATH,
    ENTITY_TYPE_PATH,
    FISCAL_RESIDENCY_PATH,
    LEGAL_ENTITY_FORM_PATH,
    LEGAL_NAME_PATH,
    REPRESENTANTE_FISCAL_NIF_PATH,
    REPRESENTANTE_FISCAL_NOMBRE_PATH,
    conditional_profile_required_paths,
    profile_value_is_present,
)
from .projections import EffectiveFact, record_to_effective_facts

_PRESENTATION_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)

#: Every conditionally required path this Step resolves applicability for,
#: mapped to the trigger path whose answer decides whether it applies at all.
_CONDITIONAL_TRIGGERS: dict[str, str] = {
    CLAVE_MOVIL_ROUTE_PATH: AUTH_PROVIDER_PATH,
    LEGAL_ENTITY_FORM_PATH: ENTITY_TYPE_PATH,
    LEGAL_NAME_PATH: ENTITY_TYPE_PATH,
    REPRESENTANTE_FISCAL_NIF_PATH: FISCAL_RESIDENCY_PATH,
    REPRESENTANTE_FISCAL_NOMBRE_PATH: FISCAL_RESIDENCY_PATH,
}


class ProfileFieldSourceClass(StrEnum):
    """Coarse origin class for a profile field's current value (D6's source table).

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
    """Classify one schema-declared provenance token into D6's coarse source class."""
    try:
        return _SOURCE_TOKEN_CLASSES[source_token]
    except KeyError:
        raise ValueError(f"unmapped provenance source token: {source_token!r}") from None


class ProfileFieldClassification(StrEnum):
    """D6's classification table, minus the two rows this module never emits.

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
        if (self.classification is ProfileFieldClassification.NEEDS_APPLICABILITY) != (not self.applicability_assessed):
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


def build_profile_presentation(record: UserProfileRecord) -> ProfilePresentationV1:
    """Build the settled presentation projection from one profile record.

    Reads only application-owned facts: the schema's own `required`
    declaration, :func:`completeness.conditional_profile_required_paths`,
    and the effective fact's own declared source -- never infers a
    classification from a value's shape or a locale string.
    """
    schema = load_user_profile_schema()
    effective = record_to_effective_facts(record)
    values = {path: fact.value for path, fact in effective.items()}
    conditional_required = frozenset(conditional_profile_required_paths(values))

    rows: list[ProfileFieldPresentationV1] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            fact = effective.get(path)
            present = fact is not None and profile_value_is_present(fact.value)
            source = profile_field_source_class(fact.source) if present and fact is not None else None
            trigger = _CONDITIONAL_TRIGGERS.get(path)

            if field.required:
                classification = _required_classification(present)
                applicability_assessed = True
            elif trigger is not None and not _path_answered(effective, trigger):
                classification = ProfileFieldClassification.NEEDS_APPLICABILITY
                applicability_assessed = False
            elif path in conditional_required:
                classification = _required_classification(present)
                applicability_assessed = True
            elif trigger is not None:
                classification = ProfileFieldClassification.NOT_APPLICABLE
                applicability_assessed = True
            else:
                classification = ProfileFieldClassification.OPTIONAL
                applicability_assessed = True

            rows.append(
                ProfileFieldPresentationV1(
                    path=path,
                    classification=classification,
                    present=present,
                    applicability_assessed=applicability_assessed,
                    source=source,
                    blocks_ready=classification in _BLOCKING_CLASSIFICATIONS,
                )
            )
    return ProfilePresentationV1(profile_id=record.profile_id, fields=tuple(rows))


def _required_classification(present: bool) -> ProfileFieldClassification:
    return (
        ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT
        if present
        else ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING
    )


def _path_answered(effective: dict[str, EffectiveFact], path: str) -> bool:
    fact = effective.get(path)
    return fact is not None and profile_value_is_present(fact.value)


__all__ = [
    "ProfileFieldClassification",
    "ProfileFieldPresentationV1",
    "ProfileFieldSourceClass",
    "ProfilePresentationV1",
    "build_profile_presentation",
    "profile_field_source_class",
]
