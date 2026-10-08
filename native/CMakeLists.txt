set(CONTRACT_DIR "${CADRUMO_PATH_GENERATED}")
string(JSON sdk_root_relative GET "${package_layout}" sdk root)
set(CPYTHON_ROOT "${CADRUMO_PATH_PYTHON_SDK}/${sdk_root_relative}")
set(sdk_link_outputs)
if(NOT WIN32)
  string(JSON sdk_link_library GET "${package_layout}" sdk link_library)
  list(APPEND sdk_link_outputs "${CPYTHON_ROOT}/${sdk_link_library}")
endif()
set(CADRUMO_BUILD_HELPER "${PROJECT_SOURCE_DIR}/dev/packaging/native/cmake_build.py")
set(CADRUMO_HELPER "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build)
file(GLOB_RECURSE native_helper_inputs CONFIGURE_DEPENDS "${PROJECT_SOURCE_DIR}/dev/packaging/native/*.py")
include("${PROJECT_SOURCE_DIR}/native/cmake/Contract.cmake")
set(shared_inputs "${PROJECT_BINARY_DIR}/build-paths.json"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/build_paths.py" "${CADRUMO_BUILD_HELPER}" "${PROJECT_SOURCE_DIR}/dev/packaging/native/action_cache.py")
include("${PROJECT_SOURCE_DIR}/native/cmake/PackageInputs.cmake")
cadrumo_provision_helpers(provision_helper_inputs "${PROJECT_SOURCE_DIR}" "${CADRUMO_BACKEND}")
set(sdk_inputs ${shared_inputs} ${contract_inputs} ${provision_helper_inputs}
  "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version"
  "${PROJECT_SOURCE_DIR}/dev/packaging/runtime_wheelhouse_contract.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/command_execution.py")
set(provision_inputs ${shared_inputs}
  "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/provision.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/build_toolchain.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/target.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/runtime_wheel_selection.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/runtime_wheelhouse_contract.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/uv_constraints.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/command_execution.py")
list(JOIN sdk_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-sdk.txt" CONTENT "${input_lines}\n")
list(JOIN provision_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-provision.txt" CONTENT "${input_lines}\n")
set(tool_inputs ${shared_inputs} "${PROJECT_SOURCE_DIR}/dev/packaging/native/build_toolchain.py")
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
add_custom_target(python_sdk
  COMMAND ${CADRUMO_HELPER} sdk --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-sdk.txt"
  DEPENDS ${sdk_inputs} "${PROJECT_BINARY_DIR}/inputs-sdk.txt"
  BYPRODUCTS "${CADRUMO_PATH_PYTHON_SDK}/ready" ${sdk_link_outputs}
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(python_dependencies
  COMMAND ${CADRUMO_HELPER} provision --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-provision.txt"
  DEPENDS ${provision_inputs} "${PROJECT_BINARY_DIR}/inputs-provision.txt"
  BYPRODUCTS "${CADRUMO_PATH_RUNTIME}/ready"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_dependencies(python_dependencies python_sdk)
add_custom_target(native_build_tools
  COMMAND ${CADRUMO_HELPER} tools --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-tools.txt"
  DEPENDS ${tool_inputs} "${PROJECT_BINARY_DIR}/inputs-tools.txt"
  BYPRODUCTS "${CADRUMO_PATH_TOOLS}/ready"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET python_sdk PATHS "${CADRUMO_PATH_PYTHON_SDK}")
  cadrumo_register_clean(TARGET python_dependencies PATHS "${CADRUMO_PATH_RUNTIME}")
  cadrumo_register_clean(TARGET native_build_tools PATHS "${CADRUMO_PATH_TOOLS}")
endif()
set(native_helper_inputs "${native_helper_inputs}" PARENT_SCOPE)
set(contract_inputs "${contract_inputs}" PARENT_SCOPE)
set(CADRUMO_HELPER "${CADRUMO_HELPER}" PARENT_SCOPE)
set(CADRUMO_BUILD_HELPER "${CADRUMO_BUILD_HELPER}" PARENT_SCOPE)
include("${PROJECT_SOURCE_DIR}/native/cmake/Rust.cmake")
set(metadata_inputs ${contract_inputs}
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/metadata.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/identity.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/stable_output.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/platforms/${CADRUMO_BACKEND}.py"
  "${PROJECT_SOURCE_DIR}/src/cadrumo/core/product_identity.py"
  "${PROJECT_SOURCE_DIR}/src/cadrumo/core/toml.py"
  "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version")
include("${PROJECT_SOURCE_DIR}/native/cmake/platforms/${CMAKE_SYSTEM_NAME}.cmake")
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_platform_static PATHS "${platform_static}")
  if(WIN32)
    cadrumo_register_clean(TARGET rust_platform_shared PATHS "${platform_import}" "${platform_dir}/cadrumo_platform.dll")
  else()
    cadrumo_register_clean(TARGET rust_platform_shared PATHS
      "${platform_dir}/${CMAKE_SHARED_LIBRARY_PREFIX}cadrumo_platform${CMAKE_SHARED_LIBRARY_SUFFIX}")
  endif()
  cadrumo_register_clean(TARGET rust_platform DEPENDS rust_platform_static rust_platform_shared)
  cadrumo_register_clean(TARGET rust_platform_consumer PATHS "${platform_consumer}")
endif()
add_subdirectory(application)
# Defines rust_manager and CADRUMO_MANAGER_EXECUTABLE in this directory scope for Packaging.cmake.
include("${PROJECT_SOURCE_DIR}/native/cmake/Manager.cmake")
include("${PROJECT_SOURCE_DIR}/native/cmake/Installer.cmake")
set(CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}" PARENT_SCOPE)
set(CADRUMO_ENTRYPOINTS "${CADRUMO_ENTRYPOINTS}" PARENT_SCOPE)
set(CADRUMO_ENTRYPOINT_TARGETS "${CADRUMO_ENTRYPOINT_TARGETS}" PARENT_SCOPE)
