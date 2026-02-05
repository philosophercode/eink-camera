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
#include <scsi/sg.h>
#include <sys/ioctl.h>

#define IT8951_USB_TIMEOUT 5000

// Send SCSI command to IT8951
static int scsi_cmd(int fd, uint8_t *cmd, int cmd_len, uint8_t *data, int data_len, int direction) {
    sg_io_hdr_t io_hdr;
    uint8_t sense[32];

    memset(&io_hdr, 0, sizeof(io_hdr));
    io_hdr.interface_id = 'S';
    io_hdr.cmd_len = cmd_len;
    io_hdr.mx_sb_len = sizeof(sense);
    io_hdr.dxfer_direction = direction;
    io_hdr.dxfer_len = data_len;
    io_hdr.dxferp = data;
    io_hdr.cmdp = cmd;
    io_hdr.sbp = sense;
    io_hdr.timeout = IT8951_USB_TIMEOUT;

    return ioctl(fd, SG_IO, &io_hdr);
}

IT8951_USB* it8951_usb_open(const char *device) {
    IT8951_USB *dev = malloc(sizeof(IT8951_USB));
    if (!dev) return NULL;

    dev->fd = open(device, O_RDWR);
    if (dev->fd < 0) {
        perror("Failed to open device");
        free(dev);
        return NULL;
    }

    // 7.8" display resolution
    dev->width = 1872;
    dev->height = 1404;

    return dev;
}

void it8951_usb_close(IT8951_USB *dev) {
    if (dev) {
        close(dev->fd);
        free(dev);
    }
}

int it8951_clear(IT8951_USB *dev, int mode) {
    uint8_t cmd[16] = {0xFE, 0x00, 0x00, 0x00, 0x00, 0x00,
                       0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                       0x00, 0x00, 0x00, 0x00};

    cmd[6] = 0;
    cmd[7] = 0;
    cmd[8] = 0;
    cmd[9] = 0;
    cmd[10] = (dev->width >> 8) & 0xFF;
    cmd[11] = dev->width & 0xFF;
    cmd[12] = (dev->height >> 8) & 0xFF;
    cmd[13] = dev->height & 0xFF;
    cmd[14] = mode;

    int size = dev->width * dev->height;
    uint8_t *buf = malloc(size);
    if (!buf) return -1;

    memset(buf, 0xFF, size);  // White

    int ret = scsi_cmd(dev->fd, cmd, 16, buf, size, SG_DXFER_TO_DEV);
    free(buf);
    return ret;
}

int it8951_display(IT8951_USB *dev, uint8_t *image, int x, int y, int w, int h, int mode) {
    uint8_t cmd[16] = {0xFE, 0x00, 0x00, 0x00, 0x00, 0x00,
                       0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                       0x00, 0x00, 0x00, 0x00};

    cmd[6] = (x >> 8) & 0xFF;
    cmd[7] = x & 0xFF;
    cmd[8] = (y >> 8) & 0xFF;
    cmd[9] = y & 0xFF;
    cmd[10] = (w >> 8) & 0xFF;
    cmd[11] = w & 0xFF;
    cmd[12] = (h >> 8) & 0xFF;
    cmd[13] = h & 0xFF;
    cmd[14] = mode;

    int size = w * h;
    return scsi_cmd(dev->fd, cmd, 16, image, size, SG_DXFER_TO_DEV);
}
