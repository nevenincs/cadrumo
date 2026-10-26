"""The original bounded worker preparation budget shared by admission transports."""

from cadrumo.adapters.persistence.storage.custody.kdf_supervision import PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS

WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS = 30.0

#: A human proof runs the worker's supervised password unwrap and then its first
#: graph preparation inside one exchange. A shorter wait fences a worker whose
#: correct proof is still inside the KDF's own bound on a loaded host.
WORKER_HUMAN_PROOF_TIMEOUT_SECONDS = (
    PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS + WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS
)
