# Copyright (c) 2026 embeddedboys developers
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# CoreMark on a Pico, clocked by pico-turbo.
#
# The clock, the core voltage and the flash divider are pico-turbo's job: it
# knows the order the regulator and the clock have to be changed in, it derives
# the divider from the highest frequency the build can reach (and rounds it to
# the even number both boot stages insist on), and with PICO_TURBO_AUTOTUNE it
# searches for the frequency instead of being told one.  This project then only
# has to run CoreMark and report what the chip was actually doing.
#
#   cmake -S . -B build -DPICO_BOARD=pico2 \
#         -DPICO_TURBO_DIR=/path/to/pico-turbo \
#         -DPICO_TURBO_SYS_CLK_KHZ=570000 -DPICO_TURBO_VREG_VOLTAGE=VREG_VOLTAGE_1_60
#   cmake --build build -j
#   cmake --build build --target flash      # erase, program, verify, run
#
# Compare two frequencies on identical work with -DCOREMARK_ITERATIONS=<n>;
# left alone, the iteration count scales with the clock so that every run takes
# about the same wall time (which is what a "CoreMark/MHz" style score wants).

cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(rpi-pico-coremark C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_EXE_LINKER_FLAGS_RELEASE "${CMAKE_EXE_LINKER_FLAGS_RELEASE} -Wl,--print-memory-usage")

if (PICO_SDK_VERSION_STRING VERSION_LESS "2.0.0")
    message(FATAL_ERROR "Raspberry Pi Pico SDK version 2.0.0 (or later) required. Your version is ${PICO_SDK_VERSION_STRING}")
endif()

# If you want debug output from USB (pass -DPICO_STDIO_USB=1) this ensures you don't lose any debug output while USB is set up
if (NOT DEFINED PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS)
    set(PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS 3000)
endif()

pico_sdk_init()

add_compile_options(-Wall
        -Wno-format          # int != int32_t as far as the compiler is concerned because gcc has int32_t as long int
        -Wno-unused-function # we have some for the docs that aren't called
        )
if (CMAKE_C_COMPILER_ID STREQUAL "GNU")
    add_compile_options(-Wno-maybe-uninitialized)
endif()

# --- the clock, the voltage and the flash divider: pico-turbo ----------------
if(NOT DEFINED PICO_TURBO_DIR)
    set(PICO_TURBO_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../pico-turbo" CACHE PATH
        "where the pico-turbo checkout lives")
