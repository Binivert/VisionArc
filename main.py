#!/usr/bin/env python3
import sys

def check_deps():
    missing = []
    for m in ['cv2', 'mediapipe', 'numpy', 'pynput', 'PIL']:
        try: __import__(m)
        except ImportError: missing.append({'cv2': 'opencv-python', 'PIL': 'Pillow'}.get(m, m))
    if missing:
        print(f"Missing: pip install {' '.join(missing)}")
        return False
    return True

def main():
    print()
    print("  ╔════════════════════════════════════════════════╗")
    print("  ║    🎮 GESTURE GAMING CONTROL v3.0 🎮           ║")
    print("  ║                                                 ║")
    print("  ╚════════════════════════════════════════════════╝")
    print()
    if not check_deps(): sys.exit(1)
    print("  Starting...\n")
    try:
        from gui import App
        App().run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
