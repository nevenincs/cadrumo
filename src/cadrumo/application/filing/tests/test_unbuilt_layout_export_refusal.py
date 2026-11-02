"""A modelo with no complete export layout refuses before creating an artefact.

Modelo 111's fixed-width fichero-BOE layout has never been built (its record
design still names producer fields with no canonical typed producer
authority). Nothing about this is an AEAT-side withdrawal; the layout simply
does not exist yet, and ``export_draft`` refuses honestly rather than writing
a partial artefact.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from ....domain.filing.errors import FilingExportError
from ..export import export_draft
from .export_support import _approved_modelo_111_registry_draft, schema_provider, typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_a_modelo_with_no_export_layout_refuses_before_writing_output(tmp_path: Path) -> None:
    snapshot = typed_producer_snapshot()
    output = tmp_path / "unbuilt-layout-modelo-111.txt"

    # Assert the CONDITION -- a revision carrying no export layout -- rather than
    # naming a modelo that happens to lack one. Modelo 111 was chosen as the
    # example and has since GAINED a layout, so the refusal correctly stopped
    # firing and this test silently stopped testing anything. Stripping the
    # layouts off the yielded subview keeps modelo 111's fixtures and makes the
    # subject the state under test, immune to any modelo later being authored.
    draft = _approved_modelo_111_registry_draft()
    provider = schema_provider(
        filing_year=draft.period.filing_year,
        period=draft.period.code,
        modelos=("111",),
    )
    subview = provider.get_subview("111")
    assert subview.export_layouts, "fixture precondition: modelo 111 must have a layout to strip"
    unbuilt = replace(
        provider,
        subviews={**provider.subviews, "111": replace(subview, export_layouts=(), export_layout_ids=())},
    )

    # Assert the CONTRACT, not the prose: this refusal is localised, so it
    # carries a message key plus a typed reason code rather than an English
    # sentence. The regex that used to match here pinned presentation.
    with pytest.raises(FilingExportError) as refusal:
        export_draft(
            draft,
            output_path=output,
            producer_snapshot=snapshot,
            schema_provider=unbuilt,
        )
    assert refusal.value.translated_message == "application.filing.export.errors.layout_not_renderable"
    context = refusal.value.context
    assert context is not None, "the refusal must carry the context that names the modelo"
    assert context["modelo"] == "111"

    assert not output.exists()
