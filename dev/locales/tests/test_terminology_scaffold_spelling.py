"""Scaffold markers remain backlog without masquerading as authored prose."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.terminology_handbook.curation import audit_handbook

from ..signal_parallel_inventory import parallel_localization_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MARKER = "(sin curar) draft pendiente de definicion"
_CONCEPTS = "src/cadrumo/_data/terminology/concepts"


def _write_concept(
    repository: Path,
    *,
    lifecycle: str | None = "draft",
    relative: str = f"{_CONCEPTS}/term.toml",
    concept_id: str = "term",
    locale: str = "es",
    field: str = "short_description",
    value: str = _MARKER,
) -> Path:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_line = f"lifecycle = '{lifecycle}'\n" if lifecycle is not None else ""
    path.write_text(
        f"[concept]\nconcept_id = '{concept_id}'\ndomain = 'concepto'\n"
        f"{lifecycle_line}created_at = 2026-06-10\nupdated_at = 2026-06-10\n"
        f"[language.{locale}]\n{field} = '{value}'\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("lifecycle", ["draft", "deprecated", "retired"])
def test_exact_nonapproved_marker_keeps_inventory_but_skips_spelling(tmp_path: Path, lifecycle: str) -> None:
    _write_concept(tmp_path, lifecycle=lifecycle)
    values: dict[str, dict[str, str]] = {}

    inventory, findings = parallel_localization_inventory(tmp_path, spelling_values=values)

    assert values == {}
    assert inventory["parallel_localization_cells"] == 4
    assert inventory["parallel_localization_declarations"] == 3
    assert {finding["detail"] for finding in findings if finding["kind"] == "parallel_translation_missing"} == {
        "ca",
        "en",
        "hu",
    }


def test_draft_marker_remains_visible_in_curation_backlog(tmp_path: Path) -> None:
    path = _write_concept(tmp_path)

    report = audit_handbook(path.parent)

    assert report.draft_count == 1
    assert report.empty_short_description == {"term": ("es",)}


@pytest.mark.parametrize("lifecycle", ["draft", "deprecated", "retired", "approved"])
@pytest.mark.parametrize("value", ["Descripcion fiscal sin acento", _MARKER + ".", " " + _MARKER])
def test_authored_prose_in_every_lifecycle_remains_spellchecked(tmp_path: Path, lifecycle: str, value: str) -> None:
    path = _write_concept(tmp_path, lifecycle=lifecycle, value=value)
    values: dict[str, dict[str, str]] = {}

    parallel_localization_inventory(tmp_path, spelling_values=values)

    key = f"parallel:{path.relative_to(tmp_path).as_posix()}:language.es.short_description"
    assert values["es"][key] == value


@pytest.mark.parametrize(
    ("lifecycle", "relative", "concept_id", "locale", "field"),
    [
        ("approved", f"{_CONCEPTS}/term.toml", "term", "es", "short_description"),
        ("unknown", f"{_CONCEPTS}/term.toml", "term", "es", "short_description"),
        ("DRAFT", f"{_CONCEPTS}/term.toml", "term", "es", "short_description"),
        (None, f"{_CONCEPTS}/term.toml", "term", "es", "short_description"),
        ("draft", f"{_CONCEPTS}/term.toml", "other", "es", "short_description"),
        ("draft", f"{_CONCEPTS}/nested/term.toml", "term", "es", "short_description"),
        ("draft", "src/cadrumo/_data/other/term.toml", "term", "es", "short_description"),
        ("draft", f"{_CONCEPTS}/term.toml", "term", "en", "short_description"),
        ("draft", f"{_CONCEPTS}/term.toml", "term", "es", "definition"),
        ("draft", f"{_CONCEPTS}/term.toml", "term", "es", "scope_note"),
    ],
)
def test_marker_outside_exact_scaffold_context_remains_spellchecked(
    tmp_path: Path, lifecycle: str | None, relative: str, concept_id: str, locale: str, field: str
) -> None:
    _write_concept(tmp_path, lifecycle=lifecycle, relative=relative, concept_id=concept_id, locale=locale, field=field)
    values: dict[str, dict[str, str]] = {}

    parallel_localization_inventory(tmp_path, spelling_values=values)

    assert values[locale][f"parallel:{relative}:language.{locale}.{field}"] == _MARKER


@pytest.mark.parametrize("concept", ["", "concept = 'draft'\n", "[concept]\nconcept_id = 'term'\nlifecycle = 1\n"])
def test_malformed_concept_metadata_does_not_hide_marker(tmp_path: Path, concept: str) -> None:
    path = tmp_path / _CONCEPTS / "term.toml"
    path.parent.mkdir(parents=True)
    path.write_text(f"{concept}[language.es]\nshort_description = '{_MARKER}'\n", encoding="utf-8")
    values: dict[str, dict[str, str]] = {}

    parallel_localization_inventory(tmp_path, spelling_values=values)

    assert values["es"][f"parallel:{_CONCEPTS}/term.toml:language.es.short_description"] == _MARKER
