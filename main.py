import os
import sys
import random
import math
import socket
import threading
import json
from dataclasses import dataclass
from enum import Enum

import pygame

# ============================================================
# Heartbeat Devil — Pixel Art + Parallax + Longer Levels + Live Biometrics
# - Mode 1: Heart Rate (BPM) -> Difficulty
# - Mode 2: Facial Emotion -> Difficulty
# ============================================================

# ----------------------------
# CONFIG
# ----------------------------
WIDTH, HEIGHT = 1000, 600
FPS = 60

# ✅ Your absolute assets folder (Windows)
# If this path doesn't exist on another machine, it falls back to local "./assets".
ABS_ASSETS_DIR = r"C:\Users\sasuke rawal\Desktop\heartbeat_devil\Capstone-Project\assets"
ASSETS_DIR = ABS_ASSETS_DIR if os.path.isdir(ABS_ASSETS_DIR) else "assets"

# ----------------------------
# LIVE UDP CONFIG (Handles both BPM numbers and Emotion strings)
# ----------------------------
USE_LIVE_UDP = True       # set False to disable UDP listening
UDP_BIND_IP = "0.0.0.0"   # listen on all interfaces
UDP_PORT = 5005           # your phone app must send to this port
UDP_TIMEOUT = 0.2         # seconds

# ----------------------------
# Player / art
# ----------------------------
PLAYER_PATH = os.path.join(ASSETS_DIR, "player", "player.png")

# Optional animation sheets
PLAYER_IDLE_PATH = os.path.join(ASSETS_DIR, "player", "player_idle.png")
PLAYER_RUN_PATH  = os.path.join(ASSETS_DIR, "player", "player_run.png")
PLAYER_JUMP_PATH = os.path.join(ASSETS_DIR, "player", "player_jump.png")
PLAYER_SHEET_FRAME = 256  

# Tilesets
TILE_SIZE = 32
TILES_GRASS = os.path.join(ASSETS_DIR, "tiles", "grass_tileset.png")
TILES_STONE = os.path.join(ASSETS_DIR, "tiles", "stone_tileset.png")
TILES_INDUSTRIAL = os.path.join(ASSETS_DIR, "tiles", "industrial_tileset.png")

# Traps
SPIKES_SHEET = os.path.join(ASSETS_DIR, "traps", "spikes.png")
LASER_TEX = os.path.join(ASSETS_DIR, "traps", "laser.png")
FALLING_BLOCK_SHEET = os.path.join(ASSETS_DIR, "traps", "falling_block.png")
SHIFTING_WALL_TEX = os.path.join(ASSETS_DIR, "traps", "moving_platform.png")

# Door sprite
DOOR_SPRITE = os.path.join(ASSETS_DIR, "props", "door.png")

# Parallax backgrounds
BG_LAYERS = {
    1: (
        os.path.join(ASSETS_DIR, "backgrounds", "level1_back.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level1_mid.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level1_front.png"),
    ),
    2: (
        os.path.join(ASSETS_DIR, "backgrounds", "level2_back.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level2_mid.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level2_front.png"),
    ),
    3: (
        os.path.join(ASSETS_DIR, "backgrounds", "level3_back.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level3_mid.png"),
        os.path.join(ASSETS_DIR, "backgrounds", "level3_front.png"),
    ),
}

# ----------------------------
# Gameplay Constants
# ----------------------------
GRAVITY = 2400.0
BASE_MOVE_SPEED = 380.0
BASE_JUMP_VEL = -850.0

STRESS_DELTA = 10
PANIC_DELTA = 20

STRESS_SPEED_MULT = 0.78
STRESS_JUMP_MULT = 0.86

PANIC_RADIUS = 185

FLASH_DURATION = 20.0
FLASH_SPEED_MULT = 1.6

INPUT_SWAP_DURATION = 3.0
JUMP_SWAP_DURATION = 3.0

PLAYER_SIZE = 40
RESPAWN_I_FRAMES = 0.8 

KEY_LEFT = (pygame.K_a, pygame.K_LEFT)
KEY_RIGHT = (pygame.K_d, pygame.K_RIGHT)
KEY_JUMP = (pygame.K_SPACE, pygame.K_w, pygame.K_UP)

KEY_FORCE_STRESS = pygame.K_i
KEY_FORCE_PANIC = pygame.K_o
KEY_FORCE_AUTO = pygame.K_u

KEY_FLASH = pygame.K_q
KEY_RESPAWN = pygame.K_r

KEY_HR_UP = pygame.K_EQUALS
KEY_HR_DOWN = pygame.K_MINUS


# ----------------------------
# ASSET CACHE / HELPERS
# ----------------------------
_ASSET_CACHE = {}
_TILESET_CACHE = {}

def load_image(path: str, alpha=True):
    """Cached image loader."""
    if path in _ASSET_CACHE:
        return _ASSET_CACHE[path]
    if not os.path.exists(path):
        # Fallback to create a colored square if asset missing (prevents crash during dev)
        # print(f"Warning: Asset not found {path}, creating placeholder.")
        surf = pygame.Surface((32, 32))
        surf.fill((255, 0, 255))
        return surf
    img = pygame.image.load(path)
    img = img.convert_alpha() if alpha else img.convert()
    _ASSET_CACHE[path] = img
    return img


def load_tileset(path: str, tile_size=TILE_SIZE):
    """Slice a tileset into a list of tile Surfaces."""
    key = (path, tile_size)
    if key in _TILESET_CACHE:
        return _TILESET_CACHE[key]
    sheet = load_image(path, alpha=True)
    sw, sh = sheet.get_size()
    tiles = []
    for y in range(0, sh, tile_size):
        for x in range(0, sw, tile_size):
            tiles.append(sheet.subsurface((x, y, tile_size, tile_size)))
    _TILESET_CACHE[key] = tiles
    return tiles


def clamp(v, a, b):
    return max(a, min(b, v))


def key_any(keys, key_tuple):
    return any(keys[k] for k in key_tuple)


# ----------------------------
# NEW: BIOMETRIC CLASSES & ENUMS
# ----------------------------
class InputMode(Enum):
    HEART_RATE = 1
    EMOTION = 2

@dataclass
class GameSettings:
    input_type: InputMode = InputMode.HEART_RATE
    baseline_bpm: int = 80

class MultiInputReceiver:
    """
    Handles both numeric BPM (for HR Mode) and text Strings (for Emotion Mode)
    running on a single UDP port.
    """
    def __init__(self, bind_ip=UDP_BIND_IP, port=UDP_PORT):
        self.bind_ip = bind_ip
        self.port = port
        self._latest_bpm = None
        self._latest_emotion = "NEUTRAL"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def get_data(self):
        """Returns (bpm, emotion_string)"""
        with self._lock:
            return self._latest_bpm, self._latest_emotion

    def _parse_bpm(self, msg: str):
        """Attempts to extract a number from the string."""
        # JSON format: {"bpm": 82}
        if msg.startswith("{") and "bpm" in msg.lower():
            try:
                obj = json.loads(msg)
                return int(float(obj.get("bpm", 0)))
            except: pass
        
        # Key-Value format: "BPM:82"
        if ":" in msg:
            parts = msg.split(":")
            for p in reversed(parts):
                clean = "".join(c for c in p if c.isdigit() or c == '.')
                if clean:
                    return int(float(clean))
        
        # Raw number: "82"
        clean = "".join(c for c in msg if c.isdigit() or c == '.')
        if clean:
            return int(float(clean))
        return None

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(UDP_TIMEOUT)
        try:
            sock.bind((self.bind_ip, self.port))
        except OSError:
            print(f"UDP Port {self.port} busy. Live input disabled.")
            return

        while not self._stop.is_set():
            try:
                data, _addr = sock.recvfrom(512)
                msg = data.decode("utf-8", errors="ignore").strip().upper()
                
                # Check for Emotion Keywords first
                # Added SURPRISED/SAD/FEAR to ensure we catch stress states
                valid_emotions = ["HAPPY", "NEUTRAL", "SAD", "ANGRY", "FEAR", "SURPRISED"]
                found_emotion = False
                
                # Simple substring check (robust against "Emotion: HAPPY" vs "HAPPY")
                for emo in valid_emotions:
                    if emo in msg:
                        with self._lock:
                            self._latest_emotion = emo
                        found_emotion = True
                        break
                
                # If it wasn't an emotion, try parsing as BPM
                if not found_emotion:
                    bpm = self._parse_bpm(msg)
                    if bpm is not None:
                        bpm = int(clamp(bpm, 40, 200))
                        with self._lock:
                            self._latest_bpm = bpm

            except socket.timeout:
                continue
            except Exception as e:
                continue


