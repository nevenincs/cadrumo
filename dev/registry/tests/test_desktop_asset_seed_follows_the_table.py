"""The desktop Assets scenario register states the registry's own amortization table.

The scenario ledger of the desktop frontend answers the form options and the
election limits from fixed data. That data must be the table the registry
compiles for the normal modality, class by class, and the methods the registry
admits per asset kind, so a scenario never shows a class, a corridor or a
method the product would not offer. The expectation is read from the bundled
registry, never restated.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEED = REPO_ROOT / "native" / "desktop" / "frontend" / "src" / "dev" / "assetsSeed.ts"
_PREFIX = "renta-actividad-inmovilizado-amortizacion-"
_REVISION = (
    REPO_ROOT
    / "src"
    / "cadrumo"
    / "_data"
    / "registry"
    / "aeat"
    / "modelos"
    / "100"
    / "revisions"
    / "2022"
    / "parameters"
    / "0001-declarations.toml"
)
_GROUP = re.compile(
    r'class_key:\s*"(?P<key>[^"]+)",\s*'
    r'maximum_coefficient:\s*\{\s*decimal:\s*"(?P<maximum>[^"]+)",?\s*\},\s*'
    r'minimum_coefficient:\s*\{\s*decimal:\s*"(?P<minimum>[^"]+)",?\s*\},\s*'
    r'maximum_period_years:\s*\{\s*decimal:\s*"(?P<years>[^"]+)",?\s*\}'
)


@cache
def _parameters() -> dict[str, dict[str, str]]:
    import tomllib

    document = tomllib.loads(_REVISION.read_text(encoding="utf-8"))
    return {
        parameter["id"]: {bracket["key"]: bracket["value"] for bracket in parameter["keyed_brackets"]}
        for parameter in document["revisions"]["2022"]["parameters"]
        if parameter["id"].startswith(_PREFIX) and "keyed_brackets" in parameter
    }


def _section(text: str, name: str) -> str:
    start = text.index(f"export const {name}")
    end = text.find("export const ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _seeded_groups(kind: str) -> dict[str, tuple[Decimal, Decimal, Decimal]]:
    section = _section(_SEED.read_text(encoding="utf-8"), "TABLE_GROUPS")
    block = section[section.index(f"{kind}:") :]
    nxt = re.search(r"\n  \w+: \[", block[len(kind) + 2 :])
    block = block if nxt is None else block[: nxt.start() + len(kind) + 2]
    return {
        match["key"]: (Decimal(match["maximum"]), Decimal(match["minimum"]), Decimal(match["years"]))
        for match in _GROUP.finditer(block)
    }


@pytest.mark.parametrize(
    ("kind", "admits"), [("material", "clase-admite-material"), ("intangible", "clase-admite-intangible")]
)
def test_the_seeded_table_classes_are_the_registrys_for_the_kind(kind: str, admits: str) -> None:
    parameters = _parameters()
    coefficient = parameters[f"{_PREFIX}normal-coeficiente-lineal-maximo"]
    period = parameters[f"{_PREFIX}normal-periodo-maximo-anos"]
    expected = {
        key: (Decimal(coefficient[key]) / 100, Decimal(1) / Decimal(period[key]), Decimal(period[key]))
        for key in coefficient
        if parameters[f"{_PREFIX}{admits}"][key] == "1"
    }

    seeded = _seeded_groups(kind)

    assert expected, "the registry lists no class for the kind, so nothing was compared"
    assert seeded.keys() == expected.keys()
    for key, (maximum, minimum, years) in expected.items():
        assert seeded[key][0] == maximum, key
        assert seeded[key][2] == years, key
        # The minimum is one over the period, to the digits the seed states.
        assert abs(seeded[key][1] - minimum) < Decimal("1e-20"), key


@pytest.mark.parametrize("kind", ["material", "intangible"])
def test_the_seeded_methods_are_the_ones_the_registry_admits_for_the_kind(kind: str) -> None:
    admitted = _parameters()[f"{_PREFIX}normal-metodo-admitido"]
    expected = sorted(
        key.split(":", 1)[1] for key, value in admitted.items() if key.startswith(f"{kind}:") and value == "1"
    )
    section = _section(_SEED.read_text(encoding="utf-8"), "ADMITTED_METHODS")
    block = section[section.index(f"{kind}:") :]
    seeded = sorted(re.findall(r'"(\w+)"', block[: block.index("]")]))

    assert expected
    assert seeded == expected


def test_the_scenario_edition_floor_is_the_registrys() -> None:
    floor = re.search(
        r"^floor\s*=\s*(\d+)",
        (
            REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "legal" / "supported-filing-years.toml"
        ).read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    fixture = Path(_SEED.parent / "assetsFixture.ts").read_text(encoding="utf-8")

    assert floor is not None
    assert f"FIRST_SUPPORTED_YEAR = {floor.group(1)};" in fixture


_NAMES = (
    REPO_ROOT
    / "src"
    / "cadrumo"
    / "_data"
    / "registry"
    / "aeat"
    / "facts"
    / "0150-renta-actividad-inmovilizado-amortizacion-clase-denominacion.toml"
)
_LABEL = re.compile(r'class_key:\s*"(?P<key>[^"]+)",.*?class_label:\s*"(?P<label>(?:[^"\\]|\\.)*)"', re.DOTALL)


def test_the_seeded_table_classes_carry_the_registrys_official_names() -> None:
    import tomllib

    entries = tomllib.loads(_NAMES.read_text(encoding="utf-8"))["fact"]["variants"][0]["payload"]["entries"]
    official = {
        entry["key"].removeprefix("normal."): entry["value"] for entry in entries if entry["key"].startswith("normal.")
    }
    text = _section(_SEED.read_text(encoding="utf-8"), "TABLE_GROUPS")
    seeded: dict[str, str] = {}
    for group in re.split(r"\n    \{\n", text)[1:]:
        match = _LABEL.search(group)
        assert match is not None, group[:80]
        seeded[match["key"]] = match["label"]

    assert seeded
    assert all(official[key] == label for key, label in seeded.items())


_VEHICLE_FLAG = re.compile(r'class_key:\s*"(?P<key>[^"]+)",.*?can_hold_vehicle:\s*(?P<flag>true|false)', re.DOTALL)


@pytest.mark.parametrize(
    ("kind", "admits"), [("material", "clase-admite-material"), ("intangible", "clase-admite-intangible")]
)
def test_the_seeded_vehicle_flag_of_each_class_is_the_registrys_classification(kind: str, admits: str) -> None:
    parameters = _parameters()
    restricted = parameters[f"{_PREFIX}clase-vehiculo-restringido"]
    expected = {
        key: kind == "material" and restricted[key] == "1"
        for key in parameters[f"{_PREFIX}normal-coeficiente-lineal-maximo"]
        if parameters[f"{_PREFIX}{admits}"].get(key) == "1"
    }
    section = _section(_SEED.read_text(encoding="utf-8"), "TABLE_GROUPS")
    block = section[section.index(f"{kind}:") :]
    nxt = re.search(r"\n  \w+: \[", block[len(kind) + 2 :])
    block = block if nxt is None else block[: nxt.start() + len(kind) + 2]
    found = [_VEHICLE_FLAG.search(group) for group in re.split(r"\n    \{\n", block)[1:]]
    seeded = {match["key"]: match["flag"] == "true" for match in found if match is not None}

    assert expected, "the registry lists no class for the kind, so nothing was compared"
    assert len(found) == len(expected), "a seeded class carries no vehicle flag"
    assert seeded == expected
