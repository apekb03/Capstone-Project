"""Menu and overlay UI screens (title, main menu, auth, mode selection, etc.)."""

import math
import traceback

import pygame
from OpenGL.GL import *

import config
import firebase_service as fb
import game_state as gs
import game_types
import ui_draw as ui

InputMode = game_types.InputMode
W, H = config.SCREEN_WIDTH, config.SCREEN_HEIGHT


class MainMenu:
	def __init__(self):
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)

		self.button_width = 460
		self.button_height = 52
		self.button_spacing = 14

		self.CARD = pygame.Rect(0, 0, 780, 700)
		self.CARD.center = (W // 2, H // 2)

		cx = self.CARD.centerx
		y0 = self.CARD.y + 184
		self.START_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.START_RECT.center = (cx, y0)
		self.LEADER_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LEADER_RECT.center = (cx, y0 + (self.button_height + self.button_spacing))
		self.LEVEL_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LEVEL_RECT.center = (cx, y0 + 2 * (self.button_height + self.button_spacing))
		self.QUIT_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.QUIT_RECT.center = (cx, y0 + 3 * (self.button_height + self.button_spacing))
		self.ACCOUNT_RECT = pygame.Rect(0, 0, 360, 36)
		self.ACCOUNT_RECT.center = (cx, self.CARD.bottom - 32)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				mousePos = event.pos
				if self.ACCOUNT_RECT.collidepoint(mousePos):
					return AuthScreen(back_to_title=False)
				if self.START_RECT.collidepoint(mousePos):
					return "start"
				if self.LEADER_RECT.collidepoint(mousePos):
					return LeaderboardHubScreen()
				if self.LEVEL_RECT.collidepoint(mousePos):
					return "lvlSelection"
				if self.QUIT_RECT.collidepoint(mousePos):
					return "quit"
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		u = gs.current_user
		status = (
			f"Signed in as {u['display_name']}"
			if u and u.get("display_name")
			else "Playing as guest — sign in from the link below to sync scores"
		)
		ui.draw_glass_panel(self.CARD, "HEART BEAT DEVIL", "Main menu")
		ui.draw_text_centered(
			status,
			self.CARD.centerx,
			self.CARD.y + 118,
			font=ui.FONT_MICRO or ui.FONT_SUB,
			color=(130, 210, 165) if u and u.get("display_name") else (155, 152, 178),
		)
		mx, my = pygame.mouse.get_pos()

		def hover(r):
			return r.collidepoint(mx, my)

		ui.draw_menu_chip(self.START_RECT, "Launch", "Choose input mode, then start a run", hover(self.START_RECT), accent=True)
		ui.draw_menu_chip(self.LEADER_RECT, "Rankings", "Firebase realtime · top times per level", hover(self.LEADER_RECT), accent=False)
		ui.draw_menu_chip(self.LEVEL_RECT, "Pick level", "Jump straight in (mode select follows)", hover(self.LEVEL_RECT), accent=False)
		ui.draw_menu_chip(self.QUIT_RECT, "Quit", None, hover(self.QUIT_RECT), accent=False)
		ah = self.ACCOUNT_RECT.collidepoint(mx, my)
		col = ui.UI_ACCENT if ah else (130, 128, 155)
		ui.draw_text_centered("Use a different account…", self.ACCOUNT_RECT.centerx, self.ACCOUNT_RECT.y + 4, font=ui.FONT_MICRO or ui.FONT_SUB, color=col)
		ui.end_2d()


class AuthScreen:
	def __init__(self, back_to_title=True):
		self.next_state = None
		self.back_to_title = back_to_title
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.mode = "login"
		self.active_field = "email"
		self.email = ""
		self.password = ""
		self.display_name = ""
		self.message = ""
		cx = W // 2
		self.CARD_W = 820
		self.CARD_H = 780
		self.CARD_RECT = pygame.Rect(0, 0, self.CARD_W, self.CARD_H)
		self.CARD_RECT.center = (cx, H // 2)

		self.GUEST_RECT = pygame.Rect(0, 0, 440, 50)
		self.GUEST_RECT.center = (cx, self.CARD_RECT.y + 168)

		tab_w = 200
		tab_h = 52
		tabs_y = self.CARD_RECT.y + 232
		self.TAB_LOGIN_RECT = pygame.Rect(self.CARD_RECT.x + 90, tabs_y, tab_w, tab_h)
		self.TAB_SIGNUP_RECT = pygame.Rect(self.CARD_RECT.x + 90 + tab_w + 16, tabs_y, tab_w, tab_h)

		self.FIELD_W = 620
		self.FIELD_H = 58
		fields_x = cx - self.FIELD_W // 2
		fields_y = self.CARD_RECT.y + 318
		self.email_rect = pygame.Rect(fields_x, fields_y, self.FIELD_W, self.FIELD_H)
		self.pass_rect = pygame.Rect(fields_x, fields_y + 96, self.FIELD_W, self.FIELD_H)
		self.name_rect = pygame.Rect(fields_x, fields_y + 192, self.FIELD_W, self.FIELD_H)

		self.SUBMIT_RECT = pygame.Rect(0, 0, 320, 54)
		self.SUBMIT_RECT.center = (cx, self.CARD_RECT.y + self.CARD_H - 168)
		self.BACK_RECT = pygame.Rect(0, 0, 260, 52)
		self.BACK_RECT.center = (cx, self.CARD_RECT.y + self.CARD_H - 88)

	def _go_back(self):
		return TitleScreen() if self.back_to_title else MainMenu()

	def _guest_to_menu(self):
		gs.current_user = None
		return MainMenu()

	def _toggle_mode(self):
		self.mode = "signup" if self.mode == "login" else "login"
		self.message = ""
		self.active_field = "email"

	def _submit(self):
		email = self.email.strip()
		password = self.password
		if not email or not password:
			self.message = "Email and password are required."
			return
		try:
			if self.mode == "signup":
				name = self.display_name.strip()
				if not name:
					self.message = "Display name is required for sign up."
					return
				res = fb.firebase_sign_up(email, password)
				uid = res.get("localId")
				if not uid:
					self.message = "Signup failed: no user id from Firebase. Check firebase_api_key matches your project."
					return
				profile, profile_warn = fb.sync_user_profile_to_firestore(uid, email, name, is_signup=True)
			else:
				res = fb.firebase_sign_in(email, password)
				uid = res.get("localId")
				if not uid:
					self.message = "Login failed: no user id from Firebase. Check firebase_api_key matches your project."
					return
				fallback_name = email.split("@")[0] if "@" in email else email
				profile, profile_warn = fb.sync_user_profile_to_firestore(uid, email, fallback_name, is_signup=False)
			gs.current_user = {
				"uid": profile.get("uid") or uid,
				"email": profile.get("email") or email,
				"display_name": profile.get("display_name") or email.split("@")[0],
			}
			self.message = profile_warn or "Signed in successfully."
			self.next_state = MainMenu()
		except fb.FirebaseAuthError as e:
			print(f"[AUTH] mode={self.mode} error={e.code}")
			self.message = fb.friendly_auth_error(e.code, self.mode)
		except Exception as e:
			traceback.print_exc()
			print(f"[AUTH] mode={self.mode} error=UNKNOWN {type(e).__name__}: {e}")
			detail = f"{type(e).__name__}: {str(e)[:160]}"
			self.message = (
				"Something went wrong after contacting Firebase. "
				"If you see this on Sign Up, check the terminal for the full error. "
				f"({detail})"
			)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.GUEST_RECT.collidepoint(event.pos):
					return self._guest_to_menu()
				if self.TAB_LOGIN_RECT.collidepoint(event.pos):
					if self.mode != "login":
						self._toggle_mode()
				elif self.TAB_SIGNUP_RECT.collidepoint(event.pos):
					if self.mode != "signup":
						self._toggle_mode()
				elif self.SUBMIT_RECT.collidepoint(event.pos):
					self._submit()
				elif self.BACK_RECT.collidepoint(event.pos):
					return self._go_back()
				elif self.email_rect.collidepoint(event.pos):
					self.active_field = "email"
				elif self.pass_rect.collidepoint(event.pos):
					self.active_field = "password"
				elif self.name_rect.collidepoint(event.pos):
					self.active_field = "display_name"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					return self._go_back()
				if event.key == pygame.K_TAB:
					if self.active_field == "email":
						self.active_field = "password"
					elif self.active_field == "password":
						self.active_field = "display_name" if self.mode == "signup" else "email"
					else:
						self.active_field = "email"
					continue
				if event.key == pygame.K_RETURN:
					self._submit()
					continue
				target = None
				limit = 64
				if self.active_field == "email":
					target = "email"
					limit = 80
				elif self.active_field == "password":
					target = "password"
					limit = 80
				elif self.active_field == "display_name":
					target = "display_name"
					limit = 24
				if target:
					if event.key == pygame.K_BACKSPACE:
						setattr(self, target, getattr(self, target)[:-1])
					else:
						if len(getattr(self, target)) < limit and event.unicode and event.unicode.isprintable():
							setattr(self, target, getattr(self, target) + event.unicode)
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		ui.draw_glass_panel(self.CARD_RECT, "Welcome", "Sign in to sync scores — or continue as guest")
		mx, my = pygame.mouse.get_pos()
		hg = self.GUEST_RECT.collidepoint(mx, my)
		ui.draw_menu_chip(
			self.GUEST_RECT,
			"Continue as guest",
			"Opens the main menu without Firebase login",
			hg,
			accent=True,
		)

		def draw_tab(rect, label, active):
			bg = (40, 40, 55) if active else (26, 26, 32)
			border = (160, 120, 255) if active else (90, 90, 100)
			pygame.draw.rect(ui.SCREEN, bg, rect, border_radius=10)
			pygame.draw.rect(ui.SCREEN, border, rect, width=2, border_radius=10)
			ui.draw_text(label, rect.x + 55, rect.y + 14)

		draw_tab(self.TAB_LOGIN_RECT, "Login", self.mode == "login")
		draw_tab(self.TAB_SIGNUP_RECT, "Sign Up", self.mode == "signup")

		if not fb.FIREBASE_WEB_API_KEY:
			ui.draw_text("Missing firebase_api_key in .env", self.CARD_RECT.x + 90, self.TAB_LOGIN_RECT.bottom + 8)

		ui.draw_labeled_input_box(self.email_rect, "Email", self.email, self.active_field == "email")
		ui.draw_labeled_input_box(self.pass_rect, "Password", self.password, self.active_field == "password", mask=True)
		if self.mode == "signup":
			ui.draw_labeled_input_box(
				self.name_rect, "Display name", self.display_name, self.active_field == "display_name"
			)
		else:
			ui.draw_text("TAB switch fields · ENTER submit", self.name_rect.x, self.name_rect.y + 12, font=ui.FONT_MICRO or ui.FONT_SUB, color=ui.UI_MUTED_TEXT)

		if self.message:
			msg_rect = pygame.Rect(self.CARD_RECT.x + 70, self.SUBMIT_RECT.y - 200, self.CARD_W - 140, 180)
			ml = self.message.lower()
			is_ok = self.message.startswith("Signed in successfully") and "firestore" not in ml
			is_warn = "firestore" in ml or "profile" in ml or "sync issue" in ml
			if is_ok:
				bg, border = (20, 55, 25), (90, 220, 120)
			elif is_warn:
				bg, border = (55, 45, 15), (220, 180, 90)
			else:
				bg, border = (55, 20, 20), (200, 80, 80)
			pygame.draw.rect(ui.SCREEN, bg, msg_rect, border_radius=12)
			pygame.draw.rect(ui.SCREEN, border, msg_rect, width=2, border_radius=12)
			words = self.message.replace("\n", " ").split()
			lines, cur = [], ""
			max_chars = 62
			for w in words:
				trial = (cur + " " + w).strip() if cur else w
				if len(trial) > max_chars and cur:
					lines.append(cur)
					cur = w
				else:
					cur = trial
				if len(lines) >= 7:
					break
			if cur and len(lines) < 8:
				lines.append(cur)
			lines = lines[:8]
			y = msg_rect.y + 10
			for line in lines:
				ui.draw_text(line[:96], msg_rect.x + 14, y)
				y += 28

		hs = self.SUBMIT_RECT.collidepoint(mx, my)
		ui.draw_menu_chip(self.SUBMIT_RECT, "Sign in" if self.mode == "login" else "Create account", None, hs, accent=False)
		hb = self.BACK_RECT.collidepoint(mx, my)
		lbl = "Back to title" if self.back_to_title else "Back to menu"
		ui.draw_menu_chip(self.BACK_RECT, lbl, None, hb, accent=False)
		ui.end_2d()


class TitleScreen:
	def __init__(self):
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				return AuthScreen(back_to_title=True)
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				return AuthScreen(back_to_title=True)
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		if not ui.menu_background_file_exists():
			ui.draw_title_particles()
		t = pygame.time.get_ticks() / 1000.0
		pulse = 0.82 + 0.18 * math.sin(t * 2.0)
		ac = (
			int(ui.UI_ACCENT[0] * pulse),
			int(ui.UI_ACCENT[1] * pulse),
			min(255, int(ui.UI_ACCENT[2] * (0.92 + 0.08 * pulse))),
		)
		hero = ui.FONT_HERO or ui.FONT_TITLE
		cy = H // 2 - 72
		ui.draw_text_centered("HEART BEAT DEVIL", W // 2, cy - 138, font=hero, color=ac)
		ui.draw_text_centered("STRESS-RESPONSIVE PLATFORMER", W // 2, cy - 38, font=ui.FONT_MICRO or ui.FONT_SUB, color=(140, 138, 168))
		ui.draw_text_centered("Your heart rate — or your face — reshapes the run.", W // 2, cy + 6, font=ui.FONT_NAV or ui.FONT_SUB, color=ui.UI_MUTED_TEXT)
		ui.draw_text_centered("Capstone build · OpenGL + pygame + Firebase", W // 2, cy + 50, font=ui.FONT_MICRO or ui.FONT_SUB, color=(120, 118, 145))
		ui.draw_cta_strip("Press any key or click to sign in (or continue as guest)", H - 148, width=680)
		ui.end_2d()


class LevelSelection:
	def __init__(self):
		self.next_state = None
		self.button_width = 440
		self.button_height = 56
		self.button_spacing = 11
		self.CARD = pygame.Rect(0, 0, 720, 540)
		self.CARD.center = (W // 2, H // 2 + 16)
		cx = self.CARD.centerx
		y0 = self.CARD.y + 168
		self.LVL1_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LVL1_RECT.center = (cx, y0)
		self.LVL2_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LVL2_RECT.center = (cx, y0 + self.button_height + self.button_spacing)
		self.LVL3_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LVL3_RECT.center = (cx, y0 + 2 * (self.button_height + self.button_spacing))
		self.BACK_RECT = pygame.Rect(0, 0, 280, 52)
		self.BACK_RECT.center = (cx, self.CARD.bottom - 52)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.BACK_RECT.collidepoint(event.pos):
					return "main_menu"
				if self.LVL1_RECT.collidepoint(event.pos):
					return ("start", "level1")
				if self.LVL2_RECT.collidepoint(event.pos):
					return ("start", "level2")
				if self.LVL3_RECT.collidepoint(event.pos):
					return ("start", "level3")
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		ui.draw_glass_panel(self.CARD, "Direct deploy", "Choose arena · input mode follows")
		mx, my = pygame.mouse.get_pos()

		def hover(r):
			return r.collidepoint(mx, my)

		ui.draw_menu_chip(self.LVL1_RECT, "Level 1 — Training grounds", "Recommended first drop", hover(self.LVL1_RECT), accent=True)
		ui.draw_menu_chip(self.LVL2_RECT, "Level 2 — Pressure climb", "Tighter timing windows", hover(self.LVL2_RECT), accent=False)
		ui.draw_menu_chip(self.LVL3_RECT, "Level 3 — Work in progress", "Experimental layout", hover(self.LVL3_RECT), accent=False)
		ui.draw_menu_chip(self.BACK_RECT, "Return to console", None, hover(self.BACK_RECT), accent=False)
		ui.end_2d()


class LvlComplete:
	def __init__(self, level_name, finish_time, deaths, next_level):
		self.level_name = level_name
		self.finish_time = finish_time
		self.deaths = deaths
		self.next_level = next_level
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.player_name = "Player"
		self.scores = fb.get_top_scores(level_name)
		self.button_width = 300
		self.button_height = 60
		self.spacing = 20
		cx = W // 2
		start_y = H // 2
		self.CONTINUE_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.CONTINUE_RECT.center = (cx, start_y)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.CONTINUE_RECT.collidepoint(event.pos):
					self.next_state = self.next_level
		return None

	def update(self, dt):
		pass

	def draw(self):
		ui.begin_2d()
		glColor4f(0, 0, 0, 0.7)
		glBegin(GL_QUADS)
		glVertex2f(0, 0)
		glVertex2f(W, 0)
		glVertex2f(W, H)
		glVertex2f(0, H)
		glEnd()
		ui.draw_text(f"{self.level_name} Level Complete!", W // 2 - 180, 100)
		ui.draw_text(f"Time: {self.finish_time:.2f}s", W // 2 - 140, 180)
		ui.draw_text(f"Deaths: {self.deaths}", W // 2 - 140, 220)
		ui.draw_text("Leaderboard", W // 2 - 100, 270)
		y = 310
		if not self.scores:
			ui.draw_text("No scores yet — finish a run and submit your name.", W // 2 - 280, y, font=ui.FONT_SUB, color=ui.UI_MUTED_TEXT)
		else:
			for i, score in enumerate(self.scores):
				line = f"{i+1}. {score['player']}  {score['time']:.2f}s  deaths:{score['deaths']}"
				ui.draw_text(line, W // 2 - 260, y)
				y += 44
		pygame.draw.rect(ui.SCREEN, (100, 100, 100), self.CONTINUE_RECT)
		ui.draw_text("Continue", self.CONTINUE_RECT.centerx - 70, self.CONTINUE_RECT.centery - 15)
		ui.end_2d()


class PauseMenu:
	def __init__(self, previous_state):
		self.previous_state = previous_state
		self.button_width = 300
		self.button_height = 60
		self.spacing = 20
		cx = W // 2
		start_y = H // 2
		self.RESUME_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.RESUME_RECT.center = (cx, start_y)
		self.MENU_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MENU_RECT.center = (cx, start_y + self.button_height + self.spacing)
		self.QUIT_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.QUIT_RECT.center = (cx, start_y + 2 * (self.button_height + self.spacing))

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return self.previous_state
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.RESUME_RECT.collidepoint(event.pos):
					return self.previous_state
				if self.MENU_RECT.collidepoint(event.pos):
					return MainMenu()
				if self.QUIT_RECT.collidepoint(event.pos):
					return "quit"
		return None

	def update(self, dt):
		pass

	def draw(self):
		self.previous_state.draw()
		ui.begin_2d()
		glColor4f(0, 0, 0, 0.7)
		glBegin(GL_QUADS)
		glVertex2f(0, 0)
		glVertex2f(W, 0)
		glVertex2f(W, H)
		glVertex2f(0, H)
		glEnd()
		pygame.draw.rect(ui.SCREEN, (100, 100, 100), self.RESUME_RECT)
		pygame.draw.rect(ui.SCREEN, (100, 100, 100), self.MENU_RECT)
		pygame.draw.rect(ui.SCREEN, (100, 100, 100), self.QUIT_RECT)
		ui.draw_text("Resume Game", self.RESUME_RECT.centerx - 100, self.RESUME_RECT.centery - 15)
		ui.draw_text("Main Menu", self.MENU_RECT.centerx - 80, self.MENU_RECT.centery - 15)
		ui.draw_text("Quit Game", self.QUIT_RECT.centerx - 72, self.QUIT_RECT.centery - 15)
		ui.draw_text("Paused", W // 2 - 60, H // 2 - 140)
		ui.end_2d()


class LeaderboardScreen:
	def __init__(self, level_name, next_level, upload_ok=None, upload_err=None):
		self.level_name = level_name
		self.next_level = next_level
		self._upload_ok = upload_ok
		self._upload_err = upload_err
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.scores = fb.get_top_scores(level_name)
		self.PANEL = pygame.Rect(0, 0, 920, 720)
		self.PANEL.center = (W // 2, H // 2 + 8)
		self.CONTINUE_RECT = pygame.Rect(0, 0, 380, 54)
		self.CONTINUE_RECT.center = (W // 2, self.PANEL.bottom - 56)
		self._reload_timer = 0.0

	def on_enter(self):
		self.scores = fb.get_top_scores(self.level_name)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				if isinstance(self.next_level, MainMenu):
					return self.next_level
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.CONTINUE_RECT.collidepoint(event.pos):
					return self.next_level
		return None

	def update(self, dt):
		self._reload_timer += dt
		if self._reload_timer >= 1.25:
			self._reload_timer = 0.0
			self.scores = fb.get_top_scores(self.level_name)

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		ui.draw_glass_panel(self.PANEL, self.level_name, "Firebase Realtime Database · fastest times · live refresh")
		y_extra = 0
		if self._upload_ok is True:
			y_extra = 44
			ui.draw_text_centered(
				"Score saved online (Realtime Database → leaderboards/).",
				W // 2,
				self.PANEL.y + 108,
				font=ui.FONT_MICRO or ui.FONT_SUB,
				color=(130, 210, 160),
			)
		elif self._upload_ok is False:
			y_extra = 52
			ui.draw_text_centered(
				"Score not saved — see terminal log. (Profiles live in Firestore; scores live in Realtime DB.)",
				W // 2,
				self.PANEL.y + 100,
				font=ui.FONT_MICRO or ui.FONT_SUB,
				color=(240, 140, 140),
			)
			if self._upload_err:
				ui.draw_text_centered(
					self._upload_err[:140],
					W // 2,
					self.PANEL.y + 126,
					font=ui.FONT_MICRO or ui.FONT_SUB,
					color=(200, 160, 160),
				)
		y = self.PANEL.y + 138 + y_extra
		if not self.scores:
			ui.draw_text_centered("No scores for this arena yet.", W // 2, y, font=ui.FONT_NAV or ui.FONT_SUB, color=ui.UI_MUTED_TEXT)
			ui.draw_text_centered(
				"Finish a run, submit a callsign, or verify FIREBASE_DATABASE_URL in .env",
				W // 2,
				y + 44,
				font=ui.FONT_MICRO or ui.FONT_SUB,
				color=(130, 128, 150),
			)
		else:
			for i, score in enumerate(self.scores):
				line = f"{i + 1}.  {score['player']}   {score['time']:.2f}s   deaths {score['deaths']}"
				ui.draw_text_centered(line, W // 2, y, font=ui.FONT_NAV or ui.FONT, color=config.WHITE)
				y += 48
		mx, my = pygame.mouse.get_pos()
		h = self.CONTINUE_RECT.collidepoint(mx, my)
		ui.draw_menu_chip(self.CONTINUE_RECT, "Continue", None, h, accent=True)
		ui.end_2d()


class LeaderboardHubScreen:
	def __init__(self):
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.CARD = pygame.Rect(0, 0, 760, 660)
		self.CARD.center = (W // 2, H // 2 + 12)
		cx = self.CARD.centerx
		y = self.CARD.y + 168
		bw, bh, sp = 440, 54, 14
		self.L1 = pygame.Rect(0, 0, bw, bh)
		self.L1.center = (cx, y)
		y += bh + sp
		self.L2 = pygame.Rect(0, 0, bw, bh)
		self.L2.center = (cx, y)
		y += bh + sp
		self.L3 = pygame.Rect(0, 0, bw, bh)
		self.L3.center = (cx, y)
		self.BACK = pygame.Rect(0, 0, 400, 56)
		self.BACK.center = (cx, self.CARD.bottom - 72)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return MainMenu()
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.BACK.collidepoint(event.pos):
					return MainMenu()
				if self.L1.collidepoint(event.pos):
					return LeaderboardScreen("Level 1", MainMenu())
				if self.L2.collidepoint(event.pos):
					return LeaderboardScreen("Level 2", MainMenu())
				if self.L3.collidepoint(event.pos):
					return LeaderboardScreen("Level 3", MainMenu())
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		ui.draw_glass_panel(self.CARD, "Rankings", "Realtime data · same boards as post-mission debrief")
		mx, my = pygame.mouse.get_pos()

		def hover(r):
			return r.collidepoint(mx, my)

		ui.draw_menu_chip(self.L1, "Level 1 board", "Top five clears", hover(self.L1), accent=True)
		ui.draw_menu_chip(self.L2, "Level 2 board", "Escalating tempo", hover(self.L2), accent=False)
		ui.draw_menu_chip(self.L3, "Level 3 board", "Experimental route", hover(self.L3), accent=False)
		ui.draw_menu_chip(self.BACK, "← Back to main menu", "Or press Esc", hover(self.BACK), accent=False)
		ui.end_2d()


class NameEntryScreen:
	def __init__(self, level_name, finish_time, deaths, next_level):
		self.level_name = level_name
		self.finish_time = finish_time
		self.deaths = deaths
		self.next_level = next_level
		self.next_state = None
		self.player_name = (gs.current_user or {}).get("display_name") or ""
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.SUBMIT_RECT = pygame.Rect(W // 2 - 150, 550, 300, 60)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_BACKSPACE:
					self.player_name = self.player_name[:-1]
				elif event.key == pygame.K_RETURN:
					if len(self.player_name.strip()) > 0:
						return self.submit_player_score()
				else:
					if len(self.player_name) < 16:
						if event.unicode.isprintable():
							self.player_name += event.unicode
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.SUBMIT_RECT.collidepoint(event.pos):
					if len(self.player_name.strip()) > 0:
						return self.submit_player_score()
		return None

	def submit_player_score(self):
		ok, err = fb.submit_score(self.level_name, self.player_name, self.finish_time, self.deaths)
		return LeaderboardScreen(self.level_name, self.next_level, upload_ok=ok, upload_err=err)

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0, 0, 0, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.draw_text("Level comlpete!", W // 2 - 100, 100)
		ui.draw_text(f"Time: {self.finish_time:.2f}s", W // 2 - 80, 200)
		ui.draw_text(f"Deaths: {self.deaths}", W // 2 - 80, 250)
		ui.draw_text("Enter Your Name", W // 2 - 100, 350)
		pygame.draw.rect(ui.SCREEN, (60, 60, 60), (W // 2 - 200, 400, 400, 70))
		ui.draw_text(self.player_name, W // 2 - 80, 440)
		pygame.draw.rect(ui.SCREEN, (200, 200, 200), self.SUBMIT_RECT)
		ui.draw_text("Submit Score", self.SUBMIT_RECT.centerx - 95, self.SUBMIT_RECT.centery - 16)
		ui.end_2d()


class ModeSelection:
	def __init__(self):
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.training_mode = False
		self.next_state = None
		self.target_level = "level1"
		self.button_width = 360
		self.button_height = 100
		self.button_spacing = 18
		self.CARD = pygame.Rect(0, 0, 640, 560)
		self.CARD.center = (W // 2, H // 2 + 10)
		cx = self.CARD.centerx
		y1 = self.CARD.y + 195
		self.MODE1_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE1_RECT.center = (cx, y1)
		self.MODE2_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE2_RECT.center = (cx, y1 + self.button_height + self.button_spacing)
		self.TRAIN_RECT = pygame.Rect(0, 0, self.button_width, 72)
		self.TRAIN_RECT.center = (cx, y1 + 2 * (self.button_height + self.button_spacing) + 10)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_1:
					gs.input_mode = InputMode.HEART_RATE
					gs.training_mode = self.training_mode
					return self.target_level
				if event.key == pygame.K_2:
					gs.input_mode = InputMode.EMOTION
					gs.training_mode = self.training_mode
					return self.target_level
				if event.key == pygame.K_t:
					self.training_mode = not self.training_mode
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				mousePos = event.pos
				if self.MODE1_RECT.collidepoint(mousePos):
					gs.input_mode = InputMode.HEART_RATE
					gs.training_mode = self.training_mode
					return self.target_level
				if self.MODE2_RECT.collidepoint(mousePos):
					gs.input_mode = InputMode.EMOTION
					gs.training_mode = self.training_mode
					return self.target_level
				if self.TRAIN_RECT.collidepoint(mousePos):
					self.training_mode = not self.training_mode
		return None

	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0.04, 0.04, 0.08, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_menu_typography()
		ui.draw_menu_backdrop()
		ui.draw_glass_panel(self.CARD, "HEART BEAT DEVIL", "Select how the simulation reads your body")
		ui.draw_text_centered(
			"Keys: 1 Heart rate  ·  2 Emotion  ·  T Training",
			self.CARD.centerx,
			self.CARD.y + 132,
			font=ui.FONT_MICRO or ui.FONT_SUB,
			color=(140, 138, 165),
		)
		ui.draw_text_centered(
			"Emotion route needs webcam + opencv / deepface / tensorflow",
			self.CARD.centerx,
			self.CARD.y + 158,
			font=ui.FONT_MICRO or ui.FONT_SUB,
			color=(110, 108, 130),
		)
		mx, my = pygame.mouse.get_pos()

		def hover(r):
			return r.collidepoint(mx, my)

		m1 = hover(self.MODE1_RECT)
		m2 = hover(self.MODE2_RECT)
		ui.draw_menu_chip(self.MODE1_RECT, "1 — Heart rate (BPM)", "BLE / Pulsoid + UDP fallback", m1, accent=True)
		ui.draw_menu_chip(self.MODE2_RECT, "2 — Facial emotion", "Webcam + DeepFace classifier", m2, accent=False)
		col_tr = ui.UI_ACCENT if self.training_mode else ui.UI_BTN_BORDER
		bg_tr = (28, 48, 32) if self.training_mode else ui.UI_BTN_BG
		if hover(self.TRAIN_RECT):
			bg_tr = (38, 58, 42)
		pygame.draw.rect(ui.SCREEN, bg_tr, self.TRAIN_RECT, border_radius=14)
		pygame.draw.rect(ui.SCREEN, col_tr, self.TRAIN_RECT, width=2, border_radius=14)
		status = "ON" if self.training_mode else "OFF"
		ui.draw_text_centered(
			f"Training mode: {status} (click or T)",
			self.TRAIN_RECT.centerx,
			self.TRAIN_RECT.centery - 10,
			font=ui.FONT_SUB,
			color=config.WHITE,
		)
		ui.end_2d()
