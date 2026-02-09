
import os
import sys
import random
import math
from dataclasses import dataclass

import pygame

# ============================================================
# Heartbeat Devil — Pixel Art + Parallax + Longer Levels
# - Keeps ALL gameplay logic (movement/trap behavior) the same.
# - Upgrades rendering: tile platforms, parallax backgrounds,
#   animated spikes / laser / cracked falling blocks.
# - Extends levels to multi-screen width with a camera.
# ============================================================

# ----------------------------
# CONFIG
# ----------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 60

ASSETS_DIR = "assets"

# Player (your provided sprite)
PLAYER_PATH = os.path.join(ASSETS_DIR, "player", "player.png")

# Optional animation sheets (generated from your character art)
PLAYER_IDLE_PATH = os.path.join(ASSETS_DIR, "player", "player_idle.png")   # 4 frames, horizontal
PLAYER_RUN_PATH  = os.path.join(ASSETS_DIR, "player", "player_run.png")    # 6 frames, horizontal
PLAYER_JUMP_PATH = os.path.join(ASSETS_DIR, "player", "player_jump.png")   # 3 frames, horizontal
PLAYER_SHEET_FRAME = 256  # our generated sheets use 256x256 per frame

# Tilesets (32×32 tiles recommended)
TILE_SIZE = 32
TILES_GRASS = os.path.join(ASSETS_DIR, "tiles", "grass_tileset.png")
TILES_STONE = os.path.join(ASSETS_DIR, "tiles", "stone_tileset.png")
TILES_INDUSTRIAL = os.path.join(ASSETS_DIR, "tiles", "industrial_tileset.png")

# Traps
SPIKES_SHEET = os.path.join(ASSETS_DIR, "traps", "spikes.png")          # 4 frames in a single horizontal row
LASER_TEX = os.path.join(ASSETS_DIR, "traps", "laser.png")             # scrolling texture
FALLING_BLOCK_SHEET = os.path.join(ASSETS_DIR, "traps", "falling_block.png")  # 2 frames row: normal, cracked

# Door (simple sprite)
DOOR_SPRITE = os.path.join(ASSETS_DIR, "props", "door.png")

# Parallax backgrounds (3-layer per level)
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

# Gameplay (UNCHANGED)
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

RESPAWN_I_FRAMES = 0.8  # prevents instant re-kill loops

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
    """Cached image loader (convert_alpha for performance)."""
    if path in _ASSET_CACHE:
        return _ASSET_CACHE[path]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing asset: {path}")
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


def stable_rng(seed_int: int):
    return random.Random(seed_int & 0xFFFFFFFF)


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
# HEART RATE + MODE CONTROL
# ----------------------------
class HeartRateController:
    def __init__(self, baseline_bpm=80):
        self.baseline = int(baseline_bpm)
        self.current = float(baseline_bpm)
        self._target = float(baseline_bpm)
        self._timer = 0.0
        self.mode_override = None

    def update(self, dt, keys):
        # manual bpm tweak
        if keys[KEY_HR_UP]:
            self.current += 60 * dt
        if keys[KEY_HR_DOWN]:
            self.current -= 60 * dt

        # mock “live” drift
        self._timer += dt
        if self._timer > 1.0:
            self._timer = 0.0
            if random.random() < 0.12:
                self._target = self.baseline + random.uniform(12, 30)
            else:
                self._target = self.baseline + random.uniform(-6, 12)

        self.current += (self._target - self.current) * min(1.0, dt * 2.0)
        self.current = clamp(self.current, 45, 190)

    def bpm(self):
        return int(round(self.current))

    def mode(self):
        if self.mode_override == "panic":
            return "panic"
        if self.mode_override == "stress":
            return "stress"

        b = self.bpm()
        # your rule:
        # stress at >= baseline+10
        # panic at > baseline+20
        if b > self.baseline + PANIC_DELTA:
            return "panic"
        if b >= self.baseline + STRESS_DELTA:
            return "stress"
        return "normal"


# ----------------------------
# PLAYER ANIM (kept simple; your sprite)
# ----------------------------

