# Console entrypoints share the interpreter host source and ship in the native directory.
string(JSON entrypoint_suffix GET "${package_layout}" entrypoint_suffix)
if(NOT entrypoint_suffix STREQUAL CMAKE_EXECUTABLE_SUFFIX)
  message(FATAL_ERROR "The platform entrypoint suffix does not match the selected toolchain")
endif()
set(CADRUMO_ENTRYPOINTS)
set(entrypoint_resources)
string(JSON entrypoint_count LENGTH "${package_layout}" entrypoints)
if(entrypoint_count GREATER 0)
  math(EXPR entrypoint_last "${entrypoint_count} - 1")
  foreach(index RANGE ${entrypoint_last})
    string(JSON entrypoint MEMBER "${package_layout}" entrypoints ${index})
    list(APPEND CADRUMO_ENTRYPOINTS "${entrypoint}")
    list(APPEND entrypoint_resources "${CONTRACT_DIR}/entrypoint-${entrypoint}.rc")
  endforeach()
endif()
add_custom_command(OUTPUT "${CONTRACT_DIR}/build_metadata.h" "${CONTRACT_DIR}/build.json"
    "${CONTRACT_DIR}/interpreter.rc" "${CONTRACT_DIR}/cadrumo.ico" ${entrypoint_resources}
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.metadata "${CONTRACT_DIR}"
    --number "${CADRUMO_BUILD_NUMBER}" --date "${CADRUMO_BUILD_DATE}" --tools "${CADRUMO_PATH_TOOLS}"
    --channel "${CADRUMO_CHANNEL}"
  DEPENDS ${native_helper_inputs} ${contract_inputs}
    "${CONTRACT_DIR}/identity.json"
    "${PROJECT_SOURCE_DIR}/docs/_static/cadrumo-favicon.svg" "${CADRUMO_PATH_TOOLS}/ready"
    "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(native_metadata DEPENDS "${CONTRACT_DIR}/build_metadata.h" "${CONTRACT_DIR}/build.json"
  "${CONTRACT_DIR}/interpreter.rc" "${CONTRACT_DIR}/cadrumo.ico" ${entrypoint_resources})
add_dependencies(native_metadata native_build_tools)

set(CADRUMO_RUST_ROOT "$ENV{USERPROFILE}/.rustup/toolchains/${CADRUMO_PIN_rust}-${CADRUMO_PIN_rust_target}"
  CACHE PATH "Pinned Rust MSVC toolchain")
