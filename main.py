import cv2

from hand_tracker import HandTracker
from game_engine import GameEngine
import renderer


MODEL_PATH = "hand_landmarker.task"


def main():

    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    tracker = HandTracker(MODEL_PATH)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    game = GameEngine(width, height)

    while True:
        success, frame = cap.read()
        if not success:
            continue

        frame = cv2.flip(frame, 1)

        hands = tracker.detect(frame)

        game.update(hands)

        renderer.render(frame, game, hands)

        cv2.imshow("Hand Game", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        if key in (ord("r"), ord("R")) and game.game_over:
            game.reset()


    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()