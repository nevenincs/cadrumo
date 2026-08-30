"""Every module that resolves the active bucket declares a coverage disposition.

WHAT THIS GATE IS FOR, AND WHAT IT IS NOT.

Cross-profile isolation is enforced structurally, not per-caller: both
active-bucket resolvers funnel through one storage-runtime accessor that
requires readiness and a current session, and readiness raises a route mismatch
as soon as the requested bucket differs from the session's. A module that
resolves the active bucket is therefore GUARDED whether or not anything tests
it. This gate does not claim otherwise and must not be read as the thing that
makes isolation hold.

What it closes is the difference between "we tested the repositories we listed"
and "we know which resolver consumers are tested". The refusal table in
``test_runtime_attached_repositories_part1`` is hand-maintained: it proves each
listed repository refuses an absent session and a route mismatch, and nothing
notices a new consumer that never gets listed. That consumer stays protected and
becomes silently untested, which is the state that reads as coverage without
being it.

So the property gated here is declaration, not protection: every production
module reaching a resolver appears below with a disposition, and one that
appears in neither map fails until someone gives it one. A reader deciding
whether a surface is exercised gets an answer here rather than inferring it from
a table that cannot enumerate its own omissions.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....tests import package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

#: The two resolvers that attach a repository to the profile in play. Both reach
#: the same runtime accessor, so a consumer of either is route-checked.
_RESOLVERS = frozenset(
    {
        "secure_object_repository_for_active_bucket",
        "secure_object_repository_for_active_bucket_or_default_route",
    },
)

#: Resolver consumers the runtime-refusal table exercises, mapped to the case
#: name that covers them. The value is the claim being made: that case drives
#: this module's storage through a missing session and a route mismatch.
_COVERED_BY_REFUSAL_TABLE: dict[str, str] = {
    "src/cadrumo/adapters/persistence/profile/buckets.py": "bucket_events",
    "src/cadrumo/adapters/persistence/profile/_secure_model_document.py": "profile_assets",
    "src/cadrumo/adapters/persistence/storage/attachment.py": "attachment",
    "src/cadrumo/adapters/persistence/storage/envelope/_secure_repository.py": "justificante",
    "src/cadrumo/adapters/outbound/aeat/auth/session_store.py": "auth_session",
    "src/cadrumo/adapters/outbound/aeat/sede/_observation_store.py": "observation",
    "src/cadrumo/adapters/outbound/google/session_store.py": "google_oauth_token",
    "src/cadrumo/adapters/outbound/llm/_cache.py": "llm_cache_stats",
    "src/cadrumo/adapters/outbound/llm/_usage.py": "llm_usage_load",
    "src/cadrumo/adapters/outbound/llm/_consent_ledger.py": "llm_consent_ledger",
    "src/cadrumo/adapters/outbound/llm/_run_telemetry.py": "llm_run_telemetry",
    "src/cadrumo/application/auth/diagnostics.py": "auth_diagnostics",
    "src/cadrumo/application/workflow/persistence.py": "workflow_state",
    "src/cadrumo/application/modelo/_review_package_recipient_registry.py": "review_recipient_registry",
    "src/cadrumo/adapters/persistence/profile/recipient_replay_guard.py": "review_recipient_replay_guard",
}

#: Resolver consumers the refusal table does NOT reach, each with the reason.
#: These are guarded -- the resolver route-checks them like every other consumer
#: -- and unexercised by that table. An entry here is an admission, not an
#: exemption: it says a surface's refusal behaviour is asserted nowhere, which is
#: worth seeing rather than discovering during an incident.
_NOT_IN_THE_REFUSAL_TABLE: dict[str, str] = {
    "src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_page_flow.py": (
        "reaches storage inside a live browser flow the table cannot drive"
    ),
    "src/cadrumo/application/diagnostics.py": (
        "reads storage to REPORT readiness, so refusing is its subject rather than its failure mode"
    ),
    "src/cadrumo/application/repair_integrity.py": (
        "a repair path deliberately reached when storage is already unhealthy"
    ),
    "src/cadrumo/application/user_profile/custody_ports.py": (
        "custody boundary; its refusals are asserted by the custody suites rather than this table"
    ),
    "src/cadrumo/entrypoints/cli/_config/_google.py": (
        "CLI verb body; its refusals are asserted through the command surface"
    ),
}


def _modules_resolving_the_active_bucket() -> set[str]:
    """Return every production module that calls an active-bucket resolver."""
    found: set[str] = set()
    for path in package_python_files():
        relative = repo_relative(path)
        if "/tests/" in relative:
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _RESOLVERS:
                found.add(relative)
                break
    return found


def test_every_active_bucket_consumer_declares_a_coverage_disposition() -> None:
    """A new resolver consumer must be declared as covered or as not covered."""
    declared = set(_COVERED_BY_REFUSAL_TABLE) | set(_NOT_IN_THE_REFUSAL_TABLE)
    found = _modules_resolving_the_active_bucket()

    undeclared = sorted(found - declared)
    assert not undeclared, (
        "these modules resolve the active profile bucket and declare no coverage disposition: "
        f"{undeclared}. They are route-checked by the resolver like every other consumer, so this "
        "is not an exposure -- it is that nothing records whether their refusal behaviour is "
        "exercised. Add each to the covered map with the refusal case that drives it, or to the "
        "not-covered map with the reason it is not driven."
    )


def test_no_declared_consumer_has_stopped_resolving_the_active_bucket() -> None:
    """A declaration outlasting its module is a claim about code that no longer exists.

    The half that rots. A module that stops resolving the active bucket, or is
    deleted outright, leaves an entry asserting coverage of something absent --
    and a covered-map entry naming a refusal case that drives nothing reads as
    protection nobody has.
    """
    declared = set(_COVERED_BY_REFUSAL_TABLE) | set(_NOT_IN_THE_REFUSAL_TABLE)
    found = _modules_resolving_the_active_bucket()

    stale = sorted(declared - found)
    assert not stale, (
        f"these modules are declared here but no longer resolve the active profile bucket: {stale}. "
        "Remove the declaration; an entry that outlives its module claims coverage of code that is "
        "not there."
    )


def test_the_two_maps_do_not_overlap() -> None:
    """A module is covered or it is not, and claiming both hides which is true."""
    overlap = sorted(set(_COVERED_BY_REFUSAL_TABLE) & set(_NOT_IN_THE_REFUSAL_TABLE))

    assert not overlap, f"declared as both covered and not covered: {overlap}"


def test_every_not_covered_entry_states_a_reason() -> None:
    """An admission without a reason is a silent exemption."""
    empty = sorted(module for module, reason in _NOT_IN_THE_REFUSAL_TABLE.items() if not reason.strip())

    assert not empty, f"not-covered entries with no stated reason: {empty}"
