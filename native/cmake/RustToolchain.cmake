# native/toolchain.json declares the Rust floor. An explicit CADRUMO_RUST_ROOT wins; otherwise
# rustup's active toolchain for the source tree is resolved once and cached like a found program.
include("${CMAKE_CURRENT_LIST_DIR}/ToolchainFloor.cmake")
set(CADRUMO_RUST_ROOT "" CACHE PATH
  "Rust toolchain root at or above the native/toolchain.json floor; empty resolves rustup's active toolchain")
if(NOT CADRUMO_RUST_ROOT)
  find_program(CADRUMO_RUSTUP NAMES rustup
    HINTS "$ENV{CARGO_HOME}/bin" "$ENV{USERPROFILE}/.cargo/bin" "$ENV{HOME}/.cargo/bin"
    DOC "rustup used to resolve the active Rust toolchain")
  if(NOT CADRUMO_RUSTUP)
    message(FATAL_ERROR "Set CADRUMO_RUST_ROOT, or install rustup, for Rust ${CADRUMO_PIN_rust} or newer")
  endif()
  execute_process(COMMAND "${CADRUMO_RUSTUP}" which rustc
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE rustup_rustc
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  cmake_path(SET rustup_rustc NORMALIZE "${rustup_rustc}")
  cmake_path(GET rustup_rustc PARENT_PATH rustup_bin)
  cmake_path(GET rustup_bin PARENT_PATH rustup_root)
  set(CADRUMO_RUST_ROOT "${rustup_root}" CACHE PATH
    "Rust toolchain root at or above the native/toolchain.json floor; empty resolves rustup's active toolchain" FORCE)
endif()
message(CHECK_START "Checking Rust ${CADRUMO_PIN_rust} or newer for ${CADRUMO_PIN_rust_target}")
set(rustc "${CADRUMO_RUST_ROOT}/bin/rustc${CMAKE_EXECUTABLE_SUFFIX}")
if(NOT EXISTS "${rustc}")
  message(CHECK_FAIL "missing ${rustc}")
  message(FATAL_ERROR "CADRUMO_RUST_ROOT ${CADRUMO_RUST_ROOT} has no rustc")
endif()
execute_process(COMMAND "${rustc}" --version
  OUTPUT_VARIABLE rust_identity OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set(CADRUMO_RUST_VERSION "")
if(rust_identity MATCHES "^rustc ([0-9]+\\.[0-9]+\\.[0-9]+)")
  set(CADRUMO_RUST_VERSION "${CMAKE_MATCH_1}")
endif()
cadrumo_floor_violation(rust_violation "Rust" "${CADRUMO_RUST_VERSION}" "${CADRUMO_PIN_rust}")
if(rust_violation)
  message(CHECK_FAIL "found ${rust_identity}")
  message(FATAL_ERROR "${rust_violation}: ${CADRUMO_RUST_ROOT}")
endif()
execute_process(COMMAND "${rustc}" --print sysroot
  OUTPUT_VARIABLE rust_sysroot OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
cmake_path(SET rust_sysroot NORMALIZE "${rust_sysroot}")
if(NOT IS_DIRECTORY "${rust_sysroot}/lib/rustlib/${CADRUMO_PIN_rust_target}/lib")
  message(CHECK_FAIL "${CADRUMO_PIN_rust_target} is not installed")
  message(FATAL_ERROR "Rust ${CADRUMO_RUST_VERSION} at ${CADRUMO_RUST_ROOT} lacks the "
    "${CADRUMO_PIN_rust_target} standard library; add that target to the toolchain")
endif()
message(CHECK_PASS "${rust_identity}")
cadrumo_build_fact("Rust" "${CADRUMO_RUST_VERSION} (floor ${CADRUMO_PIN_rust}) for ${CADRUMO_PIN_rust_target}: ${CADRUMO_RUST_ROOT}")
