/**
 * E-Ink Camera - Standalone application
 * Captures photos and displays on IT8951 e-ink via USB
 *
 * Usage: sudo ./camera /dev/sda
 * Press '1' to capture, 'q' to quit
 */

#include "it8951_usb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <termios.h>
#include <time.h>
#include <sys/time.h>

#define DISPLAY_WIDTH  1872
#define DISPLAY_HEIGHT 1404

// Get time in milliseconds
static double get_time_ms() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000.0 + tv.tv_usec / 1000.0;
}

// Set terminal to raw mode for single keypress detection
static struct termios orig_termios;

static void disable_raw_mode() {
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &orig_termios);
}

static void enable_raw_mode() {
    tcgetattr(STDIN_FILENO, &orig_termios);
    atexit(disable_raw_mode);

    struct termios raw = orig_termios;
    raw.c_lflag &= ~(ECHO | ICANON);
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 1;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
}

// Create a large digit image (7-segment style)
static void draw_digit(uint8_t *buf, int digit) {
    memset(buf, 0xFF, DISPLAY_WIDTH * DISPLAY_HEIGHT);  // White background

    int cx = DISPLAY_WIDTH / 2;
    int cy = DISPLAY_HEIGHT / 2 - 50;
    int w = 500, h = 700, t = 100;

    // 7-segment patterns: top, top-left, top-right, middle, bottom-left, bottom-right, bottom
    int segs[10][7] = {
        {1,1,1,0,1,1,1}, // 0
        {0,0,1,0,0,1,0}, // 1
        {1,0,1,1,1,0,1}, // 2
        {1,0,1,1,0,1,1}, // 3
        {0,1,1,1,0,1,0}, // 4
        {1,1,0,1,0,1,1}, // 5
        {1,1,0,1,1,1,1}, // 6
        {1,0,1,0,0,1,0}, // 7
        {1,1,1,1,1,1,1}, // 8
        {1,1,1,1,0,1,1}, // 9
    };

    int *s = segs[digit % 10];
    int x1 = cx - w/2, x2 = cx + w/2;
    int y1 = cy - h/2, y2 = cy, y3 = cy + h/2;

    // Draw filled rectangles for each segment (black = 0x00)
    for (int y = 0; y < DISPLAY_HEIGHT; y++) {
        for (int x = 0; x < DISPLAY_WIDTH; x++) {
            int px = y * DISPLAY_WIDTH + x;

            // Top segment
            if (s[0] && x >= x1 && x <= x2 && y >= y1 && y <= y1 + t)
                buf[px] = 0x00;
            // Top-left
            if (s[1] && x >= x1 && x <= x1 + t && y >= y1 && y <= y2)
                buf[px] = 0x00;
            // Top-right
            if (s[2] && x >= x2 - t && x <= x2 && y >= y1 && y <= y2)
                buf[px] = 0x00;
            // Middle
            if (s[3] && x >= x1 && x <= x2 && y >= y2 - t/2 && y <= y2 + t/2)
                buf[px] = 0x00;
            // Bottom-left
            if (s[4] && x >= x1 && x <= x1 + t && y >= y2 && y <= y3)
                buf[px] = 0x00;
            // Bottom-right
            if (s[5] && x >= x2 - t && x <= x2 && y >= y2 && y <= y3)
                buf[px] = 0x00;
            // Bottom
            if (s[6] && x >= x1 && x <= x2 && y >= y3 - t && y <= y3)
                buf[px] = 0x00;
        }
    }
}

// Capture photo using libcamera-still
static int capture_photo(const char *filename) {
    char cmd[512];
    snprintf(cmd, sizeof(cmd),
        "libcamera-still -o %s --width %d --height %d -t 1 --nopreview 2>/dev/null",
        filename, DISPLAY_WIDTH, DISPLAY_HEIGHT);
    return system(cmd);
}

// Load JPEG and convert to 8-bit grayscale raw
static uint8_t* load_jpeg_as_gray(const char *filename, int *width, int *height) {
    char cmd[512];
    char tmpfile[] = "/tmp/eink_gray.raw";

    // Use ImageMagick to convert
    snprintf(cmd, sizeof(cmd),
        "convert %s -resize %dx%d! -colorspace Gray -depth 8 gray:%s",
        filename, DISPLAY_WIDTH, DISPLAY_HEIGHT, tmpfile);

    if (system(cmd) != 0) {
        return NULL;
    }

    // Read raw file
    FILE *f = fopen(tmpfile, "rb");
    if (!f) return NULL;

    int size = DISPLAY_WIDTH * DISPLAY_HEIGHT;
    uint8_t *buf = malloc(size);
    if (!buf) {
        fclose(f);
        return NULL;
    }

    fread(buf, 1, size, f);
    fclose(f);

    *width = DISPLAY_WIDTH;
    *height = DISPLAY_HEIGHT;
    return buf;
}

// Do countdown and capture
static void do_capture(IT8951_USB *dev) {
    uint8_t *buf = malloc(DISPLAY_WIDTH * DISPLAY_HEIGHT);
    if (!buf) return;

    printf("Countdown...\n");

    // 3-2-1 countdown
    for (int i = 3; i >= 1; i--) {
        printf("%d...\n", i);
        draw_digit(buf, i);
        it8951_display(dev, buf, 0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, MODE_A2);
        if (i > 1) usleep(800000);  // 800ms between digits
    }

    printf("CAPTURE!\n");

    // Capture photo
    double t0 = get_time_ms();
    capture_photo("/tmp/capture.jpg");
    printf("Capture: %.0f ms\n", get_time_ms() - t0);

    // Load and display
    int w, h;
    uint8_t *photo = load_jpeg_as_gray("/tmp/capture.jpg", &w, &h);
    if (photo) {
        t0 = get_time_ms();
        it8951_display(dev, photo, 0, 0, w, h, MODE_GC16);
        printf("Display: %.0f ms\n", get_time_ms() - t0);
        free(photo);
    } else {
        printf("Failed to load photo\n");
    }

    free(buf);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("E-Ink Camera\n");
        printf("Usage: sudo %s /dev/sdX\n", argv[0]);
        printf("  Press '1' to capture with countdown\n");
        printf("  Press 'c' to clear display\n");
        printf("  Press 'q' to quit\n");
        return 1;
    }

    IT8951_USB *dev = it8951_usb_open(argv[1]);
    if (!dev) {
        printf("Failed to open %s\n", argv[1]);
        return 1;
    }

    printf("E-Ink Camera ready!\n");
    printf("Display: %dx%d\n", dev->width, dev->height);
    printf("Press '1' to capture, 'c' to clear, 'q' to quit\n\n");

    enable_raw_mode();

    char c;
    while (1) {
        if (read(STDIN_FILENO, &c, 1) == 1) {
            if (c == 'q' || c == 'Q') {
                printf("\nQuitting...\n");
                break;
            } else if (c == '1') {
                do_capture(dev);
                printf("\nReady for next capture (press '1')\n");
            } else if (c == 'c' || c == 'C') {
                printf("Clearing display...\n");
                it8951_clear(dev, MODE_INIT);
                printf("Done\n");
            }
        }
    }

    it8951_usb_close(dev);
    return 0;
}
