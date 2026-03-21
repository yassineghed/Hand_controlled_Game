import json
import math
import random
import time
from pathlib import Path

from objects import Ball

_SAVE_PATH = Path(__file__).resolve().parent / "hand_pop_best.json"


def _load_best_score():
    try:
        if _SAVE_PATH.exists():
            data = json.loads(_SAVE_PATH.read_text(encoding="utf-8"))
            return max(0, int(data.get("best", 0)))
    except (json.JSONDecodeError, OSError):
        pass
    return 0


def _save_best_score(value):
    try:
        _SAVE_PATH.write_text(json.dumps({"best": value}, indent=None), encoding="utf-8")
    except OSError:
        pass


class GameEngine:

    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.balls = []
        self.score = 0
        self.best_score = _load_best_score()
        self.combo = 0
        self.multiplier = 1

        self.lives_max = 5
        self.lives_left = self.lives_max
        self.game_over = False

        self.spawn_timer = 0
        self.base_spawn_interval = 40

        self.min_ball_visible_seconds = 3 / 5
        self.min_ball_travel_fraction = 0.15

        self.confetti_particles = []
        self.confetti_gravity = 0.35
        self.frame_count = 0

        self.countdown_frames = 0
        self.floating_texts = []
        self.combo_milestone = None

    def start_countdown(self, frames=72):
        self.countdown_frames = frames

    def reset(self):
        self.balls = []
        self.score = 0
        self.combo = 0
        self.multiplier = 1
        self.lives_left = self.lives_max
        self.game_over = False
        self.spawn_timer = 0
        self.confetti_particles = []
        self.countdown_frames = 0
        self.floating_texts = []
        self.combo_milestone = None


    def difficulty(self):
        # Difficulty increases as score rises but stays clamped.
        return min(4.0, 1.0 + max(0, self.score) / 25.0)


    def spawn_ball(self):
        # Health pickups only after at least one heart lost (still at full lives = no + balls).
        can_health = self.lives_left < self.lives_max
        is_health = can_health and random.random() < 0.15
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

    def update_floating_texts(self):
        alive = []
        for t in self.floating_texts:
            t["x"] += t.get("vx", 0)
            t["y"] += t.get("vy", 0)
            t["life"] -= 1
            if t["life"] > 0:
                alive.append(t)
        self.floating_texts = alive

    def update(self, hands):
        if self.game_over:
            return

        self.frame_count += 1
        self.update_confetti()
        self.update_floating_texts()

        if self.combo_milestone is not None:
            self.combo_milestone["frames"] -= 1
            if self.combo_milestone["frames"] <= 0:
                self.combo_milestone = None

        if self.countdown_frames > 0:
            self.countdown_frames -= 1
            return

        if self.score > self.best_score:
            self.best_score = self.score
            _save_best_score(self.best_score)

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
                        self.floating_texts.append({
                            "text": "+1",
                            "x": float(ball.x),
                            "y": float(ball.y),
                            "vx": 0.0,
                            "vy": -1.4,
                            "life": 50,
                            "max_life": 50,
                            "color": (0, 220, 0),
                            "scale": 0.9,
                        })
                    else:
                        old_mult = self.multiplier
                        self.combo += 1
                        self.multiplier = 1 + (self.combo // 5)
                        self.score += self.multiplier
                        if self.multiplier > old_mult:
                            self.combo_milestone = {"frames": 48, "multiplier": self.multiplier}
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
                self.floating_texts.append({
                    "text": "−1",
                    "x": float(self.width) / 2,
                    "y": float(self.height) * 0.4,
                    "vx": 0.0,
                    "vy": -0.6,
                    "life": 45,
                    "max_life": 45,
                    "color": (0, 0, 255),
                    "scale": 1.1,
                })
                if self.lives_left <= 0:
                    self.game_over = True
                    _save_best_score(self.best_score)
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