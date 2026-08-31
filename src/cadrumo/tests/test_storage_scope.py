"""The relocation helper moves what it names, and refuses what it must not move.

The helper exists so an isolation site stops restating the settings field and
the leaf directory the taxonomy already declares. That is only worth anything
if the kwargs it returns genuinely relocate the category, so the round-trip is
measured through :func:`storage_path` -- the resolver production reads --
rather than against the mapping the helper built, which would agree with itself
whatever it contained.

The expected leaf names below are written out deliberately. They are the
independent oracle: deriving them from the taxonomy would make every assertion
here compare the declaration against itself and pass for any subpath at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ..core.storage_taxonomy_locations import STORAGE_TAXONOMY, storage_path
from ..core.storage_taxonomy import StorageCategory, StorageOverridePolicy, StorageScope
from ..core.config import Settings, override_settings
from ..core.errors.hierarchy import CoreValidationError
from .env_scope import isolated_aeat_env, settings_without_env_file
from .storage_scope import relocated_storage_path, storage_env_overrides, storage_overrides

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"secrets", "financial", "runs", "transactions"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def test_the_overrides_relocate_each_category_to_its_declared_subpath(tmp_path: Path) -> None:
    """A relocated category resolves under the anchor, at the declared subpath.

    ``financial/transactions`` is here on purpose: it is the multi-segment case,
    and it is the one an isolation fixture had spelled ``txs`` for as long as
    the name was written by hand.
    """
    anchor = tmp_path / "scratch"

    with override_settings(
        **storage_overrides(anchor, StorageCategory.SECRETS, StorageCategory.FINANCIAL_TRANSACTIONS)
    ) as settings:
        assert storage_path(StorageCategory.SECRETS, settings=settings) == anchor / "secrets"
        assert storage_path(StorageCategory.FINANCIAL_TRANSACTIONS, settings=settings) == (
            anchor / "financial" / "transactions"
        )


def test_relocation_moves_the_category_off_the_storage_root(tmp_path: Path) -> None:
    """Positive control for the test above.

    Without it, a helper that returned the root-derived default unchanged would
    satisfy the subpath assertion whenever the anchor happened to be the root,
    and the relocation would never be exercised.
    """
    root = tmp_path / "storage-root"

    with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=None) as derived:
        derived_secrets = storage_path(StorageCategory.SECRETS, settings=derived)
        with override_settings(**storage_overrides(tmp_path / "elsewhere", StorageCategory.SECRETS)) as relocated:
            relocated_secrets = storage_path(StorageCategory.SECRETS, settings=relocated)

    assert derived_secrets == root / "secrets"
    assert relocated_secrets != derived_secrets
    assert root not in relocated_secrets.parents


def test_every_relocatable_member_is_accepted(tmp_path: Path) -> None:
    """The helper spans the taxonomy rather than a hand-picked subset.

    Enumerated from the declaration so a member added later is covered the
    moment it lands, instead of quietly falling outside what tests can isolate.
    """
    relocatable = tuple(
        location.category
        for location in STORAGE_TAXONOMY.values()
        if location.scope is StorageScope.ROOT
        and location.override_policy is StorageOverridePolicy.OPERATOR_OVERRIDABLE
        and location.settings_field is not None
    )
    assert len(relocatable) > 20, f"only {len(relocatable)} relocatable members; the sweep covers almost nothing"

    overrides = storage_overrides(tmp_path, *relocatable)

    assert len(overrides) == len(relocatable), "two members collapsed onto one settings field"
    for path in overrides.values():
        assert tmp_path in path.parents


def test_it_refuses_a_fixed_layout_member(tmp_path: Path) -> None:
    """Bucket layout is fixed by policy, so a test may not pin it somewhere else."""
    with pytest.raises(CoreValidationError, match="fixed layout"):
        storage_overrides(tmp_path, StorageCategory.BUCKETS)


def test_it_refuses_a_bucket_scoped_member(tmp_path: Path) -> None:
    """A per-bucket member is provisioned by the bucket lifecycle, not by settings."""
    with pytest.raises(CoreValidationError, match="provisioned per bucket"):
        storage_overrides(tmp_path, StorageCategory.BUCKET_MANIFEST)


def test_it_refuses_relocating_nothing(tmp_path: Path) -> None:
    """An empty call is a site that meant to name a category and did not."""
    with pytest.raises(CoreValidationError, match="at least one category"):
        storage_overrides(tmp_path)


def test_the_refusal_probes_would_otherwise_succeed(tmp_path: Path) -> None:
    """Positive control for the three refusals.

    Each refusal above proves a call fails; none of them proves the call would
    have succeeded on a permitted member. A helper that raised unconditionally
    would satisfy all three and isolate nothing.
    """
    assert storage_overrides(tmp_path, StorageCategory.SECRETS) == {"cadrumo_secret_store_dir": tmp_path / "secrets"}


def test_the_single_category_accessor_agrees_with_the_override_it_pairs_with(tmp_path: Path) -> None:
    """The path a test seeds is the path the override sends production to.

    These are used together — seed the directory, then enter the block — so a
    disagreement between them would have a test writing files somewhere the
    system under test never looks, and passing for the wrong reason. Checked
    end to end through :func:`storage_path` under a live override rather than
    against the mapping, which would only prove one function calls the other.
    """
    seeded = relocated_storage_path(tmp_path, StorageCategory.FINANCIAL_TRANSACTIONS)

    with override_settings(**storage_overrides(tmp_path, StorageCategory.FINANCIAL_TRANSACTIONS)) as settings:
        assert storage_path(StorageCategory.FINANCIAL_TRANSACTIONS, settings=settings) == seeded

    assert seeded == tmp_path / "financial" / "transactions"


def test_the_single_category_accessor_refuses_what_the_mapping_refuses(tmp_path: Path) -> None:
    """It inherits the refusals rather than quietly widening them."""
    with pytest.raises(CoreValidationError, match="fixed layout"):
        relocated_storage_path(tmp_path, StorageCategory.BUCKETS)


def test_the_environment_form_names_a_variable_the_settings_model_reads(tmp_path: Path) -> None:
    """The env form emits a live variable name, not an uppercased guess.

    Checked against the model's own environment inventory rather than against
    ``field.upper()``, which is the derivation under test and would agree with
    itself.
    """
    environment = storage_env_overrides(tmp_path, StorageCategory.SECRETS, StorageCategory.RUNS)

    assert set(environment) <= Settings.env_var_names()
    assert environment["CADRUMO_SECRET_STORE_DIR"] == str(tmp_path / "secrets")
    assert environment["CADRUMO_RUNS_DIR"] == str(tmp_path / "runs")


def test_the_environment_form_actually_reaches_the_settings_model(tmp_path: Path) -> None:
    """A variable this emits relocates the category when the model reads it.

    The point of the reachability check is that a name nothing reads would
    leave a subprocess pointed at the operator's real location. Proving the
    name resolves is what makes that check meaningful rather than decorative.
    """
    environment = storage_env_overrides(tmp_path, StorageCategory.SECRETS)

    with isolated_aeat_env(**environment):
        settings = settings_without_env_file()
        assert storage_path(StorageCategory.SECRETS, settings=settings) == tmp_path / "secrets"
