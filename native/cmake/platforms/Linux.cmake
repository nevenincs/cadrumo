if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "Linux adapter requires a Linux target")
endif()
include("${CMAKE_CURRENT_LIST_DIR}/Posix.cmake")
