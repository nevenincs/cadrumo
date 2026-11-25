"""A name saved before the filing-text bound still opens its Modelo form from the encrypted profile."""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)
from cadrumo.application.modelo.profile_export_binding import resolve_profile_identity_producer_values
from cadrumo.application.modelo.work_form_models import ModeloFormContextFieldBlock
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.work_profile import ModeloWorkProfile
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.period import Period
from cadrumo.core.text_bounds import FILING_TEXT_CAPACITY
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from cadrumo.domain.user_profile.errors import ProfileSchemaValidationError
from cadrumo.domain.user_profile.values import UserProfileFact

from .file_flow_test_support import T0, Repos

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OVERLONG_NAME = "N" * (FILING_TEXT_CAPACITY + 1)


def test_name_saved_past_the_bound_leaves_the_header_unknown_and_the_form_open(
    repos: Repos, operation: PinnedAuthorityOperation
) -> None:
    work_repo, calculation_repo, _, verification_repo, events = repos
    bucket_id = work_repo.bucket_id
    assert bucket_id is not None
    year = operation.supported_filing_years().horizon
    snapshot = operation.reading_snapshot("130", filing_year=year, period="1T")
    record = load_test_profile_record(bucket_id)
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=year,
        period=Period.from_year_and_code(year, "1T"),
        revision_id=snapshot.revision.id,
        name="Synthetic quarterly payment",
        ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=events),
        operation=operation,
        clock=T0,
        profile=ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context()),
    )
    # Profiles saved before the bound existed hold such a name; the fact-update
    # door that stored them carries no length refusal, so it rebuilds that state.
    replace_test_profile_record(
        record.model_copy(
            update={
                "facts": (
                    *(fact for fact in record.facts if fact.path != "identity.name"),
                    UserProfileFact(path="identity.name", value=_OVERLONG_NAME),
                )
            }
        )
    )
    stored = {fact.path: fact.value for fact in load_test_profile_record(bucket_id).facts}
    assert stored["identity.name"] == _OVERLONG_NAME
    with pytest.raises(ProfileSchemaValidationError):
        resolve_profile_identity_producer_values(bucket_id=str(bucket_id), operation=operation)

    form = load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        admission=None,
        language=OutputLanguage.ES,
    ).form
    layout = operation.form_layout("130", form.registry_revision_id)
    assert layout is not None
    header = {}
    for declared_page, page in zip(layout.pages, form.pages, strict=True):
        for declared_section, section in zip(declared_page.sections, page.sections, strict=True):
            for declared, block in zip(declared_section.blocks, section.blocks, strict=True):
                if not isinstance(declared, FormContextFieldBlock):
                    continue
                assert isinstance(block, ModeloFormContextFieldBlock)
                owner = resolve_form_context_field(snapshot.revision, declared)
                if owner.producer_key is not None:
                    header[owner.producer_key] = block.value
    assert FilingProducerKey.TAXPAYER_TAX_ID in header
    assert header[FilingProducerKey.TAXPAYER_TAX_ID] is None
    assert header.get(FilingProducerKey.TAXPAYER_GIVEN_NAME) is None
    assert _OVERLONG_NAME not in {value for value in header.values() if isinstance(value, str)}
