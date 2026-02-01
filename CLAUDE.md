# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Naver Blog Auto Blogger Pro (v3.10.3) — a Python desktop application that automates Naver blog posting using AI-generated content. Combines PySide6 GUI, Selenium browser automation, Google Gemini AI for content/image generation, and Firebase for auth and backend.

## Running the Application

```bash
pip install -r requirements.txt
python main.py              # GUI mode (default)
python main.py --cli        # CLI mode
python main.py --debug      # Debug mode
```

Environment variables needed in `.env`: `GEMINI_API_KEY`, `FIREBASE_API_KEY`, `BACKEND_URL`.

## Deploying Firebase Functions

```bash
cd functions
pip install -r requirements.txt
firebase deploy --only functions
```

## Architecture

**Entry point:** `main.py` — parses args, launches PySide6 `MainWindow` (GUI) or CLI.

**Core flow:**
1. User logs in via Firebase Auth (`ui/login_dialog.py`)
2. User configures post settings in tabbed UI (`ui/` modules)
3. `core/worker.py` runs `AutomationWorker` (QThread) to call backend API for content generation
4. `automation.py` (`NaverBlogBot`) drives Chrome via Selenium to publish on Naver Blog
5. Posts are tracked in SQLite (`post_history.db`) via `core/post_history.py`

**Content publishing has two paths:**
- **DOM manipulation:** Direct Selenium element interaction with formatting
- **JSON API:** Builds structured document via `naver_editor.py` (`NaverDocument`) and posts to Naver's RabbitWrite API

**Key modules:**
- `config.py` — app constants, API URLs, timeouts, Gemini model names
- `core/content_converter.py` — converts markdown/text into Naver editor block format
- `core/image_generator.py` — Gemini-based blog image generation
- `core/hashtag_generator.py` — auto hashtag generation
- `ui/styles.py` — Qt stylesheets

## Anti-Detection

The Selenium automation uses clipboard-based input (`pyperclip`), custom user agents, and `navigator.webdriver` removal to avoid bot detection. Changes to these mechanisms should be made carefully.

## Important Notes

- UI and all content are in Korean
- No test suite or linting config exists currently
- Naver blog editor selectors in `automation.py` are fragile — they break when Naver updates their frontend
- Chrome/Chromium must be installed; `webdriver-manager` handles ChromeDriver
