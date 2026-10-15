include_guard(GLOBAL)
# The folder is selected by this cache variable alone. The process environment is never read, so
# no environment name carries the selection into the build or its child processes.
set(CADRUMO_PACKAGE_AGENT_SOURCE_DIR "" CACHE PATH "Local cadrumo-agent project directory; set with -D or a CMake user preset")
if("${CADRUMO_PACKAGE_AGENT_SOURCE_DIR}" STREQUAL "")
  message(FATAL_ERROR "The CMake cache variable CADRUMO_PACKAGE_AGENT_SOURCE_DIR is not set. "
    "Configure with -DCADRUMO_PACKAGE_AGENT_SOURCE_DIR=<cadrumo-agent project folder> or set it in a CMake user preset; the environment is not consulted.")
endif()
if(NOT EXISTS "${CADRUMO_PACKAGE_AGENT_SOURCE_DIR}/pyproject.toml")
  message(FATAL_ERROR "The CMake cache variable CADRUMO_PACKAGE_AGENT_SOURCE_DIR is \"${CADRUMO_PACKAGE_AGENT_SOURCE_DIR}\", which holds no pyproject.toml. "
    "Set it to the cadrumo-agent project folder.")
endif()
get_filename_component(agent_source "${CADRUMO_PACKAGE_AGENT_SOURCE_DIR}" ABSOLUTE BASE_DIR "${PROJECT_SOURCE_DIR}")
file(GLOB_RECURSE agent_source_inputs CONFIGURE_DEPENDS "${agent_source}/src/*")
foreach(agent_file pyproject.toml README.md LICENSE NOTICE .gitignore package.json package-lock.json .node-version)
  if(EXISTS "${agent_source}/${agent_file}")
    list(APPEND agent_source_inputs "${agent_source}/${agent_file}")
  endif()
endforeach()
list(FILTER agent_source_inputs EXCLUDE REGEX "/(tests|testing|service_tests|capability_tests|acceptance|\\.pytest[^/]*|\\.git|\\.venv|__pycache__|dist|build|\\.tmp[^/]*)/|/src/cadrumo_agent/conftest\\.py$|\\.pyc$")
set(agent_inputs ${agent_source_inputs}
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/agent.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/agent_runtime.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/archive.py"
  "${PROJECT_SOURCE_DIR}/native/agent/runtime.json"
  "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/uv.lock"
  ${shared_inputs} "${CMAKE_COMMAND}")
list(JOIN agent_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-agent.txt" CONTENT "${input_lines}\n")
cadrumo_build_step(step_comment agent_project GROUP dependencies
  SUMMARY "build the agent wheel and its pinned Node/ACP runtime from the configured project folder"
  OUTPUTS "${CADRUMO_PATH_AGENT}")
add_custom_target(agent_project
  COMMAND ${CADRUMO_HELPER} agent --build "${PROJECT_BINARY_DIR}"
    --inputs "${PROJECT_BINARY_DIR}/inputs-agent.txt" --agent-source "${agent_source}"
  DEPENDS ${agent_inputs} WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  BYPRODUCTS "${CADRUMO_PATH_AGENT}/ready" "${CADRUMO_PATH_AGENT}/agent-wheel.json"
  COMMENT "${step_comment}" VERBATIM)
cadrumo_register_clean(TARGET agent_project PATHS "${CADRUMO_PATH_AGENT}")
cadrumo_build_step(step_comment agent-checksum GROUP verification
  SUMMARY "verify the built agent wheel checksum")
add_custom_target(agent-checksum
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.agent checksum --build "${PROJECT_BINARY_DIR}"
  DEPENDS agent_project WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
foreach(agent_target windows-x86-64 linux-x86-64 linux-aarch64 macos-arm64)
  cadrumo_build_step(step_comment "agent-lock-${agent_target}" GROUP dependencies
    SUMMARY "explicitly update the agent dependency lock for ${agent_target}")
  add_custom_target("agent-lock-${agent_target}"
    COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.agent lock
      --build "${PROJECT_BINARY_DIR}" --target "${agent_target}"
    DEPENDS agent_project WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
  cadrumo_register_clean(TARGET "agent-lock-${agent_target}"
    PATHS "${CADRUMO_PATH_TESTING}/agent-lock/${agent_target}")
endforeach()
cadrumo_build_step(step_comment agent-rebuild GROUP dependencies
  SUMMARY "remove the agent and dependent payloads, then rebuild the application bundle")
add_custom_target(agent-rebuild
  COMMAND "${CMAKE_COMMAND}" --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --target clean-agent_project clean-python_product clean-bundle
  COMMAND "${CMAKE_COMMAND}" --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>" --target bundle
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
