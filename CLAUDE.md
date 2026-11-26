# Video Production Rules

## Render & Export Standards
- Always render videos using Manim Community Edition at `1080x1920` (9:16 vertical) and `60fps`.
- Save all final rendered `.mp4` files into the `output/` folder so they are easy to access and download on mobile.
- Always execute the Manim render command after creating or editing a scene to verify zero syntax or rendering errors.
- Default render command:
  `manim -qh --resolution 1080,1920 --fps 60 --media_dir temp scenes/<script>.py <SceneName> && cp temp/videos/<script>/1920p60/<SceneName>.mp4 output/`

## Visual Aesthetic & Rigging Guidelines
- **Canvas:** Pure `#000000` black background (`config.frame_width = 9`, `config.frame_height = 16`).
- **Floor Reflection:** Place a floor plane at `y = -2.2` and render a mirrored upside-down reflection of foreground characters, objects, and glow elements at `15%–20%` opacity.
- **Characters:** Use thick rounded white vector strokes (`#FFFFFF`, `stroke_width=14`), separated circular heads, articulated shoulder/elbow/hip/knee joints, and subtle layered radial glow halos.
- **Lighting & Mood:** Use concentric translucent circles (`fill_opacity` tapering from `0.18` to `0.0`) to simulate volumetric red/orange conflict fire and warm white resolution spotlights.
- **Typography:** Use clean uppercase bold sans-serif text (`font="DejaVu Sans"`, `weight=BOLD`) centered near `y = 4.8`.
