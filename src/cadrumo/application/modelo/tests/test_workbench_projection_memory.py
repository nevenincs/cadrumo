"""Projection reuse has exact typed values and live schemas, not coordinate-only identity."""

from collections.abc import Hashable
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from importlib.resources import files
from types import MappingProxyType
from typing import override
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic_core import TzInfo

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...workbench_capture_memory import WorkbenchCaptureMemory
from ..work_form_declaration_facts import ModeloFormExport
from ..work_form_findings import ModeloFormIssue
from ..work_form_service import ModeloWorkFormLoadV1, modelo_work_form_load
from ..workbench_projection import PublicModeloFormField, PublicModeloWorkFormLoadV1
from ..workbench_projection_memory import (
    FormProjectionContext,
    form_identities,
    form_projection_is_immutable,
)
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


class _UnreviewedZone(tzinfo):
    @override
    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(0)

    @override
    def dst(self, dt: datetime | None) -> None:
        return None

    @override
    def tzname(self, dt: datetime | None) -> str:
        return "test"


@pytest.fixture
def small_load(authority_operation: PinnedAuthorityOperation) -> ModeloWorkFormLoadV1:
    """A real, small form load; the first identity taken in a process settles deferred schemas."""
    form = built_form(authority_operation, "130", filing_year_envelope().horizon, "1T")
    load = modelo_work_form_load(form, verified=False, filed=False)
    form_identities(load, PublicModeloWorkFormLoadV1)
    return load


def _form_identity(load: ModeloWorkFormLoadV1) -> Hashable | None:
    identities = form_identities(load, PublicModeloWorkFormLoadV1)
    return None if identities is None else identities.form


def _with_export(load: ModeloWorkFormLoadV1, export: ModeloFormExport) -> ModeloWorkFormLoadV1:
    return load.model_copy(update={"form": load.form.model_copy(update={"last_export": export})})


def _with_finding(load: ModeloWorkFormLoadV1, finding: ModeloVerificationFinding) -> ModeloWorkFormLoadV1:
    issue = ModeloFormIssue(finding=_finding(1)).model_copy(update={"finding": finding})
    return load.model_copy(update={"form": load.form.model_copy(update={"issues": (issue,)})})


def test_a_json_restored_export_keeps_its_fixed_offset_timezone_eligible(small_load: ModeloWorkFormLoadV1) -> None:
    export = ModeloFormExport(exported_at=datetime.now(UTC), calculation_revision_id="synthetic-revision", current=True)
    restored = ModeloFormExport.model_validate_json(export.model_dump_json())
    assert type(restored.exported_at.tzinfo) is TzInfo
    assert _form_identity(_with_export(small_load, restored)) is not None
    assert form_projection_is_immutable(restored, PublicModeloWorkFormLoadV1)


def test_timezone_identity_distinguishes_same_timestamp_representations(small_load: ModeloWorkFormLoadV1) -> None:
    export = ModeloFormExport(exported_at=datetime.now(UTC), calculation_revision_id="synthetic-revision", current=True)
    restored = ModeloFormExport.model_validate_json(export.model_dump_json())
    variants = (
        export,
        restored,
        export.model_copy(update={"exported_at": export.exported_at.replace(tzinfo=ZoneInfo("UTC"))}),
        export.model_copy(update={"exported_at": export.exported_at.replace(tzinfo=ZoneInfo("Etc/UTC"))}),
        export.model_copy(
            update={"exported_at": export.exported_at.replace(tzinfo=timezone(timedelta(0), "synthetic-offset"))}
        ),
    )
    assert len({item.exported_at.isoformat() for item in variants}) == 1
    identities = {_form_identity(_with_export(small_load, item)) for item in variants}
    assert None not in identities
    assert len(identities) == len(variants), "timezone class and zone key remain distinct even at the same offset"


def test_unreviewed_and_anonymous_timezones_decline_reuse(small_load: ModeloWorkFormLoadV1) -> None:
    restored = ModeloFormExport(
        exported_at=datetime.now(UTC), calculation_revision_id="synthetic-revision", current=True
    )
    unproved = restored.model_copy(update={"exported_at": restored.exported_at.replace(tzinfo=_UnreviewedZone())})
    assert _form_identity(_with_export(small_load, unproved)) is None
    assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)
    with files("tzdata.zoneinfo").joinpath("UTC").open("rb") as zone_file:
        anonymous = ZoneInfo.from_file(zone_file)
    unproved = restored.model_copy(update={"exported_at": restored.exported_at.replace(tzinfo=anonymous)})
    assert _form_identity(_with_export(small_load, unproved)) is None
    assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)


