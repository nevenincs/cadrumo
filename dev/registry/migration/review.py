"""Build the deterministic pre-emission review register.

This module turns the sealed source manifest into the review contract that
must be consumed before an emitter is allowed to stage output.  It does not
delete source leaves or render a catalogue: parity keeps the old value while
canonicalization records the approved representation for the later emitter.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from re import Match, compile
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex

from .manager import SourceManifest, SourceManifestEntry

_REVIEW_REGISTER_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.pre-emission-review.v1"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_YEAR_TOKEN_RE: Final = compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_ANNUAL_REVISION_RE: Final = compile(r"^(?:19|20)\d{2}$")
_YEAR_PLACEHOLDER: Final[str] = "{year}"

PlaceholderLeafState = Literal["mirrored", "key_echo"]
PlaceholderCanonicalization = Literal["delete_not_migrate"]
PlaceholderParity = Literal["preserve_old_value"]
YearCanonicalization = Literal["parameterize"]
YearParity = Literal["compare_rendered_value"]


class _StrictRecord(BaseModel):
    """Use immutable, closed records for the sealed review artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PlaceholderReviewEntry(_StrictRecord):
    """One placeholder leaf with its parity and canonicalization dispositions."""

    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    casilla_id: str = Field(min_length=1)
    candidate_chain_id: str | None = Field(default=None, min_length=1)
    locale: str = Field(min_length=1)
    field: Literal["label", "help"]
    leaf_state: PlaceholderLeafState
    source_path: str | None = Field(default=None, min_length=1)
    old_resolved_value: str = Field(min_length=1)
    canonicalization: PlaceholderCanonicalization = "delete_not_migrate"
    parity: PlaceholderParity = "preserve_old_value"

    @model_validator(mode="after")
    def _validate_leaf_contract(self) -> PlaceholderReviewEntry:
        """Keep the mirrored class bound to help leaves only."""
        if self.leaf_state == "mirrored" and self.field != "help":
            raise ValueError("mirrored placeholder entries must be help leaves")
        return self


class YearRevisionValue(_StrictRecord):
    """One exact official value represented by a year-token template."""

    revision_id: str = Field(min_length=1)
    casilla_id: str = Field(min_length=1)
    year: str = Field(pattern=r"^(?:19|20)\d{2}$")
    rendered_value: str = Field(min_length=1)


