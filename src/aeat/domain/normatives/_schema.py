"""Strict pydantic v2 schema for the ``aeat.domain.normatives`` subpackage.

Every boundary-crossing record the subpackage reads from disk, writes
to disk, or exposes over its public API is defined here. The schema is
frozen and strict wherever the loader idiom permits it, per the
project-wide pydantic v2 mandate.

Closed catalogues are :class:`enum.StrEnum`. Multilingual fields use
:class:`aeat.core.i18n.Translatable`; the authoritative ``es`` key is
enforced at load time on every title and summary.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated, override

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ...core import STRICT_FROZEN_CONFIG
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ._errors import NormativeValidationError


class NormativeKind(StrEnum):
    """Closed catalogue of Spanish legal-act kinds the project cites.

    The enum deliberately ignores the ministry prefix of an *Orden
    Ministerial* (HFP vs HAC) because the ministry label shifts every
    cabinet reshuffle and the legal nature of the act is unchanged.
    """

    LEY = "ley"
    REAL_DECRETO = "real-decreto"
    ORDEN_MINISTERIAL = "orden-ministerial"
    REAL_DECRETO_LEY = "real-decreto-ley"


_StableId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
"""Kebab-case id shape shared with :mod:`aeat.domain.manuals`."""


_Reviewer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Reviewer handle (GitHub username, email, or full name)."""


_NormativeNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Z]*[A-Za-z]*[0-9]+(?:/[0-9]{4})?$|^[A-Z]+/[0-9]+/[0-9]{4}$",
    ),
]
"""Normative number shape, e.g. ``35/2006``, ``1624/1992``, or ``HAC/242/2025``."""


_ArticuloNumero = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[0-9a-zA-Z.-]+$",
    ),
]
"""Article number shape, e.g. ``32``, ``32.1``, ``32.1.a``, ``27bis``."""


_TagField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
"""Tag shape: kebab-case slug."""


_BoeIdField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^BOE-A-[0-9]{4}-[0-9]+$",
    ),
]
"""BOE-A identifier shape, e.g. ``BOE-A-2006-20764``."""


LocalizedText = Mapping[str, str]
"""Multilingual content mapping, one entry per codified output language.

The authoritative ``es`` entry is mandatory; the remaining codified
languages (``en``, ``ca``, ``hu``) are optional translations. Unknown
language codes are rejected so corpus drift is caught at load time.
"""


def _require_spanish(translatable: LocalizedText, field_name: str) -> None:
    """Assert a localized-text mapping carries the authoritative ``es`` key.

    Args:
        translatable: The localized-text mapping under validation.
        field_name: Dotted field name surfaced in the error message.

    Raises:
        NormativeValidationError: If the ``es`` key is missing or empty,
            or if the mapping carries an unknown language code.
    """
    unknown = set(translatable) - set(SUPPORTED_OUTPUT_LANGUAGES)
    if unknown:
        raise NormativeValidationError(
            f"{field_name}: unknown language code(s) {sorted(unknown)!r} "
            f"(codified languages are {sorted(SUPPORTED_OUTPUT_LANGUAGES)!r})",
        )
    if not translatable.get("es", "").strip():
        raise NormativeValidationError(f"{field_name}: missing authoritative Spanish ('es') translation")


class _NormativeStrictFrozen(BaseModel):
    """Shared base config: strict validation, immutable, no extras."""

    model_config = STRICT_FROZEN_CONFIG


