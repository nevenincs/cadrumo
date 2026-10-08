# Native arm64 builds select a reviewed compiler and SDK without changing xcode-select.
# Root CMake owns the deployment floor and architecture; Cargo's linker stays explicit.
if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Darwin" OR NOT CMAKE_HOST_SYSTEM_PROCESSOR STREQUAL "arm64")
  message(FATAL_ERROR "The Darwin toolchain requires its native arm64 Mac builder")
endif()
if(CMAKE_CROSSCOMPILING)
  message(FATAL_ERROR "The Darwin toolchain does not support cross compilation")
endif()
foreach(name COMPILER COMPILER_IDENTITY SDK_ROOT SDK_VERSION)
  if(NOT DEFINED CADRUMO_DARWIN_${name} OR "${CADRUMO_DARWIN_${name}}" STREQUAL "")
    message(FATAL_ERROR "Supply reviewed CADRUMO_DARWIN_${name}")
  endif()
endforeach()
if(NOT IS_ABSOLUTE "${CADRUMO_DARWIN_COMPILER}" OR NOT EXISTS "${CADRUMO_DARWIN_COMPILER}"
    OR IS_DIRECTORY "${CADRUMO_DARWIN_COMPILER}")
  message(FATAL_ERROR "CADRUMO_DARWIN_COMPILER must select an existing absolute compiler file")
endif()
if(NOT IS_ABSOLUTE "${CADRUMO_DARWIN_SDK_ROOT}" OR NOT IS_DIRECTORY "${CADRUMO_DARWIN_SDK_ROOT}"
    OR NOT EXISTS "${CADRUMO_DARWIN_SDK_ROOT}/SDKSettings.json")
  message(FATAL_ERROR "CADRUMO_DARWIN_SDK_ROOT must select an absolute SDK with SDKSettings.json")
endif()
file(READ "${CADRUMO_DARWIN_SDK_ROOT}/SDKSettings.json" cadrumo_darwin_sdk)
string(JSON cadrumo_darwin_sdk_version GET "${cadrumo_darwin_sdk}" Version)
string(JSON cadrumo_darwin_sdk_name GET "${cadrumo_darwin_sdk}" CanonicalName)
if(NOT cadrumo_darwin_sdk_version STREQUAL CADRUMO_DARWIN_SDK_VERSION
    OR NOT cadrumo_darwin_sdk_name STREQUAL "macosx${CADRUMO_DARWIN_SDK_VERSION}")
  message(FATAL_ERROR "Selected SDK differs from the reviewed macOS SDK version")
endif()
execute_process(COMMAND "${CADRUMO_DARWIN_COMPILER}" --version
  OUTPUT_VARIABLE cadrumo_darwin_compiler_output OUTPUT_STRIP_TRAILING_WHITESPACE
  COMMAND_ERROR_IS_FATAL ANY)
string(REGEX MATCH "^[^\r\n]+" cadrumo_darwin_compiler_identity "${cadrumo_darwin_compiler_output}")
if(NOT cadrumo_darwin_compiler_identity MATCHES "^Apple clang version "
    OR NOT cadrumo_darwin_compiler_identity STREQUAL CADRUMO_DARWIN_COMPILER_IDENTITY)
  message(FATAL_ERROR "Selected compiler differs from the reviewed Apple clang identity")
endif()
if(DEFINED CMAKE_C_COMPILER AND NOT "${CMAKE_C_COMPILER}" STREQUAL ""
    AND NOT CMAKE_C_COMPILER STREQUAL CADRUMO_DARWIN_COMPILER)
  message(FATAL_ERROR "CMAKE_C_COMPILER differs from the reviewed Darwin toolchain input")
endif()
if(DEFINED CMAKE_OSX_SYSROOT AND NOT "${CMAKE_OSX_SYSROOT}" STREQUAL ""
    AND NOT CMAKE_OSX_SYSROOT STREQUAL CADRUMO_DARWIN_SDK_ROOT)
  message(FATAL_ERROR "CMAKE_OSX_SYSROOT differs from the reviewed Darwin toolchain input")
endif()
# Empty cache entries must bind to the admitted inputs instead of triggering discovery.
set(CMAKE_C_COMPILER "${CADRUMO_DARWIN_COMPILER}" CACHE FILEPATH "Reviewed native Apple clang" FORCE)
set(CMAKE_OSX_SYSROOT "${CADRUMO_DARWIN_SDK_ROOT}" CACHE PATH "Reviewed native macOS SDK" FORCE)
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES
  CADRUMO_DARWIN_COMPILER CADRUMO_DARWIN_COMPILER_IDENTITY
  CADRUMO_DARWIN_SDK_ROOT CADRUMO_DARWIN_SDK_VERSION)
list(REMOVE_DUPLICATES CMAKE_TRY_COMPILE_PLATFORM_VARIABLES)
