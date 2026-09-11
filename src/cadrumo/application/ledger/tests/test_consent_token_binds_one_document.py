"""An off-host acknowledgement covers the document it was taken for, and no other.

``EvidenceConsentToken`` carries a content address for a stated reason: it binds
the acknowledgement "to one document rather than to the session". Nothing
enforced that binding. The client's dispatch point cannot -- the request it
inspects carries the prompt and the images, not the address of the evidence they
were built from -- so all it could ask was whether SOME token was present.

The pairing held anyway, because the one production caller minted its token from
the same ``evidence_id`` it then read. That is a property of that caller, not of
the function, and the function is the door a second frontend comes through: the
token travels as a parameter beside ``evidence_id`` rather than being derived
from it, so the two can be paired wrongly with nothing objecting.

A wrong pairing sends THIS document off-host under an acknowledgement taken for
ANOTHER, then records the other document's address in the consent ledger -- so
the audit trail names a document that was never transmitted, which is the one
question that ledger exists to answer.

These run the real path: two documents stored through the real encrypted write,
and the real resolver reading them back. The addresses are the ones the bytes
were actually read under, not values written here.

Both specimens are committed Facturae XML rather than text PDFs, and that is
what makes the positive control honest rather than merely green. A structured
record is read exactly and reaches no model at all, so an accepted token
proves the binding passed and nothing else; a PDF would route to the reading
model, and the control would then fail wherever no local model is running --
reporting an environment as though it were a rejected token.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.outbound.llm.consent import EvidenceConsentToken
from ....adapters.outbound.llm.errors import LLMConsentError
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.config import Settings
from ..invoice_draft_extraction import extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_SURFACE = "cli:ledger.evidence.extract"
_CORPUS = Path(__file__).parent / "_evidence_corpus"
_FIRST = _CORPUS / "facturae_32_recargo_invoice.xml"
_SECOND = _CORPUS / "facturae_32_series_and_parties_invoice.xml"


def _stored(
    specimen: Path,
    name: str,
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> tuple[str, str]:
    """Store one committed specimen and return its evidence id and content address.

    The address comes off the stored record rather than being hashed here, so
    the test compares what the resolver will actually read the bytes under.
    """
    source = tmp_path / name
    source.write_bytes(specimen.read_bytes())
    service = _make_svc(isolated_settings, secure_objects)
    record = service.add(bucket_id=_BUCKET_ID, source_path=source).record
    return record.evidence_id, record.source_sha256


@pytest.mark.usefixtures("runtime_profile", "seeded_filer_profile")
class TestConsentTokenBinding:
    """The binding, exercised through the real stored-evidence read."""

    def test_a_token_minted_for_another_document_is_refused(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The defect: this document, sent under that document's acknowledgement."""
        _, first_address = _stored(
            _FIRST,
            "first.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )
        second_id, second_address = _stored(
            _SECOND,
            "second.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )
        assert first_address != second_address, "the two documents must differ for this to test anything"

        with pytest.raises(LLMConsentError):
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=second_id,
                settings=isolated_settings,
                consent_token=EvidenceConsentToken(
                    surface=_SURFACE,
                    evidence_content_address=first_address,
                ),
            )

    def test_a_token_minted_for_this_document_is_accepted(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The positive control, and the whole reason this is a binding and not a ban.

        A check that refused every token would satisfy the test above while
        making an acknowledged off-host read impossible. This one differs from
        it in exactly one fact -- which document the token names -- so the
        refusal cannot be misread as covering the matching case too.
        """
        evidence_id, address = _stored(
            _FIRST,
            "matching.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )

        draft = extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            evidence_id=evidence_id,
            settings=isolated_settings,
            consent_token=EvidenceConsentToken(surface=_SURFACE, evidence_content_address=address),
        )

        assert draft is not None

    def test_an_on_host_read_needs_no_token_at_all(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """``None`` is not a mismatch, and the ordinary read must not start needing one.

        Every on-host read passes no token. Treating absence as a failed
        binding would refuse the common case; that decision belongs at the
        dispatch point, which refuses an off-host send without one.
        """
        evidence_id, _ = _stored(
            _FIRST,
            "on-host.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )

        draft = extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            evidence_id=evidence_id,
            settings=isolated_settings,
        )

        assert draft is not None

    def test_the_refusal_names_the_address_the_bytes_were_read_under(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A mismatch the operator cannot locate is not a diagnosis.

        The refusal carries the address of the document actually read, which
        is what lets a reader tell a stale token from a misrouted one without
        reading this module.
        """
        _, first_address = _stored(
            _FIRST,
            "one.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )
        second_id, second_address = _stored(
            _SECOND,
            "two.xml",
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
        )

        with pytest.raises(LLMConsentError) as raised:
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=second_id,
                settings=isolated_settings,
                consent_token=EvidenceConsentToken(
                    surface=_SURFACE,
                    evidence_content_address=first_address,
                ),
            )

        context = raised.value.context
        assert context is not None
        assert context["evidence_content_address"] == second_address
        assert context["consent_token_binding_valid"] is False
