"""Fail-closed validation and loading for absent record-design numeric wire facts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, cast

from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .joined_record_design import JoinedRecordDesign, JoinedRecordDesignField, design_view
from .render_profile_authority import validate_render_profile_authority
from .render_profile_eligibility import (
    resolve_render_profile_eligibility,
)
from .render_profile_evidence import (
    RenderProfileSourceEvidence,
)
from .render_profile_loading import load_render_profile
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity
from .render_profile_validation import _anchor_key, _anchor_key_tuple, _duplicates, _field_anchor


def load_and_validate_render_profile(
    profile_directory: Path,
    joined: JoinedRecordDesign,
    source_evidence: RenderProfileSourceEvidence,
) -> RenderProfile:
    """Load sorted TOML fragments and validate exact coverage against parser IR."""
    profile = load_render_profile(profile_directory)
    validate_render_profile(profile, joined, source_evidence)
    return profile


def validate_render_profile(
    profile: RenderProfile,
    joined: JoinedRecordDesign,
    source_evidence: RenderProfileSourceEvidence,
) -> None:
    """Refuse every identity, membership, coverage, and representation conflict."""
    expected_identity = RenderProfileDesignIdentity(
        modelo=joined.modelo,
        design_epoch=joined.source.design_epoch,
        source_ref=joined.source.source_ref,
        source_sha256=joined.source.source_sha256,
    )
    composite_keys = frozenset(_anchor_key_tuple(rule.anchor) for rule in profile.signed_composite_rules)
    eligibility = resolve_render_profile_eligibility(
        (design_view(joined_field) for joined_field in joined.fields),
        joined.source,
        signed_composite_anchor_keys=composite_keys,
    )
    if profile.empty_rule_assertion is not None and eligibility.all_fields:
        raise RegistryValidationError("empty render profile contradicts canonical eligible policy slots")
    validate_render_profile_authority(profile, expected_identity, eligibility, source_evidence)
    literal_anchors = {
        _field_anchor(design_view(field)) for field in joined.fields if field.semantic_entry.kind.value == "literal"
    }
    if any(rule.anchor not in literal_anchors for rule in profile.literal_numeric_rules):
        raise RegistryValidationError("literal numeric rules must address literal semantic fields")
    _validate_telematic_transport_choice_rules(profile, joined)


class _TelematicTransportChoice(Protocol):
    @property
    def anchor(self) -> RenderProfileAnchor: ...

    @property
    def selected_literal(self) -> str: ...

    @property
    def alternative_literals(self) -> tuple[str, ...]: ...

    @property
    def expected_source_content(self) -> str: ...


def _validate_telematic_transport_choice_rules(profile: RenderProfile, joined: JoinedRecordDesign) -> None:
    rules = profile.telematic_transport_choice_rules
    if _duplicates(rule.anchor for rule in rules):
        raise RegistryValidationError("telematic transport choices contain duplicate exact anchors")
    by_anchor = {_field_anchor(design_view(field)): field for field in joined.fields}
    for rule in rules:
        _validate_telematic_transport_choice(rule, by_anchor)


def _validate_telematic_transport_choice(
    rule: _TelematicTransportChoice,
    by_anchor: dict[RenderProfileAnchor, JoinedRecordDesignField],
) -> None:
    joined_field = by_anchor.get(rule.anchor)
    if joined_field is None:
        raise RegistryValidationError("telematic transport choice has no exact official source anchor")
    field = design_view(joined_field)
    content = field.content
    _validate_telematic_transport_slot(
        rule,
        joined_field,
        field_length=field.length,
        aeat_type=field.aeat_type,
        normalized_description=field.normalized_description,
        content=content,
    )
    folded = cast(str, content).translate(str.maketrans({'"': "'", "“": "'", "”": "'", "«": "'", "»": "'"}))
    _validate_telematic_transport_alternatives(rule, folded)
    _validate_telematic_transport_condition(folded)


def _validate_telematic_transport_slot(
    rule: _TelematicTransportChoice,
    joined_field: JoinedRecordDesignField,
    *,
    field_length: int,
    aeat_type: str,
    normalized_description: str,
    content: str | None,
) -> None:
    if (
        joined_field.semantic_entry.kind.value != "literal"
        or joined_field.semantic_entry.literal != rule.selected_literal
        or field_length != 1
        or aeat_type.casefold().strip() not in {"alfabético", "alfabetico"}
        or normalized_description.casefold().strip(" .") != "tipo de soporte"
        or content != rule.expected_source_content
    ):
        raise RegistryValidationError(
            "telematic transport choice conflicts with its exact official slot or mapped literal"
        )


def _validate_telematic_transport_alternatives(rule: _TelematicTransportChoice, folded: str) -> None:
    source_keys = tuple(re.findall(r"'([A-Z])'\s*:", folded))
    if (
        len(source_keys) != len(set(source_keys))
        or rule.selected_literal not in source_keys
        or tuple(key for key in source_keys if key != rule.selected_literal) != rule.alternative_literals
    ):
        raise RegistryValidationError("telematic transport choice does not enumerate the exact official alternatives")


def _validate_telematic_transport_condition(folded: str) -> None:
    if re.search(r"'T'\s*:\s*Transmisi[oó]n telem[aá]tica", folded, re.IGNORECASE) is None:
        raise RegistryValidationError("telematic transport choice lacks the official telematic condition")


def render_profile_digest(
    profile: RenderProfile,
    source_evidence: RenderProfileSourceEvidence,
) -> str:
    """Digest every reviewed profile fact and resolved source-evidence fact.

    Authored fragment, rule, membership, allowed-value, and evidence ordering is
    deliberately irrelevant. Exact anchors and every policy/evidence payload
    remain part of the digest.
    """
    if source_evidence.design_identity != profile.design_identity:
        raise RegistryValidationError(
            "render profile source evidence does not match the profile design identity",
        )
    digest_payload: dict[str, object] = {
        "schema_version": profile.schema_version,
        "design_identity": profile.design_identity.model_dump(mode="json"),
        "fragment_ids": sorted(profile.fragment_ids),
    }
    digest_payload["width_17_rules"] = _width_17_digest_rules(profile)
    digest_payload["singleton_rules"] = _singleton_digest_rules(profile)
    digest_payload["source_evidence"] = {
        "design_identity": source_evidence.design_identity.model_dump(mode="json"),
        "entries": _source_evidence_digest_entries(source_evidence),
    }
    _append_optional_digest_fields(profile, digest_payload)
    return content_hash_hex(digest_payload)


def _width_17_digest_rules(profile: RenderProfile) -> list[dict[str, object]]:
    return [
        {
            **rule.model_dump(mode="json", exclude={"anchors"}),
            "anchors": [anchor.model_dump(mode="json") for anchor in sorted(rule.anchors, key=_anchor_key)],
        }
        for rule in sorted(profile.width_17_rules, key=lambda item: item.aeat_type)
    ]


def _singleton_digest_rules(profile: RenderProfile) -> list[dict[str, object]]:
    return [
        {
            **rule.model_dump(mode="json", exclude={"allowed_values"}),
            "allowed_values": sorted(rule.allowed_values),
        }
        for rule in sorted(profile.singleton_rules, key=lambda item: _anchor_key(item.anchor))
    ]


def _source_evidence_digest_entries(source_evidence: RenderProfileSourceEvidence) -> list[dict[str, object]]:
    return [
        entry.model_dump(mode="json")
        for entry in sorted(source_evidence.entries, key=lambda item: (item.sheet, item.cell))
    ]


def _append_optional_digest_fields(profile: RenderProfile, digest_payload: dict[str, object]) -> None:
    # Preserve the canonical digest representation of every pre-extension
    # profile. The new axis exists only when authored; an empty additive field
    # must not force unrelated source authorities through regeneration.
    if profile.signed_composite_rules:
        digest_payload["signed_composite_rules"] = [
            rule.model_dump(mode="json")
            for rule in sorted(profile.signed_composite_rules, key=lambda item: _anchor_key(item.anchor))
        ]
    if profile.literal_numeric_rules:
        digest_payload["literal_numeric_rules"] = [
            rule.model_dump(mode="json")
            for rule in sorted(profile.literal_numeric_rules, key=lambda item: _anchor_key(item.anchor))
        ]
    if profile.telematic_transport_choice_rules:
        digest_payload["telematic_transport_choice_rules"] = [
            rule.model_dump(mode="json")
            for rule in sorted(profile.telematic_transport_choice_rules, key=lambda item: _anchor_key(item.anchor))
        ]
    if profile.empty_rule_assertion is not None:
        digest_payload["empty_rule_assertion"] = profile.empty_rule_assertion
