"""Typed ``--json`` results for setup-wizard success emitters.

These two classes are the actual runtime payload the wizard's success
emitters build and validate (see
:mod:`application.wizard._commands`). Each is a strict
:class:`~cadrumo.core.json_contract.OutputSchema` subclass at its true owner —
the wizard, not the CLI transport — because the CLI package sits above
:mod:`application.wizard` in the accepted hexagonal direction and the wizard
cannot reach back up into an ``entrypoints.cli`` payload module for a class
to construct.

Before this module existed, ``entrypoints.cli._config_payloads`` carried a
same-shaped pair of classes purely to satisfy the CLI-leaf-has-a-registered-
schema conformance gate; nothing ever imported or constructed them, and the
wizard emitted an untyped ``dict`` instead. A field drifting between the two
therefore failed silently. Constructing :class:`ConfigProfileCreateResult` /
:class:`ConfigProfileEditResult` now IS the strict validation, enforced at
every emit rather than only by a structural CLI-tree-vs-registry test.
"""

from __future__ import annotations

from enum import StrEnum

from ...core.json_contract import OutputSchema

__all__ = ["ConfigProfileCreateResult", "ConfigProfileEditResult", "ProfileWizardStatus"]


class ProfileWizardStatus(StrEnum):
    """Closed outcome vocabulary for the profile create / edit envelopes.

    ``status`` is a machine-readable contract token, not display prose. The
    interactive wizard resolved it through the active locale while the
    profile-manager close path wrote literal English, so the two commands
    emitted the same envelope shape with different ``status`` values for any
    non-English operator -- an automation branch on ``status`` was correct in
    exactly one locale. The localized verb belongs on the envelope's text
    lines and notices, which is where both surfaces already render it.
    """

    CREATED = "created"
    UPDATED = "updated"
    ABANDONED = "abandoned"


class ConfigProfileCreateResult(OutputSchema):
    """JSON envelope for the profile-creation command.

    The successful create payload carries the active profile label. Any
    forward guidance belongs to a typed envelope notice, never a bespoke
    ``next`` field or an executable text recommendation.
    """

    profile_name: str
    status: ProfileWizardStatus
    active_profile: str | None = None


class ConfigProfileEditResult(OutputSchema):
    """JSON envelope for ``aeat config profile edit``.

    The post-edit next-step hint is surfaced on the envelope ``notices``
    channel, not as a bespoke ``next`` field. The payload reports only the
    edited profile name and mutation status; edited facts remain in secure
    profile storage.
    """

    profile_name: str
    status: ProfileWizardStatus