def _finding(value: str | int | bool | Decimal) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="test.projection.finding",
        legal_refs=("test:projection",),
        message_facts={"amount": value},
    )


def test_value_identity_preserves_types_decimal_scale_and_declines_mutable_values(
    small_load: ModeloWorkFormLoadV1,
) -> None:
    values = (1, True, "1", Decimal("1"), Decimal("1.0"), Decimal("-0"), Decimal("0"))
    identities = {_form_identity(_with_finding(small_load, _finding(value))) for value in values}
    assert None not in identities
    assert len(identities) == len(values)
    finding = _finding(Decimal("1"))
    for value in (
        [],
        {},
        set(),
        object(),
        MappingProxyType({"amount": Decimal("1")}),
        datetime.now(UTC).replace(tzinfo=_UnreviewedZone()),
    ):
        unproved = finding.model_copy(update={"message_locale_key": value})
        assert _form_identity(_with_finding(small_load, unproved)) is None
        assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)


def test_only_owner_frozen_facts_are_enrolled_and_the_key_does_not_alias_their_backing_map(
    small_load: ModeloWorkFormLoadV1,
) -> None:
    backing = {"amount": Decimal("1.00")}
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="test.projection.finding",
        legal_refs=("test:projection",),
        message_facts=backing,
    )
    original = _form_identity(_with_finding(small_load, finding))
    assert original is not None
    assert form_projection_is_immutable(finding, PublicModeloWorkFormLoadV1)
    backing["amount"] = Decimal("2.00")
    assert _form_identity(_with_finding(small_load, finding)) == original
    alias = finding.model_copy(update={"message_facts": MappingProxyType(backing)})
    before = _form_identity(_with_finding(small_load, alias))
    assert before is not None
    backing["amount"] = Decimal("3.00")
    assert _form_identity(_with_finding(small_load, alias)) != before
    mutable = finding.model_copy(update={"message_facts": backing})
    assert _form_identity(_with_finding(small_load, mutable)) is None
    assert not form_projection_is_immutable(mutable, PublicModeloWorkFormLoadV1)


def test_every_admission_authority_language_and_profile_coordinate_invalidates_the_slot() -> None:
    context = FormProjectionContext(
        UUID(int=1), "work", "work-digest", "head-digest", "head", "generation", OutputLanguage.EN
    )
    variants = (
        replace(context, profile_id=UUID(int=2)),
        replace(context, work_unit_id="other-work"),
        replace(context, work_unit_record_digest="new-work-digest"),
        replace(context, calculation_head_digest="new-head-digest"),
        replace(context, calculation_revision_id="new-head"),
        replace(context, logical_generation="new-generation"),
        replace(context, language=OutputLanguage.ES),
    )
    slot = WorkbenchCaptureMemory().form_projection
    builds: list[int] = []
    for variant in variants:
        slot.reuse((context, "same-form"), lambda: builds.append(1))
        before = len(builds)
        slot.reuse((context, "same-form"), lambda: builds.append(1))
        assert len(builds) == before
        slot.reuse((variant, "same-form"), lambda: builds.append(1))
        assert len(builds) == before + 1


def test_real_form_identity_changes_for_lifecycle_same_coordinate_copy_and_live_schema(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    form = built_form(authority_operation, "100", newest_authored_edition("100"), "0A")
    load = modelo_work_form_load(form, verified=False, filed=False)
    original = _form_identity(load)
    assert original is not None
    assert original == _form_identity(load.model_copy(deep=True))
    assert original != _form_identity(load.model_copy(update={"verified": True}))
    assert original != _form_identity(load.model_copy(update={"filed": True}))
    assert original != _form_identity(load.model_copy(update={"form": form.model_copy(update={"blocks": ()})}))
    assert not form_projection_is_immutable(load.model_copy(update={"form": []}), PublicModeloWorkFormLoadV1)

    class UnreviewedLoad(ModeloWorkFormLoadV1):
        pass

    assert _form_identity(UnreviewedLoad.model_validate(load.model_dump())) is None
    PublicModeloFormField.model_rebuild(force=True)
    assert original != _form_identity(load)
