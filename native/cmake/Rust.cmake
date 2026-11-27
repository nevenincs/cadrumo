# A Release image must not record where it was built: rustc replaces this checkout's location with a
# neutral prefix in every path it embeds, such as a panic location or a configuration file. Platform adapters
# append this to the RUSTFLAGS they set. RUSTFLAGS splits on whitespace and has no quoting, so a checkout path
# with whitespace is refused here rather than half remapped.
if(PROJECT_SOURCE_DIR MATCHES "[ \t]")
  message(FATAL_ERROR "A Release Rust image remaps the checkout path through RUSTFLAGS; "
    "move the checkout to a path without whitespace: ${PROJECT_SOURCE_DIR}")
endif()
set(rust_release_remaps "--remap-path-prefix=${PROJECT_SOURCE_DIR}=cadrumo")
# Dependency sources come from the builder's Cargo home and the standard library's from the toolchain,
# and both usually lie in the builder's home directory, whose name is the builder's account. A later
# prefix wins over an earlier one, so the home is first and the two it usually contains follow.
set(rust_builder_home "$ENV{HOME}")
if(CMAKE_HOST_WIN32)
  set(rust_builder_home "$ENV{USERPROFILE}")
endif()
set(rust_cargo_home "$ENV{CARGO_HOME}")
if(rust_cargo_home STREQUAL "" AND NOT rust_builder_home STREQUAL "")
  set(rust_cargo_home "${rust_builder_home}/.cargo")
endif()
foreach(remap IN ITEMS "rust_builder_home=home" "rust_cargo_home=cargo" "CADRUMO_RUST_ROOT=rust")
  string(REPLACE "=" ";" remap "${remap}")
  list(GET remap 0 variable)
  list(GET remap 1 neutral)
  if("${${variable}}" STREQUAL "")
    continue()
  endif()
  file(TO_CMAKE_PATH "${${variable}}" location)
  if(location MATCHES "[ \t]")
    # Not refused: a Debug image may name it, and the release image scan refuses a Release package that does.
    message(WARNING "A Release Rust image cannot remap a location with whitespace through RUSTFLAGS, "
      "so it will name it: ${location}")
    continue()
  endif()
  list(APPEND rust_release_remaps "--remap-path-prefix=${location}=${neutral}")
endforeach()
list(JOIN rust_release_remaps " " rust_release_remaps)
set(CADRUMO_RUST_RELEASE_REMAP "$<$<NOT:$<CONFIG:Debug>>:${rust_release_remaps}>")
# CMake owns target/configuration/output selection; Cargo owns Rust dependency freshness.
# Platform adapters supply compiler/linker environment facts, never a second target list.
function(cadrumo_cargo_command output)
  # Cargo combines this builder path with native separators for CARGO_TARGET_TMPDIR.
  cmake_path(NATIVE_PATH CADRUMO_PATH_CARGO NORMALIZE cargo_directory)
  # A command that builds a component's own images passes --build-identity <component>; only
  # that component's crate reads the identity, and an unchanged fingerprint changes no value.
  set(command ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --env "RUSTC=${CADRUMO_RUST_ROOT}/bin/rustc${CMAKE_EXECUTABLE_SUFFIX}"
    --env "RUSTDOC=${CADRUMO_RUST_ROOT}/bin/rustdoc${CMAKE_EXECUTABLE_SUFFIX}"
    --env "CARGO_TARGET_DIR=${cargo_directory}"
    --env "CARGO_BUILD_TARGET_DIR=${cargo_directory}"
    --env "CARGO_BUILD_BUILD_DIR=${cargo_directory}")
  foreach(name IN LISTS CADRUMO_RUST_ENVIRONMENT_NAMES)
    string(REPLACE ";" "\\;" value "${CADRUMO_RUST_ENV_${name}}")
    list(APPEND command --env "${name}=${value}")
  endforeach()
  list(APPEND command ${ARGN} -- "${CADRUMO_RUST_ROOT}/bin/cargo${CMAKE_EXECUTABLE_SUFFIX}")
  set(${output} "${command}" PARENT_SCOPE)
endfunction()
