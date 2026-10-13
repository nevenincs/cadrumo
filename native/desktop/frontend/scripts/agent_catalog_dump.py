"""Print what cadrumo-agent declares about its provider lanes, as JSON.

Run by ``agent-catalog-fixture.mjs`` with the interpreter of a cadrumo-agent
checkout, so every value is read from the agent's own registry and projected
through the agent's own catalog response; nothing is restated here. Reads no
network, starts no provider and writes nothing.

usage: agent_catalog_dump.py <backend provider-settings catalog.toml>
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import cadrumo_agent
from cadrumo_agent.api.schemas.provider_catalog import ProviderCatalogResponse
from cadrumo_agent.graph.enums import ExecutionLane
from cadrumo_agent.providers.effort import gateway_effort_control
from cadrumo_agent.providers.execution_modes import external_execution_mode
from cadrumo_agent.providers.provider_catalog import (
    AdmissionState,
    AuthenticationState,
    CatalogState,
    CatalogStatus,
    HealthState,
    ProviderCatalog,
    ProviderCatalogKey,
    ProviderHealthAxes,
    ProviderRecord,
    StructuredProviderHealth,
)
from cadrumo_agent.providers.registry import PROVIDERS
from cadrumo_agent.providers.selection import DECLARED_CATALOG_REVISION

# The files whose content decides what is printed; their digest tells a reader
# of the generated module which agent it was generated from.
SOURCES = (
    "provider_definitions.py",
    "graph/enums.py",
    "providers/registry.py",
    "providers/gateways.py",
    "providers/execution_modes.py",
    "providers/effort.py",
    "api/schemas/provider_catalog.py",
)

# The backend's catalogue is the one place a lane's credential kind is
# declared; the agent declares the rest, so the two must agree on it.
SETTINGS_FIELDS = ("provider", "transport", "display_name", "default_base_url")


def source_digest() -> str:
    """Hash the agent declarations that determine the generated catalog."""
    root = Path(cadrumo_agent.__file__).parent
    digest = hashlib.sha256()
    for relative in SOURCES:
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def records() -> tuple[ProviderRecord, ...]:
    """One record per lane, with no health or models: only the declarations."""
    now = datetime.now(UTC)
    health = StructuredProviderHealth.derive(
        ProviderHealthAxes(
            HealthState.UNKNOWN,
            HealthState.UNKNOWN,
            AuthenticationState.UNKNOWN,
            CatalogStatus.UNKNOWN,
            AdmissionState.UNKNOWN,
        ),
        checked_at=now,
    )
    out: list[ProviderRecord] = []
    for lane in ExecutionLane:
        descriptor = PROVIDERS[lane]
        mode = external_execution_mode(lane, "node")
        key = ProviderCatalogKey(provider_id=lane.value, execution_mode=mode)
        if descriptor.gateway is None:
            catalog = ProviderCatalog(key, CatalogState(CatalogStatus.UNKNOWN, now), ())
        else:
            effort = gateway_effort_control(descriptor.gateway)
            catalog = ProviderCatalog(
                key,
                CatalogState(CatalogStatus.AVAILABLE, now, revision=DECLARED_CATALOG_REVISION),
                (),
                () if effort is None else (effort,),
            )
        out.append(ProviderRecord(lane.value, descriptor.display_name, mode, health, catalog))
    return tuple(out)


def settings_lanes(backend_catalog: Path) -> list[dict[str, object]]:
    """The lanes a profile keeps a credential for, checked against the agent.

    A lane is addressed as ``<provider>_<transport>``: the pair the agent
    defines, which is also how its runs name a lane.
    """
    declared = tomllib.loads(backend_catalog.read_text(encoding="utf-8"))["providers"]
    agent: dict[tuple[str, str], dict[str, object]] = {}
    for lane in ExecutionLane:
        descriptor = PROVIDERS[lane]
        gateway = descriptor.gateway
        pair = (lane.provider.value, lane.transport.value)
        agent[pair] = {
            "id": f"{pair[0]}_{pair[1]}",
            "provider": pair[0],
            "transport": pair[1],
            "display_name": descriptor.display_name,
            "default_base_url": None if gateway is None else gateway.base_url_default,
        }
    served = {(row["provider"], row["transport"]): row for row in declared}
    if set(served) != set(agent):
        raise SystemExit(f"the backend's lanes {sorted(served)} are not the agent's {sorted(agent)}")
    lanes: list[dict[str, object]] = []
    for pair, expected in agent.items():
        row = served[pair]
        for field in SETTINGS_FIELDS:
            if row.get(field) != expected[field]:
                raise SystemExit(
                    f"lane {pair}: the backend's {field} is {row.get(field)!r}, the agent's is {expected[field]!r}"
                )
        lanes.append({**expected, "auth_kind": row["auth_kind"]})
    return lanes


def main() -> None:
    """Write the agent declarations and matching backend settings as JSON."""
    backend_catalog = Path(sys.argv[1])
    response = ProviderCatalogResponse.from_records(records()).model_dump(mode="json")
    lanes = []
    for record in response["providers"]:
        catalog = record["catalog"]
        lanes.append(
            {
                "provider_id": record["provider_id"],
                "transport": record["transport"],
                "display_name": record["display_name"],
                "execution_mode": record["execution_mode"],
                "executable": record["executable"],
                "model_source": record["model_source"],
                "catalog_revision": catalog["state"]["revision"],
                "native_controls": catalog["native_controls"],
                # Which capabilities the agent states for the lane, and for
                # which tool server; the state is the generating host's own,
                # so it is left out.
                "capability_proofs": [
                    {"capability": proof["capability"], "entry": proof["entry"]}
                    for proof in record["capability_proofs"]
                ],
            }
        )
    sys.stdout.write(
        json.dumps({"digest": source_digest(), "lanes": lanes, "settings": settings_lanes(backend_catalog)}) + "\n"
    )


main()
