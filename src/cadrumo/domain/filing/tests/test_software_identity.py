"""Contract tests for AEAT product-software filing identity."""

from __future__ import annotations

import pytest

from .. import software_identity as identity_module
from ..software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_aeat_product_software_identity_requires_exact_values_and_evidence() -> None:
    """An export header cannot reuse a filing participant or an implicit product default."""
    identity = AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:c303",
                digest="a" * 64,
            ),
        ),
    )

    assert identity.program_identifier == "C303"
    assert identity.developer_tax_id == "Y0000001S"
    assert identity.evidence[0].reference == "aeat-software-registration:c303"
    assert not {
        name
        for name in vars(identity_module)
        if name.startswith("M303ProductSoftware") or name == "M303ProgramIdentifier"
    }

    with pytest.raises(ValueError, match="program_identifier"):
        AeatProductSoftwareIdentity(
            program_identifier="303",
            developer_tax_id="Y0000001S",
            evidence=identity.evidence,
        )
    with pytest.raises(ValueError, match="at least 1 item"):
        AeatProductSoftwareIdentity(
            program_identifier="C303",
            developer_tax_id="Y0000001S",
            evidence=(),
        )


def test_product_identity_module_is_not_a_compatibility_surface() -> None:
    """The displaced core module does not forward the filing-domain contract."""
    from ....core import product_identity

    assert (
        not {
            "AeatProgramIdentifier",
            "AeatProductSoftwareEvidence",
            "AeatProductSoftwareIdentity",
        }
        & vars(product_identity).keys()
    )
