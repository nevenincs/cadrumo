include_guard(GLOBAL)
include("${CMAKE_CURRENT_LIST_DIR}/Authority.cmake")
include("${CMAKE_CURRENT_LIST_DIR}/CachedCommand.cmake")
# Bundled user documentation, shared by the source build and the desktop project.
# The owning docs driver compiles the documentation once for every language declared in
# native/package-layout.json, shares the built site between identical enrolled source graphs,
# and refuses a stale published authority at its cli-sequence gate. Staging copies the shippable
# subset into the published layout and writes the docs manifest that the package delegates to.
set(docs_helper "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cmake_build run --
  "${CADRUMO_DEV_PYTHON}" -B -m)
set(docs_target_args)
if(DEFINED CADRUMO_TARGET)
  set(docs_target_args --target "${CADRUMO_TARGET}")
endif()
option(CADRUMO_DOCS_SHARED_CACHE "Reuse documentation across build configurations" ON)
set(docs_build_args ${docs_target_args})
if(NOT CADRUMO_DOCS_SHARED_CACHE)
  list(APPEND docs_build_args --no-shared-cache)
endif()
file(GLOB_RECURSE user_docs_inputs CONFIGURE_DEPENDS
  "${CADRUMO_SOURCE_ROOT}/docs/*" "${CADRUMO_SOURCE_ROOT}/dev/docs/*" "${CADRUMO_SOURCE_ROOT}/src/*"
  "${CADRUMO_SOURCE_ROOT}/native/platforms/*.json")
list(FILTER user_docs_inputs EXCLUDE REGEX "/(__pycache__|\\.git)/|\\.pyc$|\\.lock$|/docs/_build/|/dev/docs/(.*/)?tests/")
# Documentation scenarios import source test-support modules and their helpers.
# Retain that tree so fixture changes invalidate the compiled site too.
list(FILTER user_docs_inputs EXCLUDE REGEX "/\\.aeat-generated-export-transaction-|/\\.generated-export-(backup|stage)-")
foreach(name pyproject.toml uv.lock native/package-layout.json dev/__init__.py dev/_paths.py dev/cache_root.py
    dev/packaging/__init__.py dev/packaging/command_execution.py dev/packaging/authority_staging.py
    dev/packaging/native/__init__.py dev/packaging/native/docs_build.py dev/packaging/native/docs_stage.py
    dev/packaging/native/docs_input_identity.py
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
    ${docs_build_args}
  DEPENDS ${user_docs_inputs} "${CMAKE_BINARY_DIR}/inputs-user-docs.txt"
  BYPRODUCTS "${CADRUMO_PATH_USER_DOCS_BUILD}/ready"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
add_dependencies(user_docs_build registry_authority)
add_custom_target(user_docs_driver_test
  COMMAND ${docs_helper} pytest -q "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/tests/test_docs_shared_site.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/tests/test_docs_build_environment.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/tests/test_docs_input_identity.py"
    "${CADRUMO_SOURCE_ROOT}/dev/packaging/native/tests/test_docs_input_publication.py"
  WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
cadrumo_register_clean(TARGET user_docs_build PATHS "${CADRUMO_PATH_USER_DOCS_BUILD}" "${CADRUMO_PATH_USER_DOCS_WORK}")
set(CADRUMO_DOCS_SEQUENCE_PAGES "" CACHE STRING "Documentation pages selected for explicit transcript maintenance")
set(CADRUMO_DOCS_SEQUENCE_ID "" CACHE STRING "Single documentation sequence selected for explicit transcript maintenance")
if(CADRUMO_DOCS_SEQUENCE_PAGES AND CADRUMO_DOCS_SEQUENCE_ID)
  message(FATAL_ERROR "Select CADRUMO_DOCS_SEQUENCE_PAGES or CADRUMO_DOCS_SEQUENCE_ID, not both")
endif()
set(docs_sequence_args)
if(CADRUMO_DOCS_SEQUENCE_ID)
  list(APPEND docs_sequence_args --sequence "${CADRUMO_DOCS_SEQUENCE_ID}")
endif()
set(docs_sequence_pages ${CADRUMO_DOCS_SEQUENCE_PAGES})
list(REMOVE_DUPLICATES docs_sequence_pages)
foreach(action check refresh)
  if(docs_sequence_pages)
    add_custom_target(user_docs_sequences_${action})
    foreach(page IN LISTS docs_sequence_pages)
      string(SHA256 page_hash "${page}")
      string(SUBSTRING "${page_hash}" 0 12 page_id)
      set(page_target user_docs_sequences_${action}_${page_id})
      add_custom_target(${page_target}
        COMMAND ${docs_helper} dev.docs.sequences ${action} --page "${page}"
        WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
      add_dependencies(${page_target} registry_authority)
      add_dependencies(user_docs_sequences_${action} ${page_target})
    endforeach()
  else()
    add_custom_target(user_docs_sequences_${action}
      COMMAND ${docs_helper} dev.docs.sequences ${action} ${docs_sequence_args}
      WORKING_DIRECTORY "${CADRUMO_SOURCE_ROOT}" USES_TERMINAL VERBATIM)
    add_dependencies(user_docs_sequences_${action} registry_authority)
  endif()
endforeach()
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
