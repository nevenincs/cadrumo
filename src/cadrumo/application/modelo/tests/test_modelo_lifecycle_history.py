"""Tests for the per-modelo lifecycle history assembler.

The sibling of ``test_history.py``, which covers the per-work-unit grain. The
two assemblers share a module, a substrate and an ordering, but they answer
different questions and neither narrows to the other, so their coverage is kept
apart rather than parameterised together.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ....domain.buckets.event import BucketEventType
from ....domain.modelos.errors import ModeloValidationError
from ..history import admitted_modelo_history_event_types, assemble_modelo_lifecycle_history
from ..work_lifecycle import create_work_unit, discard_work_unit
from ._file_flow_support import _FILE_FLOW_PROFILE_ID, _Repos

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def _create(repos: _Repos, *, period: str = "1T", filing_year: int = 2026):
    """Create one modelo 130 work unit through the real lifecycle service."""
    wu_repo, _, _, _, bv_repo = repos
    return create_work_unit(
        bucket_id=_FILE_FLOW_PROFILE_ID,
        modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T0,
    )


class TestAdmission:
    """The admitted set is derived from the taxonomy, never recorded as a literal."""

    def test_every_modelo_named_event_type_is_admitted(self) -> None:
        """Admission must equal the declared MODELO family, with nothing dropped.

        Asserted as an equality against the live enum rather than a count, so
        that declaring a new ``MODELO_*`` event type cannot leave this history
        silently narrower than the taxonomy it claims to cover.
        """
        assert admitted_modelo_history_event_types() == frozenset(
            event_type for event_type in BucketEventType if event_type.name.startswith("MODELO_")
        )

    def test_the_event_types_the_adapter_literal_dropped_are_admitted(self) -> None:
        """The confirmed drift casualties must be admitted.

        Each carries the ``modelo``, ``filing_year`` and ``period`` payload keys
        this history filters on, and each was absent from the hand-written set
        this policy replaced. ``MODELO_WORK_UNIT_DISCARDED`` was admitted while
        its own creation counterpart was not, so the operator was shown a work
        unit being discarded but never created.
        """
        admitted = admitted_modelo_history_event_types()

        assert BucketEventType.MODELO_WORK_UNIT_CREATED in admitted
        assert BucketEventType.MODELO_WORK_UNIT_DISCARDED in admitted
        assert BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED in admitted

    def test_censo_declarations_are_not_admitted(self) -> None:
        """Keying on the member name rather than the value string is load-bearing.

        ``CENSO_DECLARATION_*`` values begin ``modelo.036.`` while belonging to a
        different declared family, so a value-prefix derivation would widen this
        command into censo territory. That is a product decision, not a
        projection detail.
        """
        admitted = admitted_modelo_history_event_types()
        censo = {
            BucketEventType.CENSO_DECLARATION_ALTA,
            BucketEventType.CENSO_DECLARATION_BAJA,
            BucketEventType.CENSO_DECLARATION_MODIFICACION,
        }

        assert censo.isdisjoint(admitted)
        assert all(event_type.value.startswith("modelo.") for event_type in censo)


class TestAssembly:
    """Subject selection, narrowing, ordering and refusal over the real emitters."""

    def test_the_creation_event_reaches_the_history(self, repos: _Repos) -> None:
        """A work unit created through the real lifecycle service appears in its modelo's history.

        The teeth for the drift this service was extracted to fix: the event is
        emitted by production code, and the literal set it replaced dropped it.
        """
        _, _, _, _, bv_repo = repos
        created = _create(repos)

        history = assemble_modelo_lifecycle_history("130", bucket_event_repository=bv_repo)

        assert history.modelo == "130"
        assert BucketEventType.MODELO_WORK_UNIT_CREATED in [event.event_type for event in history.events]
        assert all(event.payload["modelo"] == "130" for event in history.events)
        assert any(event.object_id == created.work_unit_id for event in history.events)

    def test_a_modelo_with_no_events_returns_an_empty_history(self, repos: _Repos) -> None:
        """Selection is on the event's own subject key, so an unrelated modelo sees nothing."""
        _, _, _, _, bv_repo = repos
        _create(repos)

        assert assemble_modelo_lifecycle_history("303", bucket_event_repository=bv_repo).events == ()

    def test_filing_year_narrows_the_history(self, repos: _Repos) -> None:
        """A filing year the events do not declare yields nothing; the declared one yields rows."""
        _, _, _, _, bv_repo = repos
        _create(repos)

        assert assemble_modelo_lifecycle_history("130", filing_year=2025, bucket_event_repository=bv_repo).events == ()
        assert assemble_modelo_lifecycle_history("130", filing_year=2026, bucket_event_repository=bv_repo).events

    def test_period_narrows_the_history(self, repos: _Repos) -> None:
        """Two periods of the same modelo stay separable."""
        _, _, _, _, bv_repo = repos
        first = _create(repos, period="1T")
        _create(repos, period="2T")

        narrowed = assemble_modelo_lifecycle_history(
            "130",
            period=first.period.registry_token,
            bucket_event_repository=bv_repo,
        )

        assert narrowed.events
        assert {event.payload["period"] for event in narrowed.events} == {first.period.registry_token}

    def test_rows_are_ordered_by_the_shared_total_order(self, repos: _Repos) -> None:
        """Ordering must be the canonical key, not ``occurred_at`` alone.

        Emissions inside one operation share an instant by design, so ordering
        on the timestamp alone leaves ties falling through to catalogue mapping
        order and lets two readers render the operator different timelines with
        nothing invalid anywhere.
        """
        wu_repo, _, _, _, bv_repo = repos
        created = _create(repos)
        discard_work_unit(
            created.work_unit_id,
            actor="test-operator",
            repository=wu_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )

        events = assemble_modelo_lifecycle_history("130", bucket_event_repository=bv_repo).events
        keys = [(event.occurred_at, event.event_id) for event in events]

        assert len(events) >= 2
        assert keys == sorted(keys)

    def test_a_malformed_modelo_is_refused_rather_than_answered_empty(self, repos: _Repos) -> None:
        """An unusable identifier must refuse, not return an empty timeline.

        An empty result means the modelo has no history. That is a different
        fact from an identifier that could never have had one, and collapsing
        the two hides the operator's typo behind a plausible answer.
        """
        _, _, _, _, bv_repo = repos

        with pytest.raises(ModeloValidationError):
            assemble_modelo_lifecycle_history("abc", bucket_event_repository=bv_repo)

    def test_rows_keep_the_fields_a_restated_read_model_dropped(self, repos: _Repos) -> None:
        """The history carries validated domain events, not a lossy copy of them.

        ``bucket_id`` and ``payload_version`` were both absent from the read
        model this projection replaced. ``payload_version`` is the discriminator
        that says which payload shape a persisted row has, which is exactly what
        the filing-year fallback below turns on, so dropping it here would have
        hidden the evidence for the decision it informs.
        """
        _, _, _, _, bv_repo = repos
        _create(repos)

        events = assemble_modelo_lifecycle_history("130", bucket_event_repository=bv_repo).events

        assert events
        assert all(event.bucket_id == _FILE_FLOW_PROFILE_ID for event in events)
        assert all(event.payload_version >= 1 for event in events)


