"""Canonical modelos stage for installed export-parity seeding."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .scenario import (
    QUARTERS,
)
from .seed_contracts import (
    _ACTOR,
    _ANNUAL,
    _M100_BINDINGS,
    _M100_CASILLAS,
    _PERIODIC,
    SeedRefusalError,
)
from .seed_inputs import (
    _binding_ids,
)
from .seed_state import SeedState


def _verify_modelo_revision(self: ModeloSeedStage, stage: str, revision_id: str) -> None:
    """Verify modelo revision."""
    if self._pending(f"{stage}.verify"):
        verified = self._result(
            ("app", "modelo", "work", "verify", revision_id, "--by", _ACTOR), stage=f"{stage}.verify"
        )
        if verified.get("granted_verificado_completo") is not True:
            reasons = sorted(
                {
                    str(finding.get("kind"))
                    for finding in verified.get("findings") or ()
                    if isinstance(finding, dict) and finding.get("severity") == "blocking"
                }
            )
            self.receipt.blocked[f"{stage}.verify"] = f"not_granted: {', '.join(reasons)[:300]}"
            self.receipt.save(self.receipt_path)
            raise SeedRefusalError(f"{stage}: verification was not granted")
        self._complete(f"{stage}.verify")


class ModeloSeedStage(SeedState):
    """Own the installed seed modelos behavior."""

    def _lifecycle(self, modelo: str, year: int, period: str, extra: Callable[[], Sequence[str]] = tuple) -> None:
        stage = f"modelo:{modelo}:{year}:{period}"
        if not self._stage(stage):
            return
        work_key, revision_key = f"work:{modelo}:{year}:{period}", f"revision:{modelo}:{year}:{period}"
        if self._pending(f"{stage}.create"):
            created = self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "create",
                    "--modelo",
                    modelo,
                    "--year",
                    str(year),
                    "--period",
                    period,
                    "--by",
                    _ACTOR,
                ),
                stage=f"{stage}.create",
            )
            self._remember(work_key, created["work_unit_id"])
            self._complete(f"{stage}.create")
        work_id = self.receipt.identifiers[work_key]
        if self._pending(f"{stage}.calculate"):
            calculated = self._result(
                ("app", "modelo", "work", "calculate", work_id, *extra(), "--by", _ACTOR), stage=f"{stage}.calculate"
            )
            self._remember(revision_key, calculated["calculation_revision_id"])
            self._complete(f"{stage}.calculate")
        revision_id = self.receipt.identifiers[revision_key]
        _verify_modelo_revision(self, stage, revision_id)
        if self._pending(f"{stage}.file"):
            self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "file",
                    revision_id,
                    "--by",
                    _ACTOR,
                    "--notes",
                    "Synthetic local filing record only; never sent to AEAT",
                ),
                stage=f"{stage}.file",
            )
            self._complete(f"{stage}.file")
        self.receipt.blocked.pop(f"{stage}.verify", None)
        self._done(stage)

    def modelos(self, year: int) -> None:
        """Run the ordered quarterly and annual public modelo stages."""
        for period in QUARTERS:
            for modelo in _PERIODIC:
                self._attempt(
                    lambda modelo=modelo, period=period: self._lifecycle(
                        modelo, year, period, lambda: self._calculation_inputs(modelo, year, period)
                    )
                )
        for modelo in _ANNUAL:
            self._attempt(
                lambda modelo=modelo: self._lifecycle(
                    modelo, year, "0A", lambda: self._calculation_inputs(modelo, year, "0A")
                )
            )

    def _calculation_inputs(self, modelo: str, year: int, period: str) -> tuple[str, ...]:
        """Return the operator answers ``work calculate`` asks for this modelo and period."""
        if modelo == "303":
            inputs: tuple[str, ...] = ("--no-joint-return-elected",)
            if period == QUARTERS[-1]:
                attachment_id, sha256 = self._m303_exonerado_390_attestation(year, period)
                inputs += ("--m303-exonerado-390-attachment-id", attachment_id, "--m303-exonerado-390-sha256", sha256)
            return inputs
        if modelo == "100":
            declared = self._declared_bindings("100", year)
            casillas = tuple(argument for value in _M100_CASILLAS for argument in ("--casilla", value))
            bindings = tuple(
                argument
                for binding_id, value in _M100_BINDINGS.items()
                if binding_id in declared
                for argument in ("--binding", f"{binding_id}={value}")
            )
            return casillas + bindings
        return ()

    def _m303_exonerado_390_attestation(self, year: int, period: str) -> tuple[str, str]:
        """Attest that the filer is not exempt from Modelo 390, once per year, as the last 303 asks."""
        key = f"attest:303:{year}:{period}"
        if self._pending(key):
            attested = self._result(
                (
                    "app",
                    "modelo",
                    "work",
                    "attest-m303-exonerado-390",
                    "--year",
                    str(year),
                    "--period",
                    period,
                    "--observed-at",
                    f"{year + 1}-01-10T12:00:00+00:00",
                    "--by",
                    _ACTOR,
                ),
                stage=f"{key}.attest",
            )
            self._remember(f"{key}:attachment_id", attested["attachment_id"])
            self._remember(f"{key}:sha256", attested["sha256"])
            self._complete(key)
        return self.receipt.identifiers[f"{key}:attachment_id"], self.receipt.identifiers[f"{key}:sha256"]

    def _declared_bindings(self, modelo: str, year: int) -> frozenset[str]:
        """Read the binding ids the selected revision declares, so no other year's answer is sent."""
        listed = self._result(
            ("app", "modelo", "bindings", "list", "--modelo", modelo, "--year", str(year)),
            stage=f"bindings:{modelo}:{year}",
        )
        return frozenset(_binding_ids(listed))
