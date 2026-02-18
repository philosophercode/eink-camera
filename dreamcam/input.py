"""
Input manager for keyboard and GPIO button.

Encapsulates the button state machine (debounce, hold detection,
click counting) and keyboard handling into a clean event interface.

Usage:
    from dreamcam.input import InputManager, CLICK, DOUBLE_CLICK, HOLD

    mgr = InputManager(gpio_pin=17)
    while True:
        event = mgr.poll()
        if event == CLICK:
            do_something()
"""

from __future__ import annotations

import select
import sys
import time

# Events
CLICK = 'click'
DOUBLE_CLICK = 'double_click'
HOLD = 'hold'
QUIT = 'quit'
KEY_STYLE = 'key_style'      # 's' key
KEY_CLEAR = 'key_clear'      # 'c' key
KEY_RESET = 'key_reset'      # 'r' key
KEY_MODE = 'key_mode'        # 'm' key

# Timing
HOLD_THRESHOLD = 1.5    # Seconds to register a hold
CLICK_TIMEOUT = 0.4     # Seconds to wait for second click
DEBOUNCE_MIN = 0.05     # Minimum press duration (seconds)
POLL_INTERVAL = 0.05    # Seconds between polls when idle


class InputManager:
    """Unified keyboard + GPIO input with event-based polling."""

    def __init__(self, gpio_pin: int | None = None):
        self._has_tty = False
        self._old_settings = None
        self._gpio_chip = None
        self._gpio_pin = gpio_pin

        # Button state machine
        self._last_btn = 1
        self._btn_time = 0.0
        self._click_count = 0
        self._last_click_time = 0.0
        self._hold_fired = False

        self._setup_keyboard()
        self._setup_gpio()

    def _setup_keyboard(self):
        """Set terminal to raw mode if TTY available."""
        try:
            import termios
            import tty
            if sys.stdin.isatty():
                self._has_tty = True
                self._old_settings = termios.tcgetattr(sys.stdin)
                tty.setraw(sys.stdin.fileno())
        except (ImportError, AttributeError):
            pass

    def _setup_gpio(self):
        """Open GPIO chip and claim button pin."""
        if self._gpio_pin is None:
            return
        try:
            import lgpio
            try:
                self._gpio_chip = lgpio.gpiochip_open(4)   # Pi 5
            except Exception:
                self._gpio_chip = lgpio.gpiochip_open(0)   # Older Pi
            lgpio.gpio_claim_input(self._gpio_chip, self._gpio_pin,
                                   lgpio.SET_PULL_UP)
            print(f"  Button on GPIO{self._gpio_pin} ready!")
        except Exception as e:
            print(f"  GPIO setup failed: {e}")
            self._gpio_chip = None

    @property
    def has_input(self) -> bool:
        """True if at least one input source is available."""
        return self._has_tty or self._gpio_chip is not None

    def poll(self) -> str | None:
        """
        Check for input and return an event, or None.

        Call this in a loop. It handles its own timing — no need
        for the caller to sleep.

        Returns one of: CLICK, DOUBLE_CLICK, HOLD, QUIT,
                        KEY_STYLE, KEY_CLEAR, KEY_RESET, KEY_MODE, or None.
        """
        now = time.time()

        # Keyboard
        event = self._poll_keyboard()
        if event:
            return event

        # GPIO button
        event = self._poll_gpio(now)
        if event:
            return event

        # Click timeout — process pending clicks from GPIO
        event = self._check_click_timeout(now)
        if event:
            return event

        # Avoid busy loop
        if not self.has_input:
            time.sleep(POLL_INTERVAL)

        return None

    def _poll_keyboard(self) -> str | None:
        """Non-blocking keyboard read. Returns event or None."""
        if not self._has_tty:
            return None
        if not select.select([sys.stdin], [], [], POLL_INTERVAL)[0]:
            return None

        key = sys.stdin.read(1)
        if key == 'q':
            return QUIT
        elif key in ('1', ' '):
            return CLICK
        elif key == 'g':
            return DOUBLE_CLICK
        elif key == 'm':
            return KEY_MODE
        elif key == 's':
            return KEY_STYLE
        elif key == 'c':
            return KEY_CLEAR
        elif key == 'r':
            return KEY_RESET
        return None

    def _poll_gpio(self, now: float) -> str | None:
        """Read GPIO button state. Returns HOLD event or None."""
        if self._gpio_chip is None:
            return None

        import lgpio
        state = lgpio.gpio_read(self._gpio_chip, self._gpio_pin)

        # Falling edge — button pressed
        if self._last_btn == 1 and state == 0:
            self._btn_time = now
            self._hold_fired = False

        # Still held — check for hold
        elif self._last_btn == 0 and state == 0:
            if not self._hold_fired and now - self._btn_time >= HOLD_THRESHOLD:
                self._hold_fired = True
                self._click_count = 0
                self._last_btn = state
                return HOLD

        # Rising edge — button released
        elif self._last_btn == 0 and state == 1:
            hold = now - self._btn_time
            if hold >= DEBOUNCE_MIN and not self._hold_fired:
                self._click_count += 1
                self._last_click_time = now

        self._last_btn = state
        return None

    def _check_click_timeout(self, now: float) -> str | None:
        """After click timeout, emit click or double-click."""
        if self._click_count == 0:
            return None
        if now - self._last_click_time <= CLICK_TIMEOUT:
            return None

        count = self._click_count
        self._click_count = 0

        if count == 1:
            return CLICK
        else:
            return DOUBLE_CLICK

    def close(self):
        """Restore terminal and release GPIO."""
        if self._old_settings is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None
        if self._gpio_chip is not None:
            import lgpio
            lgpio.gpiochip_close(self._gpio_chip)
            self._gpio_chip = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
