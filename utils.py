import math
import time
from collections import deque
from typing import Tuple, Dict, List

def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def angle_between_points(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.degrees(math.atan2(p2[1]-p1[1], p2[0]-p1[0]))

class Smoother:
    def __init__(self, size: int = 5):
        self.vals = deque(maxlen=size)
    def add(self, v: float) -> float:
        self.vals.append(v)
        return sum(self.vals) / len(self.vals)
    def reset(self):
        self.vals.clear()

class StabilityFilter:
    def __init__(self, delay: float = 0.18):
        self.delay = delay
        self.pending: Dict[str, Tuple[bool, float]] = {}
        self.confirmed: Dict[str, bool] = {}

    def update(self, key: str, active: bool) -> bool:
        now = time.time()
        if key not in self.confirmed:
            self.confirmed[key] = False
        cur = self.confirmed[key]
        if active != cur:
            if key not in self.pending or self.pending[key][0] != active:
                self.pending[key] = (active, now)
            elif now - self.pending[key][1] >= self.delay:
                self.confirmed[key] = active
                del self.pending[key]
                return active
        else:
            self.pending.pop(key, None)
        return cur

    def set_delay(self, d: float):
        self.delay = max(0.05, min(0.5, d))

    def reset(self):
        self.pending.clear()
        self.confirmed.clear()

class Trail:
    def __init__(self, maxlen: int = 20):
        self.points: Dict[str, deque] = {}
        self.maxlen = maxlen
    def add(self, tid: str, pt: Tuple[int, int]):
        if tid not in self.points:
            self.points[tid] = deque(maxlen=self.maxlen)
        self.points[tid].append(pt)
    def get(self, tid: str) -> List[Tuple[int, int]]:
        return list(self.points.get(tid, []))
    def clear(self):
        self.points.clear()

KEY_NAMES = {'space':'SPACE','shift':'SHIFT','ctrl':'CTRL','alt':'ALT','up':'UP','down':'DOWN','left':'LEFT','right':'RIGHT'}
def key_display(k: str) -> str:
    return KEY_NAMES.get(k.lower(), k.upper())
  
