include_guard(GLOBAL)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build directory")
endif()
include("${CMAKE_CURRENT_LIST_DIR}/BinaryDirectory.cmake")
cadrumo_require_enrolled_binary_directory(
  "${CMAKE_BINARY_DIR}" "${CMAKE_SOURCE_DIR}/CMakePresets.json" "${CMAKE_CURRENT_LIST_DIR}/../..")

function(cadrumo_require_physical_build_member path description)
  set(expected "${path}")
  cmake_path(ABSOLUTE_PATH expected NORMALIZE OUTPUT_VARIABLE expected)
  file(RELATIVE_PATH relative "${CMAKE_BINARY_DIR}" "${expected}")
  if(relative STREQUAL ".." OR relative MATCHES [[^\.\./]] OR relative MATCHES [[/\.\./]])
    message(FATAL_ERROR "${description} is outside the selected binary directory: ${path}")
  endif()
  string(REPLACE "\\" "/" relative "${relative}")
  string(REPLACE "/" ";" components "${relative}")
  set(current "${CMAKE_BINARY_DIR}")
  foreach(component IN LISTS components)
    if(component STREQUAL "" OR component STREQUAL ".")
      continue()
    endif()
    set(current "${current}/${component}")
    if(IS_SYMLINK "${current}")
      message(FATAL_ERROR "${description} contains a symlink or junction: ${current}")
    endif()
    if(EXISTS "${current}")
      file(REAL_PATH "${current}" physical)
      set(normalized_current "${current}")
      cmake_path(ABSOLUTE_PATH normalized_current NORMALIZE OUTPUT_VARIABLE normalized_current)
      if(CMAKE_HOST_WIN32)
        string(TOLOWER "${physical}" physical)
        string(TOLOWER "${normalized_current}" normalized_current)
      endif()
      if(NOT physical STREQUAL normalized_current)
        message(FATAL_ERROR "${description} resolves through a symlink or junction: ${current}")
      endif()
    endif()
  endforeach()
endfunction()

# Build output ownership. Helpers consume build-paths.json.
set(CADRUMO_BUILD_DIRECTORIES
  GENERATED generated
  TEMPORARY temporary
  RUNTIME inputs/runtime
  PYTHON_SDK inputs/python-sdk
  TOOLS inputs/build-tools
  PRODUCT product
  AGENT inputs/agent
  BIN bin
  LIB lib
  SYMBOLS symbols
  CARGO cargo/native
  STAGE stage
  PACKAGES packages
  TESTING testing
  VERIFICATION verification
  DESKTOP_FRONTEND desktop/frontend
  DESKTOP_FRONTEND_GENERATED desktop/frontend-generated
  DESKTOP_CACHE desktop/vite-cache
  DESKTOP_ICONS desktop/icons
  DESKTOP_HOST desktop/host
  DESKTOP_CARGO cargo/desktop
  DESKTOP_TESTING desktop/testing
  DESKTOP_RESULTS desktop/test-results
  USER_DOCS_BUILD user-docs/build
  USER_DOCS_WORK user-docs/work
  USER_DOCS_STAGE user-docs/stage
  INSTALLATION_STAGE installation/stage
  INSTALLATION_METADATA installation/metadata
  INSTALLATION_RECEIPTS installation/receipts
  INSTALLATION_WORK installation/work)
set(build_paths "{\"paths\":{}}")
string(JSON build_paths SET "${build_paths}" source "\"${CMAKE_SOURCE_DIR}\"")
set(CADRUMO_BUILD_DIRECTORY_KEYS)
while(CADRUMO_BUILD_DIRECTORIES)
  list(POP_FRONT CADRUMO_BUILD_DIRECTORIES key relative)
  list(APPEND CADRUMO_BUILD_DIRECTORY_KEYS "${key}")
  set(CADRUMO_PATH_${key} "${CMAKE_BINARY_DIR}/${relative}")
  cadrumo_require_physical_build_member("${CADRUMO_PATH_${key}}" "CMake output directory")
  string(TOLOWER "${key}" name)
  string(JSON build_paths SET "${build_paths}" paths "${name}" "\"${relative}\"")
endwhile()
set(cleanup_groups [=[{
  "stage": ["stage", "verification", "testing", "temporary"],
  "packages": ["packages"],
  "dependencies": ["runtime", "python_sdk", "tools", "product", "agent"],
  "native": ["bin", "lib", "symbols", "cargo"],
  "desktop": ["desktop_frontend", "desktop_frontend_generated", "desktop_cache", "desktop_icons", "desktop_host", "desktop_cargo", "desktop_testing", "desktop_results"],
  "docs": ["user_docs_build", "user_docs_work", "user_docs_stage"]
}]=])
string(JSON build_paths SET "${build_paths}" cleanup "${cleanup_groups}")
set(build_path_manifest "${CMAKE_BINARY_DIR}/build-paths.json")
cadrumo_require_physical_build_member("${build_path_manifest}" "CMake build-path manifest")
file(CONFIGURE OUTPUT "${CMAKE_BINARY_DIR}/build-paths.json"
  CONTENT "@build_paths@\n" @ONLY)

string(JSON cleanup_count LENGTH "${cleanup_groups}")
math(EXPR cleanup_last "${cleanup_count} - 1")
set(CADRUMO_CLEANUP_GROUPS all)
foreach(index RANGE ${cleanup_last})
  string(JSON group MEMBER "${cleanup_groups}" ${index})
  list(APPEND CADRUMO_CLEANUP_GROUPS "${group}")
endforeach()
