"""Live CLI proof for the registry ``edition`` development verb.

One modelo is authored twice by this module: a tree where edition 2025 states
every row it stands for, and a tree where the same edition is authored as a
delta on 2024, stating only the row it changes and the row it adds. The reader
must print the delta as the edition its full-copy files declare.

The expected values are read from the full-copy source files themselves, one
casilla fragment block at a time, never from the reader or the loader. The
modelo is authored here rather than copied from the bundled registry because
the bundled modelos are themselves delta-authored: a copied tree has no
full-copy edition left to compare against, and the fixture cannot re-derive
one without borrowing the materialiser this gate exists to judge.

Excluded from equality, and only these:

- ``predecessor`` and ``reviewed_against``: the delta tree declares the first,
  which materialisation removes, and the second, whose review scope is
  asserted separately.
- ``export_refs`` on casilla rows, which the registry derives from export
  layouts, so a rendering may carry it whether or not the files state it.
- the ``#`` provenance comments the reader adds, which a TOML parser drops;
  they are asserted separately, line by line.
- casilla row order: a delta edition keeps its predecessor's order and appends
  new rows, so rows are compared by id.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from cadrumo.core.toml import parse_toml

from ..cli import app
from ..loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_MODELO = "999"
_PREDECESSOR = "2024"
_SUCCESSOR = "2025"
_REFUSED_EXIT_CODE = 2
_REVIEW_STATUS = "agent_reviewed"
_EXCLUDED_EDITION_KEYS = frozenset({"predecessor", "reviewed_against"})
_EXCLUDED_ROW_KEYS = frozenset({"export_refs"})
_LEGAL_REF = "ley-58-2003:art-29"
_SOURCE_REF = "aeat-manual"
_CASILLA_ROW_HEADER = re.compile(r'^\[\[revisions\.(?:"[^"\n]+"|[^".\]\n]+)\.casillas\]\]$', re.MULTILINE)

#: The governance stamp both trees declare on every edition. A reviewed
#: edition is what makes the review-scope reporting observable at all.
_STAMP = (
    'engineered_by = "agent:author"\n'
    f'review_status = "{_REVIEW_STATUS}"\n'
    'reviewed_by = "agent:reviewer"\n'
    "reviewed_at = 2026-09-10\n"
)


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "{lineage}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _write_edition(modelo_dir: Path, revision_id: str, *, year: int, fragments: Mapping[str, str], extra: str) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    (revision_dir / "casillas").mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f"{_STAMP}{extra}",
        encoding="utf-8",
        newline="\n",
    )
    for name, text in fragments.items():
        (revision_dir / "casillas" / name).write_text(text, encoding="utf-8", newline="\n")


def _predecessor_fragments() -> dict[str, str]:
    return {
        "c0001__c0002.toml": _casilla(_PREDECESSOR, "1", number="1", lineage="base")
        + _casilla(_PREDECESSOR, "2", number="2", lineage="cuota"),
        "c0003.toml": _casilla(_PREDECESSOR, "3", number="3", lineage="deduccion"),
    }


def _full_copy_fragments() -> dict[str, str]:
    """The successor stated in full: two rows restated verbatim, one changed, one new."""
    return {
        "c0001__c0002__c0003.toml": _casilla(_SUCCESSOR, "1", number="1", lineage="base")
        + _casilla(_SUCCESSOR, "2", number="22", lineage="cuota")
        + _casilla(_SUCCESSOR, "3", number="3", lineage="deduccion"),
        "c0005.toml": _casilla(_SUCCESSOR, "5", number="5", lineage="recargo"),
    }


def _delta_fragments() -> dict[str, str]:
    """The same edition as a delta: only the changed row and the new one."""
    return {
        "c0002__c0005.toml": _casilla(_SUCCESSOR, "2", number="22", lineage="cuota")
        + _casilla(_SUCCESSOR, "5", number="5", lineage="recargo"),
    }


def _write_registry(root: Path, *, delta: bool) -> Path:
    modelo_dir = root / "modelos" / _MODELO
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Test")
    _write_edition(modelo_dir, _PREDECESSOR, year=2024, fragments=_predecessor_fragments(), extra="")
    _write_edition(
        modelo_dir,
        _SUCCESSOR,
        year=2025,
        fragments=_delta_fragments() if delta else _full_copy_fragments(),
        extra=f'predecessor = "{_PREDECESSOR}"\nreviewed_against = "{_PREDECESSOR}"\n' if delta else "",
    )
    return root


def _split_casilla_rows(text: str) -> tuple[str, list[str]]:
    starts = [match.start() for match in _CASILLA_ROW_HEADER.finditer(text)]
    if not starts:
        return text, []
    bounds = [*starts, len(text)]
    return text[: starts[0]], [text[bounds[index] : bounds[index + 1]] for index in range(len(starts))]


def _row_of(block: str) -> dict[str, object]:
    (revision,) = parse_toml(block)["revisions"].values()
    (row,) = revision["casillas"]
    return dict(row)


def _file_rows(edition_dir: Path) -> list[dict[str, object]]:
    """Every casilla row the edition's own fragment files state, in file order."""
    return [
        _row_of(block)
        for fragment in sorted((edition_dir / "casillas").glob("*.toml"))
        for block in _split_casilla_rows(fragment.read_text(encoding="utf-8"))[1]
    ]


