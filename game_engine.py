import random
import math
from objects import Ball


class GameEngine:

    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.balls = []
        self.score = 0

        self.spawn_timer = 0


    def spawn_ball(self):
        ball = Ball(self.width)
        self.balls.append(ball)


    def update(self, hands):

        # spawn ball every ~40 frames
        self.spawn_timer += 1
        if self.spawn_timer > 40:
            self.spawn_ball()
            self.spawn_timer = 0

        for ball in self.balls:
            ball.update()

        self.check_collisions(hands)

        self.remove_offscreen_balls()


    def check_collisions(self, hands):

        for ball in self.balls:

            for hand in hands:

                dx = ball.x - hand["x"]
                dy = ball.y - hand["y"]

                dist = math.sqrt(dx*dx + dy*dy)

                if dist < ball.radius + hand["radius"]:
                    ball.vy = -abs(ball.vy)
                    self.score += 1


    def remove_offscreen_balls(self):

        remaining = []

        for ball in self.balls:

            if ball.y > self.height:
                self.score -= 1
            else:
                remaining.append(ball)

        self.balls = remaining