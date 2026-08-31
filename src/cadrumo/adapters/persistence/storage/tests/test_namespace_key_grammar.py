"""Prove each corrected namespace grammar describes the live object-key shape.

The :data:`~adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE` and
:data:`~adapters.persistence.storage.CALCULATION_OBSERVATIONS_NAMESPACE`
``object_key_grammar`` fields are the sole metadata authority for the secure-object
keys their repositories write. These tests derive the real object keys from the
production key-derivation helpers and assert the declared grammar matches them, so a
future drift between the grammar and the live key shape fails loudly rather than
sitting as stale documentation.
"""

from __future__ import annotations

import hashlib
import re

import pytest

from .....application.calculations import member_observation_key, observation_key
from .....core.period import Period
from .....domain.transactions.repository import transaction_index_object_key, transaction_object_key
from .. import CALCULATION_OBSERVATIONS_NAMESPACE, TRANSACTION_CATALOGUE_NAMESPACE
from .._secure_object_namespaces import STORAGE_NAMESPACE_REGISTRY
from ..errors import NamespaceRegistryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_MEMBER_ID = "GRUPO-MEMBER-PLACEHOLDER-A"
"""Obviously-synthetic stand-in for a grupo member identifier.

The key builder normalises and digests whatever it is handed, so the identity
contract under test is independent of the identifier grammar. Using a token no
identifier authority would ever issue keeps a realistic tax identifier out of
the test corpus entirely.
"""

_OTHER_MEMBER_ID = "GRUPO-MEMBER-PLACEHOLDER-B"


def _shape_to_regex(shape: str) -> re.Pattern[str]:
    """Compile one declared key-grammar shape into an anchored matcher.

    ``{placeholder}`` matches one non-``:`` segment; a ``[...]`` group is an
    optional segment; every other character is a literal separator.
    """
    parts: list[str] = ["^"]
    index = 0
    while index < len(shape):
        char = shape[index]
        if char == "{":
            close = shape.index("}", index)
            parts.append("[^:]+")
            index = close + 1
        elif char == "[":
            parts.append("(?:")
            index += 1
        elif char == "]":
            parts.append(")?")
            index += 1
        else:
            parts.append(re.escape(char))
            index += 1
    parts.append("$")
    return re.compile("".join(parts))


def _declared_shapes(grammar: str) -> list[re.Pattern[str]]:
    return [_shape_to_regex(shape.strip()) for shape in grammar.split(";")]


def _matches_any(key: str, shapes: list[re.Pattern[str]]) -> bool:
    return any(shape.match(key) for shape in shapes)


def test_transaction_catalogue_grammar_describes_live_secure_object_keys() -> None:
    shapes = _declared_shapes(TRANSACTION_CATALOGUE_NAMESPACE.object_key_grammar)

    row_key = transaction_object_key("bucket-7", "tx-42")
    index_key = transaction_index_object_key("bucket-7")

    assert row_key == "transaction:bucket-7:tx-42"
    assert index_key == "transaction-index:bucket-7"

    # Every live key the repository writes conforms to a declared shape.
    assert _matches_any(row_key, shapes)
    assert _matches_any(index_key, shapes)

    # Every declared shape is realized by a live key: no dead grammar entry.
    for shape in shapes:
        assert shape.match(row_key) or shape.match(index_key)

    # Anti-tautology: the BucketEvent audit object_id is a different concept and
    # must not be accepted as a secure-object key by this namespace's grammar.
    assert not _matches_any("transaction-catalogue:bucket-7", shapes)


def test_transaction_catalogue_pre_correction_grammar_rejected_the_live_keys() -> None:
    """The retired ``transaction-catalogue:{bucket_id}`` grammar matched neither key."""
    drifted = _declared_shapes("transaction-catalogue:{bucket_id}")

    assert not _matches_any(transaction_object_key("b", "t"), drifted)
    assert not _matches_any(transaction_index_object_key("b"), drifted)


def test_calculation_observation_grammar_describes_single_and_member_keys() -> None:
    shapes = _declared_shapes(CALCULATION_OBSERVATIONS_NAMESPACE.object_key_grammar)
    period = Period.from_year_and_code(2024, "1T")

    single_key = observation_key("353", period)
    member_key = member_observation_key("353", period, _MEMBER_ID)

    # The member key extends the single-filer key with a trailing digest segment.
    # The expected digest is computed here from the stdlib over the canonical
    # token, never read back from the production helper.
    expected_digest = hashlib.sha256(_MEMBER_ID.encode("utf-8")).hexdigest()
    assert member_key == f"{single_key}:{expected_digest}"
    assert _MEMBER_ID not in member_key

    assert _matches_any(single_key, shapes)
    assert _matches_any(member_key, shapes)

    # Anti-tautology: a truncated two-segment key is not a valid observation key.
    assert not _matches_any("100:2024", shapes)


