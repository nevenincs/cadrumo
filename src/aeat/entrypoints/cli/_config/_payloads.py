"""Typed ``--json`` payload schemas for ``aeat config`` CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass
and is decorated with :func:`register_schema` so the JSON-contract
test suite can enumerate every config-command surface. Without these
typed payloads, ``config profile set`` and ``config profile unset``
emit free-form dicts that downstream tooling cannot rely on for
shape stability.
"""

from __future__ import annotations

from .._schemas import OutputSchema, register_schema


@register_schema("config.profile.set")
class ProfileFactSetResult(OutputSchema):
    """JSON envelope for ``aeat config profile set <key> <value>``."""

    operation: str = "config.profile.set"
    key: str
    value: str


@register_schema("config.profile.unset")
class ProfileFactUnsetResult(OutputSchema):
    """JSON envelope for ``aeat config profile unset <key>``.

    The ``value`` field is intentionally retained as an empty string
    (rather than dropped or replaced with ``None``) so set/unset
    payloads share an identical shape; downstream tooling can treat
    them uniformly and infer the unset state from the empty value.
    """

    operation: str = "config.profile.unset"
    key: str
    value: str = ""
