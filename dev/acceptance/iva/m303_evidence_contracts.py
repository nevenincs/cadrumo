"""Value-free installed ordinary Modelo 303 evidence contracts and synthetic coordinates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal, cast

if TYPE_CHECKING:
    pass


_SCHEMA_VERSION: Final = "iva-01-installed-m303-evidence-journey-v2"


_CHILD_MODULE: Final = "dev.acceptance.iva.installed_m303_evidence_journey"


_PERIOD: Final = "4T"


_PRIOR_PERIOD: Final = "3T"


_WRONG_PERIOD: Final = "12"


_MONTH: Final = "12"


_PRIOR_MONTH: Final = "11"


_FIRST_QUARTER: Final = "1T"


_COORDINATES: Final = tuple(
    ("303", period) for period in (_PERIOD, _PRIOR_PERIOD, _MONTH, _PRIOR_MONTH, _FIRST_QUARTER)
)


_ORACLE_RESULTADO: Final = Decimal("21.00") - Decimal("10.50")


_RESULTADO_CASILLA: Final = "iva.resultado"


_OUTSIDE_LAST_PERIOD: Final = "exonerado_390_attestation_outside_last_period"


# Month and day of the sale and purchase inside each scenario's period.
_LAST_PERIOD_DAYS: Final = ((12, 15), (12, 18))


_FIRST_QUARTER_DAYS: Final = ((2, 15), (2, 18))


_MISMATCHED_ATTACHMENT_ID: Final = "a" * 64


_MISMATCHED_SHA256: Final = "b" * 64


_DEVELOPMENT_MOCK_HEADER: Final = {"program": b"0000", "developer": b"00000000T"}


_EVIDENCE_SUBMIT_ID: Final = "#m303-evidence-submit"


_ATTESTATION_REFUSAL_KEY: Final = "errors.refused.refused_modelo_m303_exonerado_390_attestation_unadmissible"


type ChildMode = Literal["tui-led-calculate", "tui-continue-calculate", "tui-joint-only-calculate", "tui-reopen"]


class IvaInstalledM303Error(RuntimeError):
    """The installed evidence journey could not prove a required outcome."""


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """One fresh installed CLI process, reduced to its public outcome."""

    command: str
    returncode: int
    status: str
    error_code: str | None


@dataclass(frozen=True, slots=True)
class TuiOutcome:
    """One installed TUI interaction, reduced to its public outcome."""

    step: str
    terminal_condition: str
    visible_notice_key: str | None


@dataclass(frozen=True, slots=True)
class ReopenReadback:
    """What a fresh installed TUI session shows for the calculated declaration.

    ``resultado_origin`` is the origin the workbench gives the ``iva.resultado``
    casilla (``None`` when it shows no such casilla), and
    ``resultado_matches_oracle`` whether the value it holds equals the oracle.
    """

    revision_listed_current: bool
    revision_state: str | None
    resultado_origin: str | None
    resultado_matches_oracle: bool


@dataclass(frozen=True, slots=True)
class ChildReceipt:
    """Value-free result of one installed TUI child process."""

    schema_version: str
    status: Literal["proven"]
    mode: str
    product_origin: str
    product_init_sha256: str
    outcomes: tuple[TuiOutcome, ...]
    reopen: ReopenReadback | None

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe receipt."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class ChildHandle:
    """Value-free handle for one installed TUI child process."""

    mode: str
    returncode: int
    receipt_status: str
    receipt_sha256: str
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True, slots=True)
class StoreEvidence:
    """Outcome of one isolated synthetic store."""

    scenario: Literal["tui_led", "continuation", "monthly", "first_quarter"]
    work_unit_id: str
    calculation_revision_id: str
    revision_count: int
    cli_resultado_matches_oracle: bool
    cli_revision_verified: bool
    cli_recalculated_same_revision: bool | None
    changed_evidence_produced_distinct_revision: bool | None
    tui_reopen: ReopenReadback
    commands: tuple[CommandOutcome, ...]
    children: tuple[ChildHandle, ...]
    child_outcomes: tuple[TuiOutcome, ...]


@dataclass(frozen=True, slots=True)
class JourneyReceipt:
    """Sanitized installed evidence for the ordinary M303 evidence contract."""

    schema_version: str
    status: Literal["proven"]
    filing_year: int
    periods: tuple[str, ...]
    source_commit: str
    wheel_filename: str
    wheel_sha256: str
    package_version: str
    installed_init_path: str
    installed_init_sha256: str
    authority_generation: str
    authority_descriptor_sha256: str
    bundled_authority_generation: str
    stores: tuple[StoreEvidence, ...]
    unexercised: tuple[str, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe receipt."""
        return cast(dict[str, object], asdict(self))
