file(GLOB_RECURSE product_inputs CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/src/*" "${PROJECT_SOURCE_DIR}/packaging/*"
  "${PROJECT_SOURCE_DIR}/dev/packaging/*.py")
list(FILTER product_inputs EXCLUDE REGEX "/(__pycache__|\\.git)/|\\.pyc$|\\.lock$|/\\.aeat-generated-export-transaction-")
foreach(name README.md LICENSE NOTICE pyproject.toml uv.lock dev/source_tree.py dev/_paths.py)
  if(EXISTS "${PROJECT_SOURCE_DIR}/${name}")
    list(APPEND product_inputs "${PROJECT_SOURCE_DIR}/${name}")
  endif()
endforeach()
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "from dev.packaging.authority_staging import selected_published_authority; from dev._paths import REPO_ROOT; print(';'.join(p.resolve().as_posix() for p in selected_published_authority(REPO_ROOT)))"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE authority_inputs
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${authority_inputs})
list(APPEND product_inputs ${authority_inputs} "${PROJECT_BINARY_DIR}/_deps/runtime/ready")
list(JOIN product_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-product.txt" CONTENT "${input_lines}\n")
add_custom_command(OUTPUT "${PROJECT_BINARY_DIR}/product/ready"
  COMMAND ${CADRUMO_HELPER} product --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-product.txt"
  DEPENDS ${product_inputs} "${PROJECT_BINARY_DIR}/inputs-product.txt"
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
    ${native_helper_inputs} ${contract_inputs}
    "${PROJECT_SOURCE_DIR}/native/interpreter/${CADRUMO_BACKEND}/bootstrap.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(bundle ALL DEPENDS "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/ready")
if(BUILD_TESTING)
  add_test(NAME bundle.python COMMAND "${CMAKE_COMMAND}" -E env
    "CADRUMO_LOCAL_STORAGE_ROOT=${PROJECT_BINARY_DIR}/testing/$<CONFIG>/storage"
    "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/${CADRUMO_PACKAGE_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/native/tests/package_smoke.py" "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app"
    "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/${CADRUMO_PACKAGE_MANIFEST}")
endif()
install(DIRECTORY "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/" DESTINATION .)
set(CPACK_GENERATOR ZIP)
set(CPACK_PACKAGE_NAME CADRUMO)
set(CPACK_PACKAGE_VERSION "${CADRUMO_VERSION}")
set(CPACK_PACKAGE_VENDOR CADRUMO)
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY ON)
set(CPACK_PACKAGE_DIRECTORY "${PROJECT_BINARY_DIR}/packages")
set(CADRUMO_ARTIFACT_STEM "CADRUMO-${CADRUMO_VERSION}-b${CADRUMO_BUILD_NUMBER}-${CADRUMO_PLATFORM}")
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/artifacts-$<CONFIG>.json" CONTENT
  "{\"archive\":\"${PROJECT_BINARY_DIR}/packages/$<CONFIG>/${CADRUMO_ARTIFACT_STEM}-$<CONFIG>.zip\",\"configuration\":\"$<CONFIG>\",\"development_binary\":$<BOOL:${CADRUMO_INCLUDE_DEVELOPMENT_BINARY}>}\n")
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
add_custom_target(verify-package
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.artifact_verify
    --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
  DEPENDS zip WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
