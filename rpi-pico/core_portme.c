/*
Copyright 2018 Embedded Microprocessor Benchmark Consortium (EEMBC)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Original Author: Shay Gal-on
*/

#include <stdio.h>
#include <stdlib.h>
#include "coremark.h"

#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/clocks.h"
#include "hardware/structs/watchdog.h"
#include "hardware/watchdog.h"

#include "pico_turbo.h"

#if MULTITHREAD > 1
/* The Pico has one core to spare, so the parallel contexts go to core 1 one at a
 * time: CoreMark starts every context with core_start_parallel() and joins it
 * with core_stop_parallel(), and the first caller gets core 1 while the second
 * runs here on core 0.  Both do the same work with their own results block, which
 * is what CoreMark compares. */
static core_results *s_core1_ctx;
static volatile ee_u8 s_core1_busy;
static volatile ee_u8 s_core1_done;

/*: FIFO tokens: core 1 says it is running, and says it is finished.  Without the
 *: first one a launch that did not take would look like a hang, which is the sort
 *: of thing that gets blamed on the clock. */
#define CORE1_STARTED 0xc0de0001u
#define CORE1_DONE 0xc0de0002u

/*: Core 1 gets its own stack, sized here rather than left to the SDK's default:
 *: the default is small, and a context that overflows it faults instead of
 *: finishing -- which the waiting core 0 sees as a hang.  Eight kilobytes costs
 *: nothing on this chip and is what CoreMark's own report should be measuring,
 *: not a stack shortage. */
static uint32_t core1_stack[2048] __attribute__((aligned(8)));

static void core1_entry(void)
{
	multicore_fifo_push_blocking(CORE1_STARTED);
	iterate(s_core1_ctx);
	__dmb();
	s_core1_done = 1;
	multicore_fifo_push_blocking(CORE1_DONE);
	for (;;) {
		tight_loop_contents();
	}
}

ee_u8 core_start_parallel(core_results *res)
{
	uint32_t token = 0;

	if (s_core1_busy) {
		/* Core 1 already has a context: run this one on the calling core. */
		ee_printf("Parallel context on core 0\n");
		iterate(res);
		return 0;
	}

	s_core1_ctx = res;
	s_core1_done = 0;
	__dmb();
	s_core1_busy = 1;
	multicore_reset_core1();
	multicore_launch_core1_with_stack(core1_entry, core1_stack,
					  sizeof(core1_stack));

	if (!multicore_fifo_pop_timeout_us(2000000, &token) ||
	    token != CORE1_STARTED) {
		/* Core 1 did not come up.  Say so and run the context here rather than
		 * waiting for a result that is never coming. */
		ee_printf("ERROR! core 1 did not start (token %08x)\n", token);
		s_core1_busy = 0;
		iterate(res);
		return 0;
	}

	ee_printf("Parallel context on core 1\n");

	return 0;
}

ee_u8 core_stop_parallel(core_results *res)
{
	if (s_core1_busy && s_core1_ctx == res) {
		uint32_t token = 0;

		while (!s_core1_done) {
			tight_loop_contents();
		}
		(void)multicore_fifo_pop_timeout_us(1000000, &token);
		s_core1_busy = 0;
	}

	return 0;
}
#endif /* MULTITHREAD > 1 */

#ifndef ITERATIONS
#define ITERATIONS 3000
#endif

#if VALIDATION_RUN
volatile ee_s32 seed1_volatile = 0x3415;
volatile ee_s32 seed2_volatile = 0x3415;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PERFORMANCE_RUN
volatile ee_s32 seed1_volatile = 0x0;
volatile ee_s32 seed2_volatile = 0x0;
volatile ee_s32 seed3_volatile = 0x66;
#endif
#if PROFILE_RUN
volatile ee_s32 seed1_volatile = 0x8;
volatile ee_s32 seed2_volatile = 0x8;
volatile ee_s32 seed3_volatile = 0x8;
#endif
volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;
/* Porting : Timing functions
        How to capture time and convert to seconds must be ported to whatever is
   supported by the platform. e.g. Read value from on board RTC, read value from
   cpu clock cycles performance counter etc. Sample implementation for standard
   time.h and windows.h definitions included.
*/
/* Define : TIMER_RES_DIVIDER
        Divider to trade off timer resolution and total time that can be
   measured.

        Use lower values to increase resolution, but make sure that overflow
   does not occur. If there are issues with the return value overflowing,
   increase this value.
        */
