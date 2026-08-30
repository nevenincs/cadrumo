"""Detector for divergence between the two declarations of "this profile fact is required".

Two mechanisms answer that question and neither derives from the other. The
profile schema (``schema.toml``) declares ``required`` per field. ``PROFILE_KEYS``
is compiled from ``WIZARD_FLOWS`` and carries its own ``ProfileKeyRequirement``.
They disagree today, and reconciling them is deliberately out of scope here:
doing so requires a conditional-requirement grammar the schema does not yet
have, without which the wizard would have to demand row-scoped facts
unconditionally and refuse lawful filings.

An accepted divergence without a detector widens unobserved, which is what this
file prevents. It does not close the divergence; it pins the current one, states
a cause for every entry, and fails on anything new.

Every cause is machine-checked, not merely asserted in prose. A field excused as
a repeatable-row field is verified to sit in a section the schema actually marks
``repeatable``; a field excused as conditionally rescued is verified to be
present in the wizard key space at all. A cause that stops being true reds the
gate exactly as a new divergence does — otherwise the reasons rot into
decoration and the allowlist quietly pre-approves whatever later occupies the
path.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ....domain.user_profile.loader import load_user_profile_schema
from ...wizard.compiler import ensure_profile_keys_registered

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Cause(StrEnum):
    """Why a schema-required field is not required in the wizard key space."""

    #: The field is one column of a repeatable, effective-dated section. It is
    #: required *per row*, and the wizard key space is flat — it has no row axis
    #: to express "required within each declared row" on. Verified against the
    #: schema's own ``repeatable`` flag.
    REPEATABLE_ROW = "repeatable_row"

    #: The field exists in the wizard key space as OPTIONAL and is raised to
    #: required by an explicit conditional elsewhere, so the wizard's own
    #: requirement level is deliberately weaker than the schema's.
    CONDITIONAL_RESCUE = "conditional_rescue"


_KNOWN_DIVERGENCES: dict[str, tuple[_Cause, str]] = {
    "activities.description": (
        _Cause.CONDITIONAL_RESCUE,
        "Raised to required by the readiness gate's baseline, which appends it unless the filer "
        "is a natural person with declared non-business income only. The wizard cannot ask it "
        "unconditionally without refusing that lawful case.",
    ),
    "iva.regime": (
        _Cause.CONDITIONAL_RESCUE,
        "Raised to required by iva_regime_required(values) in the keys validator: a filer with no "
        "IVA obligation legitimately declares none, so an unconditional wizard requirement would "
        "refuse them.",
    ),
    "attribution_entity_socios.nif": (_Cause.REPEATABLE_ROW, "One column of a declared socio row."),
    "attribution_entity_socios.name": (_Cause.REPEATABLE_ROW, "One column of a declared socio row."),
    "attribution_entity_socios.share_pct": (_Cause.REPEATABLE_ROW, "One column of a declared socio row."),
    "attribution_entity_socios.base_imponible_assigned": (
        _Cause.REPEATABLE_ROW,
        "One column of a declared socio row.",
    ),
    "attribution_entity_socios.participe_clave": (_Cause.REPEATABLE_ROW, "One column of a declared socio row."),
    "attribution_entity_socios.clave": (_Cause.REPEATABLE_ROW, "One column of a declared socio row."),
    "attribution_received.entity_nif": (_Cause.REPEATABLE_ROW, "One column of a received-attribution row."),
    "attribution_received.entity_name": (_Cause.REPEATABLE_ROW, "One column of a received-attribution row."),
    "attribution_received.share_pct": (_Cause.REPEATABLE_ROW, "One column of a received-attribution row."),
    "attribution_received.base_imponible_attributed": (
        _Cause.REPEATABLE_ROW,
        "One column of a received-attribution row.",
    ),
    "attribution_received.filing_year": (_Cause.REPEATABLE_ROW, "One column of a received-attribution row."),
    "usage_ratios.category_id": (_Cause.REPEATABLE_ROW, "One column of a declared usage-ratio row."),
    "usage_ratios.business_ratio": (_Cause.REPEATABLE_ROW, "One column of a declared usage-ratio row."),
}
"""Schema-required fields the wizard key space does not require, and why.

