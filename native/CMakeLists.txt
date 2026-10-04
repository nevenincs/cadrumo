set(CONTRACT_DIR "${CADRUMO_PATH_GENERATED}")
string(JSON sdk_root_relative GET "${package_layout}" sdk root)
set(CPYTHON_ROOT "${CADRUMO_PATH_RUNTIME}/${sdk_root_relative}")
set(CADRUMO_BUILD_HELPER "${PROJECT_SOURCE_DIR}/dev/packaging/native/cmake_build.py")
set(CADRUMO_HELPER "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build)
file(GLOB_RECURSE native_helper_inputs CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/dev/packaging/native/*.py")
file(GLOB platform_contract_inputs CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/native/platforms/*.json")
set(contract_inputs "${PROJECT_SOURCE_DIR}/native/package-layout.json" ${platform_contract_inputs}
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/layout.py")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${contract_inputs})
set(shared_inputs "${PROJECT_BINARY_DIR}/build-paths.json"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/build_paths.py" "${CADRUMO_BUILD_HELPER}" "${PROJECT_SOURCE_DIR}/dev/packaging/native/action_cache.py")
set(provision_inputs ${shared_inputs} ${contract_inputs}
  "${PROJECT_SOURCE_DIR}/uv.lock" "${PROJECT_SOURCE_DIR}/pyproject.toml"
  "${CMAKE_CURRENT_SOURCE_DIR}/toolchain.json" "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/provision.py" "${PROJECT_SOURCE_DIR}/dev/packaging/uv_constraints.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/platforms/${CADRUMO_BACKEND}.py")
list(JOIN provision_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-provision.txt" CONTENT "${input_lines}\n")
set(tool_inputs ${shared_inputs} "${CMAKE_CURRENT_SOURCE_DIR}/toolchain.json")
list(JOIN tool_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-tools.txt" CONTENT "${input_lines}\n")
string(JSON production_executable GET "${package_layout}" paths executable)
string(JSON development_executable GET "${package_layout}" files development_executable)
string(JSON bridge_library GET "${package_layout}" files bridge)
cmake_path(GET production_executable STEM production_name)
cmake_path(GET development_executable STEM development_name)
cmake_path(GET bridge_library STEM bridge_name)
set(CADRUMO_PACKAGE_EXECUTABLE "${production_executable}" PARENT_SCOPE)
string(JSON package_manifest GET "${package_layout}" files package_manifest)
set(CADRUMO_PACKAGE_MANIFEST "${package_manifest}" PARENT_SCOPE)
file(GLOB settings_inputs CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/src/cadrumo/core/config*.py"
  "${PROJECT_SOURCE_DIR}/src/cadrumo/core/storage*.py" "${PROJECT_SOURCE_DIR}/src/cadrumo/core/product_identity.py")
add_custom_command(OUTPUT "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h"
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.generate "${CONTRACT_DIR}"
  DEPENDS ${settings_inputs} ${contract_inputs} "${PROJECT_SOURCE_DIR}/dev/packaging/native/generate.py"
    "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version" "${PROJECT_SOURCE_DIR}/.python-version"
    "${CADRUMO_BUILD_HELPER}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(native_contract DEPENDS "${CONTRACT_DIR}/contract.rs" "${CONTRACT_DIR}/contract.h")
add_custom_command(OUTPUT "${CADRUMO_PATH_RUNTIME}/ready"
  COMMAND ${CADRUMO_HELPER} provision --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-provision.txt"
  DEPENDS ${provision_inputs} "${PROJECT_BINARY_DIR}/inputs-provision.txt"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(python_dependencies DEPENDS "${CADRUMO_PATH_RUNTIME}/ready")
add_custom_command(OUTPUT "${CADRUMO_PATH_TOOLS}/ready"
  COMMAND ${CADRUMO_HELPER} tools --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-tools.txt"
  DEPENDS ${tool_inputs} "${PROJECT_BINARY_DIR}/inputs-tools.txt"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(native_build_tools DEPENDS "${CADRUMO_PATH_TOOLS}/ready")
set(native_helper_inputs "${native_helper_inputs}" PARENT_SCOPE)
set(contract_inputs "${contract_inputs}" PARENT_SCOPE)
set(CADRUMO_HELPER "${CADRUMO_HELPER}" PARENT_SCOPE)
set(CADRUMO_BUILD_HELPER "${CADRUMO_BUILD_HELPER}" PARENT_SCOPE)
include("${PROJECT_SOURCE_DIR}/native/cmake/Rust.cmake")
include("${PROJECT_SOURCE_DIR}/native/cmake/platforms/${CMAKE_SYSTEM_NAME}.cmake")
add_subdirectory(application)
set(CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}" PARENT_SCOPE)
set(CADRUMO_ENTRYPOINTS "${CADRUMO_ENTRYPOINTS}" PARENT_SCOPE)
set(CADRUMO_ENTRYPOINT_TARGETS "${CADRUMO_ENTRYPOINT_TARGETS}" PARENT_SCOPE)
