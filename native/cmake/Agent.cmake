include_guard(GLOBAL)
file(READ "${PROJECT_SOURCE_DIR}/native/agent.json" agent_pin)
string(JSON agent_revision GET "${agent_pin}" revision)
string(JSON agent_sha256 GET "${agent_pin}" sha256)
cadrumo_build_step(step_comment agent_source GROUP dependencies
  SUMMARY "acquire and checksum the private agent archive" OUTPUTS "${CADRUMO_PATH_AGENT_SOURCE}")
add_custom_target(agent_source
  COMMAND "${CMAKE_COMMAND}" "-DAGENT_OUTPUT=${CADRUMO_PATH_AGENT_SOURCE}"
    "-DAGENT_REVISION=${agent_revision}" "-DAGENT_SHA256=${agent_sha256}" -DAGENT_ARCHIVE_ONLY=ON
    -P "${PROJECT_SOURCE_DIR}/native/cmake/AgentSource.cmake"
  DEPENDS "${PROJECT_SOURCE_DIR}/native/agent.json" "${PROJECT_SOURCE_DIR}/native/cmake/AgentSource.cmake"
  BYPRODUCTS "${CADRUMO_PATH_AGENT_SOURCE}/source.tar.gz" "${CADRUMO_PATH_AGENT_SOURCE}/source.sha256"
  COMMENT "${step_comment}" VERBATIM)
cadrumo_register_clean(TARGET agent_source PATHS "${CADRUMO_PATH_AGENT_SOURCE}")
set(agent_inputs "${PROJECT_SOURCE_DIR}/native/agent.json"
  "${CADRUMO_PATH_AGENT_SOURCE}/source.tar.gz"
  "${PROJECT_SOURCE_DIR}/native/cmake/AgentSource.cmake"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/agent.py"
  ${shared_inputs} "${CMAKE_COMMAND}")
list(JOIN agent_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-agent.txt" CONTENT "${input_lines}\n")
cadrumo_build_step(step_comment agent_project GROUP dependencies
  SUMMARY "acquire the SHA-256-pinned private agent source and build its wheel"
  OUTPUTS "${CADRUMO_PATH_AGENT}")
add_custom_target(agent_project
  COMMAND ${CADRUMO_HELPER} agent --build "${PROJECT_BINARY_DIR}"
    --inputs "${PROJECT_BINARY_DIR}/inputs-agent.txt" --cmake "${CMAKE_COMMAND}"
  DEPENDS ${agent_inputs} WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
  BYPRODUCTS "${CADRUMO_PATH_AGENT}/ready" "${CADRUMO_PATH_AGENT}/agent-wheel.json"
  COMMENT "${step_comment}" VERBATIM)
add_dependencies(agent_project agent_source)
cadrumo_register_clean(TARGET agent_project PATHS "${CADRUMO_PATH_AGENT}")
cadrumo_build_step(step_comment agent-checksum GROUP verification
  SUMMARY "verify the built agent wheel against its pinned source and checksum")
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
