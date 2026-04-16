---
name: Hand_controlled_game vision
description: Target design direction and creator's pain points for the hand-tracking game
type: project
---

Project is a webcam/MediaPipe hand-tracking arcade game (balls fly in from edges, pop with hands). Creator wants to evolve it toward a Subway-Surfers-level experience.

**Why:** Creator explicitly said the current game is "slow" and "I don't even like playing it." The game is currently tuned for accessibility over excitement — `_BALL_SPEED_SCALE = 0.68`, `min_ball_visible_seconds = 0.6s`, fairness-bounce keeping balls onscreen, difficulty caps at 3.3x. Every design choice pads the player.

**How to apply:** When proposing changes, lean toward FUN + CHALLENGING. The baseline should feel fast and punishing; accessibility comes from juice/feedback, not from slowing the game. Do not suggest "make it easier" fixes. Tension, tempo, and skill expression beat fairness.
