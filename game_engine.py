import json
import math
import random
import time
from datetime import date
from pathlib import Path

from objects import Ball
from lane_system import LaneSystem

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
        self.lane_system = LaneSystem(width, height)

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

        # Start near threshold so first ball spawns almost immediately
        self.spawn_timer = 42
        self.game_start_time = time.perf_counter()
        self.rage_mode = False
        self.rage_flash_frames = 0
        self.combo_decay_timer = 0
        self.burst_cooldown = 0

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
        self.spawn_timer = 42
        self.game_start_time = time.perf_counter()
        self.rage_mode = False
        self.rage_flash_frames = 0
        self.combo_decay_timer = 0
        self.burst_cooldown = 0
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
        tier_bonus = {
            "Rookie": 0.00,
            "Skilled": 0.15,
            "Expert": 0.28,
            "Master": 0.42,
        }.get(self.stage_name, 0.0)
        elapsed = time.perf_counter() - self.game_start_time
        return min(5.5, 1.0 + max(self.score / 25.0, elapsed / 20.0) + tier_bonus)

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


    def _z_speed(self, diff: float, variance: float = 0.0) -> float:
        """variance in [-1, 1] adds ±25% speed randomness."""
        t = min((diff - 1.0) / 4.5, 1.0)
        travel_frames = 55.0 - 27.0 * t  # 55f at diff=1, 28f at diff=5.5
        if self.rage_mode:
            travel_frames *= 0.72  # 28% faster during rage
        speed = 1.0 / travel_frames
        speed *= 1.0 + variance * 0.25
        return max(speed, 1.0 / 55.0)

    def _pick_ball_type(self, diff: float) -> str:
        r = random.random()
        bomb_chance = min(0.18, 0.06 + diff * 0.02)
        gold_chance = 0.12
        health_chance = 0.10 if self.lives_left < self.lives_max else 0.0
        if r < bomb_chance:
            return "bomb"
        if r < bomb_chance + gold_chance:
            return "gold"
        if r < bomb_chance + gold_chance + health_chance:
            return "health"
        return "normal"

    def _make_ball(self, lane: int, diff: float, ball_type: str = None) -> "Ball":
        if ball_type is None:
            ball_type = self._pick_ball_type(diff)
        variance = random.uniform(-1.0, 1.0)
        ball = Ball(
            lane=lane,
            z_speed=self._z_speed(diff, variance),
            spawn_time=time.perf_counter(),
            ball_type=ball_type,
        )
        sx, sy = self.lane_system.screen_pos(lane, 0.0)
        ball.x, ball.y = sx, sy
        ball.radius = self.lane_system.ball_radius(0.0)
        return ball

    def spawn_ball(self, force_lane: int = None, force_type: str = None):
        diff = self.difficulty()
        lane = force_lane if force_lane is not None else random.randint(0, LaneSystem.LANE_COUNT - 1)
        ball = self._make_ball(lane, diff, force_type)
        self.balls.append(ball)

        # Multi-spawn: chaos — second ball in different lane, 25% at diff<3, 50% at diff>=3
        multi_chance = 0.50 if diff >= 3.0 else 0.25
        if random.random() < multi_chance and self.burst_cooldown <= 0:
            other_lanes = [l for l in range(LaneSystem.LANE_COUNT) if l != lane]
            lane2 = random.choice(other_lanes)
            ball2 = self._make_ball(lane2, diff)
            self.balls.append(ball2)
            self.burst_cooldown = 8  # prevent infinite cascade

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
        if self.rage_flash_frames > 0:
            self.rage_flash_frames -= 1
        if self.burst_cooldown > 0:
            self.burst_cooldown -= 1
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

        # Rage mode: activated at combo >= 8, disabled on combo break
        was_rage = self.rage_mode
        self.rage_mode = self.combo >= 8
        if self.rage_mode and not was_rage:
            self.rage_flash_frames = 30
            self._emit_audio("combo_up")

        # Combo decay: if no hit for 2.5s (150f), combo drops 1 per 90f
        self.combo_decay_timer += 1
        if self.combo_decay_timer > 150 and self.combo > 0:
            if self.combo_decay_timer % 90 == 0:
                self.combo = max(0, self.combo - 1)
                self.multiplier = 1 + (self.combo // 5)

        self.spawn_timer += 1
        diff = self.difficulty()
        spawn_interval = int(max(10, 44 - diff * 6))

        if self.spawn_timer > spawn_interval:
            self.spawn_ball()
            self.spawn_timer = 0

        for ball in self.balls:
            if getattr(ball, "_near_miss_cd", 0) > 0:
                ball._near_miss_cd -= 1
            ball.update()
            # Update screen-space position from z
            sx, sy = self.lane_system.screen_pos(ball.lane, ball.z)
            ball.x, ball.y = sx, sy
            ball.radius = self.lane_system.ball_radius(ball.z)

        self.check_collisions(hands)
        self._check_near_misses(hands)

        self.remove_offscreen_balls()
        self._tick_missions()

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

            # Only hittable once ball is visible and large enough (z >= 0.45)
            if ball.z < 0.45:
                remaining_balls.append(ball)
                continue

            for hand in hands:

                dx = ball.x - hand["x"]
                dy = ball.y - hand["y"]

                dist = math.sqrt(dx*dx + dy*dy)

                if dist < ball.radius + hand["radius"]:
                    btype = getattr(ball, "ball_type", "normal")
                    if btype == "bomb":
                        # Hitting a bomb = big punishment
                        self.lives_left -= 2
                        self.combo = 0
                        self.multiplier = 1
                        self.rage_mode = False
                        self.run_misses += 1
                        self._spawn_pop_burst(ball.x, ball.y, 1)
                        self.floating_texts.append({
                            "kind": "event",
                            "text": "BOMB! -2",
                            "x": float(ball.x),
                            "y": float(ball.y) - 10,
                            "vx": 0.0,
                            "vy": -1.2,
                            "life": 50,
                            "max_life": 50,
                            "color": (30, 30, 220),
                            "scale": 0.85,
                        })
                        self.shake_keyed = True
                        self.shake_frames = max(self.shake_frames, len(SHAKE_OFFSETS))
                        self.shake_strength = 1.0
                        self.life_loss_overlay_frames = max(self.life_loss_overlay_frames, DT.DUR_LIFE_LOSS_FLASH)
                        self.life_loss_anim_frames = max(self.life_loss_anim_frames, DT.DUR_HEART_LOSS_ANIM)
                        self._emit_audio("miss")
                        if self.lives_left <= 0:
                            self.game_over = True
                            self.session_summary = self._build_session_summary()
                            _save_best_score(self.best_score)
                            self._emit_audio("game_over")
                    elif btype == "health":
                        self.lives_left = min(self.lives_max, self.lives_left + 1)
                        self.run_health_pops += 1
                        self.juice_rim_frames = max(self.juice_rim_frames, 14)
                        self.quiet_frames = max(self.quiet_frames, 36)
                        self.shake_keyed = False
                        self.shake_frames = max(self.shake_frames, 6)
                        self.shake_strength = max(self.shake_strength, 1.4)
                        self._emit_audio("health")
                        self._spawn_pop_burst(ball.x, ball.y, self.combo)
                        self.spawn_confetti(ball.x, ball.y, self.multiplier, ball.color, burst_mult=0.18, preset="health")
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
                        # normal or gold
                        old_best = self.best_score
                        old_mult = self.multiplier
                        self.combo += 1
                        self.combo_decay_timer = 0  # reset decay on hit
                        self.run_pops += 1
                        self.run_best_combo = max(self.run_best_combo, self.combo)
                        self.multiplier = 1 + (self.combo // 5)
                        rage_mult = 2 if self.rage_mode else 1
                        base_pts = 3 if btype == "gold" else 1
                        pts = self.multiplier * base_pts * rage_mult
                        self.score += pts
                        self.combo_last_pop_frame = self.frame_count
                        self.combo_pulse_frames = DT.COMBO_PULSE_FRAMES
                        self._spawn_pop_burst(ball.x, ball.y, self.combo)
                        pop_col = DT.C_AMBER if (btype == "gold" or self.combo >= 3) else DT.C_WHITE
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

        for ball in self.balls:
            if ball.z < 1.05:
                remaining.append(ball)
                continue

            btype = getattr(ball, "ball_type", "normal")
            # Health and bomb balls don't cost a life when they pass
            if btype in ("health", "bomb"):
                continue

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

        self.balls = remaining

        if removed_any:
            self.combo = 0
            self.multiplier = 1
            self.rage_mode = False
            self.combo_decay_timer = 0