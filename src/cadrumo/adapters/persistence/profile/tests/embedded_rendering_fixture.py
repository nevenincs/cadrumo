"""Install the frozen calculation catalogue written before renderings were stored by reference.

The fixture holds the decrypted rows the earlier writer stored: two 303 work
units and four revisions, three of them embedding a whole rendering (two
sharing one) and one without a rendering. Its bucket, dates and amounts are
synthetic.
"""

from __future__ import annotations

import json
import lzma
from datetime import datetime
from pathlib import Path

from ...storage.secure_object_namespaces import (
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
    MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
    SecureObjectNamespaceDefinition,
)
from ...storage.tests.secure_sql import TestRuntimeProfile

EMBEDDED_RENDERING_FIXTURE = (
    Path(__file__).parent / "fixtures" / "calculation_catalogue_303_embedded_renderings.json.xz"
)
EMBEDDED_RENDERING_FIXTURE_BUCKET_ID = "5e0b8d1c-3a2f-4c6e-9b7d-1f2e3a4b5c6d"


def _install_row(profile: TestRuntimeProfile, definition: SecureObjectNamespaceDefinition, row: object) -> None:
    assert isinstance(row, dict)
    payload = str(row["payload"])
    schema_version = row["schema_version"]
    assert isinstance(schema_version, int)
    profile.repository.save(
        namespace=definition.namespace,
        object_key=definition.require_default_object_key(),
        classification=definition.sensitivity,
        schema_version=schema_version,
        written_at=datetime.fromisoformat(json.loads(payload)["written_at"]),
        payload=payload.encode(),
    )


def install_embedded_rendering_fixture(profile: TestRuntimeProfile, *, with_calculations: bool = True) -> None:
    """Write the fixture's rows into ``profile`` exactly as the earlier writer stored them."""
    rows = json.loads(lzma.decompress(EMBEDDED_RENDERING_FIXTURE.read_bytes()))
    _install_row(profile, MODELO_WORK_UNIT_CATALOGUE_NAMESPACE, rows["work_unit_catalogue"])
    if with_calculations:
        _install_row(profile, MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE, rows["calculation_revision_catalogue"])
