"""Checkout fixture anchor obtained from the actual package-mode detector."""

from pathlib import Path

from ..storage_environment import storage_mode


def project_root() -> Path:
    """Return the checkout required by this source-fixture corpus."""
    checkout = storage_mode().checkout
    assert checkout is not None, "source fixture requires a checkout"
    return checkout