class BiometricController:
    """
    Manages game difficulty state based on the selected InputMode.
    """
    def __init__(self, settings: GameSettings):
        self.settings = settings
        
        # BPM State
        self.baseline = settings.baseline_bpm
        self.current_bpm = float(settings.baseline_bpm)
        self._bpm_timer = 0.0
        
        # Emotion State
        self.current_emotion = "NEUTRAL"
        
        # Overrides (I/O/U keys)
        self.mode_override = None

    def update(self, dt, keys, latest_bpm, latest_emotion):
        # Update raw values
        self.current_emotion = latest_emotion
        
        # Manual BPM tweak always works for testing
        if keys[KEY_HR_UP]:
            self.current_bpm += 60 * dt
        if keys[KEY_HR_DOWN]:
            self.current_bpm -= 60 * dt

        # Heart Rate Logic
        if self.settings.input_type == InputMode.HEART_RATE:
            if latest_bpm is not None:
                # Smoothly move towards live BPM
                target = float(latest_bpm)
                self.current_bpm += (target - self.current_bpm) * min(1.0, dt * 8.0)
            else:
                # Simulated drift if no signal
                self._bpm_timer += dt
                if self._bpm_timer > 1.0:
                    self._bpm_timer = 0.0
                    if random.random() < 0.12:
                        target = self.baseline + random.uniform(12, 30)
                    else:
                        target = self.baseline + random.uniform(-6, 12)
                    # We don't apply target directly in drift, just simulated jitter
                    # (Simplified: just keep current stable-ish if no input)
            
            self.current_bpm = clamp(self.current_bpm, 45, 190)

    def get_mode(self):
        # Manual Overrides check
        if self.mode_override == "panic":
            return "panic"
        if self.mode_override == "stress":
            return "stress"
        
        # Logic based on Input Type
        if self.settings.input_type == InputMode.EMOTION:
            # MAPPING:
            # Happy / Neutral -> Normal
            # Sad / Fear / Surprised -> Stress
            # Angry -> Panic
            if self.current_emotion in ["HAPPY", "NEUTRAL"]:
                return "normal"
            elif self.current_emotion in ["SAD", "FEAR", "SURPRISED"]:
                return "stress"
            elif self.current_emotion == "ANGRY":
                return "panic"
            return "normal"

        else:
            # Default: Heart Rate Logic
            b = int(round(self.current_bpm))
            if b > self.baseline + PANIC_DELTA:
                return "panic"
            if b >= self.baseline + STRESS_DELTA:
                return "stress"
            return "normal"

    def get_display_value(self):
        if self.settings.input_type == InputMode.EMOTION:
            return self.current_emotion
        return int(round(self.current_bpm))


# ----------------------------
# CAMERA (visual only)
# ----------------------------
class Camera:
    def __init__(self):
        self.x = 0.0

    def update(self, target_x: float, world_w: int):
        # follow player horizontally; keep 40% lead room
        desired = target_x - WIDTH * 0.45
        self.x = clamp(desired, 0, max(0, world_w - WIDTH))

    def world_to_screen_x(self, wx: int) -> int:
        return int(wx - self.x)


# ----------------------------
# PLAYER ANIM
# ----------------------------
class PlayerAnimator:
    """
    Visual-only animator.
    Uses optional sprite sheets (idle/run/jump) if present; otherwise falls back to player.png.
    """
    def __init__(self, base_sprite: pygame.Surface, scaled_size=40):
        self.time = 0.0
        self.scaled_size = scaled_size

        self.base = pygame.transform.smoothscale(base_sprite, (scaled_size, scaled_size))
        self.idle_frames = self._try_load_sheet(PLAYER_IDLE_PATH, frames=4)
        self.run_frames  = self._try_load_sheet(PLAYER_RUN_PATH,  frames=6)
        self.jump_frames = self._try_load_sheet(PLAYER_JUMP_PATH, frames=3)

        self.idle_fps = 6.0
        self.run_fps = 12.0
        self.jump_fps = 8.0

    def _prep_frame(self, frame: pygame.Surface) -> pygame.Surface:
        rect = frame.get_bounding_rect(min_alpha=1)
        if rect.w > 2 and rect.h > 2:
            frame = frame.subsurface(rect).copy()
        frame = pygame.transform.smoothscale(frame, (self.scaled_size, self.scaled_size))
        return frame

    def _try_load_sheet(self, path: str, frames: int):
        try:
            sheet = load_image(path, alpha=True)
        except Exception:
            return None

        fw = PLAYER_SHEET_FRAME
        fh = PLAYER_SHEET_FRAME
        out = []
        for i in range(frames):
            x = i * fw
            if x + fw > sheet.get_width():
                break
            fr = sheet.subsurface((x, 0, fw, fh)).copy()
            out.append(self._prep_frame(fr))
        return out if out else None

    def update(self, dt):
        self.time += dt

    def _frame_from(self, frames, fps):
        if not frames:
            return self.base
        idx = int(self.time * fps) % len(frames)
        return frames[idx]

    def get_frame(self, facing: int, on_ground: bool, moving: bool, vy: float):
        if not on_ground:
            spr = self._frame_from(self.jump_frames, self.jump_fps)
        elif moving:
            spr = self._frame_from(self.run_frames, self.run_fps)
        else:
            spr = self._frame_from(self.idle_frames, self.idle_fps)

        if facing == -1:
            spr = pygame.transform.flip(spr, True, False)

        return spr, 0, 0


# ----------------------------
# OBJECTS (unchanged)
# ----------------------------
@dataclass
class Trap:
    rect: pygame.Rect
    kind: str
    active: bool = True
    t: float = 0.0
    triggered: bool = False
    used: bool = False
    dir: int = 1
    speed: float = 0.0
    base_x: int = 0
    base_y: int = 0
    cooldown: float = 0.0


@dataclass
class Door:
    rect: pygame.Rect
    fake: bool = False
    moves: bool = False
    spiky: bool = False
    visible: bool = True


@dataclass
class Projectile:
    pos: pygame.Vector2
    vel: pygame.Vector2
    radius: int
    active: bool = True
    homing: bool = False
    ttl: float = 6.0


# ----------------------------
# RENDERING (pixel art)
# ----------------------------
def blit_tiled(dst: pygame.Surface, tile: pygame.Surface, x: int, y: int, w: int, h: int):
    tw, th = tile.get_width(), tile.get_height()
    for yy in range(y, y + h, th):
        for xx in range(x, x + w, tw):
            dst.blit(tile, (xx, yy))


def draw_platforms_tilemap(dst: pygame.Surface, cam: Camera, level_idx: int, platforms):
    if level_idx == 1:
        tiles = load_tileset(TILES_INDUSTRIAL)
        top = tiles[2] if len(tiles) > 2 else tiles[0]
        fill = tiles[0]
    elif level_idx == 2:
        tiles = load_tileset(TILES_STONE)
        top = tiles[0]
        fill = tiles[1] if len(tiles) > 1 else tiles[0]
    else:
        tiles = load_tileset(TILES_GRASS)
        top = tiles[0]
        fill = tiles[1] if len(tiles) > 1 else tiles[0]

    for r in platforms:
        sx = cam.world_to_screen_x(r.x)
        sy = r.y
        if sx > WIDTH or sx + r.w < 0:
            continue

        blit_tiled(dst, top, sx, sy, r.w, min(TILE_SIZE, r.h))
        if r.h > TILE_SIZE:
            blit_tiled(dst, fill, sx, sy + TILE_SIZE, r.w, r.h - TILE_SIZE)


def draw_spikes_pixel(dst: pygame.Surface, cam: Camera, rect: pygame.Rect, t=0.0):
    sheet = load_image(SPIKES_SHEET)
    frame_w = TILE_SIZE
    frame_h = TILE_SIZE
    frames = []
    for x in range(0, sheet.get_width(), frame_w):
        frames.append(sheet.subsurface((x, 0, frame_w, frame_h)))
    if not frames:
        return
    idx = int((t * 10) % len(frames))
    frame = frames[idx]

    sx = cam.world_to_screen_x(rect.x)
    if sx > WIDTH or sx + rect.w < 0:
        return

    x = sx
    while x < sx + rect.w:
        dst.blit(frame, (x, rect.y + rect.h - frame_h))
        x += frame_w


