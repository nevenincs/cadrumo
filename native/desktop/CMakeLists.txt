cmake_minimum_required(VERSION 4.4)
list(APPEND CMAKE_MESSAGE_CONTEXT desktop)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Identity.cmake")
  project(CADRUMO_DESKTOP VERSION "${CADRUMO_ID_VERSION}"
    DESCRIPTION "${CADRUMO_ID_DESCRIPTION}" HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}"
    SPDX_LICENSE "${CADRUMO_ID_LICENSE}" LANGUAGES NONE)
  include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Contract.cmake")
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
set(desktop_server_contract "${CMAKE_CURRENT_SOURCE_DIR}/development-server.json")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${desktop_server_contract}")
file(READ "${desktop_server_contract}" desktop_server)
string(JSON desktop_bind_address GET "${desktop_server}" host)
set(CADRUMO_DESKTOP_BIND_ADDRESS "${desktop_bind_address}" CACHE STRING "Frontend development bind address")
set(desktop_ports "")
foreach(port IN ITEMS devPort previewPort docsPort cataloguePort)
  string(JSON desktop_port GET "${desktop_server}" "${port}")
  if(NOT "${desktop_port}" MATCHES "^[0-9]+$" OR desktop_port LESS 1 OR desktop_port GREATER 65535)
    message(FATAL_ERROR "${port} must be a valid TCP port")
  endif()
  list(APPEND desktop_ports "${desktop_port}")
endforeach()
list(REMOVE_DUPLICATES desktop_ports)
list(LENGTH desktop_ports desktop_port_count)
if(NOT desktop_port_count EQUAL 4)
  message(FATAL_ERROR "Development listeners must have distinct ports")
endif()
# These are not cache options: every build and just dev use the same assignments.
string(JSON CADRUMO_DESKTOP_DEV_PORT GET "${desktop_server}" devPort)
string(JSON CADRUMO_DESKTOP_PREVIEW_PORT GET "${desktop_server}" previewPort)
string(JSON desktop_server SET "${desktop_server}" host "\"${CADRUMO_DESKTOP_BIND_ADDRESS}\"")
file(CONFIGURE OUTPUT "${CADRUMO_PATH_GENERATED}/desktop-server.json" CONTENT "@desktop_server@\n" @ONLY)
set(CADRUMO_NATIVE_CONTRACT "${CADRUMO_PATH_GENERATED}/contract.json" CACHE FILEPATH "Generated native package contract")
set(CADRUMO_DESKTOP_PACKAGE_ROOT "" CACHE PATH "Existing native package for desktop development")
if(NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR AND NOT CADRUMO_DESKTOP_PACKAGE_ROOT)
  set(CADRUMO_DESKTOP_PACKAGE_ROOT "${CADRUMO_PATH_STAGE}/$<CONFIG>/app")
endif()
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
cadrumo_build_step(step_comment desktop-frontend-install GROUP desktop
  SUMMARY "install the frontend packages when the installed tree differs from the lockfile"
  OUTPUTS "${desktop_frontend}/node_modules")
add_custom_target(desktop-frontend-install
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-install.mjs"
    "${CADRUMO_NPM_CLI}" ci --include=dev --no-audit --no-fund
  WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-frontend-build GROUP desktop
  SUMMARY "build the desktop frontend bundle"
  OUTPUTS "${CADRUMO_PATH_DESKTOP_FRONTEND}")
