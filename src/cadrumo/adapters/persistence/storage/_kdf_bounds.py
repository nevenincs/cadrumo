"""The one Argon2id parameter window every storage KDF record validates against.

Two records describe the same Argon2id parameter set from different sides: the
canonical enrollment record
(:class:`~.master_key._kdf_params.KdfParams`) and the bucket-manifest wire
record (:class:`~.bucket.ManifestKdfParams`). They were free to disagree, and
did -- the enrollment record pinned the OWASP window while the manifest record
declared only ``ge=1`` lower bounds, so a manifest could carry an 8 KiB,
single-iteration parameter set that enrollment would have refused outright.

The constants live here, in the package both sides already reach for
:mod:`._kdf_salt`, rather than in either record's own module: the manifest
package cannot import the master-key package without closing an import cycle,
which is exactly how the two windows came to be written twice.

Widening the window is a deliberate edit to this module; a *cost bump* raises a
bucket's enrolled parameters within it and stays non-breaking, which is the
property the manifest record was loosened for in the first place.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

#: Argon2 version 1.3, the only version the substrate derives under.
Argon2Version = Literal[19]

#: Derived KEK length in bytes, fixed by AES-256-GCM.
KdfOutputLength = Literal[32]

# The two single-valued axes are declared ONCE, as the types above, and their
# runtime values read back out. Writing the annotation and the constant
# separately would put the same number in two places, in the module whose
# entire purpose is that it is in one.
ARGON2_VERSION: Final = get_args(Argon2Version)[0]
KDF_OUTPUT_BYTES: Final = get_args(KdfOutputLength)[0]

#: OWASP 2024 Password Storage Cheat Sheet baseline, and the floor.
MIN_MEMORY_COST_KIB: Final = 19 * 1024
MAX_MEMORY_COST_KIB: Final = 1024 * 1024
MIN_TIME_COST: Final = 2
MAX_TIME_COST: Final = 16
MIN_PARALLELISM: Final = 1
MAX_PARALLELISM: Final = 8

__all__ = [
    "ARGON2_VERSION",
    "KDF_OUTPUT_BYTES",
    "MAX_MEMORY_COST_KIB",
    "MAX_PARALLELISM",
    "MAX_TIME_COST",
    "MIN_MEMORY_COST_KIB",
    "MIN_PARALLELISM",
    "MIN_TIME_COST",
    "Argon2Version",
    "KdfOutputLength",
]
