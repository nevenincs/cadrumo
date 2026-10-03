file(GLOB_RECURSE product_inputs CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/src/*" "${PROJECT_SOURCE_DIR}/packaging/*")
list(FILTER product_inputs EXCLUDE REGEX "/(__pycache__|\\.git)/|\\.pyc$")
add_custom_command(OUTPUT "${PROJECT_BINARY_DIR}/product/ready"
  COMMAND ${CADRUMO_HELPER} product --build "${PROJECT_BINARY_DIR}"
  DEPENDS ${product_inputs} "${PROJECT_BINARY_DIR}/_deps/runtime/ready"
    "${PROJECT_SOURCE_DIR}/dev/packaging/native/product.py" "${CADRUMO_BUILD_HELPER}"
    "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/packaging/authority/hatch_build.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(python_product DEPENDS "${PROJECT_BINARY_DIR}/product/ready")
add_dependencies(python_product python_dependencies)
if(CADRUMO_INCLUDE_DEVELOPMENT_BINARY)
  set(development_args --development)
  set(development_target cadrumo_python_d)
endif()
add_custom_command(OUTPUT "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/ready"
  COMMAND ${CADRUMO_HELPER} assemble --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>" ${development_args}
  DEPENDS cadrumo_python cadrumo_python_bridge python_product
    ${development_target} native_metadata "${PROJECT_BINARY_DIR}/generated/build.json"
    "${PROJECT_BINARY_DIR}/product/ready" "${PROJECT_SOURCE_DIR}/native/package-layout.json"
    "${PROJECT_SOURCE_DIR}/native/interpreter/bootstrap.py" "${PROJECT_SOURCE_DIR}/dev/packaging/native/assemble.py"
    "${PROJECT_SOURCE_DIR}/dev/packaging/native/stdlib.py"
    "${CADRUMO_BUILD_HELPER}"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(bundle ALL DEPENDS "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/ready")
if(BUILD_TESTING)
  add_test(NAME bundle.python COMMAND "${CMAKE_COMMAND}" -E env
    "CADRUMO_LOCAL_STORAGE_ROOT=${PROJECT_BINARY_DIR}/testing/$<CONFIG>/storage"
    "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/python.exe" "${PROJECT_SOURCE_DIR}/native/tests/package_smoke.py")
endif()
install(DIRECTORY "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/" DESTINATION .)
set(CPACK_GENERATOR ZIP)
set(CPACK_PACKAGE_NAME CADRUMO)
set(CPACK_PACKAGE_VERSION "${CADRUMO_VERSION}")
set(CPACK_PACKAGE_VENDOR CADRUMO)
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY ON)
set(CPACK_PACKAGE_DIRECTORY "${PROJECT_BINARY_DIR}/packages")
configure_file("${PROJECT_SOURCE_DIR}/native/cmake/CPackProject.cmake.in"
  "${PROJECT_BINARY_DIR}/CPackProject.cmake" @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/CPackProject.cmake")
include(CPack)
foreach(group stage packages dependencies native all)
  add_custom_target(clean-${group}
    COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cleanup
      "${PROJECT_BINARY_DIR}" "${group}"
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
endforeach()
add_custom_target(verify
  COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>" --output-on-failure
  DEPENDS bundle platform_static_consumer platform_dll_consumer rust_platform
  USES_TERMINAL VERBATIM)
add_custom_target(zip
  COMMAND "${CMAKE_CPACK_COMMAND}" --config "${PROJECT_BINARY_DIR}/CPackConfig.cmake" -C "$<CONFIG>"
  DEPENDS bundle USES_TERMINAL VERBATIM)
