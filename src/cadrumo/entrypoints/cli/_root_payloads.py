"""Typed ``--json`` payload schemas for root CLI group callbacks.

The root callbacks are not ordinary leaf commands, but they still emit
:class:`SchemaEnvelope` documents through :func:`emit_envelope`. Each class is
a strict :class:`OutputSchema` subclass. Production-authored CommandSpec references it as a deferred public target
so the JSON-contract and CLI-reference conformance gates can enumerate these
group-callback surfaces alongside normal command leaves.

Field sets match the production payload dicts constructed in
the root callback at the ``root.status`` and ``root.app`` emit sites. The
concrete application shape depends on the callback branch:
:class:`HelpDocument`, :class:`RootLandingReport`, or
:class:`OverviewStatusReport`.

See Also:
    :func:`build_help_document`
        Builds the root and app help documents wrapped by these group-callback
        payload schemas.
    :func:`build_root_landing_report`
        Builds the cold-start / no-session landing DTO carried by
        ``root.status``.
    :func:`build_overview_status_report`
        Builds the active-session overview DTO also accepted by
        ``root.status``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

from pydantic import BaseModel, model_validator

from ...core.json_contract import OutputSchema


def _help_document_branch() -> type[BaseModel]:
    """Resolve the ``HelpDocument`` branch DTO from its public facade."""
    from ...application.operator_surface.help_models import HelpDocument

    return HelpDocument


def _root_landing_report_branch() -> type[BaseModel]:
    """Resolve the ``RootLandingReport`` branch DTO from its public facade."""
    from ...application.operator_surface.help_models import RootLandingReport

    return RootLandingReport


def _overview_status_report_branch() -> type[BaseModel]:
    """Resolve the ``OverviewStatusReport`` branch DTO from its public facade.

    Deliberately deferred behind a thunk: importing
    :mod:`cadrumo.application.overview` materialises the calculation, ledger, and
    registry import graph. The help and cold-start landing branches are tried
    first and match without it, so ``aeat --help`` must never pay that cost.
    """
    from ...application.overview import OverviewStatusReport

    return OverviewStatusReport


def _canonical_branch_payload(
    value: object,
    *,
    branches: tuple[Callable[[], type[BaseModel]], ...],
) -> dict[str, object]:
    """Return a JSON payload validated by one of the canonical branch DTOs.

    Branches are supplied as thunks and resolved one at a time, in declaration
    order, so a payload matching an earlier branch never imports the modules
    backing the later ones. Acceptance and refusal are unchanged: the first
    branch that validates still wins, and a payload matching none still raises
    naming every candidate.
    """
    if not isinstance(value, Mapping):
        raise ValueError("root result must be a mapping")

    serialized = json.dumps(dict(value))
    attempted: list[str] = []
    for resolve_branch in branches:
        branch = resolve_branch()
        attempted.append(branch.__name__)
        try:
            dumped = branch.model_validate_json(serialized).model_dump(mode="json")
            if not isinstance(dumped, dict):
                raise ValueError("canonical root branch did not produce a mapping")
            payload: dict[str, object] = {}
            for key, item in dumped.items():
                if not isinstance(key, str):
                    raise ValueError("canonical root branch produced a non-text key")
                payload[key] = item
            return payload
        except ValueError:
            continue
    expected = ", ".join(attempted)
    raise ValueError(f"root result must match one canonical branch: {expected}")


class RootStatusResult(OutputSchema):
    """JSON envelope for the bare ``cadrumo`` (or ``aeat --help``) invocation.

    The root callback validates one of three application-layer payloads:
    :class:`HelpDocument` for ``aeat --help``, :class:`RootLandingReport` for the
    cold-start / no-session landing, or :class:`OverviewStatusReport` when an
    active session can render the full overview. These shapes vary
    significantly, so the schema preserves their flat JSON shape while
    validating every value through one of those canonical models.

    The text half of the landing branch is rendered by
    :func:`render_cli_root_landing_lines`; JSON mode keeps the application DTO
    fields intact inside :class:`SchemaEnvelope`.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class var shadows ConfigDict descriptor; mypy assignment check is in...

    @model_validator(mode="before")
    @classmethod
    def _validate_canonical_branch(cls, value: object) -> dict[str, object]:
        return _canonical_branch_payload(
            value,
            branches=(
                _help_document_branch,
                _root_landing_report_branch,
                _overview_status_report_branch,
            ),
        )


class AppRootResult(OutputSchema):
    """JSON envelope for the bare ``aeat app`` (or ``aeat app --help``) invocation.

    The app group callback wraps :class:`HelpDocument` under the stable
    ``root.app`` group-callback key. Like :class:`RootStatusResult`, the schema
    preserves the application-owned help fields after canonical validation.

    The document is produced by :func:`build_help_document` for the ``app`` help
    surface and emitted through :class:`SchemaEnvelope`.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]  # reason: TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR: pydantic v2 model_config class var shadows ConfigDict descriptor; mypy assignment check is in...

    @model_validator(mode="before")
    @classmethod
    def _validate_help_document(cls, value: object) -> dict[str, object]:
        return _canonical_branch_payload(value, branches=(_help_document_branch,))
