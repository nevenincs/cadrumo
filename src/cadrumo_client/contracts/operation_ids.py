"""Registered operation ids the runtime names without importing the product that defines the operations.

The product declares and executes these operations. The runtime only grants
their commit fences a capability, such as starting the local model program's
server, and names them here so that its adapters reach no product code.
"""

from __future__ import annotations

from typing import Final

LOCAL_READER_OPERATION_DEFINITION_ID: Final = "local-reader.provision"
"""Provisioning of the local document reader's model program."""

DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID: Final = "dependencies.setup"
"""Setup of the product's optional dependencies, including the local model program."""