#define NSECS_PER_SEC 1000000
#define CORETIMETYPE uint32_t
#define GETMYTIME(_t) (*_t = clock())
#define MYTIMEDIFF(fin, ini) ((fin) - (ini))
#define TIMER_RES_DIVIDER 1
#define SAMPLE_TIME_IMPLEMENTATION 1
#define EE_TICKS_PER_SEC (NSECS_PER_SEC / TIMER_RES_DIVIDER)

/** Define Host specific (POSIX), or target specific global time variables. */
static CORETIMETYPE start_time_val, stop_time_val;

/* The board's user led, where the board has one to drive.  A Pico W does not:
 * its led hangs off the wireless chip, and PICO_DEFAULT_LED_PIN is not defined,
 * so the run reports progress only in the console there. */
#if defined(PICO_DEFAULT_LED_PIN)
static int led = PICO_DEFAULT_LED_PIN;
#define PORT_HAS_LED 1
#else
#define PORT_HAS_LED 0
#endif

/* Function : start_time
        This function will be called right before starting the timed portion of
   the benchmark.

        Implementation may be capturing a system timer (as implemented in the
   example code) or zeroing some system parameters - e.g. setting the cpu clocks
   cycles to 0.
*/
void start_time(void)
{
	// GETMYTIME(&start_time_val);
	start_time_val = time_us_32();
}
/* Function : stop_time
        This function will be called right after ending the timed portion of the
   benchmark.

        Implementation may be capturing a system timer (as implemented in the
   example code) or other system parameters - e.g. reading the current value of
   cpu cycles counter.
*/
void stop_time(void)
{
	// GETMYTIME(&stop_time_val);
	stop_time_val = time_us_32();
}
/* Function : get_time
        Return an abstract "ticks" number that signifies time on the system.

        Actual value returned may be cpu cycles, milliseconds or any other
   value, as long as it can be converted to seconds by <time_in_secs>. This
   methodology is taken to accommodate any hardware or simulated platform. The
   sample implementation returns millisecs by default, and the resolution is
   controlled by <TIMER_RES_DIVIDER>
*/
CORE_TICKS
get_time(void)
{
	CORE_TICKS elapsed =
		(CORE_TICKS)(MYTIMEDIFF(stop_time_val, start_time_val));
	return elapsed;
}
/* Function : time_in_secs
        Convert the value returned by get_time to seconds.

        The <secs_ret> type is used to accommodate systems with no support for
   floating point. Default implementation implemented by the EE_TICKS_PER_SEC
   macro above.
*/
secs_ret time_in_secs(CORE_TICKS ticks)
{
	secs_ret retval = ((secs_ret)ticks) / (secs_ret)EE_TICKS_PER_SEC;
	return retval;
}

/* Contexts to run: one per core when MULTITHREAD is set to 2, which is the
 * point of the exercise on a Pico -- two cores at the same clock draw more
 * current, so a voltage that is merely good enough for one core gets caught. */
ee_u32 default_num_contexts = MULTITHREAD;