class PlayerAnimator:
    """
    Visual-only animator.
    Uses optional sprite sheets (idle/run/jump) if present; otherwise falls back to player.png.
    Sheet format: frames in one horizontal row, each frame is PLAYER_SHEET_FRAME × PLAYER_SHEET_FRAME.
    """
    def __init__(self, base_sprite: pygame.Surface, scaled_size=40):
        self.time = 0.0
        self.scaled_size = scaled_size

        # Fallback single sprite
        self.base = pygame.transform.smoothscale(base_sprite, (scaled_size, scaled_size))

        # Try to load sheets (safe if missing)
        self.idle_frames = self._try_load_sheet(PLAYER_IDLE_PATH, frames=4)
        self.run_frames  = self._try_load_sheet(PLAYER_RUN_PATH,  frames=6)
        self.jump_frames = self._try_load_sheet(PLAYER_JUMP_PATH, frames=3)

        # Timing
        self.idle_fps = 6.0
        self.run_fps = 12.0
        self.jump_fps = 8.0

    def _prep_frame(self, frame: pygame.Surface) -> pygame.Surface:
        # Crop to non-transparent bounds for nicer scaling
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
        # Choose animation set
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
        # Only draw if on screen (simple cull)
        if sx > WIDTH or sx + r.w < 0:
            continue

        # draw top row
        blit_tiled(dst, top, sx, sy, r.w, min(TILE_SIZE, r.h))
        # fill under top if platform is thick
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
    tex = load_image(LASER_TEX)
    sx = cam.world_to_screen_x(rect.x)
    if sx > WIDTH or sx + rect.w < 0:
        return

    scroll = int((t * 140) % tex.get_width())
    x = sx - scroll
    # tile horizontally across the rect
    while x < sx + rect.w:
        dst.blit(tex, (x, rect.y + (rect.h - tex.get_height()) // 2))
        x += tex.get_width()


def draw_falling_block(dst: pygame.Surface, cam: Camera, trap: Trap):
    sheet = load_image(FALLING_BLOCK_SHEET)
    # 2 frames (normal, cracked)
    fw = TILE_SIZE
    fh = TILE_SIZE
    normal = sheet.subsurface((0, 0, fw, fh)) if sheet.get_width() >= fw else sheet
    cracked = sheet.subsurface((fw, 0, fw, fh)) if sheet.get_width() >= fw * 2 else normal

    sx = cam.world_to_screen_x(trap.rect.x)
    if sx > WIDTH or sx + trap.rect.w < 0:
        return

    # cracked state "warning" before dropping (triggered but not yet moving)
    img = cracked if (trap.triggered and trap.active and trap.rect.y == trap.base_y) else normal
    # tile to fill the trap rect
    blit_tiled(dst, img, sx, trap.rect.y, trap.rect.w, trap.rect.h)


def draw_door_sprite(dst: pygame.Surface, cam: Camera, door: Door, t=0.0):
    spr = load_image(DOOR_SPRITE)
    sx = cam.world_to_screen_x(door.rect.x)
    if sx > WIDTH or sx + door.rect.w < 0:
        return
    # slight glow pulse for fake/spiky
    if door.fake or door.spiky:
        pulse = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(t * 6.0))
        glow = pygame.transform.rotozoom(spr, 0, 1.0)
        glow = glow.copy()
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

    # Parallax factors (far moves slow)
    x = cam.x
    for img, fac in ((back, 0.25), (mid, 0.55), (front, 0.85)):
        ox = int(-(x * fac) % img.get_width())
        # tile across screen width
        dst.blit(img, (ox - img.get_width(), 0))
        dst.blit(img, (ox, 0))
        dst.blit(img, (ox + img.get_width(), 0))


# ----------------------------
# LEVELS (longer multi-screen)
# ----------------------------
class Level:
    def __init__(self, idx: int):
        self.idx = idx
        self.spawn = (70, HEIGHT - 160)

        self.world_w = WIDTH  # updated by build()
        self.platforms = []
        self.traps = []
        self.doors = []
        self.real_door = None
        self.projectiles = []
        self.zoom_troll_zone = None
        self.level_time = 0.0

        self.build(idx)

    def build(self, idx: int):
        # Reset
        self.platforms = []
        self.traps = []
        self.doors = []
        self.projectiles = []
        self.zoom_troll_zone = None
        self.level_time = 0.0

        # Short & spicy: ~6–10 screens (we use 8)
        self.world_w = WIDTH * 8

        # Helpers
        def P(x, y, w, h=22):
            r = pygame.Rect(int(x), int(y), int(w), int(h))
            self.platforms.append(r)
            return r

        def T(rect, kind, **kw):
            tr = Trap(rect, kind, **kw)
            self.traps.append(tr)
            return tr

        # ------------------------------
        # GLOBAL: Start pad only (NO full ground)
        # ------------------------------
        start_pad = P(0, HEIGHT - 78, 520, 78)

        # Default spawn
        self.spawn = (80, HEIGHT - 160)

        # ==============================
        # LEVEL 1 — Intro / Troll
        # Goal: teach "trust issues" fast.
        # ==============================
        if idx == 1:
            # SECTION A (screen 0–1): immediate risk jumps
            # A1: short hop over pit to a collapsing floor that dumps into spikes
            P(560, HEIGHT - 170, 160)  # landing
            cf1 = T(pygame.Rect(760, HEIGHT - 190, 170, 18), "collapsing_floor", active=True)
            self.platforms.append(cf1.rect)
            T(pygame.Rect(760, HEIGHT - 110, 170, 32), "spikes")  # punishes late reaction

            # A2: trigger hidden spikes "after" you land (trust issue)
            P(980, HEIGHT - 250, 170)
            T(pygame.Rect(980, HEIGHT - 320, 120, 160), "trigger_hidden_spikes")
            hs1 = T(pygame.Rect(1140, HEIGHT - 110, 190, 32), "hidden_spikes", active=False)
            hs1.cooldown = 0.0
            P(1180, HEIGHT - 220, 160)  # safe-looking out

            # SECTION B (screen 2–3): falling blocks over predictable landings + laser gate mid-jump
            # B1: falling block above the "obvious" platform
            P(1500, HEIGHT - 260, 180)
            fb1 = T(pygame.Rect(1540, 210, 70, 70), "falling_block", active=True)
            fb1.base_x, fb1.base_y = fb1.rect.x, fb1.rect.y

            # B2: laser gate placed mid-jump corridor (timed)
            # Jump from 1780->2050 while laser toggles
            P(1780, HEIGHT - 330, 150)
            laser1 = T(pygame.Rect(1960, 0, 18, HEIGHT), "laser", active=True)
            P(2050, HEIGHT - 270, 170)

            # SECTION C (screen 3–5): shifting wall + spikes "combo room"
            # C1: a narrow hallway + shifting wall that pushes you off a ledge into spikes
            P(2300, HEIGHT - 210, 220)
            wall = T(pygame.Rect(2570, HEIGHT - 245, 34, 165), "shifting_wall", active=True, speed=260, dir=-1)
            # spikes bed positioned where you'll get shoved if you hesitate
            T(pygame.Rect(2640, HEIGHT - 110, 240, 32), "spikes")
            # escape platform
            P(2920, HEIGHT - 290, 180)

            # C2: input swap zone immediately after a safe landing (panic moment)
            T(pygame.Rect(3120, HEIGHT - 520, 520, 360), "input_swap_zone")
            P(3240, HEIGHT - 240, 220)

            # SECTION D (screen 5–7): short final gauntlet with alternating “safe” and “kill”
            # D1: collapsing floor + laser stagger (no filler)
            cf2 = T(pygame.Rect(3560, HEIGHT - 220, 180, 18), "collapsing_floor", active=True)
            self.platforms.append(cf2.rect)
            P(3810, HEIGHT - 300, 160)
            laser2 = T(pygame.Rect(4000, 0, 18, HEIGHT), "laser", active=True)
            P(4150, HEIGHT - 250, 180)

            # D2: gravity flip zone placed to throw you into a falling block (troll combo)
            # Player hits zone while airborne, flips, then must react to a block above ceiling line.
            T(pygame.Rect(4440, HEIGHT - 520, 520, 360), "gravity_flip_zone")
            P(4480, HEIGHT - 260, 190)

            fb2 = T(pygame.Rect(4700, 160, 70, 70), "falling_block", active=True)
            fb2.base_x, fb2.base_y = fb2.rect.x, fb2.rect.y

            # End platforms
            P(self.world_w - 520, HEIGHT - 210, 220)
            P(self.world_w - 260, HEIGHT - 210, 200)

            # Door troll + real door
            self.doors.append(Door(pygame.Rect(self.world_w - 230, HEIGHT - 170, 64, 98), fake=True, moves=True))
            self.real_door = Door(pygame.Rect(self.world_w - 120, HEIGHT - 170, 64, 98), fake=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(self.world_w - 900, HEIGHT - 520, 760, 420)

        # ==============================
        # LEVEL 2 — Vertical / Lasers
        # Goal: vertical climbs with laser timing + crushers.
        # ==============================
        elif idx == 2:
            # SECTION A: vertical staircase with lasers cutting climbs
            P(520, HEIGHT - 190, 160)
            P(760, HEIGHT - 300, 150)
            laserA = T(pygame.Rect(980, 0, 18, HEIGHT), "laser", active=True)
            P(1080, HEIGHT - 420, 150)
            P(1320, HEIGHT - 520, 150)

            # SECTION B: rising pit (crusher) under a bait platform
            bait = P(1600, HEIGHT - 220, 220)
            crusher = T(pygame.Rect(1600, HEIGHT - 78, 220, 78), "rising_pit", active=False)
            crusher.base_x, crusher.base_y = crusher.rect.x, crusher.rect.y
            T(pygame.Rect(1440, HEIGHT - 270, 140, 150), "trigger_rising_pit")

            # SECTION C: “trust issues” landing — collapsing floor into spikes, but with a “save” route above
            high_save = P(1980, HEIGHT - 470, 180)
            cf = T(pygame.Rect(1980, HEIGHT - 250, 180, 18), "collapsing_floor", active=True)
            self.platforms.append(cf.rect)
            T(pygame.Rect(1980, HEIGHT - 110, 200, 32), "spikes")

            # SECTION D: laser gate + falling block combo mid climb
            P(2300, HEIGHT - 360, 160)
            laserB = T(pygame.Rect(2480, 0, 18, HEIGHT), "laser", active=True)
            P(2620, HEIGHT - 480, 150)

            fb = T(pygame.Rect(2660, 170, 70, 70), "falling_block", active=True)
            fb.base_x, fb.base_y = fb.rect.x, fb.rect.y

            # SECTION E: homing pressure corridor (short, not spam)
            P(2920, HEIGHT - 300, 220)
            hz = T(pygame.Rect(3000, HEIGHT - 560, 520, 420), "spawn_homing")
            hz.cooldown = 0.0
            # escape platforms
            P(3520, HEIGHT - 420, 160)
            P(3780, HEIGHT - 320, 180)

            # SECTION F: input swap + laser “finish check”
            T(pygame.Rect(4040, HEIGHT - 520, 520, 360), "input_swap_zone")
            laserC = T(pygame.Rect(4580, 0, 18, HEIGHT), "laser", active=True)

            P(self.world_w - 520, HEIGHT - 240, 220)
            P(self.world_w - 260, HEIGHT - 240, 200)

            self.doors.append(Door(pygame.Rect(self.world_w - 230, HEIGHT - 170, 64, 98), fake=True, spiky=True))
            self.real_door = Door(pygame.Rect(self.world_w - 120, HEIGHT - 170, 64, 98), fake=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(self.world_w - 950, HEIGHT - 520, 820, 420)

        # ==============================
        # LEVEL 3 — Chaos / Kaizo
        # Goal: fast reaction chains, mixed mechanics, no safe jumps.
        # ==============================
        else:
            # SECTION A: immediate kaizo opener: jump -> laser -> collapsing floor -> spikes
            P(520, HEIGHT - 260, 150)
            laser1 = T(pygame.Rect(720, 0, 18, HEIGHT), "laser", active=True)

            cf1 = T(pygame.Rect(920, HEIGHT - 260, 160, 18), "collapsing_floor", active=True)
            self.platforms.append(cf1.rect)
            T(pygame.Rect(920, HEIGHT - 110, 180, 32), "spikes")

            # SECTION B: hidden spikes ambush + falling block (combo)
            P(1160, HEIGHT - 360, 150)
            T(pygame.Rect(1160, HEIGHT - 430, 140, 160), "trigger_hidden_spikes")
            hs = T(pygame.Rect(1340, HEIGHT - 110, 200, 32), "hidden_spikes", active=False)
            hs.cooldown = 0.0

            fb1 = T(pygame.Rect(1380, 150, 70, 70), "falling_block", active=True)
            fb1.base_x, fb1.base_y = fb1.rect.x, fb1.rect.y
            P(1460, HEIGHT - 280, 150)

            # SECTION C: gravity flip + laser timing (forces brain swap)
            T(pygame.Rect(1700, HEIGHT - 560, 520, 420), "gravity_flip_zone")
            laser2 = T(pygame.Rect(2240, 0, 18, HEIGHT), "laser", active=True)
            P(2320, HEIGHT - 420, 160)
            P(2560, HEIGHT - 300, 160)

            # SECTION D: shifting wall shove into a spike pit + homing pressure
            P(2820, HEIGHT - 220, 220)
            wall = T(pygame.Rect(3080, HEIGHT - 245, 34, 165), "shifting_wall", active=True, speed=300, dir=-1)
            T(pygame.Rect(3160, HEIGHT - 110, 260, 32), "spikes")
            hz = T(pygame.Rect(3120, HEIGHT - 560, 640, 420), "spawn_homing")
            hz.cooldown = 0.0

            # SECTION E: input swap right before a precision landing (kaizo)
            T(pygame.Rect(3680, HEIGHT - 520, 520, 360), "input_swap_zone")
            P(3840, HEIGHT - 350, 120)
            P(4040, HEIGHT - 460, 120)

            # SECTION F: final “no mercy” chain: lasers staggered + collapsing floor
            laser3 = T(pygame.Rect(4300, 0, 18, HEIGHT), "laser", active=True)
            laser4 = T(pygame.Rect(4460, 0, 18, HEIGHT), "laser", active=True)

            cf2 = T(pygame.Rect(4660, HEIGHT - 260, 170, 18), "collapsing_floor", active=True)
            self.platforms.append(cf2.rect)
            P(4880, HEIGHT - 360, 150)
            T(pygame.Rect(5060, HEIGHT - 110, 220, 32), "spikes")

            # End pads + doors
            P(self.world_w - 520, HEIGHT - 220, 220)
            P(self.world_w - 260, HEIGHT - 220, 200)

            self.doors.append(Door(pygame.Rect(self.world_w - 230, HEIGHT - 170, 64, 98), fake=True, moves=True))
            self.real_door = Door(pygame.Rect(self.world_w - 120, HEIGHT - 170, 64, 98), fake=False)
            self.doors.append(self.real_door)

            self.zoom_troll_zone = pygame.Rect(self.world_w - 1050, HEIGHT - 560, 920, 460)


    def update(self, dt, player_rect: pygame.Rect):
        self.level_time += dt

        for t in self.traps:
            t.t += dt

            if t.kind == "laser":
                on_time, off_time = 1.10, 0.78
                phase = t.t % (on_time + off_time)
                t.active = phase < on_time

            elif t.kind == "shifting_wall":
                t.rect.x += int(t.dir * t.speed * dt)
                if t.rect.x < (self.world_w - 1400):
                    t.rect.x = (self.world_w - 1400)
                    t.dir = 1
                if t.rect.x > (self.world_w - 1180):
                    t.rect.x = (self.world_w - 1180)
                    t.dir = -1

            elif t.kind == "collapsing_floor":
                if t.triggered:
                    t.active = False
                    if t.cooldown <= 0:
                        t.cooldown = 2.1
                if t.cooldown > 0:
                    t.cooldown -= dt
                    if t.cooldown <= 0:
                        t.triggered = False
                        t.active = True

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

                if player_rect.colliderect(t.rect) and t.cooldown <= 0:
                    t.cooldown = 1.2
                    start = pygame.Vector2(t.rect.left - 18, t.rect.centery + random.uniform(-70, 70))
                    vel = pygame.Vector2(230, random.uniform(-45, 45))
                    self.projectiles.append(Projectile(start, vel, radius=11, active=True, homing=True, ttl=5.5))

        # projectiles
        for p in self.projectiles:
            if not p.active:
                continue
            p.ttl -= dt
            if p.ttl <= 0:
                p.active = False
                continue

            if p.homing:
                to_player = pygame.Vector2(player_rect.centerx, player_rect.centery) - p.pos
                if to_player.length() > 0.1:
                    to_player = to_player.normalize()
                    p.vel = p.vel.lerp(to_player * 310, min(1.0, dt * 1.4))
            p.pos += p.vel * dt

            if p.pos.x < -260 or p.pos.x > self.world_w + 260 or p.pos.y < -260 or p.pos.y > HEIGHT + 260:
                p.active = False

        self.projectiles = [p for p in self.projectiles if p.active]

    def draw(self, surf: pygame.Surface, cam: Camera):
        # parallax first
        draw_parallax(surf, cam, self.idx)

        # platforms (tilemap)
        draw_platforms_tilemap(surf, cam, self.idx, self.platforms)

        # traps
        for t in self.traps:
            if t.kind in ("spikes", "delayed_spikes"):
                if t.kind == "delayed_spikes" and not t.active:
                    continue
                draw_spikes_pixel(surf, cam, t.rect, t=t.t)

            elif t.kind == "laser" and t.active:
                draw_laser_pixel(surf, cam, t.rect, t.t)

            elif t.kind == "shifting_wall":
                # draw as tiled industrial block
                tiles = load_tileset(TILES_INDUSTRIAL)
                tile = tiles[0]
                sx = cam.world_to_screen_x(t.rect.x)
                if not (sx > WIDTH or sx + t.rect.w < 0):
                    blit_tiled(surf, tile, sx, t.rect.y, t.rect.w, t.rect.h)

            elif t.kind == "collapsing_floor":
                if t.active:
                    # draw as platforms already; add subtle highlight
                    sx = cam.world_to_screen_x(t.rect.x)
                    if not (sx > WIDTH or sx + t.rect.w < 0):
                        overlay = pygame.Surface((t.rect.w, t.rect.h), pygame.SRCALPHA)
                        overlay.fill((255, 255, 255, 25))
                        surf.blit(overlay, (sx, t.rect.y))

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

            elif t.kind in ("gravity_flip_zone", "input_swap_zone", "trigger_hidden_spikes",
                            "trigger_rising_pit", "arm_delayed_spikes", "spawn_homing"):
                # invisible zones (no debug fill in shipping visuals)
                pass

        # doors
        for d in self.doors:
            draw_door_sprite(surf, cam, d, t=self.level_time)

        # projectiles
        for p in self.projectiles:
            draw_projectile(surf, cam, p)


# ----------------------------
# PLAYER (unchanged logic)
# ----------------------------
class Player:
    def __init__(self, x, y, sprite):
        self.anim = PlayerAnimator(sprite, scaled_size=PLAYER_SIZE)

        self.pos = pygame.Vector2(x, y)  # float position
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

        # gravity:
        g = -GRAVITY if self.gravity_flipped else GRAVITY

        # KEY FIX: if grounded (normal), do not accumulate gravity at all.
        if self.on_ground and not self.gravity_flipped:
            self.vy = 0.0
        else:
            self.vy += g * dt

        self.vy = clamp(self.vy, -1600, 1600)

    def draw(self, surf: pygame.Surface, cam: Camera):
        moving = (abs(self.vx) > 7) and self.on_ground
        spr, xoff, yoff = self.anim.get_frame(self.facing, self.on_ground, moving, self.vy)

        # blink during i-frames
        if self.i_frames > 0 and int(self.i_frames * 20) % 2 == 0:
            return

        surf.blit(spr, (cam.world_to_screen_x(int(self.pos.x)) + xoff, int(self.pos.y) + yoff))


# ----------------------------
# PHYSICS (same rules; world width extended)
# ----------------------------
def platform_is_active(level: Level, rect: pygame.Rect):
    for t in level.traps:
        if t.rect == rect and t.kind == "collapsing_floor":
            return t.active
    return True


def resolve_physics(player: Player, level: Level, dt):
    died = False

    # Save previous rect (for swept collisions)
    prev_rect = player.rect.copy()

    # ----------------
    # Move X + collide
    # ----------------
    player.pos.x += player.vx * dt
    player.pos.x = clamp(player.pos.x, 0, level.world_w - player.rect.w)
    player.rect.x = int(player.pos.x)

    for p in level.platforms:
        if not platform_is_active(level, p):
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

    # ----------------
    # Move Y + collide (SWEPT)
    # ----------------
    prev_rect = player.rect.copy()  # prev after X resolution
    player.pos.y += player.vy * dt
    player.rect.y = int(player.pos.y)

    player.on_ground = False

    for p in level.platforms:
        if not platform_is_active(level, p):
            continue

        # must overlap in X to land/bump
        x_overlap = (player.rect.right > p.left) and (player.rect.left < p.right)
        if not x_overlap:
            continue

        if not player.gravity_flipped:
            # --- LANDING (touch OR overlap) ---
            if player.vy >= 0 and prev_rect.bottom <= p.top and player.rect.bottom >= p.top:
                player.rect.bottom = p.top
                player.pos.y = float(player.rect.y)
                player.vy = 0.0
                player.on_ground = True

            # --- HEAD BUMP ---
            elif player.vy <= 0 and prev_rect.top >= p.bottom and player.rect.top <= p.bottom:
                player.rect.top = p.bottom
                player.pos.y = float(player.rect.y)
                player.vy = 0.0

        else:
            # gravity flipped: "ground" is ceiling

            # --- LANDING ON CEILING (touch OR overlap) ---
            if player.vy <= 0 and prev_rect.top >= p.bottom and player.rect.top <= p.bottom:
                player.rect.top = p.bottom
                player.pos.y = float(player.rect.y)
                player.vy = 0.0
                player.on_ground = True

            # --- BUMP "FLOOR" (when flipped) ---
            elif player.vy >= 0 and prev_rect.bottom <= p.top and player.rect.bottom >= p.top:
                player.rect.bottom = p.top
                player.pos.y = float(player.rect.y)
                player.vy = 0.0

    # out of bounds
    if not player.gravity_flipped and player.rect.top > HEIGHT + 220:
        died = True
    if player.gravity_flipped and player.rect.bottom < -220:
        died = True

    # i-frames ignore traps
    if player.i_frames > 0:
        return False

    # traps
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
            if t.active and player.on_ground and player.rect.colliderect(t.rect):
                t.triggered = True

        if t.kind == "falling_block":
            if t.active and (player.rect.centerx > t.rect.left and player.rect.centerx < t.rect.right):
                if player.rect.top > t.rect.bottom and (player.rect.top - t.rect.bottom) < 280:
                    t.triggered = True
            if t.active and player.rect.colliderect(t.rect):
                died = True

        if t.kind == "shifting_wall" and player.rect.colliderect(t.rect):
            push = t.dir * 240 * dt
            player.pos.x = clamp(player.pos.x + push, 0, level.world_w - player.rect.w)
            player.rect.x = int(player.pos.x)

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
            if not player.gravity_flipped:
                player.gravity_flipped = True
                player.gravity_flip_timer = 2.2

        if t.kind == "input_swap_zone" and player.rect.colliderect(t.rect):
            if not player.swap_lr:
                player.swap_lr = True
                player.swap_lr_timer = INPUT_SWAP_DURATION
            if not player.swap_jump:
                player.swap_jump = True
                player.swap_jump_timer = JUMP_SWAP_DURATION

    # projectiles
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
# UI (kept procedural — it’s UI, not world geometry)
# ----------------------------
def draw_ui(surface, font_big, font_small, hr, mode, level_idx, deaths, player: Player):
    panel = pygame.Rect(WIDTH - 455, 18, 430, 150)

    glass = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
    glass.fill((12, 6, 26, 190))
    surface.blit(glass, (panel.x, panel.y))
    pygame.draw.rect(surface, (255, 0, 255), panel, width=2, border_radius=16)

    bpm = hr.bpm()
    if mode == "normal":
        color = (255, 255, 255)
        mode_color = (160, 255, 200)
    elif mode == "stress":
        color = (255, 220, 130)
        mode_color = (255, 200, 80)
    else:
        color = (255, 140, 230)
        mode_color = (255, 80, 255)

    t1 = font_big.render(f"Heart Beat: {bpm}", True, color)
    surface.blit(t1, (panel.x + 18, panel.y + 14))

    t2 = font_small.render(
        f"Baseline: {hr.baseline}   Stress≥{hr.baseline + STRESS_DELTA}   Panic>{hr.baseline + PANIC_DELTA}",
        True,
        (215, 200, 255),
    )
    surface.blit(t2, (panel.x + 18, panel.y + 62))

    tmode = font_small.render(f"Mode: {mode.upper()}", True, mode_color)
    surface.blit(tmode, (panel.x + 18, panel.y + 86))

    flash = f"{player.flash_charges}"
    if player.flash_active:
        flash = f"ACTIVE {player.flash_timer:0.1f}s"
    t3 = font_small.render(f"Flash(Q): {flash}   Level: {level_idx}/3   Deaths: {deaths}", True, (255, 255, 255))
    surface.blit(t3, (panel.x + 18, panel.y + 110))

    # bpm bar
    bar = pygame.Rect(panel.x + 18, panel.y + 132, 394, 10)
    pygame.draw.rect(surface, (35, 18, 55), bar, border_radius=10)
    delta = max(0, bpm - hr.baseline)
    fill = int(clamp(delta / 30.0, 0, 1) * bar.w)
    pygame.draw.rect(surface, (255, 0, 255), (bar.x, bar.y, fill, bar.h), border_radius=10)


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

        # simple animated background (use level1 parallax back as a menu bg)
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
            f"Stress: BPM ≥ baseline + {STRESS_DELTA}  |  Panic: BPM > baseline + {PANIC_DELTA}",
            "Reward: finish a level in NORMAL → +1 Flash charge (Q) (speed boost 20s)",
            "Testing: I = force stress, O = force panic, U = auto mode",
            "Controls: A/D move  Space jump  Q flash  R respawn  -/= bpm tweak",
        ]
        for i, line in enumerate(lines):
            txt = font_small.render(line, True, (240, 235, 255))
            screen.blit(txt, (info_x, info_y + i * 24))

        hint = font_small.render("ENTER = Start   ESC = Quit", True, (255, 255, 255))
        screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + panel.h - 38))

        pygame.display.flip()


