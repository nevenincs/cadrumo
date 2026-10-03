cadrumo_cargo_command(application_cargo)
set(application_manifest "${CMAKE_CURRENT_SOURCE_DIR}/Cargo.toml")
set(application_profile "$<IF:$<CONFIG:Debug>,dev,release>")
set(application_output "${PROJECT_BINARY_DIR}/cargo/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/libcadrumo_application.rlib")

# Always ask Cargo to check freshness, including include_str!, lockfile and transitive inputs.
# The rlib is not a runtime payload and must not be copied into the Python package.
add_custom_target(rust_application ALL
  COMMAND ${application_cargo} build --locked --lib --manifest-path "${application_manifest}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}"
  BYPRODUCTS "${application_output}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)

if(BUILD_TESTING)
  string(JSON application_layout_abi GET "${package_layout}" abi)
  set(CADRUMO_APPLICATION_TEST_PACKAGE_ROOT "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app"
    CACHE STRING "Package root for Rust compatibility acceptance; defaults to the staged configuration")
  if(NOT IS_ABSOLUTE "${CADRUMO_APPLICATION_TEST_PACKAGE_ROOT}")
    message(FATAL_ERROR "CADRUMO_APPLICATION_TEST_PACKAGE_ROOT must be absolute")
  endif()
  add_test(NAME application.rust
    COMMAND ${application_cargo} test --locked --manifest-path "${application_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}")
  set_tests_properties(application.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 600)
  cadrumo_cargo_command(application_package_cargo
    --env "CADRUMO_TEST_PACKAGE_ROOT=${CADRUMO_APPLICATION_TEST_PACKAGE_ROOT}"
    --env "CADRUMO_TEST_PACKAGE_MANIFEST=${package_manifest}"
    --env "CADRUMO_TEST_PACKAGE_PLATFORM=${CADRUMO_PLATFORM}"
    --env "CADRUMO_TEST_PACKAGE_ABI=${application_layout_abi}")
  add_test(NAME application.package
    COMMAND ${application_package_cargo} test --locked --manifest-path "${application_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}"
      --features live-package-tests --test live_package -- --nocapture)
  set_tests_properties(application.package PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    TIMEOUT 900 RESOURCE_LOCK package_inventory)
endif()
