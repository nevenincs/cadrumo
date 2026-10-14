"""The provider catalog crosses the worker pipe as its JSON document and is parsed by the worker at use.

The request is built as the runtime builds it, written and read through the
worker request model, and its catalog read through the catalog's own parser.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from cadrumo.application.runtime.profile_worker import ProfileWorkerAgentCredentialsRequest, ProfileWorkerRequest
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.domain.provider_settings.catalog import parse_provider_catalog

from ..worker_agent_credentials import request_catalog

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DOCUMENT = json.dumps(
    {
        "schema_version": 1,
        "providers": [
            {
                "id": "example_api",
                "provider": "example",
                "transport": "api",
                "display_name": "Example",
                "auth_kind": "api_key_with_base_url",
                "default_base_url": "https://gateway.example.invalid/v1",
                "agent_credential_id": "example",
                "cli_programs": [],
            },
            {
                "id": "example_cli",
                "provider": "example",
                "transport": "cli",
                "display_name": "Example",
                "auth_kind": "provider_sign_in_only",
                "default_base_url": None,
                "agent_credential_id": None,
                "cli_programs": ["example"],
            },
        ],
    }
)


def _received(catalog_document: dict[str, object]) -> ProfileWorkerAgentCredentialsRequest:
    sent = ProfileWorkerRequest(
        ProfileWorkerAgentCredentialsRequest.model_validate(
            {"request_id": uuid4(), "session_id": uuid4(), "catalog": catalog_document}
        )
    )
    received = ProfileWorkerRequest.model_validate_json(sent.model_dump_json()).root
    assert isinstance(received, ProfileWorkerAgentCredentialsRequest)
    return received


def test_the_worker_reads_back_the_catalog_the_runtime_sent() -> None:
    catalog = parse_provider_catalog(_DOCUMENT)

    assert request_catalog(_received(catalog.model_dump(mode="json"))) == catalog


def test_a_catalog_its_parser_refuses_is_refused_as_invalid() -> None:
    malformed = json.loads(_DOCUMENT)
    malformed["providers"][0]["transport"] = "carrier-pigeon"

    with pytest.raises(AutomationCustodyError) as refused:
        request_catalog(_received(malformed))

    assert refused.value.reason is AutomationCustodyCode.INVALID
