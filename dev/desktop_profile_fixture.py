"""Generate the desktop demo from the real profile schema and overview projection.

Run after publishing a changed profile schema. No stored user profile is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cadrumo.application.user_profile.overview import build_profile_overview
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record


def render_fixture() -> str:
    """Project synthetic answers through the same schema walk as the installed runtime."""
    fixtures = {}
    with bundled_indexed_authority().operation() as operation:
        context = operation.profile_create_context()
        record = create_user_profile_record(
            context=context,
            profile_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            setup_state=ProfileSetupState.INCOMPLETE,
            facts=tuple(
                UserProfileFact(path=path, value=value)
                for path, value in {
                    "identity.name": "Ana",
                    "identity.surnames": "Soler Vidal",
                    "identity.email": "ana.soler@example.test",
                    "contact.fiscal_address": "Calle Larios 12, 2 A, Málaga",
                    "contact.postcode": "29005",
                    "contact.contact_person_phone": "952000000",
                }.items()
            ),
        )
        flow = build_setup_flow(operation)
        for language in ("en", "es", "ca", "hu"):
            with override_settings(cadrumo_output_language=language):
                data = build_profile_overview(record, schema=context.schema, flow=flow).model_dump(mode="json")
                data.pop("label")
                data.update(valid=True, pages=1, content_digest="a" * 64)
                fixtures[language] = data
    return json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    """Write or verify the checked-in, synthetic browser fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "native/desktop/frontend/src/dev/fixtures/userProfile.json"
    rendered = render_fixture()
    if args.check:
        if json.loads(target.read_text(encoding="utf-8")) != json.loads(rendered):
            raise SystemExit("Profile demo is stale; run uv run --no-sync python -m dev.desktop_profile_fixture")
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
