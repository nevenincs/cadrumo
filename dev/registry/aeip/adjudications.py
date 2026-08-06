"""Operator adjudications for the anexo-A AEIP continuity chains.

The planner in :mod:`dev.registry.aeip.manager` derives chain ids mechanically
from the programme titles AEAT publishes, but a handful of shapes cannot be
settled by reading text: a programme re-designated under a fresh window after a
gap, two title spellings that may be one relabelled programme or two successive
designations, a title too long for the 128-character chain-id budget, and a
title appearing at two ids in the same revision with nothing in the registry to
tell a genuine second box from a transcription duplicate.

Each of those is a legal-identity judgment. This module is where an operator
records the judgment and the evidence behind it, so the planner reads a decision
instead of guessing one. Every entry carries a mandatory ``reason``: an
adjudication with no stated grounding is refused, because the reason *is* the
audit trail for the identity claim.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING

__all__ = [
    "AdjudicationError",
    "AdjudicationSet",
    "ChainIdOverride",
    "Exclusion",
    "Split",
    "TitleAlias",
    "VariantsDistinct",
    "load_adjudications",
]

_UTF_8 = UTF_8_ENCODING
DEFAULT_ADJUDICATIONS_FILENAME = "adjudications.toml"


class AdjudicationError(RuntimeError):
    """Raised when the adjudications file is malformed or ungrounded."""


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One occurrence withheld from the family pending or after adjudication."""

    revision: str
    casilla: str
    reason: str


@dataclass(frozen=True, slots=True)
class TitleAlias:
    """Several published titles adjudicated as one programme."""

    slug: str
    titles: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ChainIdOverride:
    """An explicit chain id for a slug the derived form cannot express."""

    slug: str
    chain_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Split:
    """A programme re-designated: a second chain starts at ``from_revision``."""

    slug: str
    from_revision: str
    chain_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class VariantsDistinct:
    """Year-variant titles adjudicated as genuinely separate programmes."""

    slugs: tuple[str, ...]
    reason: str


def _require(table: dict[str, object], key: str, *, context: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdjudicationError(f"{context}: missing or empty {key!r}")
    return value.strip()


def _require_list(table: dict[str, object], key: str, *, context: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not value:
        raise AdjudicationError(f"{context}: {key!r} must be a non-empty list")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items):
        raise AdjudicationError(f"{context}: {key!r} contains an empty entry")
    return items


@dataclass(frozen=True, slots=True)
class AdjudicationSet:
    """Every recorded judgment, indexed for the planner."""

    exclusions: tuple[Exclusion, ...] = ()
    aliases: tuple[TitleAlias, ...] = ()
    chain_ids: tuple[ChainIdOverride, ...] = ()
    splits: tuple[Split, ...] = ()
    distinct_variants: tuple[VariantsDistinct, ...] = ()

    @classmethod
    def empty(cls) -> AdjudicationSet:
        """An adjudication set with nothing yet decided."""
        return cls()

    def is_excluded(self, revision_id: str, casilla_id: str) -> bool:
        """True when this occurrence has been withheld from the family."""
        return any(entry.revision == revision_id and entry.casilla == casilla_id for entry in self.exclusions)

    def slug_for(self, title: str) -> str | None:
        """The adjudicated slug for a published title, when one is recorded."""
        normalised = title.strip()
        for alias in self.aliases:
            if normalised in alias.titles:
                return alias.slug
        return None

    def chain_id_for(self, slug: str) -> str | None:
        """The explicit chain id recorded for a slug, when one is."""
        return next((entry.chain_id for entry in self.chain_ids if entry.slug == slug), None)

    def split_for(self, slug: str) -> Split | None:
        """The recorded re-designation split for a slug, when one is."""
        return next((entry for entry in self.splits if entry.slug == slug), None)

    def variants_resolved(self, slugs: tuple[str, ...]) -> bool:
        """True when this year-variant group has an explicit judgment.

        A group is settled either by an alias that folded the variants into one
        slug (so they no longer present as a group) or by an explicit
        ``distinct_variants`` record keeping them apart.
        """
        candidate = set(slugs)
        return any(candidate <= set(entry.slugs) for entry in self.distinct_variants)


def load_adjudications(path: Path) -> AdjudicationSet:
    """Read and validate the adjudications file.

    A missing file is not an error: it means nothing has been adjudicated yet,
    and the planner will report every ambiguity as open.
    """
    if not path.is_file():
        return AdjudicationSet.empty()
    try:
        data = tomllib.loads(path.read_text(encoding=_UTF_8))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise AdjudicationError(f"cannot read adjudications file {path}: {error}") from error

    def tables(key: str) -> list[dict[str, object]]:
        raw = data.get(key) or []
        if not isinstance(raw, list):
            raise AdjudicationError(f"{path}: {key!r} must be an array of tables")
        return [entry for entry in raw if isinstance(entry, dict)]

    exclusions = tuple(
        Exclusion(
            revision=_require(entry, "revision", context=f"{path} [[exclusions]]"),
            casilla=_require(entry, "casilla", context=f"{path} [[exclusions]]"),
            reason=_require(entry, "reason", context=f"{path} [[exclusions]]"),
        )
        for entry in tables("exclusions")
    )
    aliases = tuple(
        TitleAlias(
            slug=_require(entry, "slug", context=f"{path} [[aliases]]"),
            titles=_require_list(entry, "titles", context=f"{path} [[aliases]]"),
            reason=_require(entry, "reason", context=f"{path} [[aliases]]"),
        )
        for entry in tables("aliases")
    )
    chain_ids = tuple(
        ChainIdOverride(
            slug=_require(entry, "slug", context=f"{path} [[chain_ids]]"),
            chain_id=_require(entry, "chain_id", context=f"{path} [[chain_ids]]"),
            reason=_require(entry, "reason", context=f"{path} [[chain_ids]]"),
        )
        for entry in tables("chain_ids")
    )
    splits = tuple(
        Split(
            slug=_require(entry, "slug", context=f"{path} [[splits]]"),
            from_revision=_require(entry, "from_revision", context=f"{path} [[splits]]"),
            chain_id=_require(entry, "chain_id", context=f"{path} [[splits]]"),
            reason=_require(entry, "reason", context=f"{path} [[splits]]"),
        )
        for entry in tables("splits")
    )
    distinct = tuple(
        VariantsDistinct(
            slugs=_require_list(entry, "slugs", context=f"{path} [[distinct_variants]]"),
            reason=_require(entry, "reason", context=f"{path} [[distinct_variants]]"),
        )
        for entry in tables("distinct_variants")
    )
    return AdjudicationSet(
        exclusions=exclusions,
        aliases=aliases,
        chain_ids=chain_ids,
        splits=splits,
        distinct_variants=distinct,
    )
