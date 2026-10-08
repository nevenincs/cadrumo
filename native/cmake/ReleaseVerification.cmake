# Share one producer graph across native and extracted-artifact acceptance.
include_guard(GLOBAL)
add_custom_target(verify-release
  COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>" --output-on-failure
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.artifact_verify
    --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --application-probe-command "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}"
  DEPENDS zip ${native_verification_targets}
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
