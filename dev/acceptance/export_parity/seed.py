"""Seed resumable export-parity campaigns through installed public commands."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from collections.abc import Sequence
from pathlib import Path

from cadrumo.core.hashing import sha256_file
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError, authority_generation

from .scenario import (
    SCENARIO_VERSION,
    YEARS,
)
from .seed_campaign import _Seeder
from .seed_contracts import (
    SeedError,
    SeedReceipt,
)


def carried_years(years: Sequence[int], *, stages: Sequence[str], carry_evidence: str) -> tuple[int, ...]:
    """The seeded years whose prior-year facts the carry lane brings in.

    Only the synthetic lane carries, only for a year whose predecessor is not
    itself seeded, and only when modelos are calculated. The honest lane
    carries nothing, so a first year after the activity start keeps its
    product refusals.
    """
    if carry_evidence != "synthetic_csv_register" or "modelos" not in stages:
        return ()
    return tuple(year for year in years if year - 1 not in years)


def _open_cli(executable: Path, *, authority_root: Path, run_dir: Path) -> InstalledCli:
    run_dir.mkdir(parents=True, exist_ok=True)
    secret = run_dir / "passphrase"
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        os.chmod(secret, 0o600)
    (run_dir / "store").mkdir(exist_ok=True)
    return InstalledCli(
        executable,
        storage_root=run_dir / "store",
        authority_root=authority_root,
        passphrase=secret.read_text(encoding="utf-8").strip(),
    )


def run_seed(
    *,
    executable: Path,
    authority_root: Path,
    run_dir: Path,
    years: Sequence[int] = YEARS,
    stages: Sequence[str] = ("ledger", "amortization", "withholding", "modelos"),
    carry_evidence: str = "none",
) -> SeedReceipt:
    """Seed ``years`` into ``run_dir/store`` and return the receipt, raising :class:`SeedError` on a refusal."""
    cli = _open_cli(executable, authority_root=authority_root, run_dir=run_dir)
    receipt_path = run_dir / "seed-receipt.json"
    generation = authority_generation(authority_root)
    receipt = SeedReceipt.load(receipt_path) or SeedReceipt(
        scenario=SCENARIO_VERSION,
        authority_generation=generation,
        executable_sha256=sha256_file(cli.executable),
        carry_evidence=carry_evidence,
    )
    if receipt.authority_generation != generation:
        raise SeedError("authority generation changed since this store was seeded; seed a fresh store")
    if receipt.carry_evidence != carry_evidence:
        raise SeedError(f"this store was seeded with carry evidence {receipt.carry_evidence!r}; seed a fresh store")
    seeder = _Seeder(
        cli, receipt=receipt, receipt_path=receipt_path, artifact_dir=run_dir / "evidence", first_year=min(years)
    )
    seeder.profile()
    carried = carried_years(years, stages=stages, carry_evidence=carry_evidence)
    for year in years:
        if year in carried:
            seeder.carry_in(year)
            seeder.carry_m303_compensation(year)
        for stage in stages:
            getattr(seeder, stage)(year)
    receipt.save(receipt_path)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    """Seed the requested years and print the completed and blocked stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    parser.add_argument("--stages", nargs="+", default=["ledger", "amortization", "withholding", "modelos"])
    parser.add_argument("--carry-evidence", choices=("none", "synthetic_csv_register"), default="none")
    args = parser.parse_args(argv)
    try:
        receipt = run_seed(
            executable=args.cli.resolve(),
            authority_root=args.authority_root.resolve(),
            run_dir=args.run_dir.resolve(),
            years=args.years,
            stages=args.stages,
            carry_evidence=args.carry_evidence,
        )
    except (SeedError, InstalledCliError) as exc:
        print(f"seed stopped: {exc}")
        return 2
    print(json.dumps({"completed": receipt.completed_stages[-5:], "blocked": receipt.blocked}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
