include_guard(GLOBAL)

# A binary directory is build/<configure preset name> at the repository root, for the
# project being configured. A directory of any other name holds outputs that no preset,
# script default or cleanup knows about.
function(cadrumo_require_enrolled_binary_directory binary_dir presets repository_root)
  if(NOT EXISTS "${presets}")
    message(FATAL_ERROR "This project enrols no binary directory: ${presets} is missing")
  endif()
  file(READ "${presets}" document)
  string(JSON count ERROR_VARIABLE unreadable LENGTH "${document}" configurePresets)
  if(unreadable OR count LESS 1)
    message(FATAL_ERROR "${presets} declares no configure preset")
  endif()
  set(enrolled "")
  math(EXPR last "${count} - 1")
  foreach(index RANGE ${last})
    string(JSON hidden ERROR_VARIABLE absent GET "${document}" configurePresets ${index} hidden)
    if(NOT absent AND hidden)
      continue()
    endif()
    string(JSON name GET "${document}" configurePresets ${index} name)
    list(APPEND enrolled "${name}")
  endforeach()
  # A root spelled through .. normalizes with a trailing separator; joining first removes it.
  cmake_path(APPEND repository_root build OUTPUT_VARIABLE owner)
  cmake_path(ABSOLUTE_PATH owner NORMALIZE)
  cmake_path(ABSOLUTE_PATH binary_dir NORMALIZE OUTPUT_VARIABLE selected)
  cmake_path(GET selected FILENAME leaf)
  cmake_path(GET selected PARENT_PATH parent)
  set(expected "${owner}")
  if(CMAKE_HOST_WIN32)
    string(TOLOWER "${parent}" parent)
    string(TOLOWER "${expected}" expected)
  endif()
  if(NOT parent STREQUAL expected OR NOT leaf IN_LIST enrolled)
    list(JOIN enrolled ", " names)
    message(FATAL_ERROR
      "${selected} is not an enrolled binary directory. Configure with cmake --preset <name>; "
      "this project builds only into ${owner}/<name>, where <name> is one of: ${names}")
  endif()

  # Lexical containment is not enough: a linked build directory could redirect every
  # declared output outside the repository. Resolve the repository and both build path
  # components before accepting the preset directory; this also catches Windows junctions.
  file(REAL_PATH "${repository_root}" physical_repository_root)
  cmake_path(APPEND physical_repository_root build OUTPUT_VARIABLE physical_owner)
  file(REAL_PATH "${owner}" resolved_owner)
  cmake_path(APPEND physical_owner "${leaf}" OUTPUT_VARIABLE physical_selected)
  file(REAL_PATH "${selected}" resolved_selected)
  if(CMAKE_HOST_WIN32)
    string(TOLOWER "${physical_owner}" physical_owner)
    string(TOLOWER "${resolved_owner}" resolved_owner)
    string(TOLOWER "${physical_selected}" physical_selected)
    string(TOLOWER "${resolved_selected}" resolved_selected)
  endif()
  if(NOT resolved_owner STREQUAL physical_owner OR NOT resolved_selected STREQUAL physical_selected)
    message(FATAL_ERROR
      "${selected} resolves to ${resolved_selected}, not its enrolled physical path ${physical_selected}. "
      "A symlink or junction in the build path is not allowed.")
  endif()
endfunction()
