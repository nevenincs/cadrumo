"""Bundled-data size budget gate.

The architecture review (finding ``bundled-data-weight-unbudgeted``) measured
``src/aeat/_data`` growing from ~311 MB to 516 MB in six weeks with no ceiling
and no gate. The data-budget ADR
(`2026-07-02-arch-remediation-data-budget-adr`) converts the next doubling from
a silent surprise into an ADR-governed decision: this gate asserts the ``_data``
tree stays at or under the declared budget and fails with a message naming the
ADR and the two options a breach permits.

Bundling the corpus is an accepted decision (offline-verifiable legal grounding,
the corpus-registry-packaging ADR); growth is legitimate demand. The budget does
not forbid growth — it forces a decision when growth crosses the ceiling. The
budget may only be raised by an accepted ADR; a breach forces either that ADR or
the corpus-split escape hatch declared below.

The gate reads the tree size directly (summed file bytes, deterministic across
filesystems, unlike block-rounded ``du``) so the arithmetic lives in one place.
No mocks or skips.
"""

from __future__ import annotations

import pytest

from ._inventory import SRC_AEAT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_AEAT / "_data"

# Declared budget: 550 MiB — the 516 MiB measured at the 2026-07-02 review plus
# bounded headroom. Raising this constant requires an accepted ADR (see the
# failure message). Kept in mebibytes so the number matches the ``du -sh``
# reading operators see.
_DATA_SIZE_BUDGET_MIB = 550
_DATA_SIZE_BUDGET_BYTES = _DATA_SIZE_BUDGET_MIB * 1024 * 1024

# Deferral-as-data: the corpus-split escape hatch. When a budget breach is
# driven by legitimate corpus growth rather than accidental payload, the second
# option a breach permits is splitting the bundled corpus into a separate data
# distribution (ADR Option B). It is recorded here as a named constant carrying
# its target condition so the option is discoverable in code, not only in prose.
_CORPUS_SPLIT_ESCAPE_HATCH = (
    "Split src/aeat/_data/corpus into a separate optional data distribution "
    "(data-budget ADR Option B) when a budget raise-by-ADR is no longer the "
    "right call — i.e. when operator install-size pain appears, or the corpus "
    "growth is structural (a new modelo family's manuals) rather than incidental."
)


def _data_tree_bytes() -> int:
    """Return the summed size in bytes of every file under ``src/aeat/_data``."""

    return sum(path.stat().st_size for path in _DATA_ROOT.rglob("*") if path.is_file())


def test_data_root_exists() -> None:
    """The bundled data root is present before the budget is measured."""

    assert _DATA_ROOT.is_dir(), f"missing bundled data root: {_DATA_ROOT}"


def test_data_tree_within_declared_budget() -> None:
    """The ``_data`` tree stays at or under the declared 550 MiB budget."""

    actual_bytes = _data_tree_bytes()
    actual_mib = actual_bytes / 1024 / 1024
    assert actual_bytes <= _DATA_SIZE_BUDGET_BYTES, (
        f"src/aeat/_data is {actual_mib:.1f} MiB, over the {_DATA_SIZE_BUDGET_MIB} MiB data budget "
        f"declared by the data-budget ADR (2026-07-02-arch-remediation-data-budget-adr). "
        f"A breach permits exactly two options: (1) raise the budget with an accepted ADR that "
        f"records why the growth is warranted, or (2) take the corpus-split escape hatch — "
        f"{_CORPUS_SPLIT_ESCAPE_HATCH}"
    )
