# Native Linux builds run in the target's digest-pinned image in toolchain.json.
# Do not set CMAKE_SYSTEM_NAME: these are native builds, not cross compilation.
if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "The manylinux toolchain requires its native Linux builder")
endif()
execute_process(COMMAND /usr/bin/getconf GNU_LIBC_VERSION
  OUTPUT_VARIABLE cadrumo_builder_libc OUTPUT_STRIP_TRAILING_WHITESPACE
  COMMAND_ERROR_IS_FATAL ANY)
if(NOT cadrumo_builder_libc STREQUAL "glibc 2.28")
  message(FATAL_ERROR "Use the glibc 2.28 builder image pinned in native/toolchain.json")
endif()
set(cadrumo_native_compiler "/opt/rh/gcc-toolset-14/root/usr/bin/gcc")
if(NOT EXISTS "${cadrumo_native_compiler}")
  message(FATAL_ERROR "The pinned manylinux GCC toolset is unavailable")
endif()
set(CMAKE_C_COMPILER "${cadrumo_native_compiler}" CACHE FILEPATH "Native manylinux C compiler")
if(NOT CMAKE_C_COMPILER STREQUAL cadrumo_native_compiler)
  message(FATAL_ERROR "The selected compiler differs from the manylinux toolchain")
endif()
