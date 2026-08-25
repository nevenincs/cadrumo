"""Review-only workspace guard: real decrypt -> workspace -> official-action refusal.

Exercises :mod:`~application.modelo._review_package_review_only_workspace`
end to end against a real recipient-encryption round trip: build a real
review package, seal it with ``review_only=True`` (and, separately,
``review_only=False``), decrypt it with the real X25519/HKDF/AES-256-GCM
primitives (no mocks, no hand-rolled crypto), open a
:class:`~application.modelo.ReviewOnlyWorkspace` from the recovered
bytes, and assert the structural guard enforces the authority boundary: a
review-only workspace is refused for any composition requiring
filing authority, and a filing-grade (non-review-only) workspace is not.

See Also:
    :func:`~application.modelo.open_review_only_workspace`
        Projects decrypted review-package bytes into a workspace.
    :func:`~application.modelo.assert_workspace_permits_official_action`
        Authority guard that refuses review-only workspaces.
    :exc:`~application.modelo.ReviewOnlyWorkspaceAuthorityError`
        Refusal raised when review-only material is used for filing authority.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        X25519 transport primitive that stamps the ``review_only`` flag.
    :func:`~application.modelo.decrypt_review_package_for_recipient`
        Decrypt primitive that carries the flag into the recovered package.
    :func:`~application.modelo.verify_review_package`
        Manifest verifier used before opening the workspace.
    :class:`~domain.calculations.registry.CasillaObservation`
        Provenance row embedded in the review-package fixture.
    :class:`Period`
        Typed filing period used to derive the work-unit identifiers.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ....core import Period, validated_casilla_id
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    WorkUnitState,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from .._review_package import verify_review_package
from .._review_package_recipient_encryption import (
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
)
from .._review_package_recipient_registry import public_key_hex_from_raw_bytes
from .._review_package_review_only_workspace import (
    ReviewOnlyWorkspaceAuthorityError,
    assert_workspace_permits_official_action,
    open_review_only_workspace,
)
from ._review_package_bytes_support import build_package_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_review_only_workspace")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_review_only_workspace")
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-ONLY-WORKSPACE-TEST"


def _work_unit(*, bucket_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="review-only-workspace-revision",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="review-only-workspace-revision",
        name="303-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def _revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("test-review-package-review-only-workspace",),
            ),
        ),
        ledger_filing_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=None,
        filed_by=None,
        superseded_at=None,
        filing_instance_evidence=None,
        source_provenance=(),
    )


_build_package_bytes = functools.partial(
    build_package_bytes,
    work_unit_factory=_work_unit,
    revision_factory=_revision,
    draft_bytes=_DRAFT_BYTES,
)


def test_review_only_workspace_refuses_official_action(tmp_path: Path) -> None:
    """A ``review_only=True`` envelope opens a workspace that refuses to file."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="review-only-a")
    package_path = tmp_path / "review-package.zip"
    package_path.write_bytes(package_bytes)
    manifest = verify_review_package(package_path).manifest

    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )
    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=True,
    )
    decrypted = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)
    assert decrypted.review_only is True

    workspace = open_review_only_workspace(decrypted, manifest=manifest)
    assert workspace.is_read_only is True
    assert workspace.package_bytes == package_bytes

    with pytest.raises(ReviewOnlyWorkspaceAuthorityError):
        assert_workspace_permits_official_action(workspace)


def test_filing_grade_workspace_permits_official_action(tmp_path: Path) -> None:
    """A ``review_only=False`` envelope opens a workspace that DOES carry filing authority."""
    package_bytes = _build_package_bytes(tmp_path, bucket_id="review-only-b")
    package_path = tmp_path / "review-package.zip"
    package_path.write_bytes(package_bytes)
    manifest = verify_review_package(package_path).manifest

    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )
    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=False,
    )
    decrypted = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)
    assert decrypted.review_only is False

    workspace = open_review_only_workspace(decrypted, manifest=manifest)
    assert workspace.is_read_only is False

    returned_manifest = assert_workspace_permits_official_action(workspace)
    assert returned_manifest == manifest


def test_workspace_default_disposition_mirrors_envelope_flag_not_a_separate_toggle(tmp_path: Path) -> None:
    """The workspace's disposition is derived from the envelope, never independently settable.

    Real-behaviour proof that ``ReviewOnlyWorkspace`` cannot be constructed with
    a disposition that disagrees with the decrypted package it was opened
    from: :func:`open_review_only_workspace` always projects
    ``decrypted.review_only`` verbatim.
    """
    package_bytes = _build_package_bytes(tmp_path, bucket_id="review-only-c")
    package_path = tmp_path / "review-package.zip"
    package_path.write_bytes(package_bytes)
    manifest = verify_review_package(package_path).manifest

    recipient_private_key = X25519PrivateKey.generate()
    recipient_public_key_hex = public_key_hex_from_raw_bytes(
        recipient_private_key.public_key().public_bytes_raw(),
    )
    envelope = encrypt_review_package_for_recipient(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=True,
    )
    decrypted = decrypt_review_package_for_recipient(envelope, recipient_private_key=recipient_private_key)

    workspace = open_review_only_workspace(decrypted, manifest=manifest, opened_at=_NOW)
    assert workspace.review_only == decrypted.review_only
    assert workspace.opened_at == _NOW


__all__: list[str] = []
