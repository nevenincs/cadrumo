# Floor-provider evidence is an explicit verification input, never a target SDK path.
if(target_system STREQUAL "Linux")
  foreach(name readelf patchelf)
    string(TOUPPER "${name}" variable_suffix)
    cadrumo_record_builder_file("native/${name}" "${CADRUMO_${variable_suffix}}")
  endforeach()
  set(CADRUMO_LINUX_CPP_ABI_PROOF "" CACHE FILEPATH "Reviewed absolute Linux C++ floor-provider proof")
  if(NOT CADRUMO_LINUX_CPP_ABI_PROOF STREQUAL "")
    execute_process(COMMAND "${CADRUMO_DEV_PYTHON}" -B -m dev.packaging.native.cpp_abi_inputs
      --target "${CADRUMO_TARGET}" --proof "${CADRUMO_LINUX_CPP_ABI_PROOF}" --root "${PROJECT_SOURCE_DIR}"
      WORKING_DIRECTORY "${builder_source_root}" OUTPUT_VARIABLE linux_cpp_abi
      OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
    string(JSON build_toolchain SET "${build_toolchain}" linux_cpp_abi "${linux_cpp_abi}")
    foreach(member proof provider)
      string(JSON selected_path GET "${linux_cpp_abi}" "${member}")
      string(JSON selected_hash GET "${linux_cpp_abi}" "${member}_sha256")
      cadrumo_record_builder_file("linux_cpp_abi/${member}" "${selected_path}")
      string(JSON recorded_hash GET "${builder_files}" "linux_cpp_abi/${member}" sha256)
      if(NOT recorded_hash STREQUAL selected_hash)
        message(FATAL_ERROR "Selected Linux C++ floor ${member} changed during configure")
      endif()
    endforeach()
  endif()
endif()
