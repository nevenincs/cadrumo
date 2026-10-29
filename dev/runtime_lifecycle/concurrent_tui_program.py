"""Embedded TUI client used by the concurrent session probe."""

# The production TUI client calls without mounting Textual: resume the person's
# sign-in, read the protected overview, then report activity and status.
TUI_CLIENT = """
import asyncio, json, sys, time
from uuid import UUID

import psutil
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_runtime.host.frontend.tui.profile.overview_client import read_profile_overview
REFUSALS = (FrontendRefusedError, RefusalError, ProfileReceiptRefusedError)
def emit(**document):
    print(json.dumps(document), flush=True)
def code(error):
    reason = getattr(error, 'reason', None)
    return str(getattr(reason, 'value', reason) or type(error).__name__)
async def main():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.TUI)
    try:
        try:
            await asyncio.to_thread(client.resume_receipt)
            view = await asyncio.to_thread(
                read_profile_overview, client, profile_label='Probe', output_language=OutputLanguage.EN
            )
        except REFUSALS as error:
            emit(event='refused', code=code(error))
            return 2
        emit(event='admitted', sections=len(view.sections))
        deadline = time.monotonic() + float(sys.argv[2])
        while time.monotonic() < deadline:
            try:
                await asyncio.to_thread(client.note_activity)
                status = (await asyncio.to_thread(client.status)).status
            except REFUSALS as error:
                emit(event='refused', code=code(error))
                return 3
            denial = None if status.denial is None else str(status.denial.value)
            emit(event='status', denial=denial, own=status.session_id == client.session_id)
            if denial is not None or status.session_id != client.session_id:
                return 4
            await asyncio.sleep(1)
        return 0
    finally:
        await asyncio.to_thread(client.close)
with composed_profile_persistence_ports():
    sys.exit(asyncio.run(main()))
"""
