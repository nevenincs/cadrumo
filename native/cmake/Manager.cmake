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
foreach(required CADRUMO_PIN_rust_target CADRUMO_PATH_CARGO CADRUMO_HELPER CADRUMO_DEV_PYTHON
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
# The crate reads every name from these variables; it authors none itself.
cadrumo_cargo_command(manager_cargo
  --env "CADRUMO_ID_VERSION=${CADRUMO_ID_VERSION}"
  --env "CADRUMO_ID_NAME=${CADRUMO_ID_NAME}"
  --env "CADRUMO_ID_APPLICATION_ID=${CADRUMO_ID_APPLICATION_ID}"
  --env "CADRUMO_ID_MANAGER_ID=${CADRUMO_ID_MANAGER_ID}"
  --env "CADRUMO_ID_MANAGER_NAME=${CADRUMO_ID_MANAGER_NAME}")

# Cargo owns freshness, including build.rs inputs such as the embedded process manifest.
set(manager_commands
  COMMAND ${manager_cargo} build --locked --bins --manifest-path "${manager_cargo_manifest}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${manager_profile}")
if(WIN32)
  # build.rs embeds the canonical native-host manifest; reject a linked image that diverges.
  list(APPEND manager_commands
    COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.platforms.windows_manifest
      "${CADRUMO_MANAGER_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../interpreter/windows/host.manifest")
endif()
add_custom_target(rust_manager ALL ${manager_commands}
  BYPRODUCTS "${CADRUMO_MANAGER_EXECUTABLE}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)

if(BUILD_TESTING)
  # Covers the projected names, --version, and on Windows the GUI subsystem and the
  # System32-only DependentLoadFlags of the linked image.
  add_test(NAME manager.rust
    COMMAND ${manager_cargo} test --locked --manifest-path "${manager_cargo_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${manager_profile}")
  set_tests_properties(manager.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 600)
endif()
