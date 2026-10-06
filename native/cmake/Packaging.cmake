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
list(APPEND product_inputs ${authority_inputs} "${CADRUMO_PATH_RUNTIME}/ready")
list(JOIN product_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-product.txt" CONTENT "${input_lines}\n")
add_custom_target(python_product
  # Always run the Python admission check: it loads env/.env or inherited CI
  # credentials and binds cache reuse to their digest without CMake variables.
  COMMAND ${CADRUMO_HELPER} product --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-product.txt"
  DEPENDS ${product_inputs} "${PROJECT_BINARY_DIR}/inputs-product.txt"
  BYPRODUCTS "${CADRUMO_PATH_PRODUCT}/ready"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_dependencies(python_product python_dependencies)
if(CADRUMO_INCLUDE_DEVELOPMENT_BINARY)
  set(development_args --development)
  set(development_target cadrumo_python_d)
endif()
include("${PROJECT_SOURCE_DIR}/native/cmake/Docs.cmake")
option(CADRUMO_PACKAGE_USER_DOCS "Bundle the user documentation in the assembled package" ON)
if(CADRUMO_PACKAGE_USER_DOCS)
  set(user_docs_dependencies user_docs "${CADRUMO_PATH_USER_DOCS_STAGE}/ready")
  message(STATUS "User documentation: bundled in the package (CADRUMO_PACKAGE_USER_DOCS=ON)")
else()
  set(user_docs_args --without-user-docs)
  message(STATUS "User documentation: absent from the package; desktop payloads refuse it (CADRUMO_PACKAGE_USER_DOCS=OFF)")
endif()
# Application images are native executables that are not interpreter hosts, declared by the
# platform mapping. Each names its CMake target and the variable that holds its artifact path,
# defined in this scope or the native directory's; the layout owner decides which images stage.
if(CADRUMO_PACKAGE_USER_DOCS)
  set(images_with_docs True)
else()
  set(images_with_docs False)
endif()
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import json; from dataclasses import asdict; from dev.packaging.native.layout import application_images, load_layout, staged_application_images; layout = load_layout(); staged = staged_application_images(layout, user_docs=${images_with_docs}); print(json.dumps([dict(asdict(image), package_path=image.package_path, staged=image in staged) for image in application_images(layout)]))"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE application_images
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
# The desktop project defines desktop-host-build and the variable naming its host image.
# It needs Node.js and npm, so it is configured only when a desktop image is staged.
set(desktop_image_staged FALSE)
string(JSON image_count LENGTH "${application_images}")
if(image_count GREATER 0)
  math(EXPR image_last "${image_count} - 1")
  foreach(index RANGE ${image_last})
    string(JSON image_desktop GET "${application_images}" ${index} desktop)
    string(JSON image_staged GET "${application_images}" ${index} staged)
    if(image_desktop AND image_staged)
      set(desktop_image_staged TRUE)
    endif()
  endforeach()
endif()
if(desktop_image_staged)
  message(STATUS "Desktop application: configured; a desktop image is staged")
  add_subdirectory("${PROJECT_SOURCE_DIR}/native/desktop" "${PROJECT_BINARY_DIR}/native/desktop")
else()
  message(STATUS "Desktop application: not configured; no desktop image is staged")
endif()
set(application_image_args)
set(application_image_dependencies)
string(JSON image_count LENGTH "${application_images}")
if(image_count GREATER 0)
  math(EXPR image_last "${image_count} - 1")
  foreach(index RANGE ${image_last})
    foreach(key file target artifact staged)
      string(JSON image_${key} GET "${application_images}" ${index} ${key})
    endforeach()
    if(NOT image_staged)
      message(STATUS "Application image ${image_file}: omitted; the desktop application needs bundled user documentation")
      continue()
    endif()
    set(image_path "${${image_artifact}}")
    if(image_path STREQUAL "")
      get_directory_property(image_path DIRECTORY "${PROJECT_SOURCE_DIR}/native" DEFINITION "${image_artifact}")
    endif()
    if(NOT TARGET "${image_target}" OR image_path STREQUAL "")
      message(FATAL_ERROR "Application image ${image_file} needs CMake target ${image_target} and variable ${image_artifact}")
    endif()
    list(APPEND application_image_args --image "${image_file}=${image_path}")
    list(APPEND application_image_dependencies "${image_target}" "${image_path}")
    message(STATUS "Application image ${image_file}: staged from ${image_target}")
    if(BUILD_TESTING)
      set(image_arguments)
      string(JSON argument_count LENGTH "${application_images}" ${index} version_arguments)
      math(EXPR argument_last "${argument_count} - 1")
      foreach(argument_index RANGE ${argument_last})
        string(JSON argument GET "${application_images}" ${index} version_arguments ${argument_index})
        list(APPEND image_arguments "${argument}")
      endforeach()
      string(JSON image_package_path GET "${application_images}" ${index} package_path)
      add_test(NAME bundle.image.${image_file} COMMAND "${CMAKE_COMMAND}" -E env
        "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_TESTING}/$<CONFIG>/storage"
        "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${image_package_path}" ${image_arguments})
      set_tests_properties(bundle.image.${image_file} PROPERTIES RESOURCE_LOCK package_inventory)
    endif()
  endforeach()
endif()
add_custom_command(OUTPUT "${CADRUMO_PATH_STAGE}/$<CONFIG>/ready"
  COMMAND ${CADRUMO_HELPER} assemble --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>" ${development_args}
    ${user_docs_args} ${application_image_args}
  DEPENDS cadrumo_python cadrumo_python_bridge ${CADRUMO_ENTRYPOINT_TARGETS} ${application_image_dependencies}
    python_product ${user_docs_dependencies}
    ${development_target} native_metadata "${CADRUMO_PATH_GENERATED}/build.json"
    "${CADRUMO_PATH_PRODUCT}/ready" "${PROJECT_SOURCE_DIR}/native/package-layout.json"
    "${PROJECT_SOURCE_DIR}/native/interpreter/bootstrap.py" "${PROJECT_SOURCE_DIR}/dev/packaging/native/assemble.py"
    "${PROJECT_SOURCE_DIR}/dev/packaging/native/stdlib.py"
    ${native_helper_inputs} ${contract_inputs}
    "${PROJECT_SOURCE_DIR}/native/interpreter/${CADRUMO_BACKEND}/bootstrap.py"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(bundle ALL DEPENDS "${CADRUMO_PATH_STAGE}/$<CONFIG>/ready")
add_dependencies(bundle rust_application)
if(BUILD_TESTING)
  add_test(NAME bundle.python COMMAND "${CMAKE_COMMAND}" -E env
    "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_TESTING}/$<CONFIG>/storage"
    "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${CADRUMO_PACKAGE_EXECUTABLE}" "${PROJECT_SOURCE_DIR}/native/tests/package_smoke.py" "${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
    "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${CADRUMO_PACKAGE_MANIFEST}")
  set_tests_properties(bundle.python PROPERTIES RESOURCE_LOCK package_inventory)
  string(JSON entrypoint_directory GET "${package_layout}" paths native)
  foreach(entrypoint IN LISTS CADRUMO_ENTRYPOINTS)
    add_test(NAME bundle.entrypoint.${entrypoint} COMMAND "${CMAKE_COMMAND}" -E env
      "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_TESTING}/$<CONFIG>/storage"
      "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${entrypoint_directory}/${entrypoint}${CMAKE_EXECUTABLE_SUFFIX}" --help)
    set_tests_properties(bundle.entrypoint.${entrypoint} PROPERTIES RESOURCE_LOCK package_inventory)
  endforeach()
endif()
install(DIRECTORY "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/" DESTINATION .)
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
set(CPACK_PACKAGE_DIRECTORY "${CADRUMO_PATH_PACKAGES}")
set(CADRUMO_ARTIFACT_STEM "${CADRUMO_ID_PACKAGE_NAME}-${CADRUMO_VERSION}-b${CADRUMO_BUILD_NUMBER}-${CADRUMO_PLATFORM}")
configure_file("${PROJECT_SOURCE_DIR}/native/cmake/CPackProject.cmake.in"
  "${PROJECT_BINARY_DIR}/CPackProject.cmake" @ONLY)
configure_file("${PROJECT_SOURCE_DIR}/native/cmake/Artifact.cmake.in"
  "${PROJECT_BINARY_DIR}/Artifact.cmake" @ONLY)
set(CPACK_POST_BUILD_SCRIPTS "${PROJECT_BINARY_DIR}/Artifact.cmake")
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/CPackProject.cmake")
include(CPack)
foreach(group IN LISTS CADRUMO_CLEANUP_GROUPS)
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
