"""Generate synthetic desktop parser inputs with canonical provider-status models.

No runtime, profile, credential store or provider process is opened.
"""

import argparse
import json
from pathlib import Path

from dev.packaging.native.build_directory import require_enrolled_build
from dev.packaging.native.build_paths import build_paths

from cadrumo_agent_service.providers.application.contracts import (
    CliState,
    ProviderCredentialSource,
    ProviderReadiness,
    ProviderSettingsMode,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    ProviderStatusEntry,
    ProviderStatusReason,
)
from cadrumo_agent_service.providers.domain.catalog import ProviderAuthKind, ProviderConsumer, ProviderTransport


def document() -> dict[str, object]:
    """Exercise the real strict models and JSON serializer, using synthetic lanes."""

    def entry(provider: str, *, keyless: bool = False, cli: bool = False) -> ProviderStatusEntry:
        transport = ProviderTransport.CLI if cli else ProviderTransport.API
        return ProviderStatusEntry(
            id=f"{provider}_{transport.value}",
            provider=provider,
            display_name=provider.title(),
            transport=transport,
            auth_kind=(
                ProviderAuthKind.NONE
                if keyless
                else ProviderAuthKind.PROVIDER_SIGN_IN_ONLY
                if cli
                else ProviderAuthKind.API_KEY
            ),
            consumers=(ProviderConsumer.ASSISTANT,),
            mode=ProviderSettingsMode.UNSET,
            credential_saved=False,
            available=keyless,
            source=ProviderCredentialSource.NONE,
            readiness=(
                ProviderReadiness.NOT_VERIFIED
                if keyless
                else ProviderReadiness.SIGN_IN_REQUIRED
                if cli
                else ProviderReadiness.MISSING
            ),
            reason=(
                None
                if keyless
                else ProviderStatusReason.SIGN_IN_WITH_PROVIDER_TOOL
                if cli
                else ProviderStatusReason.NOT_CONFIGURED
            ),
            base_url=None,
            default_base_url="http://127.0.0.1:41000" if keyless else None,
            cli_state=CliState.INSTALLED_SIGNED_OUT if cli else None,
            revision="0" * 64,
        )

    status = ProviderSettingsStatus(providers=(entry("local", keyless=True), entry("alpha"), entry("beta", cli=True)))
    refusal = ProviderSettingsRefusal(code=ProviderSettingsRefusalCode.PROFILE_LOCKED)
    return {"status": status.model_dump(mode="json"), "refusal": refusal.model_dump(mode="json")}


def destination(build_directory: Path, output: Path) -> Path:
    """Require the exact declared testing member and refuse links before writing."""
    build = require_enrolled_build(build_directory)
    expected = build_paths(build)["desktop_testing"] / "provider-status-contract.json"
    if ".." in output.parts or not output.is_absolute() or output != expected:
        raise ValueError("Fixture output must be the enrolled desktop testing member")
    member = build
    for part in expected.relative_to(build).parts:
        member /= part
        if member.is_symlink() or member.is_junction():
            raise ValueError("Fixture output must not use symlinks or junctions")
    if expected.resolve() != expected:
        raise ValueError("Fixture output must remain in its physical build directory")
    return expected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = destination(args.build_dir, args.output)
    rendered = json.dumps(document(), sort_keys=True, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after directory creation before opening the output member.
    target = destination(args.build_dir, args.output)
    target.write_text(rendered, encoding="utf-8", newline="\n")
