"""Constants shared by the inward filing tests.

Encrypted-storage fixtures belong to the profile persistence adapter test
package. The filing tests that remain here are application-owned and compose
their own inward fakes or explicit test data.
"""

from __future__ import annotations

# Kept for the directly coupled filing tests that use this deterministic test
# identity while composing their own outer runtime.
_BUCKET_ID = "66666666-6666-4666-8666-666666666666"
