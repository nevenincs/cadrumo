"""Review-only workspace mode for a decrypted, recipient-encrypted review package.

Distinct from the per-package ``review_only`` flag carried by
:class:`~application.modelo.RecipientEncryptedPackage` (which only tags
the sealed envelope's disposition), this module materialises a recovered
package into a typed, read-only workspace view and enforces -- structurally,
not by convention -- that a review-only workspace can never be treated as
filing authority.

A :class:`ReviewOnlyWorkspace` is opened from a
:class:`~application.modelo.RecipientDecryptedPackage` (the output of
:func:`~application.modelo.decrypt_review_package_for_recipient`) plus
the package's recovered :class:`~application.modelo.ReviewPackageManifest`
descriptor. It is the accountant/gestor-side counterpart of
``no-silent-under-declaration``: exactly as a locally
persisted filed observation must never be mistaken for official AEAT
evidence, a review-only workspace must never be mistaken for a mandate to
file, export, or otherwise act on the underlying revision with authority.

The guard is a hard, always-fail assertion
(:func:`assert_workspace_permits_official_action`) rather than an advisory:
unlike ``no-silent-under-declaration``'s advisory-vs-blocking distinction (a
legitimately ambiguous economic state), "does this workspace carry filing
authority" is a closed binary fact carried on the envelope at encryption
time -- there is no legitimate case where a review-only workspace should be
allowed to file. Any composition (a future countersign-attach-to-journal
flow, a future decrypt-then-file verb) that touches a
:class:`ReviewOnlyWorkspace` MUST call the assertion before treating the
package as filing-grade.

See Also:
    :mod:`~application.modelo._review_package_recipient_encryption`
        Produces the :class:`~application.modelo.RecipientDecryptedPackage`
        this module wraps, and defines the ``review_only`` disposition flag.
    :mod:`~application.modelo.review_package`
        Defines :class:`~application.modelo.ReviewPackageManifest`, the
        descriptor recovered alongside the decrypted package bytes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as _utc_now
from .review_package import ReviewPackageManifest
from .review_package_recipient_encryption import RecipientDecryptedPackage


class ReviewOnlyWorkspaceError(CadrumoError):
    """Base error for review-only workspace failures."""


class ReviewOnlyWorkspaceAuthorityError(ReviewOnlyWorkspaceError):
    """Raised when a review-only workspace is used for an action requiring filing authority.

    A review-only workspace's contents may be read and verified, but MUST
    NEVER be treated as evidence that the underlying revision has been (or
    may be) filed, exported as an official artefact, or otherwise acted on
    with authority. This error is the structural refusal that enforces that
    invariant; it is never advisory.
    """


class ReviewOnlyWorkspace(BaseModel):
    """A read-only materialisation of a decrypted review package.

    Wraps the recovered plaintext archive bytes (``package_bytes``) and the
    package's descriptor (``manifest``) behind a workspace record that
    carries its own disposition (``review_only``) independently of, but
    mirroring, the envelope flag it was opened from -- so a caller that only
    has the workspace record (and not the original envelope) can still
    enforce the authority boundary without re-threading the envelope's flag
    through every downstream call.

    ``opened_at`` records when this workspace view was materialised (never
    persisted state by itself -- opening a workspace is a pure in-memory
    projection, not a write to any repository; a caller that wants an audit
    trail of the open composes
    :func:`~application.modelo.emit_collab_review_only_workspace_opened_event`
    around this constructor).
    """

    model_config = _STRICT_FROZEN

    manifest: ReviewPackageManifest
    package_bytes: bytes = Field(min_length=1)
    review_only: bool
    opened_at: datetime

    @property
    def is_read_only(self) -> bool:
        """Return ``True`` iff this workspace carries no filing authority.

        A workspace is read-only whenever its envelope was sealed
        ``review_only=True`` -- there is no separate mutable-vs-immutable
        toggle; the disposition is fixed at encryption time and carried
        verbatim through decryption and workspace materialisation.
        """
        return self.review_only


def open_review_only_workspace(
    decrypted: RecipientDecryptedPackage,
    *,
    manifest: ReviewPackageManifest,
    opened_at: datetime | None = None,
) -> ReviewOnlyWorkspace:
    """Materialise a decrypted package into a read-only :class:`ReviewOnlyWorkspace`.

    Args:
        decrypted: The :class:`~application.modelo.RecipientDecryptedPackage`
            returned by :func:`~application.modelo.decrypt_review_package_for_recipient`.
        manifest: The package's recovered :class:`~application.modelo.ReviewPackageManifest`
            descriptor (see :func:`~application.modelo.verify_review_package`
            / :func:`~application.modelo.assert_review_package_verifies`,
            which the caller should run against the recovered archive bytes
            before opening a workspace, exactly as any other review-package
            consumer does).
        opened_at: Optional override for the workspace's ``opened_at``
            timestamp (tests only); defaults to the current UTC time.

    Returns:
        A :class:`ReviewOnlyWorkspace` carrying the decrypted bytes, the
        descriptor, and the envelope's ``review_only`` disposition.
    """
    return ReviewOnlyWorkspace(
        manifest=manifest,
        package_bytes=decrypted.package_bytes,
        review_only=decrypted.review_only,
        opened_at=opened_at or _utc_now(),
    )


def assert_workspace_permits_official_action(workspace: ReviewOnlyWorkspace) -> ReviewPackageManifest:
    """Assert ``workspace`` carries filing authority; return its manifest on success.

    This is the structural guard every filing/export/official-action
    composition over a :class:`ReviewOnlyWorkspace` MUST call before treating
    the workspace's contents as evidence the underlying revision has been or
    may be filed. It is a hard refusal, never an advisory: a review-only
    workspace's disposition is a closed fact carried on the sealed envelope,
    not a judgment call with legitimate exceptions.

    Raises:
        ReviewOnlyWorkspaceAuthorityError: If ``workspace.review_only`` is
            ``True``.
    """
    if workspace.review_only:
        raise ReviewOnlyWorkspaceAuthorityError(
            translated_message="application.modelo.errors.review_only_workspace_no_authority",
            context={
                "calculation_revision_id": workspace.manifest.calculation_revision_id,
                "bucket_id": workspace.manifest.bucket_id,
            },
        )
    return workspace.manifest


__all__ = [
    "ReviewOnlyWorkspace",
    "ReviewOnlyWorkspaceAuthorityError",
    "ReviewOnlyWorkspaceError",
    "assert_workspace_permits_official_action",
    "open_review_only_workspace",
]
