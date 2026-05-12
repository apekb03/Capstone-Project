"""Menu and overlay UI screens (title, main menu, auth, mode selection, etc.)."""

import traceback

import pygame
from OpenGL.GL import *

import config
import firebase_service as fb
import game_state as gs
import game_types
import ui_draw as ui

InputMode = game_types.InputMode


class MainMenu:
	def __init__(self):
		ui.sync_frame_dimensions()
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self._bg = ui.MenuBackdropRed(70)
		self.button_width = 460
		self.button_height = 52
		self.button_spacing = 14
		self._ht = [0.0, 0.0, 0.0, 0.0]
		self._acc_ht = 0.0

		self.CARD = pygame.Rect(0, 0, 780, 700)
		self.CARD.center = (ui.frame_w() // 2, ui.frame_h() // 2)

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
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		rects = [self.START_RECT, self.LEADER_RECT, self.LEVEL_RECT, self.QUIT_RECT]
		for i, r in enumerate(rects):
			t = 1.0 if r.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)
		at = 1.0 if self.ACCOUNT_RECT.collidepoint(mp) else 0.0
		self._acc_ht += (at - self._acc_ht) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		cx = ui.frame_w() // 2
		ui.draw_red_main_title(cx, 120)
		ui.draw_red_title_underline(cx, 250)
		ui.red_blit_centered(ui.FONT_RED_LABEL, "FEEL THE BEAT  ·  SURVIVE THE DEVIL", ui.RED_C_TEXT_DIM, cx, 268)
		ui.draw_red_card_gl(self.CARD, 0.38)
		ui.red_blit_centered(ui.FONT_RED_HEADING, "Main menu", ui.RED_C_RED_BRIGHT, cx, self.CARD.y + 36)
		u = gs.current_user
		status = (
			f"Signed in as {u['display_name']}"
			if u and u.get("display_name")
			else "Guest — use link below to sign in and sync scores"
		)
		st_col = ui.red_lerp_color(ui.RED_C_TEXT_DIM, (130, 210, 160), 0.55 if u and u.get("display_name") else 0.0)
		ui.red_blit_centered(ui.FONT_RED_SMALL, status, st_col, cx, self.CARD.y + 92)
		titles = ["Launch", "Rankings", "Pick level", "Quit"]
		subs = [
			"Choose input mode, then start a run",
			"Firebase realtime · top times per level",
			"Jump straight in (mode select follows)",
			None,
		]
		rects = [self.START_RECT, self.LEADER_RECT, self.LEVEL_RECT, self.QUIT_RECT]
		for i in range(4):
			ui.draw_red_nav_button(rects[i], titles[i], subs[i], self._ht[i], accent=(i == 0))
		ac = ui.red_lerp_color(ui.RED_C_TEXT_DIM, ui.RED_C_ACCENT, self._acc_ht)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Use a different account…", ac, self.ACCOUNT_RECT.centerx, self.ACCOUNT_RECT.y + 2)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "ESC in game opens pause", ui.RED_C_TEXT_DIM, cx, ui.frame_h() - 28)
		ui.end_2d()


