"""Shared test constants for the aeat.adapters.outbound.aeat.auth package.

Contains module-level constants used across test_certificate.py and
test_authenticator.py to prevent divergence between the two test suites.
"""

from __future__ import annotations

# Canonical PKCS#12 passphrase for real self-signed bundle generation in tests.
SECRET_PASSPHRASE = "correct-horse-battery-staple"
