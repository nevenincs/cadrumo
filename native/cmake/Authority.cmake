include_guard(GLOBAL)
# Runtime publication stays with its existing validator; CMake owns when it runs.
# The canonical compiler cache owner discovers its complete source trees on every
# invocation. Do not duplicate a narrower (and incomplete) compiler list in CMake.
set(authority_compiler_inputs
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/authority_build.py")
list(JOIN authority_compiler_inputs "\n" authority_input_lines)
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/inputs-authority-compiler.txt"
  CONTENT "${authority_input_lines}\n")
add_custom_target(registry_authority
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.authority_build
    --build "${CMAKE_BINARY_DIR}"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_dependencies(registry_authority setup-native-builder)
cadrumo_register_clean(TARGET registry_authority
  PATHS "${CADRUMO_PATH_GENERATED}/authority-compiler.txt")
