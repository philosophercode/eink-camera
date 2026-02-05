/**
 * IT8951 USB Driver - Self-contained implementation
 * Based on SCSI command protocol over USB mass storage
 */

#include "it8951_usb.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <scsi/scsi.h>
#include <scsi/sg.h>
#include <sys/ioctl.h>
#include <byteswap.h>

#define IT8951_USB_TIMEOUT 10000
#define MAX_TRANSFER 60800

// Area struct for load_image_area command
typedef struct {
    int address;
    int x;
    int y;
    int w;
    int h;
} IT8951_area;

// Display area struct for display_area command
typedef struct {
    int address;
    int wavemode;
    int x;
    int y;
    int w;
    int h;
    int wait_ready;
} IT8951_display_area;

// Device info response struct
typedef struct {
    unsigned int uiStandardCmdNo;
    unsigned int uiExtendedCmdNo;
    unsigned int uiSignature;
    unsigned int uiVersion;
    unsigned int width;
    unsigned int height;
    unsigned int update_buffer_addr;
    unsigned int image_buffer_addr;
    unsigned int temperature_segment;
    unsigned int ui_mode;
    unsigned int frame_count[8];
    unsigned int buffer_count;
    unsigned int reserved[9];
    void *command_table;
} IT8951_deviceinfo;

// Load image data to display buffer
static int load_image_area(IT8951_USB *dev, int x, int y, int w, int h, uint8_t *data) {
    unsigned char cmd[16] = {
        0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xa2, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00
    };

    IT8951_area area;
    memset(&area, 0, sizeof(IT8951_area));
    area.address = dev->img_addr;
    area.x = __bswap_32(x);
    area.y = __bswap_32(y);
    area.w = __bswap_32(w);
    area.h = __bswap_32(h);

    int length = w * h;
    uint8_t *buffer = malloc(length + sizeof(IT8951_area));
    if (!buffer) return -1;

    memcpy(buffer, &area, sizeof(IT8951_area));
    memcpy(buffer + sizeof(IT8951_area), data, length);

    sg_io_hdr_t io_hdr;
    memset(&io_hdr, 0, sizeof(sg_io_hdr_t));
    io_hdr.interface_id = 'S';
    io_hdr.cmd_len = 16;
    io_hdr.dxfer_direction = SG_DXFER_TO_DEV;
    io_hdr.dxfer_len = length + sizeof(IT8951_area);
    io_hdr.dxferp = buffer;
    io_hdr.cmdp = cmd;
    io_hdr.timeout = IT8951_USB_TIMEOUT;

    int ret = ioctl(dev->fd, SG_IO, &io_hdr);
    free(buffer);
    return ret;
}

// Trigger display refresh
static int display_area(IT8951_USB *dev, int x, int y, int w, int h, int mode) {
    unsigned char cmd[16] = {
        0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x94, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00
    };

    IT8951_display_area area;
    memset(&area, 0, sizeof(IT8951_display_area));
    area.address = dev->img_addr;
    area.wavemode = __bswap_32(mode);
    area.x = __bswap_32(x);
    area.y = __bswap_32(y);
    area.w = __bswap_32(w);
    area.h = __bswap_32(h);
    area.wait_ready = __bswap_32(1);

    uint8_t *buffer = malloc(sizeof(IT8951_display_area));
    if (!buffer) return -1;
    memcpy(buffer, &area, sizeof(IT8951_display_area));

    sg_io_hdr_t io_hdr;
    memset(&io_hdr, 0, sizeof(sg_io_hdr_t));
    io_hdr.interface_id = 'S';
    io_hdr.cmd_len = 16;
    io_hdr.dxfer_direction = SG_DXFER_TO_DEV;
    io_hdr.dxfer_len = sizeof(IT8951_display_area);
    io_hdr.dxferp = buffer;
    io_hdr.cmdp = cmd;
    io_hdr.timeout = IT8951_USB_TIMEOUT;

    int ret = ioctl(dev->fd, SG_IO, &io_hdr);
    free(buffer);
    return ret;
}

IT8951_USB* it8951_usb_open(const char *device) {
    IT8951_USB *dev = malloc(sizeof(IT8951_USB));
    if (!dev) return NULL;

    dev->fd = open(device, O_RDWR | O_NONBLOCK);
    if (dev->fd < 0) {
        perror("Failed to open device");
        free(dev);
        return NULL;
    }

    // Verify it's a SCSI device
    int bus;
    if (ioctl(dev->fd, SCSI_IOCTL_GET_BUS_NUMBER, &bus) < 0) {
        fprintf(stderr, "%s is not a SCSI device\n", device);
        close(dev->fd);
        free(dev);
        return NULL;
    }

    // Get device info
    unsigned char deviceinfo_cmd[12] = {
        0xfe, 0x00,
        0x38, 0x39, 0x35, 0x31,  // "8951" signature
        0x80, 0x00,              // Get System Info
        0x01, 0x00, 0x02, 0x00   // Version
    };
    unsigned char deviceinfo_result[112];

    sg_io_hdr_t io_hdr;
    memset(&io_hdr, 0, sizeof(sg_io_hdr_t));
    io_hdr.interface_id = 'S';
    io_hdr.cmd_len = 12;
    io_hdr.dxfer_direction = SG_DXFER_FROM_DEV;
    io_hdr.dxfer_len = 112;
    io_hdr.dxferp = deviceinfo_result;
    io_hdr.cmdp = deviceinfo_cmd;
    io_hdr.timeout = IT8951_USB_TIMEOUT;

    if (ioctl(dev->fd, SG_IO, &io_hdr) < 0) {
        perror("Failed to get device info");
        close(dev->fd);
        free(dev);
        return NULL;
    }

    IT8951_deviceinfo *info = (IT8951_deviceinfo *)deviceinfo_result;
    dev->width = __bswap_32(info->width);
    dev->height = __bswap_32(info->height);
    dev->img_addr = info->image_buffer_addr;

    printf("IT8951 USB: %dx%d, buffer addr=0x%08x\n", dev->width, dev->height, dev->img_addr);

    return dev;
}

void it8951_usb_close(IT8951_USB *dev) {
    if (dev) {
        close(dev->fd);
        free(dev);
    }
}

int it8951_clear(IT8951_USB *dev, int mode) {
    int size = dev->width * dev->height;
    uint8_t *buf = malloc(size);
    if (!buf) return -1;

    memset(buf, 0xFF, size);  // White

    // Send in chunks
    int w = dev->width;
    int h = dev->height;
    int lines = MAX_TRANSFER / w;
    int offset = 0;

    while (offset < size) {
        int chunk_lines = lines;
        if ((offset / w) + chunk_lines > h) {
            chunk_lines = h - (offset / w);
        }
        load_image_area(dev, 0, offset / w, w, chunk_lines, buf + offset);
        offset += chunk_lines * w;
    }

    int ret = display_area(dev, 0, 0, w, h, mode);
    free(buf);
    return ret;
}

int it8951_display(IT8951_USB *dev, uint8_t *image, int x, int y, int w, int h, int mode) {
    // Send image in chunks (MAX_TRANSFER limit)
    int lines = MAX_TRANSFER / w;
    int offset = 0;
    int size = w * h;

    while (offset < size) {
        int chunk_lines = lines;
        if ((offset / w) + chunk_lines > h) {
            chunk_lines = h - (offset / w);
        }
        load_image_area(dev, x, y + (offset / w), w, chunk_lines, image + offset);
        offset += chunk_lines * w;
    }

    return display_area(dev, x, y, w, h, mode);
}
