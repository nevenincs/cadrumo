"""Exercise real service boundaries without repeating profile provisioning."""

import pytest

from ...agent_service_session import AgentServiceSession

pytestmark = [
    pytest.mark.integration,
    pytest.mark.native_package,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.external_tool,
]


def test_runtime_and_service_share_the_admitted_boot(agent_service: AgentServiceSession) -> None:
    assert agent_service.runtime_ready["kind"] == "runtime_ready"
    assert agent_service.service_ready["event"] == "service_ready"
    assert agent_service.service_ready["runtime_boot_id"] == agent_service.holder_identity["runtime_boot_id"]
    assert agent_service.admission["kind"] == "service_connected"
    assert agent_service.admission["lease"]["runtime_boot_id"] == agent_service.service_ready["runtime_boot_id"]
    assert agent_service.service_ready["profile_id"] == str(agent_service.profile.profile_id)
    assert agent_service.agent_event["event"] == "agent_ready", agent_service.agent_event
    assert agent_service.setup_counts == {
        "runtime_start": 1,
        "profile_create": 1,
        "profile_setup": 1,
        "profile_login": 1,
        "holder_start": 1,
        "service_start": 1,
        "service_admission": 1,
    }


def test_service_exposes_the_provider_catalog(agent_service: AgentServiceSession) -> None:
    catalog = agent_service.admin("catalog")
    assert catalog["api_version"] == "v1"
    providers = catalog["providers"]
    assert isinstance(providers, list) and providers
    assert all(isinstance(item, dict) and "provider_id" in item for item in providers)


def test_administration_reuses_the_live_service(agent_service: AgentServiceSession) -> None:
    first = agent_service.admin("status")
    second = agent_service.admin("status")
    providers = first["providers"]
    assert isinstance(providers, list) and len(providers) > 0
    assert first["providers"] == second["providers"]
    assert all(count == 1 for count in agent_service.setup_counts.values())


def test_cli_reads_the_same_profile_after_shared_setup(agent_service: AgentServiceSession) -> None:
    code, document = agent_service.cli_read(
        "app", "ledger", "list", "--limit", "1", "--offset", "0", reveal_identifiers=True
    )
    assert code == 0
    assert document["status"] in {"success", "warning"}
    assert document["result"]["bucket_id"] == str(agent_service.profile.profile_id)
    assert all(count == 1 for count in agent_service.setup_counts.values())
