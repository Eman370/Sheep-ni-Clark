#!/usr/bin/env python3
"""The Shepherd's Pasture - Python-owned game engine + offline browser renderer.

The game uses Python's standard library only. The browser canvas is a presentation
layer; game state, collisions, progression, enemy AI, and endings live in Python.
"""
from __future__ import annotations

import json
import math
import os
import random
import socket
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SAVE_FILE = ROOT / "save.json"
HOST = "0.0.0.0"
PORT = 8765
WORLD_W = 3200
WORLD_H = 2200
PLAYER_SIZE = 54

DIRECTION_VECTORS = {
    "up": (0.0, -1.0), "down": (0.0, 1.0),
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
}

EDEN_LORE = '“The Lord is my shepherd; I shall not want. He maketh me to lie down in green pastures...”'
EDEN_WHISPERS = [
    "Why do you stand so still? The eastern tree is watching.",
    "Something is breathing beneath the soil.",
    "You are not alone in the pasture.",
    "Do not look too long at the shadows.",
    "He knows you are hesitating.",
]
ABYSS_WHISPERS = [
    "IT SEES YOU STANDING THERE.", "YOUR FOOTSTEPS ECHO IN THE DARK.",
    "THE PIT DOES NOT FORGIVE STILLNESS.", "DO NOT LET IT OUT OF YOUR SIGHT.",
]
ABYSS_LORE = [
    "GENESIS 3:24 — The garden has closed its gates.",
    "EZEKIEL 1:18 — The rings are full of eyes. They never blink.",
    "JOB 26:6 — The dark has no covering.",
    "REVELATION 9:11 — Something waits beneath the roots.",
    "MATTHEW 8:12 — There is no path through the outer darkness.",
    "THE SIXTH SEAL SHATTERS. ONE REMAINS.",
    "REVELATION 8:1 — The silence is almost complete.",
    "ISAIAH 14:15 — The deepest part of the pit remembers you.",
    "THE THRONE IS EMPTY. THE EXIT IS OPEN.",
]
SEAL_ENTRIES = [
    "Seal I [Genesis 3:24]: The expulsion protocol. The path back is barred.",
    "Seal II [Ezekiel 1:18]: A thousand eyes turn in the dark.",
    "Seal III [Job 26:6]: The pit has no bottom that you can see.",
    "Seal IV [Revelation 9:11]: The keeper beneath the world has awakened.",
    "Seal V [Matthew 8:12]: The outer darkness has learned your name.",
    "Seal VI [The Scroll]: The sky folds inward like parchment.",
    "Seal VII [Revelation 8:1]: Heaven holds its breath.",
    "Seal VIII [Isaiah 14:15]: The final stair descends into nothing.",
    "Seal IX [Root Core]: The throne can be reached.",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


class GameEngine:
    """Authoritative simulation. Browser sends input; this class owns game rules."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.rng = random.Random(20261123)
        self.save = self._load_save()
        self.trees = self._make_forest()
        self.anomaly = {"x": 2820.0, "y": 1130.0, "width": 205.0, "height": 250.0}
        self.reset_game(first=True)

    def _load_save(self) -> dict:
        default = {
            "endings": {"eden": False, "death": False, "revelation": False, "trueEnd": False},
            "seals_total": 0,
            "watcher_defeated": False,
            "god_mode": False,
        }
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            default["endings"].update(data.get("endings", {}))
            default["seals_total"] = int(data.get("seals_total", 0))
            default["watcher_defeated"] = bool(data.get("watcher_defeated", False))
            default["god_mode"] = bool(data.get("god_mode", False))
        except (OSError, ValueError, TypeError):
            pass
        return default

    def _save(self) -> None:
        try:
            SAVE_FILE.write_text(json.dumps(self.save, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _make_forest(self) -> list[dict]:
        rng = random.Random(1812)
        variants = ["Tree Sprite 1.png", "Tree Sprite 2.png", "Tree Sprite 3.png"]
        trees: list[dict] = []
        # A clear starting patch, then a layered woodland around the wider map.
        fixed = [
            (760, 640, 1), (1010, 500, 2), (1260, 720, 0), (1550, 570, 1),
            (1860, 780, 2), (2200, 610, 0), (2480, 800, 1), (600, 1240, 2),
            (920, 1510, 0), (1240, 1320, 1), (1590, 1540, 2), (1950, 1280, 0),
            (2280, 1510, 1), (2640, 1360, 2), (700, 1850, 0), (1150, 1900, 2),
            (1720, 1870, 1), (2300, 1900, 0), (2800, 1830, 2),
        ]
        for x, y, variant in fixed:
            scale = rng.uniform(0.82, 1.12)
            widths = [170, 128, 152]
            heights = [252, 228, 216]
            trees.append({
                "x": float(x), "y": float(y), "width": widths[variant] * scale,
                "height": heights[variant] * scale, "sprite": variants[variant],
                "id": len(trees), "depth": "near" if y > 1100 else "mid",
            })
        # Fill out the map with varied tree silhouettes.
        attempts = 0
        while len(trees) < 48 and attempts < 600:
            attempts += 1
            x = rng.randint(150, WORLD_W - 150)
            y = rng.randint(180, WORLD_H - 100)
            if distance(x, y, 300, 1100) < 300 or distance(x, y, 2820, 1130) < 180:
                continue
            if any(distance(x, y, t["x"], t["y"]) < 155 for t in trees):
                continue
            variant = rng.randrange(3)
            scale = rng.uniform(0.7, 1.15)
            widths = [170, 128, 152]
            heights = [252, 228, 216]
            trees.append({
                "x": float(x), "y": float(y), "width": widths[variant] * scale,
                "height": heights[variant] * scale, "sprite": variants[variant],
                "id": len(trees), "depth": "far" if y < 620 else ("near" if y > 1250 else "mid"),
            })
        # The eastern anomaly is an actual tree sprite, not a placeholder shape.
        trees.append({
            "x": 2820.0, "y": 1130.0, "width": 220.0, "height": 285.0,
            "sprite": "Haunted Tree.png", "id": len(trees), "depth": "near",
            "anomaly": True,
        })
        return trees

    def _all_base_endings(self) -> bool:
        ends = self.save["endings"]
        return bool(ends["eden"] and ends["death"] and ends["revelation"])

    def _record_ending(self, key: str) -> None:
        self.save["endings"][key] = True
        self._save()

    def _event(self, name: str, **details) -> None:
        self.events.append({"name": name, **details})

    def _safe_spawn(self, near_player: bool = True) -> tuple[float, float]:
        for _ in range(120):
            if near_player:
                x = clamp(self.player["x"] + self.rng.uniform(-560, 560), 100, WORLD_W - 100)
                y = clamp(self.player["y"] + self.rng.uniform(-390, 390), 100, WORLD_H - 100)
            else:
                x = self.rng.uniform(150, WORLD_W - 150)
                y = self.rng.uniform(150, WORLD_H - 150)
            if distance(x, y, self.player["x"], self.player["y"]) < 180:
                continue
            if self._blocked(x, y, 20):
                continue
            if self.realm != "eden" and not self.save["watcher_defeated"]:
                if distance(x, y, self.monster["x"], self.monster["y"]) < 260:
                    continue
            return x, y
        return self.player["x"] + 260, self.player["y"] - 140

    def _blocked(self, x: float, y: float, radius: float) -> bool:
        for tree in self.trees:
            # Only trunks and roots block movement; the canopy is visual depth.
            tx = tree["x"]
            ty = tree["y"] - tree["height"] * 0.12
            tw = tree["width"] * 0.17
            th = tree["height"] * 0.22
            if (tx - tw / 2 - radius < x < tx + tw / 2 + radius and
                    ty - th / 2 - radius < y < ty + th / 2 + radius):
                return True
        return False

    def _spawn_item(self) -> None:
        self.item["x"], self.item["y"] = self._safe_spawn(near_player=True)
        self.item["active"] = True

    def reset_game(self, first: bool = False) -> None:
        self.realm = "eden"
        self.started = bool(first is False)
        self.game_over = False
        self.end_reason = ""
        self.eden_won = False
        self.won = False
        self.true_won = False
        self.score = 0
        self.eyes_collected = 0
        self.target_seals = 6
        self.anomaly_touches = 0
        self.anomaly_cooldown = 0.0
        self.flicker_timer = 0.0
        self.glitch_clock = 0.0
        self.whisper_timer = 0.0
        self.whisper_text = ""
        self.lore = EDEN_LORE
        self.is_whispering = False
        self.god_mode = bool(self.save.get("god_mode", False))
        self.player_speed = 255.0
        self.player = {
            "x": 300.0, "y": 1110.0, "size": PLAYER_SIZE,
            "dir": "down", "moving": False, "anim": 0.0,
        }
        self.item = {"x": 590.0, "y": 1050.0, "active": True}
        self.forbidden_fruit = {
            "x": self.anomaly["x"] - 100, "y": self.anomaly["y"] + 130,
            "active": self._all_base_endings() and not self.save["watcher_defeated"],
        }
        self.monster = {
            "x": 2500.0, "y": 800.0, "size": 150.0,
            "speed": 82.0, "observed": False, "hidden": True, "hide_tree_id": None,
            "last_known_x": 300.0, "last_known_y": 1110.0,
        }
        self.portal = {"x": WORLD_W - 210.0, "y": WORLD_H - 260.0, "active": False}
        self.jumpscare_timer = 0.0
        self.jumpscare_started = False
        self.still_timer = 0.0
        self.last_move = (self.player["x"], self.player["y"])
        self.events: list[dict] = []
        self._spawn_item()
        if not first:
            self._event("restart")

    def _start_dimension(self, realm: str) -> None:
        self.realm = realm
        self.game_over = False
        self.end_reason = ""
        self.eden_won = False
        self.won = False
        self.true_won = False
        self.score = 0
        self.eyes_collected = 0
        self.target_seals = 9 if realm == "pit" else 6
        self.lore = (
            "YOU HAVE CROSSED THE ROOT. THE DARK IS NOT EMPTY."
            if realm == "pit" else
            "YOU TOUCHED THE FORBIDDEN ROOT. THE SKY HAS ROLLED UP LIKE A SCROLL."
        )
        self.player.update({"x": 260.0, "y": 1110.0, "dir": "right", "moving": False, "anim": 0.0})
        self.monster.update({
            "x": 2500.0, "y": 800.0, "speed": 82.0,
            "last_known_x": self.player["x"], "last_known_y": self.player["y"],
            "observed": False, "hidden": True, "hide_tree_id": None,
        })
        self.portal = {"x": WORLD_W - 210.0, "y": WORLD_H - 260.0, "active": False}
        self.jumpscare_timer = 0.0
        self.jumpscare_started = False
        self._spawn_item()
        self._event("dimension_transition", realm=realm)

    def _trigger_jumpscare(self) -> None:
        if self.jumpscare_started or self.god_mode or self.save["watcher_defeated"]:
            return
        self.jumpscare_started = True
        self.jumpscare_timer = 1.25
        self.player["moving"] = False
        self._event("jumpscare")
        self.lore = "IT FOUND YOU."

    def _finish_death(self) -> None:
        self.game_over = True
        self.end_reason = "death"
        self.won = False
        self._record_ending("death")
        self._event("death")

    def _move_player(self, keys: set[str], dt: float) -> None:
        dx = (1 if ("d" in keys or "arrowright" in keys) else 0) - (1 if ("a" in keys or "arrowleft" in keys) else 0)
        dy = (1 if ("s" in keys or "arrowdown" in keys) else 0) - (1 if ("w" in keys or "arrowup" in keys) else 0)
        moving = bool(dx or dy)
        self.player["moving"] = moving
        if not moving:
            return
        mag = math.hypot(dx, dy)
        dx, dy = dx / mag, dy / mag
        if abs(dx) > abs(dy):
            self.player["dir"] = "right" if dx > 0 else "left"
        else:
            self.player["dir"] = "down" if dy > 0 else "up"
        self.player["anim"] += dt * 10.0
        speed = self.player_speed if self.realm == "eden" else self.player_speed * 0.92
        radius = 18.0
        next_x = clamp(self.player["x"] + dx * speed * dt, radius, WORLD_W - radius)
        if self.realm != "eden" or not self._blocked(next_x, self.player["y"], radius):
            self.player["x"] = next_x
        next_y = clamp(self.player["y"] + dy * speed * dt, radius, WORLD_H - radius)
        if self.realm != "eden" or not self._blocked(self.player["x"], next_y, radius):
            self.player["y"] = next_y

    def _player_looks_at_monster(self, dist: float) -> bool:
        if dist > 610:
            return False
        vx = self.monster["x"] - self.player["x"]
        vy = self.monster["y"] - self.player["y"]
        length = math.hypot(vx, vy) or 1.0
        facing = DIRECTION_VECTORS.get(self.player["dir"], (0.0, 1.0))
        dot = (vx / length) * facing[0] + (vy / length) * facing[1]
        return dot > 0.85

    def _update_monster(self, dt: float) -> None:
        if self.realm == "eden" or self.save["watcher_defeated"] or self.game_over:
            return
        if self.jumpscare_started:
            self.jumpscare_timer -= dt
            if self.jumpscare_timer <= 0:
                self._finish_death()
            return
        px, py = self.player["x"], self.player["y"]
        dx, dy = px - self.monster["x"], py - self.monster["y"]
        dist = math.hypot(dx, dy) or 1.0
        observed = self._player_looks_at_monster(dist)
        self.monster["observed"] = observed
        self.monster["last_known_x"] = px
        self.monster["last_known_y"] = py

        # It tries to stay behind a nearby tree, then moves when the sheep looks away.
        candidates = [t for t in self.trees if not t.get("anomaly") and distance(
            self.monster["x"], self.monster["y"], t["x"], t["y"] - t["height"] * .12
        ) < 300]
        if candidates:
            cover = min(candidates, key=lambda t: distance(
                self.monster["x"], self.monster["y"], t["x"], t["y"] - t["height"] * .12
            ))
            self.monster["hide_tree_id"] = cover["id"]
        else:
            cover = next((t for t in self.trees if t["id"] == self.monster.get("hide_tree_id")), None)
        self.monster["hidden"] = bool(cover and not observed and distance(
            self.monster["x"], self.monster["y"], cover["x"], cover["y"] - cover["height"] * .12
        ) < 245)

        if observed:
            # It freezes when directly illuminated; it does not rush the player.
            move_x, move_y = dx / dist, dy / dist
            speed = 1.0
        else:
            speed = self.monster["speed"] * (1.12 if self.realm == "pit" else 1.0)
            orbit = math.sin(self.glitch_clock * 0.55) * 0.22
            ndx, ndy = dx / dist, dy / dist
            move_x, move_y = ndx - ndy * orbit, ndy + ndx * orbit
            norm = math.hypot(move_x, move_y) or 1.0
            move_x, move_y = move_x / norm, move_y / norm
            if dist < 180:
                speed *= 0.5
        self.monster["x"] = clamp(self.monster["x"] + move_x * speed * dt, 55, WORLD_W - 55)
        self.monster["y"] = clamp(self.monster["y"] + move_y * speed * dt, 55, WORLD_H - 55)
        new_dist = distance(px, py, self.monster["x"], self.monster["y"])

        # A close approach to either the creature or its hiding tree triggers the scare.
        cover = next((t for t in self.trees if t["id"] == self.monster.get("hide_tree_id")), None)
        near_cover = bool(self.monster.get("hidden") and cover and distance(px, py, cover["x"], cover["y"] - cover["height"] * .10) < 118)
        if new_dist < 138 or near_cover:
            self._trigger_jumpscare()

    def _collect_item(self) -> None:
        if not self.item["active"] or distance(
            self.player["x"], self.player["y"], self.item["x"], self.item["y"]
        ) > 52:
            return
        self.item["active"] = False
        if self.realm == "eden":
            self.score += 1
            self._event("collect_fruit", count=self.score)
            if self.score == 5:
                self.lore = "Deep in the woods, the shadows grow long. Something stirs near the eastern tree."
            elif self.score == 12:
                self.lore = "You keep to the harvest. The distant branches are no longer still."
            if self.score >= 20:
                self.game_over = True
                self.eden_won = True
                self.end_reason = "eden"
                self._record_ending("eden")
                self.lore = "MATTHEW 25:21 — WELL DONE, GOOD AND FAITHFUL SERVANT."
                self._event("ending", ending="eden")
            else:
                self._spawn_item()
        else:
            self.eyes_collected += 1
            self.save["seals_total"] += 1
            self._save()
            self._event("collect_seal", count=self.eyes_collected)
            self.lore = ABYSS_LORE[min(self.eyes_collected - 1, len(ABYSS_LORE) - 1)]
            self.monster["speed"] = min(112.0, self.monster["speed"] + 3.0)
            if self.eyes_collected >= self.target_seals:
                if self.realm == "abyss":
                    self.game_over = True
                    self.won = True
                    self.end_reason = "revelation"
                    self._record_ending("revelation")
                    self.lore = "BE NOT AFRAID. YOU HAVE SURVIVED THE REVELATION."
                    self._event("ending", ending="revelation")
                else:
                    self.portal["active"] = True
                    self.lore = "THE NINTH SEAL BREAKS. THE ROOT GATE IS OPEN. REACH IT."
                    self._event("portal_open")
            else:
                self._spawn_item()

    def _update_anomaly(self, dt: float) -> None:
        if self.realm != "eden" or self.game_over:
            return
        self.anomaly_cooldown = max(0.0, self.anomaly_cooldown - dt)
        if distance(self.player["x"], self.player["y"], self.anomaly["x"], self.anomaly["y"] + 35) < 100:
            if self.anomaly_cooldown <= 0:
                self.anomaly_touches += 1
                self.anomaly_cooldown = 2.2
                self._event("anomaly_touch", count=self.anomaly_touches)
                lines = [
                    "The bark is unnaturally cold to the touch...",
                    "A dark drop of sap slides down the grain. Something is wrong.",
                    "You hear faint whispers echoing up through the roots. Turn back.",
                ]
                if self.anomaly_touches < 3:
                    self.lore = lines[min(self.anomaly_touches - 1, 2)]
                else:
                    self._start_dimension("abyss")

    def _update_forbidden_fruit(self) -> None:
        self.forbidden_fruit["active"] = self._all_base_endings() and not self.save["watcher_defeated"]
        if not self.forbidden_fruit["active"] or self.realm != "eden" or self.game_over:
            return
        if distance(self.player["x"], self.player["y"], self.forbidden_fruit["x"], self.forbidden_fruit["y"]) < 58:
            self._start_dimension("pit")

    def _build_codex(self) -> str:
        ends = self.save["endings"]
        rows = [
            "============================================",
            "       TORN MANUSCRIPT OF THE ARCHIVES      ",
            "============================================\n",
            "[ REALM I: EDEN'S GROVE // THE PASTORAL SANDBOX ]",
        ]
        if ends["eden"]:
            rows.append("The harvest is complete. The garden was a quiet cage woven from grass and silence.")
        else:
            rows.append("[Blank parchment. Gather 20 fruits in Eden to reveal this chapter.]")
        rows += ["", "[ REALM II: SHEOL // THE ABYSS ]"]
        if ends["death"] or ends["revelation"] or self.save["seals_total"]:
            rows.append("The green illusion falls away. The Watcher waits beyond the reach of the light.")
            rows.append(f"--- EXCAVATED SEALS ({min(self.save['seals_total'], 9)}/9) ---")
            for i, entry in enumerate(SEAL_ENTRIES):
                rows.append(f" - {entry}" if self.save["seals_total"] > i else f" - Seal {i+1}: [Still buried in the dark.]")
        else:
            rows.append("[The text is charred. Enter the Abyss to reveal its secrets.]")
        rows += ["", "[ REALM III: THE BOTTOMLESS PIT ]"]
        if ends["trueEnd"] or self.save["seals_total"] > 6:
            rows.append("The deepest layer. Nine seals open the root gate, but the Watcher has not left.")
        else:
            rows.append("[Sealed. Unlock the three base endings to find the crimson fruit.]")
        if ends["trueEnd"]:
            rows += ["", "[ REALM IV: THE EIGHTH DAY // THE CROWN ]", "The root gate has been crossed. The simulation no longer owns you."]
        return "\n".join(rows)

    def _command(self, command: str) -> str:
        parts = command.strip().lower().split()
        if not parts:
            return ""
        cmd = parts[0]
        if cmd == "help":
            return "COMMANDS: help, reset, revive, crown, abyss, trueabyss, unlockall, godmode, speed <1-1000>, teleport, clear"
        if cmd == "reset":
            self.save = {"endings": {"eden": False, "death": False, "revelation": False, "trueEnd": False}, "seals_total": 0, "watcher_defeated": False, "god_mode": False}
            self._save()
            self.reset_game()
            return "All endings cleared. The Watcher has returned."
        if cmd == "revive":
            self.save["watcher_defeated"] = False
            self.save["endings"]["trueEnd"] = False
            self._save()
            self.reset_game()
            return "The Watcher has been restored."
        if cmd in ("abyss", "trueabyss"):
            self._start_dimension("abyss" if cmd == "abyss" or self.save["watcher_defeated"] else "pit")
            return "Forced entry into " + self.realm.upper() + "."
        if cmd == "unlockall":
            for k in ("eden", "death", "revelation"):
                self.save["endings"][k] = True
            self.save["seals_total"] = max(6, self.save["seals_total"])
            self._save()
            self.forbidden_fruit["active"] = not self.save["watcher_defeated"]
            return "The three base endings are unlocked. The crimson fruit has appeared."
        if cmd == "godmode":
            self.god_mode = not self.god_mode
            self.save["god_mode"] = self.god_mode
            self._save()
            return f"God mode {'enabled' if self.god_mode else 'disabled'}."
        if cmd == "speed" and len(parts) > 1:
            try:
                self.player_speed = clamp(float(parts[1]), 1, 1000)
                return f"Player speed set to {self.player_speed:g}."
            except ValueError:
                return "Usage: speed <number between 1 and 1000>."
        if cmd == "teleport":
            x, y = self._safe_spawn(near_player=False)
            self.player["x"], self.player["y"] = x, y
            return f"Teleported to {int(x)}, {int(y)}."
        if cmd == "crown":
            self.save["endings"]["trueEnd"] = not self.save["endings"]["trueEnd"]
            self._save()
            return "Crown state toggled."
        if cmd == "clear":
            return "__CLEAR__"
        return f"Unknown command: {cmd}. Type help."

    def tick(self, payload: dict) -> dict:
        with self.lock:
            self.events = []
            keys = {str(k).lower() for k in payload.get("keys", [])}
            dt = clamp(float(payload.get("dt", 1 / 30)), 0.005, 0.075)
            actions = payload.get("actions", [])
            if isinstance(actions, str):
                actions = [actions]
            for action in actions:
                if action == "start":
                    self.started = True
                elif action == "restart":
                    self.reset_game()
                    self.started = True
                elif isinstance(action, dict) and action.get("command"):
                    message = self._command(str(action["command"]))
                    self._event("console", message=message)
            if not self.started:
                return self.state()
            if self.game_over:
                return self.state()
            if payload.get("paused"):
                return self.state()

            self.glitch_clock += dt
            self.flicker_timer = max(0.0, self.flicker_timer - dt)
            if self.jumpscare_started:
                self._update_monster(dt)
                return self.state()

            self._move_player(keys, dt)
            if not self.player["moving"]:
                self.still_timer += dt
                if self.still_timer > 11.0 and not self.is_whispering:
                    self.is_whispering = True
                    self.whisper_text = self.rng.choice(ABYSS_WHISPERS if self.realm != "eden" else EDEN_WHISPERS)
                    self.lore = self.whisper_text
            else:
                self.still_timer = 0.0
                self.is_whispering = False

            self._update_anomaly(dt)
            self._update_forbidden_fruit()
            if not self.game_over and not self.jumpscare_started:
                self._collect_item()
            if self.realm != "eden" and not self.game_over:
                self._update_monster(dt)
            if self.realm == "pit" and self.portal["active"] and distance(
                self.player["x"], self.player["y"], self.portal["x"], self.portal["y"]
            ) < 94:
                self.game_over = True
                self.true_won = True
                self.end_reason = "trueEnd"
                self.save["watcher_defeated"] = True
                self.save["endings"]["trueEnd"] = True
                self._save()
                self.lore = "THE EIGHTH DAY. ROOT ACCESS GRANTED."
                self._event("ending", ending="trueEnd")
            return self.state()

    def state(self) -> dict:
        with self.lock:
            return {
                "started": self.started,
                "realm": self.realm,
                "world": {"width": WORLD_W, "height": WORLD_H},
                "player": dict(self.player),
                "trees": self.trees,
                "anomaly": self.anomaly,
                "item": dict(self.item),
                "forbiddenFruit": dict(self.forbidden_fruit),
                "monster": dict(self.monster),
                "monsterHideTreeId": self.monster.get("hide_tree_id"),
                "portal": dict(self.portal),
                "score": self.score,
                "eyesCollected": self.eyes_collected,
                "targetSeals": self.target_seals,
                "baseEndings": dict(self.save["endings"]),
                "allBaseEndings": self._all_base_endings(),
                "watcherDefeated": self.save["watcher_defeated"],
                "sealsTotal": self.save["seals_total"],
                "godMode": self.god_mode,
                "gameOver": self.game_over,
                "endReason": self.end_reason,
                "edenWon": self.eden_won,
                "won": self.won,
                "trueWon": self.true_won,
                "lore": self.lore,
                "codex": self._build_codex(),
                "jumpscare": self.jumpscare_started,
                "jumpscareTimer": self.jumpscare_timer,
                "events": list(self.events),
            }


ENGINE = GameEngine()


class GameRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        # Keep the console readable while the browser polls the local game.
        if self.path.startswith("/api"):
            return
        super().log_message(fmt, *args)

    def _send_json(self, data: dict, status: int = 200):
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/state":
            self._send_json(ENGINE.state())
            return
        if path == "/health":
            self._send_json({"ok": True, "engine": "python"})
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if path == "/api/tick":
                self._send_json(ENGINE.tick(payload))
            elif path == "/api/command":
                with ENGINE.lock:
                    message = ENGINE._command(str(payload.get("command", "")))
                    self._send_json({"message": message, "state": ENGINE.state()})
            else:
                self._send_json({"error": "Not found"}, 404)
        except (ValueError, TypeError, KeyError) as exc:
            self._send_json({"error": str(exc)}, 400)
        except BrokenPipeError:
            pass


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main() -> None:
    server = None
    port = PORT
    for candidate in range(PORT, PORT + 20):
        try:
            server = ThreadingHTTPServer((HOST, candidate), GameRequestHandler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        print("Could not find an available local port (8765-8794).")
        input("Press Enter to close...")
        return
    server.daemon_threads = True
    local = local_ip()
    print("\n==============================================")
    print("       THE SHEPHERD'S PASTURE")
    print("==============================================")
    print("Python game engine: ONLINE")
    print("Dependencies: Python standard library only")
    print(f"This computer: http://127.0.0.1:{port}")
    print(f"Phone / tablet on the same Wi-Fi: http://{local}:{port}")
    print("Keep this window open while playing.")
    print("Press Ctrl+C to stop the game server.\n")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nClosing the game server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
