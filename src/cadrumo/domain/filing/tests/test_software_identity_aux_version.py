"""AEAT ``Aux/VERSION`` product-identity derivation contract."""

from __future__ import annotations

import pytest

from .. import software_identity as identity_module
from ..errors import FilingExportValidationError
from ..software_identity import aeat_aux_version

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_aeat_aux_version_derives_from_the_canonical_package_release() -> None:
    assert aeat_aux_version() == "051"


@pytest.mark.parametrize("package_version", ("0.5.1rc1", "0.5.1+local", "0.5", "0.5.1.2"))
def test_aeat_aux_version_refuses_non_release_package_versions(monkeypatch: pytest.MonkeyPatch, package_version: str) -> None:
    monkeypatch.setattr(identity_module, "PACKAGE_VERSION", package_version)

    with pytest.raises(FilingExportValidationError, match="exactly three ASCII decimal components"):
        aeat_aux_version()


def test_aeat_aux_version_refuses_a_release_that_exceeds_aeat_wire_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "PACKAGE_VERSION", "0.123.4")

    with pytest.raises(FilingExportValidationError, match="four-character limit"):
        aeat_aux_version()
