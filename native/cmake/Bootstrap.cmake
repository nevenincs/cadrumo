include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/BuildLog.cmake")
# Tool installation is an operator prerequisite, never a build side effect.
find_program(CADRUMO_UV NAMES uv REQUIRED)
if(CADRUMO_DEV_PYTHON MATCHES "[/\\\\]_deps[/\\\\]builder[/\\\\]")
  unset(CADRUMO_DEV_PYTHON CACHE)
  unset(CADRUMO_DEV_PYTHON)
endif()
if(NOT CADRUMO_DEV_PYTHON)
  execute_process(COMMAND "${CADRUMO_UV}" python find --no-python-downloads
    WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}"
    OUTPUT_VARIABLE existing_python OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE python_result ERROR_VARIABLE python_error)
  if(NOT python_result EQUAL 0 OR NOT EXISTS "${existing_python}")
    message(FATAL_ERROR "Select an existing development interpreter with CADRUMO_DEV_PYTHON. CMake does not create Python environments.\n${python_error}")
  endif()
  set(CADRUMO_DEV_PYTHON "${existing_python}" CACHE FILEPATH "Existing development Python" FORCE)
endif()
file(READ "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version" builder_version)
string(STRIP "${builder_version}" builder_version)
set(builder_check "import sys; required=tuple(map(int, '${builder_version}'.split('.'))); assert sys.version_info[:2] == required[:2] and sys.version_info[:3] >= required, 'Builder requires compatible CPython >= ${builder_version}'; import hatchling, packaging, pydantic")
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -I -B -c "${builder_check}"
  RESULT_VARIABLE builder_result ERROR_VARIABLE builder_error)
if(NOT builder_result EQUAL 0)
  message(FATAL_ERROR "Existing development Python is not ready. Provision developer dependencies outside the build, then retry:\n${builder_error}")
endif()
cadrumo_build_fact("Builder Python" "externally owned: ${CADRUMO_DEV_PYTHON}")
cadrumo_build_step(builder_comment setup-native-builder GROUP builder
  SUMMARY "validate the existing development interpreter without installing dependencies")
add_custom_target(setup-native-builder COMMAND "${CADRUMO_DEV_PYTHON}" -I -B -c "${builder_check}"
  COMMENT "${builder_comment}" VERBATIM)
add_custom_target(clean-setup-native-builder COMMAND "${CMAKE_COMMAND}" -E echo
  "[cadrumo:clean-setup-native-builder] Development tools are externally owned; nothing to clean."
  VERBATIM)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/pyproject.toml" "${CADRUMO_SOURCE_ROOT}/uv.lock"
  "${CADRUMO_SOURCE_ROOT}/dev/packaging/release-python-version")
