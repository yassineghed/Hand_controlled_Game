import random
import math
from objects import Ball


class GameEngine:

    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.balls = []
        self.score = 0
        self.combo = 0
        self.multiplier = 1

        # Kids-friendly: use lives instead of reducing score on misses.
        self.lives_max = 5
        self.lives_left = self.lives_max
        self.game_over = False

        self.spawn_timer = 0
        self.base_spawn_interval = 40

        # Confetti "pop" particles for kid-friendly feedback.
        # Stored as small flying pieces that fade out quickly.
        self.confetti_particles = []
        self.confetti_gravity = 0.35
        self.frame_count = 0

    def reset(self):
        self.balls = []
        self.score = 0
        self.combo = 0
        self.multiplier = 1
        self.lives_left = self.lives_max
        self.game_over = False
        self.spawn_timer = 0
        self.confetti_particles = []
        self.frame_count = 0


    def difficulty(self):
        # Difficulty increases as score rises but stays clamped.
        return min(4.0, 1.0 + max(0, self.score) / 25.0)


    def spawn_ball(self):
        ball = Ball(self.width, self.height, difficulty=self.difficulty())
        self.balls.append(ball)

    def spawn_confetti(self, x, y, multiplier):
        # Create a small burst of particles at (x, y).
        # Particle count scales lightly with multiplier.
        n = int(10 + min(25, multiplier * 6))
        colors = [
            (0, 255, 255),   # yellow/cyan-ish in BGR
            (255, 255, 0),   # blue? (BGR)
            (0, 255, 0),     # green
            (0, 165, 255),   # orange
            (255, 0, 255),   # pink/magenta
            (255, 0, 0),     # blue
            (255, 255, 255), # white
            (0, 0, 255),     # red
        ]

        for _ in range(n):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1.5, 5.0) * (0.85 + 0.15 * multiplier)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - random.uniform(0.5, 2.5)
            life = random.randint(12, 22)
            size = random.randint(2, 5)
            self.confetti_particles.append({
                "x": float(x),
                "y": float(y),
                "vx": vx,
                "vy": vy,
                "life": life,
                "max_life": life,
                "color": random.choice(colors),
                "size": size,
            })

        # Prevent unbounded growth in case of rapid hits.
        if len(self.confetti_particles) > 800:
            self.confetti_particles = self.confetti_particles[-800:]

    def update_confetti(self):
        alive = []
        for p in self.confetti_particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += self.confetti_gravity
            p["life"] -= 1
            if p["life"] > 0:
                alive.append(p)
        self.confetti_particles = alive


    def update(self, hands):
        if self.game_over:
            return

        self.frame_count += 1
        self.update_confetti()

        # Spawn ball faster as difficulty increases.
        self.spawn_timer += 1
        diff = self.difficulty()
        spawn_interval = int(max(12, self.base_spawn_interval / diff))

        if self.spawn_timer > spawn_interval:
            self.spawn_ball()
            self.spawn_timer = 0

        for ball in self.balls:
            ball.update()

        self.check_collisions(hands)

        self.remove_offscreen_balls()


    def check_collisions(self, hands):

        remaining_balls = []

        for ball in self.balls:

            hit = False

            for hand in hands:

                dx = ball.x - hand["x"]
                dy = ball.y - hand["y"]

                dist = math.sqrt(dx*dx + dy*dy)

                if dist < ball.radius + hand["radius"]:
                    self.combo += 1
                    # Every 5 consecutive hits increases the multiplier.
                    self.multiplier = 1 + (self.combo // 5)
                    self.score += self.multiplier
                    self.spawn_confetti(ball.x, ball.y, self.multiplier)
                    hit = True
                    break

            if not hit:
                remaining_balls.append(ball)

        self.balls = remaining_balls


    def remove_offscreen_balls(self):

        remaining = []
        removed_any = False

        for ball in self.balls:

            if (
                ball.y > self.height + ball.radius or
                ball.y < -ball.radius or
                ball.x < -ball.radius or
                ball.x > self.width + ball.radius
            ):
                self.lives_left -= 1
                if self.lives_left <= 0:
                    self.game_over = True
                removed_any = True
            else:
                remaining.append(ball)

        self.balls = remaining

        # Missing a ball breaks the combo.
        if removed_any:
            self.combo = 0
            self.multiplier = 1