class TestPersistedPayloadFallback:
    """The ``year`` fallback serves persisted payloads no live emitter writes."""

    def test_a_legacy_year_payload_still_matches_the_filing_year(self, repos: _Repos) -> None:
        """An event carrying ``year`` instead of ``filing_year`` must still narrow correctly.

        No current emitter writes ``year`` into a bucket-event payload, but the
        log is append-only and the modelo payload schema has already moved a
        version, so payloads under the older shape may still be on disk.
        Dropping the fallback would lose those rows with no error anywhere.
        """
        from ....domain.buckets.event import BucketEvent, BucketEventObjectType, derive_bucket_event_id
        from ....domain.buckets.event_repository import emit_bucket_events

        _, _, _, _, bv_repo = repos
        fields = {
            "bucket_id": _FILE_FLOW_PROFILE_ID,
            "event_type": BucketEventType.MODELO_EXPORTED,
            "occurred_at": _T0,
            "actor": "legacy-emitter",
            "object_type": BucketEventObjectType.CALCULATION_REVISION,
            "object_id": "d" * 64,
            "payload": {"modelo": "130", "year": "2026", "period": "1T"},
        }
        emit_bucket_events(
            repository=bv_repo,
            events=(
                BucketEvent(
                    event_id=derive_bucket_event_id(**fields),
                    payload_version=1,
                    **fields,
                ),
            ),
        )

        narrowed = assemble_modelo_lifecycle_history("130", filing_year=2026, bucket_event_repository=bv_repo)

        assert [event.actor for event in narrowed.events] == ["legacy-emitter"]
