cmake_minimum_required(VERSION 4.4)
list(APPEND CMAKE_MESSAGE_CONTEXT desktop)
# The desktop builds and is tested inside the repository build, never in a tree of its own.
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  message(FATAL_ERROR "The desktop is part of the repository build: configure it with cmake --preset <name> "
    "at the repository root and build its targets in build/<name>.")
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
set(desktop_temporary "${CADRUMO_PATH_DESKTOP_TESTING}/temporary")
cadrumo_require_physical_build_member("${desktop_temporary}" "Desktop test temporary directory")
file(MAKE_DIRECTORY "${desktop_temporary}")
list(APPEND desktop_environment
  "TEMP=${desktop_temporary}" "TMP=${desktop_temporary}" "TMPDIR=${desktop_temporary}")
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
set(desktop_host_contracts native_contract)
# The desktop resolves its own build identity (with the manager, installer and interpreter
# hosts it links) before Tauri compiles it; an unchanged fingerprint changes no variable.
cadrumo_identity_command(desktop_identity desktop)
# A desktop image built from the desktop's current fingerprint by the same command is current:
# the fingerprint covers every input, so the Tauri driver would only confirm it.
function(cadrumo_reuse_built output component artifact)
  set(${output} "${CMAKE_COMMAND}" -E chdir "${CADRUMO_SOURCE_ROOT}" ${CADRUMO_HELPER} run --build "${CMAKE_BINARY_DIR}"
    --config "$<CONFIG>" --reuse-built "${component}" "${artifact}" -- PARENT_SCOPE)
endfunction()
if(WIN32)
  # Cargo embeds the generated Windows manifests, including the compatibility
  # claim required by the runtime role's native login observations.
  list(APPEND desktop_host_contracts native_metadata)
endif()
set(CADRUMO_DESKTOP_PACKAGE_ROOT "" CACHE PATH "Existing native package for desktop development")
if(NOT CADRUMO_DESKTOP_PACKAGE_ROOT)
  set(CADRUMO_DESKTOP_PACKAGE_ROOT "${CADRUMO_PATH_STAGE}/$<CONFIG>/app")
endif()
# The host image desktop-host-build links, in Cargo's profile directory for the configuration.
# The platform mapping's application image names this variable; tauri.mjs refuses a build whose
# Cargo binary differs from it.
set(CADRUMO_DESKTOP_HOST_EXECUTABLE
  "${CADRUMO_PATH_DESKTOP_CARGO}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo${CMAKE_EXECUTABLE_SUFFIX}")
set(CADRUMO_DESKTOP_HOST_EXECUTABLE "${CADRUMO_DESKTOP_HOST_EXECUTABLE}" PARENT_SCOPE)
cadrumo_reuse_built(desktop_reuse desktop "${CADRUMO_DESKTOP_HOST_EXECUTABLE}")

# The checkout's shared node_modules tree is an explicit developer prerequisite. A build
# may validate it, but installation and removal belong to the operator outside CMake.
cadrumo_build_step(step_comment desktop-frontend-install GROUP desktop
  SUMMARY "verify the checkout-owned frontend packages match the lockfile")
add_custom_target(desktop-frontend-install
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-install.mjs"
    --check
  WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-frontend-build GROUP desktop
  SUMMARY "build the desktop frontend bundle"
  OUTPUTS "${CADRUMO_PATH_DESKTOP_FRONTEND}")
