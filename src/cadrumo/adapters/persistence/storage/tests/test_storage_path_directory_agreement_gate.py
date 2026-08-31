"""Gate: a grammar's directory portion agrees with the taxonomy subpath it spells.

Every :class:`~adapters.persistence.storage.StoragePathDefinition` grammar is a
hand-written string. Where its directory portion nests beneath an already-declared
:class:`~cadrumo.core.StorageCategory` member -- ``<root>/runs/<run_id>/trace.json``
nests beneath ``StorageCategory.RUNS``'s ``"runs"`` subpath -- the two spellings
duplicate each other, and nothing previously compared them: renaming the member's
subpath would leave every grammar that spelled out its old name silently
disagreeing with the taxonomy. This gate makes that comparison live, re-derived
from :func:`~cadrumo.core.storage_location` on every run rather than a copied
constant, so a rename is caught the moment it lands.

Every ``<root>``-anchored filesystem-kind entry is checked, regardless of which
:class:`~adapters.persistence.storage.StoragePathAnchor` it declares. An earlier
version of this gate scoped itself to
:attr:`~adapters.persistence.storage.StoragePathAnchor.STORAGE_ROOT` only and
excluded the three blob-content grammars (``blob_manifest``,
``blob_content_plaintext``, ``blob_content_ciphertext``) on the grounds that their
``BLOB_STORE_ROOT`` anchor was "a genuinely distinct value" from the storage root
-- a claim later found false at HEAD (see ``StoragePathAnchor``'s own docstring for
the measured fact and the now-open question about what the two-member split still
rests on). Two replacement justifications for keeping the exclusion were proposed
and both were refuted before landing. With no surviving reason to exclude them,
measurement (an isolated-archive mutation proof) showed including the three blob
entries costs nothing -- the population grows from 25 to 28 and the gate still
passes truly -- and catches a real break the exclusion used to hide, so the
exclusion was removed rather than re-justified.

``config_reset_journal``'s ``reset-operations`` directory was the one
pre-existing exception -- joined onto the raw storage root in
``application/_config_reset_repository.py`` rather than resolved through a
declared category. That gap is closed: ``reset-operations`` is now
``StorageCategory.CONFIG_RESET_JOURNAL``'s declared subpath, so the exemption
list below is empty. Kept as a live dict rather than deleted outright, so a
future genuinely-unmatched key has a declared home to name itself in rather
than reopening this docstring.
"""

from __future__ import annotations

from typing import Final

import pytest

from .....core.storage_taxonomy_locations import storage_location
from .....core.storage_taxonomy import StorageCategory
from .....tests import literal_directory_runs
from .._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .._namespace_taxonomy import StoragePathAnchor, StoragePathKind
from .._storage_path_definitions import StoragePathDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KNOWN_DIRECTORY_SUBPATHS: Final[frozenset[str]] = frozenset(
    storage_location(category).subpath for category in StorageCategory
)

_UNDECLARED_DIRECTORY_EXEMPTIONS: Final[dict[str, str]] = {}
"""Genuinely-unmatched keys, named explicitly rather than silently skipped.

Empty today: ``config_reset_journal`` was the sole prior entry, retired once
``reset-operations`` became ``StorageCategory.CONFIG_RESET_JOURNAL``'s declared
subpath. The anti-rot test below still runs over whatever this holds, so a
future entry is proven genuine rather than trusted on the comment beside it.
"""


def _anchored_definitions() -> list[StoragePathDefinition]:
    """Every filesystem-kind (``<root>``-anchored) definition, any anchor value.

    Filters on ``anchor is not None`` rather than naming a specific
    :class:`StoragePathAnchor` member, because that is exactly what the model's
    own ``_anchor_matches_kind`` validator guarantees: an anchor is present if
    and only if the kind is not ``LOGICAL_SQL``. Naming individual members here
    (as an earlier version of this gate did, scoping to ``STORAGE_ROOT`` alone)
    means a future anchor value the filter does not yet list would silently
    fall out of the check -- ``test_anchor_presence_matches_filesystem_kind``
    below pins the construction-time guarantee this filter relies on.
    """
    return [definition for definition in STORAGE_NAMESPACE_REGISTRY.paths if definition.anchor is not None]


def test_the_taxonomy_declares_more_than_a_handful_of_directory_subpaths() -> None:
    """Non-vacuity floor: a near-empty known set would make the main gate trivial."""
    assert len(_KNOWN_DIRECTORY_SUBPATHS) > 10


def test_at_least_one_grammar_yields_a_directory_literal_run() -> None:
    """Non-vacuity floor: if every grammar yielded zero runs, the gate below
    would pass on every input without ever comparing anything."""
    total_runs = sum(
        len(literal_directory_runs(grammar=definition.grammar, kind=definition.kind))
        for definition in _anchored_definitions()
    )
    assert total_runs > 0


def test_every_filesystem_grammars_directory_portion_matches_a_declared_subpath() -> None:
    unmatched: list[str] = []
    for definition in _anchored_definitions():
        if definition.key in _UNDECLARED_DIRECTORY_EXEMPTIONS:
            continue
        runs = literal_directory_runs(grammar=definition.grammar, kind=definition.kind)
        for run in runs:
            if run not in _KNOWN_DIRECTORY_SUBPATHS:
                unmatched.append(
                    f"{definition.key!r} (grammar {definition.grammar!r}) spells directory "
                    f"segment {run!r}, which no StorageCategory declares as its subpath",
                )
    assert not unmatched, "\n".join(unmatched)


def test_the_exemption_list_names_only_genuinely_unmatched_keys() -> None:
    """Anti-rot: an exemption whose key now DOES match every run must be removed,
    or a future declaration change could hide behind a stale exemption."""
    for key in _UNDECLARED_DIRECTORY_EXEMPTIONS:
        definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(key)
        runs = literal_directory_runs(grammar=definition.grammar, kind=definition.kind)
        assert any(run not in _KNOWN_DIRECTORY_SUBPATHS for run in runs), (
            f"{key!r} is exempted but every directory segment it spells now matches a "
            "declared subpath -- remove the exemption, it no longer protects anything"
        )


def test_a_renamed_subpath_would_be_caught_positive_control() -> None:
    """Prove the detector fires: reproduce the exact drift scenario named in the
    gate's own docstring by asserting a category's subpath directly, not the
    grammar text, so the comparison is genuinely against the live taxonomy."""
    runs_grammar = STORAGE_NAMESPACE_REGISTRY.path_by_key("run_trace").grammar
    assert "/runs/" in runs_grammar, "fixture assumption: run_trace nests under 'runs'"

    # The gate compares the literal run against a LIVE lookup, not this string --
    # mutate the lookup target itself to prove the comparison is real rather than
    # trivially true because both sides read the same source.
    mutated_known_subpaths = _KNOWN_DIRECTORY_SUBPATHS - {storage_location(StorageCategory.RUNS).subpath}
    runs = literal_directory_runs(grammar=runs_grammar, kind=StoragePathKind.FILE)
    assert runs == ("runs",)
    assert not any(run in mutated_known_subpaths for run in runs), (
        "the detector must report 'runs' as unmatched once StorageCategory.RUNS's "
        "subpath is removed from the known set -- if this fails, the gate above "
        "cannot actually catch a rename"
    )


def test_an_undeclared_directory_literal_is_caught_by_construction() -> None:
    """A second positive control: a synthetic grammar naming a directory no
    category declares must be reported unmatched, proving the main gate's
    membership test is not vacuously true for every string."""
    bogus_run = "definitely-not-a-declared-storage-category-subpath"
    assert bogus_run not in _KNOWN_DIRECTORY_SUBPATHS
    runs = literal_directory_runs(grammar=f"<root>/{bogus_run}/<bucket_id>/file.json", kind=StoragePathKind.FILE)
    assert runs == (bogus_run,)


def test_a_blob_grammar_break_would_be_caught_positive_control() -> None:
    """Prove the widened gate genuinely checks the three ``BLOB_STORE_ROOT``
    entries it used to skip, not merely include them without effect.

    Measured before this gate was widened (isolated-archive mutation proof, not
    argued): collapsing the old ``STORAGE_ROOT``-only filter grew the checked
    population from 25 to 28, the gate still passed truly, and mutating
    ``blob_manifest``'s literal run (``blobs`` -> ``blobsX``) reddened with a
    precise unmatched-segment message. This test pins that exact mutation as a
    standing regression check.
    """
    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("blob_manifest")
    assert definition.anchor is StoragePathAnchor.BLOB_STORE_ROOT
    mutated_grammar = definition.grammar.replace("blobs", "blobsX", 1)
    assert mutated_grammar != definition.grammar, "fixture assumption: blob_manifest's grammar spells 'blobs'"
    runs = literal_directory_runs(grammar=mutated_grammar, kind=definition.kind)
    assert runs == ("blobsX",)
    assert runs[0] not in _KNOWN_DIRECTORY_SUBPATHS, (
        "fixture assumption: 'blobsX' must not coincidentally match any declared subpath, "
        "or this mutation would not prove the widened gate catches a real break"
    )


def test_anchor_presence_matches_filesystem_kind() -> None:
    """Closes a fail-open in ``_anchored_definitions``'s filter, not merely in the
    model.

    :meth:`StoragePathDefinition._anchor_matches_kind` already enforces this
    at construction (a ``LOGICAL_SQL`` entry must not declare an anchor; every
    other kind must). Nothing previously asserted that guarantee here, and
    ``_anchored_definitions`` relies on it directly: it filters on
    ``anchor is not None`` rather than naming individual anchor values, so a
    future kind/anchor pairing that violated this invariant would silently
    change which entries the directory-agreement gate above checks, with
    nothing failing loudly to say so.
    """
    for definition in STORAGE_NAMESPACE_REGISTRY.paths:
        if definition.kind is StoragePathKind.LOGICAL_SQL:
            assert definition.anchor is None, (
                f"{definition.key!r} is LOGICAL_SQL but declares an anchor -- "
                "a db:// logical path has no <root> token to anchor"
            )
        else:
            assert definition.anchor is not None, (
                f"{definition.key!r} is {definition.kind.value} but declares no anchor -- "
                "it would silently fall out of every anchor-filtered check above"
            )


