"""Semantic-role sibling exception helpers for typo detection."""

from __future__ import annotations


def semantic_roles_are_tax_domain_siblings(left: str, right: str) -> bool:
    domain_suffixes = {"irpf", "is", "iva"}
    left_parts = left.split("_")
    right_parts = right.split("_")
    return (
        len(left_parts) > 1
        and len(right_parts) > 1
        and left_parts[:-1] == right_parts[:-1]
        and left_parts[-1] in domain_suffixes
        and right_parts[-1] in domain_suffixes
    )


_SEMANTIC_ROLE_AXIS_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("permanente", "aumento"),
    ("permanente", "disminucion"),
    ("temporaria", "ejercicio", "aumento"),
    ("temporaria", "ejercicio", "disminucion"),
    ("temporaria", "anteriores", "aumento"),
    ("temporaria", "anteriores", "disminucion"),
    ("saldo", "inicial", "aumento"),
    ("saldo", "final", "aumento"),
)


def semantic_roles_are_axis_siblings(left: str, right: str) -> bool:
    left_stem, left_axis = _split_semantic_role_axis_suffix(left)
    right_stem, right_axis = _split_semantic_role_axis_suffix(right)
    if left_stem is not None and right_stem is not None and left_stem == right_stem and left_axis != right_axis:
        return True
    if _semantic_roles_are_legal_reference_siblings(left, right):
        return True
    if _semantic_roles_are_ccaa_siblings(left, right):
        return True
    return _semantic_roles_are_axis_token_siblings(left, right)


def _split_semantic_role_axis_suffix(role: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    parts = tuple(role.split("_"))
    for suffix in _SEMANTIC_ROLE_AXIS_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix) :] == suffix:
            return parts[: -len(suffix)], suffix
    return None, None


_SEMANTIC_ROLE_AXIS_TOKEN_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"clave", "subclave"}),
    frozenset({"count", "amount"}),
    frozenset({"anteriores", "posteriores"}),
    frozenset({"ascendiente", "descendiente"}),
    frozenset({"transmision", "adquisicion"}),
    frozenset({"ab", "c"}),
)

def _semantic_roles_are_axis_token_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    if len(left_parts) == len(right_parts):
        differing = [
            (left_part, right_part)
            for left_part, right_part in zip(left_parts, right_parts, strict=True)
            if left_part != right_part
        ]
        if len(differing) == 1 and _semantic_role_tokens_share_axis(*differing[0]):
            return True
        if _semantic_role_related_party_row_slot_siblings(left_parts, right_parts):
            return True

    return False


def _semantic_role_tokens_share_axis(left: str, right: str) -> bool:
    return any(left in group and right in group for group in _SEMANTIC_ROLE_AXIS_TOKEN_GROUPS)


def _semantic_role_related_party_row_slot_siblings(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if len(left) < 4 or left[:-1] != right[:-1] or left[-1] == right[-1]:
        return False
    return (
        left[:2] == ("related", "party")
        and left[-1] in {"1", "2", "3", "4", "5"}
        and right[-1] in {"1", "2", "3", "4", "5"}
    )


_SEMANTIC_ROLE_CCAA_TOKENS: frozenset[str] = frozenset(
    {
        "andalucia",
        "aragon",
        "asturias",
        "baleares",
        "canarias",
        "cantabria",
        "galicia",
        "madrid",
        "murcia",
    },
)


def _semantic_roles_are_ccaa_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    left_normalised = _normalise_semantic_role_ccaa_tokens(left_parts)
    right_normalised = _normalise_semantic_role_ccaa_tokens(right_parts)
    return (
        left_normalised == right_normalised
        and (left_normalised != left_parts or right_normalised != right_parts)
        and left_parts != right_parts
    )


def _normalise_semantic_role_ccaa_tokens(parts: tuple[str, ...]) -> tuple[str, ...]:
    normalised: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part == "c" and index + 1 < len(parts) and parts[index + 1] == "valenciana":
            normalised.append("ccaa")
            index += 2
            continue
        if part == "la" and index + 1 < len(parts) and parts[index + 1] == "rioja":
            normalised.append("ccaa")
            index += 2
            continue
        if part in _SEMANTIC_ROLE_CCAA_TOKENS:
            normalised.append("ccaa")
            index += 1
            continue
        normalised.append(part)
        index += 1
    return tuple(normalised)


def _semantic_roles_are_legal_reference_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    left_stripped = _strip_semantic_role_legal_reference_tokens(left_parts)
    right_stripped = _strip_semantic_role_legal_reference_tokens(right_parts)
    return (
        left_stripped == right_stripped
        and (left_stripped != left_parts or right_stripped != right_parts)
        and left_parts != right_parts
    )


def _strip_semantic_role_legal_reference_tokens(parts: tuple[str, ...]) -> tuple[str, ...]:
    stripped: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part.startswith("art"):
            index += 1
            while index < len(parts) and parts[index].isdigit():
                index += 1
            continue
        if part.startswith("dt") or part in {"rdleg", "lis"}:
            index += 1
            continue
        stripped.append(part)
        index += 1
    return tuple(stripped)
