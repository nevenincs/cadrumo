"""Fragment-directory behavior for the modelo loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from .._loader_internals import _revision_section_fragment_paths, load_modelo_file
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory
from ._loader_directory_mode_support import (
    _COMPLETENESS_CASILLA_0001,
    _COMPLETENESS_CASILLA_0002,
    _TOML_CASILLA_ID_KEY,
    _minimal_fragment_revision_layout,
    _standard_manifest_text,
    _standard_revision_preamble_text,
    _write_standard_manifest,
    _write_standard_revision_preamble,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("slot_literal", ['"1"', "1.0", "true"])
def test_registry_loader_refuses_projection_slot_coercion(tmp_path: Path, slot_literal: str) -> None:
    registry_file = tmp_path / "999.toml"
    registry_file.write_text(
        _standard_manifest_text("Projection compiler proof")
        + "\n"
        + _standard_revision_preamble_text()
        + f"""

[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-projection"
offset = 1
length = 3
kind = "projection"
data_type = "text"
required = false
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025".export_layouts.records.fields.projection_ref]
projection_kind = "m303_prorrata_activity"
slot = {slot_literal}
field = "cnae"
casilla_id = "500"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="exact integer"):
        load_modelo_file(registry_file)


def test_directory_mode_loads_fragmented_revision_layout(tmp_path: Path) -> None:
    """A ``revisions/<id>/`` fragment tree compiles to the same object shape."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Fragment test")
        + "\n"
        + _standard_revision_preamble_text()
        + """

[[revisions."2025".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casilla_continuidad_evolutions]]
id = "continuidad-base-2025"
continuidad_id = "base"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "unchanged"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casilla_continuidad_evolutions]]
id = "continuidad-cuota-2025"
continuidad_id = "cuota"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "label_evolved"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "casillas").mkdir(parents=True)
    (target / "revisions" / "2025" / "casilla_continuidad_evolutions").mkdir()
    (target / "revisions" / "2025" / "export_layouts").mkdir()
    _write_standard_manifest(target, "Fragment test")
    _write_standard_revision_preamble(target / "revisions" / "2025" / "revision.toml")
    (target / "revisions" / "2025" / "casillas" / "liquidacion.toml").write_text(
        """
[[revisions."2025".casillas]]
id = "0001"
number = "1"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "casilla_continuidad_evolutions" / "base.toml").write_text(
        """
[[revisions."2025".casilla_continuidad_evolutions]]
id = "continuidad-base-2025"
continuidad_id = "base"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "unchanged"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "casilla_continuidad_evolutions" / "cuota.toml").write_text(
        """
[[revisions."2025".casilla_continuidad_evolutions]]
id = "continuidad-cuota-2025"
continuidad_id = "cuota"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "label_evolved"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export_layouts" / "0001-manifest.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export_layouts" / "0002-record-001.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_merges_completeness_manifest_casilla_fragments(tmp_path: Path) -> None:
    """Large calculation-completeness manifests can split their casilla list."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        (
            _standard_manifest_text("Fragment test")
            + "\n"
            + _standard_revision_preamble_text()
            + """

[revisions."2025".completeness_manifest]
source_ref = "aeat-manual"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".completeness_manifest.casillas]]
"""
            + f'{_TOML_CASILLA_ID_KEY} = "{_COMPLETENESS_CASILLA_0001}"\n'
            + """
number = "0001"

[[revisions."2025".completeness_manifest.casillas]]
"""
            + f'{_TOML_CASILLA_ID_KEY} = "{_COMPLETENESS_CASILLA_0002}"\n'
            + """
number = "0002"
"""
        ).lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "completeness_manifest").mkdir(parents=True)
    _write_standard_manifest(target, "Fragment test")
    _write_standard_revision_preamble(target / "revisions" / "2025" / "revision.toml")
    (target / "revisions" / "2025" / "completeness_manifest" / "0001-manifest.toml").write_text(
        """
[revisions."2025".completeness_manifest]
source_ref = "aeat-manual"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "completeness_manifest" / "0002-casillas-0001.toml").write_text(
        (
            """
[[revisions."2025".completeness_manifest.casillas]]
"""
            + f'{_TOML_CASILLA_ID_KEY} = "{_COMPLETENESS_CASILLA_0001}"\n'
            + """
number = "0001"
"""
        ).lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "completeness_manifest" / "0003-casillas-0002.toml").write_text(
        (
            """
[[revisions."2025".completeness_manifest.casillas]]
"""
            + f'{_TOML_CASILLA_ID_KEY} = "{_COMPLETENESS_CASILLA_0002}"\n'
            + """
number = "0002"
"""
        ).lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_merges_export_record_field_fragments_by_record_id(tmp_path: Path) -> None:
    """Large fixed-width records can be split across multiple field fragments."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Fragment test")
        + "\n"
        + _standard_revision_preamble_text()
        + """

[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-field-a"
offset = 1
length = 1
kind = "literal"
literal = "A"
data_type = "text"
required = true
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-field-b"
offset = 2
length = 1
kind = "literal"
literal = "B"
data_type = "text"
required = true
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "export_layouts").mkdir(parents=True)
    _write_standard_manifest(target, "Fragment test")
    _write_standard_revision_preamble(target / "revisions" / "2025" / "revision.toml")
    (target / "revisions" / "2025" / "export_layouts" / "0001-record-a.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "crlf"
required = true

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-field-a"
offset = 1
length = 1
kind = "literal"
literal = "A"
data_type = "text"
required = true
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export_layouts" / "0002-record-b.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-field-b"
offset = 2
length = 1
kind = "literal"
literal = "B"
data_type = "text"
required = true
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_merges_construct_member_fragments_by_construct_id(tmp_path: Path) -> None:
    """Large construct membership lists can be split without redeclaring the construct."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        _standard_manifest_text("Fragment test")
        + "\n"
        + _standard_revision_preamble_text()
        + """

[[revisions."2025".constructs]]
id = "modelo-999-workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
casilla_ids = ["0001"]
formulas = ["formula-1"]
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "constructs").mkdir(parents=True)
    _write_standard_manifest(target, "Fragment test")
    _write_standard_revision_preamble(target / "revisions" / "2025" / "revision.toml")
    (target / "revisions" / "2025" / "constructs" / "0001-casillas.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "modelo-999-workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
casilla_ids = ["0001"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "constructs" / "0002-formulas.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "modelo-999-workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
formulas = ["formula-1"]
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


@pytest.mark.parametrize(
    ("fragment_dir", "fragment_files", "error_match"),
    (
        pytest.param(
            "export_layouts",
            (
                (
                    "0001-record-a.toml",
                    """
