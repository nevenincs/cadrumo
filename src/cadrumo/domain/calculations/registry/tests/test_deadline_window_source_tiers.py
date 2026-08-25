"""Deadline-window evidence-tier validation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.validate import RegistryValidator
from ._registry_schema_support import _committed_registry, _revision, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validator_rejects_deadline_window_legal_ref_without_legal_authority() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    legal = dict(catalogues.legal)
    legal_ref = window.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline window modelo-130-2024-1t legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_deadline_window_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    mutated_window = window.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
    mutated_revision = revision.model_copy(
        update={"deadline_windows": (mutated_window, *revision.deadline_windows[1:])},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline window modelo-130-2024-1t requires official_source_guidance source evidence",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )


def test_validator_rejects_deadline_condition_legal_ref_without_legal_authority() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    condition = window.applicability_conditions[0]
    legal = dict(catalogues.legal)
    legal_ref = condition.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline condition for modelo-130-2024-1t legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_validator_rejects_deadline_condition_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    window = revision.deadline_windows[0]
    condition = window.applicability_conditions[0]
    mutated_condition = condition.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
    mutated_window = window.model_copy(update={"applicability_conditions": (mutated_condition,)})
    mutated_revision = revision.model_copy(
        update={"deadline_windows": (mutated_window, *revision.deadline_windows[1:])},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"deadline condition for modelo-130-2024-1t requires official_source_guidance source evidence",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )
