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

Scoped to :attr:`~adapters.persistence.storage.StoragePathAnchor.STORAGE_ROOT`
entries only. The three blob-content grammars
(``blob_manifest``, ``blob_content_plaintext``, ``blob_content_ciphertext``) anchor
their ``<root>`` token at
:class:`~adapters.persistence.storage.blob_store.EncryptedBlobStore`'s own
``root_dir`` instead -- a different coordinate system BY CONTRACT (whatever the
two currently happen to resolve to in production), with no ``StorageCategory``
subpath declared relative to IT for this gate to compare against. An earlier
version of this gate matched their literal ``blobs`` run against
``StorageCategory.BLOBS.subpath`` (also ``"blobs"``) and reported agreement --
but the two spellings only coincided by sharing a name; the gate was comparing
two different anchors, not verifying one. That risk is value-independent: even
on a day both anchors resolve to the same directory, a check that conflates
them still verifies nothing but a coincidental token match. See
``StoragePathAnchor``'s own docstring for the full reasoning.

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

from .....core import StorageCategory, storage_location
from .....tests import literal_directory_runs
from .. import STORAGE_NAMESPACE_REGISTRY, StoragePathAnchor, StoragePathKind

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


def _storage_root_anchored_definitions() -> list[object]:
    return [
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.paths
        if definition.anchor is StoragePathAnchor.STORAGE_ROOT
    ]


def _filesystem_kind_definitions() -> list[object]:
    return _storage_root_anchored_definitions()


def test_the_taxonomy_declares_more_than_a_handful_of_directory_subpaths() -> None:
    """Non-vacuity floor: a near-empty known set would make the main gate trivial."""
    assert len(_KNOWN_DIRECTORY_SUBPATHS) > 10


def test_at_least_one_grammar_yields_a_directory_literal_run() -> None:
    """Non-vacuity floor: if every grammar yielded zero runs, the gate below
    would pass on every input without ever comparing anything."""
    total_runs = sum(
        len(literal_directory_runs(grammar=definition.grammar, kind=definition.kind))
        for definition in _filesystem_kind_definitions()
    )
    assert total_runs > 0


def test_every_filesystem_grammars_directory_portion_matches_a_declared_subpath() -> None:
    unmatched: list[str] = []
    for definition in _filesystem_kind_definitions():
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


def test_the_blob_store_root_anchor_excludes_three_real_entries_not_an_empty_set() -> None:
    """Confirms the STORAGE_ROOT scoping above genuinely excludes real entries.

    Without this, an accidental filter bug (e.g. a typo'd anchor comparison
    that matches nothing, or everything) would silently pass the main gate by
    leaving it with zero or the full set to check -- this proves the excluded
    group is exactly the three blob-content entries the module docstring
    names, no more and no fewer.
    """
    blob_store_root_definitions = [
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.paths
        if definition.anchor is StoragePathAnchor.BLOB_STORE_ROOT
    ]
    assert {definition.key for definition in blob_store_root_definitions} == {
        "blob_manifest",
        "blob_content_plaintext",
        "blob_content_ciphertext",
    }


def test_a_blob_store_root_entrys_blobs_literal_would_falsely_agree_by_name_collision() -> None:
    """Reproduces the exact false-positive the earlier gate shape produced.

    ``blob_content_plaintext``'s literal run ('blobs') coincidentally equals
    ``StorageCategory.BLOBS.subpath`` -- proving that checking it against the
    known-subpath set, as the main gate does for STORAGE_ROOT entries, would
    have reported "agreement" here too. The two anchors are distinct BY
    CONTRACT (see the module docstring and StoragePathAnchor) whatever they
    currently happen to resolve to, so that agreement would have been
    coincidental, not verified -- which is exactly why this key is excluded
    from the main gate rather than included and passing.
    """
    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key("blob_content_plaintext")
    assert definition.anchor is StoragePathAnchor.BLOB_STORE_ROOT
    runs = literal_directory_runs(grammar=definition.grammar, kind=definition.kind)
    assert runs == ("blobs",)
    assert runs[0] in _KNOWN_DIRECTORY_SUBPATHS, (
        "fixture assumption: 'blobs' must still coincidentally match BLOBS.subpath for this "
        "test to demonstrate the false-positive risk the anchor exclusion avoids"
    )


_EXPECTED_RENDERED_GRAMMARS: Final[dict[str, str]] = {
    "root_fallback_database": "<root>/cadrumo.db",
    "bucket_root": "<root>/buckets/<bucket_id>/",
    "bucket_db": "<root>/buckets/<bucket_id>/db/",
    "bucket_database_file": "<root>/buckets/<bucket_id>/db/cadrumo.db",
    "bucket_blobs": "<root>/buckets/<bucket_id>/blobs/",
    "bucket_audit": "<root>/buckets/<bucket_id>/audit/",
    "bucket_manifest": "<root>/buckets/<bucket_id>/manifest.toml",
    "bucket_lock": "<root>/buckets/<bucket_id>/.lock",
    "bucket_output_language_hint": "<root>/buckets/<bucket_id>/output-language.hint",
    "keystore_bucket": "<root>/keystore/<bucket_id>/",
    "bucket_dek": "<root>/keystore/<bucket_id>/bucket.dek.json",
    "profile_session": "<root>/keystore/<bucket_id>/session.v1.json",
    "login_throttle": "<root>/keystore/<bucket_id>/login-throttle.json",
    "secret_index": "<root>/secrets/index.json",
    "config_reset_journal": "<root>/reset-operations/<operation_id>.json",
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