/* Function : portable_init
        Target specific initialization code
        Test for some common mistakes.
*/
void portable_init(core_portable *p, int *argc, char *argv[])
{
	(void)argc; // prevent unused warning
	(void)argv; // prevent unused warning

	/* The clock, the core voltage and the flash divider are pico-turbo's: it
	 * changes the regulator and the clock in the order the move needs, derives
	 * the divider from the highest frequency this build can reach, and with
	 * PICO_TURBO_AUTOTUNE it searches for the frequency rather than taking the
	 * one it was given.  Called before any peripheral, as it documents. */
	pico_turbo_init();

	stdio_uart_init_full(uart0, 115200, 0, 1);
	stdio_usb_init();

	ee_printf("\n\n\nRaspberry Pi Pico CoreMark benchmark running ...\n");
	ee_printf("CPU speed: %d(MHz), Flash speed: %d(MHz)\n",
		  (int)(pico_turbo_state().sys_clk_khz / 1000u),
		  (int)(pico_turbo_state().flash_clk_khz / 1000u));
	{
		unsigned vco = 0, pd1 = 0, pd2 = 0;
		bool ok = check_sys_clock_khz(DEFAULT_SYS_CLK_KHZ, &vco, &pd1, &pd2);

		ee_printf("DIAG: check_sys_clock_khz(%d) -> %s "
			  "(vco %u, postdiv %u/%u)\n",
			  (int)DEFAULT_SYS_CLK_KHZ, ok ? "achievable" : "NOT",
			  vco, pd1, pd2);
	}

	/* One line a log can be read back from: what was asked for, what the chip is
	 * actually running (measured with the hardware counter, not read out of the
	 * configuration), and the rest of the clocks the answer depends on. */
	{
		pico_turbo_state_t st = pico_turbo_state();
		uint32_t measured =
			frequency_count_khz(CLOCKS_FC0_SRC_VALUE_CLK_SYS);

		ee_printf("PICO-TURBO: %lu kHz asked, %lu kHz configured, "
			  "%lu kHz measured, vreg sel %u, flash %lu kHz, "
			  "clk_peri %lu kHz, usb %s\n",
			  (unsigned long)st.requested_khz,
			  (unsigned long)st.sys_clk_khz,
			  (unsigned long)measured, (unsigned)st.vreg_sel,
			  (unsigned long)st.flash_clk_khz,
			  (unsigned long)st.peri_clk_khz,
			  st.usb_ok ? "ok" : "WRONG");
	}

#if PORT_HAS_LED
	gpio_init(led);
	gpio_set_dir(led, GPIO_OUT);
#else
	ee_printf("(no user led on this board: %s)\n", PICO_BOARD);
#endif

	if (sizeof(ee_ptr_int) != sizeof(ee_u8 *)) {
		ee_printf(
			"ERROR! Please define ee_ptr_int to a type that holds a "
			"pointer!\n");
	}
	if (sizeof(ee_u32) != 4) {
		ee_printf(
			"ERROR! Please define ee_u32 to a 32b unsigned type!\n");
	}
	p->portable_id = 1;
#if PORT_HAS_LED
	gpio_put(led, 1);
#endif
}
/* Function : portable_fini
        Target specific final code
*/
/*: A run counter that survives the watchdog reboot between runs: slot 6 says the
 *: counter is ours, slot 7 is the count.  pico-turbo uses 0-3 and 6 for its own
 *: search, which this build does not run, and the SDK keeps 4. */
#define CORE_REPEAT_MAGIC 0x636d726bu /* 'cmrk' */
#define CORE_REPEAT_MAGIC_IDX 6u
#define CORE_REPEAT_COUNT_IDX 7u

void portable_fini(core_portable *p)
{
	p->portable_id = 0;

#if COREMARK_REPEAT > 1
	{
		uint32_t runs = 0;

		if (watchdog_hw->scratch[CORE_REPEAT_MAGIC_IDX] ==
		    CORE_REPEAT_MAGIC) {
			runs = watchdog_hw->scratch[CORE_REPEAT_COUNT_IDX];
		}
		runs++;
		ee_printf("COREMARK-REPEAT: run %lu of %d\n",
			  (unsigned long)runs, (int)COREMARK_REPEAT);

		if (runs < (uint32_t)COREMARK_REPEAT) {
			watchdog_hw->scratch[CORE_REPEAT_MAGIC_IDX] =
				CORE_REPEAT_MAGIC;
			watchdog_hw->scratch[CORE_REPEAT_COUNT_IDX] = runs;
			/* Reboot through the bootrom so the next run starts from the same
			 * state, clock and voltage included -- the point of repeating is to
			 * soak the chip, not to measure a warm continuation of it. */
			sleep_ms(100);
			watchdog_reboot(0, 0, 0);
			for (;;) {
				tight_loop_contents();
			}
		}

		watchdog_hw->scratch[CORE_REPEAT_MAGIC_IDX] = 0;
		watchdog_hw->scratch[CORE_REPEAT_COUNT_IDX] = 0;
		ee_printf("COREMARK-REPEAT: all %d runs finished\n",
			  (int)COREMARK_REPEAT);
	}
#endif

	for (;;) {
#if PORT_HAS_LED
		gpio_put(led, 0);
		sleep_ms(200);
		gpio_put(led, 1);
#else
		sleep_ms(200);
#endif
		sleep_ms(200);
	}
}
