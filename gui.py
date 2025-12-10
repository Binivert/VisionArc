import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import time
from typing import Optional, Set
from config import Config, PROFILES
from gesture_detector import GestureDetector, GestureState
from keyboard_controller import KeyboardController
from utils import key_display

COLORS = {
    'bg_dark': '#05080f',
    'bg_medium': '#0a1020',
    'bg_card': '#101828',
    'bg_card_light': '#182030',
    'accent': '#00e5ff',
    'accent2': '#b388ff',
    'text': '#e8eaed',
    'text_dim': '#6b7280',
    'success': '#00e676',
    'warning': '#ffab00',
    'border': '#1e3a5f',
}

class NeonButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=160, height=48, primary=True, color=None):
        super().__init__(parent, width=width, height=height, bg=COLORS['bg_medium'], highlightthickness=0, cursor='hand2')
        self.command = command
        self.text = text
        self.w, self.h = width, height
        self.primary = primary
        self.color = color or COLORS['accent']
        self.hover = False
        self._draw()
        self.bind('<Enter>', lambda e: self._set_hover(True))
        self.bind('<Leave>', lambda e: self._set_hover(False))
        self.bind('<Button-1>', lambda e: self._click())
    def _set_hover(self, state):
        self.hover = state
        self._draw()
    def _click(self):
        if self.command: self.command()
    def _draw(self):
        self.delete('all')
        r = 10
        if self.primary:
            fill = self.color if self.hover else COLORS['bg_card']
            text_col = COLORS['bg_dark'] if self.hover else self.color
            outline = self.color
        else:
            fill = COLORS['bg_card_light'] if self.hover else COLORS['bg_card']
            outline = self.color if self.hover else COLORS['border']
            text_col = self.color if self.hover else COLORS['text']
        self._rounded_rect(2, 2, self.w-2, self.h-2, r, fill=fill, outline=outline, width=2)
        self.create_text(self.w//2, self.h//2, text=self.text, fill=text_col, font=('Segoe UI', 11, 'bold'))
    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2, x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(points, smooth=True, **kwargs)

class NeonSlider(tk.Canvas):
    def __init__(self, parent, variable, from_=0, to=100, width=280, height=40):
        super().__init__(parent, width=width, height=height, bg=COLORS['bg_card'], highlightthickness=0, cursor='hand2')
        self.var = variable
        self.from_, self.to = from_, to
        self.w, self.h = width, height
        self.dragging = False
        self.bind('<Button-1>', self._click)
        self.bind('<B1-Motion>', self._drag)
        self.bind('<ButtonRelease-1>', lambda e: setattr(self, 'dragging', False))
        self.var.trace_add('write', lambda *a: self._draw())
        self._draw()
    def _val_to_x(self, val):
        return 15 + (val - self.from_) / (self.to - self.from_) * (self.w - 50)
    def _x_to_val(self, x):
        ratio = max(0, min(1, (x - 15) / (self.w - 50)))
        return self.from_ + ratio * (self.to - self.from_)
    def _click(self, e):
        self.var.set(self._x_to_val(e.x))
        self.dragging = True
    def _drag(self, e):
        if self.dragging: self.var.set(self._x_to_val(e.x))
    def _draw(self):
        self.delete('all')
        y = self.h // 2
        self.create_line(15, y, self.w-35, y, fill=COLORS['border'], width=6, capstyle='round')
        x = self._val_to_x(self.var.get())
        self.create_line(15, y, x, y, fill=COLORS['accent'], width=6, capstyle='round')
        self.create_oval(x-9, y-9, x+9, y+9, fill=COLORS['accent'], outline=COLORS['text'], width=2)
        val = self.var.get()
        txt = f"{val:.2f}" if val < 10 else f"{int(val)}"
        self.create_text(self.w-15, y, text=txt, fill=COLORS['text'], font=('Consolas', 10, 'bold'), anchor='e')

class NeonToggle(tk.Canvas):
    def __init__(self, parent, variable, width=50, height=26):
        super().__init__(parent, width=width, height=height, bg=COLORS['bg_card'], highlightthickness=0, cursor='hand2')
        self.var = variable
        self.w, self.h = width, height
        self.bind('<Button-1>', self._toggle)
        self.var.trace_add('write', lambda *a: self._draw())
        self._draw()
    def _toggle(self, e=None):
        self.var.set(not self.var.get())
    def _draw(self):
        self.delete('all')
        on = self.var.get()
        r = self.h // 2 - 2
        bg = COLORS['accent'] if on else COLORS['border']
        points = [r+2,2, self.w-r-2,2, self.w-2,2, self.w-2,r+2, self.w-2,self.h-r-2, self.w-2,self.h-2, self.w-r-2,self.h-2, r+2,self.h-2, 2,self.h-2, 2,self.h-r-2, 2,r+2, 2,2]
        self.create_polygon(points, smooth=True, fill=bg, outline='')
        cx = self.w - r - 4 if on else r + 4
        self.create_oval(cx-r+2, 4, cx+r-2, self.h-4, fill=COLORS['text'], outline='')

class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=COLORS['bg_medium']):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all("<MouseWheel>", self._scroll))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all("<MouseWheel>"))
    def _scroll(self, e):
        self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")

