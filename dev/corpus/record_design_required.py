"""Every required official record design, composed in modelo order from its range modules."""

from __future__ import annotations

from .record_design_required_01_199 import REQUIRED_01_199
from .record_design_required_200_999 import REQUIRED_200_999

REQUIRED = (*REQUIRED_01_199, *REQUIRED_200_999)
