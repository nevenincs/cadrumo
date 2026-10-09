# The interpreter and application use one assembler and the same package layout.
# Python alone needs no product wheels, desktop application or documentation.
include("${PROJECT_SOURCE_DIR}/native/cmake/CachedCommand.cmake")
set(python_distribution_inputs ${native_helper_inputs} ${contract_inputs}
  "${PROJECT_SOURCE_DIR}/native/interpreter/bootstrap.py")
string(JSON python_bootstrap GET "${package_layout}" bootstrap)
list(APPEND python_distribution_inputs "${PROJECT_SOURCE_DIR}/native/${python_bootstrap}"
  "${CADRUMO_PATH_PYTHON_SDK}" "${CADRUMO_PATH_GENERATED}/build.json"
  "${CADRUMO_PATH_GENERATED}/build-toolchain.json"
  "$<TARGET_FILE:cadrumo_python>" "$<TARGET_FILE:cadrumo_python_bridge>")
foreach(target python python_d)
  set(python_distribution_args)
  set(python_distribution_dependencies cadrumo_python cadrumo_python_bridge)
  set(python_distribution_target_inputs ${python_distribution_inputs})
  if(target STREQUAL "python_d")
    list(APPEND python_distribution_args --development)
    list(APPEND python_distribution_dependencies cadrumo_python_d)
    list(APPEND python_distribution_target_inputs "$<TARGET_FILE:cadrumo_python_d>")
  endif()
  cadrumo_cached_command(python_distribution_command ${target}
    INPUTS ${python_distribution_target_inputs}
    OUTPUTS "${CADRUMO_PATH_STAGE}/$<CONFIG>")
  add_custom_target(${target}
    COMMAND ${python_distribution_command} ${CADRUMO_HELPER} assemble
      --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>" --interpreter --without-user-docs
      ${python_distribution_args}
    DEPENDS ${python_distribution_dependencies}
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
  cadrumo_register_clean(TARGET ${target} PATHS "${CADRUMO_PATH_STAGE}/$<CONFIG>"
    DEPENDS ${python_distribution_dependencies})
endforeach()
if(BUILD_TESTING)
  add_test(NAME interpreter.python
    COMMAND "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${production_executable}"
      "${PROJECT_SOURCE_DIR}/native/tests/interpreter_smoke.py"
      "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${package_manifest}")
  set_tests_properties(interpreter.python PROPERTIES RESOURCE_LOCK package_inventory)
endif()
