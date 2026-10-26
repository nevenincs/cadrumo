"""Below the declared support floor a revision owes nothing and is not measured.

The registry's supported-filing-years declaration is the only authority for the
span the product claims. A revision that no supported coordinate can reach --
neither by its own selector nor by canonical projection -- is out of scope by
definition, so its bindings must not reach any count or finding. A revision the
floor admits, or one the selector projects forward onto a supported year, is
measured exactly as before.

Each case compiles an isolated synthetic registry through the real loader and
runs the real audit; nothing in the bundled tree is read or changed.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..binding_signal.common import required_mapping
from ..bindings import audit

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = """[supported_filing_years]
floor = 2022
horizon = 2022

[sociedades_annual_manual_coverage]
[[sociedades_annual_manual_coverage.dispositions]]
year = 2022
status = "unpublished"
official_locator = "https://sede.agenciatributaria.gob.es/Sede/manuales-practicos.html"
observed_at = 2026-09-10
acquisition_condition_key = "application.registry.manuals.coverage.recheck_aeat_publication"
"""
_MANIFEST = """[modelo]
id = "{modelo}"
tax_domain = "is"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["fixture-law:art-1"]
source_refs = ["fixture-source"]
"""
_REVISION = """[revisions."{revision}"]
valid_from = {start}-01-01
{selector}
legal_refs = ["fixture-law:art-1"]
source_refs = ["fixture-source"]
"""
# A filing-grade provider with no consumer: the shape the gate blocks on.
_UNCONSUMED_BINDING = """[[revisions."{revision}".bindings]]
id = "{binding}"
provider = {{ kind = "profile", profile_model = "taxpayer", field = "incn_prior_12_months" }}
value = {{ data_type = "money", channel = "decimal" }}
aggregation = {{ op = "copy" }}
legal_refs = ["fixture-law:art-1"]
source_refs = ["fixture-source"]
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry(tmp_path: Path, revisions: dict[str, tuple[tuple[str, int, str, str], ...]]) -> Path:
    """Write a synthetic registry: ``{modelo: ((revision, start, selector, binding), ...)}``."""
    aeat = tmp_path / "src" / "cadrumo" / "_data" / "registry" / "aeat"
    _write(aeat / "legal" / "support.toml", _SUPPORT)
    for modelo, declared in revisions.items():
        modelo_dir = aeat / "modelos" / modelo
        _write(modelo_dir / "manifest.toml", _MANIFEST.format(modelo=modelo))
        for revision, start, selector, binding in declared:
            revision_dir = modelo_dir / "revisions" / revision
            _write(
                revision_dir / "revision.toml",
                _REVISION.format(revision=revision, start=start, selector=selector),
            )
            _write(
                revision_dir / "bindings" / "0001-declarations.toml",
                _UNCONSUMED_BINDING.format(revision=revision, binding=binding),
            )
    return tmp_path


def _unconsumed(payload: dict[str, object]) -> list[tuple[object, object, object]]:
    findings = payload["findings"]
    assert isinstance(findings, list)
    return sorted(
        (item["coordinate"]["modelo"], item["coordinate"]["revision"], item["coordinate"]["binding"])
        for item in findings
        if item["code"] == "UNCONSUMED_FILING_GRADE_BINDING"
    )


def _summary(payload: dict[str, object]) -> Mapping[str, object]:
    return required_mapping(payload["summary"], context="audit summary")


def _scope(payload: dict[str, object]) -> Mapping[str, object]:
    return required_mapping(payload["scope"], context="audit scope")


_EARLY = ("2016-2017", 2016, 'valid_to = 2017-12-31\nperiod_selector = { years = [2016, 2017], periods = ["0A"] }')
_AT_FLOOR = ("2022-y-siguientes", 2022, 'period_selector = { year_from = 2022, periods = ["0A"] }')


def test_an_unconsumed_binding_below_the_floor_is_not_counted_and_one_at_the_floor_is(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    root = _registry(
        tmp_path,
        {"999": ((*_EARLY, "m999-profile-early"), (*_AT_FLOOR, "m999-profile-current"))},
    )

    payload = audit(root)

    summary = _summary(payload)
    assert summary["classification"] == "measured"
    assert _unconsumed(payload) == [("999", "2022-y-siguientes", "m999-profile-current")]
    assert summary["unreferenced_bindings"] == 1
    assert summary["bindings"] == 1
    assert summary["revisions"] == 1
    assert summary["revisions_below_support_floor"] == 1
    scope = _scope(payload)
    assert scope["revisions_below_support_floor"] == ["999/2016-2017"]
    assert scope["support_envelope"] == {
        "authority": "supported_filing_years",
        "floor": 2022,
        "horizon": 2022,
        "hard_ceiling": None,
    }


def test_a_binding_an_in_scope_edition_inherits_from_below_the_floor_is_measured_there(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Excluding the predecessor edition never excludes what a supported edition inherits from it."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    successor = (_AT_FLOOR[0], _AT_FLOOR[1], f'predecessor = "{_EARLY[0]}"\n{_AT_FLOOR[2]}')
    root = _registry(
        tmp_path,
        {"999": ((*_EARLY, "m999-profile-early"), (*successor, "m999-profile-current"))},
    )

    payload = audit(root)

    assert _summary(payload)["classification"] == "measured"
    assert _unconsumed(payload) == [
        ("999", "2022-y-siguientes", "m999-profile-current"),
        ("999", "2022-y-siguientes", "m999-profile-early"),
    ]
    assert _scope(payload)["revisions_below_support_floor"] == ["999/2016-2017"]
    findings = payload["findings"]
    assert isinstance(findings, list)
    # The successor still names a predecessor that is declared on disk.
    assert not [item for item in findings if item["code"] == "PREDECESSOR_NOT_FOUND"]


def test_a_pre_floor_revision_projected_onto_a_supported_year_stays_measured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projection answers the floor year from the nearest edition, so that edition is in scope."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    projected = (
        "2019-2020",
        2019,
        'valid_to = 2020-12-31\nperiod_selector = { years = [2019, 2020], periods = ["0A"] }',
    )
    root = _registry(tmp_path, {"998": ((*projected, "m998-profile-projected"),)})

    payload = audit(root)

    assert _summary(payload)["classification"] == "measured"
    assert _unconsumed(payload) == [("998", "2019-2020", "m998-profile-projected")]
    assert _scope(payload)["revisions_below_support_floor"] == []