[[revisions."2025".export_layouts]]
id = "layout"

[[revisions."2025".export_layouts.records]]
id = "record"
record_type = "1"
""".lstrip(),
                ),
                (
                    "0002-record-b.toml",
                    """
[[revisions."2025".export_layouts]]
id = "layout"

[[revisions."2025".export_layouts.records]]
id = "record"
record_type = "2"
""".lstrip(),
                ),
            ),
            "field 'record_type' conflicts",
            id="export-record-metadata",
        ),
        pytest.param(
            "constructs",
            (
                (
                    "0001-one.toml",
                    """
[[revisions."2025".constructs]]
id = "workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
casilla_ids = ["0001"]
""".lstrip(),
                ),
                (
                    "0002-two.toml",
                    """
[[revisions."2025".constructs]]
id = "workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["other-source"]
formulas = ["formula-1"]
""".lstrip(),
                ),
            ),
            "field 'source_refs' conflicts",
            id="construct-metadata",
        ),
    ),
)
def test_directory_mode_rejects_fragment_scalar_conflicts(
    tmp_path: Path,
    fragment_dir: str,
    fragment_files: tuple[tuple[str, str], ...],
    error_match: str,
) -> None:
    """Same-id fragments must not silently override scalar metadata."""

    target = tmp_path / "999"
    revision_dir = _minimal_fragment_revision_layout(target, fragment_dirs=(fragment_dir,))
    for filename, fragment_text in fragment_files:
        (revision_dir / fragment_dir / filename).write_text(fragment_text, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match=error_match):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_export_field_ids_after_record_merge(tmp_path: Path) -> None:
    """Same-id record fragments must not create ambiguous nested field ids."""

    target = tmp_path / "999"
    export_dir = _minimal_fragment_revision_layout(target, fragment_dirs=("export_layouts",)) / "export_layouts"
    duplicate_field_fragment = """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".export_layouts.records]]
id = "modelo-999-record"
record_type = "1"
order = 0
encoding = "latin-1"
line_ending = "none"
required = true

[[revisions."2025".export_layouts.records.fields]]
id = "modelo-999-field"
offset = 1
length = 1
kind = "literal"
literal = "A"
data_type = "text"
required = true
padding = "right_space"
justification = "left"
signed = false
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip()
    (export_dir / "0001-record-a.toml").write_text(
        duplicate_field_fragment,
        encoding="utf-8",
    )
    (export_dir / "0002-record-b.toml").write_text(
        duplicate_field_fragment,
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="appends duplicate ids"):
        load_modelo_directory(target)


def test_a_section_holding_only_a_nested_fragment_is_refused_as_empty(tmp_path: Path) -> None:
    """ "Is this section populated" is answered by the files it actually contributes.

    The emptiness refusal and the fragment collection are one listing in
    ``_revision_section_fragment_paths``, so a section cannot be called
    "populated" by one and read as empty by the other. This exercises the
    collector directly, bypassing ``_validate_section_fragment_names``'s
    categorical refusal of ANY nested section subdirectory in
    ``loader_cache.py`` (which makes this scenario unreachable through the
    full ``load_modelo_directory`` pipeline), to prove the one-level reading
    holds standalone: a section directory holding ONLY a nested fragment
    contributes nothing and is refused, rather than passing as populated on
    a file the merge would never read.
    """
    section_dir = tmp_path / "casillas"
    section_dir.mkdir()
    nested = section_dir / "nested"
    nested.mkdir()
    (nested / "extra.toml").write_text('[[revisions."2025".casillas]]\nid = "0001"\n', encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="contains no TOML fragments"):
        _revision_section_fragment_paths((section_dir,))


def test_directory_mode_rejects_fragment_revision_id_mismatch(tmp_path: Path) -> None:
    """Fragments under ``revisions/<id>/`` must declare the same revision id."""

    target = tmp_path / "999"
    _minimal_fragment_revision_layout(
        target,
        revision_text='[revisions."2024"]\nvalid_from = 2024-01-01\n',
    )

    with pytest.raises(RegistryLoadError, match="expected '2025'"):
        load_modelo_directory(target)


def test_directory_mode_rejects_fragment_scalar_redeclaration(tmp_path: Path) -> None:
    """A fragmented revision has one owner for each scalar revision field."""

    target = tmp_path / "999"
    revision_dir = _minimal_fragment_revision_layout(
        target,
        revision_text='[revisions."2025"]\nvalid_from = 2025-01-01\n',
    )
    (revision_dir / "extra.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-02-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="must live in its owned section subdirectory"):
        load_modelo_directory(target)
