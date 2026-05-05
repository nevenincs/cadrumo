"""``aeat oauth-client`` Typer sub-app — guided OAuth Desktop client provisioning.

There is no public Google API or ``gcloud`` command that creates an
OAuth 2.0 client ID for a project; the developer has to click through
the Cloud Console. This command prints the exact link, parses the
resulting JSON download, and populates the workstation's ``env/.env``
so bootstrap/operation can proceed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console

from ._i18n import tr

app = typer.Typer(name="oauth-client", no_args_is_help=True, help=tr("cli.oauth.app_help"))

CREDENTIALS_PAGE_TEMPLATE = "https://console.cloud.google.com/apis/credentials/oauthclient?project={project}"
REQUIRED_BLOCK = "\n".join(
    (
        "Application type: Desktop app",
        "Authorized redirect URI: http://localhost",
        "Download the OAuth client JSON after creation.",
    )
)


def parse_oauth_client_json(raw: str | Mapping[str, Any]) -> tuple[str, str]:
    """Extract client_id and client_secret from a Google OAuth JSON string.

    Supports both 'installed' (Desktop) and 'web' (Web Application)
    client types.

    Raises:
        ValueError: When the JSON is malformed or missing the required
            keys.
    """
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(tr("cli.oauth.errors.invalid_json", exc=str(exc))) from exc
    else:
        payload = dict(raw)

    for kind in ("installed", "web"):
        if kind in payload:
            secret_payload = payload[kind]
            if (
                isinstance(secret_payload, Mapping)
                and "client_id" in secret_payload
                and "client_secret" in secret_payload
            ):
                return cast(str, secret_payload["client_id"]), cast(str, secret_payload["client_secret"])

    raise ValueError("OAuth client JSON must contain an installed/web client_id and client_secret")


@app.command(name="init", help=tr("cli.oauth.init.help"))
def init_cmd(
    json_path: Path | None = typer.Option(
        None,
        "--json",
        exists=True,
        dir_okay=False,
        help=tr("cli.oauth.init.json_help"),
    ),
) -> None:
    """Guided Google Cloud Console Desktop OAuth client provisioning."""
    from ...core.config import load_settings

    settings = load_settings()
    console = Console()

    console.print(f"[bold]{tr('cli.oauth.labels.open_url')}[/]")
    url = f"https://console.cloud.google.com/apis/credentials/oauthclient?project={settings.google_cloud_project}"
    console.print(f"  {url}\n")

    if json_path is None:
        console.print(tr("cli.oauth.init.success"))
        return

    # 1. Parse and extract
    raw = json_path.read_text(encoding="utf-8")
    client_id, client_secret = parse_oauth_client_json(raw)

    # 2. Persist to env/.env
    env_file = settings.model_config.get("env_file")
    if isinstance(env_file, Path):
        content = env_file.read_text(encoding="utf-8")
        if "GOOGLE_OAUTH_CLIENT_ID" not in content:
            content += f"\nGOOGLE_OAUTH_CLIENT_ID={client_id}\n"
        else:
            content = re.sub(r"GOOGLE_OAUTH_CLIENT_ID=.*", f"GOOGLE_OAUTH_CLIENT_ID={client_id}", content)

        if "GOOGLE_OAUTH_CLIENT_SECRET" not in content:
            content += f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}\n"
        else:
            content = re.sub(r"GOOGLE_OAUTH_CLIENT_SECRET=.*", f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}", content)

        env_file.write_text(content, encoding="utf-8")
        console.print(f"[green]{tr('cli.oauth.success.written')}[/]")

    # 3. Copy to stable path
    stable_client_path = Path("env/oauth-client.json")
    stable_client_path.write_text(raw, encoding="utf-8")
    console.print(f"[green]{tr('cli.oauth.success.copied', path=str(stable_client_path))}[/]")

    next_step = tr("cli.oauth.labels.next_step")
    console.print(f"[bold]{next_step}[/] {tr('cli.oauth.labels.run_gcloud_auth')}")


__all__ = ["CREDENTIALS_PAGE_TEMPLATE", "REQUIRED_BLOCK", "app", "parse_oauth_client_json"]
