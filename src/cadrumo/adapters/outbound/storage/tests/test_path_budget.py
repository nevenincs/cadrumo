"""Guards for the worst-case object-path suffix budget.

The budget feeds :func:`~core.paths.windows_storage_root_long_path_margin`,
which decides whether a candidate storage root leaves headroom below the
Windows ``MAX_PATH`` ceiling. An understated budget reports headroom that a
real outbound write then consumes, so these guards recompute the shape from
the real grammar constants and prove the derivation covers the whole shipped
namespace domain rather than one sampled value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.paths import WINDOWS_MAX_PATH, windows_storage_root_long_path_margin
from ....persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ....persistence.storage.storage_path_definitions import BUCKET_BLOBS_DIRNAME, BUCKETS_DIRNAME
from .._object_name import HMAC_PREFIX_LENGTH, sanitize_provider_object_label
from ..local import SIDECAR_EXTENSION
from ..path_budget import windows_worst_case_object_path_suffix_length

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: The bucket-event object type the budget previously sampled. Kept here only
#: as the positive control below; it is NOT a registered storage namespace.
_PRIOR_SAMPLED_NAMESPACE = "ledger_transaction"


def _suffix_for(namespace: str) -> str:
    """Recompute the real sidecar path suffix for one namespace value."""
    return (
        "\\"
        + BUCKETS_DIRNAME
        + "\\"
        + ("0" * 36)  # canonical UUIDv4 bucket id
        + "\\"
        + BUCKET_BLOBS_DIRNAME
        + "\\"
        + namespace
        + "\\"
        + ("a" * HMAC_PREFIX_LENGTH)
        + "--"
        + sanitize_provider_object_label("x" * 200)  # clamps to the label cap
        + SIDECAR_EXTENSION
    )


def test_budget_matches_the_real_sidecar_shape_for_the_longest_namespace() -> None:
    """The budget equals the real path shape built with the longest registered namespace."""
    longest = max(
        (definition.namespace for definition in STORAGE_NAMESPACE_REGISTRY.namespaces),
        key=len,
    )
    assert windows_worst_case_object_path_suffix_length() == len(_suffix_for(longest))


def test_budget_covers_every_registered_namespace() -> None:
    """No shipped namespace produces a path longer than the budget.

    This is the property the margin depends on: a namespace the registry ships
    but the budget does not cover is a path the preflight probe would clear and
    a real write would then fail on.
    """
    budget = windows_worst_case_object_path_suffix_length()
    over = {
        definition.namespace: len(_suffix_for(definition.namespace))
        for definition in STORAGE_NAMESPACE_REGISTRY.namespaces
        if len(_suffix_for(definition.namespace)) > budget
    }
    assert not over, f"namespaces exceeding the {budget}-char budget: {over}"


def test_prior_sampled_namespace_understated_the_budget() -> None:
    """Positive control: the previously sampled value really does under-count.

    The budget was a literal built from a bucket-event object type. That
    vocabulary is disjoint from the registered storage namespaces the provider
    is actually handed, so the sample was not merely short -- it was drawn from
    a domain no production path uses. This asserts both halves, so a future
    change that quietly reverts to a short sample reds here.
    """
    registered = {definition.namespace for definition in STORAGE_NAMESPACE_REGISTRY.namespaces}
    assert _PRIOR_SAMPLED_NAMESPACE not in registered, (
        "the previously sampled value is now a registered namespace -- this control "
        "no longer reproduces the defect it exists to pin"
    )
    assert len(_suffix_for(_PRIOR_SAMPLED_NAMESPACE)) < windows_worst_case_object_path_suffix_length()


def test_margin_uses_the_derived_budget(tmp_path: Path) -> None:
    """The margin helper consumes the derived budget end to end."""
    budget = windows_worst_case_object_path_suffix_length()
    margin = windows_storage_root_long_path_margin(tmp_path, object_path_suffix_length=budget)
    assert margin == WINDOWS_MAX_PATH - len(str(tmp_path.resolve())) - budget
