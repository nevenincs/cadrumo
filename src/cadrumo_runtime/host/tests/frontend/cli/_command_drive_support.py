"""Drive a live command through the real CLI with synthetic arguments and observe it.

The command-graph probes share one way of reaching a command: its operator path
comes from the graph's parent chain, each required parameter gets a synthetic
value derived from its declared type, and a seeded natural-person profile gives
profile-bound commands something to open. ``sys.monitoring`` then watches the
command's own behavior target, so a probe can prove its command actually ran.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.operator import configure_operator_auth
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.tests.certificates import CERTIFICATE_BUNDLE_INPUT, build_pkcs12_bundle
from cadrumo_client.commands.tests.command_drive_support import PROBE_PROFILE_LABEL, PROBE_PROFILE_TAX_ID

from .portable_human_cli_runtime import PortableHumanCliRuntime, portable_human_cli_runtime


@contextmanager
def seeded_probe_runtime(
    tmp_path: Path,
    *,
    extra_facts: tuple[UserProfileFact, ...] = (),
    certificate_path: Path | None = None,
    client_native_store: AutomationSecretStore | None = None,
) -> Generator[PortableHumanCliRuntime]:
    """Register real password custody and own admitted, observable CLI execution.

    Registration's governed-fact lease ends before the joined runtime captures
    its context. No fixture-level governed-fact scope is lent to a handler.
    """
    with portable_password_custody(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = register_cli_profile(
            label=PROBE_PROFILE_LABEL,
            facts={
                "identity.name": "Ana",
                "identity.surnames": "Perez",
                "identity.tax_id": PROBE_PROFILE_TAX_ID,
                "taxpayer_type.entity_type": "natural_person",
                "provenance.source": "manual_cli",
                **{fact.path: str(fact.value) for fact in extra_facts},
            },
            log_in=False,
        )
        if certificate_path is not None:
            with bundled_indexed_authority().operation() as operation, validating_governed_facts(operation):
                configure_operator_auth(
                    "certificate",
                    certificate_path=certificate_path,
                    operator_scope_ports=build_operator_scope_ports(),
                    operation=operation,
                )
        with portable_human_cli_runtime(
            storage_root=root,
            profile_id=UUID(profile_id),
            label=PROBE_PROFILE_LABEL,
            client_native_store=client_native_store,
        ) as runtime:
            yield runtime


@contextmanager
def synthetic_aeat_credentials(workdir: Path) -> Generator[Path]:
    """Configure a real, self-signed certificate naming the seeded profile's taxpayer.

    A session-gated AEAT flow refuses at credential loading when nothing is
    configured, before it ever builds a Sede session. With this certificate the
    flow loads its credentials and reaches the Sede client, where a sealed run
    stops at the browser launch. The bundle is synthetic and never leaves the
    test's directory.
    """
    now = datetime.now(UTC)
    bundle = build_pkcs12_bundle(
        workdir,
        not_valid_before=now - timedelta(days=1),
        not_valid_after=now + timedelta(days=365),
        name="probe-certificate",
        subject_cn=f"PROBE HOLDER - {PROBE_PROFILE_TAX_ID}",
    )
    with override_settings(
        cadrumo_certificate_path=bundle,
        cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_BUNDLE_INPUT),
    ):
        yield bundle
