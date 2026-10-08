# Every C interpreter host independently holds its installed version in use.
# The ABI bridge depends on the shared application owner, avoiding a reverse
# platform -> application dependency and a second publication-state parser.
include_guard(GLOBAL)
set(launch_guard_source "${PROJECT_SOURCE_DIR}/native/launch_guard")
set(launch_guard_library
  "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/$<IF:$<CONFIG:Debug>,debug,release>/${CMAKE_STATIC_LIBRARY_PREFIX}cadrumo_launch_guard${CMAKE_STATIC_LIBRARY_SUFFIX}")
cadrumo_cargo_command(launch_guard_cargo
  --env "CADRUMO_NATIVE_CONTRACT=${CONTRACT_DIR}/contract.json")
add_custom_target(rust_launch_guard
  COMMAND ${launch_guard_cargo} build --locked --lib
    --manifest-path "${launch_guard_source}/Cargo.toml"
    --target "${CADRUMO_PIN_rust_target}" --profile "$<IF:$<CONFIG:Debug>,dev,release>"
  BYPRODUCTS "${launch_guard_library}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_dependencies(rust_launch_guard native_contract)
foreach(target cadrumo_python cadrumo_python_d ${CADRUMO_ENTRYPOINT_TARGETS})
  target_include_directories(${target} PRIVATE
    "${launch_guard_source}/include" "${PROJECT_SOURCE_DIR}/native/interpreter")
  target_link_libraries(${target} PRIVATE "${launch_guard_library}")
  add_dependencies(${target} rust_launch_guard)
endforeach()
if(COMMAND cadrumo_register_clean)
  cadrumo_register_clean(TARGET rust_launch_guard PATHS "${launch_guard_library}")
endif()
if(BUILD_TESTING)
  foreach(target cadrumo_python cadrumo_python_d)
    add_test(NAME launch_guard.${target}
      COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.launch_guard_check
        --executable "$<TARGET_FILE:${target}>" --contract "${CONTRACT_DIR}/contract.json")
    set_tests_properties(launch_guard.${target} PROPERTIES
      WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 0)
  endforeach()
  add_test(NAME launch_guard.rust
    COMMAND ${launch_guard_cargo} test --locked
      --manifest-path "${launch_guard_source}/Cargo.toml"
      --target "${CADRUMO_PIN_rust_target}" --profile "$<IF:$<CONFIG:Debug>,dev,release>")
  set_tests_properties(launch_guard.rust PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" TIMEOUT 0)
endif()
