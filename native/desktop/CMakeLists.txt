cmake_minimum_required(VERSION 4.4)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Identity.cmake")
  project(CADRUMO_DESKTOP VERSION "${CADRUMO_ID_VERSION}"
    DESCRIPTION "${CADRUMO_ID_DESCRIPTION}" HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}"
    SPDX_LICENSE "${CADRUMO_ID_LICENSE}" LANGUAGES NONE)
endif()
if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "Desktop build configuration" FORCE)
endif()

find_program(CADRUMO_NPM NAMES npm.cmd npm REQUIRED)
find_program(CADRUMO_NODE NAMES node REQUIRED)
set(desktop_frontend "${CMAKE_CURRENT_SOURCE_DIR}/frontend")
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/DesktopTools.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/DesktopRust.cmake")
cadrumo_desktop_rust_environment(desktop_rust_environment)
set(desktop_environment "CADRUMO_CMAKE_BINARY_DIR=${CMAKE_BINARY_DIR}")
set(desktop_configuration "CADRUMO_BUILD_CONFIG=$<CONFIG>")
set(CADRUMO_DESKTOP_BIND_ADDRESS "0.0.0.0" CACHE STRING "Frontend development bind address")
set(CADRUMO_DESKTOP_DEV_PORT 1420 CACHE STRING "Frontend development port")
set(CADRUMO_DESKTOP_PREVIEW_PORT 1421 CACHE STRING "Frontend asset server port")
foreach(port IN ITEMS CADRUMO_DESKTOP_DEV_PORT CADRUMO_DESKTOP_PREVIEW_PORT)
  if(NOT "${${port}}" MATCHES "^[0-9]+$" OR ${${port}} LESS 1 OR ${${port}} GREATER 65535)
    message(FATAL_ERROR "${port} must be a valid TCP port")
  endif()
endforeach()
set(desktop_server "{}")
string(JSON desktop_server SET "${desktop_server}" host "\"${CADRUMO_DESKTOP_BIND_ADDRESS}\"")
string(JSON desktop_server SET "${desktop_server}" devPort ${CADRUMO_DESKTOP_DEV_PORT})
string(JSON desktop_server SET "${desktop_server}" previewPort ${CADRUMO_DESKTOP_PREVIEW_PORT})
file(CONFIGURE OUTPUT "${CADRUMO_PATH_GENERATED}/desktop-server.json" CONTENT "@desktop_server@\n" @ONLY)
set(CADRUMO_NATIVE_CONTRACT "${CADRUMO_PATH_GENERATED}/contract.json" CACHE FILEPATH "Generated native package contract")
set(CADRUMO_DESKTOP_PACKAGE_ROOT "" CACHE PATH "Existing native package for desktop development")
if(NOT DEFINED CADRUMO_STORAGE_ROOT_VARIABLE)
  # The source build reads this from the storage declaration; the standalone project reads it the same way.
  execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
    "from cadrumo.core.storage_environment import STORAGE_ROOT; print(STORAGE_ROOT.variable)"
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" OUTPUT_VARIABLE CADRUMO_STORAGE_ROOT_VARIABLE
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
endif()
# The host image desktop-host-build links, in Cargo's profile directory for the configuration.
# The platform mapping's application image names this variable; tauri.mjs refuses a build whose
# Cargo binary differs from it.
set(CADRUMO_DESKTOP_HOST_EXECUTABLE
  "${CADRUMO_PATH_DESKTOP_CARGO}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo${CMAKE_EXECUTABLE_SUFFIX}")
