include_guard(GLOBAL)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build directory")
endif()
include("${CMAKE_CURRENT_LIST_DIR}/BinaryDirectory.cmake")
cadrumo_require_enrolled_binary_directory(
  "${CMAKE_BINARY_DIR}" "${CMAKE_SOURCE_DIR}/CMakePresets.json" "${CMAKE_CURRENT_LIST_DIR}/../..")

# Build output ownership. Helpers consume build-paths.json.
set(CADRUMO_BUILD_DIRECTORIES
  GENERATED generated
  RUNTIME _deps/runtime
  TOOLS _deps/build-tools
  PRODUCT product
  BIN bin
  LIB lib
  SYMBOLS symbols
  CARGO cargo
  STAGE stage
  PACKAGES packages
  TESTING testing
  VERIFICATION verification
  DESKTOP_FRONTEND desktop/frontend
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
  INSTALLATION_WORK installation/work)
set(build_paths "{\"paths\":{}}")
while(CADRUMO_BUILD_DIRECTORIES)
  list(POP_FRONT CADRUMO_BUILD_DIRECTORIES key relative)
  set(CADRUMO_PATH_${key} "${CMAKE_BINARY_DIR}/${relative}")
  string(TOLOWER "${key}" name)
  string(JSON build_paths SET "${build_paths}" paths "${name}" "\"${relative}\"")
endwhile()
set(cleanup_groups [=[{
  "stage": ["stage", "verification", "testing"],
  "packages": ["packages"],
  "dependencies": ["runtime", "tools", "product"],
  "native": ["bin", "lib", "symbols", "cargo"],
  "desktop": ["desktop_frontend", "desktop_cache", "desktop_icons", "desktop_host", "desktop_cargo", "desktop_testing", "desktop_results"],
  "docs": ["user_docs_build", "user_docs_work", "user_docs_stage"]
}]=])
string(JSON build_paths SET "${build_paths}" cleanup "${cleanup_groups}")
file(CONFIGURE OUTPUT "${CMAKE_BINARY_DIR}/build-paths.json"
  CONTENT "@build_paths@\n" @ONLY)

string(JSON cleanup_count LENGTH "${cleanup_groups}")
math(EXPR cleanup_last "${cleanup_count} - 1")
set(CADRUMO_CLEANUP_GROUPS all)
foreach(index RANGE ${cleanup_last})
  string(JSON group MEMBER "${cleanup_groups}" ${index})
  list(APPEND CADRUMO_CLEANUP_GROUPS "${group}")
endforeach()
