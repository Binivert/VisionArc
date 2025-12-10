import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict

CONFIG_DIR = os.path.expanduser("~/.gesture_gaming")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_KEYBINDINGS = {
    "steer_left": "a",
    "steer_right": "d",
    "hands_close": "space",
    "hands_far": "shift",
    "left_forward": "up",
    "left_backward": "down",
    "right_forward": "w",
    "right_backward": "s",
}

DEFAULT_ENABLED = {
    "steer_left": True,
    "steer_right": True,
    "hands_close": True,
    "hands_far": False,
    "left_forward": False,
    "left_backward": False,
    "right_forward": True,
    "right_backward": True,
}

DEFAULT_THRESHOLDS = {
    "steering_angle": 35.0,
    "hands_close_dist": 0.12,
    "hands_far_dist": 0.55,
    "finger_extend_thresh": 0.06,
    "stability_delay": 0.18,
}

DEFAULT_SENSITIVITY = {
    "steering": 1.0,
    "fingers": 1.0,
    "distance": 1.0,
}

PROFILES = {
    "racing": {
        "max_keys": 4,
        "stability_delay": 0.15,
        "steering_angle": 30.0,
    },
    "action": {
        "max_keys": 3,
        "stability_delay": 0.18,
        "steering_angle": 35.0,
    },
    "casual": {
        "max_keys": 2,
        "stability_delay": 0.22,
        "steering_angle": 40.0,
    },
}

@dataclass
class Config:
    keybindings: Dict[str, str] = field(default_factory=lambda: DEFAULT_KEYBINDINGS.copy())
    enabled_gestures: Dict[str, bool] = field(default_factory=lambda: DEFAULT_ENABLED.copy())
    thresholds: Dict[str, float] = field(default_factory=lambda: DEFAULT_THRESHOLDS.copy())
    sensitivity: Dict[str, float] = field(default_factory=lambda: DEFAULT_SENSITIVITY.copy())
    camera_index: int = 0
    max_keys: int = 4
    stability_mode: bool = True
    show_skeleton: bool = True
    show_trails: bool = True
    mirror_mode: bool = True

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> 'Config':
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                c = cls()
                for k, v in data.items():
                    if hasattr(c, k):
                        if isinstance(getattr(c, k), dict) and isinstance(v, dict):
                            getattr(c, k).update(v)
                        else:
                            setattr(c, k, v)
                return c
            except Exception:
                pass
        return cls()

    def apply_profile(self, name: str):
        if name in PROFILES:
            p = PROFILES[name]
            self.max_keys = p.get("max_keys", self.max_keys)
            for key in ["stability_delay", "steering_angle"]:
                if key in p:
                    self.thresholds[key] = p[key]

    def reset(self):
        self.keybindings = DEFAULT_KEYBINDINGS.copy()
        self.enabled_gestures = DEFAULT_ENABLED.copy()
        self.thresholds = DEFAULT_THRESHOLDS.copy()
        self.sensitivity = DEFAULT_SENSITIVITY.copy()
