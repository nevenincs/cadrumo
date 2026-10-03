file(GLOB_RECURSE product_inputs CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/src/*" "${PROJECT_SOURCE_DIR}/packaging/*"
  "${PROJECT_SOURCE_DIR}/dev/packaging/*.py"
  "${PROJECT_SOURCE_DIR}/dev/registry/*.py"
  "${PROJECT_SOURCE_DIR}/dev/corpus/*.py"
  "${PROJECT_SOURCE_DIR}/dev/docs/preprocess/*.py"
  "${PROJECT_SOURCE_DIR}/dev/.gitattributes"
  "${PROJECT_SOURCE_DIR}/dev/.gitignore")
list(FILTER product_inputs EXCLUDE REGEX "/(__pycache__|\\.git)/|\\.pyc$|\\.lock$|/\\.aeat-generated-export-transaction-|/\\.generated-export-(backup|stage)-")
list(FILTER product_inputs EXCLUDE REGEX "/dev/packaging/native/|/dev/.*/tests/")
list(APPEND product_inputs
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/product.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/hashing.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/cmake_build.py"
  "${PROJECT_SOURCE_DIR}/dev/packaging/native/action_cache.py")
foreach(name README.md LICENSE NOTICE pyproject.toml uv.lock .gitignore .gitattributes dev/source_tree.py dev/_paths.py
    dev/__init__.py dev/docs/__init__.py dev/cache_root.py)
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
add_dependencies(bundle rust_application)
if(BUILD_TESTING)
  add_test(NAME bundle.python COMMAND "${CMAKE_COMMAND}" -E env
    "CADRUMO_LOCAL_STORAGE_ROOT=${PROJECT_BINARY_DIR}/testing/$<CONFIG>/storage"
    "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/${CADRUMO_PACKAGE_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/native/tests/package_smoke.py" "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app"
    "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/${CADRUMO_PACKAGE_MANIFEST}")
  set_tests_properties(bundle.python PROPERTIES RESOURCE_LOCK package_inventory)
endif()
install(DIRECTORY "${PROJECT_BINARY_DIR}/stage/$<CONFIG>/app/" DESTINATION .)
set(CPACK_GENERATOR ZIP)
set(CPACK_VERBATIM_VARIABLES YES)
set(CPACK_PACKAGE_NAME "${CADRUMO_ID_NAME}")
set(CPACK_PACKAGE_VERSION "${CADRUMO_VERSION}")
set(CPACK_PACKAGE_VENDOR "${CADRUMO_ID_PUBLISHER}")
set(CPACK_PACKAGE_CONTACT "${CADRUMO_ID_CONTACT}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "${CADRUMO_ID_DESCRIPTION}")
set(CPACK_PACKAGE_HOMEPAGE_URL "${CADRUMO_ID_HOMEPAGE}")
set(CPACK_RESOURCE_FILE_LICENSE "${PROJECT_SOURCE_DIR}/LICENSE")
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY ON)
set(CPACK_PACKAGE_DIRECTORY "${PROJECT_BINARY_DIR}/packages")
set(CADRUMO_ARTIFACT_STEM "${CADRUMO_ID_PACKAGE_NAME}-${CADRUMO_VERSION}-b${CADRUMO_BUILD_NUMBER}-${CADRUMO_PLATFORM}")
configure_file("${PROJECT_SOURCE_DIR}/native/cmake/CPackProject.cmake.in"
  "${PROJECT_BINARY_DIR}/CPackProject.cmake" @ONLY)
configure_file("${PROJECT_SOURCE_DIR}/native/cmake/Artifact.cmake.in"
  "${PROJECT_BINARY_DIR}/Artifact.cmake" @ONLY)
set(CPACK_POST_BUILD_SCRIPTS "${PROJECT_BINARY_DIR}/Artifact.cmake")
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
  DEPENDS bundle platform_static_consumer platform_dll_consumer rust_platform rust_application
  USES_TERMINAL VERBATIM)
add_custom_target(zip
  COMMAND "${CMAKE_CPACK_COMMAND}" --config "${PROJECT_BINARY_DIR}/CPackConfig.cmake" -C "$<CONFIG>"
  DEPENDS bundle USES_TERMINAL VERBATIM)
add_custom_target(verify-package
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.artifact_verify
    --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --application-probe-command "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}"
  DEPENDS zip WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" USES_TERMINAL VERBATIM)
