import random

# BGR — pastel score targets (softer, desaturated).
BALL_COLORS = [
    (180, 230, 255),   # pastel yellow
    (220, 230, 200),   # pastel cyan
    (180, 210, 255),   # pastel peach
    (230, 200, 240),   # pastel pink
    (240, 220, 200),   # pastel blue
    (200, 200, 255),   # pastel coral
    (210, 220, 235),   # pastel lavender
    (200, 240, 230),   # pastel mint
    (225, 210, 230),   # pastel orchid
]


# BGR — distinct green for health balls (restore +1 life when popped).
HEALTH_BALL_COLOR = (0, 220, 0)


class Ball:
    def __init__(
        self,
        width,
        height,
        difficulty=1.0,
        spawn_time=0.0,
        min_visible_seconds=3 / 5,
        min_travel_fraction=0.15,
        is_health_ball=False,
    ):
        self.is_health_ball = bool(is_health_ball)
        self.radius = random.randint(34, 48) if self.is_health_ball else random.randint(20, 35)
        self.color = HEALTH_BALL_COLOR if self.is_health_ball else random.choice(BALL_COLORS)

        difficulty = max(0.5, float(difficulty))

        self.spawn_time = float(spawn_time)
        self.min_visible_seconds = float(min_visible_seconds)
        self.min_travel_fraction = float(min_travel_fraction)
        # Used to ensure a ball doesn't get removed "too quickly".
        self.start_x = 0.0
        self.start_y = 0.0

        # Spawn balls from different screen edges with higher speeds
        # (more variety than only top/left/right)
        side = random.choice(["top", "bottom", "left", "right"])

        if side == "top":
            self.x = random.randint(50, width - 50)
            self.y = -self.radius
            self.vx = random.uniform(-6, 6) * (0.8 + 0.2 * difficulty)
            self.vy = random.uniform(8, 12) * difficulty
        elif side == "bottom":
            self.x = random.randint(50, width - 50)
            self.y = height + self.radius
            self.vx = random.uniform(-6, 6) * (0.8 + 0.2 * difficulty)
            self.vy = random.uniform(-12, -8) * difficulty
        elif side == "left":
            self.x = -self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(6, 10) * difficulty
            self.vy = random.uniform(-4, 4) * (0.7 + 0.3 * difficulty)
        else:  # right
            self.x = width + self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(-10, -6) * difficulty
            self.vy = random.uniform(-4, 4) * (0.7 + 0.3 * difficulty)

        self.start_x = float(self.x)
        self.start_y = float(self.y)

    def age_seconds(self, now):
        return float(now) - self.spawn_time

    def update(self):
        self.x += self.vx
        self.y += self.vy