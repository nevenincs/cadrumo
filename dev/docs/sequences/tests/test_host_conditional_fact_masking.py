"""Only volatile free-capacity diagnostic facts are golden-masked.

``PLATFORM_CONDITIONAL_PREFLIGHT_CHECKS`` documents why a live host reading may
never be pinned into a golden: free system memory and free VRAM drift between two runs on
the SAME machine as ordinary system load shifts, so a golden carrying it reds
its own author's next run. Masking the rendered ``detail`` sentence alone left
that number pinned under ``facts``, which is the same defect one layer down.

These tests pin the narrowness as much as the masking: total RAM, VRAM, and
unrelated byte facts remain exact, registry-health tampering remains visible,
and a row that stops reporting free RAM still reds.
"""

from __future__ import annotations

import pytest

from cadrumo.tests.golden_comparison import MASK_SENTINEL

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


def test_only_free_capacity_is_masked_on_the_hardware_row() -> None:
    """The exact volatile coordinate masks while sibling byte facts remain evidence."""
    masked = mask_host_conditional_details(_hardware_row(58644553728, 11057692672))

    assert isinstance(masked, dict)
    facts = masked["facts"]
    assert isinstance(facts, dict)
    assert facts["free_memory_bytes"] == MASK_SENTINEL
    assert facts["free_vram_bytes"] == MASK_SENTINEL
    assert facts["total_memory_bytes"] == 137346269184


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


def test_two_runs_differing_only_in_free_capacity_compare_equal() -> None:
    """The defect this closes: the same box, moments apart, must not diverge."""
    first = mask_host_conditional_details(_hardware_row(58644553728, 11057692672))
    second = mask_host_conditional_details(_hardware_row(41203847104, 9884073984))

    assert first == second


def test_a_row_that_drops_free_system_memory_still_diverges() -> None:
    """Keys stay under comparison, so masking cannot hide a vanished fact.

    Without this the suffix rule would be a hole rather than a mask: a reader
    that silently stopped reporting free RAM would compare equal to one that
    still did.
    """
    complete = _hardware_row(58644553728, 11057692672)
    reduced = _hardware_row(58644553728, 11057692672)
    facts = reduced["facts"]
    assert isinstance(facts, dict)
    del facts["free_memory_bytes"]

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


def test_total_memory_remains_tamper_visible() -> None:
    """Changing total RAM must remain a real golden divergence."""
    expected = _hardware_row(58644553728, 11057692672)
    tampered = _hardware_row(58644553728, 11057692672)
    facts = tampered["facts"]
    assert isinstance(facts, dict)
    facts["total_memory_bytes"] = int(facts["total_memory_bytes"]) + 1

    assert mask_host_conditional_details(expected) != mask_host_conditional_details(tampered)


def test_registry_integrity_failure_remains_visible() -> None:
    """The workstation policy cannot hide deterministic registry-health failure."""
    healthy = {"check": "registry:referential-integrity", "ok": True, "detail": "registry valid"}
    failed = {"check": "registry:referential-integrity", "ok": False, "detail": "registry invalid"}

    assert mask_host_conditional_details(healthy) != mask_host_conditional_details(failed)
