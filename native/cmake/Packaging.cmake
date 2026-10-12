include("${CMAKE_CURRENT_LIST_DIR}/PackageInputs.cmake")
# Read the actual wheel projects and build hook from the same declarations the
# product helper consumes; installer/tooling directories are not wheel inputs.
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import pathlib, tomllib; from cadrumo.core.product_identity import PRODUCT_IDENTITY; p=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); roots=[p['tool']['uv']['sources'][name]['path'] for name in PRODUCT_IDENTITY.companion_distributions]; roots.append(str(pathlib.Path(p['tool']['hatch']['build']['targets']['wheel']['hooks']['custom']['path']).parent)); print(';'.join(roots))"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE product_directories
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
cadrumo_product_inputs(product_inputs "${PROJECT_SOURCE_DIR}" ${product_directories})
include("${CMAKE_CURRENT_LIST_DIR}/Authority.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/CachedCommand.cmake")
list(APPEND product_inputs "${CADRUMO_PATH_RUNTIME}/ready")
list(JOIN product_inputs "\n" input_lines)
file(GENERATE OUTPUT "${PROJECT_BINARY_DIR}/inputs-product.txt" CONTENT "${input_lines}\n")
cadrumo_build_step(step_comment python_product GROUP dependencies
  SUMMARY "build and install the product wheels from this checkout" OUTPUTS "${CADRUMO_PATH_PRODUCT}")
