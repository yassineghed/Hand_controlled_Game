import cv2


def draw_hands(frame, hands):

    for hand in hands:

        x = int(hand["x"])
        y = int(hand["y"])
        r = int(hand["radius"])

        cv2.circle(frame, (x, y), r, (0,255,0), 3)


def draw_balls(frame, balls):

    for ball in balls:

        cv2.circle(
            frame,
            (int(ball.x), int(ball.y)),
            ball.radius,
            (0,0,255),
            -1
        )


def draw_score(frame, score):

    cv2.putText(
        frame,
        f"Score: {score}",
        (20,60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (255,255,255),
        3
    )


def render(frame, game, hands):

    draw_hands(frame, hands)
    draw_balls(frame, game.balls)
    draw_score(frame, game.score)