# Snapshot callers supply the identifier captured from the authoring revision.
# Derive it only when configuring directly from a version-controlled checkout.
if(NOT DEFINED CADRUMO_BUILD_NUMBER)
  execute_process(COMMAND git rev-list --count HEAD WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
    OUTPUT_VARIABLE build_number OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  set(CADRUMO_BUILD_NUMBER "${build_number}" CACHE STRING "Numeric build identifier")
endif()
