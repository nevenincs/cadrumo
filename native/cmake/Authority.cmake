include_guard(GLOBAL)
# An existing publication is an explicit developer selection, not a compiler cache.
add_custom_target(registry_authority
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority setup-native-builder)
add_custom_target(registry_authority_rebuild
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}" --rebuild
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority_rebuild setup-native-builder)
foreach(target registry_authority registry_authority_rebuild)
  add_custom_target("clean-${target}"
    COMMAND "${CMAKE_COMMAND}" -E echo
      "Authority publication is shared checkout state; no binary-directory artifact to clean. Use registry_authority_rebuild to replace it."
    VERBATIM)
endforeach()
