# Native contract producer for the full application and its desktop.
include_guard(GLOBAL)
set(CONTRACT_DIR "${CADRUMO_PATH_GENERATED}")
set(CADRUMO_BUILD_HELPER "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py")
set(CADRUMO_HELPER "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build)
set(platform_contract_name "${CADRUMO_TARGET}")
if(platform_contract_name STREQUAL "windows-x86-64")
  set(platform_contract_name windows-x64)
endif()
set(platform_contract_inputs "${CADRUMO_SOURCE_ROOT}/native/platforms/${platform_contract_name}.json")
set(contract_inputs "${CADRUMO_SOURCE_ROOT}/native/package-layout.json"
  "${CADRUMO_SOURCE_ROOT}/native/application-environment.toml" ${platform_contract_inputs}
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/application_environment.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/google_oauth.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/config_google.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/config_google_client.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/linux_desktop_runtime.py")
if(CADRUMO_TARGET MATCHES "^linux-")
  execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
    "from dev.packaging.native.linux_desktop_runtime import DEPENDENCY_INPUTS; print(';'.join(DEPENDENCY_INPUTS))"
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" OUTPUT_VARIABLE desktop_dependency_inputs
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  foreach(input IN LISTS desktop_dependency_inputs)
    list(APPEND contract_inputs "${CADRUMO_SOURCE_ROOT}/${input}")
  endforeach()
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${contract_inputs})
include("${CMAKE_CURRENT_LIST_DIR}/CachedCommand.cmake")
file(GLOB manager_locale_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/dev/locales/*.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/locales/*/common.yml")
cadrumo_cached_command(contract_command native_contract SHARED
  INPUTS ${contract_inputs} ${manager_locale_inputs} "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/generate.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/storage_vectors.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/transport_contract.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/identity.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/runtime_exit_reasons.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/runtime_wheelhouse_contract.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/external_constants.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/connection_transport.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/product_identity.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo_client/contracts/contracts.py"
    "${CONTRACT_DIR}/identity.json" "${CADRUMO_SOURCE_ROOT}/pyproject.toml"
    "${CADRUMO_SOURCE_ROOT}/uv.lock" "${CADRUMO_DEV_PYTHON}"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version" "${CADRUMO_SOURCE_ROOT}/.python-version"
    "${CADRUMO_BUILD_HELPER}"
  OUTPUTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json")
cadrumo_build_step(contract_comment native_contract GROUP contract
  SUMMARY "generate the native package contract for Rust, C and the assembler"
  OUTPUTS "${CONTRACT_DIR}/contract.json" "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h")
add_custom_target(native_contract
  COMMAND ${contract_command} ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.generate "${CONTRACT_DIR}"
    --channel "${CADRUMO_ID_CHANNEL}" --target "${CADRUMO_TARGET}"
  BYPRODUCTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${contract_comment}" VERBATIM)
# Each native component resolves its own build identity just before it compiles
# (dev/packaging/native/build_stamp.py): a content fingerprint of its inputs keys the
# identity, so an unchanged component keeps its number and its generated identity file,
# and nothing that embeds it rebuilds. The registry persists in the generated directory;
# no clean target removes it. Frozen cache values reach every allocation through this file.
set(CADRUMO_BUILD_STAMP "${CONTRACT_DIR}/build-stamp.json")
# The compile steps read component-identity/<component>.json; build-identity/ holds the build
# records for readers outside the build (dev/packaging/native/build_stamp.py, read_record).
set(CADRUMO_BUILD_IDENTITY_DIR "${CONTRACT_DIR}/component-identity")
# The component fingerprints read each target's effective compile and link settings from the
# CMake file API reply this query requests at every generate.
file(CONFIGURE OUTPUT "${CMAKE_BINARY_DIR}/.cmake/api/v1/query/client-cadrumo/query.json"
  CONTENT "{\"requests\":[{\"kind\":\"codemodel\",\"version\":2}]}\n" @ONLY)
string(JSON build_freeze SET "{}" number "\"${CADRUMO_BUILD_NUMBER}\"")
string(JSON build_freeze SET "${build_freeze}" id "\"${CADRUMO_BUILD_ID}\"")
string(JSON build_freeze SET "${build_freeze}" date "\"${CADRUMO_BUILD_DATE}\"")
file(CONFIGURE OUTPUT "${CONTRACT_DIR}/build-freeze.json" CONTENT "@build_freeze@\n" @ONLY)
# Prefix a target's commands with this to publish component-identity/<Config>/<component>.json first.
function(cadrumo_identity_command output)
  set(command "${CMAKE_COMMAND}" -E chdir "${CADRUMO_SOURCE_ROOT}" ${CADRUMO_HELPER} run --build "${CMAKE_BINARY_DIR}"
    -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.build_stamp --build "${CMAKE_BINARY_DIR}" --config "$<CONFIG>")
  foreach(component IN LISTS ARGN)
    list(APPEND command --component "${component}")
  endforeach()
  set(${output} COMMAND ${command} PARENT_SCOPE)
endfunction()
