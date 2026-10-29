"""Verify native desktop window image and runtime ancestry."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from cadrumo_client.contracts.contracts import ByteChannel, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import ProfileLogin
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor, NativeServiceVerifier
from cadrumo_client.contracts.transport import ConnectionContext

if TYPE_CHECKING:
    from ..adapters.service_verification import NativeProcessIdentity


_MAXIMUM_ANCESTRY_DEPTH = 32


# The argument that starts the desktop image as one of its roles; the window has none.
_ROLE_ARGUMENT = "--role"


class DesktopImageMatcher(Protocol):
    """The one verifier question a desktop window's admission asks."""

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        """Whether ``image_path`` is the package's ``descriptor_path`` image with ``image_digest``."""
        ...


def _desktop_image_listed(verifier: DesktopImageMatcher, image: str, descriptor: InstalledServiceDescriptor) -> bool:
    return any(
        verifier.installed_parent_image_matches(image, item.launch_image, item.image_digest)
        for item in descriptor.allowed_parent_images
    )


def desktop_window_peer(
    verifier: DesktopImageMatcher,
    context: ConnectionContext,
    channel_peer: Peer,
    descriptor: InstalledServiceDescriptor,
) -> bool:
    """Whether the peer is the installed desktop image itself, connected from its window.

    The desktop window holds its own runtime connection. It is admitted as the
    desktop holder on the same evidence its hold child's parent was: the peer
    runs one of the images the package names as a desktop, by exact bytes, and
    was not started by this runtime. A role argument makes the image one of the
    runtime's own children, never the window.
    """
    from pathlib import Path

    from ..adapters.service_verification import native_process_arguments, native_process_identity

    pid, owner = context.peer.process_id, context.peer.os_owner_id
    if pid is None or context.peer != channel_peer or not descriptor.allowed_parent_images:
        return False
    try:
        identity = native_process_identity(pid, owner)
        image = channel_peer.image_path
        if image is None or Path(image).resolve() != Path(identity.image).resolve():
            return False
        if not _desktop_image_listed(verifier, identity.image, descriptor):
            return False
        if native_process_arguments(pid, owner)[:1] == (_ROLE_ARGUMENT,):
            return False
        if descends_from_this_runtime(identity, owner):
            return False
        return native_process_identity(pid, owner) == identity
    except (RefusalError, OSError):
        return False


def descends_from_this_runtime(process: NativeProcessIdentity, owner: str) -> bool:
    """Whether this runtime started ``process``, directly or through its own children.

    The runtime's workers run the same image as the desktop, so a desktop holder must not
    trace back to this process. A chain that ends, leaves the owner, or reaches a parent born
    after its child (a reused id) no longer leads back here; one too deep to follow is refused.
    """
    from ..adapters.service_verification import native_process_identity

    runtime = os.getpid()
    current = process
    for _ in range(_MAXIMUM_ANCESTRY_DEPTH):
        if current.pid == runtime:
            return True
        if current.parent_pid in (0, current.pid):
            return False
        try:
            parent = native_process_identity(current.parent_pid, owner)
        except (RefusalError, OSError):
            return False
        if parent.born > current.born:
            return False
        current = parent
    return True


def require_desktop_parent(
    verifier: DesktopImageMatcher, child: NativeProcessIdentity, owner: str, descriptor: InstalledServiceDescriptor
) -> None:
    """Require the exact non-runtime desktop parent in refusal order."""
    from ..adapters.service_verification import native_process_identity

    parent = native_process_identity(child.parent_pid, owner)
    if parent.born > child.born:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_born_after_child")
    if not any(
        verifier.installed_parent_image_matches(parent.image, item.launch_image, item.image_digest)
        for item in descriptor.allowed_parent_images
    ):
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_image_unlisted")
    if native_process_identity(parent.pid, owner) != parent:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_parent_identity_changed")
    if descends_from_this_runtime(parent, owner):
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_started_by_runtime")


def verify_desktop_holder(
    context: ConnectionContext,
    channel: ByteChannel,
    request: ProfileLogin,
    descriptor: InstalledServiceDescriptor | None,
    root: Path,
    storage_identity: str,
    verifier: NativeServiceVerifier,
) -> None:
    """Require installed desktop identity or the explicit development password path."""
    from ..adapters.service_verification import native_process_identity
    from ..application.development_root import verify_development_root

    development_password = (
        request.method == "password" and not request.persist_receipt and verify_development_root(root, storage_identity)
    )
    if descriptor is None:
        if development_password and context.peer.process_id is not None:
            native_process_identity(context.peer.process_id, context.peer.os_owner_id)
            return
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_descriptor_absent")
    if desktop_window_peer(verifier, context, channel.peer, descriptor):
        return
    if verifier.verify_service(context, channel, descriptor) is None:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="desktop_holder_unverified")
    child = native_process_identity(cast(int, context.peer.process_id), context.peer.os_owner_id)
    if development_password:
        return
    require_desktop_parent(verifier, child, context.peer.os_owner_id, descriptor)
