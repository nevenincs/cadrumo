# Rust quality gates as CTest tests: <crate>.fmt, <crate>.clippy and <crate>.deny.
#
# Include point: native/CMakeLists.txt, after Rust.cmake. Each crate's CMake calls
# cadrumo_rust_quality() with the cargo command it already builds with, so clippy sees the
# same toolchain, contract environment and target directory as that crate's own tests.
#
# The tools are resolved here, at configure time: a gate whose tool is missing must stop the
# configure, never become a test that cannot run and is skipped.
include_guard(GLOBAL)
if(NOT COMMAND cadrumo_cargo_command)
  message(FATAL_ERROR "Include Rust.cmake before RustQuality.cmake")
endif()

set(CADRUMO_RUST_QUALITY_DENY_FLOOR "0.19.0")
set(CADRUMO_RUST_QUALITY_POLICY "${PROJECT_SOURCE_DIR}/native/deny.toml")

if(BUILD_TESTING)
  # rustfmt and clippy ship with the selected toolchain; cargo reaches them as subcommands.
  foreach(tool cargo-fmt rustfmt cargo-clippy clippy-driver)
    if(NOT EXISTS "${CADRUMO_RUST_ROOT}/bin/${tool}${CMAKE_EXECUTABLE_SUFFIX}")
      message(FATAL_ERROR "The Rust quality gates need ${tool} in ${CADRUMO_RUST_ROOT}/bin; "
        "add the rustfmt and clippy components to the toolchain")
    endif()
  endforeach()
  find_program(CADRUMO_CARGO_DENY NAMES cargo-deny
    HINTS "$ENV{CARGO_HOME}/bin" "$ENV{USERPROFILE}/.cargo/bin" "$ENV{HOME}/.cargo/bin"
    DOC "cargo-deny, the license, ban, source and advisory gate for the Rust crates")
  if(NOT CADRUMO_CARGO_DENY)
    message(FATAL_ERROR "The Rust quality gates need cargo-deny ${CADRUMO_RUST_QUALITY_DENY_FLOOR} or newer: "
      "run cargo install --locked cargo-deny, or set CADRUMO_CARGO_DENY")
  endif()
  execute_process(COMMAND "${CADRUMO_CARGO_DENY}" --version
    OUTPUT_VARIABLE deny_identity OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  set(deny_version "")
  if(deny_identity MATCHES "([0-9]+\\.[0-9]+\\.[0-9]+)")
    set(deny_version "${CMAKE_MATCH_1}")
  endif()
  if(NOT deny_version OR deny_version VERSION_LESS CADRUMO_RUST_QUALITY_DENY_FLOOR)
    message(FATAL_ERROR "cargo-deny '${deny_identity}' is below the ${CADRUMO_RUST_QUALITY_DENY_FLOOR} floor "
      "native/deny.toml is written for: ${CADRUMO_CARGO_DENY}")
  endif()
  cmake_path(GET CADRUMO_CARGO_DENY PARENT_PATH CADRUMO_CARGO_DENY_DIRECTORY)
  cadrumo_build_fact("cargo-deny" "${deny_version} (floor ${CADRUMO_RUST_QUALITY_DENY_FLOOR}): ${CADRUMO_CARGO_DENY}")
endif()

# cadrumo_rust_clippy(<name> MANIFEST <Cargo.toml> CARGO <variable> [ARGS <cargo clippy argument>...])
#
# Registers <name>.clippy: every target of the crate linted with warnings denied, under the
# target directory, profile and features ARGS select, so the lint reuses the build or test it
# neighbours. CARGO names the variable holding the crate's cadrumo_cargo_command list; it is
# expanded only inside add_test, as the crate's own tests do, because copying the list would
# split the escaped semicolons of its LIB and INCLUDE values.
function(cadrumo_rust_clippy name)
  cmake_parse_arguments(PARSE_ARGV 1 GATE "" "MANIFEST;CARGO" "ARGS")
  if(NOT BUILD_TESTING)
    return()
  endif()
  if(NOT GATE_MANIFEST OR NOT GATE_CARGO OR GATE_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR "cadrumo_rust_clippy(${name}) needs MANIFEST and CARGO")
  endif()
  add_test(NAME ${name}.clippy
    COMMAND ${${GATE_CARGO}} clippy --locked --all-targets --manifest-path "${GATE_MANIFEST}"
      --target "${CADRUMO_PIN_rust_target}" ${GATE_ARGS} -- -D warnings)
  set_tests_properties(${name}.clippy PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" LABELS rust_quality TIMEOUT 1800)
endfunction()

# cadrumo_rust_quality(<crate> MANIFEST <Cargo.toml> [CLIPPY_CARGO <variable> [CLIPPY_ARGS <argument>...]])
#
# Registers <crate>.fmt (rustfmt check), <crate>.deny (the native/deny.toml policy over the
# crate's lockfile) and, when CLIPPY_CARGO is given, <crate>.clippy through cadrumo_rust_clippy.
# fmt and deny read no generated input, so they run under a plain cargo command rather than
# the crate's build command, which may resolve a build identity.
function(cadrumo_rust_quality crate)
  cmake_parse_arguments(PARSE_ARGV 1 GATE "" "MANIFEST;CLIPPY_CARGO" "CLIPPY_ARGS")
  if(NOT BUILD_TESTING)
    return()
  endif()
  if(NOT GATE_MANIFEST OR GATE_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR "cadrumo_rust_quality(${crate}) needs MANIFEST")
  endif()
  cadrumo_cargo_command(quality_cargo)
  add_test(NAME ${crate}.fmt
    COMMAND ${quality_cargo} fmt --check --manifest-path "${GATE_MANIFEST}")
  add_test(NAME ${crate}.deny
    COMMAND ${quality_cargo} deny --locked --manifest-path "${GATE_MANIFEST}" check
      --config "${CADRUMO_RUST_QUALITY_POLICY}" --hide-inclusion-graph advisories bans licenses sources)
  # cargo finds cargo-deny as a subcommand on PATH; put the resolved one first so the gate
  # runs the version that was checked against the floor.
  set_tests_properties(${crate}.deny PROPERTIES TIMEOUT 900
    ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:${CADRUMO_CARGO_DENY_DIRECTORY}")
  set_tests_properties(${crate}.fmt PROPERTIES TIMEOUT 900)
  set_tests_properties(${crate}.fmt ${crate}.deny PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" LABELS rust_quality)
  if(GATE_CLIPPY_CARGO)
    cadrumo_rust_clippy(${crate} MANIFEST "${GATE_MANIFEST}" CARGO ${GATE_CLIPPY_CARGO} ARGS ${GATE_CLIPPY_ARGS})
  endif()
endfunction()
