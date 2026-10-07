include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/Authority.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/CachedCommand.cmake")
# Bundled user documentation, shared by the source build and the desktop project.
# The owning docs driver compiles the documentation once for every language declared in
# native/package-layout.json, shares the built site between the build configurations of one
# checkout, and refuses a stale published authority at its cli-sequence gate. Staging copies the shippable
# subset into the published layout and writes the docs manifest that the package delegates to.
set(docs_helper "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build run --
  "${CADRUMO_DEV_PYTHON}" -B -m)
set(docs_target_args)
if(DEFINED CADRUMO_TARGET)
  set(docs_target_args --target "${CADRUMO_TARGET}")
endif()
file(GLOB_RECURSE user_docs_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/docs/*" "${CADRUMO_SOURCE_ROOT}/dev/docs/*" "${CADRUMO_SOURCE_ROOT}/src/*"
  "${CADRUMO_SOURCE_ROOT}/native/platforms/*.json")
list(FILTER user_docs_inputs EXCLUDE REGEX "/(__pycache__|\\.git)/|\\.pyc$|\\.lock$|/docs/_build/|/dev/docs/(.*/)?tests/")
list(FILTER user_docs_inputs EXCLUDE REGEX "/src/.*/tests/|/conftest\\.py$")
list(FILTER user_docs_inputs EXCLUDE REGEX "/\\.aeat-generated-export-transaction-|/\\.generated-export-(backup|stage)-")
foreach(name pyproject.toml uv.lock native/package-layout.json dev/__init__.py dev/_paths.py dev/cache_root.py
    dev/packaging/__init__.py dev/packaging/command_execution.py dev/packaging/authority_staging.py
    dev/packaging/native/__init__.py dev/packaging/native/docs_build.py dev/packaging/native/docs_stage.py
    dev/packaging/native/package_inventory.py dev/packaging/native/build_paths.py dev/packaging/native/hashing.py
    dev/packaging/native/layout.py dev/packaging/native/identity.py dev/packaging/native/action_cache.py
    dev/packaging/native/cmake_build.py dev/packaging/runtime_wheelhouse_contract.py)
  list(APPEND user_docs_inputs "${CADRUMO_SOURCE_ROOT}/${name}")
endforeach()
# The cli-sequence gate executes against the published authority the build selects.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/native/package-layout.json")
list(APPEND user_docs_inputs "${CMAKE_BINARY_DIR}/build-paths.json")
list(REMOVE_DUPLICATES user_docs_inputs)
list(JOIN user_docs_inputs "\n" input_lines)
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/inputs-user-docs.txt" CONTENT "${input_lines}\n")
add_custom_target(user_docs_build
  COMMAND ${docs_helper} dev.packaging.native.docs_build --build "${CMAKE_BINARY_DIR}" --inputs "${CMAKE_BINARY_DIR}/inputs-user-docs.txt"
    ${docs_target_args}
  DEPENDS ${user_docs_inputs} "${CMAKE_BINARY_DIR}/inputs-user-docs.txt"
  BYPRODUCTS "${CADRUMO_PATH_USER_DOCS_BUILD}/ready"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_dependencies(user_docs_build registry_authority)
cadrumo_register_clean(TARGET user_docs_build PATHS "${CADRUMO_PATH_USER_DOCS_BUILD}" "${CADRUMO_PATH_USER_DOCS_WORK}")
cadrumo_cached_command(docs_stage_command user_docs_stage SHARED
  INPUTS "${CADRUMO_PATH_USER_DOCS_BUILD}" "${CADRUMO_SOURCE_ROOT}/native/package-layout.json"
    "${CADRUMO_SOURCE_ROOT}/dev/docs/language_roots.py" "${CADRUMO_SOURCE_ROOT}/dev/docs/build_paths.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/hashing.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/cmake_build.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/docs_stage.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/package_inventory.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_paths.py" "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py"
  OUTPUTS "${CADRUMO_PATH_USER_DOCS_STAGE}")
add_custom_target(user_docs_stage
  COMMAND ${docs_stage_command} ${docs_helper} dev.packaging.native.docs_stage --build "${CMAKE_BINARY_DIR}"
    ${docs_target_args}
  DEPENDS user_docs_build "${CADRUMO_SOURCE_ROOT}/native/package-layout.json"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/docs_stage.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/package_inventory.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_paths.py" "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py"
  BYPRODUCTS "${CADRUMO_PATH_USER_DOCS_STAGE}/ready"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_custom_target(user_docs DEPENDS user_docs_stage)
cadrumo_register_clean(TARGET user_docs DEPENDS user_docs_build user_docs_stage)
