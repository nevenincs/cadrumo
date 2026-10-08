# A compiler path alone does not carry CMake driver arguments into Cargo.
function(cadrumo_posix_rust_linker output)
  if(NOT DEFINED CADRUMO_RUST_LINKER)
    set(CADRUMO_RUST_LINKER "" CACHE FILEPATH
      "Reviewed target linker wrapper carrying the CMake compiler/target/sysroot arguments")
  endif()
  if(CADRUMO_RUST_LINKER)
    if(NOT IS_ABSOLUTE "${CADRUMO_RUST_LINKER}" OR
       NOT EXISTS "${CADRUMO_RUST_LINKER}" OR IS_DIRECTORY "${CADRUMO_RUST_LINKER}")
      message(FATAL_ERROR "CADRUMO_RUST_LINKER must name an existing absolute linker wrapper")
    endif()
    set(${output} "${CADRUMO_RUST_LINKER}" PARENT_SCOPE)
    return()
  endif()
  foreach(setting CMAKE_SYSROOT CMAKE_SYSROOT_LINK CMAKE_C_COMPILER_TARGET
      CMAKE_C_COMPILER_EXTERNAL_TOOLCHAIN CMAKE_C_COMPILER_ARG1 CMAKE_OSX_SYSROOT
      CMAKE_C_FLAGS CMAKE_EXE_LINKER_FLAGS)
    if(NOT "${${setting}}" STREQUAL "")
      message(FATAL_ERROR
        "${setting} is set: supply CADRUMO_RUST_LINKER carrying the reviewed target link configuration; Cargo does not inherit CMake flags")
    endif()
  endforeach()
  if(CMAKE_CROSSCOMPILING)
    message(FATAL_ERROR "Cross compilation requires an explicit CADRUMO_RUST_LINKER")
  endif()
  set(${output} "${CMAKE_C_COMPILER}" PARENT_SCOPE)
endfunction()