class YearParameterizedReviewEntry(_StrictRecord):
    """One chain/locale label family admitted by the year-token decision."""

    modelo_id: str = Field(min_length=1)
    candidate_chain_id: str = Field(min_length=1)
    locale: str = Field(min_length=1)
    field: Literal["label"] = "label"
    template: str = Field(min_length=1)
    revisions: tuple[YearRevisionValue, ...] = Field(min_length=2)
    source_resolution: Literal["localized", "official_spanish"]
    canonicalization: YearCanonicalization = "parameterize"
    parity: YearParity = "compare_rendered_value"

    @model_validator(mode="after")
    def _validate_rendering_contract(self) -> YearParameterizedReviewEntry:
        """Require every rendered source value to be reproducible verbatim."""
        if self.template.count(_YEAR_PLACEHOLDER) != 1:
            raise ValueError("year parameterized template must contain exactly one {year} token")
        coordinates = tuple((item.revision_id, item.casilla_id) for item in self.revisions)
        if coordinates != tuple(sorted(coordinates)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("year parameterized revisions must be unique and sorted")
        values = tuple(item.rendered_value for item in self.revisions)
        for item in self.revisions:
            if _annual_revision_year(item.revision_id) != item.year:
                raise ValueError("year parameterized value must match its annual revision filing year")
            if self.template.replace(_YEAR_PLACEHOLDER, item.year) != item.rendered_value:
                raise ValueError("year parameterized template does not reproduce an official rendered value")
        if self.source_resolution == "official_spanish" and self.locale != "es":
            raise ValueError("official Spanish year values may only declare the es locale")
        if len(set(values)) < 2 or len({item.year for item in self.revisions}) < 2:
            raise ValueError("year parameterized family must contain at least two distinct years and values")
        return self


class PreEmissionReviewRegister(_StrictRecord):
    """Sealed pre-emission decisions bound to one source manifest."""

    schema_id: str = _REVIEW_REGISTER_SCHEMA
    source_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    placeholder_entry_count: int = Field(ge=0)
    placeholder_delete_count: int = Field(ge=0)
    mirrored_help_count: int = Field(ge=0)
    mirrored_help_debt_count: int = Field(ge=0)
    help_key_echo_count: int = Field(ge=0)
    label_key_echo_count: int = Field(ge=0)
    key_echo_count: int = Field(ge=0)
    year_family_count: int = Field(ge=0)
    year_chain_count: int = Field(ge=0)
    review_sha256: str = Field(pattern=_SHA256_PATTERN)
    placeholder_entries: tuple[PlaceholderReviewEntry, ...]
    year_entries: tuple[YearParameterizedReviewEntry, ...]

    @model_validator(mode="after")
    def _validate_register(self) -> PreEmissionReviewRegister:
        """Reject counter drift, reordering, or a tampered sealed digest."""
        if self.schema_id != _REVIEW_REGISTER_SCHEMA:
            raise ValueError(f"unsupported pre-emission review schema {self.schema_id!r}")
        placeholder_keys = tuple(_placeholder_sort_key(item) for item in self.placeholder_entries)
        if placeholder_keys != tuple(sorted(placeholder_keys)) or len(placeholder_keys) != len(set(placeholder_keys)):
            raise ValueError("placeholder review entries must be unique and sorted")
        year_keys = tuple(_year_sort_key(item) for item in self.year_entries)
        if year_keys != tuple(sorted(year_keys)) or len(year_keys) != len(set(year_keys)):
            raise ValueError("year parameterized review entries must be unique and sorted")
        if self.placeholder_entry_count != len(self.placeholder_entries):
            raise ValueError("placeholder_entry_count does not match entries")
        if self.placeholder_delete_count != sum(
            item.canonicalization == "delete_not_migrate" for item in self.placeholder_entries
        ):
            raise ValueError("placeholder_delete_count does not match dispositions")
        if self.mirrored_help_count != sum(item.leaf_state == "mirrored" for item in self.placeholder_entries):
            raise ValueError("mirrored_help_count does not match entries")
        if self.mirrored_help_debt_count != self.mirrored_help_count + self.help_key_echo_count:
            raise ValueError("mirrored_help_debt_count does not match help placeholder entries")
        if self.help_key_echo_count != sum(
            item.leaf_state == "key_echo" and item.field == "help" for item in self.placeholder_entries
        ):
            raise ValueError("help_key_echo_count does not match entries")
        if self.label_key_echo_count != sum(
            item.leaf_state == "key_echo" and item.field == "label" for item in self.placeholder_entries
        ):
            raise ValueError("label_key_echo_count does not match entries")
        if self.key_echo_count != self.help_key_echo_count + self.label_key_echo_count:
            raise ValueError("key_echo_count does not match field counts")
        if self.year_family_count != len(self.year_entries):
            raise ValueError("year_family_count does not match entries")
        if self.year_chain_count != len({(item.modelo_id, item.candidate_chain_id) for item in self.year_entries}):
            raise ValueError("year_chain_count does not match entries")
        if self.review_sha256 != _review_digest(
            self.source_manifest_sha256,
            self.placeholder_entries,
            self.year_entries,
        ):
            raise ValueError("review_sha256 does not match the canonical review entries")
        return self


def _placeholder_sort_key(entry: PlaceholderReviewEntry) -> tuple[str, str, str, str, str, str]:
    """Return the stable source-coordinate order for placeholder decisions."""
    return (
        entry.modelo_id,
        entry.revision_id,
        entry.casilla_id,
        entry.locale,
        entry.field,
        entry.leaf_state,
    )


def _year_sort_key(entry: YearParameterizedReviewEntry) -> tuple[str, str, str, str, str]:
    """Return the stable chain/template order for year families."""
    return (
        entry.modelo_id,
        entry.candidate_chain_id,
        entry.locale,
        entry.field,
        entry.template,
    )


def _annual_revision_year(revision_id: str) -> str | None:
    """Return a filing year only for a revision that names one annual year.

    Revision windows such as ``2020-y-siguientes`` and ``2019-2023`` do not
    identify one filing year.  They cannot safely supply a rendered year
    placeholder, so the review register leaves them for a later explicit
    decision instead of inferring chronology from a range label.
    """
    return revision_id if _ANNUAL_REVISION_RE.fullmatch(revision_id) else None


def _year_template(value: str) -> tuple[str, str] | None:
    """Return a one-token template and its year, or reject non-parameterizable text."""
    matches: tuple[Match[str], ...] = tuple(_YEAR_TOKEN_RE.finditer(value))
    if len(matches) != 1:
        return None
    match = matches[0]
    return f"{value[: match.start()]}{_YEAR_PLACEHOLDER}{value[match.end() :]}", match.group()


def _review_digest(
    source_manifest_sha256: str,
    placeholder_entries: Iterable[PlaceholderReviewEntry],
    year_entries: Iterable[YearParameterizedReviewEntry],
) -> str:
    """Hash the source binding and canonical entry streams into one seal."""
    payload = {
        "schema_id": _REVIEW_REGISTER_SCHEMA,
        "source_manifest_sha256": source_manifest_sha256,
        "placeholder_entries": [entry.model_dump(mode="json") for entry in placeholder_entries],
        "year_entries": [entry.model_dump(mode="json") for entry in year_entries],
    }
    return sha256_hex(canonical_json_bytes(payload))


def build_pre_emission_review_register(manifest: SourceManifest) -> PreEmissionReviewRegister:
    """Build pre-emission review decisions from the sealed source manifest only.

    Mirrored help and key echoes are explicitly marked ``delete_not_migrate``
    for canonicalization while parity retains the old value.  Year-token label
    families are admitted only when one template reproduces at least two
    distinct official values exactly.  No source or staging tree is written.
    """
    placeholders_list: list[PlaceholderReviewEntry] = []
    for entry in manifest.entries:
        if entry.leaf_state not in {"mirrored", "key_echo"} or entry.old_resolved_value is None:
            continue
        leaf_state: PlaceholderLeafState = "mirrored" if entry.leaf_state == "mirrored" else "key_echo"
        placeholders_list.append(
            PlaceholderReviewEntry(
                modelo_id=entry.candidate.candidate.modelo_id,
                revision_id=entry.candidate.candidate.revision_id,
                casilla_id=entry.candidate.candidate.casilla_id,
                candidate_chain_id=entry.candidate_chain_id,
                locale=entry.candidate.candidate.locale,
                field=entry.candidate.candidate.field,
                leaf_state=leaf_state,
                source_path=entry.source_path,
                old_resolved_value=entry.old_resolved_value,
            ),
        )
    placeholders = tuple(placeholders_list)

    grouped: dict[tuple[str, str, str, str], list[tuple[SourceManifestEntry, str]]] = defaultdict(list)
    for entry in manifest.entries:
        candidate = entry.candidate.candidate
        if candidate.field != "label" or candidate.value is None or entry.candidate_chain_id is None:
            continue
        if entry.candidate.classification not in {"grounded", "continuity_candidate"}:
            continue
        if candidate.locale != "es" and candidate.resolution != "localized":
            continue
        parsed = _year_template(candidate.value)
        if parsed is None or _annual_revision_year(candidate.revision_id) != parsed[1]:
            continue
        template, _year = parsed
        grouped[(candidate.modelo_id, entry.candidate_chain_id, candidate.locale, template)].append((entry, template))

    year_entries: list[YearParameterizedReviewEntry] = []
    for (modelo_id, candidate_chain_id, locale, template), members in grouped.items():
        revisions: list[YearRevisionValue] = []
        resolutions = {entry.candidate.candidate.resolution for entry, _template in members}
        if resolutions == {"localized"}:
            source_resolution: Literal["localized", "official_spanish"] = "localized"
        elif resolutions == {"official_spanish"}:
            source_resolution = "official_spanish"
        else:
            continue
        if source_resolution == "official_spanish" and locale != "es":
            continue
        for entry, _template in members:
            value = entry.candidate.candidate.value
            if value is None:
                continue
            parsed = _year_template(value)
            if parsed is None or parsed[0] != template:
                continue
            if _annual_revision_year(entry.candidate.candidate.revision_id) != parsed[1]:
                continue
            revisions.append(
                YearRevisionValue(
                    revision_id=entry.candidate.candidate.revision_id,
                    casilla_id=entry.candidate.candidate.casilla_id,
                    year=parsed[1],
                    rendered_value=value,
                ),
            )
        distinct_values = {item.rendered_value for item in revisions}
        distinct_years = {item.year for item in revisions}
        if len(distinct_values) < 2 or len(distinct_years) < 2:
            continue
        year_entries.append(
            YearParameterizedReviewEntry(
                modelo_id=modelo_id,
                candidate_chain_id=candidate_chain_id,
                locale=locale,
                template=template,
                revisions=tuple(sorted(revisions, key=lambda item: (item.revision_id, item.casilla_id))),
                source_resolution=source_resolution,
            ),
        )

    ordered_placeholders = tuple(sorted(placeholders, key=_placeholder_sort_key))
    ordered_year_entries = tuple(sorted(year_entries, key=_year_sort_key))
    return PreEmissionReviewRegister(
        source_manifest_sha256=manifest.manifest_sha256,
        placeholder_entry_count=len(ordered_placeholders),
        placeholder_delete_count=len(ordered_placeholders),
        mirrored_help_count=sum(item.leaf_state == "mirrored" for item in ordered_placeholders),
        mirrored_help_debt_count=sum(
            item.leaf_state == "mirrored" or (item.leaf_state == "key_echo" and item.field == "help")
            for item in ordered_placeholders
        ),
        help_key_echo_count=sum(
            item.leaf_state == "key_echo" and item.field == "help" for item in ordered_placeholders
        ),
        label_key_echo_count=sum(
            item.leaf_state == "key_echo" and item.field == "label" for item in ordered_placeholders
        ),
        key_echo_count=sum(item.leaf_state == "key_echo" for item in ordered_placeholders),
        year_family_count=len(ordered_year_entries),
        year_chain_count=len({(item.modelo_id, item.candidate_chain_id) for item in ordered_year_entries}),
        review_sha256=_review_digest(manifest.manifest_sha256, ordered_placeholders, ordered_year_entries),
        placeholder_entries=ordered_placeholders,
        year_entries=ordered_year_entries,
    )


__all__ = [
    "PlaceholderReviewEntry",
    "PreEmissionReviewRegister",
    "YearParameterizedReviewEntry",
    "YearRevisionValue",
    "build_pre_emission_review_register",
]
