"""Real registry-backed tests for modelo schema-local locale management."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ...core.external_constants import OutputLanguage
from ...core.resources import bundled_path
from .. import (
    ModeloLocaleError,
    ModeloLocaleFieldKind,
    ModeloLocaleFileTarget,
    ModeloLocaleManager,
    ModeloLocaleScope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO_ID = "130"
REVISION_ID = "2019-y-siguientes"


@pytest.fixture
def registry_root(tmp_path: Path) -> Path:
    """Return a temp registry root containing the real bundled M130 modelo."""
    root = tmp_path / "registry" / "aeat"
    modelos = root / "modelos"
    modelos.mkdir(parents=True)
    shutil.copytree(bundled_path("registry", "aeat", "modelos", MODELO_ID), modelos / MODELO_ID)
    return root


def test_coverage_uses_real_registry_keys(registry_root: Path) -> None:
    """Coverage comes from the loaded schema, not from locale-file contents alone."""
    manager = ModeloLocaleManager(registry_root)

    record = manager.coverage_record(OutputLanguage.EN, MODELO_ID, REVISION_ID)
    label_keys = {
        item.key
        for item in manager.inventory_keys(MODELO_ID, REVISION_ID)
        if item.field is ModeloLocaleFieldKind.LABELS
    }

    assert record.complete
    assert record.label_required == 20
    assert record.label_translated == 20
    assert record.help_required == 20
    assert record.help_translated == 20
    assert record.drift == ()
    assert {"01", "saldo-negativo-fin-periodo"}.issubset(label_keys)


def test_scaffold_preserves_translations_adds_placeholders_and_removes_stale_keys(registry_root: Path) -> None:
    """Scaffold aligns real TOML without overwriting translated leaves."""
    locale_path = _revision_locale_path(registry_root)
    original = locale_path.read_text(encoding="utf-8")
    assert '"01" = "Income"' in original
    assert '"02" = "Expenses"' in original

    edited = original.replace('"02" = "Expenses"\n', "")
    edited = edited.replace("[help]\n", '"stale-key" = "Stale label"\n\n[help]\n')
    locale_path.write_text(edited, encoding="utf-8")

    manager = ModeloLocaleManager(registry_root)
    changed = manager.scaffold_revision(OutputLanguage.EN, MODELO_ID, REVISION_ID)
    translation = manager.load_translation_file(_revision_target())

    assert changed == (locale_path.resolve(),)
    assert not (registry_root / "modelos" / MODELO_ID / "locales" / "en.toml").exists()
    assert translation.labels["01"] == "Income"
    assert translation.labels["02"] == "02"
    assert "stale-key" not in translation.labels


def test_set_and_remove_write_one_validated_translation_leaf(registry_root: Path) -> None:
    """Set and remove mutate one registry-validated leaf through the manager."""
    manager = ModeloLocaleManager(registry_root)

    written = manager.set_translation_value(
        OutputLanguage.EN,
        MODELO_ID,
        REVISION_ID,
        ModeloLocaleFieldKind.LABELS,
        "01",
        "Revenue",
    )
    after_set = manager.load_translation_file(_revision_target())

    removed = manager.remove_translation_value(
        OutputLanguage.EN,
        MODELO_ID,
        REVISION_ID,
        ModeloLocaleFieldKind.LABELS,
        "01",
    )
    after_remove = manager.load_translation_file(_revision_target())

    assert written == _revision_locale_path(registry_root).resolve()
    assert removed == written
    assert after_set.labels["01"] == "Revenue"
    assert "01" not in after_remove.labels


def test_set_rejects_unknown_schema_key(registry_root: Path) -> None:
    """Manager writes are refused when a key is absent from the real schema."""
    manager = ModeloLocaleManager(registry_root)

    with pytest.raises(ModeloLocaleError, match="Modelo schema key not found"):
        manager.set_translation_value(
            OutputLanguage.EN,
            MODELO_ID,
            REVISION_ID,
            ModeloLocaleFieldKind.LABELS,
            "not-a-casilla",
            "Invalid",
        )


def test_modelo_resolution_rejects_path_like_identifier(registry_root: Path) -> None:
    """Registry identifier resolution refuses path-like segments."""
    manager = ModeloLocaleManager(registry_root)

    with pytest.raises(ModeloLocaleError, match="Invalid modelo_id"):
        manager.resolve_modelo_dir("../130")


def test_scaffold_preserves_revision_key_that_exists_in_multiple_revisions(tmp_path: Path) -> None:
    """Revision-local valid-key checks must include the revision id."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir)
    locale_path = modelo_dir / "revisions" / "2020" / "locales" / "en.toml"
    locale_path.parent.mkdir(parents=True)
    locale_path.write_text(
        """[labels]
"01" = "First revision label"

[help]
"01" = "First revision help"
""",
        encoding="utf-8",
    )

    manager = ModeloLocaleManager(registry_root)
    changed = manager.scaffold_revision(OutputLanguage.EN, "777", "2020")
    translation = manager.load_translation_file(
        ModeloLocaleFileTarget(
            locale=OutputLanguage.EN,
            modelo_id="777",
            scope=ModeloLocaleScope.REVISION,
            revision_id="2020",
        ),
    )

    assert changed == ()
    assert translation.labels["01"] == "First revision label"
    assert translation.help["01"] == "First revision help"


