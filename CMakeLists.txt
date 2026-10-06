cmake_minimum_required(VERSION 4.4)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build directory")
endif()
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/tmp")

# Toolchain versions have one authored owner. Set compiler-selection inputs before project().
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/native/toolchain.json" toolchain)
foreach(key cmake msvc windows_sdk rust)
  string(JSON CADRUMO_PIN_${key} GET "${toolchain}" ${key})
endforeach()
if(NOT CMAKE_VERSION VERSION_EQUAL CADRUMO_PIN_cmake)
  message(FATAL_ERROR "CMake ${CADRUMO_PIN_cmake} is required")
endif()
include(native/cmake/Identity.cmake)
string(JSON CADRUMO_PIN_rust_target GET "${toolchain}" targets "${CADRUMO_TARGET}" rust_target)
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import json; from dataclasses import asdict; from dev.packaging.runtime_wheelhouse_contract import target_platform; print(json.dumps(asdict(target_platform('${CADRUMO_TARGET}'))))"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" OUTPUT_VARIABLE target_platform
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
string(JSON target_system GET "${target_platform}" platform_system)
string(JSON target_machine GET "${target_platform}" platform_machine)
if(target_system STREQUAL "Darwin")
  string(JSON target_floor GET "${target_platform}" floor)
  string(REPLACE "macos-" "" target_floor "${target_floor}")
  set(CMAKE_OSX_DEPLOYMENT_TARGET "${target_floor}" CACHE STRING "Canonical macOS deployment floor" FORCE)
  set(CMAKE_OSX_ARCHITECTURES "${target_machine}" CACHE STRING "Canonical macOS architecture" FORCE)
endif()
if(CADRUMO_TARGET STREQUAL "windows-x86-64")
  if(NOT CMAKE_TOOLCHAIN_FILE)
    set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/native/cmake/WindowsToolchain.cmake")
  endif()
  set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
elseif(NOT CMAKE_TOOLCHAIN_FILE)
  message(FATAL_ERROR "${CADRUMO_TARGET} requires an explicit compiler/sysroot toolchain file and reviewed SDK pins; see native/CONTRACT.md")
endif()
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/native/cmake/platforms/${target_system}.cmake")
  message(FATAL_ERROR "Native adapter ${target_system}.cmake is not enrolled for ${CADRUMO_TARGET}")
endif()
project(CADRUMO VERSION "${CADRUMO_ID_VERSION}"
  DESCRIPTION "${CADRUMO_ID_DESCRIPTION}" HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}"
  SPDX_LICENSE "${CADRUMO_ID_LICENSE}" LANGUAGES C)
include(native/cmake/Configurations.cmake)
if(WIN32)
  enable_language(RC)
endif()
if(WIN32)
  if(NOT MSVC OR NOT CMAKE_C_COMPILER MATCHES "/MSVC/${CADRUMO_PIN_msvc}/"
      OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL CADRUMO_PIN_windows_sdk)
    message(FATAL_ERROR "The selected compiler/SDK does not match native/toolchain.json")
  endif()
endif()
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
  set(CMAKE_INSTALL_PREFIX "${PROJECT_BINARY_DIR}/install" CACHE PATH "Default local installation prefix" FORCE)
endif()
if(NOT CMAKE_SYSTEM_NAME STREQUAL target_system OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "Compiler OS/bitness differs from ${CADRUMO_TARGET}")
endif()
if(WIN32)
  if(NOT CMAKE_VS_PLATFORM_NAME STREQUAL "x64" AND NOT CMAKE_C_COMPILER_ARCHITECTURE_ID STREQUAL "x64")
    message(FATAL_ERROR "windows-x86-64 requires an x64 compiler target")
  endif()
elseif(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL target_machine)
  message(FATAL_ERROR "Compiler processor ${CMAKE_SYSTEM_PROCESSOR} differs from target ${target_machine}")
endif()
find_program(CADRUMO_DEV_PYTHON NAMES python python3
  PATHS "${PROJECT_SOURCE_DIR}/.venv/Scripts" "${PROJECT_SOURCE_DIR}/.venv/bin"
  NO_DEFAULT_PATH DOC "Development Python")
if(NOT EXISTS "${CADRUMO_DEV_PYTHON}")
  message(FATAL_ERROR "Set CADRUMO_DEV_PYTHON to the project's development interpreter")
endif()
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import json,platform,sys; print(json.dumps({'executable':sys.executable,'version':platform.python_version(),'implementation':platform.python_implementation()}))"
  OUTPUT_VARIABLE host_python OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
find_program(CADRUMO_UV NAMES uv REQUIRED)
execute_process(COMMAND "${CADRUMO_UV}" --version
  OUTPUT_VARIABLE uv_version OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set(build_toolchain "{}")
string(JSON build_toolchain SET "${build_toolchain}" host_python "${host_python}")
foreach(key CADRUMO_TARGET CADRUMO_CHANNEL CMAKE_C_COMPILER CMAKE_C_COMPILER_VERSION CMAKE_TOOLCHAIN_FILE CADRUMO_UV uv_version)
  string(JSON build_toolchain SET "${build_toolchain}" "${key}" "\"${${key}}\"")
endforeach()
include(native/cmake/AssemblyTools.cmake)
include(native/cmake/ArchiveTools.cmake)
include(native/cmake/BuildNumber.cmake)
string(TIMESTAMP build_date "%Y-%m-%dT%H:%M:%SZ" UTC)
set(CADRUMO_BUILD_DATE "${build_date}" CACHE STRING "Build date; SOURCE_DATE_EPOCH controls the default")
option(CADRUMO_INCLUDE_DEVELOPMENT_BINARY "Include the development interpreter in the assembled package" OFF)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/native/toolchain.json"
  "${PROJECT_SOURCE_DIR}/native/package-layout.json")
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import json; from dev.packaging.native.layout import load_layout; print(json.dumps(load_layout('${CADRUMO_TARGET}')))"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE package_layout
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
string(JSON CADRUMO_PLATFORM GET "${package_layout}" platform)
string(JSON CADRUMO_BACKEND GET "${package_layout}" backend)
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "from cadrumo.core.storage_environment import STORAGE_ROOT; print(STORAGE_ROOT.variable)"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE CADRUMO_STORAGE_ROOT_VARIABLE
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
include(CTest)
add_subdirectory(native)
include(native/cmake/ToolchainIdentity.cmake)
include(native/cmake/Packaging.cmake)
file(CONFIGURE OUTPUT "${CADRUMO_PATH_GENERATED}/build-toolchain.json" CONTENT "@build_toolchain@\n" @ONLY)
