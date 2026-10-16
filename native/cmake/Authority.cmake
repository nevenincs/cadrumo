include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/BuildLog.cmake")
# An existing publication is an explicit developer selection, not a compiler cache.
cadrumo_build_step(authority_comment registry_authority GROUP builder
  SUMMARY "validate the existing registry authority without changing checkout state")
add_custom_target(registry_authority
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${authority_comment}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority setup-native-builder)
add_custom_target(clean-registry_authority
  COMMAND "${CMAKE_COMMAND}" -E echo
    "[cadrumo:clean-registry_authority] Published authority is an external build input; nothing to clean."
  VERBATIM)