class AuthScreen:
	def __init__(self, back_to_title=True):
		ui.sync_frame_dimensions()
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
		self._bg = ui.MenuBackdropRed(48)
		self._ht_guest = 0.0
		self._ht_submit = 0.0
		self._ht_back = 0.0
		cx = ui.frame_w() // 2
		self.CARD_W = 820
		self.CARD_H = 780
		self.CARD_RECT = pygame.Rect(0, 0, self.CARD_W, self.CARD_H)
		self.CARD_RECT.center = (cx, ui.frame_h() // 2)

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
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()

		def step(cur, cond):
			t = 1.0 if cond else 0.0
			return cur + (t - cur) * min(1.0, dt * 12)

		self._ht_guest = step(self._ht_guest, self.GUEST_RECT.collidepoint(mp))
		self._ht_submit = step(self._ht_submit, self.SUBMIT_RECT.collidepoint(mp))
		self._ht_back = step(self._ht_back, self.BACK_RECT.collidepoint(mp))

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		ui.draw_red_glass_panel(self.CARD_RECT, "Welcome", "Sign in to sync scores — or continue as guest")
		mx, my = pygame.mouse.get_pos()
		ui.draw_red_nav_button(
			self.GUEST_RECT,
			"Continue as guest",
			"Opens the main menu without Firebase login",
			self._ht_guest,
			accent=True,
		)

		def draw_tab(rect, label, active):
			bg = (55, 22, 22) if active else (26, 14, 16)
			border = (220, 90, 90) if active else (95, 50, 50)
			pygame.draw.rect(ui.SCREEN, bg, rect, border_radius=10)
			pygame.draw.rect(ui.SCREEN, border, rect, width=2, border_radius=10)
			ui.draw_text(label, rect.x + 55, rect.y + 14)

		draw_tab(self.TAB_LOGIN_RECT, "Login", self.mode == "login")
		draw_tab(self.TAB_SIGNUP_RECT, "Sign Up", self.mode == "signup")

		if not fb.FIREBASE_WEB_API_KEY:
			ui.draw_text("Missing firebase_api_key in .env", self.CARD_RECT.x + 90, self.TAB_LOGIN_RECT.bottom + 8)

		ui.draw_red_labeled_input_box(self.email_rect, "Email", self.email, self.active_field == "email")
		ui.draw_red_labeled_input_box(self.pass_rect, "Password", self.password, self.active_field == "password", mask=True)
		if self.mode == "signup":
			ui.draw_red_labeled_input_box(
				self.name_rect, "Display name", self.display_name, self.active_field == "display_name"
			)
		else:
			ui.draw_text(
				"TAB switch fields · ENTER submit",
				self.name_rect.x,
				self.name_rect.y + 12,
				font=ui.FONT_MICRO or ui.FONT_SUB,
				color=ui.RED_C_TEXT_DIM,
			)

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

		ui.draw_red_single_button(
			self.SUBMIT_RECT,
			"Sign in" if self.mode == "login" else "Create account",
			self._ht_submit,
		)
		lbl = "Back to title" if self.back_to_title else "Back to menu"
		ui.draw_red_single_button(self.BACK_RECT, lbl, self._ht_back)
		ui.end_2d()


class TitleScreen:
	def __init__(self):
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self._bg = ui.MenuBackdropRed(60)

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
		self._bg.update(dt)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		cx = ui.frame_w() // 2
		ui.draw_red_main_title(cx, 120)
		ui.draw_red_title_underline(cx, 268)
		ui.red_blit_centered(ui.FONT_RED_LABEL, "STRESS-RESPONSIVE PLATFORMER", ui.RED_C_TEXT_DIM, cx, 288)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Your heart rate — or your face — reshapes the run.", ui.RED_C_TEXT, cx, 328)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Capstone build · OpenGL + pygame + Firebase", ui.RED_C_TEXT_DIM, cx, 362)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"Press any key or click to sign in (or continue as guest)",
			ui.RED_C_ACCENT,
			cx,
			ui.frame_h() - 148,
		)
		ui.end_2d()


