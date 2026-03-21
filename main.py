import threading

import cv2
import numpy as np

from game_engine import GameEngine
import renderer


MODEL_PATH = "hand_landmarker.task"


def _load_tracker_async(model_path, out):
    try:
        from hand_tracker import HandTracker

        out["tracker"] = HandTracker(model_path)
    except Exception as e:
        out["error"] = e


def main():

    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cv2.namedWindow("Hand Game", cv2.WINDOW_AUTOSIZE)
    for _ in range(3):
        cap.read()

    load_state = {"tracker": None, "error": None}
    threading.Thread(
        target=_load_tracker_async,
        args=(MODEL_PATH, load_state),
        daemon=True,
    ).start()

    tick = 0
    while load_state["tracker"] is None and load_state["error"] is None:
        ok, frame = cap.read()
        if not ok:
            frame = np.zeros((max(height, 480), max(width, 640), 3), dtype=np.uint8)
        else:
            frame = cv2.flip(frame, 1)
        screen = renderer.draw_loading_screen(frame, tick)
        cv2.imshow("Hand Game", screen)
        cv2.waitKey(16)
        tick += 1

    if load_state["error"] is not None:
        raise load_state["error"]

    tracker = load_state["tracker"]

    game = GameEngine(width, height)

    STEADY_HAND_FRAMES = 20
    game_active = False
    steady_hands_frames = 0
    ui_tick = 0

    while True:
        success, frame = cap.read()
        if not success:
            continue

        frame = cv2.flip(frame, 1)

        hands = tracker.detect(frame)

        if not game_active:
            if len(hands) >= 2:
                steady_hands_frames += 1
                if steady_hands_frames >= STEADY_HAND_FRAMES:
                    game_active = True
            else:
                steady_hands_frames = 0
            renderer.render(
                frame,
                game,
                hands,
                game_active=False,
                pregame_steady=steady_hands_frames,
                pregame_steady_need=STEADY_HAND_FRAMES,
                ui_tick=ui_tick,
            )
        else:
            game.update(hands)
            renderer.render(frame, game, hands, game_active=True)

        cv2.imshow("Hand Game", frame)
        ui_tick += 1

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        if key in (ord("r"), ord("R")) and game.game_over:
            game.reset()
            game_active = False
            steady_hands_frames = 0


    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()