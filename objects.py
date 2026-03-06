import random

class Ball:
    def __init__(self, width):
        self.radius = random.randint(20, 35)

        self.x = random.randint(50, width - 50)
        self.y = 0

        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(4, 7)

    def update(self):
        self.x += self.vx
        self.y += self.vy