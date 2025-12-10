from pynput.keyboard import Key, Controller, KeyCode
from typing import Set
import threading

SPECIAL = {
    'space': Key.space, 'shift': Key.shift, 'ctrl': Key.ctrl,
    'alt': Key.alt, 'tab': Key.tab, 'escape': Key.esc, 'esc': Key.esc,
    'enter': Key.enter, 'backspace': Key.backspace,
    'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
    'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
}

class KeyboardController:
    def __init__(self, max_keys: int = 4):
        self.ctrl = Controller()
        self.pressed: Set[str] = set()
        self.lock = threading.Lock()
        self.enabled = True
        self.max_keys = max_keys

    def _key(self, name: str):
        n = name.lower().strip()
        if n in SPECIAL:
            return SPECIAL[n]
        return KeyCode.from_char(name[0].lower()) if name else None

    def set_max(self, m: int):
        self.max_keys = max(1, min(10, m))

    def press(self, name: str) -> bool:
        if not self.enabled or not name:
            return False
        with self.lock:
            if name in self.pressed:
                return True
            if len(self.pressed) >= self.max_keys:
                return False
            try:
                self.ctrl.press(self._key(name))
                self.pressed.add(name)
                return True
            except Exception:
                return False

    def release(self, name: str):
        if not name:
            return
        with self.lock:
            if name in self.pressed:
                try:
                    self.ctrl.release(self._key(name))
                except Exception:
                    pass
                self.pressed.discard(name)

    def release_all(self):
        with self.lock:
            for n in list(self.pressed):
                try:
                    self.ctrl.release(self._key(n))
                except Exception:
                    pass
            self.pressed.clear()

    def set_enabled(self, e: bool):
        self.enabled = e
        if not e:
            self.release_all()

    def count(self) -> int:
        return len(self.pressed)

    def get_pressed(self) -> Set[str]:
        with self.lock:
            return self.pressed.copy()