# ----------------------------
# MAIN
# ----------------------------
def main():
    pygame.init()
    pygame.display.set_caption("Heartbeat Devil — Pixel Art Edition")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Load player
    player_img = load_image(PLAYER_PATH)

    font_title = pygame.font.SysFont("arial", 58, bold=True)
    font_big = pygame.font.SysFont("arial", 40, bold=True)
    font_small = pygame.font.SysFont("arial", 20)

    baseline = baseline_input_screen(screen, font_title, font_big, font_small)
    hr = HeartRateController(baseline_bpm=baseline)

    level_idx = 1
    level = Level(level_idx)

    player = Player(level.spawn[0], level.spawn[1], player_img)
    player.set_spawn(level.spawn[0], level.spawn[1])

    deaths = 0
    finished = False

    cam = Camera()
    world = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    while True:
        dt = clock.tick(FPS) / 1000.0
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

                if event.key == KEY_RESPAWN:
                    player.respawn()
                    level.projectiles.clear()

                if event.key == KEY_FORCE_STRESS:
                    hr.mode_override = "stress"
                if event.key == KEY_FORCE_PANIC:
                    hr.mode_override = "panic"
                if event.key == KEY_FORCE_AUTO:
                    hr.mode_override = None

        hr.update(dt, keys)
        mode = hr.mode()

        if not finished:
            level.update(dt, player.rect)
            player.update(dt, keys, mode)

            died = resolve_physics(player, level, dt)
            if died:
                deaths += 1
                player.respawn()
                level.projectiles.clear()

            # door logic
            for d in level.doors:
                if d.fake and d.moves:
                    dist = abs(player.rect.centerx - d.rect.centerx) + abs(player.rect.centery - d.rect.centery)
                    if dist < 260:
                        d.rect.x = clamp(d.rect.x + 7, 0, level.world_w - d.rect.w)

                if d.fake and player.rect.colliderect(d.rect):
                    if player.i_frames <= 0:
                        deaths += 1
                        player.respawn()
                        level.projectiles.clear()

            # real door progression
            if player.rect.colliderect(level.real_door.rect):
                if mode == "normal":
                    player.flash_charges += 1

                level_idx += 1
                if level_idx > 3:
                    finished = True
                else:
                    level = Level(level_idx)
                    player.set_spawn(level.spawn[0], level.spawn[1])
                    player.respawn()

        # camera follow (visual)
        cam.update(player.rect.centerx, level.world_w)

        # camera shake / zoom (kept)
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

        # draw
        world.fill((0, 0, 0, 0))
        # draw level + player with camera; apply shake by temporary offset
        cam_shake = Camera()
        cam_shake.x = cam.x - sx  # subtract to shake in screen space
        level.draw(world, cam_shake)
        player.draw(world, cam_shake)

        if mode == "panic":
            apply_panic_vision(world, player.rect, cam_shake)

        draw_ui(world, font_big, font_small, hr, mode, min(level_idx, 3), deaths, player)

        footer = font_small.render(
            "A/D move  Space jump  Q flash  R respawn  -/= bpm  I stress  O panic  U auto",
            True, (255, 255, 255)
        )
        world.blit(footer, (20, HEIGHT - 28))

        if finished:
            msg = pygame.font.SysFont("arial", 58, bold=True).render("YOU SURVIVED.", True, (255, 255, 255))
            msg2 = pygame.font.SysFont("arial", 22).render("Press R to replay from Level 1", True, (255, 255, 255))
            world.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 140))
            world.blit(msg2, (WIDTH // 2 - msg2.get_width() // 2, 210))

            if keys[KEY_RESPAWN]:
                level_idx = 1
                level = Level(level_idx)
                player.set_spawn(level.spawn[0], level.spawn[1])
                player.respawn()
                deaths = 0
                finished = False
                hr.mode_override = None
                level.projectiles.clear()

        # zoom render
        if abs(zoom - 1.0) < 1e-3:
            screen.blit(world, (0, 0))
        else:
            scaled_w = int(WIDTH * zoom)
            scaled_h = int(HEIGHT * zoom)
            scaled = pygame.transform.smoothscale(world, (scaled_w, scaled_h))
            x = (scaled_w - WIDTH) // 2
            y = (scaled_h - HEIGHT) // 2
            screen.blit(scaled, (-x, -y))

        pygame.display.flip()


if __name__ == "__main__":
    main()
