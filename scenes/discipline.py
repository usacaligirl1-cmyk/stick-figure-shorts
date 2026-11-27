# Split-screen short: the same morning routine, motivated (top) and unmotivated (bottom).
#
# Render command (Blender; Eevee needs a display, so wrap in xvfb-run on headless machines;
# the two panels are stacked with ffmpeg, which must be on the PATH):
# xvfb-run -a blender -b -P scenes/discipline.py -- output/discipline.mp4
#
# Render one slice for parallel rendering (the workflow does this, then joins the slices):
# SHORTS_CHUNK=2/6 xvfb-run -a blender -b -P scenes/discipline.py -- output/part_02.mp4
#
# Preview a single frame instead of the full video:
# SHORTS_STILL=300 xvfb-run -a blender -b -P scenes/discipline.py -- output/preview.png
#
# Check that the figure never enters the caption zone (no render):
# SHORTS_CHECK=1 blender -b -P scenes/discipline.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.side_view import DESK_EXIT, build_morning_room, output_path_from_args, render_split_screen  # noqa: E402

# Captions: (text, first frame, frame it disappears or None). The bottom caption changes
# as the unmotivated figure gets up from the desk and heads for the shower anyway.
SWITCH = DESK_EXIT["unmotivated"]
TOP_CAPTIONS = [("MOTIVATED", 1, None)]
BOTTOM_CAPTIONS = [("UNMOTIVATED", 1, SWITCH), ("DISCIPLINE IS\nDOING IT ANYWAY", SWITCH, None)]

render_split_screen(
    "discipline",
    (
        lambda: build_morning_room("motivated", TOP_CAPTIONS),
        lambda: build_morning_room("unmotivated", BOTTOM_CAPTIONS),
    ),
    output_path_from_args("output/discipline.mp4"),
)
