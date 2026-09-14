"""The application approval-basis contract refuses malformed metadata.

``ModeloApprovalBasis`` holds eight stale-detection fingerprints and a version.
Every fingerprint used to be an unconstrained ``str``, so a blank, short,
over-long, uppercase or non-hex value persisted and read back as if it were a
content-addressed claim.  The application contract deliberately distinguishes
the draft's 16-character content address from the seven SHA-256 hex-64
upstream digests.  Encrypted runtime grounding and checksum-reload behavior
are covered at the persistence adapter seam.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.domain.filing.schema import APPROVAL_BASIS_VERSION, ModeloApprovalBasis

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEX64 = "a" * 64

_DIGEST_FIELDS = (
    "draft_review_fingerprint",
    "transaction_catalogue_fingerprint",
    "invoice_catalogue_fingerprint",
    "prior_filing_observations_fingerprint",
    "profile_activity_fingerprint",
    "category_profiles_fingerprint",
    "schema_formula_fingerprint",
)


def _valid_basis(**overrides: object) -> ModeloApprovalBasis:
    fields: dict[str, object] = {
        "draft_payload_fingerprint": "bc92044f18e612b9",
        "draft_review_fingerprint": _HEX64,
        "transaction_catalogue_fingerprint": _HEX64,
        "invoice_catalogue_fingerprint": _HEX64,
        "prior_filing_observations_fingerprint": _HEX64,
        "profile_activity_fingerprint": _HEX64,
        "category_profiles_fingerprint": _HEX64,
        "schema_formula_fingerprint": _HEX64,
    }
    fields.update(overrides)
    return ModeloApprovalBasis.model_validate(fields)


def test_valid_basis_constructs() -> None:
    """Positive control: the coherent shape is accepted, so refusals below discriminate."""
    basis = _valid_basis()

    assert basis.version == APPROVAL_BASIS_VERSION
    assert basis.schema_formula_fingerprint == _HEX64


@pytest.mark.parametrize("field", _DIGEST_FIELDS)
@pytest.mark.parametrize("malformed", ["", "a" * 63, "a" * 65, "A" * 64, "z" * 64, " " + "a" * 63])
def test_basis_refuses_a_malformed_digest_fingerprint(field: str, malformed: str) -> None:
    """A stale-detection digest must be a real content-addressed claim."""
    with pytest.raises(ValidationError):
        _valid_basis(**{field: malformed})


@pytest.mark.parametrize("malformed", ["", "bad", "BC92044F18E612B9", "z" * 16, "a" * 15, "a" * 17])
def test_basis_refuses_a_malformed_draft_content_address(malformed: str) -> None:
    """``draft_payload_fingerprint`` is the draft's own 16-hex content address."""
    with pytest.raises(ValidationError):
        _valid_basis(draft_payload_fingerprint=malformed)


@pytest.mark.parametrize("version", ["bogus-v0", "", "review-basis-v3"])
def test_basis_refuses_an_unknown_version(version: str) -> None:
    """The version names the basis layout this code computes, not free text."""
    with pytest.raises(ValidationError):
        _valid_basis(version=version)
