"""Shared test constants for the aeat.adapters.outbound.aeat.auth package.

Contains module-level constants used across test_certificate.py and
test_authenticator.py to prevent divergence between the two test suites.

Module name intentionally does NOT start with ``_test_`` so the
:mod:`aeat.tests.test_marker_integrity` glob (``**/_test_*.py``) does
not pick it up as a test module — this file holds shared constants,
not tests, and carries no ``pytestmark``.
"""

from __future__ import annotations

# Canonical PKCS#12 passphrase for real self-signed bundle generation in tests.
SECRET_PASSPHRASE = "correct-horse-battery-staple"
