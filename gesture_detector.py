import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field
from utils import distance, Smoother, StabilityFilter, Trail


@dataclass
class Hand:
    landmarks: list
    side: str
    wrist: Tuple[float, float]
    thumb_tip: Tuple[float, float]
    index_tip: Tuple[float, float]
    middle_tip: Tuple[float, float]
    ring_tip: Tuple[float, float]
    pinky_tip: Tuple[float, float]
    index_mcp: Tuple[float, float]
    middle_mcp: Tuple[float, float]
    ring_mcp: Tuple[float, float]
    pinky_mcp: Tuple[float, float]
    thumb_mcp: Tuple[float, float]
    palm: Tuple[float, float]


@dataclass
class GestureState:
    steer_left: bool = False
    steer_right: bool = False
    # This is the actual steering value (degrees-like), centered at 0.
    steering_angle: float = 0.0
    hands_close: bool = False
    hands_far: bool = False
    hands_distance: float = 0.0
    left_forward: bool = False
    left_backward: bool = False
    right_forward: bool = False
    right_backward: bool = False
    left_detected: bool = False
    right_detected: bool = False
    active: List[str] = field(default_factory=list)


class GestureDetector:
    def __init__(self, thresholds: Dict, sensitivity: Dict):
        self.thresholds = thresholds
        self.sensitivity = sensitivity

        self.mp_hands = mp.solutions.hands
        self.hands = None
        self._init()

        # Smoothers and filters
        self.steer_smooth = Smoother(12)
        self.dist_smooth = Smoother(5)
        self.stability = StabilityFilter(thresholds.get('stability_delay', 0.18))
        self.trail = Trail()

        self.left: Optional[Hand] = None
        self.right: Optional[Hand] = None
        self.state = GestureState()

        # Visual steering state in [-1, 1] (for the ball position)
        self.visual_steer_pos: float = 0.0

    def _init(self):
        if self.hands:
            self.hands.close()
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.35,
            model_complexity=1,
        )

    def reset(self):
        self._init()
        self.steer_smooth.reset()
        self.dist_smooth.reset()
        self.stability.reset()
        self.trail.clear()
        self.visual_steer_pos = 0.0

    def update_thresholds(self, t: Dict):
        self.thresholds = t
        self.stability.set_delay(t.get('stability_delay', 0.18))

    def update_sensitivity(self, s: Dict):
        self.sensitivity = s

    def _extract(self, lm, side: str) -> Hand:
        pts = [(l.x, l.y) for l in lm.landmark]
        palm = (
            sum(pts[i][0] for i in [0, 5, 9, 13, 17]) / 5,
            sum(pts[i][1] for i in [0, 5, 9, 13, 17]) / 5,
        )
        return Hand(
            landmarks=pts,
            side=side,
            wrist=pts[0],
            thumb_tip=pts[4],
            index_tip=pts[8],
            middle_tip=pts[12],
            ring_tip=pts[16],
            pinky_tip=pts[20],
            index_mcp=pts[5],
            middle_mcp=pts[9],
            ring_mcp=pts[13],
            pinky_mcp=pts[17],
            thumb_mcp=pts[2],
            palm=palm,
        )

    def _is_finger_extended(
        self,
        tip: Tuple[float, float],
        mcp: Tuple[float, float],
        wrist: Tuple[float, float],
        thresh: float,
    ) -> bool:
        tip_to_wrist = distance(tip, wrist)
        mcp_to_wrist = distance(mcp, wrist)
        return tip_to_wrist > mcp_to_wrist + thresh

    def _is_thumb_extended(self, hand: Hand, thresh: float) -> bool:
        thumb_to_pinky_mcp = distance(hand.thumb_tip, hand.pinky_mcp)
        wrist_to_pinky_mcp = distance(hand.wrist, hand.pinky_mcp)
        return thumb_to_pinky_mcp > wrist_to_pinky_mcp * 0.8

    def _detect_finger_gesture(self, hand: Hand) -> Tuple[bool, bool]:
        thresh = self.thresholds.get('finger_extend_thresh', 0.06)
        sens = self.sensitivity.get('fingers', 1.0)
        thresh = thresh / sens

        index_ext = self._is_finger_extended(hand.index_tip, hand.index_mcp, hand.wrist, thresh)
        middle_ext = self._is_finger_extended(hand.middle_tip, hand.middle_mcp, hand.wrist, thresh)
        ring_ext = self._is_finger_extended(hand.ring_tip, hand.ring_mcp, hand.wrist, thresh)
        pinky_ext = self._is_finger_extended(hand.pinky_tip, hand.pinky_mcp, hand.wrist, thresh)
        thumb_ext = self._is_thumb_extended(hand, thresh)

        forward = index_ext and middle_ext and not ring_ext and not pinky_ext
        backward = thumb_ext and not index_ext and not middle_ext and not ring_ext and not pinky_ext
        return forward, backward

    # --------------------------------------------------------------
    # Steering computation: use vertical wrist difference
    # --------------------------------------------------------------
    def _calculate_steering_angle(
        self, left_wrist: Tuple[float, float], right_wrist: Tuple[float, float]
    ) -> float:
        """Return a pseudo-angle proportional to vertical wrist difference.

        We use only dy between wrists to get a stable, smooth steering value.

        - dy < 0: right wrist higher than left -> positive steering (right)
        - dy > 0: left wrist higher than right -> negative steering (left)

        When both wrists are at the same vertical height (straight line),
        dy = 0 => angle_deg = 0 => center of the bar.
        """
        dy = right_wrist[1] - left_wrist[1]  # image coords: y grows downward

        # Scale dy into something like degrees. Tune with
        # thresholds['steering_dy_scale'] if needed.
        scale = self.thresholds.get('steering_dy_scale', 180.0)
        angle_deg = -dy * scale
        return angle_deg

    def process(self, frame: np.ndarray, use_stability: bool = True) -> Tuple[GestureState, np.ndarray]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        try:
            results = self.hands.process(rgb)
        except Exception:
            self.reset()
            results = self.hands.process(rgb)

        self.left = None
        self.right = None
        s = GestureState()

        # Hand detection
        if results and results.multi_hand_landmarks and results.multi_handedness:
            for lm, info in zip(results.multi_hand_landmarks, results.multi_handedness):
                label = info.classification[0].label
                hand = self._extract(lm, label)
                if label == "Left":
                    # MediaPipe's "Left" is usually the right side on screen
                    self.right = hand
                    s.right_detected = True
                else:
                    self.left = hand
                    s.left_detected = True

        active: List[str] = []

        def check(key, val):
            return self.stability.update(key, val) if use_stability else val

        # Finger gestures (forward/backward)
        if self.left:
            fwd, bwd = self._detect_finger_gesture(self.left)
            s.left_forward = check('l_fwd', fwd)
            s.left_backward = check('l_bwd', bwd)
            if s.left_forward:
                active.append("L-FORWARD")
            if s.left_backward:
                active.append("L-BACKWARD")

        if self.right:
            fwd, bwd = self._detect_finger_gesture(self.right)
            s.right_forward = check('r_fwd', fwd)
            s.right_backward = check('r_bwd', bwd)
            if s.right_forward:
                active.append("R-FORWARD")
            if s.right_backward:
                active.append("R-BACKWARD")

        # Two-hand gestures: distance + steering
        if self.left and self.right:
            # Distance (close / far)
            raw_dist = distance(self.left.palm, self.right.palm)
            dist = self.dist_smooth.add(raw_dist)
            s.hands_distance = dist

            sens_dist = self.sensitivity.get('distance', 1.0)
            close_t = self.thresholds.get('hands_close_dist', 0.12) / sens_dist
            far_t = self.thresholds.get('hands_far_dist', 0.55) * sens_dist

            s.hands_close = check('close', dist < close_t)
            s.hands_far = check('far', dist > far_t)
            if s.hands_close:
                active.append("CLOSE")
            if s.hands_far:
                active.append("FAR")

            # Steering: dy-based pseudo-angle, then smoothing, centered at 0
            raw_angle = self._calculate_steering_angle(self.left.wrist, self.right.wrist)
            smooth_angle = self.steer_smooth.add(raw_angle)

            # This is the value you see as `val:`. When hands are straight,
            # smooth_angle ~ 0, so ball is at center.
            s.steering_angle = smooth_angle

            # Centered value used for thresholds and ball position
            ang = smooth_angle  # 0 degrees IS the center; no extra offset

            # Turn on/off left/right steering using this centered angle
            sens_steer = self.sensitivity.get('steering', 1.0)
            steer_t = self.thresholds.get('steering_angle', 35.0) / sens_steer

            s.steer_left = check('steer_l', ang < -steer_t)
            s.steer_right = check('steer_r', ang > steer_t)

            if s.steer_left:
                active.append("STEER-L")
            if s.steer_right:
                active.append("STEER-R")

            # Update visual ball position smoothly in [-1, 1]
            max_display_angle = self.thresholds.get('visual_max_angle', 60.0)
            target_norm = max(-1.0, min(1.0, ang / max_display_angle))
            alpha = 0.25  # visual smoothing factor
            self.visual_steer_pos += (target_norm - self.visual_steer_pos) * alpha

        s.active = active
        self.state = s
        return s, frame

    def draw(self, frame: np.ndarray, skeleton: bool = True, trails: bool = True) -> np.ndarray:
        h, w = frame.shape[:2]
        steer_thresh = self.thresholds.get('steering_angle', 35.0)

        def draw_hand(hand: Hand, color, highlight):
            if not skeleton:
                return
            conns = [
                (0, 1), (1, 2), (2, 3), (3, 4),
                (0, 5), (5, 6), (6, 7), (7, 8),
                (0, 9), (9, 10), (10, 11), (11, 12),
                (0, 13), (13, 14), (14, 15), (15, 16),
                (0, 17), (17, 18), (18, 19), (19, 20),
                (5, 9), (9, 13), (13, 17),
            ]
            for a, b in conns:
                p1 = (int(hand.landmarks[a][0] * w), int(hand.landmarks[a][1] * h))
                p2 = (int(hand.landmarks[b][0] * w), int(hand.landmarks[b][1] * h))
                cv2.line(frame, p1, p2, color, 2, cv2.LINE_AA)

            for i, pt in enumerate(hand.landmarks):
                px, py = int(pt[0] * w), int(pt[1] * h)
                r = 5 if i in [4, 8, 12] else 3
                col = highlight if i in [4, 8, 12] else color
                cv2.circle(frame, (px, py), r, col, -1, cv2.LINE_AA)

            if trails:
                px, py = int(hand.palm[0] * w), int(hand.palm[1] * h)
                self.trail.add(hand.side, (px, py))

        # Draw hands
        if self.left:
            draw_hand(self.left, (0, 200, 150), (0, 255, 220))
        if self.right:
            draw_hand(self.right, (200, 120, 0), (255, 160, 40))

        # Draw trails
        if trails:
            for tid, col in [("Right", (0, 200, 150)), ("Left", (200, 120, 0))]:
                pts = self.trail.get(tid)
                for i in range(1, len(pts)):
                    a = i / len(pts)
                    cv2.line(
                        frame,
                        pts[i - 1],
                        pts[i],
                        tuple(int(c * a) for c in col),
                        max(1, int(3 * a)),
                        cv2.LINE_AA,
                    )

        # Draw steering bar
        if self.left and self.right:
            # Line between wrists
            lx, ly = int(self.left.wrist[0] * w), int(self.left.wrist[1] * h)
            rx, ry = int(self.right.wrist[0] * w), int(self.right.wrist[1] * h)
            cv2.line(frame, (lx, ly), (rx, ry), (0, 200, 255), 3, cv2.LINE_AA)

            bar_y = h - 50
            bar_left = 80
            bar_right = w - 80
            bar_width = bar_right - bar_left
            bar_center = (bar_left + bar_right) // 2

            # Background bar
            cv2.rectangle(
                frame,
                (bar_left, bar_y - 20),
                (bar_right, bar_y + 20),
                (50, 50, 50),
                -1,
            )
            cv2.rectangle(
                frame,
                (bar_left, bar_y - 20),
                (bar_right, bar_y + 20),
                (80, 80, 100),
                2,
            )

            # Map threshold angle to x positions
            max_display_angle = self.thresholds.get('visual_max_angle', 60.0)
            thresh_ratio = min(steer_thresh / max_display_angle, 0.95)
            left_thresh_x = int(bar_center - thresh_ratio * (bar_width / 2))
            right_thresh_x = int(bar_center + thresh_ratio * (bar_width / 2))

            # Left/Right/Neutral zones
            cv2.rectangle(
                frame,
                (bar_left, bar_y - 18),
                (left_thresh_x, bar_y + 18),
                (0, 100, 50),
                -1,
            )
            cv2.rectangle(
                frame,
                (right_thresh_x, bar_y - 18),
                (bar_right, bar_y + 18),
                (50, 50, 120),
                -1,
            )
            cv2.rectangle(
                frame,
                (left_thresh_x, bar_y - 18),
                (right_thresh_x, bar_y + 18),
                (80, 80, 80),
                -1,
            )

            # Threshold lines + center line
            cv2.line(
                frame,
                (left_thresh_x, bar_y - 20),
                (left_thresh_x, bar_y + 20),
                (0, 255, 100),
                3,
            )
            cv2.line(
                frame,
                (right_thresh_x, bar_y - 20),
                (right_thresh_x, bar_y + 20),
                (100, 100, 255),
                3,
            )
            cv2.line(
                frame,
                (bar_center, bar_y - 15),
                (bar_center, bar_y + 15),
                (200, 200, 200),
                1,
            )

            # Ball position from visual_steer_pos in [-1, 1]
            angle_norm = max(-1.0, min(1.0, self.visual_steer_pos))
            indicator_x = int(bar_center + angle_norm * (bar_width / 2))
            indicator_x = max(bar_left + 12, min(bar_right - 12, indicator_x))

            # Color and label depending on steering state
            if self.state.steer_left:
                ind_color = (0, 255, 100)
                cv2.putText(
                    frame,
                    "<< LEFT",
                    (bar_left, bar_y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    ind_color,
                    2,
                )
            elif self.state.steer_right:
                ind_color = (100, 100, 255)
                cv2.putText(
                    frame,
                    "RIGHT >>",
                    (bar_right - 140, bar_y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    ind_color,
                    2,
                )
            else:
                ind_color = (200, 200, 200)

            # Draw ball
            cv2.circle(frame, (indicator_x, bar_y), 14, ind_color, -1)
            cv2.circle(frame, (indicator_x, bar_y), 14, (255, 255, 255), 2)

            # Debug text: steering value (should be ~0 at straight hands)
            ang = self.state.steering_angle
            cv2.putText(
                frame,
                f"val: {ang:5.1f}",
                (bar_center - 40, bar_y + 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1,
            )
            cv2.putText(
                frame,
                "STEER",
                (bar_left - 5, bar_y - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (150, 150, 150),
                1,
            )

        return frame

    def release(self):
        if self.hands:
            self.hands.close()
            self.hands = None
