include_guard(GLOBAL)
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
execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -c
  "from dev.packaging.authority_staging import selected_published_authority; from dev._paths import REPO_ROOT; print(';'.join(p.resolve().as_posix() for p in selected_published_authority(REPO_ROOT)))"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" OUTPUT_VARIABLE user_docs_authority
  OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  ${user_docs_authority} "${CADRUMO_SOURCE_ROOT}/native/package-layout.json")
list(APPEND user_docs_inputs ${user_docs_authority} "${CMAKE_BINARY_DIR}/build-paths.json")
list(REMOVE_DUPLICATES user_docs_inputs)
list(JOIN user_docs_inputs "\n" input_lines)
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/inputs-user-docs.txt" CONTENT "${input_lines}\n")
add_custom_command(OUTPUT "${CADRUMO_PATH_USER_DOCS_BUILD}/ready"
  COMMAND ${docs_helper} dev.packaging.native.docs_build --build "${CMAKE_BINARY_DIR}" --inputs "${CMAKE_BINARY_DIR}/inputs-user-docs.txt"
    ${docs_target_args}
  DEPENDS ${user_docs_inputs} "${CMAKE_BINARY_DIR}/inputs-user-docs.txt"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_custom_command(OUTPUT "${CADRUMO_PATH_USER_DOCS_STAGE}/ready"
  COMMAND ${docs_helper} dev.packaging.native.docs_stage --build "${CMAKE_BINARY_DIR}"
    ${docs_target_args}
  DEPENDS "${CADRUMO_PATH_USER_DOCS_BUILD}/ready" "${CADRUMO_SOURCE_ROOT}/native/package-layout.json"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/docs_stage.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/package_inventory.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/build_paths.py" "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/layout.py"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_custom_target(user_docs DEPENDS "${CADRUMO_PATH_USER_DOCS_STAGE}/ready")
