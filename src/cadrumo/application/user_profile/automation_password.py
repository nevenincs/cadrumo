"""Request-bound password proof shared by enrollment and global unlock."""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID

from pydantic import SecretBytes

from ...core.time.utc import UtcInstant
from .access_administration import AccessAdministrationRequest, FreshPasswordAuthorization
from .access_contracts import ACCESS_LEASE_MAXIMUM
from .authentication import ProfilePasswordProofOperation
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import AdministrationFacts
from .custody_ports import (
    load_profile_custody_password_material,
    map_profile_authentication_proof_failure,
    unlock_profile_custody_password,
)


def prove_automation_administration(
    *,
    request: AccessAdministrationRequest,
    facts: AdministrationFacts,
    password: SecretBytes,
    storage_root: Path,
    deadline: UtcInstant,
) -> tuple[FreshPasswordAuthorization, SecretBytes]:
    """Prove exact current custody without creating or elevating a login session.

    The caller reobserves facts and evaluates the returned exact-request proof
    under its lifecycle fence before committing. The DEK is a trusted custody
    operand and must never become an operation result or a client response.
    """
    binding = facts.profile.binding
    if request.profile_id != binding.profile_id:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    material = load_profile_custody_password_material(binding.profile_id, root=storage_root)
    if (
        material.envelope.password_generation != binding.custody_generation
        or UUID(bytes=base64.b64decode(material.envelope.dek_epoch)) != binding.dek_epoch
    ):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    try:
        unlocked = unlock_profile_custody_password(material, password=password.get_secret_value().decode("utf-8"))
    except UnicodeError:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None
    except Exception as error:
        if (
            map_profile_authentication_proof_failure(error, operation=ProfilePasswordProofOperation.AUTOMATION_APPROVAL)
            is None
        ):
            raise
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None
    if unlocked.profile_id != binding.profile_id:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    proof = FreshPasswordAuthorization(
        request=request,
        binding=binding,
        profile_lock_generation=facts.profile.lock_generation,
        runtime_boot_id=facts.context.runtime_boot_id,
        connection_id=facts.context.connection_id,
        client_id=facts.context.authenticated_client_id,
        originating_login_id=facts.originating_login_id,
        verified_at=facts.context.now,
        expires_at=min(deadline, facts.context.now + ACCESS_LEASE_MAXIMUM),
        verified_monotonic=facts.context.monotonic_now,
        consumed=False,
    )
    return proof, SecretBytes(unlocked.dek)
