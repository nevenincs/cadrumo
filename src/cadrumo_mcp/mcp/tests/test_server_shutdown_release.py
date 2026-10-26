"""The MCP adapter releases the shared registry authority on an orderly shutdown, and only then.

The adapter serves until its stdio transport returns, which is what a client
closing stdin produces. A registry query admits the process-shared authority,
which then outlives the query. These cases serve a transport that answers one
real registry query and then returns, or then fails, against a private copy of
the published authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_store import AuthorityStoreError
from cadrumo.domain.calculations.registry.tests.shared_authority_isolation import isolated_shared_authority

from .. import authority_query
from .. import server as server_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _answer_one_registry_query() -> None:
    assert authority_query.authority_query({"query": "modelos"})["outcome"] == "published"


def test_an_orderly_shutdown_releases_the_shared_registry_authority(tmp_path: Path) -> None:
    with isolated_shared_authority(tmp_path) as database:
        served = bundled_indexed_authority()
        server_module._serve_until_orderly_shutdown(_answer_one_registry_query)

        with pytest.raises(AuthorityStoreError, match="closed"), served.operation():
            pass
        # Windows refuses to delete a file a live connection holds.
        database.unlink()


def test_a_failed_transport_leaves_the_shared_registry_authority_to_its_error(tmp_path: Path) -> None:
    def failed_transport() -> None:
        _answer_one_registry_query()
        raise OSError("stdio transport failed")

    with isolated_shared_authority(tmp_path):
        served = bundled_indexed_authority()
        with pytest.raises(OSError, match="stdio transport failed"):
            server_module._serve_until_orderly_shutdown(failed_transport)

        with served.operation() as operation:
            assert operation.pin().logical_generation
