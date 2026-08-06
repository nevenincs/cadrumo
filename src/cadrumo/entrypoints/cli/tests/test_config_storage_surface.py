"""CLI surface tests for ``aeat config storage``.

Exercises the five verbs through the real Click tree against a real temporary
storage root. The envelope contract is asserted from the parsed JSON document
rather than from prose, so a locale change cannot move these tests and a
message reworded in one catalogue cannot silently red them.

The reclaim refusal is asserted at this layer as well as in the service suite,
because the two prove different properties: the service suite proves the guard
refuses, and this one proves the refusal actually reaches the operator instead
of being swallowed on the way out.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ....core import (
    STORAGE_TAXONOMY,
    StorageCategory,
    StorageLifecycle,
    StorageScope,
    storage_path,
)
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _json_envelope(args: list[str]) -> Any:
    """Invoke the CLI in JSON mode and return the parsed success envelope.

    Typed loosely on purpose: the envelope is a wire document and every caller
    below asserts against its shape directly, which is the assertion that would
    fail loudly if the contract moved.
    """
    result = invoke_cached_cli(["--format", "json", *args])
    assert result.exit_code == 0, semantic_cli_output(result)
    return json.loads(result.output)


class TestListAnswersWhereTheDataIs:
    def test_list_reports_every_declared_category_on_the_envelope_spine(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        assert envelope["command"] == "config.storage.list"
        assert envelope["status"] in {"success", "warning"}
        assert "schema_version" in envelope
        assert "notices" in envelope
        rows = envelope["result"]["categories"]
        assert {row["category"] for row in rows} == {member.value for member in STORAGE_TAXONOMY}

    def test_every_row_carries_the_columns_the_operator_surface_promises(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        required = {
            "path",
            "node_kind",
            "grouping",
            "lifecycle",
            "scope",
            "override_policy",
            "occupancy",
            "settings_field",
        }
        for row in envelope["result"]["categories"]:
            assert required <= set(row), f"{row['category']} is missing {required - set(row)}"

    def test_the_populated_column_distinguishes_a_written_category_from_an_empty_one(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            written = storage_path(StorageCategory.LOGS)
            written.mkdir(parents=True, exist_ok=True)
            (written / "diagnostic.log").write_bytes(b"entry")
            empty = storage_path(StorageCategory.SUBMISSIONS)
            empty.mkdir(parents=True, exist_ok=True)

            envelope = _json_envelope(["config", "storage", "list"])

        by_category = {row["category"]: row for row in envelope["result"]["categories"]}
        assert by_category[StorageCategory.LOGS.value]["occupancy"] == "populated"
        assert by_category[StorageCategory.SUBMISSIONS.value]["occupancy"] == "empty"

    def test_list_advises_that_relocation_is_the_operators_own_move(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        codes = {notice["code"] for notice in envelope["notices"]}
        assert "storage_root_relocation_is_manual" in codes
        advisory = next(n for n in envelope["notices"] if n["code"] == "storage_root_relocation_is_manual")
        # The advisory exists to hand over the one control that does relocate.
        # An advisory that only declines, without naming it, is a dead end.
        assert advisory["context"]["variable"] in advisory["message"]

    def test_no_result_field_smuggles_a_diagnostic_past_the_notice_channel(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "list"])

        forbidden = {"next", "suggestion", "advisory"}
        assert not forbidden & set(envelope["result"])


class TestShowRendersTheAcceptedSetAtTheBoundary:
    def test_show_reports_one_category_in_full(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            envelope = _json_envelope(["config", "storage", "show", StorageCategory.LOGS.value])

        payload = envelope["result"]["category"]
        assert envelope["command"] == "config.storage.show"
        assert payload["category"] == StorageCategory.LOGS.value
        assert payload["lifecycle"] == STORAGE_TAXONOMY[StorageCategory.LOGS].lifecycle.value

    def test_an_unknown_category_is_refused_with_the_accepted_set_named(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            result = invoke_cached_cli(["config", "storage", "show", "not-a-category"])

        assert result.exit_code != 0
        output = semantic_cli_output(result)
        # The CLI boundary must be instructive, never a bare "value invalid":
        # the closed enum renders its members on a parse failure.
        assert StorageCategory.LOGS.value in output


class TestCheckReportsWithoutRepairing:
    def test_check_is_healthy_on_a_materialised_tree(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            _json_envelope(["config", "storage", "init"])
            envelope = _json_envelope(["config", "storage", "check"])

        assert envelope["result"]["healthy"] is True
        assert envelope["result"]["checked_locations"] > 0

    def test_a_directory_where_a_file_belongs_reds_the_check_and_names_the_category(self, tmp_path) -> None:
        """The drift shape the CLI can actually reach, and why it is this one.

        Bootstrap materialises the declared tree before any command body runs,
        so a missing directory is created and a directory occupied by a file is
        refused there — neither survives to be reported by ``check``. A
        file-valued member's LEAF is deliberately not created by the
        materialiser, so a directory sitting where a document belongs passes
        straight through bootstrap and is exactly what this verb is left to
        catch. Asserting the pre-empted shape here would test the bootstrap
        refusal while appearing to test ``check``.
        """
        with override_settings(cadrumo_local_storage_root=tmp_path):
            _json_envelope(["config", "storage", "init"])
            target = storage_path(StorageCategory.USAGE_RATIOS)
            target.mkdir(parents=True, exist_ok=True)

            result = invoke_cached_cli(["--format", "json", "config", "storage", "check"])

        assert result.exit_code != 0
        envelope = json.loads(result.output)
        assert envelope["result"]["healthy"] is False
        offenders = [
            issue for issue in envelope["result"]["issues"] if issue["category"] == StorageCategory.USAGE_RATIOS.value
        ]
        assert offenders
        assert offenders[0]["kind"] == "directory_where_file_expected"
        assert envelope["status"] == "warning"

    def test_bootstrap_refuses_an_occupied_directory_before_check_can_report_it(self, tmp_path) -> None:
        """Pins the pre-emption above as behaviour rather than a comment.

        The operator is not left without an answer — the bootstrap refusal names
        the offending path — but the answer comes from a different surface, and
        a future change that moved tree materialisation out of bootstrap would
        silently make ``check`` the reporter instead. That is a change someone
        should make deliberately, so it reds here first.
        """
        with override_settings(cadrumo_local_storage_root=tmp_path):
            _json_envelope(["config", "storage", "init"])
            target = storage_path(StorageCategory.SUBMISSIONS)
            target.rmdir()
            target.write_bytes(b"not a directory")

            result = invoke_cached_cli(["--format", "json", "config", "storage", "check"])

        assert result.exit_code != 0
        envelope = json.loads(result.output)
        assert envelope["status"] == "error"
        assert str(target) in envelope["error"]["message"]


class TestInitMaterialisesAndPreserves:
    def test_init_reports_the_root_and_leaves_existing_content_alone(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            _json_envelope(["config", "storage", "init"])
            survivor = storage_path(StorageCategory.SUBMISSIONS) / "declaration.boe"
            survivor.write_bytes(b"filed artefact")

            envelope = _json_envelope(["config", "storage", "init"])

        assert envelope["command"] == "config.storage.init"
        assert survivor.read_bytes() == b"filed artefact"


class TestReclaimRefusalReachesTheOperator:
    @pytest.mark.parametrize(
        "category",
        [
            member
            for member, location in STORAGE_TAXONOMY.items()
            if location.scope is StorageScope.ROOT and location.lifecycle is StorageLifecycle.UNBOUNDED_BY_DESIGN
        ][:4],
        ids=lambda c: c.value,
    )
    def test_a_protected_category_is_refused_and_keeps_its_content(self, category, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(category)
            if target.suffix:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"operator data")
            else:
                target.mkdir(parents=True, exist_ok=True)
                (target / "operator.bin").write_bytes(b"operator data")

            result = invoke_cached_cli(["config", "storage", "reclaim", category.value, "--yes"])

            assert result.exit_code != 0
            output = semantic_cli_output(result)
            # The refusal must name what it would have deleted and why, so the
            # operator can tell a protected category from a broken command.
            assert category.value in output
            assert StorageLifecycle.UNBOUNDED_BY_DESIGN.value in output
            if target.suffix:
                assert target.read_bytes() == b"operator data"
            else:
                assert (target / "operator.bin").read_bytes() == b"operator data"

    def test_reclaim_without_confirmation_refuses_and_deletes_nothing(self, tmp_path) -> None:
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            target.mkdir(parents=True, exist_ok=True)
            (target / "cached.bin").write_bytes(b"regenerable")

            result = invoke_cached_cli(["config", "storage", "reclaim", StorageCategory.LLM_CACHE.value])

            assert result.exit_code != 0
            assert (target / "cached.bin").exists()

    def test_a_reclaimable_category_is_emptied_when_confirmed(self, tmp_path) -> None:
        """The positive control: an all-refusing surface must not pass this file."""
        with override_settings(cadrumo_local_storage_root=tmp_path):
            target = storage_path(StorageCategory.LLM_CACHE)
            target.mkdir(parents=True, exist_ok=True)
            (target / "cached.bin").write_bytes(b"regenerable")

            envelope = _json_envelope(
                ["config", "storage", "reclaim", StorageCategory.LLM_CACHE.value, "--yes"],
            )

            assert envelope["command"] == "config.storage.reclaim"
            assert envelope["result"]["removed_entries"] == 1
            assert not (target / "cached.bin").exists()
            assert target.is_dir()