if(NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(CADRUMO_DESKTOP_HOST_EXECUTABLE "${CADRUMO_DESKTOP_HOST_EXECUTABLE}" PARENT_SCOPE)
endif()

# Every binary directory shares the one node_modules, and a clean install deletes it under
# whatever runs from it. The script runs the install only when the installed tree differs
# from the lockfile.
add_custom_target(desktop-frontend-install
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-install.mjs"
    "${CADRUMO_NPM_CLI}" ci --include=dev --no-audit --no-fund
  WORKING_DIRECTORY "${desktop_frontend}" VERBATIM)
foreach(action IN ITEMS build check test)
  add_custom_target(desktop-frontend-${action}
    COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" ${desktop_node_path_arguments}
      "${CADRUMO_NODE}" "${CADRUMO_NPM_CLI}" run ${action}
    WORKING_DIRECTORY "${desktop_frontend}" VERBATIM)
  add_dependencies(desktop-frontend-${action} desktop-frontend-install)
endforeach()

# Shell inputs generated from their canonical sources: the chrome strings from the
# locale catalogues and the palette from the documentation theme. They are build
# outputs of this binary directory, never written into the source tree, and
# regenerate whenever a source or a generator changes.
set(desktop_generated "${CADRUMO_PATH_DESKTOP_FRONTEND_GENERATED}")
set(desktop_generator "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build run --
  "${CADRUMO_DEV_PYTHON}" -B -m)
file(GLOB_RECURSE desktop_chrome_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/locales/*.yml" "${CADRUMO_SOURCE_ROOT}/dev/locales/*.py")
list(FILTER desktop_chrome_inputs EXCLUDE REGEX "/dev/locales/tests/")
add_custom_command(OUTPUT "${desktop_generated}/chrome-strings.json"
  COMMAND ${desktop_generator} dev.locales.desktop_chrome --output "${desktop_generated}/chrome-strings.json"
  DEPENDS ${desktop_chrome_inputs} "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/i18n/render.py"
    "${CADRUMO_SOURCE_ROOT}/dev/_paths.py"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
add_custom_command(OUTPUT "${desktop_generated}/palette.css"
  COMMAND ${desktop_generator} dev.docs.desktop_palette --output "${desktop_generated}/palette.css"
  DEPENDS "${CADRUMO_SOURCE_ROOT}/docs/conf.py" "${CADRUMO_SOURCE_ROOT}/docs/_static/cadrumo-docs.css"
    "${CADRUMO_SOURCE_ROOT}/dev/docs/desktop_palette.py" "${CADRUMO_SOURCE_ROOT}/dev/_paths.py"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
add_custom_target(desktop-frontend-generated
  DEPENDS "${desktop_generated}/chrome-strings.json" "${desktop_generated}/palette.css")
foreach(action IN ITEMS build test)
  add_dependencies(desktop-frontend-${action} desktop-frontend-generated)
endforeach()

include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Docs.cmake")
add_custom_target(desktop-paths-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/build-paths.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
add_custom_target(desktop-configuration-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/configuration.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
add_custom_target(desktop-host-build
  COMMAND "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
    "${desktop_environment}" "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_HOST_EXECUTABLE=${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs"
  DEPENDS desktop-frontend-build user_docs
  BYPRODUCTS "${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
if(TARGET native_contract)
  # Inside the source build the contract is a build output, not a configured input.
  add_dependencies(desktop-host-build native_contract)
endif()

foreach(action IN ITEMS test clippy)
  add_custom_target(desktop-host-${action}
    COMMAND "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
      "${desktop_environment}" "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
      "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
      "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
      "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_DESKTOP_TESTING}/storage"
      "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" ${action}
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" VERBATIM)
endforeach()

add_custom_target(desktop-run
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" run
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" VERBATIM)

add_custom_target(desktop-headless-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/headless.test.mjs"
  DEPENDS desktop-host-build
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" VERBATIM)

# The packaged end-to-end test drives the window over the WebView2 DevTools protocol, so
# it needs an interactive desktop session. Its host carries the webview2-remote-debugging
# feature and is built apart, into the desktop testing directory: it is never the image
# desktop-host-build declares, and nothing stages or packages it.
add_custom_target(desktop-packaged-host
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged/host.mjs"
  DEPENDS desktop-frontend-build
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
if(TARGET native_contract)
  add_dependencies(desktop-packaged-host native_contract)
endif()
add_custom_target(desktop-packaged-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "CADRUMO_STORAGE_ROOT_VARIABLE=${CADRUMO_STORAGE_ROOT_VARIABLE}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged.test.mjs"
  DEPENDS desktop-packaged-host
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" USES_TERMINAL VERBATIM)
# The harness's own frame and assertion logic against a plain Chromium and stand-in pages.
add_custom_target(desktop-packaged-harness-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged-harness.test.mjs"
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" USES_TERMINAL VERBATIM)
