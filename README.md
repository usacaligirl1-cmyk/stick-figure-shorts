# Stick Figure Shorts Studio

Automated 1080x1920 (9:16) 60fps minimalist vector storytelling studio powered by **Manim Community Edition**, **FFmpeg**, and **Claude Code**.

## Layout
- `scenes/` — Manim scene scripts (one file per short).
- `output/` — final rendered `.mp4` files, ready to download.
- `temp/` — Manim's working files (ignored by git).
- `CLAUDE.md` — render and visual style rules.

## Quick Start (Mobile & Cloud)
1. Open the repository in **Claude Code on the web (`claude.ai/code`)** or **GitHub Codespaces**.
2. Ask Claude Code to generate or modify scenes in `scenes/`.
3. Download the finished videos from `output/`.

## Manual Render Command
```bash
manim -qh --resolution 1080,1920 --fps 60 --media_dir temp scenes/wall_story.py WallStory && cp temp/videos/wall_story/1920p60/WallStory.mp4 output/
```
