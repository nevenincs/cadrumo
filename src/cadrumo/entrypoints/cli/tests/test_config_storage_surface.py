"""Real CLI contract tests for the stable four-area storage surface."""

from __future__ import annotations

import json
from typing import Any

import pytest

from ....core import StorageArea, StorageCategory, storage_path
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _json_envelope(args: list[str]) -> Any:
    result = invoke_cached_cli(["--format", "json", *args])
    assert result.exit_code == 0, semantic_cli_output(result)
    return json.loads(result.output)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


class TestListAggregatesByArea:
    def test_list_returns_exactly_the_four_stable_areas(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        rows = envelope["result"]["areas"]
        assert [row["area"] for row in rows] == [area.value for area in StorageArea]
        assert {row["disposition"] for row in rows} == {"durable", "reclaimable", "mixed"}

    def test_list_measures_area_occupancy_and_footprint(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            logs = storage_path(StorageCategory.LOGS)
            logs.mkdir(parents=True, exist_ok=True)
            (logs / "diagnostic.log").write_bytes(b"entry")
            envelope = _json_envelope(["config", "storage", "list"])

        by_area = {row["area"]: row for row in envelope["result"]["areas"]}
        assert by_area[StorageArea.LOGS.value]["occupancy"] == "populated"
        assert by_area[StorageArea.LOGS.value]["footprint_bytes"] == 5

    def test_public_payload_contains_no_internal_taxonomy_fields(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        assert not {
            "category",
            "scope",
            "node_kind",
            "grouping",
            "settings_field",
            "bucket_id",
        } & _all_keys(envelope["result"])

    def test_relocation_advisory_remains_visible(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        advisory = next(
            notice for notice in envelope["notices"] if notice["code"] == "storage_root_relocation_is_manual"
        )
        assert advisory["context"]["variable"] in advisory["message"]


class TestShowUsesAreaVocabulary:
    def test_show_reports_one_aggregate_area(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "show", StorageArea.CACHE.value])

        assert envelope["result"]["area"]["area"] == StorageArea.CACHE.value
        assert envelope["result"]["area"]["disposition"] == "mixed"
        assert "category" not in _all_keys(envelope["result"])

    def test_unknown_area_failure_names_the_four_accepted_values(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            result = invoke_cached_cli(["config", "storage", "show", "not-an-area"])

        assert result.exit_code != 0
        output = semantic_cli_output(result)
        for area in StorageArea:
            assert area.value in output


class TestTextOutputIsReadable:
    def test_list_keeps_the_approved_table_and_wrapped_notice(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            result = invoke_cached_cli(["config", "storage", "list", "--output-language", "en"])

        assert result.exit_code == 0, semantic_cli_output(result)
        assert "\t" not in result.output
        assert "Storage root" in result.output
        assert "Area" in result.output
        assert "Lifecycle" in result.output
        assert "Info:" in result.output
        notice_lines = result.output.split("Info: ", maxsplit=1)[1].splitlines()
        assert len(notice_lines) > 1
        assert all(len(line) <= 96 for line in notice_lines)
        assert all(line.startswith("      ") for line in notice_lines[1:])

    def test_show_uses_aligned_aggregate_fields(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            result = invoke_cached_cli(
                ["config", "storage", "show", StorageArea.LOGS.value, "--output-language", "en"]
            )

        assert result.exit_code == 0, semantic_cli_output(result)
        assert any(line.startswith("Area") and line.endswith("logs") for line in result.output.splitlines())
        assert "Resolved paths" in result.output
        assert "Footprint" in result.output
        assert "Category" not in result.output

    def test_init_noop_notice_remains_visible(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            assert invoke_cached_cli(["config", "storage", "init", "--output-language", "en"]).exit_code == 0
            second = invoke_cached_cli(["config", "storage", "init", "--output-language", "en"])

        assert second.exit_code == 0, semantic_cli_output(second)
        assert "Already present" in second.output
        assert "Created" in second.output
        assert "Info:" in second.output

    def test_spanish_list_uses_one_coherent_output_language(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            result = invoke_cached_cli(["config", "storage", "list", "--output-language", "es"])

        assert result.exit_code == 0, semantic_cli_output(result)
        assert "Raíz de almacenamiento" in result.output
        assert "Área" in result.output
        assert "Ciclo de vida" in result.output
        assert "Información:" in result.output
        for area_label in ("estado", "registros", "caché", "exportaciones"):
            assert area_label in result.output
        assert "Storage root" not in result.output
        assert "Lifecycle" not in result.output

    def test_spanish_durable_refusal_localizes_heading_reason_and_context(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.BLOBS)
            target.mkdir(parents=True, exist_ok=True)
            (target / "durable.bin").write_bytes(b"preserve")
            result = invoke_cached_cli(
                ["config", "storage", "reclaim", "state", "--yes", "--output-language", "es"]
            )

        output = semantic_cli_output(result)
        assert result.exit_code != 0
        assert "Rechazado." in output
        assert "el área contiene estado duradero" in output
        assert "área: estado" in output
        assert "número de entradas:" in output
        assert "motivo:" in output
        assert "Refused" not in output
        assert "the area contains durable state" not in output

    def test_spanish_unconfirmed_refusal_localizes_heading_and_context(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            target.mkdir(parents=True, exist_ok=True)
            (target / "cached.bin").write_bytes(b"rebuild")
            result = invoke_cached_cli(
                ["config", "storage", "reclaim", "cache", "--output-language", "es"]
            )

        output = semantic_cli_output(result)
        assert result.exit_code != 0
        assert "Rechazado." in output
        assert "caché" in output
        assert "área: caché" in output
        assert "número de entradas:" in output
        assert "Refused" not in output


class TestCheckKeepsInternalNodesPrivate:
    def test_check_issue_reports_area_without_category_or_node_kind(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            _json_envelope(["config", "storage", "init"])
            target = storage_path(StorageCategory.USAGE_RATIOS)
            target.mkdir(parents=True, exist_ok=True)
            result = invoke_cached_cli(["--format", "json", "config", "storage", "check"])

        assert result.exit_code == 2, semantic_cli_output(result)
        envelope = json.loads(result.output)
        issue = envelope["result"]["issues"][0]
        assert issue["area"] == StorageArea.EXPORTS.value
        assert issue["kind"] == "path_type_mismatch"
        assert "category" not in _all_keys(envelope["result"])
        assert envelope["result"]["checked_areas"] == 4
        assert StorageCategory.USAGE_RATIOS.value not in json.dumps(envelope["result"])
        assert issue["path"] == str(tmp_path)

    def test_text_check_groups_the_topology_neutral_issue(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            assert invoke_cached_cli(["config", "storage", "init"]).exit_code == 0
            storage_path(StorageCategory.USAGE_RATIOS).mkdir(parents=True, exist_ok=True)
            result = invoke_cached_cli(["config", "storage", "check", "--output-language", "en"])

        assert result.exit_code == 2, semantic_cli_output(result)
        assert "  - path_type_mismatch" in result.output
        assert "    Area: exports" in result.output
        assert "Category" not in result.output


class TestReclaimUsesAreaVocabulary:
    @pytest.mark.parametrize("area", [StorageArea.STATE, StorageArea.EXPORTS])
    def test_durable_area_refusal_keeps_content(self, area: StorageArea, tmp_path) -> None:
        category = StorageCategory.BLOBS if area is StorageArea.STATE else StorageCategory.SUBMISSIONS
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "operator.bin"
            marker.write_bytes(b"preserve")
            result = invoke_cached_cli(["config", "storage", "reclaim", area.value, "--yes"])

        assert result.exit_code != 0
        assert marker.read_bytes() == b"preserve"
        assert area.value in semantic_cli_output(result)

    def test_unconfirmed_reclaim_deletes_nothing(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            target.mkdir(parents=True, exist_ok=True)
            marker = target / "cached.bin"
            marker.write_bytes(b"regenerable")
            result = invoke_cached_cli(["config", "storage", "reclaim", "cache"])

        assert result.exit_code != 0
        assert marker.exists()

    def test_confirmed_cache_reclaim_reports_area_and_removes_regenerable_content(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            target.mkdir(parents=True, exist_ok=True)
            (target / "cached.bin").write_bytes(b"regenerable")
            envelope = _json_envelope(["config", "storage", "reclaim", "cache", "--yes"])

        assert envelope["result"]["area"] == StorageArea.CACHE.value
        assert envelope["result"]["removed_entries"] == 1
        assert "category" not in _all_keys(envelope["result"])
        assert not (target / "cached.bin").exists()
