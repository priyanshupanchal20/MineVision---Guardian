/* OV7670 DVP grabber for Raspberry Pi 3.
 *
 * Data is sampled AFTER the PCLK edge so D0–D7 have settled.
 * First few clocks of each HREF line are skipped (blanking).
 *
 * gcc -O3 -fomit-frame-pointer -shared -fPIC -o ov7670_grab.so ov7670_grab.c
 */

#define _GNU_SOURCE

#include <fcntl.h>
#include <sched.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

#define GPIO_LEN 4096
#define GPLEV0 13
#define PCLK_BIT  (1u << 22)
#define VSYNC_BIT (1u << 27)
#define HREF_BIT  (1u << 17)
#define MAX_LINE 1280
#define MAX_ROWS 240
#define SKIP_LEAD 8

static volatile uint32_t *gpio;
static int rt_done;

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static void pin_input(unsigned pin) {
    unsigned reg = pin / 10;
    unsigned shift = (pin % 10) * 3;
    gpio[reg] &= ~(7u << shift);
}

static int map_gpio(void) {
    if (gpio)
        return 0;
    int fd = open("/dev/gpiomem", O_RDWR | O_SYNC);
    if (fd < 0)
        return -2;
    void *m = mmap(0, GPIO_LEN, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (m == MAP_FAILED)
        return -2;
    gpio = (volatile uint32_t *)m;
    static const unsigned pins[] = {5, 6, 13, 16, 17, 19, 20, 21, 22, 26, 27};
    for (unsigned i = 0; i < sizeof pins / sizeof pins[0]; i++)
        pin_input(pins[i]);
    return 0;
}

static void try_rt(void) {
    if (rt_done)
        return;
    rt_done = 1;
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(3, &set);
    sched_setaffinity(0, sizeof(set), &set);
    setpriority(PRIO_PROCESS, 0, -20);
    struct sched_param sp;
    sp.sched_priority = 80;
    sched_setscheduler(0, SCHED_FIFO, &sp);
}

static inline uint32_t lev(void) { return gpio[GPLEV0]; }

static inline uint8_t pack(uint32_t v) {
    return (uint8_t)(((v >> 5) & 1u) | ((v >> 5) & 2u) | ((v >> 11) & 4u) |
                     ((v >> 16) & 8u) | ((v >> 22) & 16u) | ((v >> 11) & 32u) |
                     ((v >> 14) & 64u) | ((v >> 14) & 128u));
}

static int wait_bit(uint32_t bit, int want_high, uint64_t deadline) {
    if (want_high) {
        while ((lev() & bit) == 0)
            if (now_ns() >= deadline)
                return 0;
    } else {
        while (lev() & bit)
            if (now_ns() >= deadline)
                return 0;
    }
    return 1;
}

static int grab_line(uint8_t *p, int maxn, int rising) {
    uint32_t last = lev();
    int n = 0;
    int skip = SKIP_LEAD;
    if (rising) {
        while (n < maxn) {
            uint32_t v = gpio[GPLEV0];
            if (!(v & HREF_BIT))
                return n;
            if ((v & ~last) & PCLK_BIT) {
                uint32_t v2 = gpio[GPLEV0];
                if (skip)
                    skip--;
                else
                    p[n++] = pack(v2);
            }
            last = v;
        }
    } else {
        while (n < maxn) {
            uint32_t v = gpio[GPLEV0];
            if (!(v & HREF_BIT))
                return n;
            if ((last & ~v) & PCLK_BIT) {
                uint32_t v2 = gpio[GPLEV0];
                if (skip)
                    skip--;
                else
                    p[n++] = pack(v2);
            }
            last = v;
        }
    }
    return n;
}

static int grab_frame(uint8_t *out, int max_bytes, int rising, uint64_t deadline,
                      int *line0_out, int *rows_out) {
    int line0 = 0;
    int rows = 0;
    int used = 0;
    uint8_t *p = out;

    while (rows < MAX_ROWS && used + MAX_LINE <= max_bytes) {
        if (!wait_bit(HREF_BIT, 0, deadline) || !wait_bit(HREF_BIT, 1, deadline))
            break;
        int nb = grab_line(p, MAX_LINE, rising);
        if (nb < 40)
            break;
        if (rows == 0) {
            line0 = nb & ~1;
            if (line0 < 40)
                break;
        } else if (nb < line0) {
            while (nb < line0)
                p[nb++] = 128;
        }
        p += line0;
        used += line0;
        rows++;
    }
    *line0_out = line0;
    *rows_out = rows;
    return used;
}

int ov7670_levels(void) {
    if (map_gpio() < 0)
        return -2;
    uint32_t v = lev();
    return (int)(((v & VSYNC_BIT) ? 4 : 0) | ((v & HREF_BIT) ? 2 : 0) |
                 ((v & PCLK_BIT) ? 1 : 0));
}

int ov7670_grab(uint8_t *out, int max_bytes, int timeout_ms, int rising,
                int *out_line_bytes, int *out_rows) {
    if (!out || max_bytes < 256)
        return -1;
    if (map_gpio() < 0)
        return -2;
    try_rt();
    if (timeout_ms < 300)
        timeout_ms = 300;
    if (out_line_bytes)
        *out_line_bytes = 0;
    if (out_rows)
        *out_rows = 0;

    uint64_t deadline = now_ns() + (uint64_t)timeout_ms * 1000000ull;
    int line0 = 0, rows = 0, used = 0;

    if (wait_bit(VSYNC_BIT, 1, deadline) && wait_bit(VSYNC_BIT, 0, deadline))
        used = grab_frame(out, max_bytes, rising, deadline, &line0, &rows);

    if (rows == 0) {
        deadline = now_ns() + (uint64_t)timeout_ms * 1000000ull;
        if (wait_bit(VSYNC_BIT, 0, deadline) && wait_bit(VSYNC_BIT, 1, deadline))
            used = grab_frame(out, max_bytes, rising, deadline, &line0, &rows);
    }

    if (out_line_bytes)
        *out_line_bytes = line0;
    if (out_rows)
        *out_rows = rows;
    return used;
}
