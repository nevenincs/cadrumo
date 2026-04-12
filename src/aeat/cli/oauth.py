"""``aeat oauth-client`` sub-app — guided OAuth Desktop client provisioning.

There is no public Google API or gcloud command that creates an OAuth
2.0 client ID for a project; the developer has to click through the
Cloud Console UI. This sub-app does the next-best thing: prints a deep
link to the credentials page, lists the exact fields and scopes the
project needs, accepts the path to the JSON the developer downloads,
copies it to ``env/oauth-client.json`` (gitignored) so gcloud has a
stable file path to consume via ``--client-id-file``, and writes
``GOOGLE_OAUTH_CLIENT_ID`` and ``GOOGLE_OAUTH_CLIENT_SECRET`` into
``env/.env`` from the parsed JSON.

This is **on the critical path** for vanilla-workstation bootstrap.
``gcloud auth application-default login --scopes=...`` against
gcloud's built-in OAuth client is rejected by Google's "This app is
blocked" screen for any scope outside gcloud's whitelist
(cloud-platform, userinfo.email, openid, sqlservice.login). Drive,
Sheets, and Docs are not in that whitelist. The only way to acquire
ADC with the Workspace scopes the bootstrap needs is to pass
``--client-id-file=<your-own-client.json>`` to ``application-default
login``, which is exactly what ``just gcloud-auth`` does after this
helper has been run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

app = typer.Typer(name="oauth-client", no_args_is_help=True, help="OAuth 2.0 Desktop client provisioning.")


CREDENTIALS_PAGE_TEMPLATE = "https://console.cloud.google.com/apis/credentials?project={project}"

REQUIRED_BLOCK = """\
Required fields when creating the OAuth client in Cloud Console:

  Application type:    Desktop app
  Name:                aeat-cli (or any name you prefer)
  Authorized URIs:     not applicable for desktop clients
  Redirect URI:        http://localhost:8080
  Scopes (granted on first consent):
    - https://www.googleapis.com/auth/drive
    - https://www.googleapis.com/auth/spreadsheets
    - https://www.googleapis.com/auth/documents
    - https://www.googleapis.com/auth/cloud-platform
    - openid
    - https://www.googleapis.com/auth/userinfo.email
"""


def parse_oauth_client_json(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract the client_id and client_secret from a downloaded OAuth JSON.

    Cloud Console writes desktop OAuth credentials under either an
    ``installed`` or ``web`` top-level key depending on the client type.
    Only ``installed`` is the documented Desktop shape, but we accept
    both for resilience.

    Args:
        payload: Parsed JSON dict from the downloaded credentials file.

    Returns:
        Tuple of ``(client_id, client_secret)``.

    Raises:
        ValueError: If the payload does not match either expected shape.
    """
    for key in ("installed", "web"):
        block = payload.get(key)
        if isinstance(block, dict):
            client_id = block.get("client_id")
            client_secret = block.get("client_secret")
            if isinstance(client_id, str) and isinstance(client_secret, str):
                return (client_id, client_secret)
    msg = "OAuth client JSON does not contain installed/web client_id and client_secret"
    raise ValueError(msg)


@app.command(name="init", help="Print the Console deep link, parse the downloaded JSON, write env/.env.")
def init(
    json_path: Path | None = typer.Option(
        None,
        "--json",
        "-j",
        help="Path to the downloaded OAuth client JSON. If omitted, only the instructions are printed.",
    ),
) -> None:
    """Walk the developer through OAuth Desktop client setup."""
    from aeat.config import PROJECT_ROOT, Settings
    from aeat.env_io import write_env_vars

    settings = Settings()
    project = settings.google_cloud_project or "<your-project-id>"
    console = Console()
    console.print(f"[bold]Open this URL in a browser:[/]\n  {CREDENTIALS_PAGE_TEMPLATE.format(project=project)}")
    console.print()
    console.print(REQUIRED_BLOCK)

    if json_path is None:
        console.print(
            "[yellow]Run `aeat oauth-client init --json <path>` after downloading the JSON to write env/.env.[/]"
        )
        return

    if not json_path.exists():
        console.print(f"[red]json file does not exist: {json_path}[/]")
        raise typer.Exit(code=1)

    raw = json_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        console.print(f"[red]could not parse json: {exc}[/]")
        raise typer.Exit(code=1) from exc

    try:
        client_id, client_secret = parse_oauth_client_json(payload)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    # Persist a stable copy of the OAuth client JSON inside env/ so
    # gcloud can consume it via --client-id-file. The env/ directory
    # is gitignored except for .env.example, so this file never lands
    # in version control.
    stable_client_path = PROJECT_ROOT / "env" / "oauth-client.json"
    stable_client_path.parent.mkdir(parents=True, exist_ok=True)
    stable_client_path.write_text(raw, encoding="utf-8")

    write_env_vars(
        PROJECT_ROOT / "env" / ".env",
        {
            "GOOGLE_OAUTH_CLIENT_ID": client_id,
            "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
            "GOOGLE_OAUTH_CLIENT_JSON": str(stable_client_path),
        },
    )
    console.print(f"[green]copied OAuth client JSON to {stable_client_path}[/]")
    console.print("[green]wrote GOOGLE_OAUTH_CLIENT_ID, _SECRET, _JSON to env/.env[/]")
    console.print("[bold]Next step:[/] run `just gcloud-auth`")


__all__ = ["app", "parse_oauth_client_json"]