class LevelSelection:
	def __init__(self):
		ui.sync_frame_dimensions()
		self.next_state = None
		self._bg = ui.MenuBackdropRed(55)
		self._ht = [0.0, 0.0, 0.0, 0.0]
		self.button_width = 440
		self.button_height = 56
		self.button_spacing = 11
		self.CARD = pygame.Rect(0, 0, 720, 540)
		self.CARD.center = (ui.frame_w() // 2, ui.frame_h() // 2 + 16)
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
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		rects = [self.LVL1_RECT, self.LVL2_RECT, self.LVL3_RECT, self.BACK_RECT]
		for i, r in enumerate(rects):
			t = 1.0 if r.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		ui.draw_red_card_gl(self.CARD, 0.4)
		cx = self.CARD.centerx
		ui.red_blit_centered(ui.FONT_RED_HEADING, "Direct deploy", ui.RED_C_RED_BRIGHT, cx, self.CARD.y + 36)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Choose arena · input mode follows", ui.RED_C_TEXT_DIM, cx, self.CARD.y + 88)
		ui.draw_red_nav_button(
			self.LVL1_RECT, "Level 1 — Training grounds", "Recommended first drop", self._ht[0], accent=True
		)
		ui.draw_red_nav_button(self.LVL2_RECT, "Level 2 — Pressure climb", "Tighter timing windows", self._ht[1], accent=False)
		ui.draw_red_nav_button(self.LVL3_RECT, "Level 3 — Work in progress", "Experimental layout", self._ht[2], accent=False)
		ui.draw_red_single_button(self.BACK_RECT, "← Main menu", self._ht[3])
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
		cx = ui.frame_w() // 2
		start_y = ui.frame_h() // 2
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
		glVertex2f(ui.frame_w(), 0)
		glVertex2f(ui.frame_w(), ui.frame_h())
		glVertex2f(0, ui.frame_h())
		glEnd()
		ui.draw_text(f"{self.level_name} Level Complete!", ui.frame_w() // 2 - 180, 100)
		ui.draw_text(f"Time: {self.finish_time:.2f}s", ui.frame_w() // 2 - 140, 180)
		ui.draw_text(f"Deaths: {self.deaths}", ui.frame_w() // 2 - 140, 220)
		ui.draw_text("Leaderboard", ui.frame_w() // 2 - 100, 270)
		y = 310
		if not self.scores:
			ui.draw_text("No scores yet — finish a level (exit door saves automatically).", ui.frame_w() // 2 - 320, y, font=ui.FONT_SUB, color=ui.UI_MUTED_TEXT)
		else:
			for i, score in enumerate(self.scores):
				line = f"{i+1}. {score['player']}  {score['time']:.2f}s  deaths:{score['deaths']}"
				ui.draw_text(line, ui.frame_w() // 2 - 260, y)
				y += 44
		pygame.draw.rect(ui.SCREEN, (100, 100, 100), self.CONTINUE_RECT)
		ui.draw_text("Continue", self.CONTINUE_RECT.centerx - 70, self.CONTINUE_RECT.centery - 15)
		ui.end_2d()


class PauseMenu:
	def __init__(self, previous_state):
		self.previous_state = previous_state
		self.button_width = 320
		self.button_height = 58
		self.spacing = 16
		cx = ui.frame_w() // 2
		start_y = ui.frame_h() // 2 + 30
		self._ht = [0.0, 0.0, 0.0]
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
		mp = pygame.mouse.get_pos()
		rects = [self.RESUME_RECT, self.MENU_RECT, self.QUIT_RECT]
		for i, r in enumerate(rects):
			t = 1.0 if r.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		self.previous_state.draw()
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		ui.red_gl_rect(0, 0, ui.frame_w(), ui.frame_h(), 0, 0, 0, 0.72)
		cy = ui.frame_h() // 2 - 80
		glColor4f(0.7, 0.1, 0.1, 0.4)
		glLineWidth(1.0)
		glBegin(GL_LINES)
		glVertex2f(0, cy)
		glVertex2f(ui.frame_w(), cy)
		glEnd()
		cx = ui.frame_w() // 2
		pw, ph = 420, 340
		px, py = cx - pw // 2, cy - 30
		ui.red_gl_rect(px, py, pw, ph, 0.04, 0.04, 0.08, 0.88)
		ui.red_gl_border(px, py, pw, ph, 0.6, 0.1, 0.1, 0.5, 1.0)
		ui.red_blit_centered(ui.FONT_RED_HEADING, "PAUSED", ui.RED_C_RED_BRIGHT, cx, cy - 20)
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 100, cy + 50)
		glVertex2f(cx + 100, cy + 50)
		glEnd()
		ui.draw_red_single_button(self.RESUME_RECT, "Resume", self._ht[0])
		ui.draw_red_single_button(self.MENU_RECT, "Main Menu", self._ht[1])
		ui.draw_red_single_button(self.QUIT_RECT, "Quit Game", self._ht[2])
		ui.end_2d()


class LeaderboardScreen:
	_RANK_COLORS = [(255, 200, 40), (180, 180, 195), (200, 130, 60)]

	def __init__(self, level_name, next_level, upload_ok=None, upload_err=None, last_run=None):
		ui.sync_frame_dimensions()
		self.level_name = level_name
		self.next_level = next_level
		self._upload_ok = upload_ok
		self._upload_err = upload_err
		self._last_run = last_run
		self.next_state = None
		self._bg = ui.MenuBackdropRed(45)
		self._cont_ht = 0.0
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.scores = fb.get_top_scores(level_name, limit=40)
		self.CONTINUE_RECT = pygame.Rect(0, 0, 380, 58)
		self.CONTINUE_RECT.center = (ui.frame_w() // 2, ui.frame_h() - 100)
		self._reload_timer = 0.0

	def on_enter(self):
		self.scores = fb.get_top_scores(self.level_name, limit=40)

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
		self._bg.update(dt)
		self._reload_timer += dt
		if self._reload_timer >= 1.25:
			self._reload_timer = 0.0
			self.scores = fb.get_top_scores(self.level_name, limit=40)
		t = 1.0 if self.CONTINUE_RECT.collidepoint(pygame.mouse.get_pos()) else 0.0
		self._cont_ht += (t - self._cont_ht) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		cx = ui.frame_w() // 2
		ui.red_blit_centered(ui.FONT_RED_HEADING, "LEADERBOARD", ui.RED_C_RED_BRIGHT, cx, 72)
		ui.red_blit_centered(ui.FONT_RED_LABEL, self.level_name.upper(), ui.RED_C_TEXT_DIM, cx, 128)
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 300, 152)
		glVertex2f(cx + 300, 152)
		glEnd()
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"Firebase Realtime Database · fastest clears (top 40 pulled)",
			ui.RED_C_TEXT_DIM,
			cx,
			162,
		)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"No submit button — your run is saved when you reach the exit door.",
			ui.RED_C_TEXT_DIM,
			cx,
			178,
		)

		y_msg = 200
		if self._upload_ok is True:
			ui.red_blit_centered(
				ui.FONT_RED_SMALL,
				"Saved to online leaderboard.",
				(130, 210, 160),
				cx,
				y_msg,
			)
			y_msg += 36
		elif self._upload_ok is False:
			ui.red_blit_centered(
				ui.FONT_RED_SMALL,
				"Score not saved — check terminal / FIREBASE_DATABASE_URL",
				(240, 140, 140),
				cx,
				y_msg,
			)
			y_msg += 30
			if self._upload_err:
				ui.red_blit_centered(ui.FONT_RED_SMALL, self._upload_err[:120], (200, 160, 160), cx, y_msg)
				y_msg += 32
		if self._last_run:
			lr = self._last_run
			pname = str(lr.get("player", "Player"))
			tm = float(lr.get("time", 0.0))
			dt = int(lr.get("deaths", 0))
			ui.red_blit_centered(
				ui.FONT_RED_MENU,
				f"This run · {pname} · {tm:.2f}s · deaths {dt}",
				ui.RED_C_ACCENT,
				cx,
				y_msg,
			)
			y_msg += 40

		y0 = y_msg + 16
		btn_top = self.CONTINUE_RECT.top
		avail = max(220, btn_top - y0 - 72)
		row_h = 48
		max_rows = max(5, min(18, avail // row_h))
		visible = self.scores[:max_rows]
		if not self.scores:
			ui.red_blit_centered(ui.FONT_RED_LABEL, "No scores for this arena yet.", ui.RED_C_TEXT_DIM, cx, y0 + 40)
			ui.red_blit_centered(
				ui.FONT_RED_SMALL,
				"Finish a level — your time posts automatically when you reach the door",
				ui.RED_C_TEXT_DIM,
				cx,
				y0 + 80,
			)
		else:
			ui.red_blit_left(ui.FONT_RED_SMALL, "RANK", ui.RED_C_TEXT_DIM, cx - 280, y0)
			ui.red_blit_left(ui.FONT_RED_SMALL, "PLAYER", ui.RED_C_TEXT_DIM, cx - 180, y0)
			ui.red_blit_right(ui.FONT_RED_SMALL, "TIME", ui.RED_C_TEXT_DIM, cx + 80, y0)
			ui.red_blit_right(ui.FONT_RED_SMALL, "DEATHS", ui.RED_C_TEXT_DIM, cx + 280, y0)
			if len(self.scores) > len(visible):
				ui.red_blit_centered(
					ui.FONT_RED_SMALL,
					f"Showing top {len(visible)} of {len(self.scores)} loaded",
					ui.RED_C_TEXT_DIM,
					cx,
					y0 - 18,
				)
			glColor4f(0.4, 0.08, 0.08, 0.3)
			glBegin(GL_LINES)
			glVertex2f(cx - 280, y0 + 22)
			glVertex2f(cx + 280, y0 + 22)
			glEnd()
			for i, score in enumerate(visible):
				row_y_top = y0 + 32 + i * row_h
				row_y_mid = row_y_top + 28
				ui.red_gl_rect(cx - 285, row_y_top, 570, row_h - 4, 1, 1, 1, 0.06 if i % 2 == 0 else 0.0)
				rank_col = self._RANK_COLORS[i] if i < 3 else ui.RED_C_TEXT_DIM
				ui.red_blit_left(ui.FONT_RED_MENU, f"#{i + 1}", rank_col, cx - 280, row_y_mid)
				ui.red_blit_left(ui.FONT_RED_MENU, str(score.get("player", "???")), ui.RED_C_TEXT, cx - 180, row_y_mid)
				ui.red_blit_right(ui.FONT_RED_MENU, f"{score['time']:.2f}s", ui.RED_C_ACCENT, cx + 80, row_y_mid)
				ui.red_blit_right(ui.FONT_RED_LABEL, str(score["deaths"]), ui.RED_C_RED, cx + 280, row_y_mid)

		ui.draw_red_single_button(self.CONTINUE_RECT, "Continue", self._cont_ht)
		ui.end_2d()


class LeaderboardHubScreen:
	def __init__(self):
		ui.sync_frame_dimensions()
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self._bg = ui.MenuBackdropRed(50)
		self._ht = [0.0, 0.0, 0.0, 0.0]
		self.CARD = pygame.Rect(0, 0, 760, 660)
		self.CARD.center = (ui.frame_w() // 2, ui.frame_h() // 2 + 12)
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
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		for i, r in enumerate([self.L1, self.L2, self.L3, self.BACK]):
			t = 1.0 if r.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		ui.draw_red_card_gl(self.CARD, 0.4)
		cx = self.CARD.centerx
		ui.red_blit_centered(ui.FONT_RED_HEADING, "Rankings", ui.RED_C_RED_BRIGHT, cx, self.CARD.y + 36)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Clears save at the exit door — no submit step", ui.RED_C_TEXT_DIM, cx, self.CARD.y + 92)
		ui.draw_red_nav_button(self.L1, "Level 1 board", "Top five clears", self._ht[0], accent=True)
		ui.draw_red_nav_button(self.L2, "Level 2 board", "Escalating tempo", self._ht[1], accent=False)
		ui.draw_red_nav_button(self.L3, "Level 3 board", "Experimental route", self._ht[2], accent=False)
		ui.draw_red_single_button(self.BACK, "← Back to main menu", self._ht[3])
		ui.end_2d()


class NameEntryScreen:
	def __init__(self, level_name, finish_time, deaths, next_level):
		ui.sync_frame_dimensions()
		self.level_name = level_name
		self.finish_time = finish_time
		self.deaths = deaths
		self.next_level = next_level
		self.next_state = None
		self.player_name = (gs.current_user or {}).get("display_name") or ""
		self._bg = ui.MenuBackdropRed(40)
		self._submit_ht = 0.0
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.SUBMIT_RECT = pygame.Rect(0, 0, 300, 58)
		self.SUBMIT_RECT.center = (ui.frame_w() // 2, ui.frame_h() - 120)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					return MainMenu()
				if event.key == pygame.K_BACKSPACE:
					self.player_name = self.player_name[:-1]
				elif event.key == pygame.K_RETURN:
					if len(self.player_name.strip()) > 0:
						return self.submit_player_score()
				else:
					if len(self.player_name) < 16 and event.unicode.isprintable():
						self.player_name += event.unicode
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self.SUBMIT_RECT.collidepoint(event.pos) and len(self.player_name.strip()) > 0:
					return self.submit_player_score()
		return None

	def submit_player_score(self):
		name = (self.player_name or "Player").strip()[:64]
		ok, err = fb.submit_score(self.level_name, name, self.finish_time, self.deaths, source="menu_submit")
		last_run = {
			"player": name,
			"time": float(self.finish_time),
			"deaths": int(self.deaths),
			"saved": ok,
		}
		return LeaderboardScreen(
			self.level_name, self.next_level, upload_ok=ok, upload_err=err, last_run=last_run
		)

	def update(self, dt):
		self._bg.update(dt)
		t = 1.0 if self.SUBMIT_RECT.collidepoint(pygame.mouse.get_pos()) else 0.0
		self._submit_ht += (t - self._submit_ht) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		cx = ui.frame_w() // 2
		pw, ph = 560, 460
		px, py = cx - pw // 2, 200
		ui.red_gl_rect(px, py, pw, ph, ui.RED_PANEL[0] / 255, ui.RED_PANEL[1] / 255, ui.RED_PANEL[2] / 255, 0.92)
		ui.red_gl_border(px, py, pw, ph, 0.55, 0.08, 0.08, 0.6, 1.5)
		ui.red_gl_rect(px, py, pw, 3, 0.8, 0.15, 0.15, 0.9)
		ui.red_blit_centered(ui.FONT_RED_HEADING, "LEVEL COMPLETE", ui.RED_C_RED_BRIGHT, cx, 228)
		glColor4f(0.5, 0.08, 0.08, 0.35)
		glBegin(GL_LINES)
		glVertex2f(px + 30, 308)
		glVertex2f(px + pw - 30, 308)
		glEnd()
		col_l = cx - 120
		col_r = cx + 120
		ui.red_blit_centered(ui.FONT_RED_SMALL, "TIME", ui.RED_C_TEXT_DIM, col_l, 328)
		ui.red_blit_centered(ui.FONT_RED_MENU, f"{self.finish_time:.2f}s", ui.RED_C_ACCENT, col_l, 358)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "DEATHS", ui.RED_C_TEXT_DIM, col_r, 328)
		ui.red_blit_centered(ui.FONT_RED_MENU, str(self.deaths), ui.RED_C_RED_BRIGHT, col_r, 358)
		glColor4f(0.5, 0.08, 0.08, 0.35)
		glBegin(GL_LINES)
		glVertex2f(px + 30, 418)
		glVertex2f(px + pw - 30, 418)
		glEnd()
		ui.red_blit_centered(ui.FONT_RED_LABEL, "ENTER YOUR NAME", ui.RED_C_TEXT_DIM, cx, 438)
		iw, ih = 380, 56
		ix, iy = cx - iw // 2, 472
		ui.red_gl_rect(ix, iy, iw, ih, 0.06, 0.06, 0.10, 1.0)
		ui.red_gl_border(ix, iy, iw, ih, 0.6, 0.12, 0.12, 0.7, 1.0)
		show_cursor = (pygame.time.get_ticks() // 530) % 2 == 0
		display_name = self.player_name + ("|" if show_cursor else " ")
		ui.red_blit_centered(ui.FONT_RED_MENU, display_name, ui.RED_C_WHITE, cx, iy + 36)
		ui.draw_red_single_button(self.SUBMIT_RECT, "Submit Score", self._submit_ht)
		ui.red_blit_centered(ui.FONT_RED_SMALL, "Esc — main menu without saving", ui.RED_C_TEXT_DIM, cx, ui.frame_h() - 36)
		ui.end_2d()


class ModeSelection:
	def __init__(self):
		ui.sync_frame_dimensions()
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.training_mode = False
		self.next_state = None
		self.target_level = "level1"
		self._bg = ui.MenuBackdropRed(50)
		self._ht = [0.0, 0.0, 0.0]
		self.button_width = 420
		self.button_height = 90
		self.button_spacing = 16
		cx = ui.frame_w() // 2
		base_y = 420
		self.MODE1_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE1_RECT.center = (cx, base_y)
		self.MODE2_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE2_RECT.center = (cx, base_y + self.button_height + self.button_spacing)
		self.TRAIN_RECT = pygame.Rect(0, 0, self.button_width, 52)
		self.TRAIN_RECT.center = (cx, base_y + 2 * (self.button_height + self.button_spacing) + 24)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					return "main_menu"
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
				mp = event.pos
				if self.MODE1_RECT.collidepoint(mp):
					gs.input_mode = InputMode.HEART_RATE
					gs.training_mode = self.training_mode
					return self.target_level
				if self.MODE2_RECT.collidepoint(mp):
					gs.input_mode = InputMode.EMOTION
					gs.training_mode = self.training_mode
					return self.target_level
				if self.TRAIN_RECT.collidepoint(mp):
					self.training_mode = not self.training_mode
		return None

	def update(self, dt):
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		self._ht[0] += ((1.0 if self.MODE1_RECT.collidepoint(mp) else 0.0) - self._ht[0]) * min(1.0, dt * 12)
		self._ht[1] += ((1.0 if self.MODE2_RECT.collidepoint(mp) else 0.0) - self._ht[1]) * min(1.0, dt * 12)
		self._ht[2] += ((1.0 if self.TRAIN_RECT.collidepoint(mp) else 0.0) - self._ht[2]) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*ui.RED_CLEAR_RGB, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		ui.begin_2d()
		ui.init_red_theme_fonts()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()
		cx = ui.frame_w() // 2
		ui.red_blit_centered(ui.FONT_RED_HEADING, "SELECT MODE", ui.RED_C_RED_BRIGHT, cx, 120)
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 220, 188)
		glVertex2f(cx + 220, 188)
		glEnd()
		ui.red_blit_centered(ui.FONT_RED_LABEL, "Choose how your body controls the run", ui.RED_C_TEXT_DIM, cx, 202)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"Keys: 1 Heart rate  ·  2 Emotion  ·  T Training  ·  Esc Main menu",
			ui.RED_C_TEXT_DIM,
			cx,
			232,
		)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"Emotion route: webcam + OpenCV / DeepFace / TensorFlow",
			ui.RED_C_TEXT_DIM,
			cx,
			258,
		)
		ui.draw_red_nav_button(self.MODE1_RECT, "", "", self._ht[0], accent=True)
		ui.red_blit_centered(ui.FONT_RED_MENU, "Heart rate (BPM)", ui.RED_C_TEXT, cx, self.MODE1_RECT.top + 14)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"BLE / Pulsoid + UDP fallback  ·  press 1",
			ui.RED_C_TEXT_DIM,
			cx,
			self.MODE1_RECT.top + 50,
		)
		ui.draw_red_nav_button(self.MODE2_RECT, "", "", self._ht[1], accent=False)
		ui.red_blit_centered(ui.FONT_RED_MENU, "Facial emotion", ui.RED_C_TEXT, cx, self.MODE2_RECT.top + 14)
		ui.red_blit_centered(
			ui.FONT_RED_SMALL,
			"Webcam + DeepFace  ·  press 2",
			ui.RED_C_TEXT_DIM,
			cx,
			self.MODE2_RECT.top + 50,
		)
		tr_on = self.training_mode
		tr_bg = (10, 30, 10) if tr_on else ui.RED_PANEL
		ui.red_gl_rect(
			self.TRAIN_RECT.x,
			self.TRAIN_RECT.y,
			self.TRAIN_RECT.w,
			self.TRAIN_RECT.h,
			tr_bg[0] / 255,
			tr_bg[1] / 255,
			tr_bg[2] / 255,
			0.9,
		)
		tr_bc = (60, 200, 60) if tr_on else (60, 60, 60)
		ui.red_gl_border(
			self.TRAIN_RECT.x,
			self.TRAIN_RECT.y,
			self.TRAIN_RECT.w,
			self.TRAIN_RECT.h,
			tr_bc[0] / 255,
			tr_bc[1] / 255,
			tr_bc[2] / 255,
			0.8,
			1.0,
		)
		status_col = (80, 220, 80) if tr_on else ui.RED_C_TEXT_DIM
		status_label = "Training mode  ·  ON  [T]" if tr_on else "Training mode  ·  OFF  [T]"
		ui.red_blit_centered(ui.FONT_RED_LABEL, status_label, status_col, cx, self.TRAIN_RECT.top + 14)
		ui.end_2d()