def draw_laser_pixel(dst: pygame.Surface, cam: Camera, rect: pygame.Rect, t: float):
    """FIXED: Laser now scrolls vertically."""
    raw_tex = load_image(LASER_TEX)
    # Rotate texture so pattern flows vertically
    tex = pygame.transform.rotate(raw_tex, 90)
    
    # Scale: keep roughly same thickness relative to original
    scaled_tex = pygame.transform.smoothscale(tex, (int(tex.get_width() * 0.1), int(tex.get_height() * 0.1)))

    sx = cam.world_to_screen_x(rect.x)
    if sx > WIDTH or sx + rect.w < 0:
        return

    scroll_speed = 45 
    scroll = int((t * scroll_speed) % scaled_tex.get_height())
    
    # Calculate X position to center the laser beam in the rect
    tx = sx + (rect.w - scaled_tex.get_width()) // 2
    
    # Draw loop along Y axis
    y = rect.y - scroll
    while y < rect.y + rect.h:
        # Clip if it goes outside the rect boundaries
        draw_y = max(y, rect.y)
        draw_h = min(scaled_tex.get_height(), rect.y + rect.h - y) - (draw_y - y)
        
        if draw_h > 0:
            area = pygame.Rect(0, draw_y - y, scaled_tex.get_width(), draw_h)
            dst.blit(scaled_tex, (tx, draw_y), area)
            
        y += scaled_tex.get_height()


def draw_falling_block(dst: pygame.Surface, cam: Camera, trap: Trap):
    sheet = load_image(FALLING_BLOCK_SHEET)
    fw = TILE_SIZE
    fh = TILE_SIZE
    normal = sheet.subsurface((0, 0, fw, fh)) if sheet.get_width() >= fw else sheet
    cracked = sheet.subsurface((fw, 0, fw, fh)) if sheet.get_width() >= fw * 2 else normal

    sx = cam.world_to_screen_x(trap.rect.x)
    if sx > WIDTH or sx + trap.rect.w < 0:
        return

    img = cracked if (trap.triggered and trap.active and trap.rect.y == trap.base_y) else normal
    blit_tiled(dst, img, sx, trap.rect.y, trap.rect.w, trap.rect.h)


def draw_door_sprite(dst: pygame.Surface, cam: Camera, door: Door, t=0.0):
    if not door.visible:
        return
    spr = load_image(DOOR_SPRITE)
    sx = cam.world_to_screen_x(door.rect.x)
    if sx > WIDTH or sx + door.rect.w < 0:
        return
    if door.fake or door.spiky:
        pulse = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(t * 6.0))
        glow = spr.copy()
        glow.fill((255, 60, 220, int(120 * pulse)), special_flags=pygame.BLEND_RGBA_MULT)
        dst.blit(glow, (sx - 6, door.rect.y - 6))
    dst.blit(spr, (sx, door.rect.y))


def draw_projectile(dst: pygame.Surface, cam: Camera, p: Projectile):
    sx = cam.world_to_screen_x(int(p.pos.x))
    if sx < -300 or sx > WIDTH + 300:
        return
    pygame.draw.circle(dst, (255, 80, 255), (sx, int(p.pos.y)), p.radius)
    pygame.draw.circle(dst, (20, 8, 32), (sx, int(p.pos.y)), max(2, p.radius - 5))


def draw_parallax(dst: pygame.Surface, cam: Camera, level_idx: int):
    back_p, mid_p, front_p = BG_LAYERS[level_idx]
    back = load_image(back_p)
    mid = load_image(mid_p)
    front = load_image(front_p)

    x = cam.x
    for img, fac in ((back, 0.25), (mid, 0.55), (front, 0.85)):
        ox = int(-(x * fac) % img.get_width())
        dst.blit(img, (ox - img.get_width(), 0))
        dst.blit(img, (ox, 0))
        dst.blit(img, (ox + img.get_width(), 0))


