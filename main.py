import platform
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

from audio_system import SoundManager
from game_engine import GameEngine
import renderer


MODEL_PATH = "hand_landmarker.task"
CAM_W, CAM_H = 1280, 720


def _resolve_model_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    return p if p.is_absolute() else Path(__file__).resolve().parent / p


def _open_webcam(width: int, height: int):
    """Try default + DirectShow (Windows); indices 0 and 1. Returns cap or None."""
    indices = (0, 1)
    backends = [None]
    if platform.system() == "Windows" and hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)

    for backend in backends:
        for idx in indices:
            cap = (
                cv2.VideoCapture(idx, backend)
                if backend is not None
                else cv2.VideoCapture(idx)
            )
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            ok_any = False
            for _ in range(8):
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    ok_any = True
                    break
            if ok_any:
                return cap
            cap.release()
    return None


def _load_tracker_async(model_path: str, out: dict):
    try:
        from hand_tracker import HandTracker

        out["tracker"] = HandTracker(model_path)
    except Exception as e:
        out["error"] = e


def main():
    model_path = _resolve_model_path(MODEL_PATH)
    if not model_path.is_file():
        print(
            f"Missing hand model: {model_path}\n"
            "Place hand_landmarker.task next to main.py (MediaPipe hand landmarker).",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    cap = None
    try:
        cap = _open_webcam(CAM_W, CAM_H)
        if cap is None:
            print(
                "Could not open a camera (tried indices 0–1, default + DirectShow on Windows).\n"
                "Check the device, USB, privacy settings, and that no other app is using it.",
                file=sys.stderr,
                flush=True,
            )
            sys.exit(1)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cv2.namedWindow("Hand Game", cv2.WINDOW_AUTOSIZE)

        load_state = {"tracker": None, "error": None}
        threading.Thread(
            target=_load_tracker_async,
            args=(str(model_path), load_state),
            daemon=True,
        ).start()

        tick = 0
        while load_state["tracker"] is None and load_state["error"] is None:
            ok, frame = cap.read()
            if not ok:
                frame = np.zeros((max(height, 480), max(width, 640), 3), dtype=np.uint8)
            else:
                frame = cv2.flip(frame, 1)
            screen = renderer.draw_frame(
                frame,
                {
                    "mode": "loading",
                    "tick": tick,
                    "balls": [],
                    "hand_positions": [],
                    "particles": [],
                    "popups": [],
                    "shake_frames": 0,
                    "combo_flash_frames": 0,
                    "score": 0,
                    "best_score": 0,
                    "lives": 0,
                    "max_lives": 0,
                    "combo": 0,
                    "goals": [],
                    "run_number": 1,
                    "level": 1,
                    "coins": 0,
                    "hint_alpha": 1.0,
                },
            )
            cv2.imshow("Hand Game", screen)
            cv2.waitKey(16)
            tick += 1

        if load_state["error"] is not None:
            raise load_state["error"]

        tracker = load_state["tracker"]
        game = GameEngine(width, height)
        sound = SoundManager()

        STEADY_HAND_FRAMES = 20
        game_active = False
        steady_hands_frames = 0
        ui_tick = 0
        read_fail_streak = 0

        while True:
            success, frame = cap.read()
            if not success:
                read_fail_streak += 1
                if read_fail_streak in (1, 60, 180, 300):
                    print(
                        "Camera read failed — check cable, permissions, other apps using the camera.",
                        file=sys.stderr,
                        flush=True,
                    )
                continue
            read_fail_streak = 0

            frame = cv2.flip(frame, 1)
            hands = tracker.detect(frame)

            if not game_active:
                if len(hands) >= 2:
                    steady_hands_frames += 1
                    if steady_hands_frames >= STEADY_HAND_FRAMES:
                        game_active = True
                        game.start_countdown(72)
                else:
                    steady_hands_frames = 0
                frame = renderer.draw_frame(
                    frame,
                    {
                        "mode": "pregame",
                        "balls": game.balls,
                        "spawn_pending": game.spawn_pending,
                        "hand_positions": [
                            (h["x"], h["y"], h["confidence"], h["radius"])
                            for h in hands
                        ],
                        "particles": (
                            game.confetti_particles + game.pop_particles + game.near_miss_sparks
                        ),
                        "popups": game.floating_texts,
                        "shake_frames": game.shake_frames,
                        "combo_flash_frames": game.combo_flash_frames,
                        "combo_pulse_frames": game.combo_pulse_frames,
                        "combo_last_pop_frame": game.combo_last_pop_frame,
                        "frame_count": game.frame_count,
                        "life_loss_overlay_frames": game.life_loss_overlay_frames,
                        "score": game.score,
                        "best_score": game.best_score,
                        "lives": game.lives_left,
                        "max_lives": game.lives_max,
                        "combo": game.combo,
                        "goals": [
                            {
                                "name": m["label"],
                                "current": m["progress"],
                                "target": m["target"],
                            }
                            for m in game.missions
                        ],
                        "run_number": game.play_level,
                        "level": game.level,
                        "coins": game.coins,
                        "hint_alpha": game.hint_bar_opacity,
                        "pregame_steady": steady_hands_frames,
                        "pregame_steady_need": STEADY_HAND_FRAMES,
                        "ui_tick": ui_tick,
                    },
                )
            else:
                game.update(hands)
                while game.pending_audio_events:
                    sound.play(game.pending_audio_events.pop(0))
                frame = renderer.draw_frame(
                    frame,
                    {
                        "mode": "play",
                        "balls": game.balls,
                        "spawn_pending": game.spawn_pending,
                        "hand_positions": [
                            (h["x"], h["y"], h["confidence"], h["radius"])
                            for h in hands
                        ],
                        "particles": (
                            game.confetti_particles + game.pop_particles + game.near_miss_sparks
                        ),
                        "popups": game.floating_texts,
                        "shake_frames": game.shake_frames,
                        "combo_flash_frames": game.combo_flash_frames,
                        "combo_pulse_frames": game.combo_pulse_frames,
                        "combo_last_pop_frame": game.combo_last_pop_frame,
                        "frame_count": game.frame_count,
                        "life_loss_overlay_frames": game.life_loss_overlay_frames,
                        "score": game.score,
                        "best_score": game.best_score,
                        "lives": game.lives_left,
                        "max_lives": game.lives_max,
                        "combo": game.combo,
                        "goals": [
                            {
                                "name": m["label"],
                                "current": m["progress"],
                                "target": m["target"],
                            }
                            for m in game.missions
                        ],
                        "run_number": game.play_level,
                        "level": game.level,
                        "coins": game.coins,
                        "hint_alpha": game.hint_bar_opacity,
                        "ui_tick": ui_tick,
                    },
                )
                # Step 1 extraction: shake rendering will be implemented inside renderer.
                if game.shake_frames > 0:
                    game.shake_frames -= 1

            cv2.imshow("Hand Game", frame)
            ui_tick += 1

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            if key in (ord("n"), ord("N")) and not game.game_over:
                game.force_next_level()
            if key in (ord("m"), ord("M")) and not game.game_over:
                game.reroll_missions()
            if key in (ord("r"), ord("R")) and game.game_over:
                game.reset()
                game_active = False
                steady_hands_frames = 0

    except KeyboardInterrupt:
        print("\nExiting.", flush=True)
    finally:
        if cap is not None:
            cap.release()
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass


if __name__ == "__main__":
    main()