def test_fragmented_revision_locale_is_loaded_and_updated_in_place(tmp_path: Path) -> None:
    """Large-model locale fragments remain the write target for their keys."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir)
    locale_dir = modelo_dir / "revisions" / "2020" / "locales" / "en"
    locale_dir.mkdir(parents=True)
    labels_path = locale_dir / "001-labels.toml"
    help_path = locale_dir / "101-help.toml"
    labels_path.write_text(
        """[labels]
"01" = "First revision label"
""",
        encoding="utf-8",
    )
    help_path.write_text(
        """[help]
"01" = "First revision help"
""",
        encoding="utf-8",
    )

    manager = ModeloLocaleManager(registry_root)
    record = manager.coverage_record(OutputLanguage.EN, "777", "2020")
    written = manager.set_translation_value(
        OutputLanguage.EN,
        "777",
        "2020",
        ModeloLocaleFieldKind.LABELS,
        "01",
        "Updated fragment label",
    )
    translation = manager.load_translation_file(
        ModeloLocaleFileTarget(
            locale=OutputLanguage.EN,
            modelo_id="777",
            scope=ModeloLocaleScope.REVISION,
            revision_id="2020",
        ),
    )

    assert record.complete
    assert written == labels_path.resolve()
    assert '"01" = "Updated fragment label"' in labels_path.read_text(encoding="utf-8")
    assert '"01" = "First revision help"' in help_path.read_text(encoding="utf-8")
    assert not (modelo_dir / "revisions" / "2020" / "locales" / "en.toml").exists()
    assert translation.labels["01"] == "Updated fragment label"
    assert translation.help["01"] == "First revision help"


def test_coverage_refuses_mirrored_help_and_key_echoes(tmp_path: Path) -> None:
    """A help value repeating the label, and a key-echo, never count as translated."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir, casilla_ids=("01", "02", "03"))
    locale_path = modelo_dir / "revisions" / "2020" / "locales" / "en.toml"
    locale_path.parent.mkdir(parents=True)
    locale_path.write_text(
        """[labels]
"01" = "Income"
"02" = "02"
"03" = "Expenses"

[help]
"01" = "Income"
"02" = "Etiqueta 02"
"03" = "Total deductible expenses for the period."
""",
        encoding="utf-8",
    )

    record = ModeloLocaleManager(registry_root).coverage_record(OutputLanguage.EN, "777", "2020")

    assert record.label_translated == 2
    assert record.label_key_echo == 1
    assert record.label_absent == 0
    # "01" mirrors its own label and "02" mirrors the official Spanish label.
    assert record.help_translated == 1
    assert record.help_mirrored == 2
    assert record.help_key_echo == 0
    assert record.help_absent == 0
    assert not record.complete


def test_coverage_counts_genuinely_authored_leaves_complete(tmp_path: Path) -> None:
    """Authored labels and distinct help still reach a complete record."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir)
    locale_path = modelo_dir / "revisions" / "2020" / "locales" / "en.toml"
    locale_path.parent.mkdir(parents=True)
    locale_path.write_text(
        """[labels]
"01" = "Income"

[help]
"01" = "Total cumulative business income for the tax year."
""",
        encoding="utf-8",
    )

    record = ModeloLocaleManager(registry_root).coverage_record(OutputLanguage.EN, "777", "2020")

    assert record.complete
    assert record.label_translated == 1
    assert record.help_translated == 1
    assert record.help_mirrored == 0


def test_fragmented_scaffold_materialises_missing_keys_and_spills_at_capacity(tmp_path: Path) -> None:
    """Scaffold appends missing keys to the tail fragment and creates the next at capacity."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir, casilla_ids=("01", "02", "03"))
    locale_dir = modelo_dir / "revisions" / "2020" / "locales" / "en"
    locale_dir.mkdir(parents=True)
    labels_path = locale_dir / "001-labels.toml"
    labels_path.write_text(
        """[labels]
"01" = "First revision label"
"stale-key" = "Stale label"
""",
        encoding="utf-8",
    )

    manager = ModeloLocaleManager(registry_root, fragment_leaf_capacity=2)
    changed = manager.scaffold_revision(OutputLanguage.EN, "777", "2020")
    translation = manager.load_translation_file(
        ModeloLocaleFileTarget(
            locale=OutputLanguage.EN,
            modelo_id="777",
            scope=ModeloLocaleScope.REVISION,
            revision_id="2020",
        ),
    )

    assert labels_path.resolve() in changed
    assert (locale_dir / "002-labels.toml").is_file()
    assert (locale_dir / "101-help.toml").is_file()
    assert (locale_dir / "102-help.toml").is_file()
    assert not (modelo_dir / "revisions" / "2020" / "locales" / "en.toml").exists()
    assert translation.labels == {"01": "First revision label", "02": "02", "03": "03"}
    assert translation.help == {"01": "01", "02": "02", "03": "03"}
    assert "stale-key" not in labels_path.read_text(encoding="utf-8")