# ----------------------------
# LEVELS
# ----------------------------
class Level:
    def __init__(self, idx: int):
        self.idx = idx
        self.spawn = (70, HEIGHT - 160)

        self.world_w = WIDTH
        self.platforms = []
        self.traps = []
        self.doors = []
        self.real_door = None
        self.projectiles = []
        self.zoom_troll_zone = None
        self.level_time = 0.0

        self.build(idx)

    def build(self, idx: int):
        self.platforms = []
        self.traps = []
        self.doors = []
        self.projectiles = []
        self.zoom_troll_zone = None
        self.level_time = 0.0

        self.world_w = WIDTH * 8

        def P(x, y, w, h=22):
            r = pygame.Rect(int(x), int(y), int(w), int(h))
            self.platforms.append(r)
            return r

        def T(rect, kind, **kw):
            tr = Trap(rect, kind, **kw)
            # FIX 1: initialize base_x so shifting walls know where they started
            tr.base_x = rect.x 
            tr.base_y = rect.y
            self.traps.append(tr)
            return tr

        # Start pad only
        P(0, HEIGHT - 78, 350, 78)
        self.spawn = (80, HEIGHT - 160)

        # LEVEL 1
        if idx == 1:
            # Shortened Level 1 to avoid empty gap
            self.world_w = 6000 
            
            P(560, HEIGHT - 170, 110)
            cf1 = T(pygame.Rect(760, HEIGHT - 190, 110, 18), "collapsing_floor", active=True)
            self.platforms.append(cf1.rect)
            T(pygame.Rect(623, HEIGHT - 188, 60, 18), "spikes")

            P(820, HEIGHT - 320, 110)
            T(pygame.Rect(1180, HEIGHT - 320, 120, 160), "trigger_hidden_spikes")
            hs1 = T(pygame.Rect(1265, HEIGHT - 238, 60, 18), "hidden_spikes", active=False)
            hs1.cooldown = 3.0
            P(1200, HEIGHT - 220, 110)

            P(1500, HEIGHT - 260, 180)
            fb1 = T(pygame.Rect(1540, 210, 70, 70), "falling_block", active=True)
            fb1.base_x, fb1.base_y = fb1.rect.x, fb1.rect.y

            P(1780, HEIGHT - 330, 150)
            T(pygame.Rect(1960, 0, 30, HEIGHT), "laser", active=True)
            P(2050, HEIGHT - 270, 90)

            P(2300, HEIGHT - 210, 90)
            # This wall will now move relative to its spawn point (2570)
            T(pygame.Rect(2570, HEIGHT - 245, 34, 34), "shifting_wall", active=True, speed=260, dir=-1)
            # T(pygame.Rect(2640, HEIGHT - 110, 240, 32), "spikes")
            P(2920, HEIGHT - 290, 180)

            T(pygame.Rect(3120, HEIGHT - 520, 520, 360), "input_swap_zone")
            P(3240, HEIGHT - 240, 220)

            cf2 = T(pygame.Rect(3560, HEIGHT - 220, 180, 18), "collapsing_floor", active=True)
            self.platforms.append(cf2.rect)
            P(3810, HEIGHT - 300, 120)
            T(pygame.Rect(4000, 0, 18, HEIGHT), "laser", active=True)
            P(4150, HEIGHT - 250, 90)

            T(pygame.Rect(4440, HEIGHT - 520, 520, 360), "gravity_flip_zone")
            P(4480, HEIGHT - 260, 190)

            fb2 = T(pygame.Rect(4850, 160, 70, 70), "falling_block", active=True)
            fb2.base_x, fb2.base_y = fb2.rect.x, fb2.rect.y

            # Moved the final section significantly closer (was at world_w - 520)
            final_base_x = 5100
            P(final_base_x, HEIGHT - 210, 220)
            P(final_base_x + 60, HEIGHT - 210, 200)

            self.doors.append(Door(pygame.Rect(final_base_x + 145, HEIGHT - 305, 64, 98), fake=True, moves=False))
            self.real_door = Door(pygame.Rect(final_base_x + 290, HEIGHT - 305, 64, 98), fake=False, visible=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(final_base_x - 400, HEIGHT - 520, 760, 420)

        # LEVEL 2
        elif idx == 2:
            P(535, HEIGHT - 110, 10)
            cf3 = T(pygame.Rect(600, HEIGHT - 235, 30, 18), "collapsing_floor", active=True)
            self.platforms.append(cf3.rect)
            # P(600, HEIGHT - 235, 30)
            T(pygame.Rect(800, 0, 18, HEIGHT), "laser", active=True)
            P(980, HEIGHT - 95, 10)
            T(pygame.Rect(1040, 0, 18, HEIGHT), "laser", active=True)
            cf4 = T(pygame.Rect(1080, HEIGHT - 210, 10, 18), "collapsing_floor", active=True)
            self.platforms.append(cf4.rect)
            # P(1080, HEIGHT - 210, 10)

            P(1200, HEIGHT - 300, 60)
            # crusher = T(pygame.Rect(1200, HEIGHT - 280, 60, 78), "rising_pit", active=False)
            # crusher.base_x, crusher.base_y = crusher.rect.x, crusher.rect.y
            # T(pygame.Rect(1200, HEIGHT - 270, 140, 150), "trigger_rising_pit")

            P(1320, HEIGHT - 435, 180)
            hs3 = T(pygame.Rect(1340, HEIGHT - 435, 60, 18), "hidden_spikes", active=False)
            hs3.cooldown = 3.0

            cf5 = T(pygame.Rect(1980, HEIGHT - 250, 180, 18), "collapsing_floor", active=True)
            self.platforms.append(cf5.rect)
            T(pygame.Rect(1980, HEIGHT - 110, 200, 32), "spikes")

            P(2300, HEIGHT - 360, 160)
            T(pygame.Rect(2480, 0, 18, HEIGHT), "laser", active=True)
            P(2620, HEIGHT - 480, 150)

            fb = T(pygame.Rect(2660, 170, 70, 70), "falling_block", active=True)
            fb.base_x, fb.base_y = fb.rect.x, fb.rect.y

            P(2920, HEIGHT - 300, 220)
            hz = T(pygame.Rect(3000, HEIGHT - 560, 520, 420), "spawn_homing")
            hz.cooldown = 0.0
            P(3520, HEIGHT - 420, 160)
            P(3780, HEIGHT - 320, 180)

            T(pygame.Rect(4040, HEIGHT - 520, 520, 360), "input_swap_zone")
            T(pygame.Rect(4580, 0, 18, HEIGHT), "laser", active=True)

            P(self.world_w - 520, HEIGHT - 240, 220)
            P(self.world_w - 260, HEIGHT - 240, 200)

            self.doors.append(Door(pygame.Rect(self.world_w - 230, HEIGHT - 170, 64, 98), fake=True, spiky=True))
            self.real_door = Door(pygame.Rect(self.world_w - 120, HEIGHT - 170, 64, 98), fake=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(self.world_w - 950, HEIGHT - 520, 820, 420)

        # LEVEL 3
        else:
            P(520, HEIGHT - 260, 150)
            T(pygame.Rect(720, 0, 18, HEIGHT), "laser", active=True)

            cf1 = T(pygame.Rect(920, HEIGHT - 260, 160, 18), "collapsing_floor", active=True)
            self.platforms.append(cf1.rect)
            T(pygame.Rect(920, HEIGHT - 110, 180, 32), "spikes")

            P(1160, HEIGHT - 360, 150)
            T(pygame.Rect(1160, HEIGHT - 430, 140, 160), "trigger_hidden_spikes")
            hs = T(pygame.Rect(1340, HEIGHT - 110, 200, 32), "hidden_spikes", active=False)
            hs.cooldown = 0.0

            fb1 = T(pygame.Rect(1380, 150, 70, 70), "falling_block", active=True)
            fb1.base_x, fb1.base_y = fb1.rect.x, fb1.rect.y
            P(1460, HEIGHT - 280, 150)

            T(pygame.Rect(1700, HEIGHT - 560, 520, 420), "gravity_flip_zone")
            T(pygame.Rect(2240, 0, 18, HEIGHT), "laser", active=True)
            P(2320, HEIGHT - 420, 160)
            P(2560, HEIGHT - 300, 160)

            P(2820, HEIGHT - 220, 220)
            T(pygame.Rect(3080, HEIGHT - 245, 34, 165), "shifting_wall", active=True, speed=300, dir=-1)
            T(pygame.Rect(3160, HEIGHT - 110, 260, 32), "spikes")
            hz = T(pygame.Rect(3120, HEIGHT - 560, 640, 420), "spawn_homing")
            hz.cooldown = 0.0

            T(pygame.Rect(3680, HEIGHT - 520, 520, 360), "input_swap_zone")
            P(3840, HEIGHT - 350, 120)
            P(4040, HEIGHT - 460, 120)

            T(pygame.Rect(4300, 0, 18, HEIGHT), "laser", active=True)
            T(pygame.Rect(4460, 0, 18, HEIGHT), "laser", active=True)

            cf2 = T(pygame.Rect(4660, HEIGHT - 260, 170, 18), "collapsing_floor", active=True)
            self.platforms.append(cf2.rect)
            P(4880, HEIGHT - 360, 150)
            T(pygame.Rect(5060, HEIGHT - 110, 220, 32), "spikes")

            P(self.world_w - 520, HEIGHT - 220, 220)
            P(self.world_w - 260, HEIGHT - 220, 200)

            self.doors.append(Door(pygame.Rect(self.world_w - 230, HEIGHT - 170, 64, 98), fake=True, moves=True))
            self.real_door = Door(pygame.Rect(self.world_w - 120, HEIGHT - 170, 64, 98), fake=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(self.world_w - 1050, HEIGHT - 560, 920, 460)

    def update(self, dt, player):
        """
        Updates level elements.
        RETURNS: True if player died (e.g. crushed), False otherwise.
        """
        self.level_time += dt
        player_died = False

        for t in self.traps:
            t.t += dt

            if t.kind == "laser":
                on_time, off_time = 0.80, 0.95
                phase = t.t % (on_time + off_time)
                t.active = phase < on_time

            elif t.kind == "shifting_wall":
                # --- NEW PHYSICS LOGIC ---
                # 1. Calculate how much the wall WANTS to move
                move_amt = int(t.dir * t.speed * dt)

                # 2. RIDING LOGIC: Check if player is standing on this wall
                # Conditions: On ground, feet near top of wall, horizontally within wall bounds
                is_riding = False
                if player.on_ground:
                    # Vertical alignment check (small epsilon for float errors)
                    if abs(player.rect.bottom - t.rect.top) <= 4:
                        # Horizontal alignment check
                        if player.rect.right > t.rect.left and player.rect.left < t.rect.right:
                            is_riding = True

                # 3. Move the wall
                t.rect.x += move_amt

                # Bounds check (reverse direction)
                if t.rect.x < t.base_x - 140:
                    t.rect.x = t.base_x - 140
                    t.dir = 1
                elif t.rect.x > t.base_x + 140:
                    t.rect.x = t.base_x + 140
                    t.dir = -1

                # 4. Apply Effects to Player
                
                # A) RIDING: Move player with the wall
                if is_riding:
                    player.pos.x += move_amt
                    player.rect.x = int(player.pos.x)
                    
                    # Optional: Check if riding pushed player into a static ceiling/wall (crush)
                    for p in self.platforms:
                        if player.rect.colliderect(p):
                            # If we rode into a solid block, that's a crush
                            player_died = True

                # B) PUSHING: Wall moved INTO the player (Lateral collision)
                elif player.rect.colliderect(t.rect):
                    # Displace player based on wall direction
                    if move_amt > 0: # Moving Right -> Push Player Right
                        player.rect.left = t.rect.right
                    elif move_amt < 0: # Moving Left -> Push Player Left
                        player.rect.right = t.rect.left
                    
                    # Update float position to match new rect
                    player.pos.x = float(player.rect.x)
                    
                    # C) CRUSHING: Check if pushed into static geometry
                    for p in self.platforms:
                        if player.rect.colliderect(p):
                            player_died = True
                    
                    # Also check world bounds if pushed off map
                    if player.rect.right < 0 or player.rect.left > self.world_w:
                        player_died = True

            elif t.kind == "collapsing_floor":
                if t.triggered and t.active:
                    # Delay timer logic
                    if t.cooldown == 0: t.cooldown = 0.001 
                    else: t.cooldown += dt
                    
                    if t.cooldown > 0.35: 
                        t.active = False
                        t.cooldown = 2.0 
                        
                elif not t.active:
                    t.cooldown -= dt
                    if t.cooldown <= 0:
                        t.active = True
                        t.triggered = False
                        t.cooldown = 0

            elif t.kind == "falling_block":
                if t.triggered and t.active:
                    t.rect.y += int(820 * dt)
                    if t.rect.y > HEIGHT + 250:
                        t.active = False
                        t.cooldown = 1.5
                if not t.active:
                    t.cooldown -= dt
                    if t.cooldown <= 0:
                        t.active = True
                        t.triggered = False
                        t.rect.x, t.rect.y = t.base_x, t.base_y

            elif t.kind == "hidden_spikes":
                if t.active and t.cooldown > 0:
                    t.cooldown -= dt
                    if t.cooldown <= 0:
                        t.active = False

            elif t.kind == "rising_pit":
                if t.active is True:
                    t.rect.y -= int(920 * dt)
                    if t.rect.y <= HEIGHT - 230:
                        t.rect.y = HEIGHT - 230
                        t.cooldown = 0.9
                        t.active = "hold"
                elif t.active == "hold":
                    t.cooldown -= dt
                    if t.cooldown <= 0:
                        t.active = "down"
                elif t.active == "down":
                    t.rect.y += int(960 * dt)
                    if t.rect.y >= t.base_y:
                        t.rect.y = t.base_y
                        t.active = False

            elif t.kind == "spawn_homing":
                if t.cooldown > 0:
                    t.cooldown -= dt
                if player.rect.colliderect(t.rect) and t.cooldown <= 0:
                    t.cooldown = 1.2
                    start = pygame.Vector2(t.rect.left - 18, t.rect.centery + random.uniform(-70, 70))
                    vel = pygame.Vector2(230, random.uniform(-45, 45))
                    self.projectiles.append(Projectile(start, vel, radius=11, active=True, homing=True, ttl=5.5))

        for p in self.projectiles:
            if not p.active:
                continue
            p.ttl -= dt
            if p.ttl <= 0:
                p.active = False
                continue

            if p.homing:
                to_player = pygame.Vector2(player.rect.centerx, player.rect.centery) - p.pos
                if to_player.length() > 0.1:
                    to_player = to_player.normalize()
                    p.vel = p.vel.lerp(to_player * 310, min(1.0, dt * 1.4))
            p.pos += p.vel * dt

            if p.pos.x < -260 or p.pos.x > self.world_w + 260 or p.pos.y < -260 or p.pos.y > HEIGHT + 260:
                p.active = False

        self.projectiles = [p for p in self.projectiles if p.active]
        return player_died

    def draw(self, surf: pygame.Surface, cam: Camera):
        draw_parallax(surf, cam, self.idx)
        draw_platforms_tilemap(surf, cam, self.idx, self.platforms)

        for t in self.traps:
            if t.kind in ("spikes", "delayed_spikes"):
                if t.kind == "delayed_spikes" and not t.active:
                    continue
                draw_spikes_pixel(surf, cam, t.rect, t=t.t)
            elif t.kind == "laser" and t.active:
                draw_laser_pixel(surf, cam, t.rect, t.t)
            elif t.kind == "shifting_wall":
                # --- DRAWING LOGIC ---
                wall_tex = load_image(SHIFTING_WALL_TEX)
                
                sx = cam.world_to_screen_x(t.rect.x)
                if not (sx > WIDTH or sx + t.rect.w < 0):
                    # Draw the shifting wall texture instead of tiles
                    scaled_tex = pygame.transform.smoothscale(wall_tex, (t.rect.w, t.rect.h))
                    surf.blit(scaled_tex, (sx, t.rect.y))
            elif t.kind == "collapsing_floor":
                if t.active:
                    sx = cam.world_to_screen_x(t.rect.x)
                    if not (sx > WIDTH or sx + t.rect.w < 0):

                        # Shake effect if about to fall
                        offset_x = 0
                        if t.triggered:
                            offset_x = random.randint(-2, 2)
                        
                        overlay = pygame.Surface((t.rect.w, t.rect.h), pygame.SRCALPHA)
                        overlay.fill((255, 255, 255, 25))
                        surf.blit(overlay, (sx + offset_x, t.rect.y))
            elif t.kind == "falling_block":
                if t.active:
                    draw_falling_block(surf, cam, t)
            elif t.kind == "hidden_spikes":
                if t.active:
                    draw_spikes_pixel(surf, cam, t.rect, t=t.t)
            elif t.kind == "rising_pit":
                if t.active or t.active in ("hold", "down"):
                    tiles = load_tileset(TILES_STONE)
                    tile = tiles[0]
                    sx = cam.world_to_screen_x(t.rect.x)
                    if not (sx > WIDTH or sx + t.rect.w < 0):
                        blit_tiled(surf, tile, sx, t.rect.y, t.rect.w, t.rect.h)
            else:
                pass

        for d in self.doors:
            draw_door_sprite(surf, cam, d, t=self.level_time)

        for p in self.projectiles:
            draw_projectile(surf, cam, p)


# ----------------------------
# PLAYER
# ----------------------------
class Player:
    def __init__(self, x, y, sprite):
        self.anim = PlayerAnimator(sprite, scaled_size=PLAYER_SIZE)

        self.pos = pygame.Vector2(x, y)
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)

        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1

        self.spawn = pygame.Vector2(x, y)

        self.coyote = 0.0
        self.jump_buf = 0.0

        self.gravity_flipped = False
        self.gravity_flip_timer = 0.0

        self.swap_lr = False
        self.swap_lr_timer = 0.0

        self.swap_jump = False
        self.swap_jump_timer = 0.0

        self.flash_charges = 0
        self.flash_active = False
        self.flash_timer = 0.0

        self.i_frames = 0.0

    def set_spawn(self, x, y):
        self.spawn = pygame.Vector2(x, y)

    def respawn(self):
        self.pos.update(self.spawn.x, self.spawn.y)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buf = 0.0

        self.gravity_flipped = False
        self.gravity_flip_timer = 0.0
        self.swap_lr = False
        self.swap_lr_timer = 0.0
        self.swap_jump = False
        self.swap_jump_timer = 0.0

        self.flash_active = False
        self.flash_timer = 0.0

        self.i_frames = RESPAWN_I_FRAMES

        self.rect.topleft = (int(self.pos.x), int(self.pos.y))

    def update(self, dt, keys, mode: str):
        self.anim.update(dt)

        if self.i_frames > 0:
            self.i_frames -= dt

        if self.gravity_flipped:
            self.gravity_flip_timer -= dt
            if self.gravity_flip_timer <= 0:
                self.gravity_flipped = False

        if self.swap_lr:
            self.swap_lr_timer -= dt
            if self.swap_lr_timer <= 0:
                self.swap_lr = False

        if self.swap_jump:
            self.swap_jump_timer -= dt
            if self.swap_jump_timer <= 0:
                self.swap_jump = False

        if self.flash_active:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.flash_active = False

        if keys[KEY_FLASH] and (not self.flash_active) and self.flash_charges > 0:
            self.flash_charges -= 1
            self.flash_active = True
            self.flash_timer = FLASH_DURATION

        speed_mult = 1.0
        jump_mult = 1.0
        if mode == "stress":
            speed_mult *= STRESS_SPEED_MULT
            jump_mult *= STRESS_JUMP_MULT
        if self.flash_active:
            speed_mult *= FLASH_SPEED_MULT

        left = key_any(keys, KEY_LEFT)
        right = key_any(keys, KEY_RIGHT)

        move = 0
        if left:
            move -= 1
        if right:
            move += 1
        if self.swap_lr:
            move *= -1

        self.vx = move * BASE_MOVE_SPEED * speed_mult
        if move != 0:
            self.facing = 1 if move > 0 else -1

        jump_pressed = key_any(keys, KEY_JUMP)
        if self.swap_jump:
            jump_pressed = keys[pygame.K_s] or keys[pygame.K_DOWN]

        if jump_pressed:
            self.jump_buf = 0.10
        else:
            self.jump_buf = max(0.0, self.jump_buf - dt)

        if self.on_ground:
            self.coyote = 0.10
        else:
            self.coyote = max(0.0, self.coyote - dt)

        if self.jump_buf > 0 and self.coyote > 0:
            v = BASE_JUMP_VEL * jump_mult
            self.vy = -v if self.gravity_flipped else v
            self.jump_buf = 0.0
            self.coyote = 0.0
            self.on_ground = False

        g = -GRAVITY if self.gravity_flipped else GRAVITY
        if self.on_ground and not self.gravity_flipped:
            self.vy = 0.0
        else:
            self.vy += g * dt

        self.vy = clamp(self.vy, -1600, 1600)

    def draw(self, surf: pygame.Surface, cam: Camera):
        moving = (abs(self.vx) > 7) and self.on_ground
        spr, xoff, yoff = self.anim.get_frame(self.facing, self.on_ground, moving, self.vy)
        if self.i_frames > 0 and int(self.i_frames * 20) % 2 == 0:
            return
        surf.blit(spr, (cam.world_to_screen_x(int(self.pos.x)) + xoff, int(self.pos.y) + yoff))


# ----------------------------
# PHYSICS
# ----------------------------
def platform_is_active(level: Level, rect: pygame.Rect):
    for t in level.traps:
        if t.rect == rect and t.kind == "collapsing_floor":
            return t.active
    return True


def resolve_physics(player: Player, level: Level, dt):
    """
    Standard physics for player vs static world.
    Note: Moving wall push/crush logic is now handled in Level.update()
    """
    died = False

    prev_rect = player.rect.copy()

    # --- 1. Horizontal Phase ---
    player.pos.x += player.vx * dt
    player.pos.x = clamp(player.pos.x, 0, level.world_w - player.rect.w)
    player.rect.x = int(player.pos.x)

    # Collect all collidables: static platforms + moving walls
    # (Walls are treated as solid static objects during player movement)
    collidables = level.platforms[:]
    for t in level.traps:
        if t.kind == "shifting_wall":
            collidables.append(t.rect)

    for p in collidables:
        # Special check for active/inactive traps (e.g. collapsing floor)
        is_active = True
        for tr in level.traps:
            if tr.rect == p and tr.kind == "collapsing_floor" and not tr.active:
                is_active = False
                break
        if not is_active:
            continue

        if player.rect.colliderect(p):
            if player.vx > 0:
                player.rect.right = p.left
                player.pos.x = float(player.rect.x)
                player.vx = 0.0
            elif player.vx < 0:
                player.rect.left = p.right
                player.pos.x = float(player.rect.x)
                player.vx = 0.0

    # --- 2. Vertical Phase ---
    prev_rect = player.rect.copy()
    player.pos.y += player.vy * dt
    player.rect.y = int(player.pos.y)
    player.on_ground = False

    for p in collidables:
        is_active = True
        for tr in level.traps:
            if tr.rect == p and tr.kind == "collapsing_floor" and not tr.active:
                is_active = False
                break
        if not is_active:
            continue

        x_overlap = (player.rect.right > p.left) and (player.rect.left < p.right)
        if not x_overlap:
            continue

        if not player.gravity_flipped:
            if player.vy >= 0 and prev_rect.bottom <= p.top and player.rect.bottom >= p.top:
                player.rect.bottom = p.top
                player.pos.y = float(player.rect.y)
                player.vy = 0.0
                player.on_ground = True
            elif player.vy <= 0 and prev_rect.top >= p.bottom and player.rect.top <= p.bottom:
                player.rect.top = p.bottom
                player.pos.y = float(player.rect.y)
                player.vy = 0.0
        else:
            if player.vy <= 0 and prev_rect.top >= p.bottom and player.rect.top <= p.bottom:
                player.rect.top = p.bottom
                player.pos.y = float(player.rect.y)
                player.vy = 0.0
                player.on_ground = True
            elif player.vy >= 0 and prev_rect.bottom <= p.top and player.rect.bottom >= p.top:
                player.rect.bottom = p.top
                player.pos.y = float(player.rect.y)
                player.vy = 0.0

    if not player.gravity_flipped and player.rect.top > HEIGHT + 220:
        died = True
    if player.gravity_flipped and player.rect.bottom < -220:
        died = True

    if player.i_frames > 0:
        return False

    # Check dangerous traps (Spikes, Lasers, etc)
    for t in level.traps:
        if t.kind == "spikes" and player.rect.colliderect(t.rect):
            died = True

        if t.kind == "laser" and t.active and player.rect.colliderect(t.rect):
            died = True

        if t.kind == "trigger_hidden_spikes" and player.rect.colliderect(t.rect):
            for h in level.traps:
                if h.kind == "hidden_spikes":
                    h.active = True
                    h.cooldown = 2.0

        if t.kind == "hidden_spikes" and t.active and player.rect.colliderect(t.rect):
            died = True

        if t.kind == "collapsing_floor":
            # Check 1 pixel below (or above if flipped) to detect 'standing on'
            check_rect = player.rect.move(0, 1 if not player.gravity_flipped else -1)
            if t.active and player.on_ground and check_rect.colliderect(t.rect):
                t.triggered = True

        if t.kind == "falling_block":
            if t.active and (player.rect.centerx > t.rect.left and player.rect.centerx < t.rect.right):
                if player.rect.top > t.rect.bottom and (player.rect.top - t.rect.bottom) < 280:
                    t.triggered = True
            if t.active and player.rect.colliderect(t.rect):
                died = True

        if t.kind == "trigger_rising_pit" and player.rect.colliderect(t.rect):
            for rp in level.traps:
                if rp.kind == "rising_pit" and rp.active is False:
                    rp.active = True

        if t.kind == "rising_pit":
            if (t.active or t.active in ("hold", "down")) and player.rect.colliderect(t.rect):
                died = True

        if t.kind == "arm_delayed_spikes" and player.rect.colliderect(t.rect):
            for ds in level.traps:
                if ds.kind == "delayed_spikes" and not ds.used:
                    ds.used = True
                    ds.active = True

        if t.kind == "delayed_spikes" and t.active and player.rect.colliderect(t.rect):
            died = True

        if t.kind == "gravity_flip_zone" and player.rect.colliderect(t.rect):
            # FIXED: Refresh timer constantly while inside zone
            player.gravity_flipped = True
            player.gravity_flip_timer = 0.07 # Lasts 2s after leaving the zone

        if t.kind == "input_swap_zone" and player.rect.colliderect(t.rect):
            if not player.swap_lr:
                player.swap_lr = True
                player.swap_lr_timer = INPUT_SWAP_DURATION
            # Removed jump swapping as requested
            # if not player.swap_jump:
            #     player.swap_jump = True
            #     player.swap_jump_timer = JUMP_SWAP_DURATION

    for p in level.projectiles:
        pr = pygame.Rect(int(p.pos.x - p.radius), int(p.pos.y - p.radius), p.radius * 2, p.radius * 2)
        if player.rect.colliderect(pr):
            p.active = False
            died = True

    return died


def apply_panic_vision(surface, player_rect: pygame.Rect, cam: Camera):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 240))
    cx, cy = cam.world_to_screen_x(player_rect.centerx), player_rect.centery
    pygame.draw.circle(overlay, (0, 0, 0, 0), (cx, cy), PANIC_RADIUS)
    pygame.draw.circle(overlay, (0, 0, 0, 120), (cx, cy), PANIC_RADIUS + 18, width=18)
    surface.blit(overlay, (0, 0))


