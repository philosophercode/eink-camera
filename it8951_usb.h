/**
 * IT8951 USB Driver - Self-contained header
 * Based on SCSI command protocol over USB mass storage
 */

#ifndef IT8951_USB_H
#define IT8951_USB_H

#include <stdint.h>

// Display modes
#define MODE_INIT 0   // Full clear
#define MODE_DU   1   // Direct update
#define MODE_GC16 2   // 16-level grayscale
#define MODE_A2   4   // Fast 2-level (B&W)

typedef struct {
    int fd;
    uint16_t width;
    uint16_t height;
} IT8951_USB;

// Initialize USB connection to IT8951
IT8951_USB* it8951_usb_open(const char *device);

// Close connection
void it8951_usb_close(IT8951_USB *dev);

// Clear display to white
int it8951_clear(IT8951_USB *dev, int mode);

// Display 8-bit grayscale image
int it8951_display(IT8951_USB *dev, uint8_t *image, int x, int y, int w, int h, int mode);

#endif
