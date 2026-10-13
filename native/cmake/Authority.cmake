include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/BuildLog.cmake")
# An existing publication is an explicit developer selection, not a compiler cache.
cadrumo_build_step(authority_comment registry_authority GROUP builder
  SUMMARY "publish the registry authority when it is missing or stale (shared checkout state)")
add_custom_target(registry_authority
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${authority_comment}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority setup-native-builder)
cadrumo_build_step(authority_comment registry_authority_rebuild GROUP builder
  SUMMARY "recompile and republish the registry authority (shared checkout state)")
add_custom_target(registry_authority_rebuild
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}" --rebuild
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${authority_comment}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority_rebuild setup-native-builder)
foreach(target registry_authority registry_authority_rebuild)
  add_custom_target("clean-${target}"
    COMMAND "${CMAKE_COMMAND}" -E echo
      "[cadrumo:clean-${target}] Authority publication is shared checkout state; no binary-directory artifact to clean. Use registry_authority_rebuild to replace it."
    VERBATIM)
endforeach()
