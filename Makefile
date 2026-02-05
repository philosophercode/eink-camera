# E-Ink Camera - Standalone Makefile
# Build: make
# Run: sudo ./camera /dev/sda

CC = gcc
CFLAGS = -Wall -O2
LDFLAGS =

TARGET = camera
SRCS = camera.c it8951_usb.c
OBJS = $(SRCS:.c=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
