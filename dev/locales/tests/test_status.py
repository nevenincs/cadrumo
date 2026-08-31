"""Honest state-partition contracts for the locale status surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.tests.cli_runner import invoke_typer_app

from .._status import CatalogueLeafState, catalogue_status, classify_catalogue_leaf
from ..cli import app
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES = ("ca", "en", "es", "hu")


@pytest.fixture
def manager(tmp_path: Path) -> LocaleManager:
    """Return a manager over real catalogues seeded with every leaf state."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "surface.py").write_text(
        "from cadrumo.core.i18n import tr\n\n"
        "def render() -> tuple[str, str, str, str, str]:\n"
        '    return (tr("audit.first"), tr("audit.second"), tr("audit.third"),\n'
        '            tr("audit.fourth"), tr("audit.fifth"))\n',
        encoding="utf-8",
    )
    catalogues = {
        # fourth carries a token named after tr()'s reserved locale
        # meta-kwarg, so it can never bind: structurally broken.
        "en": (
            "audit:\n  first: 'First message'\n  second: 'Second message'\n  third: 'Third message'\n"
            "  fourth: 'Recorded %{locale} entry'\n  fifth: 'Fifth message'\n"
        ),
        # first echoes its own key despite the trailing space, second is
        # authored, third is absent, fifth is whitespace-only.
        "ca": "audit:\n  first: 'audit.first '\n  second: 'Segon missatge'\n  fifth: '   '\n",
        # first is identical to en without an allowlist entry, second is
        # identical WITH one, third is authored.
        "hu": ("audit:\n  first: 'First message'\n  second: 'Second message'\n  third: 'Harmadik üzenet'\n"),
        # Fully authored, plus one key the codebase never declares.
        "es": (
            "audit:\n  first: 'Primer mensaje'\n  second: 'Segundo mensaje'\n  third: 'Tercer mensaje'\n"
            "  fifth: 'Quinto mensaje'\n"
            "orphan:\n  leaf: 'Sin uso'\n"
        ),
    }
    for locale in _LOCALES:
        (locales_dir / f"{locale}.yml").write_text(catalogues[locale], encoding="utf-8")
    (locales_dir / "_intentional_identical.json").write_text(
        json.dumps({"hu": {"audit.second": "brand name shared with English"}}),
        encoding="utf-8",
    )
    return LocaleManager(src_dir=source_dir, locales_dir=locales_dir)


@pytest.fixture
def sharded_manager(manager: LocaleManager) -> LocaleManager:
    """Return the same catalogues resharded into per-locale shard directories.

    Production ships this shape, not the flat one: each locale is a directory
    of ``*.yml`` shards rather than a single file. The catalogue content is
    byte-identical to the flat fixture and lands in one shard, so this isolates
    discovery: any partition difference between the two layouts is a discovery
    defect, not a classification one. Multi-shard deep merging is a separate
    contract and is covered by the sharded-manager tests.
    """
    locales_dir = manager.locales_dir
    for locale in _LOCALES:
        flat = locales_dir / f"{locale}.yml"
        body = flat.read_text(encoding="utf-8")
        flat.unlink()
        shard_dir = locales_dir / locale
        shard_dir.mkdir()
        (shard_dir / "audit.yml").write_text(body, encoding="utf-8")
    return manager


def test_catalogue_status_partitions_every_required_key(manager: LocaleManager) -> None:
    """Each defect lands in exactly one state and the partition sums to required."""
    by_file = {record.locale_file: record for record in catalogue_status(manager)}

    # The registry/f-string scanners contribute required keys beyond the
    # fixture's source file, so present-leaf counts are asserted while the
    # ``absent`` remainder is checked through the partition sum below.
    observed = {
        name: (
            record.authored,
            record.key_echo,
            record.blank,
            record.unbindable,
            record.identical_allowlisted,
            record.identical_pending,
            record.extra,
        )
        for name, record in by_file.items()
    }
    assert observed == {
        "en.yml": (4, 0, 0, 1, 0, 0, 0),
        "ca.yml": (1, 1, 1, 0, 0, 0, 0),
        "hu.yml": (1, 0, 0, 0, 1, 1, 0),
        "es.yml": (4, 0, 0, 0, 0, 0, 1),
    }

    for record in by_file.values():
        partition = (
            record.authored
            + record.key_echo
            + record.blank
            + record.unbindable
            + record.identical_allowlisted
            + record.identical_pending
            + record.absent
        )
        assert partition == record.required


