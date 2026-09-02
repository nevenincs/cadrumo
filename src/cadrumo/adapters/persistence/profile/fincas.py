"""ORM-backed repositories for the rental-register record types.

These concrete repositories are the persistence adapter behind the
read-side ports declared in :mod:`domain.fincas.repository_ports`.
They bridge the public :mod:`domain.fincas.models` records and the
internal :mod:`adapters.persistence.storage.sql._orm` mapper rows;
every method routes through ``_flush_or_wrap`` so DB integrity violations
surface as :class:`RepositoryError`.

Living in the persistence adapter (not in :mod:`domain.fincas`) keeps
the SQLAlchemy and ORM-row coupling out of the domain layer: the domain
aggregation functions depend only on the structural ``*`` reader ports,
never on this module. Storage imports remain deferred behind the methods
that consult them so the module stays import-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....core.logging import get_logger
from ....domain.fincas.enums import (
    ExpenseCategory,
    TitularContribuyente,
    TitularidadRegime,
    UseType,
)
from ....domain.fincas.errors import FincaValidationError
from ....domain.fincas.models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)
from ....domain.fincas.titularidad import Titularidad

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from ..storage.sql import orm as _orm

_log = get_logger(__name__)


def _flush_or_wrap(session: Session, kind: str) -> None:
    from ..storage.errors import RepositoryError

    try:
        session.flush()
    except IntegrityError as exc:
        raise RepositoryError(f"integrity violation during {kind} operation: {exc.orig}") from exc


class FincaRepository:
    """Repository for :class:`Finca`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an open ORM ``session``."""
        self.session = session

    def list_all(self) -> list[Finca]:
        """Return every record in the table, ordered by surrogate id.

        Returns:
            List of all :class:`Finca` records.
        """
        from ..storage.sql import orm as _orm

        rows = self.session.execute(select(_orm.FincaRow).order_by(_orm.FincaRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    def get(self, record_id: int) -> Finca:
        """Return the record with surrogate id ``record_id``.

        Args:
            record_id: Surrogate integer primary key.

        Returns:
            The matching :class:`Finca` record.

        Raises:
            RepositoryError: When no row matches.
        """
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.FincaRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_finca id={record_id} not found")
        return self._to_record(row)

    def get_by_identifier(self, identifier: str) -> Finca | None:
        """Return the record matching ``identifier``, or ``None`` if absent.

        Returns:
            The matching :class:`Finca`, or ``None`` when not found.
        """
        from ..storage.sql import orm as _orm

        row = self.session.execute(
            select(_orm.FincaRow).where(_orm.FincaRow.identifier == identifier),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: Finca) -> Finca:
        """Insert or update ``record`` and return the persisted entity.

        Returns:
            The persisted :class:`Finca` with any database-generated fields populated.
        """
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row: _orm.FincaRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.FincaRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_finca id={record.id} not found for update")
        else:
            row = self.session.execute(
                select(_orm.FincaRow).where(
                    _orm.FincaRow.identifier == record.identifier,
                ),
            ).scalar_one_or_none()
        if row is None:
            _log.debug("rental_finca: inserting new finca identifier=%s", record.identifier)
            row = _orm.FincaRow(
                identifier=record.identifier,
                address=record.address,
                valor_catastral_total=record.valor_catastral_total,
                valor_catastral_construccion=record.valor_catastral_construccion,
                valor_catastral_revision_year=record.valor_catastral_revision_year,
                coste_adquisicion=record.coste_adquisicion,
                coste_adquisicion_construccion=record.coste_adquisicion_construccion,
                acquisition_date=record.acquisition_date,
                disposal_date=record.disposal_date,
                use_type=record.use_type.value,
                is_stressed_area=record.is_stressed_area,
                titularidad_regime=record.titularidad.regime.value,
                titularidad_contribuyente=(
                    None if record.titularidad.contribuyente is None else record.titularidad.contribuyente.value
                ),
                titularidad_hijo_ordinal=record.titularidad.hijo_ordinal,
                porcentaje_propiedad=record.titularidad.porcentaje_propiedad,
                porcentaje_usufructo=record.titularidad.porcentaje_usufructo,
                schema_version=record.schema_version,
            )
            self.session.add(row)
        else:
            _log.debug("rental_finca: updating finca id=%s identifier=%s", record.id, record.identifier)
            row.identifier = record.identifier
            row.address = record.address
            row.valor_catastral_total = record.valor_catastral_total
            row.valor_catastral_construccion = record.valor_catastral_construccion
            row.valor_catastral_revision_year = record.valor_catastral_revision_year
            row.coste_adquisicion = record.coste_adquisicion
            row.coste_adquisicion_construccion = record.coste_adquisicion_construccion
            row.acquisition_date = record.acquisition_date
            row.disposal_date = record.disposal_date
            row.use_type = record.use_type.value
            row.is_stressed_area = record.is_stressed_area
            row.titularidad_regime = record.titularidad.regime.value
            row.titularidad_contribuyente = (
                None if record.titularidad.contribuyente is None else record.titularidad.contribuyente.value
            )
            row.titularidad_hijo_ordinal = record.titularidad.hijo_ordinal
            row.porcentaje_propiedad = record.titularidad.porcentaje_propiedad
            row.porcentaje_usufructo = record.titularidad.porcentaje_usufructo
            row.schema_version = record.schema_version
        _flush_or_wrap(self.session, "rental_finca")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.FincaRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_finca id={record_id} not found")
        _log.debug("rental_finca: deleting id=%d", record_id)
        self.session.delete(row)
        _flush_or_wrap(self.session, "rental_finca")

    @staticmethod
    def _to_record(row: _orm.FincaRow) -> Finca:
        from ..storage.errors import RepositoryError

        try:
            use_type = UseType(row.use_type)
        except ValueError as exc:
            _log.error(
                "rental_finca id=%s has unknown use_type=%r",
                row.id,
                row.use_type,
                exc_info=True,
            )
            raise RepositoryError(
                f"rental_finca id={row.id} has unknown use_type={row.use_type!r}",
            ) from exc
        try:
            titularidad = Titularidad(
                regime=TitularidadRegime(row.titularidad_regime),
                contribuyente=(
                    None
                    if row.titularidad_contribuyente is None
                    else TitularContribuyente(row.titularidad_contribuyente)
                ),
                hijo_ordinal=row.titularidad_hijo_ordinal,
                porcentaje_propiedad=row.porcentaje_propiedad,
                porcentaje_usufructo=row.porcentaje_usufructo,
            )
        except (ValueError, FincaValidationError) as exc:
            _log.error("rental_finca id=%s has an unreadable titularidad", row.id, exc_info=True)
            raise RepositoryError(
                f"rental_finca id={row.id} has an unreadable titularidad: {exc}",
            ) from exc
        return Finca(
            id=row.id,
            identifier=row.identifier,
            address=row.address,
            valor_catastral_total=row.valor_catastral_total,
            valor_catastral_construccion=row.valor_catastral_construccion,
            valor_catastral_revision_year=row.valor_catastral_revision_year,
            coste_adquisicion=row.coste_adquisicion,
            coste_adquisicion_construccion=row.coste_adquisicion_construccion,
            acquisition_date=row.acquisition_date,
            disposal_date=row.disposal_date,
            use_type=use_type,
            is_stressed_area=row.is_stressed_area,
            titularidad=titularidad,
            schema_version=row.schema_version,
        )


class ArrendamientoRepository:
    """Repository for :class:`Arrendamiento`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an open ORM ``session``."""
        self.session = session

    def list_all(self) -> list[Arrendamiento]:
        """Return every :class:`Arrendamiento` record in the table, ordered by surrogate id."""
        from ..storage.sql import orm as _orm

        rows = self.session.execute(select(_orm.ArrendamientoRow).order_by(_orm.ArrendamientoRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    def list_for_finca(self, finca_id: int) -> list[Arrendamiento]:
        """Return every :class:`Arrendamiento` record attached to the supplied finca."""
        from ..storage.sql import orm as _orm

        rows = (
            self.session.execute(
                select(_orm.ArrendamientoRow)
                .where(_orm.ArrendamientoRow.finca_id == finca_id)
                .order_by(_orm.ArrendamientoRow.contract_celebration_date),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get(self, record_id: int) -> Arrendamiento:
        """Return the record with surrogate id ``record_id``.

        Args:
            record_id: Surrogate integer primary key.

        Returns:
            The matching :class:`Arrendamiento` record.

        Raises:
            RepositoryError: When no row matches.
        """
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.ArrendamientoRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_contract id={record_id} not found")
        return self._to_record(row)

    def upsert(self, record: Arrendamiento) -> Arrendamiento:
        """Insert or update ``record`` and return the persisted :class:`Arrendamiento`."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row: _orm.ArrendamientoRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.ArrendamientoRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_contract id={record.id} not found for update")
        if row is None:
            row = _orm.ArrendamientoRow(**self._row_kwargs(record))
            self.session.add(row)
        else:
            for attr, value in self._row_kwargs(record).items():
                setattr(row, attr, value)
        _flush_or_wrap(self.session, "rental_contract")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.ArrendamientoRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_contract id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "rental_contract")

    @staticmethod
    def _row_kwargs(record: Arrendamiento) -> dict[str, object]:
        return {
            "finca_id": record.finca_id,
            "contract_celebration_date": record.contract_celebration_date,
            "contract_termination_date": record.contract_termination_date,
            "tenant_count": record.tenant_count,
            "qualifying_co_tenant_count": record.qualifying_co_tenant_count,
            "tenant_min_age": record.tenant_min_age,
            "tenant_max_age": record.tenant_max_age,
            "tenant_is_public_admin": record.tenant_is_public_admin,
            "tenant_is_ley_49_2002_entity_with_social_use": record.tenant_is_ley_49_2002_entity_with_social_use,
            "tenant_is_imv_beneficiary": record.tenant_is_imv_beneficiary,
            "dwelling_in_public_program": record.dwelling_in_public_program,
            "prior_contract_last_rent": record.prior_contract_last_rent,
            "prior_contract_indexation": record.prior_contract_indexation,
            "initial_rent": record.initial_rent,
            "is_first_rental": record.is_first_rental,
            "rehabilitation_finished_date": record.rehabilitation_finished_date,
            "lau_17_6_compliant": record.lau_17_6_compliant,
            "schema_version": record.schema_version,
        }

    @staticmethod
    def _to_record(row: _orm.ArrendamientoRow) -> Arrendamiento:
        return Arrendamiento(
            id=row.id,
            finca_id=row.finca_id,
            contract_celebration_date=row.contract_celebration_date,
            contract_termination_date=row.contract_termination_date,
            tenant_count=row.tenant_count,
            qualifying_co_tenant_count=row.qualifying_co_tenant_count,
            tenant_min_age=row.tenant_min_age,
            tenant_max_age=row.tenant_max_age,
            tenant_is_public_admin=row.tenant_is_public_admin,
            tenant_is_ley_49_2002_entity_with_social_use=row.tenant_is_ley_49_2002_entity_with_social_use,
            tenant_is_imv_beneficiary=row.tenant_is_imv_beneficiary,
            dwelling_in_public_program=row.dwelling_in_public_program,
            prior_contract_last_rent=row.prior_contract_last_rent,
            prior_contract_indexation=row.prior_contract_indexation,
            initial_rent=row.initial_rent,
            is_first_rental=row.is_first_rental,
            rehabilitation_finished_date=row.rehabilitation_finished_date,
            lau_17_6_compliant=row.lau_17_6_compliant,
            schema_version=row.schema_version,
        )


