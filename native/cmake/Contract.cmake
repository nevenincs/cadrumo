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
  "${CADRUMO_SOURCE_ROOT}/native/llamacpp-pins.json" "${CADRUMO_SOURCE_ROOT}/dev/env/llamacpp_pins.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/application_environment.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_compile.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_declaration_primitives.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_root.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_models.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_declaration_constants.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_profiles.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_components.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_launch_vectors.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_path.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/environment_reference.py"
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
# The manager strings are the contract's one projection of the locale tooling, whose
# import closure (and the authority it loads) is far wider than the contract's own. They
# are their own discovering action: an edit in that closure reruns only the projection,
# and an unchanged projection leaves the contract and everything compiled from it current.
cadrumo_cached_command(manager_strings_command native_manager_strings SHARED DISCOVER
  INPUTS "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/generate.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cached_command.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/pyproject.toml" "${CADRUMO_SOURCE_ROOT}/uv.lock" "${CADRUMO_DEV_PYTHON}"
    "${CADRUMO_BUILD_HELPER}"
  OUTPUTS "${CONTRACT_DIR}/manager-chrome.json")
cadrumo_build_step(manager_strings_comment native_manager_strings GROUP contract
  SUMMARY "project the native manager strings from the locale catalogues"
  OUTPUTS "${CONTRACT_DIR}/manager-chrome.json")
add_custom_target(native_manager_strings
  COMMAND ${manager_strings_command} ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.generate "${CONTRACT_DIR}" --project-manager-strings
  BYPRODUCTS "${CONTRACT_DIR}/manager-chrome.json"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${manager_strings_comment}" VERBATIM)
cadrumo_cached_command(contract_command native_contract SHARED DISCOVER
  INPUTS ${contract_inputs} "${CONTRACT_DIR}/manager-chrome.json"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/generate.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_directory.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/storage_vectors.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/transport_contract.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/operational_settings.py"
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
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cargo_command.py"
  OUTPUTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json"
    "${CONTRACT_DIR}/contract_vectors.rs" "${CONTRACT_DIR}/operational-settings.ts")
cadrumo_build_step(contract_comment native_contract GROUP contract
  SUMMARY "generate the native package contract for Rust, C and the assembler"
  OUTPUTS "${CONTRACT_DIR}/contract.json" "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h")
add_custom_target(native_contract
  COMMAND ${contract_command} ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.generate "${CONTRACT_DIR}"
    --channel "${CADRUMO_ID_CHANNEL}" --target "${CADRUMO_TARGET}" --manager-strings "${CONTRACT_DIR}/manager-chrome.json"
  BYPRODUCTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json"
    "${CONTRACT_DIR}/contract_vectors.rs" "${CONTRACT_DIR}/operational-settings.ts"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${contract_comment}" VERBATIM)
add_dependencies(native_contract native_manager_strings)
# The contract no package embeds: the same projection with no package-fixed value bound, so the
# desktop host's unit tests and lints build where no publisher provisioning exists. Its directory
# also holds the outputs that carry no build identity, which the host's build scripts read beside
# the contract, so those targets need neither the package contract nor the interpreter metadata.
set(CADRUMO_UNPROVISIONED_CONTRACT_DIR "${CONTRACT_DIR}/unprovisioned" CACHE INTERNAL
  "Generated native contract without package provisioning, for the host unit and lint actions")
set(unprovisioned_contract_outputs "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract.rs"
  "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract.h" "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract.json"
  "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract_vectors.rs"
  "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/operational-settings.ts")
set(unstamped_metadata_outputs "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/build_layout.h")
if(CADRUMO_TARGET MATCHES "^windows-")
  foreach(image IN ITEMS process desktop)
    foreach(build_kind IN ITEMS release development)
      list(APPEND unstamped_metadata_outputs "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/${image}-${build_kind}.manifest")
    endforeach()
  endforeach()
endif()
cadrumo_cached_command(unstamped_metadata_command native_unstamped_metadata SHARED DISCOVER
  INPUTS ${platform_contract_inputs} "${CADRUMO_SOURCE_ROOT}/native/package-layout.json"
    "${CADRUMO_SOURCE_ROOT}/native/interpreter/windows/host.manifest"
    "${CADRUMO_SOURCE_ROOT}/native/desktop/src-tauri/windows/desktop.manifest"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/metadata.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/identity.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/platforms/windows.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/platforms/linux.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/platforms/macos.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/product_identity.py"
    "${CADRUMO_SOURCE_ROOT}/pyproject.toml" "${CADRUMO_SOURCE_ROOT}/uv.lock" "${CADRUMO_DEV_PYTHON}"
    "${CADRUMO_BUILD_HELPER}"
  OUTPUTS ${unstamped_metadata_outputs})
cadrumo_build_step(unstamped_metadata_comment native_unstamped_metadata GROUP contract
  SUMMARY "generate the layout header and manifests the unprovisioned contract's hosts compile beside it"
  OUTPUTS ${unstamped_metadata_outputs})
add_custom_target(native_unstamped_metadata
  COMMAND ${unstamped_metadata_command} ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.metadata "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}" --unstamped
    --channel "${CADRUMO_CHANNEL}" --target "${CADRUMO_TARGET}"
  BYPRODUCTS ${unstamped_metadata_outputs}
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${unstamped_metadata_comment}" VERBATIM)
cadrumo_cached_command(unprovisioned_contract_command native_contract_unprovisioned SHARED DISCOVER
  INPUTS ${contract_inputs} "${CONTRACT_DIR}/manager-chrome.json"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/generate.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/storage_vectors.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/transport_contract.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/operational_settings.py"
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
  OUTPUTS ${unprovisioned_contract_outputs})
cadrumo_build_step(unprovisioned_contract_comment native_contract_unprovisioned GROUP contract
  SUMMARY "generate the unprovisioned native contract the desktop host's unit tests and lints compile"
  OUTPUTS "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract.json" "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}/contract.rs")
add_custom_target(native_contract_unprovisioned
  COMMAND ${unprovisioned_contract_command} ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.generate "${CADRUMO_UNPROVISIONED_CONTRACT_DIR}" --unprovisioned
    --channel "${CADRUMO_ID_CHANNEL}" --target "${CADRUMO_TARGET}" --manager-strings "${CONTRACT_DIR}/manager-chrome.json"
  BYPRODUCTS ${unprovisioned_contract_outputs}
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${unprovisioned_contract_comment}" VERBATIM)
add_dependencies(native_contract_unprovisioned native_manager_strings native_unstamped_metadata)
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
# A target that builds a component's staged images also opens its build record; a target that
# only tests, lints or generates passes IDENTITY_ONLY, so the record keeps describing the bytes
# the last stage of that component holds.
function(cadrumo_identity_command output)
  cmake_parse_arguments(PARSE_ARGV 1 IDENTITY "IDENTITY_ONLY" "" "")
  # One process: the resolution writes only generated/ files and needs no wrapped environment.
  set(command "${CMAKE_COMMAND}" -E chdir "${CADRUMO_SOURCE_ROOT}"
    "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.build_stamp --build "${CMAKE_BINARY_DIR}" --config "$<CONFIG>")
  if(IDENTITY_IDENTITY_ONLY)
    list(APPEND command --identity-only)
  endif()
  foreach(component IN LISTS IDENTITY_UNPARSED_ARGUMENTS)
    list(APPEND command --component "${component}")
  endforeach()
  set(${output} COMMAND ${command} PARENT_SCOPE)
endfunction()
