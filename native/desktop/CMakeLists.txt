cmake_minimum_required(VERSION 4.4)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Identity.cmake")
  project(CADRUMO_DESKTOP VERSION "${CADRUMO_ID_VERSION}"
    DESCRIPTION "${CADRUMO_ID_DESCRIPTION}" HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}"
    SPDX_LICENSE "${CADRUMO_ID_LICENSE}" LANGUAGES NONE)
endif()

find_program(CADRUMO_NPM NAMES npm.cmd npm REQUIRED)
set(desktop_frontend "${CMAKE_CURRENT_SOURCE_DIR}/frontend")
set(desktop_environment "CADRUMO_CMAKE_BINARY_DIR=${CMAKE_BINARY_DIR}")
set(CADRUMO_NATIVE_CONTRACT "${CADRUMO_PATH_GENERATED}/contract.json" CACHE FILEPATH "Generated native package contract")
set(CADRUMO_DESKTOP_PACKAGE_ROOT "" CACHE PATH "Existing native package for desktop development")

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
add_custom_target(desktop-paths-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/build-paths.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
add_custom_target(desktop-host-build
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs"
  DEPENDS desktop-frontend-build
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)

foreach(action IN ITEMS test clippy)
  add_custom_target(desktop-host-${action}
    COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
      "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
      "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
      "CADRUMO_LOCAL_STORAGE_ROOT=${CADRUMO_PATH_DESKTOP_TESTING}/storage"
      "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" ${action}
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
endforeach()

add_custom_target(desktop-run
  COMMAND "${CMAKE_COMMAND}" -E env
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_PATH_DESKTOP_CARGO}/debug/cadrumo${CMAKE_EXECUTABLE_SUFFIX}"
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" VERBATIM)

add_custom_target(desktop-headless-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/headless.test.mjs"
  DEPENDS desktop-host-build
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" VERBATIM)
