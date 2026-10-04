"""Canonical Google contract map contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleFolderSetProjection,
    GoogleFolderSetRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)

GOOGLE_REQUEST_OPERATIONS: dict[type[BaseModel], tuple[str, type[BaseModel]]] = {
    GoogleFolderSetRequest: (GOOGLE_FOLDER_SET_OPERATION_DEFINITION_ID, GoogleFolderSetProjection),
    GoogleFolderViewRequest: (GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, GoogleFolderViewProjection),
    GoogleLoginRequest: (GOOGLE_LOGIN_OPERATION_DEFINITION_ID, GoogleLoginProjection),
    GoogleLogoutRequest: (GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, GoogleLogoutProjection),
    GoogleProbeRequest: (GOOGLE_PROBE_OPERATION_DEFINITION_ID, GoogleProbeProjection),
    GoogleRegisterRequest: (GOOGLE_REGISTER_OPERATION_DEFINITION_ID, GoogleRegisterProjection),
    GoogleStatusRequest: (GOOGLE_STATUS_OPERATION_DEFINITION_ID, GoogleStatusProjection),
}