class App:
    def __init__(self):
        self.cfg = Config.load()
        self.root = tk.Tk()
        self.root.title("GESTURE GAMING CONTROL")
        self.root.configure(bg=COLORS['bg_dark'])
        self.root.state('zoomed')
        self.root.minsize(1400, 800)
        self.detector: Optional[GestureDetector] = None
        self.keyboard = KeyboardController(self.cfg.max_keys)
        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.state = GestureState()
        self.active_keys: Set[str] = set()
        self.last_time = 0
        self.fps = 0
        self._build_ui()
        self._load_config()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=COLORS['bg_card'], background=COLORS['bg_card'], foreground=COLORS['text'], arrowcolor=COLORS['accent'])
        main = tk.Frame(self.root, bg=COLORS['bg_dark'])
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        left = tk.Frame(main, bg=COLORS['bg_medium'], width=340)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left.pack_propagate(False)
        self._build_left(left)
        center = tk.Frame(main, bg=COLORS['bg_dark'])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        self._build_center(center)
        right = tk.Frame(main, bg=COLORS['bg_medium'], width=400)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)
        self._build_right(right)

    def _build_left(self, parent):
        scroll = ScrollFrame(parent, bg=COLORS['bg_medium'])
        scroll.pack(fill=tk.BOTH, expand=True)
        c = scroll.inner
        tk.Label(c, text="🎮 CONTROLS", bg=COLORS['bg_medium'], fg=COLORS['accent'], font=('Segoe UI', 24, 'bold')).pack(anchor=tk.W, padx=20, pady=(25, 5))
        tk.Label(c, text="Gesture Gaming System v3.0", bg=COLORS['bg_medium'], fg=COLORS['text_dim'], font=('Segoe UI', 10)).pack(anchor=tk.W, padx=20, pady=(0, 20))
        btn_frame = tk.Frame(c, bg=COLORS['bg_medium'])
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        self.start_btn = NeonButton(btn_frame, "▶ START", self._start, width=145, height=52)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = NeonButton(btn_frame, "⏹ STOP", self._stop, width=145, height=52, primary=False)
        self.stop_btn.pack(side=tk.LEFT)
        card = self._card(c, "CAMERA")
        row = tk.Frame(card, bg=COLORS['bg_card'])
        row.pack(fill=tk.X, padx=15, pady=12)
        tk.Label(row, text="Select Camera:", bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 11)).pack(side=tk.LEFT)
        self.cam_var = tk.StringVar(value="0")
        ttk.Combobox(row, textvariable=self.cam_var, values=["0","1","2"], width=5, state="readonly").pack(side=tk.RIGHT)
        card = self._card(c, "OPTIONS")
        self.opt_vars = {}
        for name, default in [("Show Skeleton", True), ("Show Trails", True), ("Mirror Mode", True), ("Stability Filter", True), ("Enable Keyboard", True)]:
            row = tk.Frame(card, bg=COLORS['bg_card'])
            row.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(row, text=name, bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 11)).pack(side=tk.LEFT)
            var = tk.BooleanVar(value=default)
            NeonToggle(row, var).pack(side=tk.RIGHT)
            self.opt_vars[name] = var
        self.opt_vars["Enable Keyboard"].trace_add('write', lambda *a: self.keyboard.set_enabled(self.opt_vars["Enable Keyboard"].get()))
        row = tk.Frame(card, bg=COLORS['bg_card'])
        row.pack(fill=tk.X, padx=15, pady=(10, 15))
        tk.Label(row, text="Max Keys:", bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 11)).pack(side=tk.LEFT)
        self.maxk_var = tk.StringVar(value=str(self.cfg.max_keys))
        maxk = ttk.Combobox(row, textvariable=self.maxk_var, values=["1","2","3","4","5"], width=4, state="readonly")
        maxk.pack(side=tk.RIGHT)
        maxk.bind('<<ComboboxSelected>>', lambda e: self._maxk_change())
        card = self._card(c, "STATUS")
        self.fps_lbl = tk.Label(card, text="FPS: --", bg=COLORS['bg_card'], fg=COLORS['success'], font=('Consolas', 20, 'bold'))
        self.fps_lbl.pack(anchor=tk.W, padx=15, pady=8)
        self.hands_lbl = tk.Label(card, text="Hands: None", bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 12))
        self.hands_lbl.pack(anchor=tk.W, padx=15, pady=3)
        self.keys_lbl = tk.Label(card, text="Active: 0/4", bg=COLORS['bg_card'], fg=COLORS['accent'], font=('Segoe UI', 12))
        self.keys_lbl.pack(anchor=tk.W, padx=15, pady=(3, 15))
        card = self._card(c, "PROFILES")
        for name in PROFILES:
            NeonButton(card, f"⚡ {name.upper()}", lambda n=name: self._apply_profile(n), width=280, height=44, primary=False, color=COLORS['accent2']).pack(pady=6, padx=15)
        tk.Frame(c, height=30, bg=COLORS['bg_medium']).pack()

    def _build_center(self, parent):
        tk.Label(parent, text="📹 CAMERA FEED", bg=COLORS['bg_dark'], fg=COLORS['accent'], font=('Segoe UI', 20, 'bold')).pack(anchor=tk.W, pady=(0, 12))
        cam_border = tk.Frame(parent, bg=COLORS['accent'])
        cam_border.pack()
        cam_inner = tk.Frame(cam_border, bg=COLORS['bg_dark'], width=640, height=480)
        cam_inner.pack(padx=3, pady=3)
        cam_inner.pack_propagate(False)
        self.cam_lbl = tk.Label(cam_inner, text="\n\n📷 Camera Not Started\n\nClick START", bg=COLORS['bg_dark'], fg=COLORS['text_dim'], font=('Segoe UI', 16))
        self.cam_lbl.pack(fill=tk.BOTH, expand=True)
        gest = tk.Frame(parent, bg=COLORS['bg_card'])
        gest.pack(fill=tk.X, pady=15)
        tk.Label(gest, text="⚡ ACTIVE GESTURES", bg=COLORS['bg_card'], fg=COLORS['accent'], font=('Segoe UI', 14, 'bold')).pack(anchor=tk.W, padx=20, pady=(15, 8))
        self.gest_lbl = tk.Label(gest, text="None", bg=COLORS['bg_card'], fg=COLORS['success'], font=('Consolas', 15, 'bold'), wraplength=600)
        self.gest_lbl.pack(anchor=tk.W, padx=25, pady=(0, 8))
        self.pressed_lbl = tk.Label(gest, text="Keys: None", bg=COLORS['bg_card'], fg=COLORS['warning'], font=('Consolas', 12))
        self.pressed_lbl.pack(anchor=tk.W, padx=25, pady=(0, 15))
        info = tk.Frame(parent, bg=COLORS['bg_card'])
        info.pack(fill=tk.X, pady=5)
        tk.Label(info, text="💡 GESTURES: Forward=Point 2 fingers | Backward=Thumbs up | Steer=Tilt hands", bg=COLORS['bg_card'], fg=COLORS['text_dim'], font=('Segoe UI', 10)).pack(padx=15, pady=10)

    def _build_right(self, parent):
        tk.Label(parent, text="⚙️ SETTINGS", bg=COLORS['bg_medium'], fg=COLORS['accent'], font=('Segoe UI', 24, 'bold')).pack(pady=(25, 5), padx=20, anchor=tk.W)
        scroll = ScrollFrame(parent, bg=COLORS['bg_medium'])
        scroll.pack(fill=tk.BOTH, expand=True)
        c = scroll.inner
        card = self._card(c, "GESTURE BINDINGS")
        self.key_entries = {}
        self.gesture_enabled = {}
        bindings = [("steer_left", "Steer Left"), ("steer_right", "Steer Right"), ("hands_close", "Hands Close"), ("hands_far", "Hands Far"), ("left_forward", "L Forward"), ("left_backward", "L Backward"), ("right_forward", "R Forward"), ("right_backward", "R Backward")]
        for key, label in bindings:
            row = tk.Frame(card, bg=COLORS['bg_card'])
            row.pack(fill=tk.X, padx=12, pady=4)
            var = tk.BooleanVar(value=self.cfg.enabled_gestures.get(key, True))
            NeonToggle(row, var, width=44, height=22).pack(side=tk.LEFT, padx=(0, 8))
            self.gesture_enabled[key] = var
            tk.Label(row, text=label, bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 10), width=11, anchor='w').pack(side=tk.LEFT)
            entry = tk.Entry(row, width=8, bg=COLORS['bg_medium'], fg=COLORS['accent'], font=('Consolas', 11), relief=tk.FLAT, insertbackground=COLORS['accent'])
            entry.pack(side=tk.RIGHT, padx=5)
            self.key_entries[key] = entry
        card = self._card(c, "THRESHOLDS")
        self.thresh_vars = {}
        thresholds = [("steering_angle", "Steering Angle", 15, 50), ("finger_extend_thresh", "Finger Extend", 0.02, 0.12), ("hands_close_dist", "Hands Close", 0.05, 0.25), ("hands_far_dist", "Hands Far", 0.40, 0.70), ("stability_delay", "Stability (s)", 0.08, 0.30)]
        for key, label, mn, mx in thresholds:
            row = tk.Frame(card, bg=COLORS['bg_card'])
            row.pack(fill=tk.X, padx=12, pady=6)
            tk.Label(row, text=label, bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 10)).pack(anchor=tk.W)
            var = tk.DoubleVar(value=self.cfg.thresholds.get(key, (mn+mx)/2))
            NeonSlider(row, var, from_=mn, to=mx, width=320, height=36).pack(anchor=tk.W, pady=(4, 0))
            self.thresh_vars[key] = var
        card = self._card(c, "SENSITIVITY")
        self.sens_vars = {}
        for key in ["steering", "fingers", "distance"]:
            row = tk.Frame(card, bg=COLORS['bg_card'])
            row.pack(fill=tk.X, padx=12, pady=6)
            tk.Label(row, text=key.title(), bg=COLORS['bg_card'], fg=COLORS['text'], font=('Segoe UI', 10)).pack(anchor=tk.W)
            var = tk.DoubleVar(value=self.cfg.sensitivity.get(key, 1.0))
            NeonSlider(row, var, from_=0.5, to=2.0, width=320, height=36).pack(anchor=tk.W, pady=(4, 0))
            self.sens_vars[key] = var
        btn_frame = tk.Frame(c, bg=COLORS['bg_medium'])
        btn_frame.pack(fill=tk.X, pady=20, padx=12)
        NeonButton(btn_frame, "💾 SAVE", self._save, width=160, height=48).pack(side=tk.LEFT, padx=(0, 10))
        NeonButton(btn_frame, "↺ RESET", self._reset, width=160, height=48, primary=False).pack(side=tk.LEFT)
        tk.Frame(c, height=30, bg=COLORS['bg_medium']).pack()

    def _card(self, parent, title):
        card = tk.Frame(parent, bg=COLORS['bg_card'])
        card.pack(fill=tk.X, padx=10, pady=8)
        header = tk.Frame(card, bg=COLORS['bg_card'])
        header.pack(fill=tk.X, padx=12, pady=(12, 8))
        tk.Frame(header, bg=COLORS['accent'], width=4, height=20).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(header, text=title, bg=COLORS['bg_card'], fg=COLORS['accent'], font=('Segoe UI', 13, 'bold')).pack(side=tk.LEFT)
        return card

    def _load_config(self):
        for k, e in self.key_entries.items():
            e.delete(0, tk.END)
            e.insert(0, self.cfg.keybindings.get(k, ''))
        for k, v in self.gesture_enabled.items():
            v.set(self.cfg.enabled_gestures.get(k, True))
        for k, v in self.thresh_vars.items():
            v.set(self.cfg.thresholds.get(k, 0.5))
        for k, v in self.sens_vars.items():
            v.set(self.cfg.sensitivity.get(k, 1.0))
        self.opt_vars["Show Skeleton"].set(self.cfg.show_skeleton)
        self.opt_vars["Show Trails"].set(self.cfg.show_trails)
        self.opt_vars["Mirror Mode"].set(self.cfg.mirror_mode)
        self.opt_vars["Stability Filter"].set(self.cfg.stability_mode)
        self.cam_var.set(str(self.cfg.camera_index))
        self.maxk_var.set(str(self.cfg.max_keys))

    def _maxk_change(self):
        try:
            v = int(self.maxk_var.get())
            self.keyboard.set_max(v)
            self.cfg.max_keys = v
        except: pass

    def _apply_profile(self, name):
        self.cfg.apply_profile(name)
        self._load_config()
        if self.detector:
            self.detector.update_thresholds(self.cfg.thresholds)
            self.detector.update_sensitivity(self.cfg.sensitivity)
        self.keyboard.set_max(self.cfg.max_keys)
        messagebox.showinfo("Profile", f"{name.upper()} profile loaded!")

    def _save(self):
        for k, e in self.key_entries.items():
            self.cfg.keybindings[k] = e.get().strip()
        for k, v in self.gesture_enabled.items():
            self.cfg.enabled_gestures[k] = v.get()
        for k, v in self.thresh_vars.items():
            self.cfg.thresholds[k] = v.get()
        for k, v in self.sens_vars.items():
            self.cfg.sensitivity[k] = v.get()
        if self.detector:
            self.detector.update_thresholds(self.cfg.thresholds)
            self.detector.update_sensitivity(self.cfg.sensitivity)
        self.cfg.save()
        messagebox.showinfo("Saved", "Settings saved!")

    def _reset(self):
        self.cfg.reset()
        self._load_config()
        if self.detector:
            self.detector.update_thresholds(self.cfg.thresholds)
            self.detector.update_sensitivity(self.cfg.sensitivity)

    def _start(self):
        if self.running: return
        idx = int(self.cam_var.get())
        self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened(): self.cap = cv2.VideoCapture(idx)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"Cannot open camera {idx}")
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        for _ in range(5): self.cap.read()
        self.detector = GestureDetector(self.cfg.thresholds, self.cfg.sensitivity)
        self.running = True
        self.last_time = time.time()
        self._loop()

    def _stop(self):
        self.running = False
        if self.cap: self.cap.release(); self.cap = None
        if self.detector: self.detector.release(); self.detector = None
        self.keyboard.release_all()
        self.active_keys.clear()
        self.cam_lbl.config(image='', text="\n\n📷 Camera Stopped\n\nClick START")
        self.fps_lbl.config(text="FPS: --")
        self.hands_lbl.config(text="Hands: None")
        self.gest_lbl.config(text="None")
        self.pressed_lbl.config(text="Keys: None")

    def _loop(self):
        if not self.running or not self.cap: return
        ret, frame = self.cap.read()
        if not ret:
            self.root.after(10, self._loop)
            return
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        self.fps = 1.0 / dt if dt > 0 else 0
        if self.opt_vars["Mirror Mode"].get(): frame = cv2.flip(frame, 1)
        if self.detector:
            try:
                self.state, frame = self.detector.process(frame, self.opt_vars["Stability Filter"].get())
                frame = self.detector.draw(frame, self.opt_vars["Show Skeleton"].get(), self.opt_vars["Show Trails"].get())
                self._handle_gestures()
            except Exception as e:
                print(f"Error: {e}")
                if self.detector: self.detector.reset()
        cv2.putText(frame, f"FPS: {int(self.fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 230, 255), 2)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.cam_lbl.imgtk = img
        self.cam_lbl.config(image=img, text="")
        self.fps_lbl.config(text=f"FPS: {int(self.fps)}")
        hands = []
        if self.state.left_detected: hands.append("Left")
        if self.state.right_detected: hands.append("Right")
        self.hands_lbl.config(text=f"Hands: {', '.join(hands) if hands else 'None'}")
        self.keys_lbl.config(text=f"Active: {self.keyboard.count()}/{self.keyboard.max_keys}")
        self.gest_lbl.config(text="  |  ".join(self.state.active) if self.state.active else "None")
        pressed = self.keyboard.get_pressed()
        self.pressed_lbl.config(text=f"Keys: {' + '.join(key_display(k) for k in pressed) if pressed else 'None'}")
        self.root.after(1, self._loop)

    def _handle_gestures(self):
        s = self.state
        mapping = {
            'steer_left': s.steer_left, 'steer_right': s.steer_right,
            'hands_close': s.hands_close, 'hands_far': s.hands_far,
            'left_forward': s.left_forward, 'left_backward': s.left_backward,
            'right_forward': s.right_forward, 'right_backward': s.right_backward,
        }
        new_active = set()
        for gesture, active in mapping.items():
            if not self.gesture_enabled.get(gesture, tk.BooleanVar(value=True)).get(): continue
            key = self.cfg.keybindings.get(gesture, '')
            if not key: continue
            if active:
                if self.keyboard.press(key): new_active.add(key)
            elif key in self.active_keys:
                self.keyboard.release(key)
        for key in self.active_keys - new_active:
            self.keyboard.release(key)
        self.active_keys = new_active

    def _close(self):
        self._stop()
        self.cfg.show_skeleton = self.opt_vars["Show Skeleton"].get()
        self.cfg.show_trails = self.opt_vars["Show Trails"].get()
        self.cfg.mirror_mode = self.opt_vars["Mirror Mode"].get()
        self.cfg.stability_mode = self.opt_vars["Stability Filter"].get()
        self.cfg.camera_index = int(self.cam_var.get())
        self.cfg.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
