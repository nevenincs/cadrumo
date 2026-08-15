"""Decide which tools the console advertises by default.

Dumping the whole ~273-verb tree into ``tools/list`` crowds out the user's
question and degrades tool selection. The console therefore
advertises an **orientation core** by default - the always-on floor, grounding,
and meta-discovery tools (the ``contract`` capability manifest among them) plus
the small manifest-derived orientation slice: the ``overview``
obligation-derivation family, the per-verb surface the operator rules mandate
reading first. The full per-verb universe stays reachable through the ``search``
+ ``execute`` meta pair and through runtime toolset activation; it is not
advertised up front.

The ``CADRUMO_MCP_SURFACE`` environment toggle preserves the flat surface for an
operator who wants it (``full``) and for the core-vs-full A/B measurement; the
shipped default is ``core``. This module is SDK-independent and pure - it
classifies descriptors by command key - so the policy is unit-tested directly
without the stdio transport.
"""

from __future__ import annotations

from enum import StrEnum

from ._tools import McpToolDescriptor

#: The environment variable selecting the advertised tool surface.
SURFACE_ENV_VAR = "CADRUMO_MCP_SURFACE"

#: Command-key prefixes whose verbs are part of the orientation slice. The
#: ``overview`` family derives the taxpayer's obligations from the live surface -
#: the operator rules mandate reading it first - so its verbs are always
#: advertised. Membership is a prefix test against the live command keys, never a
#: hand-listed verb set, so a verb added to the family joins the core for free.
_ORIENTATION_PREFIXES: tuple[str, ...] = ("overview.",)


class SurfaceMode(StrEnum):
    """The advertised-tool-surface policy.

    ``CORE`` (the shipped default) advertises only the orientation slice up
    front; ``FULL`` advertises every persona-scoped per-verb tool, the prior
    flat surface, kept for opt-out and for the core-vs-full measurement.
    """

    CORE = "core"
    FULL = "full"


def resolve_surface_mode(raw: str | None) -> SurfaceMode:
    """Resolve the ``CADRUMO_MCP_SURFACE`` value to a :class:`SurfaceMode`.

    An unset or blank value is the shipped ``core`` default. A set value must
    name a mode exactly (case-insensitively); an unrecognised value raises with
    the accepted set named, so a misconfiguration fails loudly rather than
    silently reverting to a surface the operator did not choose.

    Args:
        raw: The raw environment value, or ``None`` when unset.

    Returns:
        The selected :class:`SurfaceMode`.

    Raises:
        ValueError: When ``raw`` is a non-empty string naming no known mode.
    """
    if raw is None or not raw.strip():
        return SurfaceMode.CORE
    value = raw.strip().lower()
    try:
        return SurfaceMode(value)
    except ValueError:
        accepted = ", ".join(mode.value for mode in SurfaceMode)
        raise ValueError(
            f"{SURFACE_ENV_VAR}={raw!r} is not a valid surface mode; accepted: {accepted}",
        ) from None


def is_orientation_command(command_key: str) -> bool:
    """Whether ``command_key`` belongs to the always-advertised orientation slice."""
    return any(command_key.startswith(prefix) for prefix in _ORIENTATION_PREFIXES)


def advertised_descriptors(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    mode: SurfaceMode,
) -> tuple[McpToolDescriptor, ...]:
    """Narrow the per-verb descriptors to those advertised under ``mode``.

    ``FULL`` returns ``descriptors`` unchanged - the flat surface. ``CORE``
    returns only the orientation slice; the rest of the universe stays reachable
    through the meta pair and toolset activation but is not listed up front. The
    caller has already narrowed ``descriptors`` to the active persona's scope, so
    the orientation core is itself persona-filtered.

    Returns:
        The subset of ``descriptors`` to advertise in ``tools/list``.
    """
    if mode is SurfaceMode.FULL:
        return descriptors
    return tuple(descriptor for descriptor in descriptors if is_orientation_command(descriptor.command_key))
