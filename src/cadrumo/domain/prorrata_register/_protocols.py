"""Domain-level repository Protocol for the cross-period IVA prorrata register.

Application-layer code that persists or loads the :class:`ProrrataRegister`
depends on :class:`ProrrataRegisterRepositoryProtocol`, not on the concrete
adapter-backed :class:`ProrrataRegisterRepository`. This keeps the domain layer
free of adapter imports while still providing a typed port surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing-only boundary DTO (lives in core, not adapters)
    from ...core import SecureObjectWrite
    from . import ProrrataRegister


@runtime_checkable
class ProrrataRegisterRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the prorrata register.

    Any object that provides its readable bucket identity together with
    ``load`` and ``to_secure_object_write`` over the singleton
    :class:`ProrrataRegister` satisfies this protocol. The concrete
    secure-object-backed implementation is :class:`ProrrataRegisterRepository`.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when the repository is explicitly bound to one."""
        ...

    def load(self) -> ProrrataRegister:
        """Return the persisted register or an empty register if absent.

        Returns:
            The :class:`ProrrataRegister` loaded from storage.
        """
        ...

    def to_secure_object_write(self, register: ProrrataRegister) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` for ``register`` without committing it."""
        ...


__all__ = ["ProrrataRegisterRepositoryProtocol"]
