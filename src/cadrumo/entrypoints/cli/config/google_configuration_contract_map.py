"""Canonical Google contract map contracts."""

from __future__ import annotations

from pydantic import BaseModel

from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_FOLDER_ORGANIZE_OPERATION_DEFINITION_ID,
    GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID,
    GOOGLE_LOGIN_OPERATION_DEFINITION_ID,
    GOOGLE_LOGOUT_OPERATION_DEFINITION_ID,
    GOOGLE_PROBE_OPERATION_DEFINITION_ID,
    GOOGLE_STATUS_OPERATION_DEFINITION_ID,
    GoogleFolderOrganizeRequest,
    GoogleFolderViewProjection,
    GoogleFolderViewRequest,
    GoogleLoginProjection,
    GoogleLoginRequest,
    GoogleLogoutProjection,
    GoogleLogoutRequest,
    GoogleProbeProjection,
    GoogleProbeRequest,
    GoogleStatusProjection,
    GoogleStatusRequest,
)

GOOGLE_REQUEST_OPERATIONS: dict[type[BaseModel], tuple[str, type[BaseModel]]] = {
    GoogleFolderOrganizeRequest: (GOOGLE_FOLDER_ORGANIZE_OPERATION_DEFINITION_ID, GoogleFolderViewProjection),
    GoogleFolderViewRequest: (GOOGLE_FOLDER_VIEW_OPERATION_DEFINITION_ID, GoogleFolderViewProjection),
    GoogleLoginRequest: (GOOGLE_LOGIN_OPERATION_DEFINITION_ID, GoogleLoginProjection),
    GoogleLogoutRequest: (GOOGLE_LOGOUT_OPERATION_DEFINITION_ID, GoogleLogoutProjection),
    GoogleProbeRequest: (GOOGLE_PROBE_OPERATION_DEFINITION_ID, GoogleProbeProjection),
    GoogleStatusRequest: (GOOGLE_STATUS_OPERATION_DEFINITION_ID, GoogleStatusProjection),
}