Pinned rather than fixed: closing the divergence needs a schema grammar that
does not yet exist, so it is not this gate's job. An entry is removed when its
field stops diverging, never left standing.
"""


def _schema_facts() -> tuple[set[str], set[str], dict[str, bool]]:
    """Return schema paths, schema-required paths, and path -> section repeatable."""
    schema = load_user_profile_schema()
    paths: set[str] = set()
    required: set[str] = set()
    repeatable: dict[str, bool] = {}
    for section in schema.sections:
        for field in section.fields:
            path = f"{section.key}.{field.key}"
            paths.add(path)
            repeatable[path] = section.repeatable
            if field.required:
                required.add(path)
    return paths, required, repeatable


def _key_facts() -> tuple[set[str], set[str]]:
    """Return every wizard key path and the subset the wizard marks REQUIRED.

    ``PROFILE_KEYS`` is a lazily-resolved registry that refuses to be read before
    the wizard catalogue has pushed the compiled keys, so it is imported here
    rather than at module scope — after the registration call, never before.
    """
    ensure_profile_keys_registered()
    from ....domain.contribuyente.keys import PROFILE_KEYS, ProfileKeyRequirement

    paths = {entry.key for entry in PROFILE_KEYS}
    required = {entry.key for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.REQUIRED}
    return paths, required


def test_no_new_schema_required_field_diverges_from_the_wizard() -> None:
    """A newly schema-required field must be reconciled or explicitly pinned here.

    Without this, a field added as schema-required and never wired into the
    wizard joins the divergence silently, and the two surfaces return opposite
    verdicts on the same record.
    """
    _, schema_required, _ = _schema_facts()
    _, keys_required = _key_facts()

    diverging = schema_required - keys_required
    unpinned = sorted(diverging - set(_KNOWN_DIVERGENCES))

    assert not unpinned, (
        "these fields are required by the profile schema but not by the wizard key space, "
        f"and are not pinned as known divergences: {unpinned}. Either wire them into the "
        "wizard flow or add them here with a cause."
    )


def test_no_pinned_divergence_outlives_its_cause() -> None:
    """A pinned entry whose field stopped diverging must be removed, not left standing.

    A stale entry pre-approves whatever later occupies that path and reads to the
    next author as a decision rather than as residue.
    """
    _, schema_required, _ = _schema_facts()
    _, keys_required = _key_facts()

    diverging = schema_required - keys_required
    stale = sorted(path for path in _KNOWN_DIVERGENCES if path not in diverging)

    assert not stale, f"these pinned divergences no longer diverge and must be removed: {stale}"


def test_every_repeatable_row_cause_names_an_actually_repeatable_section() -> None:
    """The REPEATABLE_ROW cause is checked against the schema, not taken on trust.

    If a section is made non-repeatable, every field excused by its row-ness loses
    that excuse and must be re-judged rather than continuing to ride a reason that
    is no longer true.
    """
    _, _, repeatable_by_path = _schema_facts()

    misdescribed = sorted(
        path
        for path, (cause, _reason) in _KNOWN_DIVERGENCES.items()
        if cause is _Cause.REPEATABLE_ROW and not repeatable_by_path.get(path, False)
    )

    assert not misdescribed, f"excused as repeatable-row fields but their section is not repeatable: {misdescribed}"


def test_every_conditional_rescue_cause_names_a_field_the_wizard_actually_carries() -> None:
    """The CONDITIONAL_RESCUE cause claims the wizard knows the field at all.

    The claim is that the wizard carries the field but at a weaker requirement
    level. A field absent from the key space entirely is a different, larger
    divergence and must not hide behind this cause.
    """
    key_paths, _ = _key_facts()

    absent = sorted(
        path
        for path, (cause, _reason) in _KNOWN_DIVERGENCES.items()
        if cause is _Cause.CONDITIONAL_RESCUE and path not in key_paths
    )

    assert not absent, f"excused as conditionally rescued but absent from the wizard key space: {absent}"


def test_every_pinned_divergence_states_a_reason() -> None:
    """An entry with no reason is an unexplained exemption."""
    unexplained = sorted(path for path, (_cause, reason) in _KNOWN_DIVERGENCES.items() if not reason.strip())

    assert not unexplained, f"pinned divergences must state a reason: {unexplained}"


def test_the_wizard_never_requires_a_fact_the_schema_does_not() -> None:
    """The divergence must stay one-directional.

    The schema is the canonical declaration. A wizard key required where the
    schema does not require it would mean the wizard refuses a record the schema
    considers complete — the opposite failure, and currently absent. Asserted so
    it stays absent rather than being discovered later.
    """
    _, schema_required, _ = _schema_facts()
    _, keys_required = _key_facts()

    assert not sorted(keys_required - schema_required), (
        "the wizard requires facts the schema does not, inverting which declaration is canonical"
    )


def test_every_wizard_key_names_a_real_schema_path() -> None:
    """A wizard key naming no schema field collects a value nothing can validate."""
    schema_paths, _, _ = _schema_facts()
    key_paths, _ = _key_facts()

    assert not sorted(key_paths - schema_paths), "wizard keys naming no schema field"
