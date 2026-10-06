# Shared by the source build and the native distribution project.
include("${CMAKE_CURRENT_LIST_DIR}/BuildPaths.cmake")
get_filename_component(CADRUMO_SOURCE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
find_program(CADRUMO_DEV_PYTHON NAMES python python3
  PATHS "${CADRUMO_SOURCE_ROOT}/.venv/Scripts" "${CADRUMO_SOURCE_ROOT}/.venv/bin"
  NO_DEFAULT_PATH DOC "Development Python")
if(NOT EXISTS "${CADRUMO_DEV_PYTHON}")
  message(FATAL_ERROR "Set CADRUMO_DEV_PYTHON to the project's development interpreter")
endif()
if(NOT DEFINED CADRUMO_TARGET)
  cmake_host_system_information(RESULT host_arch QUERY OS_PLATFORM)
  if(CMAKE_HOST_WIN32 AND host_arch MATCHES "^(AMD64|x86_64)$")
    set(default_target windows-x86-64)
  elseif(CMAKE_HOST_APPLE AND host_arch MATCHES "^(arm64|aarch64)$")
    set(default_target macos-arm64)
  elseif(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux" AND host_arch MATCHES "^(x86_64|aarch64)$")
    string(REPLACE x86_64 x86-64 host_arch "${host_arch}")
    set(default_target "linux-${host_arch}")
  else()
    message(FATAL_ERROR "Set CADRUMO_TARGET to a supported distribution target")
  endif()
  set(CADRUMO_TARGET "${default_target}" CACHE STRING "Canonical distribution target")
endif()
if(DEFINED CADRUMO_CONFIGURED_TARGET AND NOT CADRUMO_CONFIGURED_TARGET STREQUAL CADRUMO_TARGET)
  message(FATAL_ERROR "Target changes require a fresh binary directory; this directory belongs to ${CADRUMO_CONFIGURED_TARGET}")
endif()
set(CADRUMO_CONFIGURED_TARGET "${CADRUMO_TARGET}" CACHE INTERNAL "Target owning this binary directory")
set(CADRUMO_CHANNEL stable CACHE STRING "Installation channel, independent of Debug/Release")
set_property(CACHE CADRUMO_CHANNEL PROPERTY STRINGS stable preview)
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.identity
  --target "${CADRUMO_TARGET}" --channel "${CADRUMO_CHANNEL}" --output "${CADRUMO_PATH_GENERATED}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMAND_ERROR_IS_FATAL ANY)
include("${CADRUMO_PATH_GENERATED}/Identity.cmake")
set(CADRUMO_VERSION "${CADRUMO_ID_VERSION}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/pyproject.toml"
  "${CADRUMO_SOURCE_ROOT}/src/cadrumo/core/product_identity.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/identity.py"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/runtime_wheelhouse_contract.py")
