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
    return _semantic_roles_are_axis_token_siblings(left, right)


def _split_semantic_role_axis_suffix(role: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    parts = tuple(role.split("_"))
    for suffix in _SEMANTIC_ROLE_AXIS_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix) :] == suffix:
            return parts[: -len(suffix)], suffix
    return None, None


def _semantic_roles_are_axis_token_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    return _semantic_role_related_party_row_slot_siblings(left_parts, right_parts)


def _semantic_role_related_party_row_slot_siblings(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if len(left) < 4 or left[:-1] != right[:-1] or left[-1] == right[-1]:
        return False
    return (
        left[:2] == ("related", "party")
        and left[-1] in {"1", "2", "3", "4", "5"}
        and right[-1] in {"1", "2", "3", "4", "5"}
    )
