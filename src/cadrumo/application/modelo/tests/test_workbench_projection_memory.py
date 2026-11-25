"""Projection reuse has exact typed values and live schemas, not coordinate-only identity."""

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
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...workbench_capture_memory import WorkbenchCaptureMemory
from ..work_form_declaration_facts import ModeloFormExport
from ..work_form_service import ModeloWorkFormLoadV1, modelo_work_form_load
from ..workbench_projection import PublicModeloFormField, PublicModeloWorkFormLoadV1
from ..workbench_projection_memory import (
    FormProjectionContext,
    form_projection_identity,
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


def test_a_json_restored_export_keeps_its_fixed_offset_timezone_eligible() -> None:
    export = ModeloFormExport(exported_at=datetime.now(UTC), calculation_revision_id="synthetic-revision", current=True)
    restored = ModeloFormExport.model_validate_json(export.model_dump_json())
    assert type(restored.exported_at.tzinfo) is TzInfo
    assert form_projection_identity(restored, PublicModeloWorkFormLoadV1) is not None
    assert form_projection_is_immutable(restored, PublicModeloWorkFormLoadV1)


def test_timezone_identity_distinguishes_same_timestamp_representations() -> None:
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
    identities = {form_projection_identity(item, PublicModeloWorkFormLoadV1) for item in variants}
    assert None not in identities
    assert len(identities) == len(variants), "timezone class and zone key remain distinct even at the same offset"


def test_unreviewed_and_anonymous_timezones_decline_reuse() -> None:
    restored = ModeloFormExport(
        exported_at=datetime.now(UTC), calculation_revision_id="synthetic-revision", current=True
    )
    unproved = restored.model_copy(update={"exported_at": restored.exported_at.replace(tzinfo=_UnreviewedZone())})
    assert form_projection_identity(unproved, PublicModeloWorkFormLoadV1) is None
    assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)
    with files("tzdata.zoneinfo").joinpath("UTC").open("rb") as zone_file:
        anonymous = ZoneInfo.from_file(zone_file)
    unproved = restored.model_copy(update={"exported_at": restored.exported_at.replace(tzinfo=anonymous)})
    assert form_projection_identity(unproved, PublicModeloWorkFormLoadV1) is None
    assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)


def _finding(value: str | int | bool | Decimal) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="test.projection.finding",
        legal_refs=("test:projection",),
        message_facts={"amount": value},
    )


def test_value_identity_preserves_types_decimal_scale_and_declines_mutable_values() -> None:
    values = (1, True, "1", Decimal("1"), Decimal("1.0"), Decimal("-0"), Decimal("0"))
    identities = {form_projection_identity(_finding(value), PublicModeloWorkFormLoadV1) for value in values}
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
        assert form_projection_identity(unproved, PublicModeloWorkFormLoadV1) is None
        assert not form_projection_is_immutable(unproved, PublicModeloWorkFormLoadV1)


def test_only_owner_frozen_facts_are_enrolled_and_the_key_does_not_alias_their_backing_map() -> None:
    backing = {"amount": Decimal("1.00")}
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="test.projection.finding",
        legal_refs=("test:projection",),
        message_facts=backing,
    )
    original = form_projection_identity(finding, PublicModeloWorkFormLoadV1)
    assert original is not None
    assert form_projection_is_immutable(finding, PublicModeloWorkFormLoadV1)
    backing["amount"] = Decimal("2.00")
    assert form_projection_identity(finding, PublicModeloWorkFormLoadV1) == original
    alias = finding.model_copy(update={"message_facts": MappingProxyType(backing)})
    before = form_projection_identity(alias, PublicModeloWorkFormLoadV1)
    assert before is not None
    backing["amount"] = Decimal("3.00")
    assert form_projection_identity(alias, PublicModeloWorkFormLoadV1) != before
    mutable = finding.model_copy(update={"message_facts": backing})
    assert form_projection_identity(mutable, PublicModeloWorkFormLoadV1) is None
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
    original = form_projection_identity(load, PublicModeloWorkFormLoadV1)
    assert original is not None
    assert original == form_projection_identity(load.model_copy(deep=True), PublicModeloWorkFormLoadV1)
    assert original != form_projection_identity(load.model_copy(update={"verified": True}), PublicModeloWorkFormLoadV1)
    assert original != form_projection_identity(load.model_copy(update={"filed": True}), PublicModeloWorkFormLoadV1)
    assert original != form_projection_identity(
        load.model_copy(update={"form": form.model_copy(update={"blocks": ()})}), PublicModeloWorkFormLoadV1
    )
    assert form_projection_identity(load.model_copy(update={"form": []}), PublicModeloWorkFormLoadV1) is None

    class UnreviewedLoad(ModeloWorkFormLoadV1):
        pass

    assert (
        form_projection_identity(UnreviewedLoad.model_validate(load.model_dump()), PublicModeloWorkFormLoadV1) is None
    )
    PublicModeloFormField.model_rebuild(force=True)
    assert original != form_projection_identity(load, PublicModeloWorkFormLoadV1)
