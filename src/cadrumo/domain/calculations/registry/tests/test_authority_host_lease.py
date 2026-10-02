"""A host's physical publication lease does not borrow an asyncio task's context."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack

import pytest

from ..authority import IndexedRegistryAuthority, PinnedAuthorityOperation, bundled_authority_descriptor_path
from ..governed_fact_scope import (
    governed_facts_in_scope,
    outside_governed_fact_validation,
    validating_governed_facts,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def test_host_lease_crosses_tasks_without_leaking_fact_scope() -> None:
    authority = IndexedRegistryAuthority(bundled_authority_descriptor_path())
    lifetime = ExitStack()

    async def acquire() -> PinnedAuthorityOperation:
        pinned = lifetime.enter_context(authority.lease_operation())
        assert governed_facts_in_scope() is None
        return pinned

    async def query(pinned: PinnedAuthorityOperation) -> None:
        assert governed_facts_in_scope() is None
        with validating_governed_facts(pinned):
            assert governed_facts_in_scope() is pinned
            assert pinned.profile_decode_context().generation == pinned.generation
            await asyncio.sleep(0)
            assert governed_facts_in_scope() is pinned
        assert governed_facts_in_scope() is None

    async def exercise() -> None:
        pinned = await asyncio.create_task(acquire())
        await asyncio.gather(query(pinned), query(pinned))
        assert governed_facts_in_scope() is None
        lifetime.close()
        with authority.operation() as ordinary:
            assert governed_facts_in_scope() is ordinary
            assert ordinary.generation == pinned.generation
        assert governed_facts_in_scope() is None

    try:
        with outside_governed_fact_validation():
            asyncio.run(exercise())
    finally:
        lifetime.close()
        authority.close()
