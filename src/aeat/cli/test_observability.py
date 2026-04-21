"""Tests for the shared ``cli_run_context`` helpers (#99)."""

from __future__ import annotations

import pytest

from ..observability import ArgumentSource
from ._observability import build_arguments

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class TestBuildArguments:
    def test_preserves_insertion_order_for_flags(self) -> None:
        values = {"b_flag": "1", "a_flag": "2", "c_flag": "3"}
        records = build_arguments(values)
        assert tuple(r.name for r in records) == ("b_flag", "a_flag", "c_flag")
        assert all(r.source is ArgumentSource.FLAG for r in records)

    def test_positional_first_then_flags(self) -> None:
        values = {"as_json": True, "run_id": "abcd1234", "since": "2026-01-01"}
        records = build_arguments(values, positional=("run_id",))
        assert records[0].name == "run_id"
        assert records[0].source is ArgumentSource.POSITIONAL
        flag_names = tuple(r.name for r in records[1:])
        assert flag_names == ("as_json", "since")
        assert all(r.source is ArgumentSource.FLAG for r in records[1:])

    def test_multiple_positionals_preserve_declared_order(self) -> None:
        values = {"modelo": "130", "period": "2026Q1", "force": True}
        records = build_arguments(values, positional=("modelo", "period"))
        positional_names = tuple(r.name for r in records if r.source is ArgumentSource.POSITIONAL)
        assert positional_names == ("modelo", "period")

    def test_none_values_are_skipped(self) -> None:
        values = {"modelo": None, "period": "2026Q1"}
        records = build_arguments(values, positional=("modelo",))
        assert tuple(r.name for r in records) == ("period",)
