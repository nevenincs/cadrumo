"""Catalogue parity, placeholder, scalar, and revision audit results."""

from dataclasses import dataclass

from cadrumo.core.i18n.render import extract_placeholders

from ._casilla_keys import is_delta_keyed_leaf
from ._revision_drift import RevisionMoveCandidate, classify_revision_moves


@dataclass(frozen=True)
class LocaleScalarViolation:
    """One locale key whose YAML leaf is not a string."""

    locale_file: str
    key: str
    value_type: str


@dataclass(frozen=True)
class LocalePlaceholderVariant:
    """The placeholder set used by one locale for a shared key."""

    locale_file: str
    placeholders: frozenset[str]


@dataclass(frozen=True)
class LocalePlaceholderMismatch:
    """All differing placeholder variants for one shared locale key."""

    key: str
    variants: tuple[LocalePlaceholderVariant, ...]


@dataclass(frozen=True)
class LocaleFileAudit:
    """Structured audit findings owned by one locale catalogue.

    ``revision_moves`` is a READING of the two key-set findings, never a
    replacement for them: a rename leaves its keys in ``codebase_missing`` and
    ``codebase_extra`` so this catalogue stays un-``ok`` until the move is
    performed. The two ``move_accounted_*`` sets name the keys that reading
    explains, so a report can print each of them once as a relocation instead
    of twice as unrelated work.
    """

    locale_file: str
    codebase_missing: tuple[str, ...]
    codebase_extra: tuple[str, ...]
    inter_locale_missing: tuple[str, ...]
    scalar_violations: tuple[LocaleScalarViolation, ...]
    revision_moves: tuple[RevisionMoveCandidate, ...] = ()
    move_accounted_missing: frozenset[str] = frozenset()
    move_accounted_extra: frozenset[str] = frozenset()

    @property
    def ok(self) -> bool:
        """Return whether this catalogue has no file-local findings."""
        return not (self.codebase_missing or self.codebase_extra or self.inter_locale_missing or self.scalar_violations)


@dataclass(frozen=True)
class LocaleAuditResult:
    """Complete production locale audit across every configured catalogue."""

    files: tuple[LocaleFileAudit, ...]
    placeholder_mismatches: tuple[LocalePlaceholderMismatch, ...]

    @property
    def ok(self) -> bool:
        """Return whether every scalar, key, and placeholder contract passes."""
        return all(file.ok for file in self.files) and not self.placeholder_mismatches


def _audit_locale_file(
    locale_file: str,
    leaves: dict[str, object],
    keys: set[str],
    *,
    codebase_keys: set[str],
    all_locale_keys: set[str],
    namespace_prefixes: tuple[str, ...],
) -> LocaleFileAudit:
    """Compute one catalogue's key-set, scalar, and revision-move findings."""
    violations = tuple(
        LocaleScalarViolation(locale_file, key, type(value).__name__)
        for key, value in sorted(leaves.items())
        if not isinstance(value, str) and not (value is None and key.startswith("modelo.schema."))
    )
    codebase_missing = tuple(sorted(codebase_keys - keys))
    codebase_extra = tuple(
        sorted(key for key in keys - codebase_keys if not _covered_by_namespace(key, namespace_prefixes))
    )
    moves = classify_revision_moves(locale_file, codebase_missing, codebase_extra)
    return LocaleFileAudit(
        locale_file=locale_file,
        codebase_missing=codebase_missing,
        codebase_extra=codebase_extra,
        inter_locale_missing=tuple(sorted(key for key in all_locale_keys - keys if not is_delta_keyed_leaf(key))),
        scalar_violations=violations,
        revision_moves=moves.candidates,
        move_accounted_missing=moves.accounted_missing,
        move_accounted_extra=moves.accounted_extra,
    )


def _audit_placeholder_mismatches(
    key_sets: dict[str, set[str]],
    locale_leaves: dict[str, dict[str, object]],
) -> tuple[LocalePlaceholderMismatch, ...]:
    """Return placeholder-parity mismatches across keys shared by every catalogue."""
    shared_keys = set.intersection(*key_sets.values()) if key_sets else set()
    mismatches: list[LocalePlaceholderMismatch] = []
    for key in sorted(shared_keys):
        values = {name: leaves[key] for name, leaves in locale_leaves.items()}
        if not all(isinstance(value, str) for value in values.values()):
            continue
        variants = tuple(
            LocalePlaceholderVariant(name, extract_placeholders(value))
            for name, value in sorted(values.items())
            if isinstance(value, str)
        )
        if len({variant.placeholders for variant in variants}) > 1:
            mismatches.append(LocalePlaceholderMismatch(key, variants))
    return tuple(mismatches)


def _covered_by_namespace(key: str, namespace_prefixes: tuple[str, ...]) -> bool:
    """Return whether a dotted locale key belongs to a namespace governed outside key-set parity.

    Dynamic namespaces are one such family; delta-keyed casilla leaves are
    another, and their presence is checked by the Modelo casilla catalogue.
    Form layout headings the committed layouts declare are the third: they are
    optional translations with a declared fallback chain.
    """
    from ._registry_scanner import is_form_layout_heading_candidate, scan_form_layout_heading_keys

    return (
        is_delta_keyed_leaf(key)
        or any(f".{prefix}." in f".{key}." for prefix in namespace_prefixes)
        or (is_form_layout_heading_candidate(key) and key in scan_form_layout_heading_keys())
    )
