"""Equivalence tests for the directory-mode modelo loader.

The single-file ``modelos/<id>.toml`` layout and the directory-mode
``modelos/<id>/{manifest.toml, revisions/*.toml}`` layout must produce
byte-identical ``ModeloDefinition`` objects from the same TOML data.

This is the safety net for the segmentation migration: by exercising
the round trip
``load_modelo_file(file) == load_modelo_directory(dir-built-from-file)``
on every realistic shape (multi-revision, single-revision, with /
without manifest-level metadata), the migration of any modelo from
single-file to directory layout can be done without behavioral risk.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_origin

import pytest

from .....core.resources import bundled_path
from .. import _loader
from .._errors import RegistryLoadError, RegistryValidationError
from .._loader import (
    discover_modelo_sources,
    load_modelo_directory,
    load_modelo_file,
    load_modelo_source,
    load_registry_tree,
)
from .._schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_REVISION_HEADER_RE = re.compile(r'^\[\[?revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))(?=[.\]])')
_MAX_SINGLE_FILE_MODELO_LINES = 2_000
_MAX_TOML_FRAGMENT_LINES = 1_750
_MAX_TOML_ROW_CHARS = 600


def _build_directory_layout(
    target_dir: Path,
    *,
    manifest_text: str,
    revision_files: dict[str, str],
) -> None:
    """Materialise a directory-mode modelo at ``target_dir``."""

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manifest.toml").write_text(manifest_text, encoding="utf-8")
    revisions_dir = target_dir / "revisions"
    revisions_dir.mkdir(exist_ok=True)
    for filename, content in revision_files.items():
        (revisions_dir / filename).write_text(content, encoding="utf-8")


def _split_single_file_modelo_text(text: str) -> tuple[str, str, dict[str, str]]:
    """Split one modelo TOML into manifest text and revision table text."""

    manifest_lines: list[str] = []
    revision_lines: list[str] = []
    revision_lines_by_id: dict[str, list[str]] = {}
    current_revision_id: str | None = None
    in_revision = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        match = _REVISION_HEADER_RE.match(stripped)
        if stripped.startswith("[revisions") or stripped.startswith("[[revisions"):
            in_revision = True
            if match is None:
                raise AssertionError(f"cannot determine revision id from TOML header {stripped!r}")
            current_revision_id = match.group(1) or match.group(2)
            assert current_revision_id is not None
            revision_lines_by_id.setdefault(current_revision_id, [])
        if in_revision:
            revision_lines.append(line)
            if current_revision_id is None:
                raise AssertionError(f"revision line appeared before a revision header: {line!r}")
            revision_lines_by_id[current_revision_id].append(line)
        else:
            manifest_lines.append(line)

    return (
        "".join(manifest_lines),
        "".join(revision_lines),
        {revision_id: "".join(lines) for revision_id, lines in revision_lines_by_id.items()},
    )


def test_directory_mode_round_trip_matches_every_single_file_modelo(tmp_path: Path) -> None:
    """Every single-file modelo loads byte-identically in directory mode.

    For each real single-file modelo TOML in registry/aeat/modelos/,
    this test builds a temporary directory layout with one revision
    file carrying the original revision tables, then checks it produces
    the same ``ModeloDefinition`` object as the source file.

    Equivalence is at the ``ModeloDefinition`` level — pydantic
    structural equality. Any divergence between the two loaders is a
    blocker for migrating modelos to directory mode.
    """

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    checked: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "single_file":
            continue
        checked.append(source.modelo_id)
        expected = load_modelo_source(source)
        manifest_text, revision_text, _revision_text_by_id = _split_single_file_modelo_text(
            source.path.read_text(encoding="utf-8"),
        )

        target = tmp_path / f"modelo_dir_{source.modelo_id}"
        _build_directory_layout(
            target,
            manifest_text=manifest_text,
            revision_files={"all.toml": revision_text},
        )
        actual = load_modelo_directory(target)
        assert actual == expected, source.modelo_id

    if not checked:
        assert list(modelos_dir.glob("*.toml")) == []


def test_fragment_directory_round_trip_matches_every_single_file_modelo(tmp_path: Path) -> None:
    """Every single-file modelo can be represented as revision fragment directories."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    checked: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "single_file":
            continue
        checked.append(source.modelo_id)
        expected = load_modelo_source(source)
        manifest_text, _revision_text, revision_text_by_id = _split_single_file_modelo_text(
            source.path.read_text(encoding="utf-8"),
        )

        target = tmp_path / f"fragmented_modelo_{source.modelo_id}"
        (target / "revisions").mkdir(parents=True)
        (target / "manifest.toml").write_text(manifest_text, encoding="utf-8")
        for revision_id, revision_text in revision_text_by_id.items():
            revision_dir = target / "revisions" / revision_id
            revision_dir.mkdir()
            (revision_dir / "revision.toml").write_text(revision_text, encoding="utf-8")

        actual = load_modelo_directory(target)
        assert actual == expected, source.modelo_id

    if not checked:
        assert list(modelos_dir.glob("*.toml")) == []


