add_custom_command(OUTPUT "${CONTRACT_DIR}/build_metadata.h" "${CONTRACT_DIR}/build.json"
    "${CONTRACT_DIR}/interpreter.rc" "${CONTRACT_DIR}/cadrumo.ico"
  COMMAND ${CADRUMO_HELPER} run -- "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.metadata "${CONTRACT_DIR}"
    --number "${CADRUMO_BUILD_NUMBER}" --date "${CADRUMO_BUILD_DATE}" --tools "${PROJECT_BINARY_DIR}/_deps/build-tools"
    --channel "${CADRUMO_CHANNEL}"
  DEPENDS ${native_helper_inputs} ${contract_inputs}
    "${CONTRACT_DIR}/identity.json"
    "${PROJECT_SOURCE_DIR}/docs/_static/cadrumo-favicon.svg" "${PROJECT_BINARY_DIR}/_deps/build-tools/ready"
    "${PROJECT_SOURCE_DIR}/pyproject.toml" "${PROJECT_SOURCE_DIR}/dev/packaging/release-python-version"
  WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" VERBATIM)
add_custom_target(native_metadata DEPENDS "${CONTRACT_DIR}/build_metadata.h" "${CONTRACT_DIR}/build.json"
  "${CONTRACT_DIR}/interpreter.rc" "${CONTRACT_DIR}/cadrumo.ico")
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
set(platform_dir "${PROJECT_BINARY_DIR}/cargo/${CADRUMO_PIN_rust_target}/${rust_profile}")
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

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/bin/$<CONFIG>")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/lib/$<CONFIG>")
set(CMAKE_PDB_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/symbols/$<CONFIG>")
add_executable(cadrumo_python interpreter/windows/host.c interpreter/windows/host.manifest "${CONTRACT_DIR}/interpreter.rc")
set_target_properties(cadrumo_python PROPERTIES OUTPUT_NAME "${production_name}")
add_executable(cadrumo_python_d EXCLUDE_FROM_ALL interpreter/windows/host.c interpreter/windows/host.manifest "${CONTRACT_DIR}/interpreter.rc")
set_target_properties(cadrumo_python_d PROPERTIES OUTPUT_NAME "${development_name}")
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
foreach(target cadrumo_python cadrumo_python_d cadrumo_python_bridge platform_static_consumer platform_dll_consumer)
  cadrumo_compile_policy(${target})
  target_include_directories(${target} PRIVATE "${CONTRACT_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/platform/include")
  add_dependencies(${target} native_contract)
endforeach()
foreach(target cadrumo_python cadrumo_python_d platform_static_consumer)
  target_link_libraries(${target} PRIVATE "${platform_static}" userenv ws2_32 ntdll bcrypt shell32 ole32 advapi32)
  add_dependencies(${target} rust_platform)
endforeach()
foreach(target cadrumo_python cadrumo_python_d cadrumo_python_bridge)
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