add_custom_target(python_product
  # Always run the Python admission check: it loads env/.env or inherited CI
  # credentials and binds cache reuse to their digest without CMake variables.
  COMMAND ${CADRUMO_HELPER} product --build "${PROJECT_BINARY_DIR}" --inputs "${PROJECT_BINARY_DIR}/inputs-product.txt"
  DEPENDS ${product_inputs} "${PROJECT_BINARY_DIR}/inputs-product.txt"
  BYPRODUCTS "${CADRUMO_PATH_PRODUCT}/ready"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
add_dependencies(python_product python_dependencies registry_authority)
cadrumo_register_clean(TARGET python_product PATHS "${CADRUMO_PATH_PRODUCT}")
if(CADRUMO_INCLUDE_DEVELOPMENT_BINARY)
  set(development_args --development)
  set(development_target cadrumo_python_d)
endif()
include("${PROJECT_SOURCE_DIR}/native/cmake/Docs.cmake")
option(CADRUMO_PACKAGE_USER_DOCS "Bundle the user documentation in the assembled package" ON)
if(CADRUMO_PACKAGE_USER_DOCS)
  set(user_docs_dependencies user_docs "${CADRUMO_PATH_USER_DOCS_STAGE}/ready")
  cadrumo_build_fact("User documentation" "bundled in the package (CADRUMO_PACKAGE_USER_DOCS=ON)")
else()
  set(user_docs_args --without-user-docs)
  cadrumo_build_fact("User documentation"
    "not bundled; the package manifest states it (CADRUMO_PACKAGE_USER_DOCS=OFF)")
endif()
# Application images are native executables that are not interpreter hosts, declared by the
# platform mapping. Each names its CMake target and the variable that holds its artifact path,
# defined in this scope or the native directory's. The layout owner only reports the declarations;
# CMake stages every declared image, and user documentation never decides which images ship.
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "import json; from dataclasses import asdict; from dev.packaging.native.layout import application_images, load_layout; print(json.dumps([dict(asdict(image), package_path=image.package_path) for image in application_images(load_layout('${CADRUMO_TARGET}'))]))"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE application_images
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
# The desktop project defines desktop-host-build and the variable naming its host image.
# It needs Node.js and npm, so it is configured only when the platform declares a desktop image.
set(desktop_image_staged FALSE)
string(JSON image_count LENGTH "${application_images}")
if(image_count GREATER 0)
  math(EXPR image_last "${image_count} - 1")
  foreach(index RANGE ${image_last})
    string(JSON image_desktop GET "${application_images}" ${index} desktop)
    if(image_desktop)
      set(desktop_image_staged TRUE)
      string(JSON desktop_package_path GET "${application_images}" ${index} package_path)
    endif()
  endforeach()
endif()
if(desktop_image_staged)
  cadrumo_build_fact("Desktop application" "configured: the platform stages a desktop image")
  add_subdirectory("${PROJECT_SOURCE_DIR}/native/desktop" "${PROJECT_BINARY_DIR}/native/desktop")
else()
  cadrumo_build_fact("Desktop application" "not configured: the platform stages no desktop image")
endif()
set(application_image_args)
set(application_image_dependencies)
set(staged_images)
string(JSON image_count LENGTH "${application_images}")
if(image_count GREATER 0)
  math(EXPR image_last "${image_count} - 1")
  foreach(index RANGE ${image_last})
    foreach(key file target artifact desktop)
      string(JSON image_${key} GET "${application_images}" ${index} ${key})
    endforeach()
    set(image_path "${${image_artifact}}")
    if(image_path STREQUAL "")
      get_directory_property(image_path DIRECTORY "${PROJECT_SOURCE_DIR}/native" DEFINITION "${image_artifact}")
    endif()
    if(NOT TARGET "${image_target}" OR image_path STREQUAL "")
      message(FATAL_ERROR "Application image ${image_file} needs CMake target ${image_target} and variable ${image_artifact}")
    endif()
    list(APPEND application_image_args --image "${image_file}=${image_path}")
    list(APPEND application_image_dependencies "${image_target}" "${image_path}")
    list(APPEND staged_images "${image_file} from ${image_target}")
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
        --unset=CADRUMO_DESKTOP_PACKAGE_ROOT
        "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_TESTING}/$<CONFIG>/storage"
        "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${image_package_path}" ${image_arguments})
      set_tests_properties(bundle.image.${image_file} PROPERTIES RESOURCE_LOCK package_inventory)
      if(WIN32 AND image_desktop)
        add_test(NAME bundle.health.${image_file} COMMAND "${CADRUMO_DEV_PYTHON}" -B -m
          dev.packaging.native.package_launch_smoke --health
          "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${image_package_path}" "${CADRUMO_STORAGE_ROOT_VARIABLE}")
        set_tests_properties(bundle.health.${image_file} PROPERTIES RESOURCE_LOCK package_inventory
          FIXTURES_REQUIRED desktop_package_ready FIXTURES_SETUP desktop_runtime_ready TIMEOUT 360
          WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}")
        add_test(NAME bundle.launch.${image_file} COMMAND "${CMAKE_COMMAND}" -E env
          "${CADRUMO_STORAGE_ROOT_VARIABLE}=${CADRUMO_PATH_TESTING}/$<CONFIG>/storage"
          "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.package_launch_smoke
          "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${image_package_path}" "${CADRUMO_VERSION}"
          "${CADRUMO_STORAGE_ROOT_VARIABLE}" "${CADRUMO_PATH_TESTING}/$<CONFIG>")
        set_tests_properties(bundle.launch.${image_file} PROPERTIES RESOURCE_LOCK package_inventory TIMEOUT 600
          FIXTURES_SETUP desktop_package_ready WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}")
      endif()
    endif()
  endforeach()
endif()
cadrumo_build_fact("Application images" ${staged_images})
include("${PROJECT_SOURCE_DIR}/native/cmake/PackageInputs.cmake")
cadrumo_package_bootstrap(package_bootstrap "${package_layout}" "${PROJECT_SOURCE_DIR}")
cadrumo_assembly_product_inputs(assembly_product_inputs "${CADRUMO_PATH_PRODUCT}")
set(assembly_inputs "${CADRUMO_PATH_RUNTIME}/runtime-inputs.json" "${CADRUMO_PATH_PYTHON_SDK}" ${assembly_product_inputs}
  "${CADRUMO_PATH_GENERATED}/build.json" "${CADRUMO_PATH_GENERATED}/build-toolchain.json"
  "${package_bootstrap}" ${contract_inputs})
foreach(target cadrumo_python cadrumo_python_bridge ${CADRUMO_ENTRYPOINT_TARGETS} ${development_target})
  list(APPEND assembly_inputs "$<TARGET_FILE:${target}>")
