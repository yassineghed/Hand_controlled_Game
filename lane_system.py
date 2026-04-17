"""Perspective projection for the 3-lane runner."""


class LaneSystem:
    LANE_COUNT = 3

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.vp_x = float(width) / 2.0
        self.vp_y = float(height) * 0.33
        self.player_y = float(height) * 0.92
        self.lane_x_near = [
            float(width) * 0.22,
            float(width) * 0.50,
            float(width) * 0.78,
        ]

    def screen_pos(self, lane: int, z: float):
        sx = self.vp_x + (self.lane_x_near[lane] - self.vp_x) * z
        sy = self.vp_y + (self.player_y - self.vp_y) * z
        return float(sx), float(sy)

    def ball_radius(self, z: float) -> int:
        return max(3, int(4 + 58 * (z ** 1.2)))

    def hand_lane(self, hx: float) -> int:
        w3 = self.width / 3.0
        if hx < w3:
            return 0
        if hx < w3 * 2:
            return 1
        return 2

    def info_dict(self) -> dict:
        return {
            "vp_x": self.vp_x,
            "vp_y": self.vp_y,
            "player_y": self.player_y,
            "lane_x_near": self.lane_x_near,
            "width": self.width,
            "height": self.height,
        }