_EXPECTED_RENDERED_GRAMMARS: Final[dict[str, str]] = {
    "root_fallback_database": "<root>/cadrumo.db",
    "bucket_root": "<root>/buckets/<bucket_id>/",
    "bucket_db": "<root>/buckets/<bucket_id>/db/",
    "bucket_database_file": "<root>/buckets/<bucket_id>/db/cadrumo.db",
    "bucket_blobs": "<root>/buckets/<bucket_id>/blobs/",
    "bucket_lock": "<root>/buckets/<bucket_id>/.lock",
    "bucket_output_language_hint": "<root>/buckets/<bucket_id>/output-language.hint",
    "profile_capsule_password_envelope": "<root>/buckets/<bucket_id>/custody/envelope.v1.json",
    "profile_capsule_recovery_envelope": "<root>/buckets/<bucket_id>/custody/recovery.v1.json",
    "profile_capsule_commit": "<root>/buckets/<bucket_id>/profile.commit.v1.json",
    "active_profile_pointer": "<root>/active-profile",
    "keystore_bucket": "<root>/keystore/<bucket_id>/",
    "profile_session": "<root>/keystore/<bucket_id>/session.v2.json",
    "profile_session_retirement_journal": "<root>/keystore/<bucket_id>/session.v2.retirement.json",
    "login_throttle": "<root>/keystore/<bucket_id>/login-throttle.json",
    "profile_legal_hold_snapshot": "<root>/profile-custody-holds/legal-case-owner/<profile_id>.json",
    "profile_filing_retention_snapshot": ("<root>/profile-custody-holds/filing-retention-owner/<profile_id>.json"),
    "profile_custody_hold_evidence": ("<root>/profile-custody-holds/derived-evidence/<owner>/<profile_id>.json"),
    "secret_index": "<root>/secrets/index.json",
    "config_reset_journal": "<root>/reset-operations/<operation_id>.json",
    "operation_journal": "<root>/operation-journals/<operation_id>.json",
    "secure_objects_table": "db://secure_objects/<namespace>/<object_key>",
    "blob_manifest": "<root>/blobs/<sha256[:2]>/<sha256>.manifest.json",
    "blob_content_plaintext": "<root>/blobs/<sha256[:2]>/<sha256>",
    "blob_content_ciphertext": "<root>/blobs/<sha256[:2]>/<sha256>.enc",
    "local_provider_object": "<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.bin",
    "local_provider_object_sidecar": ("<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.meta.json"),
    "run_trace": "<root>/runs/<run_id>/trace.json",
    "run_events": "<root>/runs/<run_id>/events.jsonl",
    "run_envelope": "<root>/runs/<run_id>/envelope.json",
    "llm_usage_record": "<root>/llm-usage/usage-<timestamp>.jsonl",
    "llm_run_telemetry_record": "<root>/llm-run-telemetry/run-telemetry-<timestamp>.jsonl",
    "auth_acquisition_lock": "<root>/tokens/<bucket_id>-<auth_provider_kind>-auth.lock",
    "validation_verdict_cache_entry": ("<root>/cache/registry-verdict/cadrumo_validation_verdict_<sha256[:16]>.json"),
    "llm_cache_entry": "<root>/cache/llm-cache/<provider>/<model>/<sha256>-<sha256>.json",
}
"""One byte-exact expected string per :data:`STORAGE_PATH_DEFINITIONS` key.

The directory-agreement gate above checks *membership*: every literal run a
grammar spells must be SOME declared subpath. Measured directly against
:func:`~cadrumo.tests.literal_directory_runs`, that check catches a
DOUBLED segment (``bucket_database_file`` briefly interpolated
``BUCKET_DB_DIRNAME`` twice, rendering ``<root>/buckets/<bucket_id>/db/db/cadrumo.db``;
the collapsed run ``"db/db"`` matches no declared subpath, so the existing
gate above already fails on it) -- but it cannot catch a DROPPED segment.
Removing the same interpolated segment renders
``<root>/buckets/<bucket_id>/cadrumo.db``: the run set shrinks from
``("buckets", "db")`` to ``("buckets",)``, and ``"buckets"`` alone is still
a real, declared subpath, so membership holds and the gate above reports
nothing missing. A membership check can only see an EXTRA run that matches
nothing; it is structurally blind to a run that silently stopped
appearing. This test closes that gap with a full-string equality pin, so a
dropped interpolation segment -- which produces zero unmatched tokens --
still fails loudly here.
"""


def test_every_definitions_rendered_grammar_matches_its_pinned_string() -> None:
    """Full-string pin, catching a dropped interpolation segment the membership gate cannot see."""
    actual = {definition.key: definition.grammar for definition in STORAGE_NAMESPACE_REGISTRY.paths}
    assert actual == _EXPECTED_RENDERED_GRAMMARS


def test_the_pinned_grammar_map_covers_every_declared_key() -> None:
    """Anti-rot: a new StoragePathDefinition must be added here, not silently pass by omission."""
    actual_keys = {definition.key for definition in STORAGE_NAMESPACE_REGISTRY.paths}
    assert actual_keys == set(_EXPECTED_RENDERED_GRAMMARS)
