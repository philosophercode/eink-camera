"""Tests for the input manager."""

from dreamcam.input import (
    CLICK, DOUBLE_CLICK, HOLD, QUIT,
    HOLD_THRESHOLD, CLICK_TIMEOUT, DEBOUNCE_MIN,
    InputManager,
)


def test_constants():
    """Timing constants should be sane."""
    assert HOLD_THRESHOLD > CLICK_TIMEOUT
    assert CLICK_TIMEOUT > DEBOUNCE_MIN
    assert DEBOUNCE_MIN > 0


def test_input_manager_no_sources():
    """InputManager with no TTY and no GPIO should not crash."""
    mgr = InputManager(gpio_pin=None)
    # has_input should be based on what's available
    # In test environment, TTY may or may not be available
    mgr.close()


def test_check_click_timeout_no_clicks():
    """No pending clicks should return None."""
    mgr = InputManager(gpio_pin=None)
    import time
    result = mgr._check_click_timeout(time.time())
    assert result is None
    mgr.close()


def test_check_click_timeout_single():
    """Single click after timeout should return CLICK."""
    mgr = InputManager(gpio_pin=None)
    mgr._click_count = 1
    mgr._last_click_time = 0  # Long ago
    import time
    result = mgr._check_click_timeout(time.time())
    assert result == CLICK
    assert mgr._click_count == 0
    mgr.close()


def test_check_click_timeout_double():
    """Two clicks after timeout should return DOUBLE_CLICK."""
    mgr = InputManager(gpio_pin=None)
    mgr._click_count = 2
    mgr._last_click_time = 0  # Long ago
    import time
    result = mgr._check_click_timeout(time.time())
    assert result == DOUBLE_CLICK
    assert mgr._click_count == 0
    mgr.close()


def test_check_click_timeout_waiting():
    """Clicks within timeout window should return None."""
    mgr = InputManager(gpio_pin=None)
    mgr._click_count = 1
    import time
    mgr._last_click_time = time.time()  # Just now
    result = mgr._check_click_timeout(time.time())
    assert result is None
    assert mgr._click_count == 1  # Still pending
    mgr.close()