add_custom_target(desktop-frontend-build
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-build.mjs" "${CADRUMO_NPM_CLI}"
  DEPENDS desktop-frontend-install
  WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
# This intentionally cleans the one shared install used by every binary directory.
add_custom_target(clean-desktop-frontend-install
  COMMAND "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-install.mjs" clean
  WORKING_DIRECTORY "${desktop_frontend}" VERBATIM)
foreach(action IN ITEMS check test)
  cadrumo_build_step(step_comment desktop-frontend-${action} GROUP verification
    SUMMARY "run the frontend's npm ${action} script")
  add_custom_target(desktop-frontend-${action}
    COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" ${desktop_node_path_arguments}
      "${CADRUMO_NODE}" "${CADRUMO_NPM_CLI}" run ${action}
    WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
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
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/locales/*.yml"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo_agent_service/locales/*.yml"
  "${CADRUMO_SOURCE_ROOT}/dev/locales/*.py")
list(FILTER desktop_chrome_inputs EXCLUDE REGEX "/dev/locales/tests/")
list(APPEND desktop_chrome_inputs "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/i18n/render.py"
  "${CADRUMO_SOURCE_ROOT}/dev/_paths.py")
set(desktop_palette_inputs "${CADRUMO_SOURCE_ROOT}/docs/conf.py" "${CADRUMO_SOURCE_ROOT}/docs/_static/cadrumo-docs.css"
  "${CADRUMO_SOURCE_ROOT}/dev/docs/desktop_palette.py" "${CADRUMO_SOURCE_ROOT}/dev/_paths.py")
set(desktop_chrome_output chrome-strings.json)
set(desktop_palette_output palette.css)
set(desktop_chrome_module dev.locales.desktop_chrome)
set(desktop_palette_module dev.docs.desktop_palette)
set(desktop_chrome_description "chrome strings from the locale catalogues")
set(desktop_palette_description "palette from the documentation theme")
foreach(generator IN ITEMS chrome palette)
  set(generator_input_json "[]")
  set(generator_inputs ${desktop_${generator}_inputs}
    "${CADRUMO_DEV_PYTHON}" "${CADRUMO_SOURCE_ROOT}/uv.lock"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/atomic_write.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/external_constants.py")
  foreach(input IN LISTS generator_inputs)
    string(JSON input_index LENGTH "${generator_input_json}")
    string(JSON generator_input_json SET "${generator_input_json}" ${input_index} "\"${input}\"")
  endforeach()
  set(generator_input_file "${CADRUMO_PATH_GENERATED}/desktop-${generator}-inputs.json")
  file(CONFIGURE OUTPUT "${generator_input_file}" CONTENT "@generator_input_json@\n" @ONLY)
  cadrumo_build_step(step_comment desktop-frontend-${generator} GROUP desktop
    SUMMARY "generate the shell ${desktop_${generator}_description}"
    OUTPUTS "${desktop_generated}/${desktop_${generator}_output}")
  add_custom_target(desktop-frontend-${generator}
    COMMAND "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/content-build.mjs"
      --record "${CADRUMO_PATH_DESKTOP_CACHE}/${generator}-build.json"
      --output "${desktop_generated}/${desktop_${generator}_output}" --inputs-file "${generator_input_file}"
      -- ${desktop_generator} ${desktop_${generator}_module} --output "${desktop_generated}/${desktop_${generator}_output}"
    BYPRODUCTS "${desktop_generated}/${desktop_${generator}_output}"
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${step_comment}" VERBATIM)
endforeach()
cadrumo_build_step(step_comment desktop-frontend-generated GROUP desktop
  SUMMARY "every generated shell input"
  OUTPUTS "${desktop_generated}")
add_custom_target(desktop-frontend-generated
  DEPENDS desktop-frontend-chrome desktop-frontend-palette COMMENT "${step_comment}")
foreach(action IN ITEMS build test)
  add_dependencies(desktop-frontend-${action} desktop-frontend-generated)
endforeach()

include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Docs.cmake")
cadrumo_build_step(step_comment desktop-paths-test GROUP verification
  SUMMARY "test the desktop build path resolution")
add_custom_target(desktop-paths-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/build-paths.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-configuration-test GROUP verification
  SUMMARY "test the desktop build configuration selection")
add_custom_target(desktop-configuration-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/configuration.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-host-build GROUP desktop
  SUMMARY "compile the desktop host image around the frontend bundle"
  OUTPUTS "${CADRUMO_DESKTOP_HOST_EXECUTABLE}")
add_custom_target(desktop-host-build
  COMMAND "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
    "${desktop_environment}" "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_HOST_EXECUTABLE=${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs"
  DEPENDS desktop-frontend-build
  BYPRODUCTS "${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
if(TARGET native_contract)
  # Inside the source build the contract is a build output, not a configured input.
  add_dependencies(desktop-host-build native_contract)
endif()

cadrumo_build_step(step_comment desktop-host-prepare GROUP desktop
  SUMMARY "prepare the desktop host project and its icons"
  OUTPUTS "${CADRUMO_PATH_DESKTOP_HOST}" "${CADRUMO_PATH_DESKTOP_ICONS}")
add_custom_target(desktop-host-prepare
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}" ${desktop_node_path_arguments}
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" prepare
  DEPENDS desktop-frontend-install
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-build-test GROUP verification
  SUMMARY "test the desktop build scripts")
add_custom_target(desktop-build-test
  COMMAND "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/content-build.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/backend-snapshot.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend-clean.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend-install.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
if(TARGET native_contract)
  add_dependencies(desktop-host-prepare native_contract)
endif()

# Host tests and lint read the staged documentation only when the package bundles it.
set(desktop_user_docs)
if(NOT DEFINED CADRUMO_PACKAGE_USER_DOCS OR CADRUMO_PACKAGE_USER_DOCS)
  set(desktop_user_docs user_docs)
endif()
foreach(action IN ITEMS test clippy)
  if(action STREQUAL "test")
    set(host_summary "run the desktop host Rust tests")
  else()
    set(host_summary "lint the desktop host with clippy")
  endif()
  cadrumo_build_step(step_comment desktop-host-${action} GROUP verification SUMMARY "${host_summary}")
  add_custom_target(desktop-host-${action}
    COMMAND "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
      "${desktop_environment}" "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
      "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
      "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
      "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_DESKTOP_TESTING}/storage"
      "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" ${action}
    DEPENDS desktop-frontend-build ${desktop_user_docs}
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
  if(TARGET native_contract)
    add_dependencies(desktop-host-${action} native_contract)
  endif()
endforeach()

cadrumo_build_step(step_comment desktop-run GROUP desktop
  SUMMARY "run the desktop application against the package root")
add_custom_target(desktop-run
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" run
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" VERBATIM)

cadrumo_build_step(step_comment desktop-headless-test GROUP verification
  SUMMARY "start the built desktop host headless against the bundle")
add_custom_target(desktop-headless-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/headless.test.mjs"
  DEPENDS desktop-host-build
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" VERBATIM)

# The packaged end-to-end test drives the window over the WebView2 DevTools protocol, so
# it needs an interactive desktop session. Its host carries the webview2-remote-debugging
# feature and is built apart, into the desktop testing directory: it is never the image
# desktop-host-build declares, and nothing stages or packages it.
cadrumo_build_step(step_comment desktop-packaged-host GROUP verification
  SUMMARY "compile the remote-debugging desktop host for packaged end-to-end tests (never shipped)"
  OUTPUTS "${CADRUMO_PATH_DESKTOP_TESTING}")
add_custom_target(desktop-packaged-host
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged/host.mjs"
  DEPENDS desktop-frontend-build
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
if(TARGET native_contract)
  add_dependencies(desktop-packaged-host native_contract)
endif()
cadrumo_build_step(step_comment desktop-packaged-test GROUP verification
  SUMMARY "drive the packaged desktop window end to end (needs an interactive desktop)")
add_custom_target(desktop-packaged-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}" "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "CADRUMO_STORAGE_ROOT_VARIABLE=${CADRUMO_STORAGE_ROOT_VARIABLE}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged.test.mjs"
  DEPENDS desktop-packaged-host
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
# The harness's own frame and assertion logic against a plain Chromium and stand-in pages.
cadrumo_build_step(step_comment desktop-packaged-harness-test GROUP verification
  SUMMARY "test the packaged end-to-end harness against stand-in pages")
add_custom_target(desktop-packaged-harness-test
  COMMAND "${CMAKE_COMMAND}" -E env "${desktop_environment}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged-harness.test.mjs"
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)

# Target cleanup owns only this action's products; prerequisites keep their
# caches unless the operator explicitly selects their own clean target.
cadrumo_register_clean(TARGET desktop-frontend-build PATHS
  "${CADRUMO_PATH_DESKTOP_FRONTEND}" "${CADRUMO_PATH_DESKTOP_CACHE}/frontend-build.json")
foreach(generator IN ITEMS chrome palette)
  cadrumo_register_clean(TARGET desktop-frontend-${generator} PATHS
    "${desktop_generated}/${desktop_${generator}_output}"
    "${CADRUMO_PATH_DESKTOP_CACHE}/${generator}-build.json")
endforeach()
cadrumo_register_clean(TARGET desktop-frontend-generated DEPENDS
  desktop-frontend-chrome desktop-frontend-palette)
cadrumo_register_clean(TARGET desktop-host-prepare PATHS
  "${CADRUMO_PATH_DESKTOP_HOST}" "${CADRUMO_PATH_DESKTOP_ICONS}"
  "${CADRUMO_PATH_DESKTOP_CACHE}/icons-build.json")
cadrumo_register_clean(TARGET desktop-host-build PATHS
  "${CADRUMO_DESKTOP_HOST_EXECUTABLE}" "${CADRUMO_PATH_GENERATED}/desktop-$<CONFIG>.json")
