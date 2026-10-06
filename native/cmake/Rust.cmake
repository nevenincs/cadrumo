# CMake owns target/configuration/output selection; Cargo owns Rust dependency freshness.
# Platform adapters supply compiler/linker environment facts, never a second target list.
function(cadrumo_cargo_command output)
  # Cargo combines this builder path with native separators for CARGO_TARGET_TMPDIR.
  cmake_path(NATIVE_PATH CADRUMO_PATH_CARGO NORMALIZE cargo_directory)
  set(command ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}"
    --env "RUSTC=${CADRUMO_RUST_ROOT}/bin/rustc${CMAKE_EXECUTABLE_SUFFIX}"
    --env "RUSTDOC=${CADRUMO_RUST_ROOT}/bin/rustdoc${CMAKE_EXECUTABLE_SUFFIX}"
    --env "CARGO_TARGET_DIR=${cargo_directory}")
  foreach(name IN LISTS CADRUMO_RUST_ENVIRONMENT_NAMES)
    string(REPLACE ";" "\\;" value "${CADRUMO_RUST_ENV_${name}}")
    list(APPEND command --env "${name}=${value}")
  endforeach()
  list(APPEND command ${ARGN} -- "${CADRUMO_RUST_ROOT}/bin/cargo${CMAKE_EXECUTABLE_SUFFIX}")
  set(${output} "${command}" PARENT_SCOPE)
endfunction()
