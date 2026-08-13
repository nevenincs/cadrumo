"""Host-conditional rows mask their measured byte quantities, not just their prose.

``PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS`` documents why a live host reading may
never be pinned into a golden: ``free_memory_bytes`` and ``free_vram_bytes``
drift between two runs on the SAME machine as ordinary system load shifts, so a
golden carrying them reds its own author's next run. Masking the rendered
``detail`` sentence alone left those numbers pinned under ``facts``, which is the
same defect one layer down.

These tests pin the narrowness as much as the masking: the suffix rule applies
only to rows the host-conditional predicate already recognises, and it drops
values while keeping keys, so a row that stops reporting a quantity still reds.
"""

from __future__ import annotations

import pytest

from cadrumo.core.observability import MASK_SENTINEL

from .._golden_store import mask_host_conditional_details

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _hardware_row(free_memory: int, free_vram: int) -> dict[str, object]:
    """Return a ``local-inference-hardware`` dependency row shaped like the live envelope."""
    return {
        "service": "local-inference-hardware",
        "available": True,
        "precondition_action": None,
        "detail": f"free system memory {free_memory} bytes",
        "facts": {
            "accelerator_kind": "nvidia_cuda",
            "free_memory_bytes": free_memory,
            "free_memory_measured": True,
            "free_vram_bytes": free_vram,
            "total_memory_bytes": 137346269184,
        },
    }


def test_a_host_conditional_row_masks_every_byte_quantity() -> None:
    """Every ``*_bytes`` fact on a recognised host row reduces to the sentinel."""
    masked = mask_host_conditional_details(_hardware_row(58644553728, 11057692672))

    assert isinstance(masked, dict)
    facts = masked["facts"]
    assert isinstance(facts, dict)
    assert facts["free_memory_bytes"] == MASK_SENTINEL
    assert facts["free_vram_bytes"] == MASK_SENTINEL
    assert facts["total_memory_bytes"] == MASK_SENTINEL


def test_non_byte_facts_on_a_host_conditional_row_stay_asserted() -> None:
    """The suffix rule is narrow: non-quantity facts remain under exact comparison.

    ``accelerator_kind`` distinguishes a CUDA host from a CPU-only one, and the
    measured-flag booleans record whether a reader was installed at all. Masking
    those would drop real signal the row exists to carry.
    """
    masked = mask_host_conditional_details(_hardware_row(1, 2))

    assert isinstance(masked, dict)
    facts = masked["facts"]
    assert isinstance(facts, dict)
    assert facts["accelerator_kind"] == "nvidia_cuda"
    assert facts["free_memory_measured"] is True


def test_two_runs_differing_only_in_measured_bytes_compare_equal() -> None:
    """The defect this closes: the same box, moments apart, must not diverge."""
    first = mask_host_conditional_details(_hardware_row(58644553728, 11057692672))
    second = mask_host_conditional_details(_hardware_row(41203847104, 9884073984))

    assert first == second


def test_a_row_that_drops_a_quantity_still_diverges() -> None:
    """Keys stay under comparison, so masking cannot hide a vanished fact.

    Without this the suffix rule would be a hole rather than a mask: a reader
    that silently stopped reporting free VRAM would compare equal to one that
    still did.
    """
    complete = _hardware_row(58644553728, 11057692672)
    reduced = _hardware_row(58644553728, 11057692672)
    facts = reduced["facts"]
    assert isinstance(facts, dict)
    del facts["free_vram_bytes"]

    assert mask_host_conditional_details(complete) != mask_host_conditional_details(reduced)


def test_a_row_outside_the_host_conditional_set_keeps_its_byte_facts() -> None:
    """A ``*_bytes`` fact on an ordinary product row is real output, never masked.

    The predicate, not the suffix, decides which rows are host-conditional. A
    storage-occupancy row reporting bytes is asserting product behaviour, and
    masking it would silently retire a genuine assertion.
    """
    row = {
        "check": "storage:occupancy",
        "detail": "bucket occupies 4096 bytes",
        "facts": {"occupied_bytes": 4096},
    }

    masked = mask_host_conditional_details(row)

    assert isinstance(masked, dict)
    facts = masked["facts"]
    assert isinstance(facts, dict)
    assert facts["occupied_bytes"] == 4096
    assert masked["detail"] == "bucket occupies 4096 bytes"