endif()
if(NOT EXISTS "${PICO_TURBO_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "pico-turbo not found at ${PICO_TURBO_DIR}: pass -DPICO_TURBO_DIR=<path>")
endif()
add_subdirectory(${PICO_TURBO_DIR} ${CMAKE_BINARY_DIR}/pico_turbo)

# The frequency the score is reported against: what the library was asked for,
# or the platform's stock clock when no overclocking was configured.
if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
    set(PICO_BASE_SYS_CLK_KHZ 125000)
    set(COREMARK_BASE_ITRE 3000)
elseif(${PICO_BOARD} STREQUAL "pico2" OR ${PICO_PLATFORM} STREQUAL "rp2350")
    set(PICO_BASE_SYS_CLK_KHZ 150000)
    set(COREMARK_BASE_ITRE 5000)
endif()
if(PICO_TURBO_SYS_CLK_KHZ)
    set(COREMARK_SYS_CLK_KHZ ${PICO_TURBO_SYS_CLK_KHZ})
else()
    set(COREMARK_SYS_CLK_KHZ ${PICO_BASE_SYS_CLK_KHZ})
endif()

# Iterations.  Zero (the default) leaves ITERATIONS undefined and lets CoreMark
# calibrate: it runs for a second, then scales so the measured run is about ten
# seconds -- which is what CoreMark's reporting rules ask for, at every clock and
# without a formula to get wrong.  A fixed count is only useful to compare two
# runs on identical work; note that a count that is fine at 150 MHz is under
# CoreMark's ten seconds at 500 MHz, which it reports as "Errors detected" even
# though the results were correct.
# (The port's core_portme.c has a #ifndef ITERATIONS fallback, so ITERATIONS
# cannot be left undefined and CoreMark cannot calibrate itself: the count is
# computed here instead, from the clock, so that a run takes about twelve
# seconds -- which is CoreMark's own rule for a reportable result.)
if(NOT DEFINED COREMARK_ITERATIONS OR COREMARK_ITERATIONS EQUAL 0)
    math(EXPR COREMARK_ITERATIONS
        "${COREMARK_BASE_ITRE} * ${COREMARK_SYS_CLK_KHZ} / ${PICO_BASE_SYS_CLK_KHZ}")
    if(COREMARK_MULTITHREAD GREATER 1)
        # Two contexts share the machine and finish in about half the time, so
        # the same iteration count would drop under CoreMark's ten seconds.
        math(EXPR COREMARK_ITERATIONS "${COREMARK_ITERATIONS} * 2")
    endif()
endif()

# Repeat the whole benchmark this many times, rebooting between runs with the
# watchdog and counting in its scratch registers.  Each run is a calibration plus
# a ten second measurement, so ~50 repeats is a ten minute soak -- which is what
# "stable" should be based on, rather than a single run.  A repeat count of 1
# leaves the board blinking.
if(NOT DEFINED COREMARK_REPEAT)
    set(COREMARK_REPEAT 1)
endif()

math(EXPR COREMARK_SYS_MHZ "${COREMARK_SYS_CLK_KHZ} / 1000")
message(STATUS "coremark: ${COREMARK_SYS_MHZ} MHz, ${COREMARK_ITERATIONS} iterations")

include_directories(. include)

file(GLOB_RECURSE COMMON_SOURCES
    core_list_join.c
    core_main.c
    core_matrix.c
    core_portme.c
    core_state.c
    core_util.c
)

add_executable(${PROJECT_NAME} ${COMMON_SOURCES})
target_link_libraries(${PROJECT_NAME}
    pico_turbo
    pico_bootsel_via_double_reset
    pico_multicore
    pico_stdlib
)
target_include_directories(${PROJECT_NAME} PUBLIC .)

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    string(REPLACE "\"" "\\\"" FLAGS_STR_ESCAPED "${CMAKE_C_FLAGS} ${CMAKE_C_FLAGS_RELEASE}")
elseif(CMAKE_BUILD_TYPE STREQUAL "Debug")
    string(REPLACE "\"" "\\\"" FLAGS_STR_ESCAPED "${CMAKE_C_FLAGS} ${CMAKE_C_FLAGS_DEBUG}")
endif()

# Contexts to run.  The Pico has two cores, so 2 runs one CoreMark per core and
# reports both: it is the same measurement with more current asked of the
# regulator, which is where a marginal voltage shows up.
if(NOT DEFINED COREMARK_MULTITHREAD)
    set(COREMARK_MULTITHREAD 1)
endif()

target_compile_definitions(${PROJECT_NAME} PRIVATE
    FLAGS_STR="${FLAGS_STR_ESCAPED}"
    DEFAULT_SYS_CLK_KHZ=${COREMARK_SYS_CLK_KHZ}
    MULTITHREAD=${COREMARK_MULTITHREAD}
    COREMARK_REPEAT=${COREMARK_REPEAT}
)
target_compile_definitions(${PROJECT_NAME} PRIVATE ITERATIONS=${COREMARK_ITERATIONS})
# CoreMark's memory method is left alone: MEM_STATIC is refused outright with more
# than one context ("Cannot use a static data area with multiple contexts!"), so
# the per-context blocks live in stack_memblock[TOTAL_DATA_SIZE * MULTITHREAD] in
# main() -- a few kilobytes on core 0's stack, which is what the barebones port
# expects and what the default stack has room for.

# default | copy_to_ram | no_flash: copy_to_ram is what tells a flash-limited
# result apart from a core-limited one.
if(NOT DEFINED PICO_TURBO_BINARY_TYPE)
    set(PICO_TURBO_BINARY_TYPE default)
endif()
pico_set_binary_type(${PROJECT_NAME} ${PICO_TURBO_BINARY_TYPE})

pico_enable_stdio_usb(${PROJECT_NAME} 1)
pico_enable_stdio_uart(${PROJECT_NAME} 1)
# Wait for a host to open the port before printing anything.  Without this the
# SDK drops every character written while nobody is attached, so a run whose
# reader is a second late prints nothing at all -- and a soak that reboots
# between runs is exactly when a reader is a second late.  With it, each boot
# waits for the port instead of the run being silently lost.  The wait happens in
# portable_init(), before CoreMark starts timing, so it costs nothing but time.
target_compile_definitions(${PROJECT_NAME} PRIVATE
    PICO_STDIO_USB_CONNECT_WAIT_TIMEOUT_MS=20000)
pico_add_extra_outputs(${PROJECT_NAME})

add_custom_target(
    print-memory-usage ALL
    COMMAND arm-none-eabi-size -G ${CMAKE_PROJECT_NAME}.elf
    DEPENDS ${PROJECT_NAME}
    COMMENT "Print target size info"
)

# Erase first, then program, then verify: openocd has been seen reporting
# "Verified OK" here after writing only the first couple of kilobytes of the
# image, which leaves the chip running whatever was there before.
if(NOT DEFINED PICO_OPENOCD_TARGET)
    if(${PICO_BOARD} STREQUAL "pico" OR ${PICO_PLATFORM} STREQUAL "rp2040")
        set(PICO_OPENOCD_TARGET target/rp2040.cfg)
    else()
        set(PICO_OPENOCD_TARGET target/rp2350.cfg)
    endif()
endif()
add_custom_target(
    flash
    COMMAND openocd -f interface/cmsis-dap.cfg -c "adapter speed 1000"
            -f ${PICO_OPENOCD_TARGET}
            -c "program ${CMAKE_PROJECT_NAME}.elf verify reset exit"
    DEPENDS ${PROJECT_NAME}
    COMMENT "Flashing firmware using CMSIS-DAP Debugger..."
)
add_custom_target(
    flash-erase
    COMMAND openocd -f interface/cmsis-dap.cfg -c "adapter speed 1000"
            -f ${PICO_OPENOCD_TARGET}
            -c "init" -c "halt" -c "flash probe 0" -c "flash erase_sector 0 0 1023"
            -c "program ${CMAKE_PROJECT_NAME}.elf verify reset exit" -c "shutdown"
    DEPENDS ${PROJECT_NAME}
    COMMENT "Erasing the flash, then programming and verifying..."
)
