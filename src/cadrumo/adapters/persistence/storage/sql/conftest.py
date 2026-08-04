"""Shared fixtures for storage/sql tests.

These tests self-provision an isolated secure-storage runtime per test through a
function-scoped ``tmp_path`` (each ``isolated_runtime_profile`` /
``isolated_ephemeral_secure_sql`` call receives its own storage root), so
per-test isolation comes from filesystem separation rather than a shared
module-scoped fixture. No module-shared runtime and no per-test on-disk reset is
needed here: nothing is shared across tests, so there is no cross-test bleed.

The module-scope hoist with ``Session().begin_nested()`` rollback that a prior
attempt (peer commit ``4f83fefb9``) added here was never wired into any test and
``begin_nested`` was never implemented; the surfaces that genuinely reuse a
module-shared runtime (application/filing, application/ledger) do so with a real
per-test ``reset_secure_object_store`` teardown, not a savepoint.
"""

from __future__ import annotations
