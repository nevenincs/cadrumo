"""New-declaration choices from the pinned registry's supported legal windows.

A revision that declares filing schedules files each period only under the
schedule the taxpayer's own facts select, such as a monthly or a quarterly
family. The choices keep only the periods of the family the profile selects;
while a fact deciding the family is unanswered, every period it decides stays
offered and names that fact, so the choice is neither guessed nor hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.errors import NoRevisionForPeriodError
from ...domain.calculations.registry.schedules import (
    applicable_filing_schedules,
    unresolved_schedule_deciding_fields,
)
from ...domain.calculations.registry.temporal import select_revision_metadata
from ...domain.deadlines.errors import ProfileError
from ...domain.user_profile.errors import UserProfileValidationError
from ..user_profile.projections import projection_for_taxpayer

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.temporal import RevisionSelectionMetadata
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.user_profile.schema import ProfileSchemaDefinition
    from ...domain.user_profile.values import UserProfileRecord


@dataclass(frozen=True, slots=True)
class DeclarationTarget:
    """An admitted natural filing coordinate; the picker never accepts arbitrary years.

    ``profile_requirements`` holds the dotted profile paths of the unanswered
    facts that decide whether this period's filing schedule applies; empty when
    the profile already decides it or the revision declares no schedule.
    """

    modelo: str
    period: Period
    profile_requirements: tuple[str, ...] = ()


def declaration_targets(
    operation: PinnedAuthorityOperation, *, profile: UserProfileRecord | None
) -> tuple[DeclarationTarget, ...]:
    """Every modelo period the registry envelope admits, narrowed to the filing family the profile selects.

    A modelo's periods are those its editions declare filing windows for. Each is offered in every
    envelope year the resolver answers, a year without its own edition projected from the nearest
    authored one; a year before the modelo's declared inception is refused there and not offered.

    With ``profile``, the selected revision's filing schedules narrow its periods to the family the
    profile selects. A profile the taxpayer projection refuses, or no profile, decides no family,
    and every admitted period is offered.
    """
    support = operation.supported_filing_years()
    schema = operation.profile_schema()
    taxpayer = None if profile is None else _taxpayer(profile, schema)
    targets: list[DeclarationTarget] = []
    for modelo in sorted(operation.modelo_ids()):
        directory = operation.modelo_directory(modelo)
        codes = sorted(
            {str(window.period.code) for revision in directory.revisions for window in revision.deadline_windows}
        )
        for year in support.years:
            for code in codes:
                period = Period.from_year_and_code(year, code)
                try:
                    revision = select_revision_metadata(
                        directory, filing_year=year, period=period.registry_token, support=support
                    )
                except NoRevisionForPeriodError:
                    continue
                requirements = (
                    () if taxpayer is None else _schedule_requirements(revision, taxpayer, period=period, schema=schema)
                )
                if requirements is not None:
                    targets.append(DeclarationTarget(modelo, period, requirements))
    return tuple(targets)


def _taxpayer(profile: UserProfileRecord, schema: ProfileSchemaDefinition) -> TaxpayerProfile | None:
    try:
        return projection_for_taxpayer(profile, tax_id_default="00000000T", schema=schema)
    except (ProfileError, UserProfileValidationError):
        return None


def _schedule_requirements(
    revision: RevisionSelectionMetadata,
    taxpayer: TaxpayerProfile,
    *,
    period: Period,
    schema: ProfileSchemaDefinition,
) -> tuple[str, ...] | None:
    """Say whether ``period`` is offered under the profile's schedules, and what it still needs answered.

    ``None`` drops the period: every schedule filing it fails on an answered
    fact while the profile selects another family of the same revision. A
    revision whose schedules the profile selects none of, on answered facts,
    is not narrowed here; whether that modelo applies at all is the calendar's
    and the work gate's to say.
    """
    if not revision.filing_schedules:
        return ()
    token = period.registry_token
    if applicable_filing_schedules(revision, taxpayer, period=token):
        return ()
    unresolved = unresolved_schedule_deciding_fields(revision, taxpayer, period=token)
    if unresolved:
        paths = (schema.schedule_predicate_path(predicate) for predicate in unresolved)
        return tuple(dict.fromkeys(path for path in paths if path is not None))
    return None if applicable_filing_schedules(revision, taxpayer) else ()
