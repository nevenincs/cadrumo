"""Verification-expectation source-tier validation."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.validate import RegistryValidator

from .....core.resources import bundled_path
from ._registry_schema_support import _committed_registry, _revision, _with_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validator_rejects_verification_expectation_without_official_guidance_source() -> None:
    modelo, catalogues = _committed_registry()
    revision = _revision(modelo)
    expectation = revision.verification_expectations[0]
    mutated_expectation = expectation.model_copy(update={"source_refs": ("aeat-dr-130-2019-v12",)})
    mutated_revision = revision.model_copy(
        update={"verification_expectations": (mutated_expectation, *revision.verification_expectations[1:])},
    )

    with pytest.raises(
        RegistryValidationError,
        match=(
            r"verification expectation modelo-130-calculation-verification "
            r"requires official_source_guidance source evidence"
        ),
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(
            _with_revision(modelo, mutated_revision),
        )