def test_classifier_never_reports_a_defect_as_authored() -> None:
    """Key-echo and unallowlisted identical values are refused as authored."""
    assert (
        classify_catalogue_leaf(
            "audit.first",
            "audit.first",
            reference_value="First message",
            is_reference_locale=False,
            allowlisted=True,
        )
        is CatalogueLeafState.KEY_ECHO
    )
    assert (
        classify_catalogue_leaf(
            "audit.first",
            "First message",
            reference_value="First message",
            is_reference_locale=False,
            allowlisted=False,
        )
        is CatalogueLeafState.IDENTICAL_PENDING
    )
    assert (
        classify_catalogue_leaf(
            "audit.first",
            None,
            reference_value="First message",
            is_reference_locale=False,
            allowlisted=False,
        )
        is CatalogueLeafState.ABSENT
    )
    assert (
        classify_catalogue_leaf(
            "audit.first",
            "First message",
            reference_value="First message",
            is_reference_locale=True,
            allowlisted=False,
        )
        is CatalogueLeafState.AUTHORED
    )
    # A token named after a tr() rendering directive can never bind, so the
    # value is structurally broken even though it reads as authored prose.
    assert (
        classify_catalogue_leaf(
            "audit.first",
            "Recorded %{locale} entry",
            reference_value="First message",
            is_reference_locale=False,
            allowlisted=False,
        )
        is CatalogueLeafState.UNBINDABLE
    )
    # Empty and whitespace-only values are their own never-authored state,
    # and a stray character cannot smuggle an echo past the check.
    for planted, expected in (
        ("", CatalogueLeafState.BLANK),
        ("   ", CatalogueLeafState.BLANK),
        ("audit.first ", CatalogueLeafState.KEY_ECHO),
        ("audit.first.", CatalogueLeafState.KEY_ECHO),
        (" audit.first: ", CatalogueLeafState.KEY_ECHO),
    ):
        assert (
            classify_catalogue_leaf(
                "audit.first",
                planted,
                reference_value="First message",
                is_reference_locale=False,
                allowlisted=False,
            )
            is expected
        ), planted


def test_status_command_reports_catalogue_partition(manager: LocaleManager) -> None:
    """The status command prints one greppable partition row per catalogue."""
    result = invoke_typer_app(app, ["status"], obj=manager)
    rows = {
        line.split()[1].removeprefix("file="): dict(part.split("=", 1) for part in line.split()[2:])
        for line in result.output.splitlines()
        if line.startswith("catalogue file=")
    }

    assert result.exit_code == 0, result.output
    assert set(rows) == {"ca.yml", "en.yml", "es.yml", "hu.yml"}
    assert (rows["ca.yml"]["authored"], rows["ca.yml"]["key_echo"]) == ("1", "1")
    assert rows["ca.yml"]["blank"] == "1"
    assert rows["en.yml"]["unbindable"] == "1"
    assert rows["en.yml"]["namespace_exempted"] == "0"
    assert rows["hu.yml"]["identical_allowlisted"] == "1"
    assert rows["hu.yml"]["identical_pending"] == "1"
    assert rows["es.yml"]["extra"] == "1"


def test_catalogue_status_reads_the_sharded_layout_production_ships(
    sharded_manager: LocaleManager,
    manager: LocaleManager,
) -> None:
    """Discovery must find shard directories, not just legacy flat files.

    A discovery pass that globs one catalogue shape does not fail loudly when
    the tree carries the other -- it returns nothing, and nothing partitions
    into a clean report. This asserts the sharded layout yields one record per
    locale so that silence cannot pass as a measurement.
    """
    records = catalogue_status(sharded_manager)

    assert {record.locale_file for record in records} == {f"{locale}.yml" for locale in _LOCALES}
    assert records, "sharded catalogues produced no status rows"
    for record in records:
        assert record.required > 0, f"{record.locale_file} reported a zero required set"


def test_sharded_and_flat_layouts_partition_identically(
    tmp_path: Path,
    sharded_manager: LocaleManager,
) -> None:
    """The same catalogue content must classify the same in either layout."""
    sharded = {record.locale_file: record.model_dump() for record in catalogue_status(sharded_manager)}

    assert sharded, "sharded catalogues produced no status rows"
    assert sharded["ca.yml"]["required"] == sharded["en.yml"]["required"]
    assert sharded["es.yml"]["extra"] >= 1