def _manifest(edition_dir: Path) -> dict[str, object]:
    (revision,) = parse_toml((edition_dir / "revision.toml").read_text(encoding="utf-8"))["revisions"].values()
    return dict(revision)


def _edition_dir(registry_root: Path, revision_id: str) -> Path:
    return registry_root / "modelos" / _MODELO / "revisions" / revision_id


@pytest.fixture(scope="module")
def full_copy_registry(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _write_registry(tmp_path_factory.mktemp("full-copy") / "registry", delta=False)


@pytest.fixture(scope="module")
def delta_registry(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _write_registry(tmp_path_factory.mktemp("delta") / "registry", delta=True)


@pytest.fixture(scope="module")
def inherited_rows(full_copy_registry: Path, delta_registry: Path) -> frozenset[str]:
    """The rows the delta drops, which can only come back by inheritance."""
    stated = {str(row["id"]) for row in _file_rows(_edition_dir(delta_registry, _SUCCESSOR))}
    return frozenset(str(row["id"]) for row in _file_rows(_edition_dir(full_copy_registry, _SUCCESSOR))) - stated


def _view(registry_root: Path, modelo: str, revision: str, *, output_format: str = "text") -> Result:
    arguments = ["edition", modelo, revision, "--registry-root", str(registry_root)]
    return CliRunner().invoke(app, [*arguments, "--json"] if output_format == "json" else arguments)


def _rendered_edition(result: Result, revision: str) -> dict[str, object]:
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    return dict(parse_toml(result.stdout)["revisions"][revision])


def _comparable_row(row: object) -> dict[str, object]:
    assert isinstance(row, dict), row
    return {key: value for key, value in row.items() if key not in _EXCLUDED_ROW_KEYS}


def _edition_differences(
    rendered: Mapping[str, object],
    *,
    file_rows: list[dict[str, object]],
    manifest: Mapping[str, object],
    excluded_keys: frozenset[str],
) -> list[str]:
    """Every way a rendered edition departs from the files that declare it in full."""
    rendered_rows = rendered.get("casillas", [])
    assert isinstance(rendered_rows, list)
    by_id = {str(row["id"]): _comparable_row(row) for row in rendered_rows}
    expected = {str(row["id"]): _comparable_row(row) for row in file_rows}
    differences = [f"missing row {row_id}" for row_id in sorted(expected.keys() - by_id.keys())]
    differences += [f"unexpected row {row_id}" for row_id in sorted(by_id.keys() - expected.keys())]
    differences += [
        f"changed row {row_id}"
        for row_id in sorted(expected.keys() & by_id.keys())
        if expected[row_id] != by_id[row_id]
    ]
    if len(rendered_rows) != len(by_id):
        differences.append("duplicate row ids")
    differences += [
        f"changed field {key}"
        for key, value in manifest.items()
        if key not in excluded_keys and rendered.get(key) != value
    ]
    return differences


def _without(table: Mapping[str, object], keys: frozenset[str]) -> dict[str, object]:
    return {key: value for key, value in table.items() if key not in keys}


def _row_markers(stdout: str) -> list[str]:
    return [line.removeprefix("# ") for line in stdout.splitlines() if line.startswith("# row: ")]


def test_a_delta_edition_renders_identically_to_its_full_copy_files(
    full_copy_registry: Path, delta_registry: Path, inherited_rows: frozenset[str]
) -> None:
    full_copy_dir = _edition_dir(full_copy_registry, _SUCCESSOR)
    # Non-vacuity: rows really are absent from the delta's files and can only come back by inheritance.
    assert inherited_rows
    assert not inherited_rows & {str(row["id"]) for row in _file_rows(_edition_dir(delta_registry, _SUCCESSOR))}

    result = _view(delta_registry, _MODELO, _SUCCESSOR)
    rendered = _rendered_edition(result, _SUCCESSOR)

    assert (
        _edition_differences(
            rendered,
            file_rows=_file_rows(full_copy_dir),
            manifest=_manifest(full_copy_dir),
            excluded_keys=_EXCLUDED_EDITION_KEYS,
        )
        == []
    )
    # Every family beyond the casillas is declared in full by both trees, so
    # the whole table matches the full copy's own rendering.
    full_copy_rendered = _rendered_edition(_view(full_copy_registry, _MODELO, _SUCCESSOR), _SUCCESSOR)
    excluded = _EXCLUDED_EDITION_KEYS | {"casillas"}
    assert _without(rendered, excluded) == _without(full_copy_rendered, excluded)
    assert "predecessor" not in rendered
    # Materialisation removes the inheritance edge, never the review it records.
    assert rendered["review_status"] == _REVIEW_STATUS
    rendered_rows = rendered["casillas"]
    assert isinstance(rendered_rows, list)
    assert _row_markers(result.stdout) == [
        f"row: casilla={row['id']} source=inherited inherited_from={_PREDECESSOR}"
        if row["id"] in inherited_rows
        else f"row: casilla={row['id']} source=stated"
        for row in rendered_rows
    ]


def test_the_json_form_reports_row_provenance_and_the_review_scope(
    delta_registry: Path, inherited_rows: frozenset[str]
) -> None:
    text = _view(delta_registry, _MODELO, _SUCCESSOR)

    result = _view(delta_registry, _MODELO, _SUCCESSOR, output_format="json")

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["document"] == text.stdout
    assert payload["inherits_from"] == _PREDECESSOR
    rows = payload["rows"]
    assert {row["casilla_id"] for row in rows if row["source"] == "inherited"} == inherited_rows
    assert {row["inherited_from"] for row in rows if row["source"] == "inherited"} == {_PREDECESSOR}
    assert {row["casilla_id"] for row in rows if row["source"] == "stated"} == {
        str(row["id"]) for row in _file_rows(_edition_dir(delta_registry, _SUCCESSOR))
    }
    assert payload["review_scope"] == {
        "declared_review_status": _REVIEW_STATUS,
        "coverage": "stated_rows",
        "reviewed_against": _PREDECESSOR,
        "rendered_review_status": _REVIEW_STATUS,
        "inherited_attestations": [
            {"revision_id": _PREDECESSOR, "row_count": len(inherited_rows), "review_status": _REVIEW_STATUS},
        ],
    }
    assert f"# review: declared_status={_REVIEW_STATUS} coverage=stated_rows" in text.stdout


def test_a_full_copy_edition_renders_identically_to_its_files(full_copy_registry: Path) -> None:
    edition_dir = _edition_dir(full_copy_registry, _SUCCESSOR)

    result = _view(full_copy_registry, _MODELO, _SUCCESSOR)
    rendered = _rendered_edition(result, _SUCCESSOR)

    # Nothing is excluded but derived export references: an edition stating
    # every row keeps its review stamp, because its table is the stamp's scope.
    assert (
        _edition_differences(
            rendered, file_rows=_file_rows(edition_dir), manifest=_manifest(edition_dir), excluded_keys=frozenset()
        )
        == []
    )
    rendered_rows = rendered["casillas"]
    assert isinstance(rendered_rows, list)
    assert _row_markers(result.stdout) == [f"row: casilla={row['id']} source=stated" for row in rendered_rows]
    assert "coverage=complete_edition" in result.stdout


def test_rendering_only_the_rows_a_delta_declares_is_detected(
    full_copy_registry: Path, delta_registry: Path, inherited_rows: frozenset[str]
) -> None:
    full_copy_dir = _edition_dir(full_copy_registry, _SUCCESSOR)
    rendered = _rendered_edition(_view(delta_registry, _MODELO, _SUCCESSOR), _SUCCESSOR)
    declared_only = {**rendered, "casillas": _file_rows(_edition_dir(delta_registry, _SUCCESSOR))}

    differences = _edition_differences(
        declared_only,
        file_rows=_file_rows(full_copy_dir),
        manifest=_manifest(full_copy_dir),
        excluded_keys=_EXCLUDED_EDITION_KEYS,
    )

    assert differences == [f"missing row {row_id}" for row_id in sorted(inherited_rows)]


@pytest.mark.parametrize(
    ("modelo", "revision", "condition_id", "refused_context"),
    [
        ("998", _SUCCESSOR, "registry.edition.modelo.declared", {"modelo": "998"}),
        (_MODELO, "1999", "registry.edition.revision.declared", {"modelo": _MODELO, "revision": "1999"}),
    ],
)
def test_an_unknown_modelo_or_edition_is_refused_on_the_error_channel(
    full_copy_registry: Path, modelo: str, revision: str, condition_id: str, refused_context: dict[str, str]
) -> None:
    text = _view(full_copy_registry, modelo, revision)

    assert text.exit_code == _REFUSED_EXIT_CODE
    assert text.stdout == ""
    assert f"status=refused\tcondition={condition_id}" in text.stderr
    assert all(f"{key}={value}" in text.stderr for key, value in refused_context.items())

    result = _view(full_copy_registry, modelo, revision, output_format="json")

    assert result.exit_code == _REFUSED_EXIT_CODE
    assert result.stdout == ""
    refusal = json.loads(result.stderr)
    assert refusal["status"] == "refused"
    assert refusal["failed_condition_id"] == condition_id
    assert refusal["context"].items() >= refused_context.items()
