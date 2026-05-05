"""Tests for deny-by-default AEAT remote-state guard policy."""

from __future__ import annotations

import pytest
from pydantic import AnyUrl

from aeat.core.paths import PROJECT_ROOT

from . import build_snapshot, load_registry_tree
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    evaluate_remote_operation,
    remote_state_policy_from_cross_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _open_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="m303-open",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_remote_state_guard_allows_read_only_open_simulator_get() -> None:
    result = assert_remote_operation_allowed(
        _open_policy(),
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ08.shtml"),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_blocks_post_even_on_allowed_host() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="POST",
                url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ08.shtml"),
            ),
        )


def test_remote_state_guard_blocks_stateful_tokens_in_browser_actions() -> None:
    result = evaluate_remote_operation(
        _open_policy(),
        RemoteOperation(kind="browser_action", action="Presentar declaracion"),
    )

    assert result.decision == "blocked"
    assert "presentar" in result.reason


def test_remote_state_guard_blocks_unknown_aeat_host() -> None:
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl("https://www2.agenciatributaria.gob.es/wlpl/some/path"),
            ),
        )


def test_remote_state_guard_allows_local_workbook_for_static_policy() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        evidence_tier="layout_authority",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = assert_remote_operation_allowed(policy, RemoteOperation(kind="local_workbook"))

    assert result.decision == "allowed"


def test_remote_state_guard_rejects_static_policy_live_http() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        evidence_tier="layout_authority",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = evaluate_remote_operation(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro.html"),
        ),
    )

    assert result.decision == "blocked"
    assert "static_official_only" in result.reason


def test_remote_state_guard_rejects_live_policy_without_executable_parity_tier() -> None:
    with pytest.raises(ValueError, match="requires executable parity evidence"):
        RemoteStateGuardPolicy(
            id="open-without-parity",
            evidence_tier="official_source_guidance",
            classification="open_simulator",
            allowed_hosts=("sede.agenciatributaria.gob.es",),
            synthetic_data_allowed=True,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_remote_state_guard_rejects_static_policy_as_executable_parity() -> None:
    with pytest.raises(ValueError, match="static official documentation is not executable parity evidence"):
        RemoteStateGuardPolicy(
            id="static-as-parity",
            evidence_tier="executable_parity_evidence",
            classification="static_official_only",
            allowed_hosts=(),
            synthetic_data_allowed=False,
            requires_authentication=False,
            requires_aeat_authorization=False,
        )


def test_remote_state_guard_allows_authenticated_read_surface_get() -> None:
    policy = RemoteStateGuardPolicy(
        id="filed-data-read",
        evidence_tier="official_source_guidance",
        classification="authenticated_read_surface",
        allowed_hosts=("www6.agenciatributaria.gob.es",),
        synthetic_data_allowed=False,
        requires_authentication=True,
        requires_aeat_authorization=True,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_rejects_authenticated_read_as_parity() -> None:
    with pytest.raises(ValueError, match="not executable parity evidence"):
        RemoteStateGuardPolicy(
            id="filed-data-read",
            evidence_tier="executable_parity_evidence",
            classification="authenticated_read_surface",
            allowed_hosts=("www6.agenciatributaria.gob.es",),
            synthetic_data_allowed=False,
            requires_authentication=True,
            requires_aeat_authorization=True,
        )


def test_remote_state_guard_allows_public_read_surface_get() -> None:
    policy = RemoteStateGuardPolicy(
        id="public-read",
        evidence_tier="official_source_guidance",
        classification="public_read_surface",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl(
                "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-practicas-manuales/"
                "verificacion-integridad-documentos.html"
            ),
        ),
    )

    assert result.decision == "allowed"


def test_committed_static_cross_references_reject_remote_state_operations() -> None:
    modelos, catalogues = load_registry_tree(PROJECT_ROOT / "registry" / "aeat")

    policies = [
        remote_state_policy_from_cross_reference(cross_reference)
        for modelo in modelos
        for cross_reference in _first_snapshot(modelo, catalogues).live_cross_references.values()
    ]

    assert policies
    for policy in policies:
        assert_remote_operation_allowed(policy, RemoteOperation(kind="local_workbook"))
        assert (
            evaluate_remote_operation(
                policy,
                RemoteOperation(
                    kind="http",
                    method="GET",
                    url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro.html"),
                ),
            ).decision
            == "blocked"
        )
        assert (
            evaluate_remote_operation(
                policy,
                RemoteOperation(kind="browser_action", action="Presentar declaracion"),
            ).decision
            == "blocked"
        )


def _first_snapshot(modelo, catalogues):
    for revision in modelo.revisions.values():
        year = (
            revision.period_selector.years[0] if revision.period_selector.years else revision.period_selector.year_from
        )
        if year is None:
            continue
        try:
            return build_snapshot(
                modelo,
                catalogues,
                source_root=PROJECT_ROOT,
                filing_year=year,
                period=revision.period_selector.periods[0],
            )
        except RegistrySnapshotError:
            continue
    raise AssertionError(f"modelo {modelo.id} has no selectable committed snapshot")