def test_member_segment_addresses_one_identity_across_spellings() -> None:
    """Two renderings of ONE member token address ONE row; two members do not.

    The member segment is the widening the 353<-322 per_grupo_member fan-in
    counts over, so its identity contract IS the count's correctness. While the
    declared value was appended verbatim, a member captured lower-cased in one
    pull and space-padded in the next persisted as two rows and was enumerated
    twice.
    """
    period = Period.from_year_and_code(2024, "1T")
    canonical = member_observation_key("353", period, _MEMBER_ID)

    for variant in (_MEMBER_ID.lower(), f"  {_MEMBER_ID}  ", f"{_MEMBER_ID.lower()}\t"):
        assert member_observation_key("353", period, variant) == canonical

    # ...and a genuinely different member is a genuinely different row.
    assert member_observation_key("353", period, _OTHER_MEMBER_ID) != canonical

    # The single-filer key is untouched by the widening.
    assert member_observation_key("353", period, None) == observation_key("353", period)


def test_calculation_observation_pre_correction_grammar_rejected_the_member_key() -> None:
    """The retired ``{modelo}:{filing_year}:{period}`` grammar dropped the member row."""
    drifted = _declared_shapes("{modelo}:{filing_year}:{period}")
    period = Period.from_year_and_code(2024, "1T")

    assert not _matches_any(member_observation_key("353", period, _MEMBER_ID), drifted)
    # The single-filer key was always covered; only the member variant drifted.
    assert _matches_any(observation_key("100", period), drifted)


def test_singleton_namespaces_admit_only_their_declared_key() -> None:
    """A grammar with no placeholder names one literal key, and only that key.

    Before the grammar was enforced, a singleton namespace accepted any key.
    A valid envelope written under a mistyped key round-tripped through raw
    storage while the owning repository -- which addresses the singleton by
    its canonical key -- reported the record absent, silently orphaning the
    row from the catalogue it belonged to.
    """
    singletons = [
        definition
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if definition.singleton_object_key is not None
    ]
    assert singletons, "registry declares at least one singleton namespace"

    for definition in singletons:
        declared = definition.singleton_object_key
        assert declared is not None
        # The declared key is admitted...
        definition.validate_object_key(declared)
        # ...and every other spelling of it is refused.
        for rejected in (f"{declared}-other", f"{declared}:other", "wrong", "../escape"):
            with pytest.raises(NamespaceRegistryError):
                definition.validate_object_key(rejected)


def test_templated_namespaces_admit_their_real_keys_and_refuse_traversal() -> None:
    """A multi-key namespace keeps accepting the keys its own repositories derive.

    Positive control for the enforcement above: the singleton rule must not
    leak into templated namespaces, whose keys carry segment separators and
    (for path-rooted grammars) path separators by declaration. Only a ``..``
    traversal segment is refused.
    """
    period = Period.from_year_and_code(2024, "1T")
    observations = CALCULATION_OBSERVATIONS_NAMESPACE
    assert observations.singleton_object_key is None

    observations.validate_object_key(observation_key("100", period))
    observations.validate_object_key(member_observation_key("353", period, _MEMBER_ID))

    transactions = TRANSACTION_CATALOGUE_NAMESPACE
    assert transactions.singleton_object_key is None
    transactions.validate_object_key(transaction_object_key("bucket", "txn"))
    transactions.validate_object_key(transaction_index_object_key("bucket"))

    for traversal in ("..", "a:..:b", "a/../b"):
        with pytest.raises(NamespaceRegistryError):
            transactions.validate_object_key(traversal)


def test_singleton_default_object_key_agrees_with_its_grammar() -> None:
    """A singleton's repository-facing default key is the key its grammar admits.

    If the two disagreed, every write through the repository's own default
    would be refused by the namespace's own contract.
    """
    for definition in STORAGE_NAMESPACE_REGISTRY.namespaces:
        declared = definition.singleton_object_key
        if declared is None or definition.default_object_key is None:
            continue
        assert definition.default_object_key == declared
        definition.validate_object_key(definition.default_object_key)
