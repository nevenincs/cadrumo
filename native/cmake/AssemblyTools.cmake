# Native rewriting tools belong to the selected builder and never to runtime paths.
set(native_tools "{}")
set(native_tool_hashes "{}")
set(native_tool_names)
if(target_system STREQUAL "Linux")
  set(native_tool_names readelf patchelf)
elseif(target_system STREQUAL "Darwin")
  set(native_tool_names install_name_tool codesign)
endif()
foreach(name IN LISTS native_tool_names)
  string(TOUPPER "${name}" variable_suffix)
  set(variable "CADRUMO_${variable_suffix}")
  set(${variable} "" CACHE FILEPATH "Reviewed absolute ${name} tool for package assembly")
  if(NOT IS_ABSOLUTE "${${variable}}" OR NOT EXISTS "${${variable}}" OR IS_DIRECTORY "${${variable}}")
    message(FATAL_ERROR "Supply ${variable} as an absolute existing tool path for ${CADRUMO_TARGET}")
  endif()
  file(SHA256 "${${variable}}" tool_hash)
  string(JSON native_tools SET "${native_tools}" "${name}" "\"${${variable}}\"")
  string(JSON native_tool_hashes SET "${native_tool_hashes}" "${name}" "\"${tool_hash}\"")
endforeach()
string(JSON build_toolchain SET "${build_toolchain}" native_tools "${native_tools}")
string(JSON build_toolchain SET "${build_toolchain}" native_tool_sha256 "${native_tool_hashes}")
if(target_system STREQUAL "Windows")
  # The bundled llama-server imports the C++ runtime and loads it from its own directory, so the package
  # carries app-local copies. They come from the redistributable folder of the selected MSVC toolset, found
  # from the Visual Studio instance and toolset this configure resolved and never from PATH, and each is
  # hashed here for assembly to check.
  string(REGEX REPLACE ",.*$" "" msvc_redist_root "${CMAKE_GENERATOR_INSTANCE}")
  execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.msvc_redist
    --visual-studio "${msvc_redist_root}" --msvc-version "${msvc_version}"
    WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}" OUTPUT_VARIABLE msvc_redist
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
  string(JSON build_toolchain SET "${build_toolchain}" msvc_redist "${msvc_redist}")
endif()
if(target_system STREQUAL "Darwin")
  # The ad-hoc identity is the distribution signature; another local identity only
  # changes the seal on this builder's own images.
  set(CADRUMO_NATIVE_SIGNING_IDENTITY "-" CACHE STRING "Identity for signing assembled native images; - is the ad-hoc seal")
  if(CADRUMO_NATIVE_SIGNING_IDENTITY STREQUAL "")
    message(FATAL_ERROR "Supply CADRUMO_NATIVE_SIGNING_IDENTITY for macOS package assembly")
  endif()
  string(JSON build_toolchain SET "${build_toolchain}" native_signing_identity "\"${CADRUMO_NATIVE_SIGNING_IDENTITY}\"")
  # The desktop image must embed exactly the identity this build generated for it.
  string(JSON build_toolchain SET "${build_toolchain}" desktop_info_plist "\"${CADRUMO_PATH_GENERATED}/desktop-info.plist\"")
endif()