endforeach()
foreach(argument IN LISTS application_image_args)
  if(argument MATCHES "^[^=]+=(.+)$")
    list(APPEND assembly_inputs "${CMAKE_MATCH_1}")
  endif()
endforeach()
if(CADRUMO_PACKAGE_USER_DOCS)
  list(APPEND assembly_inputs "${CADRUMO_PATH_USER_DOCS_STAGE}")
endif()
# These helpers own assembly; unrelated native build/test helpers are not inputs.
foreach(helper assemble stdlib package_inventory layout hashing build_paths docs_stage cmake_build cached_command build_timing)
  list(APPEND assembly_inputs "${PROJECT_SOURCE_DIR}/dev/packaging/native/${helper}.py")
endforeach()
cadrumo_assembly_backend_inputs(assembly_backend_inputs "${PROJECT_SOURCE_DIR}" "${CADRUMO_BACKEND}")
list(APPEND assembly_inputs ${assembly_backend_inputs})
if(WIN32)
  list(APPEND assembly_inputs "${PROJECT_SOURCE_DIR}/dev/packaging/native/platforms/pe.py")
else()
  list(APPEND assembly_inputs "${PROJECT_SOURCE_DIR}/dev/packaging/native/platforms/posix.py")
endif()
list(APPEND assembly_inputs "${PROJECT_SOURCE_DIR}/native/interpreter/bootstrap.py")
foreach(input uv.lock pyproject.toml dev/packaging/release-python-version
    dev/packaging/runtime_wheel_selection.py dev/packaging/runtime_wheelhouse_contract.py
    dev/packaging/native/action_cache.py dev/packaging/native/build_toolchain.py)
  list(APPEND assembly_inputs "${PROJECT_SOURCE_DIR}/${input}")
endforeach()
cadrumo_cached_command(assembly_command bundle INPUTS ${assembly_inputs}
  OUTPUTS "${CADRUMO_PATH_STAGE}/$<CONFIG>/app" "${CADRUMO_PATH_STAGE}/$<CONFIG>/ready")
cadrumo_build_step(step_comment native-process-quiesce GROUP assembly
  SUMMARY "stop Cadrumo processes running from this build before its images are replaced")
