"""Exact source readings admit their own leaves and refuse changed source pins."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ...compiler.authority import compiled_bundled_authority
from ...tests.authored_edition_support import authored_revisions as compiled_revisions
from ...tests.authored_edition_support import authored_revisions_where
from ..generated_export_inheritance_model import GeneratedExportInheritance, GeneratedExportInheritanceContext
from ..joined_record_design import design_view
from ..render_check import revision_render_inputs
from ..source_signed_components import signed_component_policy_for
from ..source_signed_triples import signed_triple_policy_for
from ..source_stated_year_constant import source_stated_year_constant_for
from ..source_text_date_components import text_date_component_policy_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _first_generated_revision(modelo: str) -> str:
    """Return the oldest revision of one modelo that carries a generated export layout."""
    return str(authored_revisions_where(modelo, lambda revision: bool(revision.export_layouts))[0].id)


_OLDEST_190 = _first_generated_revision("190")
_OLDEST_165 = _first_generated_revision("165")


@pytest.mark.parametrize(
    ("modelo", "revision", "resolver", "expected"),
    [
        ("190", _OLDEST_190, signed_component_policy_for, ExportValuePolicy.SIGNED_COMPONENT_SIGN),
        ("165", _OLDEST_165, signed_triple_policy_for, ExportValuePolicy.SIGNED_COMPONENT_SIGN),
        ("165", _OLDEST_165, text_date_component_policy_for, ExportValuePolicy.YYYYMMDD_TEXT_YEAR),
    ],
)
def test_reviewed_component_admissions_refuse_reissued_source_bytes(modelo, revision, resolver, expected) -> None:
    inputs = revision_render_inputs(compiled_bundled_authority(), modelo=modelo, revision=revision)
    source = inputs.joined.source
    arguments = {
        "modelo": modelo,
        "epoch": inputs.transport_profile.design_epoch,
        "source_ref": str(source.source_ref),
        "source_sha256": source.source_sha256,
    }
    views = [field.model_copy(update={"parser_field": design_view(field)}) for field in inputs.joined.fields]
    matching = [field for field in views if resolver(field, **arguments) is expected]
    assert matching, (modelo, revision, expected)
    for field in matching:
        with pytest.raises(RegistryValidationError, match=r"source identity.*stale"):
            resolver(field, **{**arguments, "source_sha256": "0" * 64})


def test_source_stated_year_is_not_a_literal_year_or_an_unpinned_constant() -> None:
    revision = open_ended_revision("131")
    inputs = revision_render_inputs(compiled_bundled_authority(), modelo="131", revision=str(revision.id))
    source = inputs.joined.source
    fields = [field.parser_field for field in inputs.joined.fields if field.parser_field.source_cell == "A15"]
    matches = [
        field
        for field in fields
        if source_stated_year_constant_for(
            source_ref=str(source.source_ref), source_sha256=source.source_sha256, field=field
        )
        is not None
    ]
    assert len(matches) == 1
    with pytest.raises(RegistryValidationError, match=r"stale"):
        source_stated_year_constant_for(source_ref=str(source.source_ref), source_sha256="0" * 64, field=matches[0])
    with pytest.raises(RegistryValidationError, match=r"no longer matches"):
        source_stated_year_constant_for(
            source_ref=str(source.source_ref),
            source_sha256=source.source_sha256,
            field=matches[0].model_copy(update={"content": str(revision.valid_from.year)}),
        )


def test_inheritance_context_preserves_every_ancestor_pin_in_storage_order() -> None:
    older_revision, newer_revision = compiled_revisions("303")[-2:]
    layout = newer_revision.export_layouts[0]

    def pin(revision: str, digest: str) -> GeneratedExportInheritance:
        return GeneratedExportInheritance(
            baseline_revision_id=revision,
            baseline_revision_sha256=digest * 64,
            baseline_manifest_sha256="b" * 64,
            baseline_layout_sha256="c" * 64,
            baseline_source_ref="aeat-dr-303-2025",
            baseline_source_sha256="d" * 64,
        )

    older = GeneratedExportInheritanceContext(pin(str(older_revision.id), "a"), layout)
    newer = GeneratedExportInheritanceContext(pin(str(newer_revision.id), "e"), layout, older)
    assert newer.pinned_ancestors == ((str(older_revision.id), "a" * 64), (str(newer_revision.id), "e" * 64))
    with pytest.raises(ValueError, match="baseline_revision_sha256"):
        pin(str(older_revision.id), "invalid")