class _NormativeStrictMutable(BaseModel):
    """Strict validation but mutable; used for aggregate catalogues."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


class Articulo(_NormativeStrictFrozen):
    """A single article inside a :class:`NormativeReference`.

    The project codifies only the articles it actively cites. Missing
    articles are silently permitted — the catalogue is not a complete
    index of every article in every law, it is the set of articles the
    project's automation has an opinion about.
    """

    numero: _ArticuloNumero = Field(description="Article number, e.g. '32' or '32.1.a'.")
    titulo: LocalizedText = Field(description="Article title in all supplied languages.")
    summary: LocalizedText = Field(description="One-paragraph plain-language article summary.")
    permalink: AnyHttpUrl = Field(description="BOE deep link to the article (fragment-addressed).")
    text_es: str = Field(
        default="",
        description=(
            "Verbatim authoritative Spanish article text. Optional; when present "
            "it grounds registry legal-reference required_text substring checks."
        ),
    )
    notes: str = Field(default="", description="Free-form reviewer notes.")

    @model_validator(mode="after")
    def _check_spanish(self) -> Articulo:
        """Enforce the authoritative Spanish translation invariant."""
        _require_spanish(self.titulo, f"Articulo[{self.numero}].titulo")
        _require_spanish(self.summary, f"Articulo[{self.numero}].summary")
        return self


class NormativeReference(_NormativeStrictFrozen):
    """A single Spanish tax normative codified by the project."""

    id: _StableId = Field(description="Stable kebab-case id, e.g. 'ley-35-2006'.")
    kind: NormativeKind = Field(description="Legal-act kind.")
    number: _NormativeNumber = Field(description="Normative number, e.g. '35/2006' or 'HAC/242/2025'.")
    title: LocalizedText = Field(description="Full normative title in all supplied languages.")
    published_at: date = Field(description="BOE publication date.")
    boe_url: AnyHttpUrl = Field(description="Canonical BOE consolidated-text URL.")
    boe_id: _BoeIdField = Field(description="BOE-A identifier, e.g. 'BOE-A-2006-20764'.")
    articulos: tuple[Articulo, ...] = Field(
        default_factory=tuple,
        description="Articles the project cites. Need not cover every article in the act.",
    )
    tags: tuple[_TagField, ...] = Field(
        default_factory=tuple,
        description="Tax-domain tags grouping the normative, e.g. ('irpf', 'general').",
    )
    last_reviewed_at: date = Field(description="Date a human last hand-reviewed this record.")
    reviewed_by: _Reviewer = Field(description="Reviewer handle.")

    @model_validator(mode="after")
    def _validate(self) -> NormativeReference:
        """Enforce translation, article uniqueness, and permalink invariants."""
        _require_spanish(self.title, f"NormativeReference[{self.id}].title")
        seen: set[str] = set()
        for articulo in self.articulos:
            if articulo.numero in seen:
                raise NormativeValidationError(
                    f"NormativeReference[{self.id}]: duplicate articulo numero {articulo.numero!r}",
                )
            seen.add(articulo.numero)
            permalink = str(articulo.permalink)
            if self.boe_id not in permalink:
                raise NormativeValidationError(
                    f"NormativeReference[{self.id}].articulo[{articulo.numero}]: "
                    f"permalink {permalink!r} does not reference boe_id {self.boe_id!r}",
                )
        return self


class NormativeCatalogue(_NormativeStrictMutable):
    """Aggregate view over every loaded :class:`NormativeReference`.

    The aggregate is mutable to keep the loader idiom simple (the
    loader populates the mapping incrementally). Individual
    :class:`NormativeReference` records remain frozen, so callers
    cannot corrupt loaded records in place.
    """

    references: dict[str, NormativeReference] = Field(
        default_factory=dict,
        description="Loaded references keyed by stable id.",
    )

    @model_validator(mode="after")
    def _check_id_alignment(self) -> NormativeCatalogue:
        """Ensure every mapping key matches its record's id."""
        for key, ref in self.references.items():
            if key != ref.id:
                raise NormativeValidationError(
                    f"NormativeCatalogue: key {key!r} does not match reference id {ref.id!r}",
                )
        return self

    @override
    def __iter__(self) -> Iterator[NormativeReference]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        """Iterate over every loaded :class:`NormativeReference`."""
        return iter(self.references.values())

    def __len__(self) -> int:
        """Return the number of loaded references."""
        return len(self.references)

    def __contains__(self, key: object) -> bool:
        """Check whether ``key`` names a loaded reference id."""
        return key in self.references

    def get(self, ref_id: str) -> NormativeReference | None:
        """Return the :class:`NormativeReference` keyed by ``ref_id`` or ``None`` if absent."""
        return self.references.get(ref_id)


class NormativeVerificationIssue(_NormativeStrictFrozen):
    """A single finding produced by :func:`aeat.domain.normatives.verify_catalogue`."""

    level: str = Field(description="'error' or 'warning'.")
    code: str = Field(description="Short, stable issue code.")
    message: str = Field(description="Human-readable detail.")
    reference_id: str | None = Field(default=None, description="Affected reference id, if any.")


class NormativeVerificationReport(_NormativeStrictFrozen):
    """Aggregate verification report for :class:`NormativeCatalogue`."""

    issues: tuple[NormativeVerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[NormativeVerificationIssue, ...]:
        """Return the subset of issues whose level is ``error``.

        Returns:
            Tuple of :class:`NormativeVerificationIssue` objects with error severity.
        """
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def clean(self) -> bool:
        """Return ``True`` when no error-level issues were found."""
        return not self.errors
