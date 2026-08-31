"""The declared-but-never-filled Workspace fields, as a burndown with teeth.

This exists because the measurement behind it was taken BY HAND six times and
grew on five of them, and every intermediate version would have passed its own
closure check. A hand-walk that has to be repeated is a hand-walk that will
disagree with itself; a scan disagrees only when the tree changes.

The assertion is on MEMBERS, never on a count. A count would go green the
moment somebody populated one field and introduced another, which is exactly
the substitution this campaign keeps finding. Each entry below is an address a
reader can search for, and the failure message says which direction the set
moved -- because a NEW unfilled field and a POPULATED one need opposite
responses and a bare inequality would not distinguish them.

Populating a field is expected to fail this gate. That is the burndown working:
remove the entry in the same change that fills it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.quality.workspace_field_population_scan import scan_unfilled_workspace_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _ROOT / "src" / "cadrumo"
_MODELS_MODULE = _SOURCE_ROOT / "application" / "modelo" / "workspace_models.py"

_OUTSTANDING: frozenset[str] = frozenset(
    {
        # Bounded-facet pagination. NOT a gap: all three are supplied in
        # production by `paginate_modelo_workspace_facet`, which computes the
        # page, `has_more` and `next_cursor` and builds the facet. They are
        # listed only because the scan cannot SEE that construction: the
        # callee there is `facet_type`, a type passed in as a PARAMETER, so
        # the call site carries no model name to match on. Recognising it
        # would need dataflow the scan does not do.
        #
        # Kept here rather than removed, because removing them would make the
        # gate fail on their reappearance every run. The register is the right
        # home for a fact the scan cannot reach -- the same role it plays for
        # DomainRefusal.capability below, which is correctly None rather than
        # missing.
        "ModeloWorkspaceBoundedFacetV1.has_more",
        "ModeloWorkspaceBoundedFacetV1.next_cursor",
        "ModeloWorkspaceBoundedFacetV1.records",
        # Capability explanation surface. ONE cause, measured at both builders
        # rather than three separate gaps: the capability denominator is
        # assembled from a static (capability, producer-contract, disposition)
        # table plus, on the graded path, a CalculationRevision. The producer
        # contract carries contributor identity, projection discriminator,
        # version and fingerprint -- and no evidence, no facts, and no registry
        # family disposition. So none of these three has a source at the call
        # site, and filling them means threading the registry authority into
        # the denominator, which is a design change and not a population.
        # `recovery_action` is blocked differently and for a harder reason:
        # the canonical action vocabulary has no member meaning "re-request
        # with graded admission", which is what the UNMEASURED rows would have
        # to point at, and those rows are unmeasured because the CALLER chose
        # static admission.
        "ModeloWorkspaceCapabilityV1.evidence",
        "ModeloWorkspaceCapabilityV1.facts",
        "ModeloWorkspaceCapabilityV1.recovery_action",
        "ModeloWorkspaceCapabilityV1.source_disposition",
        # Refusal explanation surface. All three are CORRECTLY absent, and it
        # is one cause rather than three: every production refusal is built at
        # boundary="admission" -- measured, all three construction sites -- and
        # these fields belong to the capability and schema boundaries. A
        # capability name, a schema-evidence reference and a registry family
        # disposition have nothing to say about a target that was not found or
        # a calculation that does not exist yet.
        #
        # Note what that implies about the `boundary` union itself: it declares
        # five values and production emits ONE. The other four advertise
        # refusal shapes nothing constructs, which is the closed-union finding
        # the gate-integrity audit already collects, and these three fields are
        # its downstream symptom rather than an independent gap. They become
        # fillable exactly when a non-admission refusal is first produced, and
        # not before.
        "ModeloWorkspaceDomainRefusalV1.capability",
        "ModeloWorkspaceDomainRefusalV1.evidence",
        "ModeloWorkspaceDomainRefusalV1.source_disposition",
        # Not a field-level gap at all: this refusal TYPE has zero production
        # constructions. The refusal union declares three members and
        # production builds exactly one of them, so two advertise outcomes
        # nothing emits -- the finding the gate-integrity audit already carries,
        # and this field is its symptom. It becomes fillable when the type is
        # first produced, and asking for a recovery action on a refusal nobody
        # raises is asking about a payload that does not exist.
        "ModeloWorkspaceRevisionMismatchRefusalV1.recovery_action",
        # Not populatable, and the reason is structural rather than a missing
        # field. Applicability is declared on the REVISION and expressed against
        # TAXPAYER conditions -- entity types, income categories, estimation
        # regimes, fiscal residencies, IVA regimes, a payer fact. An
        # applicability rule names no casillas at all, so there is no
        # record-to-rule relation in the registry to project. This field asks
        # for one, which makes it a per-record shape over a revision-level
        # concept.
        #
        # That matters because the governing ruling says POPULATE. It cannot be
        # satisfied as the registry is modelled: filling it would mean either
        # attaching every revision-level rule to every casilla, which is false,
        # or inventing a mapping nothing declares. The ruling needs revisiting
        # by its author -- delete the field, or extend the registry to carry a
        # real per-casilla applicability relation. Nothing reads it today.
        "ModeloWorkspaceSchemaRecordV1.applicability",
    }
)


def test_the_scan_finds_the_declaring_module_at_all() -> None:
    """A moved or renamed models module would empty every assertion below."""
    assert _MODELS_MODULE.is_file(), (
        f"{_MODELS_MODULE} is not where this gate expects it, so the scan is walking nothing and "
        "its green means only that it found no declarations"
    )


def test_no_workspace_field_is_unfilled_beyond_the_recorded_set() -> None:
    """New unfilled fields fail; populated ones fail until their entry goes."""
    found = {str(finding) for finding in scan_unfilled_workspace_fields(_SOURCE_ROOT, _MODELS_MODULE)}

    appeared = sorted(found - _OUTSTANDING)
    assert not appeared, (
        "these Workspace fields are declared with a default and supplied by no construction site, "
        "so the payload advertises them and never carries them:\n"
        + "\n".join(f"  {entry}" for entry in appeared)
        + "\nFill them, delete them, or record them here with the reason they cannot be filled."
    )

    populated = sorted(_OUTSTANDING - found)
    assert not populated, (
        "these fields are now supplied somewhere, so their entries here are stale and this gate is "
        "protecting nothing for them:\n" + "\n".join(f"  {entry}" for entry in populated)
    )


def test_the_scan_reports_a_field_no_caller_supplies(tmp_path: Path) -> None:
    """Teeth, over a fixture tree rather than the live one.

    Driven over a temporary module so the proof does not depend on the live
    inventory happening to contain an example, and so it keeps working after
    the burndown reaches zero -- which is when a gate most needs to still be
    able to fail.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text(
        "from typing import Literal\n"
        "class _WorkspaceModel:\n"
        "    pass\n"
        "class Thing(_WorkspaceModel):\n"
        "    kind: Literal['thing'] = 'thing'\n"
        "    supplied: str | None = None\n"
        "    never: str | None = None\n"
        "    required: str\n",
        encoding="utf-8",
    )
    caller = tmp_path / "caller.py"
    caller.write_text("Thing(required='x', supplied='y')\n", encoding="utf-8")
    assert caller.exists()

    found = {str(entry) for entry in scan_unfilled_workspace_fields(tmp_path, models)}

    assert found == {"Thing.never"}, (
        "the scan must report only the optional field nobody supplies: a supplied one is not a "
        "finding, a required one cannot be omitted, and a Literal discriminator is filled by its "
        f"own default -- got {sorted(found)}"
    )


def test_a_file_being_rewritten_does_not_abort_the_scan(tmp_path: Path) -> None:
    """Another lane's half-written file must not decide this gate's verdict.

    The tree is edited concurrently, so a scan that raises on the first
    unparseable file reports nothing about the rest -- and reports it as a
    crash rather than as a finding.
    """
    models = tmp_path / "workspace_models.py"
    models.write_text("class Thing:\n    never: str | None = None\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def unfinished(:\n", encoding="utf-8")

    found = {str(entry) for entry in scan_unfilled_workspace_fields(tmp_path, models)}

    assert found == {"Thing.never"}
