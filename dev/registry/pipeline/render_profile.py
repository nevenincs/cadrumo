"""Fail-closed validation and loading for absent record-design numeric wire facts."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .joined_record_design import JoinedRecordDesign, design_view
from .render_profile_authority import validate_render_profile_authority
from .render_profile_eligibility import (
    resolve_render_profile_eligibility,
)
from .render_profile_evidence import (
    RenderProfileSourceEvidence,
)
from .render_profile_loading import load_render_profile
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileDesignIdentity
from .render_profile_validation import _anchor_key, _anchor_key_tuple, _field_anchor


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
    validate_render_profile_authority(profile, expected_identity, eligibility, source_evidence)
    literal_anchors = {
        _field_anchor(design_view(field)) for field in joined.fields if field.semantic_entry.kind.value == "literal"
    }
    if any(rule.anchor not in literal_anchors for rule in profile.literal_numeric_rules):
        raise RegistryValidationError("literal numeric rules must address literal semantic fields")


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
    width_rules: list[dict[str, object]] = [
        {
            **rule.model_dump(mode="json", exclude={"anchors"}),
            "anchors": [anchor.model_dump(mode="json") for anchor in sorted(rule.anchors, key=_anchor_key)],
        }
        for rule in sorted(profile.width_17_rules, key=lambda item: item.aeat_type)
    ]
    singleton_rules: list[dict[str, object]] = [
        {
            **rule.model_dump(mode="json", exclude={"allowed_values"}),
            "allowed_values": sorted(rule.allowed_values),
        }
        for rule in sorted(profile.singleton_rules, key=lambda item: _anchor_key(item.anchor))
    ]
    signed_composite_rules = [
        rule.model_dump(mode="json")
        for rule in sorted(profile.signed_composite_rules, key=lambda item: _anchor_key(item.anchor))
    ]
    evidence_entries = [
        entry.model_dump(mode="json")
        for entry in sorted(source_evidence.entries, key=lambda item: (item.sheet, item.cell))
    ]
    digest_payload: dict[str, object] = {
        "schema_version": profile.schema_version,
        "design_identity": profile.design_identity.model_dump(mode="json"),
        "fragment_ids": sorted(profile.fragment_ids),
        "width_17_rules": width_rules,
        "singleton_rules": singleton_rules,
        "source_evidence": {
            "design_identity": source_evidence.design_identity.model_dump(mode="json"),
            "entries": evidence_entries,
        },
    }
    # Preserve the canonical digest representation of every pre-extension
    # profile. The new axis exists only when authored; an empty additive field
    # must not force unrelated source authorities through regeneration.
    if signed_composite_rules:
        digest_payload["signed_composite_rules"] = signed_composite_rules
    if profile.literal_numeric_rules:
        digest_payload["literal_numeric_rules"] = [
            rule.model_dump(mode="json")
            for rule in sorted(profile.literal_numeric_rules, key=lambda item: _anchor_key(item.anchor))
        ]
    return content_hash_hex(digest_payload)
