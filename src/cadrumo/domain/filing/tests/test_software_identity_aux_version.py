"""AEAT ``Aux/VERSION`` product-identity derivation contract."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from .. import software_identity as identity_module
from ..errors import FilingExportValidationError
from ..software_identity import aeat_aux_version

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


@pytest.mark.parametrize(("package_version", "token"), (("0.5.1", "051"), ("0.6.0", "060"), ("1.10.2", "1102")))
def test_aeat_aux_version_derives_from_the_canonical_package_release(
    monkeypatch: pytest.MonkeyPatch, package_version: str, token: str
) -> None:
    monkeypatch.setattr(identity_module, "PACKAGE_VERSION", package_version)

    assert aeat_aux_version() == token


@pytest.mark.parametrize("package_version", ("0.5.1rc1", "0.5.1+local", "0.5", "0.5.1.2"))
def test_aeat_aux_version_refuses_non_release_package_versions(
    monkeypatch: pytest.MonkeyPatch, package_version: str
) -> None:
    monkeypatch.setattr(identity_module, "PACKAGE_VERSION", package_version)

    with pytest.raises(FilingExportValidationError, match="exactly three ASCII decimal components"):
        aeat_aux_version()


def test_aeat_aux_version_refuses_a_release_that_exceeds_aeat_wire_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "PACKAGE_VERSION", "0.123.4")

    with pytest.raises(FilingExportValidationError, match="4-character limit"):
        aeat_aux_version()
