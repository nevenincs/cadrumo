"""The Modelo envelope producer names each id a run mints by what its row states, and refuses a name that merges.

The producer is the script the ``modelo-envelopes`` family runs. Its naming is
exercised here directly over planted envelopes: each calculation revision id is
named as the producer names one it read, and each envelope is recorded in the
profile it was written in, as the producer records it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCER = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts" / "modelo_fixtures.py"

#: Two revision ids two scenario profiles mint for one calculation: each profile's keyed references differ.
_FIRST_ID = "a" * 64
_SECOND_ID = "b" * 64
#: What both revisions state: one work unit, one set of values, one instant.
_STATED: dict[str, Any] = {
    "work_unit_id": "c" * 64,
    "registry_snapshot_ref": {"modelo": "130", "period": "1T"},
    "casilla_values": {"01": "100.00"},
    "created_at": "2000-01-01T09:00:00Z",
}


@pytest.fixture
def producer() -> ModuleType:
    """A fresh load of the producer, so no name minted by one test reaches another."""
    spec = importlib.util.spec_from_file_location("modelo_fixtures_under_test", _PRODUCER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _envelope(directory: Path, producer: ModuleType, name: str, profile: str | None, value: Any) -> None:
    """Write ``value`` as the envelope ``name``, recorded as written in ``profile`` or outside every profile."""
    (directory / name).write_text(json.dumps(value), "utf-8")
    if profile is not None:
        producer._ENVELOPE_PROFILES[name] = profile


def _read_revision(producer: ModuleType, raw: str, stated: dict[str, Any]) -> None:
    """Name ``raw`` as the producer names a calculation revision it read: by what the revision states."""
    producer._MINTED_IDS[raw] = producer._token("calculation-revision", stated)


def _named(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text("utf-8"))


def test_one_calculation_read_in_two_profiles_shares_its_name(producer: ModuleType, tmp_path: Path) -> None:
    _read_revision(producer, _FIRST_ID, _STATED)
    _read_revision(producer, _SECOND_ID, _STATED)
    _envelope(tmp_path, producer, "first.json", "profile-one", {"calculation_revision_id": _FIRST_ID})
    _envelope(tmp_path, producer, "second.json", "profile-two", {"calculation_revision_id": _SECOND_ID})

    producer._name_minted_ids(tmp_path, ["first.json", "second.json"])

    name = producer._token("calculation-revision", _STATED)
    assert _named(tmp_path, "first.json") == {"calculation_revision_id": name}
    assert _named(tmp_path, "second.json") == {"calculation_revision_id": name}


def test_two_revisions_stated_alike_in_one_profile_are_refused(producer: ModuleType, tmp_path: Path) -> None:
    _read_revision(producer, _FIRST_ID, _STATED)
    _read_revision(producer, _SECOND_ID, _STATED)
    _envelope(tmp_path, producer, "first.json", "profile-one", {"calculation_revision_id": _FIRST_ID})
    _envelope(tmp_path, producer, "second.json", "profile-one", {"calculation_revision_id": _SECOND_ID})

    with pytest.raises(SystemExit, match="would merge them"):
        producer._name_minted_ids(tmp_path, ["first.json", "second.json"])


def test_a_revision_in_an_envelope_of_no_known_profile_is_refused_a_shared_name(
    producer: ModuleType, tmp_path: Path
) -> None:
    _read_revision(producer, _FIRST_ID, _STATED)
    _read_revision(producer, _SECOND_ID, _STATED)
    _envelope(tmp_path, producer, "first.json", "profile-one", {"calculation_revision_id": _FIRST_ID})
    _envelope(tmp_path, producer, "second.json", None, {"calculation_revision_id": _SECOND_ID})

    with pytest.raises(SystemExit, match="would merge them"):
        producer._name_minted_ids(tmp_path, ["first.json", "second.json"])


def test_revisions_stated_differently_keep_their_own_names(producer: ModuleType, tmp_path: Path) -> None:
    _read_revision(producer, _FIRST_ID, _STATED)
    _read_revision(producer, _SECOND_ID, {**_STATED, "casilla_values": {"01": "200.00"}})
    _envelope(
        tmp_path,
        producer,
        "both.json",
        "profile-one",
        {"current_calculation_revision_id": _FIRST_ID, "filed_calculation_revision_id": _SECOND_ID},
    )

    producer._name_minted_ids(tmp_path, ["both.json"])

    named = _named(tmp_path, "both.json")
    assert named["current_calculation_revision_id"] != named["filed_calculation_revision_id"]
    assert _FIRST_ID not in json.dumps(named) and _SECOND_ID not in json.dumps(named)


def test_one_export_event_stated_differently_in_two_profiles_is_refused(producer: ModuleType, tmp_path: Path) -> None:
    from cadrumo.application.modelo.export_projection import ModeloFicheroBoePublicReceipt

    _read_revision(producer, _FIRST_ID, _STATED)
    event = "d" * 64

    def receipt(file_sha256: str) -> dict[str, Any]:
        row = dict.fromkeys(ModeloFicheroBoePublicReceipt.model_fields, "")
        row.update(bucket_event_id=event, calculation_revision_id=_FIRST_ID, file_sha256=file_sha256)
        return row

    _envelope(tmp_path, producer, "first.json", "profile-one", receipt("e" * 64))
    _envelope(tmp_path, producer, "second.json", "profile-two", receipt("f" * 64))

    with pytest.raises(SystemExit, match="is stated differently by two rows"):
        producer._name_minted_ids(tmp_path, ["first.json", "second.json"])
