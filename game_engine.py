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
    except json.JSONDecodeError:
        try:
            bad = _SAVE_PATH.with_suffix(".corrupt.json")
            if bad.exists():
                bad.unlink()
            _SAVE_PATH.rename(bad)
        except OSError:
            pass
    except OSError:
        pass
    return 0


def _save_best_score(value):
    try:
        payload = json.dumps({"best": int(value)}, indent=None)
        tmp = _SAVE_PATH.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(_SAVE_PATH)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
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
        self.base_spawn_interval = 52

        self.min_ball_visible_seconds = 3 / 5
        self.min_ball_travel_fraction = 0.15

        self.confetti_particles = []
        self.confetti_gravity = 0.35
        self.frame_count = 0

        self.countdown_frames = 0
        self.floating_texts = []
        self.combo_milestone = None
        self.juice_rim_frames = 0
        self.quiet_frames = 0
        self.hit_stop_frames = 0
        self.shake_frames = 0
        self.shake_strength = 0.0
        self.pending_audio_events = []

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
        self.juice_rim_frames = 0
        self.quiet_frames = 0
        self.hit_stop_frames = 0
        self.shake_frames = 0
        self.shake_strength = 0.0
        self.pending_audio_events = []


    def difficulty(self):
        # Gentler ramp: more score per step, lower ceiling (easier on hands / camera lag).
        return min(3.1, 1.0 + max(0, self.score) / 42.0)


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

    def _emit_audio(self, name):
        self.pending_audio_events.append(str(name))
        if len(self.pending_audio_events) > 32:
            self.pending_audio_events = self.pending_audio_events[-32:]

    def spawn_confetti(self, x, y, multiplier, color, burst_mult=1.0, preset="normal"):
        # Create a small burst of particles at (x, y).
        # Particle count scales lightly with multiplier.
        profile = {
            "normal": {"speed": (1.4, 4.6), "life": (12, 20), "size": (2, 4)},
            "combo": {"speed": (2.2, 6.2), "life": (16, 28), "size": (2, 5)},
            "health": {"speed": (1.1, 3.8), "life": (14, 24), "size": (2, 4)},
            "miss": {"speed": (1.0, 2.6), "life": (10, 16), "size": (1, 3)},
        }.get(preset, {"speed": (1.4, 4.6), "life": (12, 20), "size": (2, 4)})
        n = int((10 + min(25, multiplier * 6)) * burst_mult)
        # Same color as the ball; particles share it and fade via draw_confetti.
        burst_color = color

        for _ in range(n):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(*profile["speed"]) * (0.85 + 0.15 * multiplier)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - random.uniform(0.5, 2.5)
            life = random.randint(*profile["life"])
            size = random.randint(*profile["size"])
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

        if self.juice_rim_frames > 0:
            self.juice_rim_frames -= 1
        if self.quiet_frames > 0:
            self.quiet_frames -= 1
        if self.shake_frames > 0:
            self.shake_frames -= 1
        if self.hit_stop_frames > 0:
            self.hit_stop_frames -= 1
            return

        if self.countdown_frames > 0:
            self.countdown_frames -= 1
            return

        if self.score > self.best_score:
            self.best_score = self.score
            _save_best_score(self.best_score)

        self.spawn_timer += 1
        diff = self.difficulty()
        spawn_interval = int(max(24, self.base_spawn_interval / diff))

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
                        self.juice_rim_frames = max(self.juice_rim_frames, 14)
                        self.quiet_frames = max(self.quiet_frames, 36)
                        self.shake_frames = max(self.shake_frames, 6)
                        self.shake_strength = max(self.shake_strength, 1.4)
                        self._emit_audio("health")
                        self.floating_texts.append({
                            "text": "LIFE!",
                            "x": float(ball.x),
                            "y": float(ball.y) - 8,
                            "vx": random.uniform(-0.25, 0.25),
                            "vy": -1.1,
                            "life": 52,
                            "max_life": 52,
                            "color": (120, 255, 160),
                            "scale": 0.72,
                        })
                    else:
                        old_best = self.best_score
                        old_mult = self.multiplier
                        self.combo += 1
                        self.multiplier = 1 + (self.combo // 5)
                        pts = self.multiplier
                        self.score += pts
                        self.floating_texts.append({
                            "text": f"+{pts}",
                            "x": float(ball.x),
                            "y": float(ball.y) - float(ball.radius) * 0.35,
                            "vx": random.uniform(-0.35, 0.35),
                            "vy": -1.25,
                            "life": 40,
                            "max_life": 40,
                            "color": (140, 230, 255),
                            "scale": 0.68,
                        })
                        if self.multiplier > old_mult:
                            self.combo_milestone = {"frames": 52, "multiplier": self.multiplier}
                            self.juice_rim_frames = max(self.juice_rim_frames, 22)
                            self.quiet_frames = max(self.quiet_frames, 20)
                            self.hit_stop_frames = max(self.hit_stop_frames, 2)
                            self.shake_frames = max(self.shake_frames, 10)
                            self.shake_strength = max(self.shake_strength, 3.2)
                            self._emit_audio("combo_up")
                            self.spawn_confetti(
                                ball.x,
                                ball.y,
                                self.multiplier + 2,
                                (100, 210, 255),
                                burst_mult=1.55,
                                preset="combo",
                            )
                        else:
                            self._emit_audio("pop")
                        if self.score > old_best:
                            self.juice_rim_frames = max(self.juice_rim_frames, 30)
                            self.quiet_frames = max(self.quiet_frames, 44)
                            self._emit_audio("new_best")
                            self.floating_texts.append({
                                "text": "NEW BEST!",
                                "x": float(self.width) * 0.5,
                                "y": float(self.height) * 0.22,
                                "vx": 0.0,
                                "vy": -0.45,
                                "life": 55,
                                "max_life": 55,
                                "color": (180, 255, 255),
                                "scale": 0.62,
                            })
                    self.spawn_confetti(
                        ball.x,
                        ball.y,
                        self.multiplier,
                        ball.color,
                        preset="health" if ball.is_health_ball else "normal",
                    )
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
                    self._emit_audio("game_over")
                else:
                    self._emit_audio("miss")
                self.shake_frames = max(self.shake_frames, 8)
                self.shake_strength = max(self.shake_strength, 2.6)
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