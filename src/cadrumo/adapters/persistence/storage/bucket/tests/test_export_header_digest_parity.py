"""The sealed-archive header's manifest digest is the canonical digest shape.

``ExportArchiveHeader.manifest_digest`` restated the lowercase-hex-64 rule in a
local validator alongside private length and alphabet constants. The restated
rule agreed with :data:`~core.identity.ContentDigest` on every malformed value
-- uppercase, non-hex, short -- which is exactly what made the divergence hard
to notice: it appeared only on a *valid* digest that arrived with surrounding
whitespace, which the canonical alias strips and the local rule refused.

The header is consumed by archive export, import, and inspect, and sits beside
``bucket_id``, already typed through the same identity module. These tests
therefore assert parity against the canonical alias's own verdict rather than
restating the rule a third time: agreement on the malformed set, agreement on
the normalized valid case, and a real header round-trip so the constraint
cannot be tightened past what the archive writer produces.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from ......core.hashing import sha256_hex
from ......core.identity import ContentDigest
from ......core.product_identity import PRODUCT_IDENTITY
from ..export_archive_header import ARCHIVE_SCHEMA_VERSION, ExportArchiveHeader

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_CREATED_AT = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_VALID_DIGEST = sha256_hex(b"archive-manifest-bytes")

_MALFORMED = (
    pytest.param("", id="empty"),
    pytest.param("a" * 63, id="too-short"),
    pytest.param("a" * 65, id="too-long"),
    pytest.param("A" * 64, id="uppercase"),
    pytest.param("z" * 64, id="non-hex"),
    pytest.param("g" * 64, id="non-hex-adjacent"),
)
#: Valid digests carrying transport whitespace: the canonical alias strips
#: these, and the retired local validator refused them.
_PADDED = (
    pytest.param(f"  {_VALID_DIGEST}  ", id="spaces"),
    pytest.param(f"\t{_VALID_DIGEST}", id="leading-tab"),
    pytest.param(f"{_VALID_DIGEST}\n", id="trailing-newline"),
)

_digest_adapter: TypeAdapter[str] = TypeAdapter(ContentDigest)


def _canonical_verdict(value: str) -> str | None:
    """Return the alias's normalized value, or ``None`` when it refuses."""
    try:
        return _digest_adapter.validate_python(value)
    except ValidationError:
        return None


def _header(digest: str) -> ExportArchiveHeader:
    return ExportArchiveHeader(
        product=PRODUCT_IDENTITY.python_package,
        bucket_id=_BUCKET_ID,
        manifest_digest=digest,
        archive_schema_version=ARCHIVE_SCHEMA_VERSION,
        created_at=_CREATED_AT,
    )


@pytest.mark.parametrize("value", _MALFORMED)
def test_header_and_canonical_alias_agree_on_refusal(value: str) -> None:
    """Both refuse the same malformed digests.

    This half always held; it is asserted so a future change that loosened the
    header could not pass by breaking only the normalization half below.
    """
    assert _canonical_verdict(value) is None
    with pytest.raises(ValidationError):
        _header(value)


@pytest.mark.parametrize("value", _PADDED)
def test_header_normalizes_a_padded_digest_like_the_canonical_alias(value: str) -> None:
    """The divergent half: a padded valid digest normalizes rather than failing.

    The discriminating case for this finding. Restoring a hand-written
    lowercase-hex-64 validator would leave the refusal tests above green and
    only this one red.
    """
    assert _canonical_verdict(value) == _VALID_DIGEST

    assert _header(value).manifest_digest == _VALID_DIGEST


def test_a_real_manifest_digest_round_trips_through_the_header() -> None:
    """Positive control from the production digest helper.

    Guards against over-tightening: the digest here is produced by the same
    function the archive writer uses, so a constraint stricter than its output
    fails here rather than at export time.
    """
    header = _header(_VALID_DIGEST)

    assert header.manifest_digest == _VALID_DIGEST
    assert ExportArchiveHeader.model_validate_json(header.model_dump_json()) == header
