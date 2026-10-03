"""Documentation placeholder, role, literal, and link preservation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from cadrumo.core.i18n.render import extract_placeholders

from .locale_mutation_contracts import DocumentationLocaleMutationError

_INLINE_LITERAL: Final[re.Pattern[str]] = re.compile(r"`([^`\r\n]+)`")


_RST_ROLE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:")


_MYST_ROLE_PREFIX: Final[re.Pattern[str]] = re.compile(r"\{(?P<role>[A-Za-z][A-Za-z0-9_-]*)\}\Z")


_MYST_ROLE_TARGET: Final[re.Pattern[str]] = re.compile(r"\s*[^<>\r\n]*?\s*<(?P<target>[^<>\r\n]+)>\s*\Z")


_PYTHON_PERCENT: Final[re.Pattern[str]] = re.compile(
    r"%(?:\([A-Za-z_][A-Za-z0-9_]*\))?[#0\- +]?(?:\d+|\*)?(?:\.\d+|\.\*)?(?:[hlL])?[diouxXeEfFgGcrsa%]"
)


def _validate_format_contract(
    msgid: str,
    current: str,
    replacement: str,
    path: Path,
    identity: tuple[str, str],
) -> None:
    """Require production placeholders and inline documentation tokens to survive."""
    source_placeholders = extract_placeholders(msgid)
    target_placeholders = extract_placeholders(replacement)
    if source_placeholders != target_placeholders:
        raise DocumentationLocaleMutationError(
            f"placeholder mismatch in {path} for {identity!r}: "
            f"source={sorted(source_placeholders)!r} target={sorted(target_placeholders)!r}"
        )
    source_percent = _percent_placeholders(msgid)
    target_percent = _percent_placeholders(replacement)
    if source_percent != target_percent:
        raise DocumentationLocaleMutationError(
            f"percent placeholder mismatch in {path} for {identity!r}: "
            f"source={sorted(source_percent)!r} target={sorted(target_percent)!r}"
        )
    source_inline = _inline_tokens(msgid)
    target_inline = _inline_tokens(replacement)
    if source_inline != target_inline:
        raise DocumentationLocaleMutationError(
            f"inline backtick role/literal mismatch in {path} for {identity!r}: "
            f"source={source_inline!r} target={target_inline!r}"
        )
    # The ``current`` argument is intentionally part of the validator's public
    # call contract: conflicts are checked before format validation, and this
    # assertion keeps accidental future callers from validating another source.
    if not isinstance(current, str):
        raise DocumentationLocaleMutationError(f"non-text gettext translation in {path} for {identity!r}")


def _percent_placeholders(value: str) -> frozenset[str]:
    """Return Python percent-format tokens, excluding the literal ``%%``."""
    return frozenset(match.group(0) for match in _PYTHON_PERCENT.finditer(value) if match.group(0) != "%%")


def _inline_tokens(
    value: str,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[tuple[str, bool, str], ...],
    tuple[str, ...],
    int,
]:
    """Return literal text, RST roles, MyST role contracts, and link targets.

    Backtick literals remain exact unless they are the body of a MyST role.
    For a role body in the form ``label <target>``, only the role name and
    target are contract tokens; the display label is translated prose. Markdown
    links follow the same rule: their labels may translate, while their target
    remains exact.
    """
    literals: list[str] = []
    myst_roles: list[tuple[str, bool, str]] = []
    for match in _INLINE_LITERAL.finditer(value):
        prefix = value[: match.start()]
        role_match = _MYST_ROLE_PREFIX.search(prefix)
        if role_match is None:
            literals.append(match.group(1))
            continue
        body = match.group(1)
        target_match = _MYST_ROLE_TARGET.fullmatch(body)
        if target_match is None:
            myst_roles.append((role_match.group("role"), False, body))
        else:
            myst_roles.append((role_match.group("role"), True, target_match.group("target")))
    rst_roles = tuple(sorted(match.group(0) for match in _RST_ROLE.finditer(value)))
    return (
        tuple(sorted(literals)),
        rst_roles,
        tuple(sorted(myst_roles)),
        _markdown_link_targets(value),
        value.count("`"),
    )


def _markdown_link_targets(value: str) -> tuple[str, ...]:
    """Return exact destinations from Markdown links, allowing label changes."""
    targets: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "[":
            index += 1
            continue
        label_end = _balanced_delimiter_end(value, index, "[", "]")
        if label_end is None or label_end + 1 >= len(value) or value[label_end + 1] != "(":
            index += 1
            continue
        target_end = _balanced_delimiter_end(value, label_end + 1, "(", ")")
        if target_end is None:
            index += 1
            continue
        targets.append(value[label_end + 2 : target_end])
        index = target_end + 1
    return tuple(sorted(targets))


def _balanced_delimiter_end(value: str, start: int, opening: str, closing: str) -> int | None:
    """Find a balanced delimiter while honoring backslash escapes."""
    depth = 0
    escaped = False
    for index in range(start, len(value)):
        character = value[index]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index
    return None
