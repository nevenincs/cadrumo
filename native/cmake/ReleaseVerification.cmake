# Share one producer graph across native and extracted-artifact acceptance.
include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/BuildLog.cmake")
cadrumo_build_step(release_comment verify-release GROUP verification
  SUMMARY "run ordinary CTest tests, then verify the extracted release ZIP")
add_custom_target(verify-release
  COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>" --output-on-failure --no-tests=error -LE external_tool
  COMMAND ${CADRUMO_HELPER} run --build "${PROJECT_BINARY_DIR}" -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.artifact_verify
    --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --application-probe-command "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}"
  DEPENDS zip ${native_verification_targets}
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${release_comment}" USES_TERMINAL VERBATIM)
if(CADRUMO_PACKAGE_USER_DOCS)
  add_dependencies(verify-release user_docs_verify)
endif()
cadrumo_build_step(release_comment release GROUP package
  SUMMARY "build one bundle and ZIP and accept them as a release candidate")
add_custom_target(release DEPENDS verify-release COMMENT "${release_comment}")
