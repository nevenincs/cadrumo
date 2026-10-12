include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/BuildLog.cmake")
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
  message(CHECK_START "Converging the managed release builder Python ${builder_version} (uv sync --locked)")
  execute_process(COMMAND ${builder_command} WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}"
    RESULT_VARIABLE builder_result OUTPUT_VARIABLE builder_output ERROR_VARIABLE builder_output)
  if(NOT builder_result EQUAL 0)
    message(CHECK_FAIL "uv sync exited with ${builder_result}")
    message(FATAL_ERROR "The managed release builder could not be converged:\n${builder_output}")
  endif()
  message(CHECK_PASS "${builder_python}")
  string(STRIP "${builder_output}" builder_output)
  string(REPLACE "\n" ";" builder_output "${builder_output}")
  foreach(line IN LISTS builder_output)
    message(VERBOSE "${line}")
  endforeach()
  set(CADRUMO_DEV_PYTHON "${builder_python}" CACHE FILEPATH "Release builder Python" FORCE)
  cadrumo_build_fact("Builder Python" "${builder_version}, managed: ${CADRUMO_DEV_PYTHON}")
  cadrumo_build_step(builder_comment setup-native-builder GROUP builder
    SUMMARY "converge the managed release builder Python ${builder_version}"
    OUTPUTS "${CADRUMO_BUILDER_DIRECTORY}")
  add_custom_target(setup-native-builder COMMAND ${builder_command}
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" COMMENT "${builder_comment}" VERBATIM)
  add_custom_target(clean-setup-native-builder
    COMMAND "${CMAKE_COMMAND}" "-DBUILD=${CMAKE_BINARY_DIR}" "-DSOURCE=${CMAKE_SOURCE_DIR}"
      -P "${CMAKE_CURRENT_LIST_DIR}/CleanBuilder.cmake" VERBATIM)
else()
  # Explicit interpreters are externally owned; neither setup nor clean mutates them.
  cadrumo_build_fact("Builder Python" "${builder_version}, external: ${CADRUMO_DEV_PYTHON}")
  cadrumo_build_step(builder_comment setup-native-builder GROUP builder
    SUMMARY "check that the external builder Python is ${builder_version}")
  add_custom_target(setup-native-builder COMMAND "${CADRUMO_DEV_PYTHON}" -I -c
    "import platform; assert platform.python_version() == '${builder_version}', 'Release builder Python version differs'"
    COMMENT "${builder_comment}" VERBATIM)
  add_custom_target(clean-setup-native-builder
    COMMAND "${CMAKE_COMMAND}" -E echo
      "[cadrumo:clean-setup-native-builder] Release builder is externally owned: ${CADRUMO_DEV_PYTHON}. There are no owned builder artifacts to clean."
    VERBATIM)
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/pyproject.toml" "${CADRUMO_SOURCE_ROOT}/uv.lock"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version")
