"""Compose the canonical installed export-parity seed stages."""

from __future__ import annotations

from .seed_carry import CarrySeedStage
from .seed_ledger import LedgerSeedStage
from .seed_modelos import ModeloSeedStage
from .seed_profile import ProfileSeedStage
from .seed_withholding import WithholdingSeedStage


class _Seeder(ProfileSeedStage, LedgerSeedStage, WithholdingSeedStage, CarrySeedStage, ModeloSeedStage):
    """Combine the ordered public seed stages over one resumable receipt."""
