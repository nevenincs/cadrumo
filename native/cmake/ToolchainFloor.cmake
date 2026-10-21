# native/toolchain.json declares minimum tool versions; any newer release is admitted.
include_guard(GLOBAL)

# Set output to a refusal message when found is not a version at or above floor, else to "".
function(cadrumo_floor_violation output tool found floor)
  if(NOT found MATCHES "^[0-9]+(\\.[0-9]+)*$")
    set(${output} "${tool} version '${found}' is not a dotted numeric version" PARENT_SCOPE)
  elseif(found VERSION_LESS floor)
    set(${output} "${tool} ${found} is below the native/toolchain.json floor ${floor}" PARENT_SCOPE)
  else()
    set(${output} "" PARENT_SCOPE)
  endif()
endfunction()

# Set output to the newest versioned child of directory at or above floor whose every marker
# exists; markers are absolute paths with {version} standing for the candidate. Empty if none.
function(cadrumo_newest_at_floor output directory floor)
  file(GLOB candidates LIST_DIRECTORIES true RELATIVE "${directory}" "${directory}/*")
  set(selected "")
  foreach(candidate IN LISTS candidates)
    if(NOT candidate MATCHES "^[0-9]+(\\.[0-9]+)*$" OR candidate VERSION_LESS floor
        OR (selected AND candidate VERSION_LESS_EQUAL selected))
      continue()
    endif()
    set(complete TRUE)
    foreach(marker IN LISTS ARGN)
      string(REPLACE "{version}" "${candidate}" marker "${marker}")
      if(NOT EXISTS "${marker}")
        set(complete FALSE)
      endif()
    endforeach()
    if(complete)
      set(selected "${candidate}")
    endif()
  endforeach()
  set(${output} "${selected}" PARENT_SCOPE)
endfunction()