add_custom_target(desktop-frontend-build
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/frontend-build.mjs" "${CADRUMO_NPM_CLI}"
  DEPENDS desktop-frontend-install
  WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
add_custom_target(clean-desktop-frontend-install
  COMMAND "${CMAKE_COMMAND}" -E echo
    "[cadrumo:clean-desktop-frontend-install] Frontend dependencies are checkout-owned; run just setup-desktop-frontend to replace them."
  VERBATIM)
set(CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS "" CACHE STRING
  "Optional Playwright worker count for desktop-frontend-test")
option(CADRUMO_DESKTOP_FRONTEND_TEST_LAST_FAILED "Rerun only the last failed frontend tests" OFF)
if(NOT CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS STREQUAL ""
    AND NOT CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR "CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS must be a positive integer")
endif()
foreach(action IN ITEMS check test)
  set(desktop_frontend_script_arguments)
  if(action STREQUAL "test")
    if(NOT CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS STREQUAL "")
      list(APPEND desktop_frontend_script_arguments "--workers=${CADRUMO_DESKTOP_FRONTEND_TEST_WORKERS}")
    endif()
    if(CADRUMO_DESKTOP_FRONTEND_TEST_LAST_FAILED)
      list(APPEND desktop_frontend_script_arguments --last-failed)
    endif()
    if(desktop_frontend_script_arguments)
      list(PREPEND desktop_frontend_script_arguments --)
    endif()
  endif()
  cadrumo_build_step(step_comment desktop-frontend-${action} GROUP verification
    SUMMARY "run the frontend's npm ${action} script")
  add_custom_target(desktop-frontend-${action}
    COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} ${desktop_node_path_arguments}
      "${CADRUMO_NODE}" "${CADRUMO_NPM_CLI}" run ${action} ${desktop_frontend_script_arguments}
    WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" VERBATIM)
  add_dependencies(desktop-frontend-${action} desktop-frontend-install)
endforeach()

# Shell inputs generated from their canonical sources: the chrome strings from the
# locale catalogues and the palette from the documentation theme. They are build
# outputs of this binary directory, never written into the source tree, and
# regenerate whenever a source or a generator changes.
set(desktop_generated "${CADRUMO_PATH_DESKTOP_FRONTEND_GENERATED}")
set(desktop_generator "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build run --build "${PROJECT_BINARY_DIR}" --
  "${CADRUMO_DEV_PYTHON}" -B -m)
file(GLOB_RECURSE desktop_chrome_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/locales/*.yml"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo_runtime/_data/locales/*.yml"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo_agent_service/locales/*.yml"
  "${CADRUMO_SOURCE_ROOT}/dev/locales/*.py")
list(FILTER desktop_chrome_inputs EXCLUDE REGEX "/dev/locales/tests/")
list(APPEND desktop_chrome_inputs "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/i18n/render.py"
  "${CADRUMO_SOURCE_ROOT}/dev/_paths.py" "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py"
  # The shell source names the keys; generation refuses one it would not carry.
  "${CMAKE_CURRENT_SOURCE_DIR}/frontend/src")
set(desktop_palette_inputs "${CADRUMO_SOURCE_ROOT}/docs/conf.py" "${CADRUMO_SOURCE_ROOT}/docs/_static/cadrumo-docs.css"
  "${CADRUMO_SOURCE_ROOT}/dev/docs/desktop_palette.py" "${CADRUMO_SOURCE_ROOT}/dev/_paths.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py")
set(desktop_icons_inputs
  "${CADRUMO_PATH_AGENT}/agent-wheel.json" "${CADRUMO_PATH_AGENT}/wheels"
  "${CADRUMO_SOURCE_ROOT}/dev/_paths.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/provider_icon_assets.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/agent.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_paths.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/hashing.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py")
set(desktop_chrome_output chrome-strings.json)
set(desktop_palette_output palette.css)
set(desktop_icons_output provider-icons.json)
set(desktop_chrome_module dev.locales.desktop_chrome)
set(desktop_palette_module dev.docs.desktop_palette)
set(desktop_icons_module dev.packaging.native.provider_icon_assets)
set(desktop_chrome_description "chrome strings from the locale catalogues")
set(desktop_palette_description "palette from the documentation theme")
set(desktop_icons_description "pinned provider marks from the admitted agent wheel")
set(desktop_chrome_arguments --shell-source "${CMAKE_CURRENT_SOURCE_DIR}/frontend/src")
set(desktop_icons_arguments --build "${PROJECT_BINARY_DIR}")
set(desktop_icons_dependencies agent_project)
foreach(generator IN ITEMS chrome palette icons)
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
      --record "${CADRUMO_PATH_DESKTOP_CACHE}/frontend-${generator}-build.json"
      --output "${desktop_generated}/${desktop_${generator}_output}" --inputs-file "${generator_input_file}"
      -- ${desktop_generator} ${desktop_${generator}_module} --output "${desktop_generated}/${desktop_${generator}_output}"
        ${desktop_${generator}_arguments}
    BYPRODUCTS "${desktop_generated}/${desktop_${generator}_output}"
    DEPENDS ${desktop_${generator}_dependencies}
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${step_comment}" VERBATIM)
endforeach()
cadrumo_build_step(step_comment desktop-frontend-generated GROUP desktop
  SUMMARY "every generated shell input"
  OUTPUTS "${desktop_generated}")
add_custom_target(desktop-frontend-generated
  DEPENDS desktop-frontend-chrome desktop-frontend-palette desktop-frontend-icons COMMENT "${step_comment}")
foreach(action IN ITEMS build test)
  add_dependencies(desktop-frontend-${action} desktop-frontend-generated)
endforeach()
cadrumo_build_step(step_comment desktop-frontend-dev GROUP desktop
  SUMMARY "serve the development display from this build's generated inputs until stopped")
add_custom_target(desktop-frontend-dev
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} ${desktop_node_path_arguments}
    "${CADRUMO_NODE}" "${desktop_frontend}/scripts/dev.mjs"
  DEPENDS desktop-frontend-install desktop-frontend-generated
  WORKING_DIRECTORY "${desktop_frontend}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)

include("${CMAKE_CURRENT_LIST_DIR}/../cmake/Docs.cmake")
cadrumo_build_step(step_comment desktop-paths-test GROUP verification
  SUMMARY "test the desktop build path resolution")
add_custom_target(desktop-paths-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment}
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/build-paths.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-configuration-test GROUP verification
  SUMMARY "test the desktop build configuration selection")
add_custom_target(desktop-configuration-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment}
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/configuration.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-host-build GROUP desktop
  SUMMARY "compile the desktop host image around the frontend bundle"
  OUTPUTS "${CADRUMO_DESKTOP_HOST_EXECUTABLE}")
add_custom_target(desktop-host-build
  ${desktop_identity}
  COMMAND ${desktop_reuse} "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
    ${desktop_environment} "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_HOST_EXECUTABLE=${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs"
  DEPENDS desktop-frontend-build
  BYPRODUCTS "${CADRUMO_DESKTOP_HOST_EXECUTABLE}"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
add_dependencies(desktop-host-build ${desktop_host_contracts})

cadrumo_build_step(step_comment desktop-host-prepare GROUP desktop
  SUMMARY "prepare the desktop host project and its icons"
  OUTPUTS "${CADRUMO_PATH_DESKTOP_HOST}" "${CADRUMO_PATH_DESKTOP_ICONS}")
add_custom_target(desktop-host-prepare
  ${desktop_identity}
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}" ${desktop_node_path_arguments}
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" prepare
  DEPENDS desktop-frontend-install
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment desktop-build-test GROUP verification
  SUMMARY "test the desktop build scripts")
add_custom_target(desktop-build-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment}
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/content-build.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/backend-snapshot.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend-clean.test.mjs"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/frontend-install.test.mjs"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
add_dependencies(desktop-host-prepare ${desktop_host_contracts})

# Host tests and lint read the staged documentation only when the package bundles it.
set(desktop_user_docs)
set(desktop_test_user_docs 0)
if(NOT DEFINED CADRUMO_PACKAGE_USER_DOCS OR CADRUMO_PACKAGE_USER_DOCS)
  set(desktop_user_docs user_docs)
  set(desktop_test_user_docs 1)
endif()
set(CADRUMO_DESKTOP_HOST_TEST_FILTER "" CACHE STRING "Optional Rust test-name filter for desktop host tests")
foreach(action IN ITEMS test clippy unit-test unit-clippy)
  set(host_driver_action "${action}")
  set(host_dependencies desktop-frontend-build ${desktop_user_docs})
  set(host_fixture_check)
  if(action STREQUAL "unit-test" OR action STREQUAL "unit-clippy")
    set(host_dependencies desktop-frontend-install)
    if(action STREQUAL "unit-test")
      set(host_driver_action test-unit)
    else()
      set(host_driver_action clippy-backend)
    endif()
    set(host_fixture_check COMMAND "${CADRUMO_DEV_PYTHON}" -B
      "${CMAKE_CURRENT_SOURCE_DIR}/src-tauri/src/shell/sign_in/cli_contract_fixtures.py" --check)
    list(APPEND host_fixture_check COMMAND "${CADRUMO_DEV_PYTHON}" -B
      "${CMAKE_CURRENT_SOURCE_DIR}/src-tauri/src/shell/ledger/relay_contracts.py" --check)
    list(APPEND host_fixture_check COMMAND "${CADRUMO_DEV_PYTHON}" -B
      "${CMAKE_CURRENT_SOURCE_DIR}/src-tauri/src/shell/modelo/relay_contracts.py" --check)
  endif()
  set(host_test_arguments)
  if(action STREQUAL "test" OR action STREQUAL "unit-test")
    set(host_summary "run the desktop host Rust tests")
    if(NOT CADRUMO_DESKTOP_HOST_TEST_FILTER STREQUAL "")
      list(APPEND host_test_arguments "${CADRUMO_DESKTOP_HOST_TEST_FILTER}")
    endif()
  else()
    set(host_summary "lint the desktop host with clippy")
  endif()
  cadrumo_build_step(step_comment desktop-host-${action} GROUP verification SUMMARY "${host_summary}")
  add_custom_target(desktop-host-${action}
    ${host_fixture_check}
    ${desktop_identity}
    COMMAND "${CMAKE_COMMAND}" -E env --unset=CARGO_BUILD_TARGET
      ${desktop_environment} "${desktop_configuration}" ${desktop_node_path_arguments} ${desktop_rust_environment}
      "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
      "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
      "CADRUMO_PACKAGE_USER_DOCS=${desktop_test_user_docs}"
      "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_DESKTOP_TESTING}/storage"
      "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" ${host_driver_action} ${host_test_arguments}
    DEPENDS ${host_dependencies}
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
  add_dependencies(desktop-host-${action} ${desktop_host_contracts})
endforeach()
# The backend-only lint needs the frontend packages but not a frontend build or staged
# documentation. CTest drives the existing target, so its identity, fixture and environment
# steps stay in one place; desktop.fmt and desktop.deny are registered with the other crates.
if(BUILD_TESTING)
  add_test(NAME desktop.clippy
    COMMAND "${CMAKE_COMMAND}" --build "${CMAKE_BINARY_DIR}" --config "$<CONFIG>" --target desktop-host-unit-clippy)
  set_tests_properties(desktop.clippy PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" LABELS rust_quality TIMEOUT 1800)
endif()

cadrumo_build_step(step_comment desktop-run GROUP desktop
  SUMMARY "run the desktop application against the package root")
add_custom_target(desktop-run
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/tauri.mjs" run
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" VERBATIM)

cadrumo_build_step(step_comment desktop-headless-test GROUP verification
  SUMMARY "start the built desktop host headless against the bundle")
add_custom_target(desktop-headless-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
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
# The test host has its own build record (desktop-test-host): the desktop's inputs and identity
# with one more feature. It is opened before the host builds and settled from the host.json
# the build writes, with the image's digest.
cadrumo_identity_command(desktop_test_host_identity desktop-test-host)
set(desktop_test_host_record "${CADRUMO_PATH_DESKTOP_TESTING}/packaged/host.json")
cadrumo_reuse_built(desktop_test_host_reuse desktop-test-host
  "${CADRUMO_PATH_DESKTOP_TESTING}/packaged/cargo/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo${CMAKE_EXECUTABLE_SUFFIX}")
set(desktop_resource_environment)
if(WIN32)
  get_directory_property(desktop_resource_compiler DIRECTORY "${CADRUMO_SOURCE_ROOT}/native"
    DEFINITION CADRUMO_RUST_ENV_CADRUMO_RC_COMPILER)
  set(desktop_resource_environment "CADRUMO_RC_COMPILER=${desktop_resource_compiler}")
endif()
add_custom_target(desktop-packaged-host
  ${desktop_test_host_identity}
  COMMAND ${desktop_test_host_reuse} "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}" ${desktop_resource_environment}
    "${CADRUMO_NODE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged/host.mjs"
  COMMAND "${CMAKE_COMMAND}" -E chdir "${CADRUMO_SOURCE_ROOT}" ${CADRUMO_HELPER} run --build "${CMAKE_BINARY_DIR}"
    -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.build_stamp --build "${CMAKE_BINARY_DIR}"
    --settle-test-host "${desktop_test_host_record}"
  DEPENDS desktop-frontend-build
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
add_dependencies(desktop-packaged-host ${desktop_host_contracts})
cadrumo_build_step(step_comment desktop-packaged-test GROUP verification
  SUMMARY "drive the packaged desktop window end to end (needs an interactive desktop)")
add_custom_target(desktop-packaged-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "CADRUMO_STORAGE_ROOT_VARIABLE=${CADRUMO_STORAGE_ROOT_VARIABLE}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged.test.mjs"
  DEPENDS desktop-packaged-host
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
# The setup acceptance downloads the browser into one throwaway root under the testing
# directory, interrupts and resumes it, and removes the root when it ends.
cadrumo_build_step(step_comment desktop-packaged-setup-test GROUP verification
  SUMMARY "set the browser up through the packaged window in a throwaway root (downloads; needs an interactive desktop)")
add_custom_target(desktop-packaged-setup-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "CADRUMO_STORAGE_ROOT_VARIABLE=${CADRUMO_STORAGE_ROOT_VARIABLE}"
    "CADRUMO_PACKAGED_SETUP=1"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged.test.mjs"
  DEPENDS desktop-packaged-host
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
cadrumo_build_step(step_comment desktop-startup-test GROUP verification
  SUMMARY "verify loading, runtime readiness, workspace handoff and startup cancellation")
add_custom_target(desktop-startup-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment} "${desktop_configuration}"
    "CADRUMO_NATIVE_CONTRACT=${CADRUMO_NATIVE_CONTRACT}"
    "CADRUMO_DESKTOP_PACKAGE_ROOT=${CADRUMO_DESKTOP_PACKAGE_ROOT}"
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/startup.test.mjs"
  DEPENDS desktop-packaged-host
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
# The harness's own frame and assertion logic against a plain Chromium and stand-in pages.
cadrumo_build_step(step_comment desktop-packaged-harness-test GROUP verification
  SUMMARY "test the packaged end-to-end harness against stand-in pages")
add_custom_target(desktop-packaged-harness-test
  COMMAND "${CMAKE_COMMAND}" -E env ${desktop_environment}
    "${CADRUMO_NODE}" --test "${CMAKE_CURRENT_SOURCE_DIR}/tests/packaged-harness.test.mjs"
  WORKING_DIRECTORY "${CMAKE_BINARY_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)

# Target cleanup owns only this action's products; prerequisites keep their
# caches unless the operator explicitly selects their own clean target.
cadrumo_register_clean(TARGET desktop-frontend-build PATHS
  "${CADRUMO_PATH_DESKTOP_FRONTEND}" "${CADRUMO_PATH_DESKTOP_CACHE}/frontend-build.json")
foreach(generator IN ITEMS chrome palette icons)
  cadrumo_register_clean(TARGET desktop-frontend-${generator} PATHS
    "${desktop_generated}/${desktop_${generator}_output}"
    "${CADRUMO_PATH_DESKTOP_CACHE}/frontend-${generator}-build.json")
endforeach()
cadrumo_register_clean(TARGET desktop-frontend-generated DEPENDS
  desktop-frontend-chrome desktop-frontend-palette desktop-frontend-icons)
cadrumo_register_clean(TARGET desktop-host-prepare PATHS
  "${CADRUMO_PATH_DESKTOP_HOST}" "${CADRUMO_PATH_DESKTOP_ICONS}"
  "${CADRUMO_PATH_DESKTOP_CACHE}/icons-build.json")
cadrumo_register_clean(TARGET desktop-host-build PATHS
  "${CADRUMO_DESKTOP_HOST_EXECUTABLE}" "${CADRUMO_PATH_GENERATED}/desktop-$<CONFIG>.json")