def test_directory_mode_rejects_manifest_with_revisions_table(tmp_path: Path) -> None:
    """The manifest must not declare [revisions] — that lives in revisions/*.toml."""

    target = tmp_path / "bad_manifest"
    target.mkdir()
    (target / "manifest.toml").write_text(
        '[modelo]\nid = "999"\nlabel = "test"\n[revisions."2025"]\n',
        encoding="utf-8",
    )
    (target / "revisions").mkdir()
    with pytest.raises(RegistryLoadError, match="manifest must not declare \\[revisions\\]"):
        load_modelo_directory(target)


def test_directory_mode_rejects_revision_file_with_modelo_table(tmp_path: Path) -> None:
    """A revision file must not redeclare [modelo] — that's manifest-only."""

    target = tmp_path / "bad_revision"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    (target / "revisions").mkdir()
    (target / "revisions" / "2025.toml").write_text(
        '[modelo]\nid = "999"\n[revisions."2025"]\n',
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="must not declare \\[modelo\\]"):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_revision_ids_across_files(tmp_path: Path) -> None:
    """Two revision files cannot both declare the same revision id."""

    target = tmp_path / "duplicate_rev"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    (target / "revisions").mkdir()
    rev_text = '[revisions."2025"]\n[[revisions."2025".casillas]]\nid = "0001"\n'
    (target / "revisions" / "a.toml").write_text(rev_text, encoding="utf-8")
    (target / "revisions" / "b.toml").write_text(rev_text, encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="already declared in another revisions"):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_revision_id_across_file_and_fragment_dir(tmp_path: Path) -> None:
    """A revision id cannot be owned by both ``revisions/<id>.toml`` and ``revisions/<id>/``."""

    target = tmp_path / "duplicate_rev_file_and_dir"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "test"\n', encoding="utf-8")
    revisions_dir = target / "revisions"
    revisions_dir.mkdir()
    (revisions_dir / "2025.toml").write_text('[revisions."2025"]\nvalid_from = 2025-01-01\n', encoding="utf-8")
    (revisions_dir / "2025").mkdir()
    (revisions_dir / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_modelo_directory(target)


def test_directory_mode_loads_plain_revision_file_layout(tmp_path: Path) -> None:
    """A directory modelo can carry a normal ``revisions/<id>.toml`` revision file."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Revision-file test"
official_name = "Revision-file test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions").mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Revision-file test"
official_name = "Revision-file test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_loads_fragmented_revision_layout(tmp_path: Path) -> None:
    """A ``revisions/<id>/`` fragment tree compiles to the same object shape."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
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
    (target / "revisions" / "2025" / "continuidad").mkdir()
    (target / "revisions" / "2025" / "export").mkdir()
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "casillas" / "liquidacion.toml").write_text(
        """
[[revisions."2025".casillas]]
id = "0001"
number = "1"
label = "Base"
section = ["liquidacion"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "continuidad" / "base.toml").write_text(
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
    (target / "revisions" / "2025" / "continuidad" / "cuota.toml").write_text(
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
    (target / "revisions" / "2025" / "export" / "manifest.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "modelo-999-layout"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-001.toml").write_text(
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
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025".completeness_manifest]
source_ref = "aeat-manual"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".completeness_manifest.casillas]]
number = "0001"

[[revisions."2025".completeness_manifest.casillas]]
number = "0002"
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "completeness").mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "completeness" / "manifest.toml").write_text(
        """
[revisions."2025".completeness_manifest]
source_ref = "aeat-manual"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "completeness" / "casillas-0001.toml").write_text(
        """
[[revisions."2025".completeness_manifest.casillas]]
number = "0001"
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "completeness" / "casillas-0002.toml").write_text(
        """
[[revisions."2025".completeness_manifest.casillas]]
number = "0002"
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_merges_export_record_field_fragments_by_record_id(tmp_path: Path) -> None:
    """Large fixed-width records can be split across multiple field fragments."""

    single_file = tmp_path / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
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
    (target / "revisions" / "2025" / "export").mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-a.toml").write_text(
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
    (target / "revisions" / "2025" / "export" / "record-b.toml").write_text(
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
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[[revisions."2025".constructs]]
id = "modelo-999-workflow"
title = "Modelo 999 workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
casillas = ["0001"]
formulas = ["formula-1"]
""".lstrip(),
        encoding="utf-8",
    )
    expected = load_modelo_file(single_file)

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "constructs").mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "constructs" / "casillas.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "modelo-999-workflow"
title = "Modelo 999 workflow"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
casillas = ["0001"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "constructs" / "formulas.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "modelo-999-workflow"
formulas = ["formula-1"]
""".lstrip(),
        encoding="utf-8",
    )

    actual = load_modelo_directory(target)
    assert actual == expected


def test_directory_mode_rejects_export_record_scalar_conflict(tmp_path: Path) -> None:
    """Same-id record fragments must not silently override record metadata."""

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "export").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n',
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-a.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "layout"

