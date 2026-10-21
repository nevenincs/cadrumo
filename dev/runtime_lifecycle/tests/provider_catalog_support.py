"""Build the small package-shaped agent used by the provider-catalog integration test."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from cadrumo.adapters.persistence.storage.secure_object_namespaces import EXTENSION_SETTINGS_NAMESPACE
from cadrumo_client.contracts.extension_records import ExtensionRecordCapability


def provider_record_capability() -> ExtensionRecordCapability:
    """Bind the synthetic service descriptor to the actual provider record policy."""
    namespace = EXTENSION_SETTINGS_NAMESPACE
    return ExtensionRecordCapability(
        capability="provider-settings",
        namespace=namespace.namespace,
        schema_version=namespace.schema_version,
        classification=namespace.sensitivity,
        key_pattern=r"[a-z][a-z0-9_]*",
        actions=frozenset({"read", "write", "delete", "generation"}),
    )


def stand_in_agent_image(directory: Path, *, catalog_document: str) -> tuple[Path, Path]:
    """Return an isolated Python image whose agent CLI emits one declared catalog."""
    image = directory / "agent-image"
    record = directory / "agent-record"
    environment = Path(sys.executable).parent
    executable = image / "bin" / "cadrumo-agent.exe"
    site = image / "Lib" / "site-packages"
    command = site / "cadrumo_agent" / "cli"
    executable.parent.mkdir(parents=True)
    command.mkdir(parents=True)
    record.mkdir()
    shutil.copy2(environment / "python.exe", executable)
    shutil.copy2(environment.parent / "pyvenv.cfg", image / "pyvenv.cfg")
    (command.parent / "__init__.py").write_text("", encoding="utf-8")
    (command / "__init__.py").write_text("", encoding="utf-8")
    (site / "stand_in.json").write_text(
        json.dumps({"catalog": catalog_document, "record": str(record)}), encoding="utf-8"
    )
    (command / "main.py").write_text(
        "\n".join(
            (
                "import json, os, sys",
                "from pathlib import Path",
                "config_path = Path(__file__).resolve().parents[2] / 'stand_in.json'",
                "config = json.loads(config_path.read_text(encoding='utf-8'))",
                "if sys.argv[1:] != ['providers', '--declared', '--json']:",
                "    raise SystemExit(2)",
                "Path(config['record'], 'invocation.json').write_text(json.dumps({",
                "    'arguments': sys.argv[1:],",
                "    'provider_secret_names': sorted(name for name in os.environ if name.startswith('CADRUMO_LLM_')),",
                "}), encoding='utf-8')",
                "sys.stdout.write(config['catalog'])",
            )
        ),
        encoding="utf-8",
    )
    return executable, record