class FincaRendimientoRepository:
    """Repository for :class:`FincaRendimientoRecord`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an open ORM ``session``."""
        self.session = session

    def list_for_period(self, period_year: int) -> list[FincaRendimientoRecord]:
        """Return every record whose period overlaps the supplied window.

        Returns:
            List of :class:`FincaRendimientoRecord` for the given period year.
        """
        from ..storage.sql import orm as _orm

        rows = (
            self.session.execute(
                select(_orm.FincaRendimientoRecordRow)
                .where(_orm.FincaRendimientoRecordRow.period_year == period_year)
                .order_by(_orm.FincaRendimientoRecordRow.id),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_for_contract_period(
        self,
        contract_id: int,
        period_year: int,
    ) -> FincaRendimientoRecord | None:
        """Return the :class:`FincaRendimientoRecord` for ``contract_id`` matching ``period``, or ``None``."""
        from ..storage.sql import orm as _orm

        row = self.session.execute(
            select(_orm.FincaRendimientoRecordRow).where(
                _orm.FincaRendimientoRecordRow.contract_id == contract_id,
                _orm.FincaRendimientoRecordRow.period_year == period_year,
            ),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: FincaRendimientoRecord) -> FincaRendimientoRecord:
        """Insert or update ``record`` and return the persisted :class:`FincaRendimientoRecord`."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row: _orm.FincaRendimientoRecordRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.FincaRendimientoRecordRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_income_record id={record.id} not found for update")
        else:
            row = self.session.execute(
                select(_orm.FincaRendimientoRecordRow).where(
                    _orm.FincaRendimientoRecordRow.contract_id == record.contract_id,
                    _orm.FincaRendimientoRecordRow.period_year == record.period_year,
                ),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.FincaRendimientoRecordRow(
                contract_id=record.contract_id,
                period_year=record.period_year,
                gross_rent_received=record.gross_rent_received,
                dias_alquilados=record.dias_alquilados,
                schema_version=record.schema_version,
            )
            self.session.add(row)
        else:
            row.gross_rent_received = record.gross_rent_received
            row.dias_alquilados = record.dias_alquilados
            row.schema_version = record.schema_version
        _flush_or_wrap(self.session, "rental_income_record")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.FincaRendimientoRecordRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_income_record id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "rental_income_record")

    @staticmethod
    def _to_record(row: _orm.FincaRendimientoRecordRow) -> FincaRendimientoRecord:
        return FincaRendimientoRecord(
            id=row.id,
            contract_id=row.contract_id,
            period_year=row.period_year,
            gross_rent_received=row.gross_rent_received,
            dias_alquilados=row.dias_alquilados,
            schema_version=row.schema_version,
        )


class FincaGastoRepository:
    """Repository for :class:`FincaGasto`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an open ORM ``session``."""
        self.session = session

    def list_for_finca_period(self, finca_id: int, period_year: int) -> list[FincaGasto]:
        """Return every :class:`FincaGasto` record attached to ``finca_id`` within the period window."""
        from ..storage.sql import orm as _orm

        rows = (
            self.session.execute(
                select(_orm.FincaGastoRow)
                .where(
                    _orm.FincaGastoRow.finca_id == finca_id,
                    _orm.FincaGastoRow.period_year == period_year,
                )
                .order_by(_orm.FincaGastoRow.id),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def add(self, record: FincaGasto) -> FincaGasto:
        """Insert ``record`` and return the persisted :class:`FincaGasto` entity."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        if record.id is not None:
            raise RepositoryError(
                "FincaGastoRepository.add expects a record without an id; use upsert() to update an existing row",
            )
        row = _orm.FincaGastoRow(
            finca_id=record.finca_id,
            period_year=record.period_year,
            category=record.category.value,
            amount=record.amount,
            schema_version=record.schema_version,
        )
        self.session.add(row)
        _flush_or_wrap(self.session, "rental_expense")
        return self._to_record(row)

    def upsert(self, record: FincaGasto) -> FincaGasto:
        """Insert or update ``record`` and return the persisted entity.

        Returns:
            The persisted :class:`FincaGasto` with any database-generated fields populated.
        """
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        if record.id is None:
            return self.add(record)
        row = self.session.get(_orm.FincaGastoRow, record.id)
        if row is None:
            raise RepositoryError(f"rental_expense id={record.id} not found for update")
        row.finca_id = record.finca_id
        row.period_year = record.period_year
        row.category = record.category.value
        row.amount = record.amount
        row.schema_version = record.schema_version
        _flush_or_wrap(self.session, "rental_expense")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.FincaGastoRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_expense id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "rental_expense")

    @staticmethod
    def _to_record(row: _orm.FincaGastoRow) -> FincaGasto:
        from ..storage.errors import RepositoryError

        try:
            category = ExpenseCategory(row.category)
        except ValueError as exc:
            _log.error(
                "rental_expense id=%s has unknown category=%r",
                row.id,
                row.category,
                exc_info=True,
            )
            raise RepositoryError(
                f"rental_expense id={row.id} has unknown category={row.category!r}",
            ) from exc
        return FincaGasto(
            id=row.id,
            finca_id=row.finca_id,
            period_year=row.period_year,
            category=category,
            amount=row.amount,
            schema_version=row.schema_version,
        )


class FincaAmortizacionLedgerRepository:
    """Repository for :class:`FincaAmortizacionLedgerEntry`."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an open ORM ``session``."""
        self.session = session

    def list_for_finca(self, finca_id: int) -> list[FincaAmortizacionLedgerEntry]:
        """Return every record attached to the supplied finca.

        Returns:
            List of :class:`FincaAmortizacionLedgerEntry` for the finca.
        """
        from ..storage.sql import orm as _orm

        rows = (
            self.session.execute(
                select(_orm.FincaAmortizacionLedgerRow)
                .where(_orm.FincaAmortizacionLedgerRow.finca_id == finca_id)
                .order_by(_orm.FincaAmortizacionLedgerRow.period_year),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_for_finca_period(
        self,
        finca_id: int,
        period_year: int,
    ) -> FincaAmortizacionLedgerEntry | None:
        """Return the record for ``finca_id`` matching ``period``, or ``None``.

        Returns:
            The matching :class:`FincaAmortizacionLedgerEntry`, or ``None`` when absent.
        """
        from ..storage.sql import orm as _orm

        row = self.session.execute(
            select(_orm.FincaAmortizacionLedgerRow).where(
                _orm.FincaAmortizacionLedgerRow.finca_id == finca_id,
                _orm.FincaAmortizacionLedgerRow.period_year == period_year,
            ),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: FincaAmortizacionLedgerEntry) -> FincaAmortizacionLedgerEntry:
        """Insert or update ``record`` and return the persisted :class:`FincaAmortizacionLedgerEntry`."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row: _orm.FincaAmortizacionLedgerRow | None = None
        if record.id is not None:
            row = self.session.get(_orm.FincaAmortizacionLedgerRow, record.id)
            if row is None:
                raise RepositoryError(
                    f"rental_amortization_ledger id={record.id} not found for update",
                )
        else:
            row = self.session.execute(
                select(_orm.FincaAmortizacionLedgerRow).where(
                    _orm.FincaAmortizacionLedgerRow.finca_id == record.finca_id,
                    _orm.FincaAmortizacionLedgerRow.period_year == record.period_year,
                ),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.FincaAmortizacionLedgerRow(
                finca_id=record.finca_id,
                period_year=record.period_year,
                dias_alquilados=record.dias_alquilados,
                basis_used=record.basis_used,
                amortization_amount=record.amortization_amount,
                cumulative_amortization_through_year=record.cumulative_amortization_through_year,
                schema_version=record.schema_version,
            )
            self.session.add(row)
        else:
            row.dias_alquilados = record.dias_alquilados
            row.basis_used = record.basis_used
            row.amortization_amount = record.amortization_amount
            row.cumulative_amortization_through_year = record.cumulative_amortization_through_year
            row.schema_version = record.schema_version
        _flush_or_wrap(self.session, "rental_amortization_ledger")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ..storage.errors import RepositoryError
        from ..storage.sql import orm as _orm

        row = self.session.get(_orm.FincaAmortizacionLedgerRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_amortization_ledger id={record_id} not found")
        self.session.delete(row)
        _flush_or_wrap(self.session, "rental_amortization_ledger")

    @staticmethod
    def _to_record(row: _orm.FincaAmortizacionLedgerRow) -> FincaAmortizacionLedgerEntry:
        return FincaAmortizacionLedgerEntry(
            id=row.id,
            finca_id=row.finca_id,
            period_year=row.period_year,
            dias_alquilados=row.dias_alquilados,
            basis_used=row.basis_used,
            amortization_amount=row.amortization_amount,
            cumulative_amortization_through_year=row.cumulative_amortization_through_year,
            schema_version=row.schema_version,
        )


__all__ = [
    "ArrendamientoRepository",
    "FincaAmortizacionLedgerRepository",
    "FincaGastoRepository",
    "FincaRendimientoRepository",
    "FincaRepository",
]
