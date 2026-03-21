import random
import math
import time
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

        # Fairness: don't remove a ball immediately after spawning.
        # - visible for at least 3/5 seconds
        # - travel through at least 15% of the screen (by path length)
        self.min_ball_visible_seconds = 3 / 5  # 0.6s
        self.min_ball_travel_fraction = 0.15

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
        is_health = random.random() < 0.15
        ball = Ball(
            self.width,
            self.height,
            difficulty=self.difficulty(),
            spawn_time=time.perf_counter(),
            min_visible_seconds=self.min_ball_visible_seconds,
            min_travel_fraction=self.min_ball_travel_fraction,
            is_health_ball=is_health,
        )
        self.balls.append(ball)

    def spawn_confetti(self, x, y, multiplier, color):
        # Create a small burst of particles at (x, y).
        # Particle count scales lightly with multiplier.
        n = int(10 + min(25, multiplier * 6))
        # Same color as the ball; particles share it and fade via draw_confetti.
        burst_color = color

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
                "color": burst_color,
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

        now = time.perf_counter()
        for ball in self.balls:
            ball.update()
            self._apply_fairness_bounce(ball, now)

        self.check_collisions(hands)

        self.remove_offscreen_balls()

    def _ball_is_fair(self, ball, now):
        """True when age + travel rules allow the ball to leave / count as a miss."""
        min_travel_pixels = self.min_ball_travel_fraction * float(
            max(self.width, self.height)
        )
        age_ok = ball.age_seconds(now) >= self.min_ball_visible_seconds
        travel_ok = (
            math.hypot(ball.x - ball.start_x, ball.y - ball.start_y)
            >= min_travel_pixels
        )
        return age_ok and travel_ok

    def _apply_fairness_bounce(self, ball, now):
        """
        While the ball is still in its 'unfair' window, keep it inside the
        extended play rect (same bounds used for off-screen checks) by
        clamping position and reflecting velocity — so it doesn't sit
        invisibly off-screen until the timer expires.
        """
        if self._ball_is_fair(ball, now):
            return

        r = float(ball.radius)
        min_x, max_x = -r, self.width + r
        min_y, max_y = -r, self.height + r
        eps = 2.0
        damp = 0.92

        if ball.x < min_x:
            ball.x = min_x + eps
            ball.vx = abs(ball.vx) * damp
        elif ball.x > max_x:
            ball.x = max_x - eps
            ball.vx = -abs(ball.vx) * damp

        if ball.y < min_y:
            ball.y = min_y + eps
            ball.vy = abs(ball.vy) * damp
        elif ball.y > max_y:
            ball.y = max_y - eps
            ball.vy = -abs(ball.vy) * damp


    def check_collisions(self, hands):

        remaining_balls = []

        for ball in self.balls:

            hit = False

            for hand in hands:

                dx = ball.x - hand["x"]
                dy = ball.y - hand["y"]

                dist = math.sqrt(dx*dx + dy*dy)

                if dist < ball.radius + hand["radius"]:
                    if ball.is_health_ball:
                        self.lives_left = min(self.lives_max, self.lives_left + 1)
                    else:
                        self.combo += 1
                        self.multiplier = 1 + (self.combo // 5)
                        self.score += self.multiplier
                    self.spawn_confetti(ball.x, ball.y, self.multiplier, ball.color)
                    hit = True
                    break

            if not hit:
                remaining_balls.append(ball)

        self.balls = remaining_balls


    def remove_offscreen_balls(self):

        remaining = []
        removed_any = False

        now = time.perf_counter()

        for ball in self.balls:

            is_offscreen = (
                ball.y > self.height + ball.radius or
                ball.y < -ball.radius or
                ball.x < -ball.radius or
                ball.x > self.width + ball.radius
            )

            if not is_offscreen:
                remaining.append(ball)
                continue

            # Health balls are optional bonus; missing them doesn't cost a life.
            if ball.is_health_ball:
                continue

            # Fairness: don't immediately penalize for balls that are just spawned.
            if self._ball_is_fair(ball, now):
                self.lives_left -= 1
                if self.lives_left <= 0:
                    self.game_over = True
                removed_any = True
            else:
                # Keep the ball around until it has had time to "exist"
                # and travel far enough to be fair to the player.
                remaining.append(ball)

        self.balls = remaining

        # Missing a ball breaks the combo.
        if removed_any:
            self.combo = 0
            self.multiplier = 1