# Release callers supply the captured identifier; local development defaults to 1.
set(CADRUMO_BUILD_NUMBER "1" CACHE STRING "Explicit numeric build identifier")
if(NOT CADRUMO_BUILD_NUMBER MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR "CADRUMO_BUILD_NUMBER must be a positive integer")
endif()
