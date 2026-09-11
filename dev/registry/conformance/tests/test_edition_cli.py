"""Live CLI proof for the registry ``edition`` development verb.

Two temporary registries hold modelo 303: one exactly as shipped, where every
edition states all of its rows, and one where edition 2025 is re-authored as a
delta on 2024-desde-09-y-3t by deleting every row it states identically to
that predecessor. The reader must print the delta as the edition its full-copy
files declared.

The expected values are read from the full-copy source files themselves, one
casilla fragment block at a time, never from the reader or the loader.

Excluded from equality, and only these:

- ``predecessor`` and the review claim keys (every governance stamp field but
  ``engineered_by``, and ``reviewed_against``): the migration adds the first,
  and a delta's review covers only the rows it states, so the complete edition
  carries no review claim of its own. The review scope is asserted separately.
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
import shutil
import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import REVISION_GOVERNANCE_FIELDS

from ..cli import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_M303 = "303"
_PREDECESSOR = "2024-desde-09-y-3t"
_SUCCESSOR = "2025"
_REFUSED_EXIT_CODE = 2
_EXCLUDED_EDITION_KEYS = (REVISION_GOVERNANCE_FIELDS - {"engineered_by"}) | {"predecessor", "reviewed_against"}
_EXCLUDED_ROW_KEYS = frozenset({"export_refs"})
_CASILLA_ROW_HEADER = re.compile(r'^\[\[revisions\.(?:"[^"\n]+"|[^".\]\n]+)\.casillas\]\]$', re.MULTILINE)


def _split_casilla_rows(text: str) -> tuple[str, list[str]]:
    starts = [match.start() for match in _CASILLA_ROW_HEADER.finditer(text)]
    if not starts:
        return text, []
    bounds = [*starts, len(text)]
    return text[: starts[0]], [text[bounds[index] : bounds[index + 1]] for index in range(len(starts))]


def _row_of(block: str) -> dict[str, object]:
    (revision,) = tomllib.loads(block)["revisions"].values()
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
    (revision,) = tomllib.loads((edition_dir / "revision.toml").read_text(encoding="utf-8"))["revisions"].values()
    return dict(revision)


def _edition_dir(registry_root: Path, revision_id: str) -> Path:
    return registry_root / "modelos" / _M303 / "revisions" / revision_id


def _declare(edition_dir: Path, declaration: str) -> None:
    manifest = edition_dir / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    name = re.escape(edition_dir.name)
    match = re.compile(rf'^\[revisions\.(?:"{name}"|{name})\]\n', re.MULTILINE).search(text)
    assert match is not None, manifest
    manifest.write_text(text[: match.end()] + declaration + text[match.end() :], encoding="utf-8", newline="\n")


def _migrate(registry_root: Path) -> frozenset[str]:
    """Re-author the successor as a delta: drop every row it states identically to the predecessor."""
    predecessor_rows = {
        row["continuidad_id"]: row
        for row in _file_rows(_edition_dir(registry_root, _PREDECESSOR))
        if row.get("continuidad_id") is not None
    }
    successor_dir = _edition_dir(registry_root, _SUCCESSOR)
    inherited = frozenset(
        str(row["id"])
        for row in _file_rows(successor_dir)
        if row.get("continuidad_id") is not None and predecessor_rows.get(row["continuidad_id"]) == row
    )
    editions = sorted(
        (path for path in (registry_root / "modelos" / _M303 / "revisions").iterdir()),
        key=lambda path: str(_manifest(path)["valid_from"]),
    )
    for edition_dir in editions[1:]:
        manifest = _manifest(edition_dir)
        if edition_dir.name == _SUCCESSOR:
            reviewed = manifest.get("review_status", "pending_review") != "pending_review"
            scope = f'reviewed_against = "{_PREDECESSOR}"\n' if reviewed else ""
            _declare(edition_dir, f'predecessor = "{_PREDECESSOR}"\n{scope}')
            continue
        legal_refs, source_refs = manifest["legal_refs"], manifest["source_refs"]
        assert isinstance(legal_refs, list) and isinstance(source_refs, list)
        _declare(
            edition_dir,
            'predecessor = { none = { reason = "Authored as its own full copy; it inherits from no sibling edition.", '
            f'legal_refs = ["{legal_refs[0]}"], source_refs = ["{source_refs[0]}"] }} }}\n',
        )
    for fragment in sorted((successor_dir / "casillas").glob("*.toml")):
        preamble, blocks = _split_casilla_rows(fragment.read_text(encoding="utf-8"))
        kept = [block for block in blocks if str(_row_of(block)["id"]) not in inherited]
        if len(kept) == len(blocks):
            continue
        if kept:
            fragment.write_text(preamble + "".join(kept), encoding="utf-8", newline="\n")
        else:
            fragment.unlink()
    return inherited


@pytest.fixture(scope="module")
def full_copy_registry(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("full-copy") / "registry"
    shutil.copytree(bundled_path("registry", "aeat", "modelos", _M303), root / "modelos" / _M303)
    return root


@pytest.fixture(scope="module")
def migrated_registry(
    full_copy_registry: Path, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, frozenset[str]]:
    root = tmp_path_factory.mktemp("migrated") / "registry"
    shutil.copytree(full_copy_registry, root)
    return root, _migrate(root)


def _view(registry_root: Path, modelo: str, revision: str, *, output_format: str = "text") -> Result:
    arguments = ["edition", modelo, revision, "--registry-root", str(registry_root)]
    return CliRunner().invoke(app, [*arguments, "--json"] if output_format == "json" else arguments)


def _rendered_edition(result: Result, revision: str) -> dict[str, object]:
    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    return dict(tomllib.loads(result.stdout)["revisions"][revision])


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


def test_a_migrated_edition_renders_identically_to_its_pre_migration_files(
    full_copy_registry: Path, migrated_registry: tuple[Path, frozenset[str]]
) -> None:
    migrated_root, inherited = migrated_registry
    full_copy_dir = _edition_dir(full_copy_registry, _SUCCESSOR)
    # Non-vacuity: rows really left the delta's files and can only come back by inheritance.
    assert inherited
    assert not inherited & {str(row["id"]) for row in _file_rows(_edition_dir(migrated_root, _SUCCESSOR))}

    result = _view(migrated_root, _M303, _SUCCESSOR)
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
    full_copy_rendered = _rendered_edition(_view(full_copy_registry, _M303, _SUCCESSOR), _SUCCESSOR)
    excluded = _EXCLUDED_EDITION_KEYS | {"casillas"}
    assert _without(rendered, excluded) == _without(full_copy_rendered, excluded)
    assert "predecessor" not in rendered
    assert rendered["review_status"] == "pending_review"
    rendered_rows = rendered["casillas"]
    assert isinstance(rendered_rows, list)
    assert _row_markers(result.stdout) == [
        f"row: casilla={row['id']} source=inherited inherited_from={_PREDECESSOR}"
        if row["id"] in inherited
        else f"row: casilla={row['id']} source=stated"
        for row in rendered_rows
    ]


def test_the_json_form_reports_row_provenance_and_the_review_scope(
    full_copy_registry: Path, migrated_registry: tuple[Path, frozenset[str]]
) -> None:
    migrated_root, inherited = migrated_registry
    text = _view(migrated_root, _M303, _SUCCESSOR)

    result = _view(migrated_root, _M303, _SUCCESSOR, output_format="json")

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["document"] == text.stdout
    assert payload["inherits_from"] == _PREDECESSOR
    rows = payload["rows"]
    assert {row["casilla_id"] for row in rows if row["source"] == "inherited"} == inherited
    assert {row["inherited_from"] for row in rows if row["source"] == "inherited"} == {_PREDECESSOR}
    assert {row["casilla_id"] for row in rows if row["source"] == "stated"} == {
        str(row["id"]) for row in _file_rows(_edition_dir(migrated_root, _SUCCESSOR))
    }
    declared_status = _manifest(_edition_dir(full_copy_registry, _SUCCESSOR))["review_status"]
    assert declared_status != "pending_review"
    assert payload["review_scope"] == {
        "declared_review_status": declared_status,
        "coverage": "stated_rows",
        "reviewed_against": _PREDECESSOR,
        "rendered_review_status": "pending_review",
        "inherited_attestations": [
            {
                "revision_id": _PREDECESSOR,
                "row_count": len(inherited),
                "review_status": _manifest(_edition_dir(full_copy_registry, _PREDECESSOR))["review_status"],
            },
        ],
    }
    assert f"# review: declared_status={declared_status} coverage=stated_rows" in text.stdout


def test_an_unmigrated_edition_renders_identically_to_its_files(full_copy_registry: Path) -> None:
    edition_dir = _edition_dir(full_copy_registry, _SUCCESSOR)

    result = _view(full_copy_registry, _M303, _SUCCESSOR)
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
    full_copy_registry: Path, migrated_registry: tuple[Path, frozenset[str]]
) -> None:
    migrated_root, inherited = migrated_registry
    full_copy_dir = _edition_dir(full_copy_registry, _SUCCESSOR)
    rendered = _rendered_edition(_view(migrated_root, _M303, _SUCCESSOR), _SUCCESSOR)
    declared_only = {**rendered, "casillas": _file_rows(_edition_dir(migrated_root, _SUCCESSOR))}

    differences = _edition_differences(
        declared_only,
        file_rows=_file_rows(full_copy_dir),
        manifest=_manifest(full_copy_dir),
        excluded_keys=_EXCLUDED_EDITION_KEYS,
    )

    assert differences == [f"missing row {row_id}" for row_id in sorted(inherited)]


@pytest.mark.parametrize(
    ("modelo", "revision", "condition_id", "refused_context"),
    [
        ("998", _SUCCESSOR, "registry.edition.modelo.declared", {"modelo": "998"}),
        (_M303, "1999", "registry.edition.revision.declared", {"modelo": _M303, "revision": "1999"}),
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
