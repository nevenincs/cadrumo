"""Typed repositories for the rental-register record types.

Bridges between the public :mod:`aeat.domain.rental._models` records and the
internal :mod:`aeat.adapters.persistence.storage._orm` mapper rows. Every method routes
through ``Repository._flush_or_wrap`` so DB integrity violations
surface as :class:`RepositoryError`.

Storage imports are deferred behind methods that consult them so the
rental subpackage does not pull :mod:`aeat.adapters.persistence.storage` (with its
Alembic plugin discovery) into every CLI command's import chain;
this preserves the json-pipe-safety contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.logging import get_logger
from ._enums import ExpenseCategory, UseType
from ._models import (
    RentalAmortizationLedgerEntry,
    RentalContract,
    RentalExpense,
    RentalFinca,
    RentalIncomeRecord,
)

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from ...adapters.persistence.storage.sql import _orm

_log = get_logger(__name__)


def _flush_or_wrap(session: Session, kind: str) -> None:
    from ...adapters.persistence.storage.errors import RepositoryError

    try:
        session.flush()
    except IntegrityError as exc:
        raise RepositoryError(f"integrity violation during {kind} operation: {exc.orig}") from exc


class RentalFincaRepository:
    """Repository for :class:`RentalFinca`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[RentalFinca]:
        """Return every record in the table, ordered by surrogate id."""
        from ...adapters.persistence.storage.sql import _orm

        rows = self._session.execute(select(_orm.RentalFincaRow).order_by(_orm.RentalFincaRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    def get(self, record_id: int) -> RentalFinca:
        """Return the record with surrogate id ``record_id``.

        Raises:
            RepositoryError: When no row matches.
        """
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalFincaRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_finca id={record_id} not found")
        return self._to_record(row)

    def get_by_identifier(self, identifier: str) -> RentalFinca | None:
        """Return the record matching ``identifier``, or ``None`` if absent."""
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.execute(
            select(_orm.RentalFincaRow).where(_orm.RentalFincaRow.identifier == identifier),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: RentalFinca) -> RentalFinca:
        """Insert or update ``record`` and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row: _orm.RentalFincaRow | None = None
        if record.id is not None:
            row = self._session.get(_orm.RentalFincaRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_finca id={record.id} not found for update")
        else:
            row = self._session.execute(
                select(_orm.RentalFincaRow).where(
                    _orm.RentalFincaRow.identifier == record.identifier,
                ),
            ).scalar_one_or_none()
        if row is None:
            _log.debug("rental_finca: inserting new finca identifier=%s", record.identifier)
            row = _orm.RentalFincaRow(
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
                schema_version=record.schema_version,
            )
            self._session.add(row)
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
            row.schema_version = record.schema_version
        _flush_or_wrap(self._session, "rental_finca")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalFincaRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_finca id={record_id} not found")
        _log.debug("rental_finca: deleting id=%d", record_id)
        self._session.delete(row)
        _flush_or_wrap(self._session, "rental_finca")

    @staticmethod
    def _to_record(row: _orm.RentalFincaRow) -> RentalFinca:
        from ...adapters.persistence.storage.errors import RepositoryError

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
        return RentalFinca(
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
            schema_version=row.schema_version,
        )


class RentalContractRepository:
    """Repository for :class:`RentalContract`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[RentalContract]:
        """Return every record in the table, ordered by surrogate id."""
        from ...adapters.persistence.storage.sql import _orm

        rows = self._session.execute(select(_orm.RentalContractRow).order_by(_orm.RentalContractRow.id)).scalars().all()
        return [self._to_record(row) for row in rows]

    def list_for_finca(self, finca_id: int) -> list[RentalContract]:
        """Return every record attached to the supplied finca."""
        from ...adapters.persistence.storage.sql import _orm

        rows = (
            self._session.execute(
                select(_orm.RentalContractRow)
                .where(_orm.RentalContractRow.finca_id == finca_id)
                .order_by(_orm.RentalContractRow.contract_celebration_date),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get(self, record_id: int) -> RentalContract:
        """Return the record with surrogate id ``record_id``.

        Raises:
            RepositoryError: When no row matches.
        """
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalContractRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_contract id={record_id} not found")
        return self._to_record(row)

    def upsert(self, record: RentalContract) -> RentalContract:
        """Insert or update ``record`` and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row: _orm.RentalContractRow | None = None
        if record.id is not None:
            row = self._session.get(_orm.RentalContractRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_contract id={record.id} not found for update")
        if row is None:
            row = _orm.RentalContractRow(**self._row_kwargs(record))
            self._session.add(row)
        else:
            for attr, value in self._row_kwargs(record).items():
                setattr(row, attr, value)
        _flush_or_wrap(self._session, "rental_contract")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalContractRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_contract id={record_id} not found")
        self._session.delete(row)
        _flush_or_wrap(self._session, "rental_contract")

    @staticmethod
    def _row_kwargs(record: RentalContract) -> dict[str, object]:
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
    def _to_record(row: _orm.RentalContractRow) -> RentalContract:
        return RentalContract(
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


class RentalIncomeRepository:
    """Repository for :class:`RentalIncomeRecord`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_period(self, period_year: int) -> list[RentalIncomeRecord]:
        """Return every record whose period overlaps the supplied window."""
        from ...adapters.persistence.storage.sql import _orm

        rows = (
            self._session.execute(
                select(_orm.RentalIncomeRecordRow)
                .where(_orm.RentalIncomeRecordRow.period_year == period_year)
                .order_by(_orm.RentalIncomeRecordRow.id),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_for_contract_period(
        self,
        contract_id: int,
        period_year: int,
    ) -> RentalIncomeRecord | None:
        """Return the record for ``contract_id`` matching ``period``, or ``None``."""
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.execute(
            select(_orm.RentalIncomeRecordRow).where(
                _orm.RentalIncomeRecordRow.contract_id == contract_id,
                _orm.RentalIncomeRecordRow.period_year == period_year,
            ),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: RentalIncomeRecord) -> RentalIncomeRecord:
        """Insert or update ``record`` and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row: _orm.RentalIncomeRecordRow | None = None
        if record.id is not None:
            row = self._session.get(_orm.RentalIncomeRecordRow, record.id)
            if row is None:
                raise RepositoryError(f"rental_income_record id={record.id} not found for update")
        else:
            row = self._session.execute(
                select(_orm.RentalIncomeRecordRow).where(
                    _orm.RentalIncomeRecordRow.contract_id == record.contract_id,
                    _orm.RentalIncomeRecordRow.period_year == record.period_year,
                ),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.RentalIncomeRecordRow(
                contract_id=record.contract_id,
                period_year=record.period_year,
                gross_rent_received=record.gross_rent_received,
                dias_alquilados=record.dias_alquilados,
                schema_version=record.schema_version,
            )
            self._session.add(row)
        else:
            row.gross_rent_received = record.gross_rent_received
            row.dias_alquilados = record.dias_alquilados
            row.schema_version = record.schema_version
        _flush_or_wrap(self._session, "rental_income_record")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalIncomeRecordRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_income_record id={record_id} not found")
        self._session.delete(row)
        _flush_or_wrap(self._session, "rental_income_record")

    @staticmethod
    def _to_record(row: _orm.RentalIncomeRecordRow) -> RentalIncomeRecord:
        return RentalIncomeRecord(
            id=row.id,
            contract_id=row.contract_id,
            period_year=row.period_year,
            gross_rent_received=row.gross_rent_received,
            dias_alquilados=row.dias_alquilados,
            schema_version=row.schema_version,
        )


class RentalExpenseRepository:
    """Repository for :class:`RentalExpense`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_finca_period(self, finca_id: int, period_year: int) -> list[RentalExpense]:
        """Return every record attached to ``finca_id`` within the period window."""
        from ...adapters.persistence.storage.sql import _orm

        rows = (
            self._session.execute(
                select(_orm.RentalExpenseRow)
                .where(
                    _orm.RentalExpenseRow.finca_id == finca_id,
                    _orm.RentalExpenseRow.period_year == period_year,
                )
                .order_by(_orm.RentalExpenseRow.id),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def add(self, record: RentalExpense) -> RentalExpense:
        """Insert ``record`` into the underlying store and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        if record.id is not None:
            raise RepositoryError(
                "RentalExpenseRepository.add expects a record without an id; use upsert() to update an existing row",
            )
        row = _orm.RentalExpenseRow(
            finca_id=record.finca_id,
            period_year=record.period_year,
            category=record.category.value,
            amount=record.amount,
            schema_version=record.schema_version,
        )
        self._session.add(row)
        _flush_or_wrap(self._session, "rental_expense")
        return self._to_record(row)

    def upsert(self, record: RentalExpense) -> RentalExpense:
        """Insert or update ``record`` and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        if record.id is None:
            return self.add(record)
        row = self._session.get(_orm.RentalExpenseRow, record.id)
        if row is None:
            raise RepositoryError(f"rental_expense id={record.id} not found for update")
        row.finca_id = record.finca_id
        row.period_year = record.period_year
        row.category = record.category.value
        row.amount = record.amount
        row.schema_version = record.schema_version
        _flush_or_wrap(self._session, "rental_expense")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalExpenseRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_expense id={record_id} not found")
        self._session.delete(row)
        _flush_or_wrap(self._session, "rental_expense")

    @staticmethod
    def _to_record(row: _orm.RentalExpenseRow) -> RentalExpense:
        from ...adapters.persistence.storage.errors import RepositoryError

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
        return RentalExpense(
            id=row.id,
            finca_id=row.finca_id,
            period_year=row.period_year,
            category=category,
            amount=row.amount,
            schema_version=row.schema_version,
        )


class RentalAmortizationLedgerRepository:
    """Repository for :class:`RentalAmortizationLedgerEntry`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_finca(self, finca_id: int) -> list[RentalAmortizationLedgerEntry]:
        """Return every record attached to the supplied finca."""
        from ...adapters.persistence.storage.sql import _orm

        rows = (
            self._session.execute(
                select(_orm.RentalAmortizationLedgerRow)
                .where(_orm.RentalAmortizationLedgerRow.finca_id == finca_id)
                .order_by(_orm.RentalAmortizationLedgerRow.period_year),
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_for_finca_period(
        self,
        finca_id: int,
        period_year: int,
    ) -> RentalAmortizationLedgerEntry | None:
        """Return the record for ``finca_id`` matching ``period``, or ``None``."""
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.execute(
            select(_orm.RentalAmortizationLedgerRow).where(
                _orm.RentalAmortizationLedgerRow.finca_id == finca_id,
                _orm.RentalAmortizationLedgerRow.period_year == period_year,
            ),
        ).scalar_one_or_none()
        return None if row is None else self._to_record(row)

    def upsert(self, record: RentalAmortizationLedgerEntry) -> RentalAmortizationLedgerEntry:
        """Insert or update ``record`` and return the persisted entity."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row: _orm.RentalAmortizationLedgerRow | None = None
        if record.id is not None:
            row = self._session.get(_orm.RentalAmortizationLedgerRow, record.id)
            if row is None:
                raise RepositoryError(
                    f"rental_amortization_ledger id={record.id} not found for update",
                )
        else:
            row = self._session.execute(
                select(_orm.RentalAmortizationLedgerRow).where(
                    _orm.RentalAmortizationLedgerRow.finca_id == record.finca_id,
                    _orm.RentalAmortizationLedgerRow.period_year == record.period_year,
                ),
            ).scalar_one_or_none()
        if row is None:
            row = _orm.RentalAmortizationLedgerRow(
                finca_id=record.finca_id,
                period_year=record.period_year,
                dias_alquilados=record.dias_alquilados,
                basis_used=record.basis_used,
                amortization_amount=record.amortization_amount,
                cumulative_amortization_through_year=record.cumulative_amortization_through_year,
                schema_version=record.schema_version,
            )
            self._session.add(row)
        else:
            row.dias_alquilados = record.dias_alquilados
            row.basis_used = record.basis_used
            row.amortization_amount = record.amortization_amount
            row.cumulative_amortization_through_year = record.cumulative_amortization_through_year
            row.schema_version = record.schema_version
        _flush_or_wrap(self._session, "rental_amortization_ledger")
        return self._to_record(row)

    def delete(self, record_id: int) -> None:
        """Delete the record with surrogate id ``record_id``."""
        from ...adapters.persistence.storage.errors import RepositoryError
        from ...adapters.persistence.storage.sql import _orm

        row = self._session.get(_orm.RentalAmortizationLedgerRow, record_id)
        if row is None:
            raise RepositoryError(f"rental_amortization_ledger id={record_id} not found")
        self._session.delete(row)
        _flush_or_wrap(self._session, "rental_amortization_ledger")

    @staticmethod
    def _to_record(row: _orm.RentalAmortizationLedgerRow) -> RentalAmortizationLedgerEntry:
        return RentalAmortizationLedgerEntry(
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
    "RentalAmortizationLedgerRepository",
    "RentalContractRepository",
    "RentalExpenseRepository",
    "RentalFincaRepository",
    "RentalIncomeRepository",
]
