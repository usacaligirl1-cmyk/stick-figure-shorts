# Stick Figure Shorts Studio

Automated 1080x1920 (9:16) 60fps minimalist vector storytelling studio powered by **Manim Community Edition**, **FFmpeg**, and **Claude Code**.

## Layout
- `scenes/` — scene scripts, one file per short. Manim (2D): `wall_story.py`, `tug_of_war.py`. Blender (3D): `mountain_climb.py`, and the split-screen `what_people_see.py` and `discipline.py`.
- `lib/blender_rig.py`, `lib/side_view.py` — shared 3D helpers: fused stick figure, captions, side-view poses, split-screen rendering.
- `lib/rig.py` — shared rig for new scenes: posable stick figure, floor reflections, glows, titles.
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

## Blender (3D) Render Command
Blender's Eevee renderer needs a display, so wrap it in `xvfb-run` on headless machines:
```bash
xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/mountain_climb.mp4
```
Without a GPU this is slow, so the GitHub workflow renders six slices of the frame range on parallel runners (`SHORTS_CHUNK=i/N`) and joins them with FFmpeg. It pins Blender 4.1.1.

Check that nothing enters the caption zone with `SHORTS_CHECK=1` (no render). Preview one frame with `SHORTS_STILL=300` (write to a `.png`), or raise quality with `SHORTS_SAMPLES=64` (much slower without a GPU).
