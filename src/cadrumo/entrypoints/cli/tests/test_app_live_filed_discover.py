"""Conformance and behaviour for the ``app live filed discover`` verb.

The envelope-level conformance cases are written out explicitly here rather than
left to the shared parametrised gates in ``test_json_schema_conformance.py``.
Those gates parametrise over the immutable command-spec schema projection at COLLECTION
time, and that module imports only the ``config`` payload modules -- so the whole
``app.live.*`` schema family, including the two shipped ``filed`` verbs, never
reaches ``test_registered_schema_envelope_round_trips`` or
``test_registered_schema_has_no_bespoke_notice_field``. Relying on those cases
here would be a green that never ran. The two properties are therefore asserted
directly against this verb's schema.

The behaviour cases cover what the verb tells the operator. The result payload
and the notices are built by pure functions over a
:class:`FiledHistoryDiscoveryReport`, so they are exercised without a live
session -- which is the point of the design, not a shortcut around it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from ....adapters.outbound.aeat.sede.schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport
from ....application.live.filed_data_capture import (
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryReport,
    filed_history_discovery_report,
)
from ....core import FiledHistoryDiscoverySignal
from ....core.json_contract import NoticeSeverity, SchemaEnvelope
from .._app_live import _filed_discover_notices, _filed_discover_result_and_lines
from .._app_live_command_specs import LIVE_COMMAND_SPECS
from .._app_live_filed_payloads import FiledDiscoverResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SCHEMA_KEY = "app.live.filed.discover"


def _offered_100_2024() -> FiledDeclarationAvailabilityReport:
    """A register option set offering one pair the profile below never expects."""
    return FiledDeclarationAvailabilityReport(
        items=(FiledDeclarationAvailability(modelo="100", ejercicios=(2024,)),),
        discovered_at=datetime(2026, 8, 7, 11, 0, tzinfo=UTC),
    )


def _expects_303_2025() -> ExpectedFiledDeclarationGrid:
    return ExpectedFiledDeclarationGrid(
        modelos=("303",),
        ejercicios=(2025,),
        activity_start_declared=True,
    )


def _profile_report() -> FiledHistoryDiscoveryReport:
    return filed_history_discovery_report(expected=_expects_303_2025(), availability=None)


def _both_signals_report() -> FiledHistoryDiscoveryReport:
    return filed_history_discovery_report(expected=_expects_303_2025(), availability=_offered_100_2024())


def _register_only_report() -> FiledHistoryDiscoveryReport:
    return filed_history_discovery_report(
        expected=ExpectedFiledDeclarationGrid(),
        availability=_offered_100_2024(),
    )


# --------------------------------------------------------------- conformance


def test_the_verb_registers_its_schema() -> None:
    spec = next(spec for spec in LIVE_COMMAND_SPECS if spec.result_schema.identity == _SCHEMA_KEY)
    assert spec.result_schema.target is not None
    assert spec.result_schema.target.qualname == FiledDiscoverResult.__name__


def test_the_schema_specialises_the_shared_envelope() -> None:
    envelope_cls = cast(Any, SchemaEnvelope)[FiledDiscoverResult]
    assert envelope_cls.__pydantic_generic_metadata__["args"] == (FiledDiscoverResult,)


def test_the_schema_carries_no_bespoke_notice_field() -> None:
    forbidden = {
        "next",
        "suggestion",
        "suggestions",
        "hint",
        "hints",
        "advisory",
        "advisories",
        "source_advisories",
    }
    offending = sorted(
        name
        for name in FiledDiscoverResult.model_fields
        if name in forbidden or name.endswith(("_advisory", "_advisories"))
    )
    assert offending == []


def test_the_result_survives_a_strict_json_roundtrip() -> None:
    result, _lines = _filed_discover_result_and_lines(_profile_report())
    assert FiledDiscoverResult.model_validate_json(result.model_dump_json()) == result


# ------------------------------------------------------------------ payload


def test_the_payload_carries_each_pairs_signals_and_its_anomaly_flag() -> None:
    result, _lines = _filed_discover_result_and_lines(_both_signals_report())
    by_modelo = {pair.modelo: pair for pair in result.pairs}

    assert by_modelo["303"].signals == [FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value]
    assert by_modelo["303"].zero_rows_is_an_anomaly is True
    assert by_modelo["100"].signals == [FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS.value]
    assert by_modelo["100"].zero_rows_is_an_anomaly is False


def test_the_counts_separate_the_two_signals() -> None:
    result, _lines = _filed_discover_result_and_lines(_both_signals_report())
    assert result.pair_count == 2
    assert result.profile_expected_count == 1
    assert result.register_options_only_count == 1
    assert result.carries_a_taxpayer_specific_denominator is True


def test_the_text_lines_and_the_payload_report_the_same_counts() -> None:
    result, lines = _filed_discover_result_and_lines(_profile_report())
    joined = "\n".join(lines)
    assert f"{result.pair_count}" in joined
    assert "profile_expected_count" in joined
    assert "register_options_only_count" in joined
    # Every pair is rendered with its signal set, so the text surface cannot
    # report a pair while hiding what nominated it.
    assert joined.count("pair") >= len(result.pairs)
    assert FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY.value in joined


# ------------------------------------------------------------------ notices


def test_the_register_scope_caveat_always_fires() -> None:
    # The caveat is unconditional because the misreading it guards against does
    # not depend on how many register-only pairs came back: it is about what the
    # option list establishes at all.
    for report in (_profile_report(), _register_only_report()):
        codes = [notice.code for notice in _filed_discover_notices(report)]
        assert "live.filed.discover.register_options_scope_unconfirmed" in codes


def test_a_report_with_a_profile_denominator_raises_no_warning() -> None:
    notices = _filed_discover_notices(_profile_report())
    assert [notice.severity for notice in notices] == [NoticeSeverity.INFO]


def test_a_report_without_a_profile_denominator_warns() -> None:
    notices = _filed_discover_notices(_register_only_report())
    warnings = [notice for notice in notices if notice.severity is NoticeSeverity.WARNING]
    assert len(warnings) == 1
    assert warnings[0].code == "live.filed.discover.no_taxpayer_specific_denominator"


def test_every_notice_message_resolves_to_real_copy() -> None:
    # A notice whose message is still its locale key would put the key itself in
    # front of the operator, which is the failure the locale honesty gate exists
    # for; assert it here too because this verb's notices are its whole caveat.
    for report in (_profile_report(), _register_only_report()):
        for notice in _filed_discover_notices(report):
            assert notice.message
            assert "cli.app.live.filed." not in notice.message


def test_every_notice_carries_machine_queryable_context() -> None:
    for notice in _filed_discover_notices(_register_only_report()):
        assert notice.context
        assert all(isinstance(value, str) for value in notice.context.values())
