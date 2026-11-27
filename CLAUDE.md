# Video Production Rules

## Render & Export Standards
- Always render videos at `1080x1920` (9:16 vertical) and `60fps`: 2D scenes with Manim Community Edition, 3D scenes with Blender (see "3D Scene Standards" below).
- Every short must run at least 30 seconds (`1800` frames at 60fps). Fill the time with more story beats and acting, never by slowing the motion down or holding a still.
- Save all final rendered `.mp4` files into the `output/` folder so they are easy to access and download on mobile.
- Always execute the Manim render command after creating or editing a scene to verify zero syntax or rendering errors.
- Default render command:
  `manim -qh --resolution 1080,1920 --fps 60 --media_dir temp scenes/<script>.py <SceneName> && cp temp/videos/<script>/1920p60/<SceneName>.mp4 output/`

## Visual Aesthetic & Rigging Guidelines (2D Manim scenes)
- **Canvas:** Pure `#000000` black background (`config.frame_width = 9`, `config.frame_height = 16`).
- **Floor Reflection:** Place a floor plane at `y = -2.2` and render a mirrored upside-down reflection of foreground characters, objects, and glow elements at `15%–20%` opacity.
- **Characters:** Use thick rounded white vector strokes (`#FFFFFF`, `stroke_width=14`), separated circular heads, articulated shoulder/elbow/hip/knee joints, and subtle layered radial glow halos.
- **Lighting & Mood:** Use concentric translucent circles (`fill_opacity` tapering from `0.18` to `0.0`) to simulate volumetric red/orange conflict fire and warm white resolution spotlights.
- **Typography:** Use clean uppercase bold sans-serif text (`font="DejaVu Sans"`, `weight=BOLD`) centered near `y = 4.8`.

## 3D Scene Standards (Blender scenes)
Reference implementation: `scenes/mountain_climb.py`. New 3D scenes must match its level of polish.

### Render
- Engine: Eevee on Blender `4.1.1` (the GitHub workflow pins it; 4.2+ is far slower without a GPU and has no bloom). `1080x1920`, `60fps`, H.264 MP4.
- `scene.eevee.taa_render_samples = 16`. Use the `Standard` view transform so emission `1.0` is exactly white.
- The script takes its output path after `--` and must support `SHORTS_CHUNK=i/N` (render the i-th of N slices of the frame range; the workflow renders twelve in parallel and joins them), `SHORTS_STILL=<frame>` (one preview frame) and `SHORTS_SAMPLES`.
- Render command (Eevee needs a display, so use `xvfb-run` on headless machines):
  `xvfb-run -a blender -b -P scenes/<script>.py -- output/<script>.mp4`
- Before a full render, preview stills from every act (`SHORTS_STILL`) and run the safe-zone check (`SHORTS_CHECK=1`).

### HUD Text
- Captions are text objects parented to the camera, so they are locked in the frame. Centre them in the top safe zone: the top 20% of the frame (`HUD_CENTER = 0.78` of the half-height above centre), longest line 70% of the frame width.
- Uppercase bold DejaVu Sans, pure white. Material: black base colour, `Emission Strength = 1.0`. No bloom on text: keep `bloom_threshold` above `1.0` (currently `1.4`) so only the strong emitters glow.
- Nothing important (character head, summit, flag, props) may enter the caption zone at any frame, including during camera moves. Aim the camera so they stay below 80% of the frame height, and verify with a per-frame projection check (`world_to_camera_view`), as `SHORTS_CHECK=1` does.

### Character Rigging
- Stick figure in the 2D style: thick rounded white limbs (`radius 0.05`), round head (`radius 0.17`) floating just above the neck, black outline (inverted-hull Solidify, thickness `0.022`), white emission `0.65`.
- Use `FusedFigure` from `lib/blender_rig.py` rather than rebuilding the rig. Every limb segment is a capsule (cylinder with hemispherical caps), so shoulders, elbows, hips and knees are spherical joints with no floating gaps. The segments are gathered into one object and fused with a voxel remesh before the outline modifier, so the outline traces the whole silhouette and no rings show at the joints. Do not fuse with a Boolean union: it drops the whole body on some poses.
- Pose from joint positions, not hand-placed parts: compute joints with two-bone IK (`bend`), plant feet on the terrain height function, and bake one keyframe per frame.
- Motion must be acted, not static: give the character an entrance and a settled end pose (e.g. limp up the last steps, turn, sit down cleanly). Seated pose: hips on the ground, knees bent, feet planted, hands resting on the knees, head dropping last.

### Terrain
- Height comes from a single `mountain_height(x, y)` function that everything else (trail, feet, props, camera) samples, so nothing floats or sinks.
- Shape: a creased ridge (`|x|^1.45` profile, not a smooth Gaussian) plus multi-octave ridged noise (large rock spurs and small facet chips). Fade the detail out along the path the character and trail use.
- Dense mesh (about `220 x 260`) with flat shading for crisp facets. Material by slope: snow on gentle faces, dark rock on steep ones.

### Atmosphere & Light
- Night sky: dark zenith with a soft band of blue-grey mist along the horizon (smoothstep gradient, subtle), small emissive stars.
- Mist on the terrain: blend toward the mist colour with distance from the camera and toward the valley floor. Keep it subtle; the foreground stays clear.
- Cool moonlight sun. Bloom only on the strong emitters (trail, flag, stars).

### Glowing Trail
- A bevelled curve sampled densely on the terrain (lifted about `0.07`), golden emission `4.5`.
- Tapered: full width at the character, thinning naturally toward the valley (per-point radius from `1.0` down to about `0.28`). It must end exactly where the character is.


### Split-Screen Scenes
- Build two `1080x960` panels and stack them with `render_split_screen` from `lib/side_view.py` (reference: `scenes/what_people_see.py`, `scenes/discipline.py`). It handles `SHORTS_CHUNK`, `SHORTS_STILL` and `SHORTS_CHECK` and needs `ffmpeg` on the PATH.
- Side-view figures are posed with the pose dictionaries in `lib/side_view.py` (`stand`, `walk`, `mix`, `chain`), which feed `FusedFigure`.
- Each panel gets its own caption in its own top safe zone, and the safe-zone rule applies per panel. Keep bright set dressing (windows, lamps) below the caption zone too.
- Frame the figure large: it should fill roughly 40% of the panel height or more.
