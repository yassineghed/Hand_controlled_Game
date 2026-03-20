import random

class Ball:
    def __init__(
        self,
        width,
        height,
        difficulty=1.0,
        spawn_time=0.0,
        min_visible_seconds=3 / 5,
        min_travel_fraction=0.15,
    ):
        self.radius = random.randint(20, 35)

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