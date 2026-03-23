import json
import math
import random
import time
from datetime import date
from pathlib import Path

from objects import Ball

import design_tokens as DT

_SAVE_PATH = Path(__file__).resolve().parent / "hand_pop_best.json"

# 0.35s @ 60fps — edge telegraph; pop burst lifetime (spec).
TELEGRAPH_FRAMES = int(round(60 * DT.TELEGRAPH_SEC))
POP_BURST_FRAMES = DT.DUR_POP_BURST

SHAKE_OFFSETS = [(0, 0), (-8, 4), (7, -5), (-5, 3), (4, -2), (-2, 1)]
_PROGRESS_PATH = Path(__file__).resolve().parent / "hand_pop_progress.json"


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


def _load_progress():
    try:
        if _PROGRESS_PATH.exists():
            data = json.loads(_PROGRESS_PATH.read_text(encoding="utf-8"))
            return {
                "coins": max(0, int(data.get("coins", 0))),
                "xp": max(0, int(data.get("xp", 0))),
                "level": max(1, int(data.get("level", 1))),
            }
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        pass
    return {"coins": 0, "xp": 0, "level": 1}


def _save_progress(coins, xp, level):
    try:
        payload = json.dumps(
            {"coins": int(coins), "xp": int(xp), "level": int(level)},
            indent=None,
        )
        tmp = _PROGRESS_PATH.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(_PROGRESS_PATH)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _mission_rng_seed(day_ordinal: int, reroll_count: int):
    # Stable daily seed with small reroll offsets.
    return int(day_ordinal) * 7919 + int(reroll_count) * 101