def test_fragmented_set_accepts_new_schema_key(tmp_path: Path) -> None:
    """A schema key with no owning fragment is appended to the field family tail."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir, casilla_ids=("01", "02"))
    locale_dir = modelo_dir / "revisions" / "2020" / "locales" / "en"
    locale_dir.mkdir(parents=True)
    labels_path = locale_dir / "001-labels.toml"
    labels_path.write_text(
        """[labels]
"01" = "First revision label"
""",
        encoding="utf-8",
    )
    help_path = locale_dir / "101-help.toml"
    help_path.write_text(
        """[help]
"01" = "First revision help"
""",
        encoding="utf-8",
    )

    manager = ModeloLocaleManager(registry_root)
    written = manager.set_translation_value(
        OutputLanguage.EN,
        "777",
        "2020",
        ModeloLocaleFieldKind.LABELS,
        "02",
        "Second label",
    )
    translation = manager.load_translation_file(
        ModeloLocaleFileTarget(
            locale=OutputLanguage.EN,
            modelo_id="777",
            scope=ModeloLocaleScope.REVISION,
            revision_id="2020",
        ),
    )

    assert written == labels_path.resolve()
    assert translation.labels == {"01": "First revision label", "02": "Second label"}
    assert translation.help == {"01": "First revision help"}


def test_fragmented_set_creates_next_fragment_when_tail_is_full(tmp_path: Path) -> None:
    """A full tail fragment spills the new key into the next numbered fragment."""
    registry_root = tmp_path / "registry" / "aeat"
    modelo_dir = registry_root / "modelos" / "777"
    _write_minimal_modelo(modelo_dir, casilla_ids=("01", "02"))
    locale_dir = modelo_dir / "revisions" / "2020" / "locales" / "en"
    locale_dir.mkdir(parents=True)
    (locale_dir / "001-labels.toml").write_text(
        """[labels]
"01" = "First revision label"
""",
        encoding="utf-8",
    )
    (locale_dir / "101-help.toml").write_text(
        """[help]
"01" = "First revision help"
""",
        encoding="utf-8",
    )

    manager = ModeloLocaleManager(registry_root, fragment_leaf_capacity=1)
    written = manager.set_translation_value(
        OutputLanguage.EN,
        "777",
        "2020",
        ModeloLocaleFieldKind.LABELS,
        "02",
        "Second label",
    )

    assert written == (locale_dir / "002-labels.toml").resolve()
    assert '"02" = "Second label"' in written.read_text(encoding="utf-8")


def _revision_target() -> ModeloLocaleFileTarget:
    return ModeloLocaleFileTarget(
        locale=OutputLanguage.EN,
        modelo_id=MODELO_ID,
        scope=ModeloLocaleScope.REVISION,
        revision_id=REVISION_ID,
    )


def _revision_locale_path(registry_root: Path) -> Path:
    return registry_root / "modelos" / MODELO_ID / "revisions" / REVISION_ID / "locales" / "en.toml"


def _write_minimal_modelo(modelo_dir: Path, casilla_ids: tuple[str, ...] = ("01",)) -> None:
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(
        """
[modelo]
id = "777"
title = "Modelo 777"
official_name = "MODELO 777"
tax_domain = "irpf"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-source-test"]
""",
        encoding="utf-8",
    )
    for revision_id, valid_from in (("2020", "2020-01-01"), ("2021", "2021-01-01")):
        revision_dir = modelo_dir / "revisions" / revision_id
        revision_dir.mkdir(parents=True)
        revision_dir.joinpath("revision.toml").write_text(
            f"""
[revisions.{revision_id}]
valid_from = {valid_from}
period_selector = {{ year_from = {revision_id}, periods = ["0A"] }}
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-source-test"]
""",
            encoding="utf-8",
        )
        casillas_dir = revision_dir / "casillas"
        casillas_dir.mkdir()
        casillas_dir.joinpath("0001-casillas.toml").write_text(
            "\n".join(
                f"""
[[revisions."{revision_id}".casillas]]
id = "{casilla_id}"
number = "{casilla_id}"
label = "Etiqueta {casilla_id}"
section = ["section"]
input_kind = "manual"
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-source-test"]
"""
                for casilla_id in casilla_ids
            ),
            encoding="utf-8",
        )
