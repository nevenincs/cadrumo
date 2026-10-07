cadrumo_cargo_command(application_cargo
  --env "CADRUMO_CONTRACT_RS=${CONTRACT_DIR}/contract.rs")
set(application_manifest "${CMAKE_CURRENT_SOURCE_DIR}/Cargo.toml")
set(application_profile "$<IF:$<CONFIG:Debug>,dev,release>")
set(application_output "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/libcadrumo_application.rlib")
string(JSON application_layout_abi GET "${package_layout}" abi)
cadrumo_cargo_command(application_artifact_probe
  --env "CADRUMO_CONTRACT_RS=${CONTRACT_DIR}/contract.rs"
  --env "CADRUMO_TEST_PACKAGE_MANIFEST=${package_manifest}"
  --env "CADRUMO_TEST_PACKAGE_PLATFORM=${CADRUMO_PLATFORM}"
  --env "CADRUMO_TEST_PACKAGE_ABI=${application_layout_abi}")
list(APPEND application_artifact_probe test --locked --manifest-path "${application_manifest}"
  --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}"
  --features live-release-tests --test live_package -- --nocapture)
# Serialize argv without shell quoting; the verifier supplies the extracted package root.
set(probe_json "[]")
set(probe_index 0)
foreach(argument IN LISTS application_artifact_probe)
  string(REPLACE "\\" "\\\\" argument "${argument}")
  string(REPLACE "\"" "\\\"" argument "${argument}")
  string(JSON probe_json SET "${probe_json}" ${probe_index} "\"${argument}\"")
  math(EXPR probe_index "${probe_index} + 1")
endforeach()
set(probe_file "${CMAKE_CURRENT_BINARY_DIR}/artifact-probe-$<CONFIG>.json")
file(GENERATE OUTPUT "${probe_file}" CONTENT "${probe_json}\n")
set(CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE "${probe_file}" PARENT_SCOPE)

# Always ask Cargo to check freshness, including include_str!, lockfile and transitive inputs.
# The rlib is not a runtime payload and must not be copied into the Python package.
add_custom_target(rust_application ALL
  COMMAND ${application_cargo} build --locked --lib --manifest-path "${application_manifest}"
    --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}" --features platform
  BYPRODUCTS "${application_output}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_dependencies(rust_application native_contract)
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_application PATHS "${application_output}")
endif()

if(BUILD_TESTING)
  set(CADRUMO_APPLICATION_TEST_PACKAGE_ROOT "${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
    CACHE STRING "Package root for Rust compatibility acceptance; defaults to the staged configuration")
  if(NOT IS_ABSOLUTE "${CADRUMO_APPLICATION_TEST_PACKAGE_ROOT}")
    message(FATAL_ERROR "CADRUMO_APPLICATION_TEST_PACKAGE_ROOT must be absolute")
  endif()
  add_test(NAME application.rust
    COMMAND ${application_cargo} test --locked --manifest-path "${application_manifest}"
      --target "${CADRUMO_PIN_rust_target}" --profile "${application_profile}" --features platform)
  set_tests_properties(application.rust PROPERTIES WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 600)
  cadrumo_cargo_command(application_package_cargo
    --env "CADRUMO_CONTRACT_RS=${CONTRACT_DIR}/contract.rs"
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