class GameEngine:

    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.balls = []
        self.score = 0
        self.best_score = _load_best_score()
        progress = _load_progress()
        self.coins = progress["coins"]
        self.xp = progress["xp"]
        self.level = progress["level"]
        self.stage_name = "Rookie"
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
        self.pop_particles = []
        self.spawn_pending = []
        self.frame_count = 0

        self.countdown_frames = 0
        self.floating_texts = []
        self.combo_milestone = None
        self.juice_rim_frames = 0
        self.quiet_frames = 0
        self.hit_stop_frames = 0
        self.shake_frames = 0
        self.shake_strength = 0.0
        self.shake_keyed = False
        self.hint_bar_opacity = 1.0
        self.combo_last_pop_frame = -99999
        self.combo_pulse_frames = 0
        self.combo_flash_frames = 0
        self.life_loss_overlay_frames = 0
        self.life_loss_anim_frames = 0
        self.goal_flash_frames = 0
        self.near_miss_sparks = []
        self.pending_audio_events = []
        self.missions = []
        self.play_level = 1
        self.level_transition_pending = False
        self.level_complete_frames = 0
        self.mission_base = {"pops": 0, "score": 0, "combo": 0, "heal": 0}
        self.run_pops = 0
        self.run_health_pops = 0
        self.run_misses = 0
        self.run_best_combo = 0
        self.run_reward_coins = 0
        self.run_missions_completed = 0
        self.session_summary = None
        self.mission_rerolls = 0
        self.mission_day = date.today().toordinal()
        self._sync_stage()
        self._generate_missions()

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
        self.pop_particles = []
        self.spawn_pending = []
        self.countdown_frames = 0
        self.floating_texts = []
        self.combo_milestone = None
        self.juice_rim_frames = 0
        self.quiet_frames = 0
        self.hit_stop_frames = 0
        self.shake_frames = 0
        self.shake_strength = 0.0
        self.shake_keyed = False
        self.hint_bar_opacity = 1.0
        self.combo_last_pop_frame = -99999
        self.combo_pulse_frames = 0
        self.combo_flash_frames = 0
        self.life_loss_overlay_frames = 0
        self.life_loss_anim_frames = 0
        self.goal_flash_frames = 0
        self.near_miss_sparks = []
        self.pending_audio_events = []
        self.play_level = 1
        self.level_transition_pending = False
        self.level_complete_frames = 0
        self.mission_base = {"pops": 0, "score": 0, "combo": 0, "heal": 0}
        self.run_pops = 0
        self.run_health_pops = 0
        self.run_misses = 0
        self.run_best_combo = 0
        self.run_reward_coins = 0
        self.run_missions_completed = 0
        self.session_summary = None
        self.mission_rerolls = 0
        self.mission_day = date.today().toordinal()
        self._sync_stage()
        self._generate_missions()


    def difficulty(self):
        # Scale with score + account level tiers; still clamped for fairness.
        tier_bonus = {
            "Rookie": 0.00,
            "Skilled": 0.10,
            "Expert": 0.18,
            "Master": 0.24,
        }.get(self.stage_name, 0.0)
        return min(3.3, 1.0 + max(0, self.score) / 42.0 + tier_bonus)

    def _xp_needed(self, level=None):
        lv = self.level if level is None else int(level)
        return 60 + lv * 28

    def _sync_stage(self):
        if self.level >= 16:
            self.stage_name = "Master"
        elif self.level >= 11:
            self.stage_name = "Expert"
        elif self.level >= 6:
            self.stage_name = "Skilled"
        else:
            self.stage_name = "Rookie"

    @property
    def xp_next(self):
        return self._xp_needed(self.level)

    def _grant_progress(self, coins=0, xp=0):
        self.coins += int(max(0, coins))
        self.xp += int(max(0, xp))
        leveled_up = False
        while self.xp >= self._xp_needed(self.level):
            self.xp -= self._xp_needed(self.level)
            self.level += 1
            self._sync_stage()
            leveled_up = True
            self.floating_texts.append({
                "kind": "event",
                "text": f"LEVEL {self.level}!",
                "x": float(self.width) * 0.5,
                "y": float(self.height) * 0.28,
                "vx": 0.0,
                "vy": -0.5,
                "life": 60,
                "max_life": 60,
                "color": (170, 230, 255),
                "scale": 0.7,
            })
            self._emit_audio("mission")
        if leveled_up:
            self.juice_rim_frames = max(self.juice_rim_frames, 18)
        _save_progress(self.coins, self.xp, self.level)

    def _generate_missions(self):
        seed = _mission_rng_seed(self.mission_day + self.play_level * 17, self.mission_rerolls)
        rng = random.Random(seed)
        lvl_scale = max(0, self.play_level - 1)
        templates = [
            (
                "pop",
                "Pop {n} balls",
                rng.randint(18 + lvl_scale * 2, 34 + lvl_scale * 3),
                rng.randint(18 + lvl_scale, 32 + lvl_scale * 2),
            ),
            (
                "score",
                "Reach score {n}",
                rng.randint(45 + lvl_scale * 4, 95 + lvl_scale * 6),
                rng.randint(22 + lvl_scale * 2, 40 + lvl_scale * 3),
            ),
            (
                "combo",
                "Reach combo x{n}",
                rng.randint(3 + lvl_scale // 3, 6 + lvl_scale // 2),
                rng.randint(24 + lvl_scale * 2, 45 + lvl_scale * 3),
            ),
            (
                "heal",
                "Collect {n} health pickups",
                rng.randint(2, 4 + lvl_scale // 4),
                rng.randint(20 + lvl_scale * 2, 34 + lvl_scale * 3),
            ),
        ]
        rng.shuffle(templates)
        chosen = templates[:3]
        self.missions = [
            {
                "id": k,
                "label": label.format(n=target),
                "target": int(target),
                "progress": 0,
                "reward": int(reward),
                "done": False,
            }
            for (k, label, target, reward) in chosen
        ]
        self.mission_base = {
            "pops": self.run_pops,
            "score": self.score,
            "combo": self.run_best_combo,
            "heal": self.run_health_pops,
        }

    def reroll_missions(self):
        self.mission_rerolls += 1
        self._generate_missions()
        self._emit_audio("mission")

    def _advance_play_level(self):
        self.play_level += 1
        self.level_transition_pending = False
        self.level_complete_frames = 0
        self.mission_rerolls = 0
        self.balls = []
        self.spawn_pending = []
        self.start_countdown(54)
        self._generate_missions()
        self._emit_audio("mission")

    def force_next_level(self):
        if self.level_transition_pending:
            self._advance_play_level()

    def _tick_missions(self):
        for m in self.missions:
            if m["done"]:
                continue
            if m["id"] == "pop":
                m["progress"] = min(m["target"], self.run_pops - self.mission_base["pops"])
            elif m["id"] == "score":
                m["progress"] = min(m["target"], self.score - self.mission_base["score"])
            elif m["id"] == "combo":
                m["progress"] = min(m["target"], self.run_best_combo - self.mission_base["combo"])
            elif m["id"] == "heal":
                m["progress"] = min(m["target"], self.run_health_pops - self.mission_base["heal"])

            if m["progress"] >= m["target"]:
                m["done"] = True
                self.goal_flash_frames = max(self.goal_flash_frames, DT.DUR_GOAL_FLASH)
                self.run_missions_completed += 1
                self.run_reward_coins += m["reward"]
                self._grant_progress(coins=m["reward"], xp=m["reward"] * 2)
                self.floating_texts.append({
                    "kind": "event",
                    "text": f"MISSION +{m['reward']}c",
                    "x": float(self.width) * 0.5,
                    "y": float(self.height) * 0.18,
                    "vx": 0.0,
                    "vy": -0.45,
                    "life": 55,
                    "max_life": 55,
                    "color": (150, 235, 255),
                    "scale": 0.58,
                })
                self.juice_rim_frames = max(self.juice_rim_frames, 18)
                self._emit_audio("mission")
        if self.missions and all(bool(m.get("done", False)) for m in self.missions):
            if not self.level_transition_pending:
                self.level_transition_pending = True
                self.level_complete_frames = 90
                self.juice_rim_frames = max(self.juice_rim_frames, 28)
                self._emit_audio("combo_up")

    def _build_session_summary(self):
        total_events = self.run_pops + self.run_misses
        accuracy = 100.0 * self.run_pops / total_events if total_events > 0 else 100.0
        return {
            "pops": int(self.run_pops),
            "misses": int(self.run_misses),
            "accuracy": float(accuracy),
            "best_combo": int(self.run_best_combo),
            "missions_completed": int(self.run_missions_completed),
            "coins_earned": int(self.run_reward_coins),
            "level": int(self.level),
            "stage": str(self.stage_name),
            "play_level": int(self.play_level),
        }


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
        self.spawn_pending.append({"frames": TELEGRAPH_FRAMES, "ball": ball})

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
        n = max(2, n)
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

    def _spawn_pop_burst(self, x, y, combo_for_scale: int):
        """White ~80% opacity particles; count & speed scale lightly with combo."""
        ml = POP_BURST_FRAMES
        n = random.randint(DT.POP_PARTICLE_MIN, DT.POP_PARTICLE_MAX)
        mult = 1.0 + min(0.4, max(0, int(combo_for_scale) - 1) * 0.13)
        wcol = tuple(int(c * DT.POP_PARTICLE_WHITE) for c in DT.C_WHITE)
        for _ in range(n):
            ang = random.uniform(0, math.pi * 2)
            spd = random.uniform(4.0, 9.0) * mult
            self.pop_particles.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "vx": math.cos(ang) * spd,
                    "vy": math.sin(ang) * spd,
                    "life": ml,
                    "max_life": ml,
                    "r0": random.uniform(3.0, 6.0),
                    "color": wcol,
                }
            )
        if len(self.pop_particles) > 400:
            self.pop_particles = self.pop_particles[-400:]

    def update_pop_particles(self):
        alive = []
        for p in self.pop_particles:
            p["vx"] *= 0.88
            p["vy"] *= 0.88
            p["vy"] += 0.11
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["life"] > 0:
                alive.append(p)
        self.pop_particles = alive

    def _tick_spawn_pending(self):
        if not self.spawn_pending:
            return
        nxt = []
        for item in self.spawn_pending:
            item["frames"] -= 1
            if item["frames"] <= 0:
                b = item["ball"]
                b.spawn_time = time.perf_counter()
                self.balls.append(b)
            else:
                nxt.append(item)
        self.spawn_pending = nxt

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
        # Keep telegraphs advancing during hit-stop (combo freeze is only 1–2 frames)
        if self.countdown_frames <= 0 and not self.level_transition_pending:
            self._tick_spawn_pending()
        self.update_confetti()
        self.update_pop_particles()
        self.update_floating_texts()
        self._update_near_miss_sparks()

        if self.play_level > 2:
            self.hint_bar_opacity = max(0.0, self.hint_bar_opacity - 1.0 / 60.0)
        else:
            self.hint_bar_opacity = 1.0

        if self.combo_pulse_frames > 0:
            self.combo_pulse_frames -= 1
        if self.combo_flash_frames > 0:
            self.combo_flash_frames -= 1
        if self.life_loss_overlay_frames > 0:
            self.life_loss_overlay_frames -= 1
        if self.life_loss_anim_frames > 0:
            self.life_loss_anim_frames -= 1
        if self.goal_flash_frames > 0:
            self.goal_flash_frames -= 1

        if self.combo_milestone is not None:
            self.combo_milestone["frames"] -= 1
            if self.combo_milestone["frames"] <= 0:
                self.combo_milestone = None

        if self.juice_rim_frames > 0:
            self.juice_rim_frames -= 1
        if self.quiet_frames > 0:
            self.quiet_frames -= 1
        if self.hit_stop_frames > 0:
            self.hit_stop_frames -= 1
            return

        if self.countdown_frames > 0:
            self.countdown_frames -= 1
            return
        if self.level_transition_pending:
            self.level_complete_frames -= 1
            if self.level_complete_frames <= 0:
                self._advance_play_level()
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
            if getattr(ball, "_near_miss_cd", 0) > 0:
                ball._near_miss_cd -= 1
            ball.update()
            self._apply_fairness_bounce(ball, now)

        self.check_collisions(hands)
        self._check_near_misses(hands)

        self.remove_offscreen_balls()
        self._tick_missions()

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

    def _spawn_near_miss(self, hx, hy, bx, by):
        ang = math.atan2(by - hy, bx - hx)
        for _ in range(DT.NEAR_MISS_SPARK_COUNT):
            a = ang + random.uniform(-0.4, 0.4)
            spd = random.uniform(1.4, 3.6)
            self.near_miss_sparks.append(
                {
                    "x": float(hx),
                    "y": float(hy),
                    "vx": math.cos(a) * spd,
                    "vy": math.sin(a) * spd,
                    "life": DT.DUR_NEAR_MISS_SPARK,
                    "max_life": DT.DUR_NEAR_MISS_SPARK,
                    "r": 2,
                }
            )
        if len(self.near_miss_sparks) > 200:
            self.near_miss_sparks = self.near_miss_sparks[-200:]

    def _update_near_miss_sparks(self):
        alive = []
        for p in self.near_miss_sparks:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["life"] > 0:
                alive.append(p)
        self.near_miss_sparks = alive

    def _check_near_misses(self, hands):
        for ball in self.balls:
            for hand in hands:
                dist = math.hypot(ball.x - hand["x"], ball.y - hand["y"])
                hit_r = ball.radius + hand["radius"]
                if dist >= hit_r and dist < DT.NEAR_MISS_DIST_MULT * hit_r:
                    if getattr(ball, "_near_miss_cd", 0) <= 0:
                        self._spawn_near_miss(
                            hand["x"], hand["y"], ball.x, ball.y
                        )
                        ball._near_miss_cd = 12
                    break

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
                        self.run_health_pops += 1
                        self.juice_rim_frames = max(self.juice_rim_frames, 14)
                        self.quiet_frames = max(self.quiet_frames, 36)
                        self.shake_keyed = False
                        self.shake_frames = max(self.shake_frames, 6)
                        self.shake_strength = max(self.shake_strength, 1.4)
                        self._emit_audio("health")
                        self._spawn_pop_burst(ball.x, ball.y, self.combo)
                        self.spawn_confetti(
                            ball.x,
                            ball.y,
                            self.multiplier,
                            ball.color,
                            burst_mult=0.18,
                            preset="health",
                        )
                        self.floating_texts.append({
                            "kind": "event",
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
                        self.run_pops += 1
                        self.run_best_combo = max(self.run_best_combo, self.combo)
                        self.multiplier = 1 + (self.combo // 5)
                        pts = self.multiplier
                        self.score += pts
                        self.combo_last_pop_frame = self.frame_count
                        self.combo_pulse_frames = DT.COMBO_PULSE_FRAMES
                        self._spawn_pop_burst(ball.x, ball.y, self.combo)
                        pop_col = (
                            DT.C_WHITE if self.combo < 3 else DT.C_AMBER
                        )
                        self.floating_texts.append(
                            {
                                "kind": "score_popup",
                                "text": f"+{pts}",
                                "x": float(ball.x),
                                "y": float(ball.y) - float(ball.radius) * 0.35,
                                "vx": random.uniform(-0.15, 0.15),
                                "vy": -(DT.SCORE_POP_DRIFT_PX / float(DT.DUR_SCORE_POP)),
                                "life": DT.DUR_SCORE_POP,
                                "max_life": DT.DUR_SCORE_POP,
                                "color": pop_col,
                                "scale": 0.74,
                            }
                        )
                        if self.multiplier > old_mult:
                            self.combo_milestone = {"frames": 52, "multiplier": self.multiplier}
                            self.combo_flash_frames = max(
                                self.combo_flash_frames, DT.DUR_COMBO_FLASH
                            )
                            self.juice_rim_frames = max(self.juice_rim_frames, 22)
                            self.quiet_frames = max(self.quiet_frames, 20)
                            self.hit_stop_frames = max(self.hit_stop_frames, 2)
                            self.shake_keyed = False
                            self.shake_frames = max(self.shake_frames, 10)
                            self.shake_strength = max(self.shake_strength, 3.2)
                            self._emit_audio("combo_up")
                            self.spawn_confetti(
                                ball.x,
                                ball.y,
                                self.multiplier + 2,
                                (100, 210, 255),
                                burst_mult=1.35,
                                preset="combo",
                            )
                        else:
                            self._emit_audio("pop")
                            self.spawn_confetti(
                                ball.x,
                                ball.y,
                                self.multiplier,
                                ball.color,
                                burst_mult=0.22,
                                preset="normal",
                            )
                        if self.score > old_best:
                            self.juice_rim_frames = max(self.juice_rim_frames, 30)
                            self.quiet_frames = max(self.quiet_frames, 44)
                            self._emit_audio("new_best")
                            self.floating_texts.append(
                                {
                                    "kind": "event",
                                    "text": "NEW BEST!",
                                    "x": float(self.width) * 0.5,
                                    "y": float(self.height) * 0.22,
                                    "vx": 0.0,
                                    "vy": -0.45,
                                    "life": 55,
                                    "max_life": 55,
                                    "color": (180, 255, 255),
                                    "scale": 0.62,
                                }
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
                self.run_misses += 1
                self.floating_texts.append({
                    "kind": "event",
                    "text": "-1",
                    "x": float(self.width) / 2,
                    "y": float(self.height) * 0.36,
                    "vx": 0.0,
                    "vy": -0.6,
                    "life": 45,
                    "max_life": 45,
                    # Light coral (BGR): reads on dark hair; outline from renderer adds contrast.
                    "color": (210, 230, 255),
                    "scale": 1.0,
                })
                if self.lives_left <= 0:
                    self.game_over = True
                    self.session_summary = self._build_session_summary()
                    _save_best_score(self.best_score)
                    self._emit_audio("game_over")
                else:
                    self._emit_audio("miss")
                self.shake_keyed = True
                self.shake_frames = len(SHAKE_OFFSETS)
                self.shake_strength = 1.0
                self.life_loss_overlay_frames = max(
                    self.life_loss_overlay_frames, DT.DUR_LIFE_LOSS_FLASH
                )
                self.life_loss_anim_frames = max(
                    self.life_loss_anim_frames, DT.DUR_HEART_LOSS_ANIM
                )
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