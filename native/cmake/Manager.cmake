# Builds the per-user runtime manager image (native/manager, Cargo package cadrumo-manager).
#
# Include point: native/CMakeLists.txt, after Rust.cmake and the platform adapter
# platforms/${CMAKE_SYSTEM_NAME}.cmake, for example directly after add_subdirectory(application).
# Those supply cadrumo_cargo_command, the pinned Rust environment and CADRUMO_HELPER; the root
# Identity.cmake supplies the CADRUMO_ID_* projection. Package placement, verification and
# signing of the image belong to the including packaging owner, which consumes
# CADRUMO_MANAGER_EXECUTABLE and the rust_manager target.
include_guard(GLOBAL)
if(NOT COMMAND cadrumo_cargo_command)
  message(FATAL_ERROR "Include Rust.cmake and the platform adapter before Manager.cmake")
endif()
foreach(required CADRUMO_PIN_rust_target CADRUMO_PATH_CARGO CADRUMO_HELPER CADRUMO_DEV_PYTHON CONTRACT_DIR
    CADRUMO_ID_VERSION CADRUMO_ID_NAME CADRUMO_ID_APPLICATION_ID CADRUMO_ID_MANAGER_ID CADRUMO_ID_MANAGER_NAME)
  if(NOT DEFINED ${required} OR "${${required}}" STREQUAL "")
    message(FATAL_ERROR "Manager.cmake requires ${required}")
  endif()
endforeach()

get_filename_component(manager_source "${CMAKE_CURRENT_LIST_DIR}/../manager" ABSOLUTE)
set(manager_cargo_manifest "${manager_source}/Cargo.toml")
set(manager_profile "$<IF:$<CONFIG:Debug>,dev,release>")
set(CADRUMO_MANAGER_EXECUTABLE
  "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/cadrumo-manager${CMAKE_EXECUTABLE_SUFFIX}")
# The crate reads every name from these variables, and the runtime protocol from the generated
# contract; it authors none of them itself.
cadrumo_cargo_command(manager_cargo
  --env "CADRUMO_TEST_PYTHON=${CADRUMO_DEV_PYTHON}"
  --env "CADRUMO_CONTRACT_RS=${CONTRACT_DIR}/contract.rs"
  --env "CADRUMO_ID_VERSION=${CADRUMO_ID_VERSION}"
  --env "CADRUMO_ID_NAME=${CADRUMO_ID_NAME}"
  --env "CADRUMO_ID_APPLICATION_ID=${CADRUMO_ID_APPLICATION_ID}"
  --env "CADRUMO_ID_MANAGER_ID=${CADRUMO_ID_MANAGER_ID}"
  --env "CADRUMO_ID_MANAGER_NAME=${CADRUMO_ID_MANAGER_NAME}")

set(manager_manifest_check)
if(WIN32)
  # build.rs embeds the canonical native-host manifest; reject a linked image that diverges.
  set(manager_manifest_check
    COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.platforms.windows_manifest
      "${CADRUMO_MANAGER_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../interpreter/windows/host.manifest")
endif()
# Cargo owns freshness, including build.rs inputs such as the embedded process manifest.
# manager_cargo expands only here and in add_test: copying it into another list would split
# the escaped semicolons of its LIB and INCLUDE values.
add_custom_target(rust_manager ALL
  COMMAND ${manager_cargo} build --locked --bins --manifest-path "${manager_cargo_manifest}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${manager_profile}"
  ${manager_manifest_check}
  BYPRODUCTS "${CADRUMO_MANAGER_EXECUTABLE}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_dependencies(rust_manager native_contract)
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_manager PATHS "${CADRUMO_MANAGER_EXECUTABLE}")
endif()

if(BUILD_TESTING)
  # Covers the projected names, --version, and on Windows the GUI subsystem, the
  # System32-only DependentLoadFlags and the version resource of the linked image.
  add_test(NAME manager.rust
    COMMAND ${manager_cargo} test --locked --manifest-path "${manager_cargo_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${manager_profile}")
  set_tests_properties(manager.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 0)
  # Fixture supervision builds with the fixture feature into its own target directory, so it
  # never replaces the image the package stages from CADRUMO_MANAGER_EXECUTABLE.
  # These Windows cases launch real processes against short timing bounds; avoid
  # imposing the fixture suite's own concurrent process load on those bounds.
  add_test(NAME manager.supervision
    COMMAND ${manager_cargo} test --locked --features fixture-test-mode --profile dev
      --target-dir "${CADRUMO_PATH_CARGO}/manager-fixture" --manifest-path "${manager_cargo_manifest}"
      --target "${CADRUMO_PIN_rust_target}" -- --test-threads=1)
  set_tests_properties(manager.supervision PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 0)
endif()