# ----------------------------
# UI
# ----------------------------
def draw_ui(surface, font_big, font_small, controller: BiometricController, mode, level_idx, deaths, player: Player, training_mode: bool):
    panel = pygame.Rect(WIDTH - 455, 18, 430, 150)

    glass = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
    glass.fill((12, 6, 26, 190))
    surface.blit(glass, (panel.x, panel.y))
    pygame.draw.rect(surface, (255, 0, 255), panel, width=2, border_radius=16)

    val = controller.get_display_value()
    
    if mode == "normal":
        color = (255, 255, 255)
        mode_color = (160, 255, 200)
    elif mode == "stress":
        color = (255, 220, 130)
        mode_color = (255, 200, 80)
    else:
        color = (255, 140, 230)
        mode_color = (255, 80, 255)

    # Dynamic Label based on input mode
    if controller.settings.input_type == InputMode.HEART_RATE:
        label_text = f"Heart Beat: {val}"
        info_text = f"Base: {controller.baseline} | Panic > {controller.baseline + PANIC_DELTA}"
    else:
        label_text = f"Emotion: {val}"
        # Updated UI to show the 3 states clearly
        info_text = "Happy=OK | Sad=Stress | Angry=Panic"

    t1 = font_big.render(label_text, True, color)
    surface.blit(t1, (panel.x + 18, panel.y + 14))

    t2 = font_small.render(info_text, True, (215, 200, 255))
    surface.blit(t2, (panel.x + 18, panel.y + 62))

    tmode = font_small.render(f"Mode: {mode.upper()}", True, mode_color)
    surface.blit(tmode, (panel.x + 18, panel.y + 86))

    flash = f"{player.flash_charges}"
    if player.flash_active:
        flash = f"ACTIVE {player.flash_timer:0.1f}s"
    t3 = font_small.render(f"Flash(Q): {flash}   Level: {level_idx}/3   Deaths: {deaths}", True, (255, 255, 255))
    surface.blit(t3, (panel.x + 18, panel.y + 110))

    # Stress Bar (Only relevant for Heart Rate Mode mainly, but we can fake it for Emotion)
    bar = pygame.Rect(panel.x + 18, panel.y + 132, 394, 10)
    pygame.draw.rect(surface, (35, 18, 55), bar, border_radius=10)
    
    if controller.settings.input_type == InputMode.HEART_RATE:
        delta = max(0, val - controller.baseline)
        fill = int(clamp(delta / 30.0, 0, 1) * bar.w)
    else:
        # Visual bar for emotion intensity
        fill = 0
        if val in ["SAD", "FEAR", "SURPRISED"]: fill = int(bar.w * 0.5)
        if val == "ANGRY": fill = bar.w
        
    pygame.draw.rect(surface, (255, 0, 255), (bar.x, bar.y, fill, bar.h), border_radius=10)
    
    if training_mode:
        tr_txt = font_small.render("[TRAINING MODE]", True, (50, 255, 100))
        surface.blit(tr_txt, (panel.x + panel.w - tr_txt.get_width() - 10, panel.y + 10))


