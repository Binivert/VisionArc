import time
from pynput.keyboard import Controller, Key
from typing import Set, Dict, Optional


class KeyboardController:
    """Keyboard controller with PWM-style pulsing for progressive steering."""
    
    # Special key mapping
    SPECIAL_KEYS = {
        'space': Key.space,
        'shift': Key.shift,
        'ctrl': Key.ctrl,
        'alt': Key.alt,
        'tab': Key.tab,
        'enter': Key.enter,
        'esc': Key.esc,
        'up': Key.up,
        'down': Key.down,
        'left': Key.left,
        'right': Key.right,
        'backspace': Key.backspace,
        'delete': Key.delete,
        'home': Key.home,
        'end': Key.end,
        'pageup': Key.page_up,
        'pagedown': Key.page_down,
    }

    def __init__(self, max_keys: int = 4):
        self.controller = Controller()
        self.max_keys = max_keys
        self._pressed: Set[str] = set()
        self._enabled = True
        
        # PWM state for steering keys
        self._pwm_state: Dict[str, dict] = {}  # key -> {force, last_toggle, is_on}
        self._base_cycle_ms = 500  # Base PWM cycle time in ms
        self._steering_strength = 1.0  # Multiplier for steering responsiveness

    def set_enabled(self, enabled: bool):
        if not enabled:
            self.release_all()
        self._enabled = enabled

    def set_max(self, n: int):
        self.max_keys = n

    def set_steering_strength(self, strength: float):
        """Set steering strength multiplier (0.5 to 2.0)."""
        self._steering_strength = max(0.5, min(2.0, strength))

    def _get_key(self, key_str: str):
        """Convert string to pynput key."""
        key_str = key_str.lower().strip()
        if key_str in self.SPECIAL_KEYS:
            return self.SPECIAL_KEYS[key_str]
        if len(key_str) == 1:
            return key_str
        return None

    def _calculate_pwm_timing(self, force: float) -> tuple:
        """Calculate on/off times based on force level.
        
        Returns (on_time_ms, off_time_ms)
        
        At low force: short on, long off (gentle taps)
        At high force: long on, short off (strong steering)
        At 100% force: always on
        """
        # Clamp force to valid range
        force = max(0.0, min(1.0, force))
        
        # Apply steering strength multiplier
        effective_force = min(1.0, force * self._steering_strength)
        
        # Base cycle time (adjustable)
        cycle_ms = self._base_cycle_ms
        
        # Calculate duty cycle (percentage of time key is pressed)
        # Minimum 10% duty cycle at lowest force, 100% at max force
        min_duty = 0.10
        duty_cycle = min_duty + (1.0 - min_duty) * effective_force
        
        on_time = int(cycle_ms * duty_cycle)
        off_time = int(cycle_ms * (1.0 - duty_cycle))
        
        # Minimum times to prevent flickering
        on_time = max(30, on_time)
        off_time = max(0, off_time)
        
        return on_time, off_time

    def press_pwm(self, key: str, force: float) -> bool:
        """Press a key with PWM-style pulsing based on force.
        
        This should be called every frame. It manages the on/off timing internally.
        
        Args:
            key: The key to press
            force: Force level 0.0 to 1.0
            
        Returns:
            True if key is currently in 'on' state
        """
        if not self._enabled or not key:
            return False
        
        pkey = self._get_key(key)
        if pkey is None:
            return False
        
        current_time = time.time() * 1000  # Convert to ms
        
        # Initialize PWM state if needed
        if key not in self._pwm_state:
            self._pwm_state[key] = {
                'force': force,
                'last_toggle': current_time,
                'is_on': False
            }
        
        state = self._pwm_state[key]
        state['force'] = force
        
        # At 100% force (or very close), just hold the key
        if force >= 0.95:
            if key not in self._pressed:
                if len(self._pressed) >= self.max_keys:
                    return False
                try:
                    self.controller.press(pkey)
                    self._pressed.add(key)
                except Exception:
                    return False
            state['is_on'] = True
            return True
        
        # Calculate timing
        on_time, off_time = self._calculate_pwm_timing(force)
        
        # Check if we need to toggle
        time_since_toggle = current_time - state['last_toggle']
        
        if state['is_on']:
            # Currently on, check if we should turn off
            if time_since_toggle >= on_time:
                # Turn off
                if key in self._pressed:
                    try:
                        self.controller.release(pkey)
                        self._pressed.discard(key)
                    except Exception:
                        pass
                state['is_on'] = False
                state['last_toggle'] = current_time
        else:
            # Currently off, check if we should turn on
            if time_since_toggle >= off_time:
                # Turn on
                if len(self._pressed) < self.max_keys:
                    try:
                        self.controller.press(pkey)
                        self._pressed.add(key)
                        state['is_on'] = True
                    except Exception:
                        pass
                state['last_toggle'] = current_time
        
        return state['is_on']

    def press(self, key: str) -> bool:
        """Press a key (non-PWM, for regular gestures)."""
        if not self._enabled or not key:
            return False
        if len(self._pressed) >= self.max_keys:
            return False
        pkey = self._get_key(key)
        if pkey is None:
            return False
        if key in self._pressed:
            return True
        try:
            self.controller.press(pkey)
            self._pressed.add(key)
            return True
        except Exception:
            return False

    def release(self, key: str):
        """Release a key."""
        if not key:
            return
        pkey = self._get_key(key)
        if pkey is None:
            return
        if key in self._pressed:
            try:
                self.controller.release(pkey)
            except Exception:
                pass
            self._pressed.discard(key)
        # Clear PWM state
        if key in self._pwm_state:
            del self._pwm_state[key]

    def release_all(self):
        """Release all pressed keys."""
        for key in list(self._pressed):
            pkey = self._get_key(key)
            if pkey:
                try:
                    self.controller.release(pkey)
                except Exception:
                    pass
        self._pressed.clear()
        self._pwm_state.clear()

    def count(self) -> int:
        return len(self._pressed)

    def get_pressed(self) -> Set[str]:
        return self._pressed.copy()

    def get_pwm_state(self, key: str) -> Optional[dict]:
        """Get PWM state for a key (for debugging/display)."""
        return self._pwm_state.get(key)
