# Shared native contract producer for the full application and standalone desktop.
include_guard(GLOBAL)
set(CONTRACT_DIR "${CADRUMO_PATH_GENERATED}")
set(CADRUMO_BUILD_HELPER "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py")
set(CADRUMO_HELPER "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build)
set(platform_contract_name "${CADRUMO_TARGET}")
if(platform_contract_name STREQUAL "windows-x86-64")
  set(platform_contract_name windows-x64)
endif()
set(platform_contract_inputs "${CADRUMO_SOURCE_ROOT}/native/platforms/${platform_contract_name}.json")
set(contract_inputs "${CADRUMO_SOURCE_ROOT}/native/package-layout.json" ${platform_contract_inputs}
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${contract_inputs})
file(GLOB settings_inputs CONFIGURE_DEPENDS "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/config*.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/storage*.py" "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/product_identity.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/logging.py")
include("${CMAKE_CURRENT_LIST_DIR}/CachedCommand.cmake")
file(GLOB manager_locale_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/dev/locales/*.py"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/locales/*/common.yml")
cadrumo_cached_command(contract_command native_contract SHARED
  INPUTS ${settings_inputs} ${contract_inputs} ${manager_locale_inputs} "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/generate.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/stable_output.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/storage_vectors.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/identity.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/runtime_exit_reasons.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/runtime_wheelhouse_contract.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/external_constants.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/toml.py"
    "${CADRUMO_SOURCE_ROOT}/src/cadrumo/application/runtime/contracts.py"
    "${CONTRACT_DIR}/identity.json" "${CADRUMO_SOURCE_ROOT}/pyproject.toml"
    "${CADRUMO_SOURCE_ROOT}/uv.lock" "${CADRUMO_DEV_PYTHON}"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version" "${CADRUMO_SOURCE_ROOT}/.python-version"
    "${CADRUMO_BUILD_HELPER}"
  OUTPUTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json")
add_custom_target(native_contract
  COMMAND ${contract_command} ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B
    -m dev.packaging.native.generate "${CONTRACT_DIR}"
    --channel "${CADRUMO_ID_CHANNEL}" --target "${CADRUMO_TARGET}"
  BYPRODUCTS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h" "${CONTRACT_DIR}/contract.json"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
