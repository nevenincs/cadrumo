# CMake reads this before compiler detection, including try_compile projects.
# native/toolchain.json declares MSVC and Windows SDK floors. The newest installed release at
# or above each is selected once and cached; -DCADRUMO_MSVC_VERSION / -DCADRUMO_WINDOWS_SDK_VERSION
# select another release at or above the floor.
include("${CMAKE_CURRENT_LIST_DIR}/ToolchainFloor.cmake")
file(READ "${CMAKE_CURRENT_LIST_DIR}/../toolchain.json" cadrumo_toolchain)
string(JSON cadrumo_msvc_floor GET "${cadrumo_toolchain}" msvc)
string(JSON cadrumo_sdk_floor GET "${cadrumo_toolchain}" windows_sdk)
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES CADRUMO_MSVC_VERSION CADRUMO_WINDOWS_SDK_VERSION)
if(NOT CADRUMO_MSVC_VERSION)
  if(CMAKE_GENERATOR_INSTANCE)
    string(REGEX REPLACE ",.*$" "" cadrumo_vs_root "${CMAKE_GENERATOR_INSTANCE}")
  else()
    cmake_host_system_information(RESULT cadrumo_vs_root QUERY VS_17_DIR)
  endif()
  cmake_path(SET cadrumo_vs_root NORMALIZE "${cadrumo_vs_root}")
  set(cadrumo_msvc_tools "${cadrumo_vs_root}/VC/Tools/MSVC")
  cadrumo_newest_at_floor(cadrumo_msvc "${cadrumo_msvc_tools}" "${cadrumo_msvc_floor}"
    "${cadrumo_msvc_tools}/{version}/bin/Hostx64/x64/cl.exe"
    "${cadrumo_msvc_tools}/{version}/lib/x64/libcmt.lib")
  if(NOT cadrumo_msvc)
    message(FATAL_ERROR "No x64 MSVC toolset at or above the native/toolchain.json floor "
      "${cadrumo_msvc_floor} is installed under ${cadrumo_msvc_tools}")
  endif()
  set(CADRUMO_MSVC_VERSION "${cadrumo_msvc}" CACHE STRING
    "MSVC toolset at or above the native/toolchain.json floor" FORCE)
endif()
if(NOT CADRUMO_WINDOWS_SDK_VERSION)
  cmake_host_system_information(RESULT cadrumo_kits_root QUERY WINDOWS_REGISTRY
    "HKLM/SOFTWARE/Microsoft/Windows Kits/Installed Roots" VALUE KitsRoot10 VIEW 64)
  cmake_path(SET cadrumo_kits_root NORMALIZE "${cadrumo_kits_root}")
  cadrumo_newest_at_floor(cadrumo_sdk "${cadrumo_kits_root}/Lib" "${cadrumo_sdk_floor}"
    "${cadrumo_kits_root}/Lib/{version}/um/x64/kernel32.lib"
    "${cadrumo_kits_root}/Lib/{version}/ucrt/x64/ucrt.lib"
    "${cadrumo_kits_root}/Include/{version}/um/Windows.h")
  if(NOT cadrumo_sdk)
    message(FATAL_ERROR "No x64 Windows SDK at or above the native/toolchain.json floor "
      "${cadrumo_sdk_floor} is installed under ${cadrumo_kits_root}")
  endif()
  set(CADRUMO_WINDOWS_SDK_VERSION "${cadrumo_sdk}" CACHE STRING
    "Windows SDK at or above the native/toolchain.json floor" FORCE)
endif()
cadrumo_floor_violation(cadrumo_violation "MSVC" "${CADRUMO_MSVC_VERSION}" "${cadrumo_msvc_floor}")
if(NOT cadrumo_violation)
  cadrumo_floor_violation(cadrumo_violation "Windows SDK" "${CADRUMO_WINDOWS_SDK_VERSION}" "${cadrumo_sdk_floor}")
endif()
if(cadrumo_violation)
  message(FATAL_ERROR "${cadrumo_violation}")
endif()
set(CMAKE_GENERATOR_PLATFORM x64 CACHE STRING "CADRUMO architecture")
set(CMAKE_GENERATOR_TOOLSET "version=${CADRUMO_MSVC_VERSION}" CACHE STRING "CADRUMO MSVC toolset" FORCE)
set(CMAKE_SYSTEM_VERSION "${CADRUMO_WINDOWS_SDK_VERSION}" CACHE STRING "CADRUMO Windows SDK" FORCE)