# ----------------------------
# SCREENS (Mode Select & Baseline)
# ----------------------------
def mode_selection_screen(screen, font_title, font_big):
    """
    New start screen to choose between Heart Rate and Emotion mode.
    Includes mouse support for clicking options.
    Returns: (InputMode, training_mode_boolean)
    """
    clock = pygame.time.Clock()
    t = 0.0
    training_mode = False

    # Define the rectangles for mouse interaction (approximate positions)
    cx, cy = WIDTH // 2, HEIGHT // 2
    rect1 = pygame.Rect(cx - 200, 280, 400, 80)
    rect2 = pygame.Rect(cx - 200, 380, 400, 80)
    rect_train = pygame.Rect(cx - 200, 480, 400, 50) # Toggle button

    while True:
        dt = clock.tick(FPS) / 1000.0
        t += dt
        
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            
            # Keyboard Support
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    return InputMode.HEART_RATE, training_mode
                if event.key == pygame.K_2:
                    return InputMode.EMOTION, training_mode
                if event.key == pygame.K_t:
                    training_mode = not training_mode
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            
            # Mouse Support
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left Click
                    if rect1.collidepoint(mx, my):
                        return InputMode.HEART_RATE, training_mode
                    if rect2.collidepoint(mx, my):
                        return InputMode.EMOTION, training_mode
                    if rect_train.collidepoint(mx, my):
                        training_mode = not training_mode

        # Background effect
        screen.fill((10, 5, 20))
        temp_cam = Camera()
        temp_cam.x = (t * 20) % WIDTH
        draw_parallax(screen, temp_cam, 1)

        # Draw UI
        title = font_title.render("HEARTBEAT DEVIL", True, (255, 0, 255))
        screen.blit(title, (cx - title.get_width() // 2, 80))

        opt_title = font_big.render("SELECT INPUT MODE", True, (255, 255, 255))
        screen.blit(opt_title, (cx - opt_title.get_width() // 2, 180))

        # Option 1 (Heart Rate)
        # Check hover
        color1 = (230, 255, 230) if rect1.collidepoint(mx, my) else (150, 220, 150)
        # Visual Box
        pygame.draw.rect(screen, (30, 40, 30), rect1, border_radius=12)
        pygame.draw.rect(screen, color1, rect1, width=2, border_radius=12)
        
        txt1 = font_big.render("1. Heart Rate (BPM)", True, color1)
        screen.blit(txt1, (rect1.centerx - txt1.get_width() // 2, rect1.centery - 25))
        desc1 = pygame.font.SysFont("arial", 20).render("Uses UDP or Manual Key Input", True, (200, 200, 200))
        screen.blit(desc1, (rect1.centerx - desc1.get_width() // 2, rect1.centery + 15))

        # Option 2 (Emotion)
        color2 = (230, 230, 255) if rect2.collidepoint(mx, my) else (150, 150, 220)
        # Visual Box
        pygame.draw.rect(screen, (30, 30, 40), rect2, border_radius=12)
        pygame.draw.rect(screen, color2, rect2, width=2, border_radius=12)

        txt2 = font_big.render("2. Facial Emotion", True, color2)
        screen.blit(txt2, (rect2.centerx - txt2.get_width() // 2, rect2.centery - 25))
        desc2 = pygame.font.SysFont("arial", 20).render("Happy=OK, Sad=Stress, Angry=Panic", True, (200, 200, 200))
        screen.blit(desc2, (rect2.centerx - desc2.get_width() // 2, rect2.centery + 15))
        
        # Training Mode Toggle
        col_tr = (100, 255, 100) if training_mode else (100, 100, 100)
        bg_tr = (20, 50, 20) if training_mode else (30, 30, 30)
        pygame.draw.rect(screen, bg_tr, rect_train, border_radius=8)
        pygame.draw.rect(screen, col_tr, rect_train, width=2, border_radius=8)
        
        tr_status = "ON" if training_mode else "OFF"
        # Resize font for this button to fit
        tr_txt_small = pygame.font.SysFont("arial", 30, bold=True).render(f"Training Mode (Checkpoints): {tr_status}", True, col_tr)
        screen.blit(tr_txt_small, (rect_train.centerx - tr_txt_small.get_width() // 2, rect_train.centery - tr_txt_small.get_height() // 2))
        
        help_txt = pygame.font.SysFont("arial", 18).render("(Press T to toggle)", True, (150, 150, 150))
        screen.blit(help_txt, (rect_train.centerx - help_txt.get_width()//2, rect_train.bottom + 5))
        
        pygame.display.flip()

def baseline_input_screen(screen, font_title, font_big, font_small):
    bpm_text = ""
    clock = pygame.time.Clock()
    t = 0.0

    while True:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_RETURN:
                    if bpm_text.isdigit():
                        bpm = int(bpm_text)
                        if 40 <= bpm <= 200:
                            return bpm
                if event.key == pygame.K_BACKSPACE:
                    bpm_text = bpm_text[:-1]
                else:
                    if event.unicode.isdigit():
                        bpm_text += event.unicode
                    bpm_text = bpm_text[:3]

        temp_cam = Camera()
        temp_cam.x = (t * 40) % WIDTH
        draw_parallax(screen, temp_cam, 1)

        panel = pygame.Rect(WIDTH // 2 - 360, 110, 720, 400)
        glass = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
        glass.fill((10, 6, 22, 215))
        screen.blit(glass, (panel.x, panel.y))
        pygame.draw.rect(screen, (255, 0, 255), panel, width=2, border_radius=20)

        title = font_title.render("HEARTBEAT DEVIL", True, (255, 255, 255))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 28))

        subtitle = font_big.render("Enter your baseline BPM", True, (255, 205, 255))
        screen.blit(subtitle, (panel.centerx - subtitle.get_width() // 2, panel.y + 100))

        box = pygame.Rect(panel.centerx - 130, panel.y + 170, 260, 78)
        pygame.draw.rect(screen, (18, 10, 35), box, border_radius=14)
        pygame.draw.rect(screen, (255, 0, 255), box, width=2, border_radius=14)

        val = font_big.render(bpm_text if bpm_text else "___", True, (255, 255, 255))
        screen.blit(val, (box.centerx - val.get_width() // 2, box.centery - val.get_height() // 2))

        info_x = panel.x + 34
        info_y = panel.y + 270
        lines = [
            f"Stress: BPM >= baseline + {STRESS_DELTA}   |   Panic: BPM > baseline + {PANIC_DELTA}",
            "Controls: A/D move   Space jump   Q flash   R respawn",
        ]
        for i, line in enumerate(lines):
            txt = font_small.render(line, True, (240, 235, 255))
            screen.blit(txt, (info_x, info_y + i * 24))

        pygame.display.flip()


# ----------------------------
# MAIN
# ----------------------------
def main():
    pygame.init()
    pygame.display.set_caption("Heartbeat Devil — Biometric Edition")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # 1. Start Multi-Input Receiver
    input_rx = MultiInputReceiver()
    if USE_LIVE_UDP:
        input_rx.start()

    font_title = pygame.font.SysFont("arial", 58, bold=True)
    font_big = pygame.font.SysFont("arial", 40, bold=True)
    font_small = pygame.font.SysFont("arial", 20)

    # --- OUTER APP LOOP (Allows returning to menu) ---
    while True:
        # 2. Mode Selection
        selected_mode, training_mode = mode_selection_screen(screen, font_title, font_big)

        # 3. Setup Logic based on Mode
        baseline = 80
        if selected_mode == InputMode.HEART_RATE:
            baseline = baseline_input_screen(screen, font_title, font_big, font_small)
        
        settings = GameSettings(input_type=selected_mode, baseline_bpm=baseline)
        bio_ctrl = BiometricController(settings)

        # 4. Load Assets & Level
        player_img = load_image(PLAYER_PATH)
        level_idx = 1
        level = Level(level_idx)

        player = Player(level.spawn[0], level.spawn[1], player_img)
        player.set_spawn(level.spawn[0], level.spawn[1])
        
        # Checkpoint (Initially Spawn)
        current_checkpoint = pygame.Vector2(level.spawn[0], level.spawn[1])

        deaths = 0
        finished = False

        cam = Camera()
        world = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        # Menu Button Rect (Screen Coordinates)
        menu_btn_rect = pygame.Rect(20, 20, 100, 40) # Top left

        running = True
        while running:
            dt = clock.tick(FPS) / 1000.0
            keys = pygame.key.get_pressed()
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    input_rx.stop()
                    pygame.quit(); sys.exit()
                
                # Check Menu Button Click
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: # Left click
                        if menu_btn_rect.collidepoint(mx, my):
                            running = False # Break loop, returns to Mode Select

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False 
                    
                    if event.key == KEY_RESPAWN:
                        if training_mode:
                            player.set_spawn(current_checkpoint.x, current_checkpoint.y)
                        player.respawn()
                        level.projectiles.clear()

                    # Manual Mode Overrides (for testing)
                    if event.key == KEY_FORCE_STRESS:
                        bio_ctrl.mode_override = "stress"
                    if event.key == KEY_FORCE_PANIC:
                        bio_ctrl.mode_override = "panic"
                    if event.key == KEY_FORCE_AUTO:
                        bio_ctrl.mode_override = None

            # 5. Get Live Data & Update Controller
            latest_bpm, latest_emotion = input_rx.get_data()
            bio_ctrl.update(dt, keys, latest_bpm, latest_emotion)
            
            mode = bio_ctrl.get_mode()

            if not finished:
                # Update Level (which includes wall physics/crush logic)
                # Level.update now returns True if player died (e.g. crushed)
                died_in_level = level.update(dt, player)
                if died_in_level:
                    if training_mode:
                        player.set_spawn(current_checkpoint.x, current_checkpoint.y)
                        player.respawn()
                        level.projectiles.clear()
                        deaths += 1
                    else:
                        deaths += 1
                        player.respawn()
                        level.projectiles.clear()

                player.update(dt, keys, mode)

                # Standard Physics (Player vs Static World)
                died_physics = resolve_physics(player, level, dt)
                
                # CHECKPOINT LOGIC
                # Only update checkpoint if: Training Mode ON, Player Alive, On Ground
                if training_mode and not died_physics and not died_in_level and player.on_ground:
                    # Filter dangerous traps to avoid saving checkpoint on them
                    trap_rects = [t.rect for t in level.traps if t.kind in ("collapsing_floor", "falling_block", "shifting_wall", "rising_pit")]
                    
                    foot_rect = pygame.Rect(player.rect.x, player.rect.bottom, player.rect.w, 2)
                    on_safe_ground = False
                    
                    for plat in level.platforms:
                        if foot_rect.colliderect(plat):
                            # Ensure this platform isn't a dangerous trap
                            is_trap = False
                            for tr in trap_rects:
                                if tr == plat:
                                    is_trap = True
                                    break
                            if not is_trap:
                                on_safe_ground = True
                                break
                    
                    if on_safe_ground:
                        current_checkpoint = pygame.Vector2(player.pos.x, player.pos.y)
                
                if died_physics:
                    if training_mode:
                        player.set_spawn(current_checkpoint.x, current_checkpoint.y)
                        player.respawn()
                        level.projectiles.clear()
                        deaths += 1
                    else:
                        deaths += 1
                        player.respawn()
                        level.projectiles.clear()

                for d in level.doors:
                    # Level 1 specific: Reveal real door if player passes fake door
                    if level_idx == 1 and d.fake and not level.real_door.visible:
                        if player.rect.x > d.rect.x + 80:
                            level.real_door.visible = True

                    if d.fake and d.moves:
                        dist = abs(player.rect.centerx - d.rect.centerx) + abs(player.rect.centery - d.rect.centery)
                        if dist < 260:
                            d.rect.x = clamp(d.rect.x + 7, 0, level.world_w - d.rect.w)

                    if d.fake and player.rect.colliderect(d.rect):
                        if player.i_frames <= 0:
                            if training_mode:
                                player.set_spawn(current_checkpoint.x, current_checkpoint.y)
                                player.respawn()
                                level.projectiles.clear()
                                deaths += 1
                            else:
                                deaths += 1
                                player.respawn()
                                level.projectiles.clear()

                if player.rect.colliderect(level.real_door.rect) and level.real_door.visible:
                    if mode == "normal":
                        player.flash_charges += 1

                    level_idx += 1
                    if level_idx > 3:
                        finished = True
                    else:
                        level = Level(level_idx)
                        player.set_spawn(level.spawn[0], level.spawn[1])
                        # Reset checkpoint for new level
                        current_checkpoint = pygame.Vector2(level.spawn[0], level.spawn[1])
                        player.respawn()

            cam.update(player.rect.centerx, level.world_w)

            # 6. Visual Effects
            if mode == "stress":
                shake = 1
                zoom = 1.03
            elif mode == "panic":
                shake = 3
                zoom = 1.06
            else:
                shake = 0
                zoom = 1.0

            if level.zoom_troll_zone and player.rect.colliderect(level.zoom_troll_zone):
                zoom = max(zoom, 1.07)
                shake = max(shake, 2)

            sx = random.randint(-shake, shake) if shake else 0
            sy = random.randint(-shake, shake) if shake else 0

            # Draw World
            world.fill((0, 0, 0, 0))
            cam_shake = Camera()
            cam_shake.x = cam.x - sx
            level.draw(world, cam_shake)
            player.draw(world, cam_shake)

            if mode == "panic":
                apply_panic_vision(world, player.rect, cam_shake)

            # Draw UI
            draw_ui(world, font_big, font_small, bio_ctrl, mode, min(level_idx, 3), deaths, player, training_mode)

            footer = font_small.render(
                "A/D move   Space jump   Q flash   R respawn   -/= bpm   I stress   O panic   U auto",
                True, (255, 255, 255)
            )
            world.blit(footer, (150, HEIGHT - 28)) # Moved slightly right to avoid menu button

            if finished:
                msg = pygame.font.SysFont("arial", 58, bold=True).render("YOU SURVIVED.", True, (255, 255, 255))
                msg2 = pygame.font.SysFont("arial", 22).render("Press R to replay from Level 1", True, (255, 255, 255))
                world.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 140))
                world.blit(msg2, (WIDTH // 2 - msg2.get_width() // 2, 210))

                if keys[KEY_RESPAWN]:
                    level_idx = 1
                    level = Level(level_idx)
                    player.set_spawn(level.spawn[0], level.spawn[1])
                    current_checkpoint = pygame.Vector2(level.spawn[0], level.spawn[1])
                    player.respawn()
                    deaths = 0
                    finished = False
                    bio_ctrl.mode_override = None
                    level.projectiles.clear()

            # Final Scale to Screen
            if abs(zoom - 1.0) < 1e-3:
                screen.blit(world, (0, 0))
            else:
                scaled_w = int(WIDTH * zoom)
                scaled_h = int(HEIGHT * zoom)
                scaled = pygame.transform.smoothscale(world, (scaled_w, scaled_h))
                x = (scaled_w - WIDTH) // 2
                y = (scaled_h - HEIGHT) // 2
                screen.blit(scaled, (-x, -y))

            # --- Draw Menu Button on Screen (Top Layer) ---
            # Using screen coords so it doesn't shake/zoom
            btn_color = (60, 60, 90) if not menu_btn_rect.collidepoint(mx, my) else (80, 80, 110)
            pygame.draw.rect(screen, btn_color, menu_btn_rect, border_radius=8)
            pygame.draw.rect(screen, (200, 200, 255), menu_btn_rect, width=2, border_radius=8)
            
            lbl = font_small.render("MENU", True, (255, 255, 255))
            screen.blit(lbl, (menu_btn_rect.centerx - lbl.get_width()//2, menu_btn_rect.centery - lbl.get_height()//2))

            pygame.display.flip()

if __name__ == "__main__":
    main()
