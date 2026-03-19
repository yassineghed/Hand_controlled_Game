import random

class Ball:
    def __init__(self, width, height):
        self.radius = random.randint(20, 35)

        # Spawn balls from different screen edges with higher speeds
        side = random.choice(["top", "left", "right"])

        if side == "top":
            self.x = random.randint(50, width - 50)
            self.y = -self.radius
            self.vx = random.uniform(-6, 6)
            self.vy = random.uniform(8, 12)
        elif side == "left":
            self.x = -self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(6, 10)
            self.vy = random.uniform(-4, 4)
        else:  # right
            self.x = width + self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(-10, -6)
            self.vy = random.uniform(-4, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy