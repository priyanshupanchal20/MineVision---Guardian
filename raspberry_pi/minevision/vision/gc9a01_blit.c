/* Fast GC9A01 SPI via /dev/gpiomem. pigpio bb_spi is capped at 500 kHz.
 *
 * gcc -O3 -fomit-frame-pointer -shared -fPIC -o gc9a01_blit.so gc9a01_blit.c
 */

#define _GNU_SOURCE

#include <fcntl.h>
#include <sched.h>
#include <stdint.h>
#include <sys/mman.h>
#include <unistd.h>

#define GPIO_LEN 4096
#define GPSET0 7
#define GPCLR0 10

static volatile uint32_t *gpio;
static uint32_t cs_bit, mosi_bit, sck_bit, dc_bit;
static int ready;

static void pin_output(unsigned pin) {
    unsigned reg = pin / 10;
    unsigned shift = (pin % 10) * 3;
    uint32_t v = gpio[reg];
    v &= ~(7u << shift);
    v |= (1u << shift);
    gpio[reg] = v;
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
    return 0;
}

static inline void spi_byte(uint8_t b) {
    for (int i = 0; i < 8; i++) {
        if (b & 0x80)
            gpio[GPSET0] = mosi_bit;
        else
            gpio[GPCLR0] = mosi_bit;
        gpio[GPSET0] = sck_bit;
        __asm__ __volatile__("nop\nnop\nnop\nnop");
        gpio[GPCLR0] = sck_bit;
        b <<= 1;
    }
}

int gc9a01_init(int cs, int mosi, int sck, int dc) {
    if (map_gpio() < 0)
        return -2;
    cs_bit = 1u << (unsigned)cs;
    mosi_bit = 1u << (unsigned)mosi;
    sck_bit = 1u << (unsigned)sck;
    dc_bit = 1u << (unsigned)dc;
    pin_output((unsigned)cs);
    pin_output((unsigned)mosi);
    pin_output((unsigned)sck);
    pin_output((unsigned)dc);
    gpio[GPSET0] = cs_bit;
    gpio[GPCLR0] = sck_bit | mosi_bit;
    gpio[GPSET0] = dc_bit;
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(2, &set);
    sched_setaffinity(0, sizeof(set), &set);
    ready = 1;
    return 0;
}

int gc9a01_write(int dc, const uint8_t *p, int n) {
    if (!ready || !p || n <= 0)
        return -1;
    if (dc)
        gpio[GPSET0] = dc_bit;
    else
        gpio[GPCLR0] = dc_bit;
    gpio[GPCLR0] = cs_bit;
    for (int i = 0; i < n; i++)
        spi_byte(p[i]);
    gpio[GPSET0] = cs_bit;
    return n;
}
