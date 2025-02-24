import random
from typing import Optional
import pygame
import os
import numpy as np
from stable_baselines3 import PPO
from mlgame.utils.enum import get_ai_name
import math
from src.env import BACKWARD_CMD, FORWARD_CMD, TURN_LEFT_CMD, TURN_RIGHT_CMD, SHOOT, AIM_LEFT_CMD, AIM_RIGHT_CMD
import random

WIDTH = 1000 # pixel
HEIGHT = 600 # pixel
TANK_SPEED = 8 # pixel
CELL_PIXEL_SIZE = 50 # pixel
DEGREES_PER_SEGMENT = 45 # degree

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # 上層資料夾
MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_AIM_PATH = os.path.join(MODEL_DIR, "aim_bad.zip")
MODEL_CHASE_PATH = os.path.join(MODEL_DIR, "chase_new.zip")

COMMAND_AIM = [
    ["NONE"],
    [AIM_LEFT_CMD],
    [AIM_RIGHT_CMD],
    [SHOOT],   
]

COMMAND_CHASE = [
    ["NONE"],
    [FORWARD_CMD],
    [BACKWARD_CMD],
    [TURN_LEFT_CMD],
    [TURN_RIGHT_CMD],
]

class MLPlay:
    def __init__(self, ai_name, *args, **kwargs):
        """
        Constructor

        @param side A string like "1P" or "2P" indicates which player the `MLPlay` is for.
        """
        self.side = ai_name
        print(f"Initial Game {ai_name} ML script")
        self.time = 0
        self.player: str = "1P"

        # Load the trained models
        self.model_aim = PPO.load(MODEL_AIM_PATH)
        self.model_chase = PPO.load(MODEL_CHASE_PATH)

        self.target_x = None
        self.target_y = None
        self.closest_competitor = None

    def update(self, scene_info: dict, keyboard=[], *args, **kwargs):
        """
        Generate the command according to the received scene information
        """
        self.player = scene_info["id"]
        if scene_info["status"] != "GAME_ALIVE":
            self.closest_competitor = None
            return "RESET"

        self._scene_info = scene_info
        self.target_x = WIDTH
        self.target_y = 100

        if self.closest_competitor is None:  # 如果還沒抓到敵人
            self.closest_competitor = min(  # 抓一個最近的
                scene_info["competitor_info"],
                key=lambda x: (scene_info["x"] - x["x"]) ** 2
                + (scene_info["y"] - x["y"]) ** 2,  # 算距離(我設平方因為我懶得開根號)
            )
            self.competitor_lives = self.closest_competitor["lives"]

        self.target_x = self.closest_competitor["x"]  # 敵人x座標
        self.target_y = -self.closest_competitor["y"]  # 敵人y座標
        # print(f"Target is : ({self.target_x, self.target_y})")

        if self.target_x is None or self.target_y is None:
            print("No valid target available.")
            return "RESET"

        dist = (abs(scene_info["x"]) - abs(self.target_x)) ** 2 + (
            abs(scene_info["y"]) - abs(self.target_y)
        ) ** 2
        # print(scene_info["x"])
        # print(scene_info["y"])
        # Randomly switch between model_aim and model_chase
        if dist < 295**2 and (
            abs(scene_info["x"] - self.target_x) <= 5
            or abs(scene_info["y"] - abs(self.target_y)) <= 5
        ):
            obs = self._get_obs_aim()
            action, _ = self.model_aim.predict(obs, deterministic=True)
            command = COMMAND_AIM[action]
            # for tm in scene_info["competitor_info"]:
            #     if (
            #         tm["y"] == scene_info["y"] and abs(tm["x"] - scene_info["x"])
            #     ) < abs(self.closest_competitor["x"] - scene_info["x"]):
            #         command = [FORWARD_CMD]
            #     else:
            # command = [SHOOT]
            self.competitor_lives -= 1
            # print(self.competitor_lives)
            if self.competitor_lives == 0:
                self.closest_competitor = None
            # print(dist**0.5)
        elif dist < 295**2:
            if scene_info["y"] - abs(self.target_y) > 0:
                if scene_info["angle"] != 270:
                    command = [TURN_RIGHT_CMD]
                else:
                    command = [FORWARD_CMD]
            elif scene_info["y"] - abs(self.target_y) < 0:
                if scene_info["angle"] != 90:
                    command = [TURN_RIGHT_CMD]
                else:
                    command = [FORWARD_CMD]
            else:
                if scene_info["angle"] != 0:
                    command = [TURN_LEFT_CMD]
                else:
                    command = [FORWARD_CMD]
            # self.target_x = scene_info["x"]
            # obs = self._get_obs_chase()
            # action, _ = self.model_chase.predict(obs, deterministic=True)
            # command = COMMAND_CHASE[action]
        else:
            # command = ["NONE"]
            obs = self._get_obs_chase()
            action, _ = self.model_chase.predict(obs, deterministic=True)
            command = COMMAND_CHASE[action]
            # print(dist**0.5)

        # print(f"Target is : ({self.target_x, self.target_y})")
        # print(f"Predicted action: {command}")
        self.time += 1
        return command
    
    def reset(self):
        """
        Reset the status
        """
        print(f"Resetting Game {self.side}")

    def get_obs_chase(self, player: str, target_x: int, target_y: int, scene_info: dict) -> np.ndarray:
        player_x = scene_info.get("x", 0)
        player_y = -scene_info.get("y", 0)
        tank_angle = scene_info.get("angle", 0) + 180
        tank_angle_index: int = self._angle_to_index(tank_angle)
        dx = target_x - player_x
        dy = target_y - player_y
        angle_to_target = math.degrees(math.atan2(dy, dx))
        angle_to_target_index: int = self._angle_to_index(angle_to_target)
        obs = np.array([float(tank_angle_index), float(angle_to_target_index)], dtype=np.float32)
        print("Chase obs: " + str(obs))
        return obs

    def get_obs_aim(self, player: str, target_x: int, target_y: int, scene_info: dict) -> np.ndarray:
        player_x = scene_info.get("x", 0)
        player_y = -scene_info.get("y", 0)
        gun_angle = scene_info.get("gun_angle", 0) + scene_info.get("angle", 0) + 180
        gun_angle_index: int = self._angle_to_index(gun_angle)
        dx = target_x - player_x
        dy = target_y - player_y 
        angle_to_target = math.degrees(math.atan2(dy, dx))
        angle_to_target_index: int = self._angle_to_index(angle_to_target)
        print("Aim angle: " + str(angle_to_target))
        obs = np.array([float(gun_angle_index), float(angle_to_target_index)], dtype=np.float32)
        return obs

    def _get_obs_chase(self) -> np.ndarray:
        return self.get_obs_chase(
            self.player,
            self.target_x,
            self.target_y,
            self._scene_info,
        )

    def _get_obs_aim(self) -> np.ndarray:
        return self.get_obs_aim(
            self.player,
            self.target_x,
            self.target_y,
            self._scene_info,
        )

    def _angle_to_index(self, angle: float) -> int:
        angle = (angle + 360) % 360

        segment_center = (angle + DEGREES_PER_SEGMENT/2) // DEGREES_PER_SEGMENT
        return int(segment_center % (360 // DEGREES_PER_SEGMENT))
