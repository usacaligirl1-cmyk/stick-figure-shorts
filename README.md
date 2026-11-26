# Stick Figure Shorts Studio

Automated 1080x1920 (9:16) 60fps minimalist vector storytelling studio powered by **Manim Community Edition**, **FFmpeg**, and **Claude Code**.

## Quick Start (Mobile & Cloud)
1. Upload these files to a new GitHub repository (`stick-figure-shorts`).
2. Open the repository in **Claude Code on the web (`claude.ai/code`)** or **GitHub Codespaces**.
3. Ask Claude Code to generate or modify scenes and render them directly into `/output`.

## Manual Render Command
```bash
manim -qh --resolution 1080,1920 --fps 60 scenes/wall_story.py WallStory -o wall_story.mp4
```