execute_process(COMMAND "${CADRUMO_RUST_ROOT}/bin/rustc.exe" --version
  OUTPUT_VARIABLE rust_version OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
if(NOT rust_version MATCHES "^rustc ${CADRUMO_PIN_rust} ")
  message(FATAL_ERROR "Rust ${CADRUMO_PIN_rust} is required")
endif()
cmake_host_system_information(RESULT sdk_root QUERY WINDOWS_REGISTRY
  "HKLM/SOFTWARE/Microsoft/Windows Kits/Installed Roots" VALUE KitsRoot10 VIEW 64)
set(msvc_root "${CMAKE_GENERATOR_INSTANCE}/VC/Tools/MSVC/${CADRUMO_PIN_msvc}")
if(NOT EXISTS "${msvc_root}/lib/x64/libcmt.lib" OR NOT EXISTS "${sdk_root}/Lib/${CADRUMO_PIN_windows_sdk}/um/x64/kernel32.lib")
  message(FATAL_ERROR "Pinned MSVC/SDK libraries are missing")
endif()
set(rust_profile "$<IF:$<CONFIG:Debug>,debug,release>")
set(CADRUMO_RUST_ENVIRONMENT_NAMES RUSTFLAGS CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER LIB INCLUDE
  "CC_${CADRUMO_PIN_rust_target}" "AR_${CADRUMO_PIN_rust_target}")
set(CADRUMO_RUST_ENV_RUSTFLAGS "-C target-feature=+crt-static")
set(CADRUMO_RUST_ENV_CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER "${CMAKE_LINKER}")
set(CADRUMO_RUST_ENV_LIB "${msvc_root}/lib/x64;${sdk_root}/Lib/${CADRUMO_PIN_windows_sdk}/um/x64;${sdk_root}/Lib/${CADRUMO_PIN_windows_sdk}/ucrt/x64")
set(CADRUMO_RUST_ENV_INCLUDE "${msvc_root}/include;${sdk_root}/Include/${CADRUMO_PIN_windows_sdk}/ucrt;${sdk_root}/Include/${CADRUMO_PIN_windows_sdk}/shared;${sdk_root}/Include/${CADRUMO_PIN_windows_sdk}/um;${sdk_root}/Include/${CADRUMO_PIN_windows_sdk}/winrt")
set("CADRUMO_RUST_ENV_CC_${CADRUMO_PIN_rust_target}" "${CMAKE_C_COMPILER}")
set("CADRUMO_RUST_ENV_AR_${CADRUMO_PIN_rust_target}" "${CMAKE_AR}")
cadrumo_cargo_command(platform_cargo --env "CADRUMO_CONTRACT_RS=${CONTRACT_DIR}/contract.rs")
set(platform_dir "${CADRUMO_PATH_CARGO}/${CADRUMO_PIN_rust_target}/${rust_profile}")
set(platform_static "${platform_dir}/cadrumo_platform.lib")
set(platform_import "${platform_dir}/cadrumo_platform.dll.lib")
file(GLOB_RECURSE rust_sources CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/platform/src/*.rs")
add_custom_command(OUTPUT "${platform_static}" "${platform_import}" "${platform_dir}/cadrumo_platform.dll"
    "${platform_dir}/platform-consumer.exe"
  COMMAND ${platform_cargo} build --locked --manifest-path "${CMAKE_CURRENT_SOURCE_DIR}/platform/Cargo.toml"
      --target "${CADRUMO_PIN_rust_target}" --profile "$<IF:$<CONFIG:Debug>,dev,release>"
  DEPENDS ${rust_sources} platform/Cargo.toml platform/Cargo.lock "${CONTRACT_DIR}/contract.rs" "${CADRUMO_BUILD_HELPER}"
    "${PROJECT_SOURCE_DIR}/native/cmake/Rust.cmake" "${CMAKE_CURRENT_LIST_FILE}" "${PROJECT_SOURCE_DIR}/native/toolchain.json"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(rust_platform DEPENDS "${platform_static}" "${platform_import}" "${platform_dir}/cadrumo_platform.dll"
  "${platform_dir}/platform-consumer.exe")

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CADRUMO_PATH_BIN}/$<CONFIG>")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CADRUMO_PATH_LIB}/$<CONFIG>")
set(CMAKE_PDB_OUTPUT_DIRECTORY "${CADRUMO_PATH_SYMBOLS}/$<CONFIG>")
add_executable(cadrumo_python interpreter/windows/host.c interpreter/windows/host.rc "${CONTRACT_DIR}/interpreter.rc")
set_target_properties(cadrumo_python PROPERTIES OUTPUT_NAME "${production_name}")
add_executable(cadrumo_python_d EXCLUDE_FROM_ALL interpreter/windows/host.c interpreter/windows/host.rc "${CONTRACT_DIR}/interpreter.rc")
set_target_properties(cadrumo_python_d PROPERTIES OUTPUT_NAME "${development_name}")
set(CADRUMO_ENTRYPOINT_TARGETS)
foreach(entrypoint IN LISTS CADRUMO_ENTRYPOINTS)
  string(MAKE_C_IDENTIFIER "cadrumo_entrypoint_${entrypoint}" target)
  add_executable(${target} interpreter/windows/host.c interpreter/windows/host.rc
    "${CONTRACT_DIR}/entrypoint-${entrypoint}.rc")
  set_target_properties(${target} PROPERTIES OUTPUT_NAME "${entrypoint}")
  target_compile_definitions(${target} PRIVATE "$<$<COMPILE_LANGUAGE:C>:CADRUMO_ENTRYPOINT=\"${entrypoint}\">")
  list(APPEND CADRUMO_ENTRYPOINT_TARGETS ${target})
endforeach()
set(host_targets cadrumo_python cadrumo_python_d ${CADRUMO_ENTRYPOINT_TARGETS})
set_property(SOURCE interpreter/windows/host.rc APPEND PROPERTY OBJECT_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/interpreter/windows/host.manifest")
foreach(target IN LISTS host_targets)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/interpreter/windows")
  # Entrypoint hosts run from the native directory beside bundled DLLs; resolve their
  # load-time imports from System32 only (LOAD_LIBRARY_SEARCH_SYSTEM32).
  target_link_options(${target} PRIVATE /MANIFEST:NO /DEPENDENTLOADFLAG:0x800)
  add_custom_command(TARGET ${target} POST_BUILD
    COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.platforms.windows_manifest
      "$<TARGET_FILE:${target}>" "${CMAKE_CURRENT_SOURCE_DIR}/interpreter/windows/host.manifest"
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
endforeach()
target_compile_definitions(cadrumo_python_d PRIVATE CADRUMO_DEVELOPMENT=1)
target_compile_options(cadrumo_python_d PRIVATE /Od /Zi)
target_link_options(cadrumo_python_d PRIVATE /DEBUG)
add_library(cadrumo_python_bridge SHARED interpreter/windows/python.c)
set_target_properties(cadrumo_python_bridge PROPERTIES OUTPUT_NAME "${bridge_name}")
# Debug the host against the shipped release CPython ABI and release CRT.
target_compile_options(cadrumo_python_bridge PRIVATE "$<$<CONFIG:Debug>:/U_DEBUG>")
target_include_directories(cadrumo_python_bridge PRIVATE "${CPYTHON_ROOT}/include")
target_link_libraries(cadrumo_python_bridge PRIVATE "${CPYTHON_ROOT}/libs/python313.lib")
add_dependencies(cadrumo_python_bridge python_dependencies)
add_executable(platform_static_consumer platform/tests/consumer.c)
add_executable(platform_dll_consumer platform/tests/consumer.c)
include("${PROJECT_SOURCE_DIR}/native/cmake/CompilePolicy.cmake")
foreach(target ${host_targets} cadrumo_python_bridge platform_static_consumer platform_dll_consumer)
  cadrumo_compile_policy(${target})
  target_include_directories(${target} PRIVATE "${CONTRACT_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/platform/include")
  add_dependencies(${target} native_contract)
endforeach()
foreach(target ${host_targets} platform_static_consumer)
  target_link_libraries(${target} PRIVATE "${platform_static}" userenv ws2_32 ntdll bcrypt shell32 ole32 advapi32)
  add_dependencies(${target} rust_platform)
endforeach()
foreach(target ${host_targets} cadrumo_python_bridge)
  add_dependencies(${target} native_metadata)
endforeach()
add_custom_target(python DEPENDS cadrumo_python cadrumo_python_bridge)
add_custom_target(python_d DEPENDS cadrumo_python_d cadrumo_python_bridge)
target_link_libraries(platform_dll_consumer PRIVATE "${platform_import}")
add_dependencies(platform_dll_consumer rust_platform)
foreach(target platform_static_consumer platform_dll_consumer)
  target_compile_options(${target} PRIVATE /UNDEBUG)
endforeach()
if(BUILD_TESTING)
  add_test(NAME platform.static COMMAND platform_static_consumer)
  add_test(NAME platform.dll COMMAND platform_dll_consumer)
  set_tests_properties(platform.dll PROPERTIES WORKING_DIRECTORY "${platform_dir}")
  add_test(NAME platform.rust COMMAND "${platform_dir}/platform-consumer.exe")
  set_tests_properties(platform.dll PROPERTIES ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:${platform_dir}")
endif()