add_custom_target(native-process-quiesce
  COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.process_quiescence
    --build "${PROJECT_BINARY_DIR}" --target "${CADRUMO_TARGET}"
  DEPENDS native_contract WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
foreach(product_target cadrumo_python cadrumo_python_bridge ${CADRUMO_ENTRYPOINT_TARGETS}
    ${application_image_dependencies} ${development_target})
  if(TARGET "${product_target}")
    add_dependencies("${product_target}" native-process-quiesce)
  endif()
endforeach()
cadrumo_build_step(step_comment app-payload GROUP assembly
  SUMMARY "assemble the application payload: interpreter, product, native images and documentation"
  OUTPUTS "${CADRUMO_PATH_STAGE}/$<CONFIG>/app")
add_custom_target(app-payload
  COMMAND ${assembly_command} ${CADRUMO_HELPER} assemble --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>" ${development_args}
    ${user_docs_args} ${application_image_args}
  DEPENDS cadrumo_python cadrumo_python_bridge ${CADRUMO_ENTRYPOINT_TARGETS} ${application_image_dependencies}
    python_product ${user_docs_dependencies}
    ${development_target} native_metadata "${CADRUMO_PATH_GENERATED}/build.json"
    "${CADRUMO_PATH_PRODUCT}/ready" "${PROJECT_SOURCE_DIR}/native/package-layout.json"
    "${PROJECT_SOURCE_DIR}/native/interpreter/bootstrap.py" "${PROJECT_SOURCE_DIR}/dev/packaging/native/assemble.py"
    "${PROJECT_SOURCE_DIR}/dev/packaging/native/stdlib.py"
    ${contract_inputs}
    "${package_bootstrap}"
  BYPRODUCTS "${CADRUMO_PATH_STAGE}/$<CONFIG>/ready"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
add_dependencies(app-payload rust_application)
set(desktop_delivery_check)
if(WIN32 AND desktop_image_staged)
  # Bootstrap admission is required for delivery even when optional tests are off.
  # Exercise the existing native test against this exact assembled app/kit pair.
  enable_testing()
  set(installer_bootstrap_test
    "runner::bootstrap::tests::assembled_kit_admits_both_scopes_and_refuses_wrong_native_role_without_installing")
  cadrumo_cargo_command(installer_bootstrap_cargo
    --env "CADRUMO_BOOTSTRAP_TEST_PACKAGE=${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
    --env "CADRUMO_NATIVE_CONTRACT=${CADRUMO_PATH_GENERATED}/contract.json")
  add_test(NAME bundle.installer-bootstrap
    COMMAND ${installer_bootstrap_cargo} test --locked --lib
      --manifest-path "${PROJECT_SOURCE_DIR}/native/installer/Cargo.toml"
      --target "${CADRUMO_PIN_rust_target}" --profile "$<IF:$<CONFIG:Debug>,dev,release>"
      "${installer_bootstrap_test}" -- --ignored --exact)
  set_tests_properties(bundle.installer-bootstrap PROPERTIES
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" RESOURCE_LOCK package_inventory TIMEOUT 900
    FAIL_REGULAR_EXPRESSION "running 0 tests;test result: FAILED")
  set(desktop_delivery_check COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.package_launch_smoke --kit
    "${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
    COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>"
      --output-on-failure --no-tests=error -R "^bundle[.]installer-bootstrap$"
    COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.package_launch_smoke --health
    "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/${desktop_package_path}" "${CADRUMO_STORAGE_ROOT_VARIABLE}")
endif()
if(desktop_delivery_check)
  set(bundle_summary "the assembled payload, after its desktop delivery checks")
else()
  set(bundle_summary "the assembled payload")
endif()
cadrumo_build_step(step_comment bundle GROUP assembly SUMMARY "${bundle_summary}"
  OUTPUTS "${CADRUMO_PATH_STAGE}/$<CONFIG>/app")
add_custom_target(bundle ALL ${desktop_delivery_check} DEPENDS app-payload
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" VERBATIM)
cadrumo_build_step(step_comment app-distro GROUP assembly SUMMARY "alias of bundle")
add_custom_target(app-distro DEPENDS bundle COMMENT "${step_comment}")
if(TARGET desktop-headless-test)
  add_dependencies(desktop-headless-test bundle)
endif()
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
if(BUILD_TESTING AND WIN32)
  # Exercise the assembled clients and real supervisor through the existing harness.
  add_test(NAME bundle.runtime-lifecycle COMMAND "${CADRUMO_DEV_PYTHON}" -B -m pytest
    -n 0 -m integration "${PROJECT_SOURCE_DIR}/dev/runtime_lifecycle/tests"
    --lifecycle-manager "${CADRUMO_PATH_CARGO}/manager-lifecycle/${CADRUMO_PIN_rust_target}/debug/cadrumo-manager-lifecycle.exe"
    --lifecycle-package "${CADRUMO_PATH_STAGE}/$<CONFIG>/app"
    --junitxml "${CADRUMO_PATH_TESTING}/$<CONFIG>/lifecycle.xml" -o junit_family=legacy)
  set_tests_properties(bundle.runtime-lifecycle PROPERTIES RESOURCE_LOCK package_inventory
    RUN_SERIAL TRUE TIMEOUT 1800 WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}")
  if(desktop_image_staged)
    set_tests_properties(bundle.runtime-lifecycle PROPERTIES FIXTURES_REQUIRED "desktop_package_ready;desktop_runtime_ready")
  endif()
endif()
if(WIN32 AND desktop_image_staged)
  # Preserve the app/services relationship used by desktop provisioning.
  install(DIRECTORY "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/" DESTINATION app USE_SOURCE_PERMISSIONS)
else()
  install(DIRECTORY "${CADRUMO_PATH_STAGE}/$<CONFIG>/app/" DESTINATION . USE_SOURCE_PERMISSIONS)
endif()
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
set(native_verification_targets rust_platform rust_platform_consumer rust_application)
if(BUILD_TESTING AND WIN32)
  list(APPEND native_verification_targets rust_manager_lifecycle)
endif()
foreach(consumer platform_static_consumer platform_dll_consumer)
  if(TARGET ${consumer})
    list(APPEND native_verification_targets ${consumer})
  endif()
endforeach()
cadrumo_build_step(step_comment verify GROUP verification
  SUMMARY "build the bundle and native verification targets, then run every CTest test")
add_custom_target(verify
  COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>" --output-on-failure --no-tests=error
  DEPENDS bundle ${native_verification_targets}
  COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
cadrumo_build_step(step_comment verify-app-distro GROUP verification
  SUMMARY "run the bundle and application package CTest tests")
add_custom_target(verify-app-distro
  COMMAND "${CMAKE_CTEST_COMMAND}" --test-dir "${PROJECT_BINARY_DIR}" -C "$<CONFIG>"
    --output-on-failure --no-tests=error -R "^(bundle[.]|application[.]package$)"
  DEPENDS bundle COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
if(BUILD_TESTING AND WIN32)
  add_dependencies(verify-app-distro rust_manager_lifecycle)
endif()
set(zip_delivery_inputs)
if(WIN32 AND desktop_image_staged)
  string(JSON zip_bootstrap_directory GET "${package_layout}" installation bootstrap directory)
  list(APPEND zip_delivery_inputs "${CADRUMO_PATH_STAGE}/$<CONFIG>/${zip_bootstrap_directory}")
endif()
cadrumo_cached_command(zip_command zip
  INPUTS "${CADRUMO_PATH_STAGE}/$<CONFIG>/app" "${PROJECT_BINARY_DIR}/CPackConfig.cmake"
    ${zip_delivery_inputs}
    "${PROJECT_BINARY_DIR}/CPackProject.cmake" "${PROJECT_BINARY_DIR}/Artifact.cmake"
    "${PROJECT_BINARY_DIR}/cmake_install.cmake" "${CADRUMO_PATH_GENERATED}/contract.json"
    "${PROJECT_SOURCE_DIR}/LICENSE" "${CMAKE_CPACK_COMMAND}"
  OUTPUTS "${CADRUMO_PATH_PACKAGES}/$<CONFIG>/${CADRUMO_ARTIFACT_STEM}-$<CONFIG>.zip"
    "${PROJECT_BINARY_DIR}/artifacts-$<CONFIG>.json")
cadrumo_build_step(step_comment zip GROUP package
  SUMMARY "package the bundle as the distributable ZIP"
  OUTPUTS "${CADRUMO_PATH_PACKAGES}/$<CONFIG>/${CADRUMO_ARTIFACT_STEM}-$<CONFIG>.zip")
add_custom_target(zip
  COMMAND ${zip_command} "${CMAKE_CPACK_COMMAND}" --config "${PROJECT_BINARY_DIR}/CPackConfig.cmake" -C "$<CONFIG>"
  DEPENDS bundle COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
add_custom_target(clean-package DEPENDS clean-zip)
cadrumo_build_step(step_comment verify-package GROUP verification
  SUMMARY "extract the ZIP and verify the package it contains"
  OUTPUTS "${CADRUMO_PATH_VERIFICATION}/$<CONFIG>")
add_custom_target(verify-package
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.artifact_verify
    --build "${PROJECT_BINARY_DIR}" --config "$<CONFIG>"
    --application-probe-command "${CADRUMO_APPLICATION_ARTIFACT_PROBE_FILE}"
  DEPENDS zip WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" COMMENT "${step_comment}" USES_TERMINAL VERBATIM)
# One dependency graph builds the bundle/ZIP once and verifies that exact artifact.
# Separate recipe invocations repeat graph traversal and can observe different inputs.
include("${CMAKE_CURRENT_LIST_DIR}/ReleaseVerification.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/InstallerFlow.cmake")
