"""Typed ``--json`` payload schemas for root CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every root-command surface this module covers.

Field sets match the production payload dicts constructed in ``__init__.py``
at their emit sites. All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


@register_schema("root.status")
class RootStatusResult(OutputSchema):
    """JSON envelope for the bare ``aeat`` (or ``aeat --help``) invocation.

    The root landing surfaces an operator_surface help document or an
    overview status report. Both shapes vary significantly, so we accept
    extra fields from the application-layer model dump.
    """

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]


@register_schema("root.app")
class AppRootResult(OutputSchema):
    """JSON envelope for the bare ``aeat app`` (or ``aeat app --help``) invocation."""

    # TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR:
    # pydantic v2 model_config class var shadows ConfigDict descriptor;
    # mypy assignment check is incorrect.
    model_config = {"extra": "allow"}  # type: ignore[assignment]
