include_guard(GLOBAL)
# CMake configures its own release builder before importing project Python modules.
find_program(CADRUMO_UV NAMES uv REQUIRED)
set(CADRUMO_BUILDER_DIRECTORY "${CMAKE_BINARY_DIR}/_deps/builder")
if(CMAKE_HOST_WIN32)
  set(builder_python "${CADRUMO_BUILDER_DIRECTORY}/Scripts/python.exe")
else()
  set(builder_python "${CADRUMO_BUILDER_DIRECTORY}/bin/python")
endif()
file(READ "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version" builder_version)
string(STRIP "${builder_version}" builder_version)
set(builder_command "${CMAKE_COMMAND}" -E env
  "UV_PROJECT_ENVIRONMENT=${CADRUMO_BUILDER_DIRECTORY}" "CADRUMO_EDITABLE_AUTHORITY=skip"
  "${CADRUMO_UV}" sync --locked --python "${builder_version}")
if(NOT CADRUMO_DEV_PYTHON OR CADRUMO_DEV_PYTHON STREQUAL builder_python)
  # This included file is a regeneration prerequisite. Cleaning the interpreter
  # changes it so every subsequent build restores the builder during configure,
  # before any individual target can try to launch that interpreter.
  set(builder_state "${CMAKE_BINARY_DIR}/builder-state.cmake")
  if(NOT EXISTS "${builder_state}")
    file(WRITE "${builder_state}" "# Managed release builder is configured.\n")
  endif()
  include("${builder_state}")
  execute_process(COMMAND ${builder_command} WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}"
    COMMAND_ERROR_IS_FATAL ANY)
  set(CADRUMO_DEV_PYTHON "${builder_python}" CACHE FILEPATH "Release builder Python" FORCE)
  add_custom_target(setup-native-builder COMMAND ${builder_command}
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" VERBATIM)
  add_custom_target(clean-setup-native-builder
    COMMAND "${CMAKE_COMMAND}" "-DBUILD=${CMAKE_BINARY_DIR}" "-DSOURCE=${CMAKE_SOURCE_DIR}"
      -P "${CMAKE_CURRENT_LIST_DIR}/CleanBuilder.cmake" VERBATIM)
else()
  # Explicit interpreters are externally owned; neither setup nor clean mutates them.
  add_custom_target(setup-native-builder COMMAND "${CADRUMO_DEV_PYTHON}" -I -c
    "import platform; assert platform.python_version() == '${builder_version}', 'Release builder Python version differs'"
    VERBATIM)
  add_custom_target(clean-setup-native-builder
    COMMAND "${CMAKE_COMMAND}" -E echo
      "Release builder is externally owned: ${CADRUMO_DEV_PYTHON}. There are no owned builder artifacts to clean."
    VERBATIM)
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/pyproject.toml" "${CADRUMO_SOURCE_ROOT}/uv.lock"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version")