[[revisions."2025".export_layouts.records]]
id = "record"
record_type = "1"
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-b.toml").write_text(
        """
[[revisions."2025".export_layouts]]
id = "layout"

[[revisions."2025".export_layouts.records]]
id = "record"
record_type = "2"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="field 'record_type' conflicts"):
        load_modelo_directory(target)


def test_directory_mode_rejects_duplicate_export_field_ids_after_record_merge(tmp_path: Path) -> None:
    """Same-id record fragments must not create ambiguous nested field ids."""

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "export").mkdir(parents=True)
    (target / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Fragment test"
official_name = "Fragment test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "revision.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
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
    (target / "revisions" / "2025" / "export" / "record-a.toml").write_text(
        duplicate_field_fragment,
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "export" / "record-b.toml").write_text(
        duplicate_field_fragment,
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="appends duplicate ids"):
        load_modelo_directory(target)


def test_directory_mode_rejects_construct_scalar_conflict(tmp_path: Path) -> None:
    """Same-id construct fragments must not silently override construct metadata."""

    target = tmp_path / "999"
    (target / "revisions" / "2025" / "constructs").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nvalid_from = 2025-01-01\n',
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "constructs" / "one.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "workflow"
title = "One"
casillas = ["0001"]
""".lstrip(),
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "constructs" / "two.toml").write_text(
        """
[[revisions."2025".constructs]]
id = "workflow"
title = "Two"
formulas = ["formula-1"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="field 'title' conflicts"):
        load_modelo_directory(target)


def test_directory_mode_rejects_fragment_revision_id_mismatch(tmp_path: Path) -> None:
    """Fragments under ``revisions/<id>/`` must declare the same revision id."""

    target = tmp_path / "999"
    (target / "revisions" / "2025").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2024"]\nvalid_from = 2024-01-01\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="expected '2025'"):
        load_modelo_directory(target)


def test_directory_mode_rejects_fragment_scalar_redeclaration(tmp_path: Path) -> None:
    """A fragmented revision has one owner for each scalar revision field."""

    target = tmp_path / "999"
    (target / "revisions" / "2025").mkdir(parents=True)
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\ntitle = "x"\n', encoding="utf-8")
    (target / "revisions" / "2025" / "revision.toml").write_text(
        '[revisions."2025"]\nlabel = "one"\n',
        encoding="utf-8",
    )
    (target / "revisions" / "2025" / "extra.toml").write_text(
        '[revisions."2025"]\nlabel = "two"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="redeclares scalar field 'label'"):
        load_modelo_directory(target)


def test_directory_mode_rejects_missing_manifest(tmp_path: Path) -> None:
    """Directory-mode requires manifest.toml at the root of the modelo dir."""

    target = tmp_path / "no_manifest"
    target.mkdir()
    with pytest.raises(RegistryLoadError, match=r"missing manifest\.toml"):
        load_modelo_directory(target)


def test_directory_mode_rejects_no_revisions(tmp_path: Path) -> None:
    """A directory-mode modelo must have at least one revision file."""

    target = tmp_path / "no_revs"
    target.mkdir()
    (target / "manifest.toml").write_text('[modelo]\nid = "999"\nlabel = "test"\n', encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="no revisions found"):
        load_modelo_directory(target)


def test_committed_registry_tree_loads_directory_modelos() -> None:
    """Registry discovery must load every committed directory-form modelo."""

    registry_root = bundled_path("registry", "aeat")
    modelos_dir = registry_root / "modelos"
    sources = discover_modelo_sources(modelos_dir)
    modelos, _catalogues = load_registry_tree(registry_root)
    loaded_ids = {modelo.id for modelo in modelos}

    assert loaded_ids == {source.modelo_id for source in sources}
    assert {load_modelo_source(source).id for source in sources} == loaded_ids
    assert any(source.layout == "directory" for source in sources)
    assert all(source.layout == "directory" for source in sources)


def test_committed_key_modelos_load_through_generic_fragment_sources() -> None:
    """Key committed modelos use the same generic directory-source contract."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    sources = {source.modelo_id: source for source in discover_modelo_sources(modelos_dir)}

    for modelo_id in ("036", "100", "200", "303"):
        source = sources[modelo_id]
        modelo = load_modelo_source(source)

        assert source.layout == "directory"
        assert source.path.name == modelo_id
        assert modelo.id == modelo_id
        assert source.revision_sources
        assert all(revision_source.layout == "fragment_directory" for revision_source in source.revision_sources)
        assert {revision_source.revision_id for revision_source in source.revision_sources} == set(modelo.revisions)


def test_discovery_rejects_single_file_and_directory_layout_collision(tmp_path: Path) -> None:
    """A modelo id cannot be declared by both supported layouts."""

    modelos_dir = tmp_path / "modelos"
    modelos_dir.mkdir()
    single_file = modelos_dir / "999.toml"
    single_file.write_text(
        """
[modelo]
id = "999"
title = "Collision test"
official_name = "Collision test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]

[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    directory = modelos_dir / "999"
    (directory / "revisions").mkdir(parents=True)
    (directory / "manifest.toml").write_text(
        """
[modelo]
id = "999"
title = "Collision test"
official_name = "Collision test"
tax_domain = "iva"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )
    (directory / "revisions" / "2025.toml").write_text(
        """
[revisions."2025"]
valid_from = 2025-01-01
period_selector = { years = [2025], periods = ["0A"] }
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="also declared"):
        discover_modelo_sources(modelos_dir)


def test_fragmented_modelos_do_not_keep_stale_single_file_siblings() -> None:
    """A fragmented modelo cannot also keep ``modelos/<id>.toml``."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    sources = discover_modelo_sources(modelos_dir)
    offenders = [
        source.modelo_id
        for source in sources
        if source.layout == "directory" and (modelos_dir / f"{source.modelo_id}.toml").exists()
    ]

    assert offenders == []


def test_multi_revision_modelos_do_not_use_single_file_layout() -> None:
    """Multi-revision modelos must use directory layout, not inline copy-per-revision TOML."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    offenders: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "single_file":
            continue
        modelo = load_modelo_source(source)
        if len(modelo.revisions) <= 1:
            continue
        offenders.append(f"{source.modelo_id}: {len(modelo.revisions)} revisions in {source.path.name}")

    assert offenders == []


def test_fragmented_revision_directories_are_schema_owned() -> None:
    """Every committed revision fragment directory has a schema manifest and loads."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    checked: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "directory":
            continue
        modelo = load_modelo_source(source)
        for revision_source in source.revision_sources:
            if revision_source.layout != "fragment_directory":
                continue
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
            assert (revision_source.path / "revision.toml").is_file()
            assert revision_source.revision_id in modelo.revisions
            assert not (source.path / "revisions" / f"{revision_source.revision_id}.toml").exists()

    assert checked, "at least one committed revision must use fragment-directory layout"


def test_committed_directory_source_inventory_lists_every_revision_fragment_toml() -> None:
    """Discovery exposes all TOML fragments that participate in a directory revision."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    checked: list[str] = []
    for source in discover_modelo_sources(modelos_dir):
        if source.layout != "directory":
            continue
        revisions_dir = source.path / "revisions"
        expected_paths = {p for p in revisions_dir.rglob("*.toml") if not any(part == "locales" for part in p.parts)}
        discovered_paths: set[Path] = set()
        for revision_source in source.revision_sources:
            if revision_source.layout == "revision_file":
                assert revision_source.fragment_paths == (revision_source.path,)
            else:
                expected_revision_paths = tuple(
                    sorted(
                        path.resolve()
                        for path in revision_source.path.rglob("*.toml")
                        if not any(part == "locales" for part in path.parts)
                    ),
                )
                assert tuple(sorted(revision_source.fragment_paths)) == expected_revision_paths
            discovered_paths.update(path.resolve() for path in revision_source.fragment_paths)
            checked.append(f"{source.modelo_id}/{revision_source.revision_id}")
        assert discovered_paths == {path.resolve() for path in expected_paths}

    assert checked, "at least one committed directory revision must be discovered"


def test_revision_fragment_merge_contract_covers_repeatable_revision_fields() -> None:
    """Repeatable revision fields must be classified by the fragment compiler."""

    repeatable_revision_fields = {
        field_name
        for field_name, field in ModeloRevision.model_fields.items()
        if field.default == () and get_origin(field.annotation) is tuple
    }
    fragment_merge_fields = {
        *_loader._REVISION_APPEND_ARRAYS,
        _loader._REVISION_CONSTRUCTS,
        _loader._REVISION_EXPORT_LAYOUTS,
    }

    assert repeatable_revision_fields == fragment_merge_fields
    assert _loader._REVISION_COMPLETENESS_MANIFEST in ModeloRevision.model_fields
    assert _loader._REVISION_COMPLETENESS_MANIFEST not in repeatable_revision_fields


def test_locale_translation_fragments_merge_by_language_directory(tmp_path: Path) -> None:
    """Locale directories allow large reviewable language fragments."""

    locales_dir = tmp_path / "locales"
    en_dir = locales_dir / "en"
    en_dir.mkdir(parents=True)
    (en_dir / "001-labels.toml").write_text(
        '[labels]\n"0001" = "One"\n',
        encoding="utf-8",
    )
    (en_dir / "002-help.toml").write_text(
        '[help]\n"0002" = "Two help"\n',
        encoding="utf-8",
    )

    translations = _loader._load_locale_translations(locales_dir)

    assert translations["en"].labels == {"0001": "One"}
    assert translations["en"].help == {"0002": "Two help"}


def test_locale_translation_fragments_reject_duplicate_keys(tmp_path: Path) -> None:
    """Fragmented locale tables must remain unambiguous."""

    locales_dir = tmp_path / "locales"
    en_dir = locales_dir / "en"
    en_dir.mkdir(parents=True)
    (en_dir / "001-labels.toml").write_text(
        '[labels]\n"0001" = "One"\n',
        encoding="utf-8",
    )
    (en_dir / "002-labels.toml").write_text(
        '[labels]\n"0001" = "Uno"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="Duplicate 'en' locale translation keys"):
        _loader._load_locale_translations(locales_dir)


def test_committed_registry_toml_files_stay_reviewable() -> None:
    """Registry TOML files must not regress toward monolithic artifacts."""

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    oversized_single_file_modelos: list[str] = []
    oversized_fragments: list[str] = []
    oversized_rows: list[str] = []

    for path in sorted(modelos_dir.rglob("*.toml")):
        relative_path = path.relative_to(modelos_dir).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        if path.parent == modelos_dir and len(lines) > _MAX_SINGLE_FILE_MODELO_LINES:
            oversized_single_file_modelos.append(
                f"{relative_path}: {len(lines)} lines > {_MAX_SINGLE_FILE_MODELO_LINES}",
            )
        if len(lines) > _MAX_TOML_FRAGMENT_LINES:
            oversized_fragments.append(f"{relative_path}: {len(lines)} lines > {_MAX_TOML_FRAGMENT_LINES}")
        for line_number, line in enumerate(lines, start=1):
            if len(line) <= _MAX_TOML_ROW_CHARS:
                continue
            oversized_rows.append(f"{relative_path}:{line_number}: {len(line)} chars > {_MAX_TOML_ROW_CHARS}")

    assert oversized_single_file_modelos == []
    assert oversized_fragments == []
    assert oversized_rows == []
