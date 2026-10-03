cmake_minimum_required(VERSION 3.25)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(cadrumo_desktop_preview LANGUAGES NONE)
endif()

find_program(CADRUMO_NPM NAMES npm.cmd npm REQUIRED)
set(desktop_frontend "${CMAKE_CURRENT_SOURCE_DIR}/frontend")
set(desktop_environment "CADRUMO_CMAKE_BINARY_DIR=${CMAKE_BINARY_DIR}")

add_custom_target(desktop-frontend-install
  COMMAND "${CADRUMO_NPM}" ci --no-audit --no-fund
  WORKING_DIRECTORY "${desktop_frontend}" VERBATIM)
foreach(action IN ITEMS build check test)
  add_custom_target(desktop-frontend-${action}
    COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
      "${CADRUMO_NPM}" run ${action}
    WORKING_DIRECTORY "${desktop_frontend}" VERBATIM)
endforeach()

find_program(CADRUMO_NODE NAMES node REQUIRED)
add_custom_target(desktop-host-build
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/host.mjs"
  DEPENDS desktop-frontend-build
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)


add_custom_target(desktop-preview
  COMMAND "${CMAKE_COMMAND}" -E env
    "CADRUMO_DESKTOP_PREVIEW_DATA_DIR=${CMAKE_BINARY_DIR}/desktop/webview"
    "${CMAKE_BINARY_DIR}/cargo/desktop/debug/cadrumo${CMAKE_EXECUTABLE_SUFFIX}"
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" VERBATIM)
