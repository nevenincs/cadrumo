"""Operator-facing CLI/JSON output boundary shared by the CLI transport and the wizard.

The CLI's ``--json`` transport (:mod:`entrypoints.cli._common`) sits ABOVE the
setup wizard (:mod:`application.wizard`) in the accepted hexagonal direction,
so the wizard cannot import :func:`entrypoints.cli._common.emit_envelope`.
Both surfaces nonetheless owe the operator the same guarantee: a persistent
sandbox-active :class:`~cadrumo.core.json_contract.Notice` on every command
result while the active profile bucket is a discardable sandbox, in both JSON
and text mode. This package is the shared home for that guarantee, sitting
below both consumers.

:func:`emit_operator_json_success` is the SOLE sanctioned direct caller of
:func:`~cadrumo.core.json_contract.emit_json_success` for an operator-facing
command result; :func:`sandbox_notice_for_active_bucket` and
:func:`sandbox_banner_line` are its text-mode counterparts for callers that
render lines directly rather than through the JSON envelope.

See Also:
    :func:`~cadrumo.entrypoints.cli._common.emit_envelope`
        CLI transport funnel; delegates its JSON branch here and reuses
        :func:`sandbox_notice_for_active_bucket` for its text-mode banner.
    :mod:`application.wizard.commands`
        Setup-wizard success/save-exit emitters; route through the same
        two functions rather than calling
        :func:`~cadrumo.core.json_contract.emit_json_success` directly.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
