"""Side-view split-screen shorts: a 2D-style pose system driving the fused 3D figure,
plus the "morning routine" bedroom set (bed -> workout mat -> desk -> shower).

Scenes build two 1080x960 panels and hand them to `render_split_screen`."""

import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector

from lib.blender_rig import (
    FOREARM, HEAD_RADIUS, HIP_HALF, LIMB_RADIUS, NECK_GAP, SHIN, SHOULDER_HALF, SPINE_LENGTH,
    THIGH, UP, UPPER_ARM, FusedFigure, add_hud_text, bend, chunk_range, lerp, make_material,
    safe_zone_check, set_still_output, set_video_output, setup_render, show_between, smoothstep,
)

FIRST_FRAME, LAST_FRAME = 1, 600  # 10 seconds at 60fps
PANEL_WIDTH, PANEL_HEIGHT = 1080, 960  # two panels stack into 1080x1920

# ---------------------------------------------------------------------------- layout
# Four zones along X, close enough together that the figure can walk between them
# at a believable pace: bed -> workout mat -> desk -> shower.
BED_X = -3.30
BED_TOP = 0.56
BED_EXIT_X = BED_X + 1.25      # standing at the foot of the bed
MAT_X = -1.30
PLANK_FEET_X = MAT_X - 0.68
PLANK_HANDS_X = MAT_X + 0.67
PRE_PLANK_X = MAT_X - 0.20     # where the figure stands before dropping to the mat
MAT_EXIT_X = MAT_X - 0.10
CHAIR_X = 0.25
SEAT_TOP = 0.48
DESK_X = CHAIR_X + 0.65
DESK_TOP = 0.76
CHAIR_APPROACH_X = CHAIR_X - 0.25
SHOWER_X = 2.45

LANE_Y = -0.35                 # walking lane, in front of the furniture
FOOT_Z = LIMB_RADIUS + 0.01
STAND_Z = 0.90                 # hip height when standing (knees a touch bent)
LEG_LINE = 0.895               # hip-to-foot length with the leg straight
BODY_LINE = LEG_LINE + 0.56    # foot-to-shoulder length in a plank

# ----------------------------------------------------------------------------- poses
# A pose is a dict in the side-view plane:
#   x, z   pelvis position        y      depth (distance into the room)
#   lean   torso tilt in degrees, positive toward +X (the direction of travel)
#   head   extra forward tilt of the head, degrees
#   fl, fr (x, z) foot targets    kh     knee fold direction (x, z)
#   hl, hr hand targets: ("rel", dx, dz) from the shoulder or ("abs", x, z)
#   eh     elbow fold direction (x, z)


def stand(x, slump=0.0, y=LANE_Y):
    return dict(
        x=x, z=STAND_Z - 0.03 * slump, y=y, lean=3.0 + 20.0 * slump, head=4.0 + 24.0 * slump,
        fl=(x - 0.03, FOOT_Z), fr=(x + 0.03, FOOT_Z), kh=(1.0, 0.4),
        hl=("rel", 0.04 + 0.10 * slump, -0.56), hr=("rel", 0.00 + 0.10 * slump, -0.56), eh=(-1.0, -0.2),
    )


def lie_in_bed():
    x, z = BED_X + 0.05, BED_TOP + LIMB_RADIUS + 0.01
    return dict(
        x=x, z=z, y=0.5, lean=-90.0, head=0.0,
        fl=(x + 0.88, z), fr=(x + 0.88, z), kh=(0.0, 1.0),
        hl=("abs", x - 0.08, z + 0.02), hr=("abs", x - 0.08, z + 0.02), eh=(0.0, 1.0),
    )


def sit_up_in_bed(slump=0.0):
    pose = lie_in_bed()
    pose.update(lean=-12.0 + 40.0 * slump, head=2.0 + 26.0 * slump,
                hl=("rel", 0.16, -0.50), hr=("rel", 0.12, -0.50), eh=(-1.0, 0.2))
    return pose


def sit_on_bed_end(slump=0.0, droop=0.0):
    x, z = BED_X + 0.83, BED_TOP + LIMB_RADIUS + 0.01
    return dict(
        x=x, z=z, y=0.5, lean=8.0 + 30.0 * slump, head=5.0 + 26.0 * slump + 18.0 * droop,
        fl=(x + 0.44, FOOT_Z), fr=(x + 0.48, FOOT_Z), kh=(1.0, 1.0),
        hl=("rel", 0.22, -0.42), hr=("rel", 0.20, -0.42), eh=(-1.0, -0.3),
    )


def crouch(feet_x):
    """Deep squat with the hands planted on the mat, the way into and out of a plank."""
    return dict(
        x=feet_x + 0.15, z=0.36, y=0.3, lean=70.0, head=-20.0,
        fl=(feet_x - 0.03, FOOT_Z), fr=(feet_x + 0.03, FOOT_Z), kh=(1.0, 1.0),
        hl=("abs", PLANK_HANDS_X, LIMB_RADIUS), hr=("abs", PLANK_HANDS_X, LIMB_RADIUS), eh=(-1.0, 0.6),
    )


def plank(shoulder_height, sag=0.0):
    """Straight body from the feet to the shoulders, hands under the shoulders."""
    angle = math.asin((shoulder_height - FOOT_Z) / BODY_LINE)
    return dict(
        x=PLANK_FEET_X + LEG_LINE * math.cos(angle), z=FOOT_Z + LEG_LINE * math.sin(angle) - sag, y=0.3,
        lean=90.0 - math.degrees(angle), head=-28.0,
        fl=(PLANK_FEET_X, FOOT_Z), fr=(PLANK_FEET_X, FOOT_Z), kh=(0.0, 1.0),
        hl=("abs", PLANK_HANDS_X, LIMB_RADIUS), hr=("abs", PLANK_HANDS_X, LIMB_RADIUS), eh=(-1.0, 0.6),
    )


def seated(slouch=0.0, tap_l=0.0, tap_r=0.0):
    x, z = CHAIR_X, SEAT_TOP + LIMB_RADIUS + 0.01
    keys_x = x + 0.42 + 0.06 * slouch
    return dict(
        x=x, z=z, y=0.4, lean=6.0 + 28.0 * slouch, head=8.0 + 24.0 * slouch,
        fl=(x + 0.36, FOOT_Z), fr=(x + 0.42, FOOT_Z), kh=(1.0, 1.0),
        hl=("abs", keys_x, DESK_TOP + 0.06 + tap_l), hr=("abs", keys_x + 0.06, DESK_TOP + 0.06 + tap_r),
        eh=(-1.0, -0.5),
    )


def showering(slump=0.0, scrub=0.0):
    pose = stand(SHOWER_X, slump, y=0.4)
    if slump < 0.5:
        # Energised: both hands up, scrubbing the hair
        crown = STAND_Z + SPINE_LENGTH + NECK_GAP + 2 * HEAD_RADIUS
        pose.update(
            hl=("abs", SHOWER_X + 0.10 + 0.07 * math.sin(scrub), crown + 0.02 + 0.03 * math.cos(scrub)),
            hr=("abs", SHOWER_X - 0.02 - 0.07 * math.sin(scrub), crown + 0.02 - 0.03 * math.cos(scrub)),
            eh=(1.0, 0.1), lean=2.0, head=6.0,
        )
    return pose


def shoulder_of(pose):
    lean = math.radians(pose["lean"])
    return pose["x"] + SPINE_LENGTH * math.sin(lean), pose["z"] + SPINE_LENGTH * math.cos(lean)


def hand_point(pose, key, shoulder):
    kind, a, b = pose[key]
    return (a, b) if kind == "abs" else (shoulder[0] + a, shoulder[1] + b)


def mix(a, b, t):
    """Blend two poses. Hands are blended as points in space."""
    out = {k: lerp(a[k], b[k], t) for k in ("x", "z", "y", "lean", "head")}
    for k in ("fl", "fr", "kh", "eh"):
        out[k] = (lerp(a[k][0], b[k][0], t), lerp(a[k][1], b[k][1], t))
    for k in ("hl", "hr"):
        pa, pb = hand_point(a, k, shoulder_of(a)), hand_point(b, k, shoulder_of(b))
        out[k] = ("abs", lerp(pa[0], pb[0], t), lerp(pa[1], pb[1], t))
    return out


def chain(frame, keys):
    """Ease through a list of (frame, pose) keys."""
    if frame <= keys[0][0]:
        return keys[0][1]
    for (f0, p0), (f1, p1) in zip(keys, keys[1:]):
        if frame <= f1:
            return mix(p0, p1, smoothstep(f0, f1, frame))
    return keys[-1][1]


def hop(pose, t, height):
    """Lift both feet through a transition (the kick back into a plank and the jump out)."""
    lift = height * math.sin(math.pi * t)
    pose["fl"] = (pose["fl"][0], pose["fl"][1] + lift)
    pose["fr"] = (pose["fr"][0], pose["fr"][1] + lift)
    return pose


def walk(x_from, x_to, u, steps, slump=0.0, lift=0.09, y_from=LANE_Y, y_to=LANE_Y):
    """Walk from one standing spot to another in `steps` alternating steps; u runs 0..1.
    The feet start and end together, so it joins cleanly onto a standing pose."""
    distance = x_to - x_from

    def plant(k):  # where step k puts its foot down
        return x_from + distance * min(1.0, (k + 1) / max(1, steps - 1))

    u = max(0.0, min(1.0, u))
    index = min(steps - 1, int(u * steps))
    tau = u * steps - index
    feet = [x_from, x_from]
    for k in range(index):
        feet[k % 2] = plant(k)
    swing = smoothstep(0.0, 1.0, tau)
    moving = index % 2
    feet[moving] = lerp(feet[moving], plant(index), swing)
    heights = [FOOT_Z, FOOT_Z]
    heights[moving] += lift * math.sin(math.pi * swing)

    edge = min(1.0, 4.0 * u, 4.0 * (1.0 - u))  # ease the gait in and out of standing
    pose = stand(lerp(x_from, x_to, u), slump, y=lerp(y_from, y_to, smoothstep(0.0, 1.0, u)))
    pose["z"] -= edge * (0.03 + 0.03 * abs(math.cos(math.pi * tau)))
    pose["lean"] += edge * (7.0 - 3.0 * slump)
    pose["fl"], pose["fr"] = (feet[0], heights[0]), (feet[1], heights[1])
    arm = edge * (0.20 - 0.12 * slump) * math.cos(math.pi * (index + tau))
    pose["hl"] = ("rel", pose["hl"][1] + arm, pose["hl"][2])
    pose["hr"] = ("rel", pose["hr"][1] - arm, pose["hr"][2])
    return pose


# --------------------------------------------------------------------- choreography
# Both figures do the same four things. The motivated one is brisk and upright; the
# unmotivated one is slow, heavy and slouched, but still gets through all of it.

def motivated(frame):
    f = float(frame)
    if f <= 36:   # springs out of bed
        return chain(f, [(1, lie_in_bed()), (12, sit_up_in_bed()), (24, sit_on_bed_end()),
                         (36, stand(BED_EXIT_X))])
    if f <= 52:
        return walk(BED_EXIT_X, PRE_PLANK_X, (f - 36) / 16, steps=2)
    if f <= 62:   # hands down
        return mix(stand(PRE_PLANK_X), crouch(PRE_PLANK_X), smoothstep(52, 62, f))
    if f <= 72:   # kick back into a plank
        t = smoothstep(62, 72, f)
        return hop(mix(crouch(PRE_PLANK_X), plank(0.60), t), t, 0.10)
    if f <= 212:  # four quick push-ups
        down = 0.5 - 0.5 * math.cos(2.0 * math.pi * (f - 72) / 35.0)
        return plank(lerp(0.60, 0.22, down))
    if f <= 222:  # jump the feet back in
        t = smoothstep(212, 222, f)
        return hop(mix(plank(0.60), crouch(MAT_EXIT_X), t), t, 0.10)
    if f <= 234:
        return mix(crouch(MAT_EXIT_X), stand(MAT_EXIT_X), smoothstep(222, 234, f))
    if f <= 282:
        return walk(MAT_EXIT_X, CHAIR_APPROACH_X, (f - 234) / 48, steps=4)
    if f <= 298:
        return mix(stand(CHAIR_APPROACH_X), seated(), smoothstep(282, 298, f))
    if f <= 430:  # focused typing
        return seated(tap_l=0.03 * max(0.0, math.sin(f * 0.9)), tap_r=0.03 * max(0.0, math.sin(f * 0.9 + 2.0)))
    if f <= 444:
        return mix(seated(), stand(CHAIR_APPROACH_X), smoothstep(430, 444, f))
    if f <= 500:  # jogs to the shower
        return walk(CHAIR_APPROACH_X, SHOWER_X, (f - 444) / 56, steps=5, lift=0.14, y_to=0.4)
    arms_up = smoothstep(500, 512, f)
    return mix(stand(SHOWER_X, y=0.4), showering(scrub=(f - 500) * 0.22), arms_up)


def unmotivated(frame):
    f = float(frame)
    if f <= 128:  # drags itself out of bed
        return chain(f, [(1, lie_in_bed()), (40, lie_in_bed()), (78, sit_up_in_bed(1.0)),
                         (104, sit_on_bed_end(1.0)), (114, sit_on_bed_end(1.0, droop=1.0)),
                         (128, stand(BED_EXIT_X, 1.0))])
    if f <= 156:
        return walk(BED_EXIT_X, PRE_PLANK_X, (f - 128) / 28, steps=3, slump=1.0, lift=0.04)
    if f <= 172:
        return mix(stand(PRE_PLANK_X, 1.0), crouch(PRE_PLANK_X), smoothstep(156, 172, f))
    if f <= 186:
        t = smoothstep(172, 186, f)
        return hop(mix(crouch(PRE_PLANK_X), plank(0.58, sag=0.03), t), t, 0.04)
    if f <= 306:  # two slow, heavy push-ups
        down = 0.5 - 0.5 * math.cos(2.0 * math.pi * (f - 186) / 60.0)
        return plank(lerp(0.58, 0.18, down), sag=0.03 + 0.03 * down)
    if f <= 322:
        t = smoothstep(306, 322, f)
        return hop(mix(plank(0.58, sag=0.03), crouch(MAT_EXIT_X), t), t, 0.04)
    if f <= 342:
        return mix(crouch(MAT_EXIT_X), stand(MAT_EXIT_X, 1.0), smoothstep(322, 342, f))
    if f <= 412:
        return walk(MAT_EXIT_X, CHAIR_APPROACH_X, (f - 342) / 70, steps=4, slump=1.0, lift=0.04)
    if f <= 432:
        return mix(stand(CHAIR_APPROACH_X, 1.0), seated(1.0), smoothstep(412, 432, f))
    if f <= 470:  # slouched, pecking at the keys
        return seated(1.0, tap_l=0.03 * max(0.0, math.sin(f * 0.3)), tap_r=0.03 * max(0.0, math.sin(f * 0.3 + 2.4)))
    if f <= 486:
        return mix(seated(1.0), stand(CHAIR_APPROACH_X, 1.0), smoothstep(470, 486, f))
    if f <= 588:  # trudges to the shower
        return walk(CHAIR_APPROACH_X, SHOWER_X, (f - 486) / 102, steps=6, slump=1.0, lift=0.04, y_to=0.4)
    return showering(slump=1.0)


ROUTINES = {"motivated": motivated, "unmotivated": unmotivated}
SHOWER_ARRIVAL = {"motivated": 500, "unmotivated": 588}
BLANKET_SLIDE = {"motivated": (3, 14), "unmotivated": (44, 80)}


def joints_of(pose):
    """World-space joints for a side-view pose."""
    y = pose["y"]

    def point(x, z, depth=0.0):
        return Vector((x, y + depth, z))

    lean = math.radians(pose["lean"])
    look = lean + math.radians(pose["head"])
    pelvis = point(pose["x"], pose["z"])
    neck = pelvis + Vector((math.sin(lean), 0.0, math.cos(lean))) * SPINE_LENGTH
    shoulder = shoulder_of(pose)
    knee_hint = Vector((pose["kh"][0], 0.0, pose["kh"][1]))
    elbow_hint = Vector((pose["eh"][0], 0.0, pose["eh"][1]))

    joints = {"pelvis": pelvis, "neck": neck}
    joints["head"] = neck + Vector((math.sin(look), 0.0, math.cos(look))) * (HEAD_RADIUS + NECK_GAP)
    for tag, depth in (("l", 1.0), ("r", -1.0)):  # left limbs sit further into the room
        hip = pelvis + Vector((0.0, depth * HIP_HALF, 0.0))
        foot = point(*pose["f" + tag], depth * HIP_HALF)
        joints["hip_" + tag] = hip
        joints["knee_" + tag], joints["foot_" + tag] = bend(hip, foot, THIGH, SHIN, knee_hint)
        sh = neck + Vector((0.0, depth * SHOULDER_HALF, 0.0))
        hand = point(*hand_point(pose, "h" + tag, shoulder), depth * (SHOULDER_HALF + 0.02))
        joints["sh_" + tag] = sh
        joints["elbow_" + tag], joints["hand_" + tag] = bend(sh, hand, UPPER_ARM, FOREARM, elbow_hint)
    return joints


# ----------------------------------------------------------------------------- scene

def add_box(location, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    box = bpy.context.active_object
    box.scale = scale
    box.data.materials.append(material)
    return box


def new_panel_scene():
    """Fresh scene set up for one 1080x960 panel."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    setup_render(scene, PANEL_WIDTH, PANEL_HEIGHT)
    scene.frame_start, scene.frame_end = FIRST_FRAME, LAST_FRAME
    return scene


def add_captions(scene, cam, captions):
    """captions: list of (text, first frame, frame it disappears or None)."""
    for i, (text, first, last) in enumerate(captions):
        show_between(add_hud_text(scene, cam, text, f"Caption{i}"), first, last)


def build_morning_room(mode, captions):
    """Side-view bedroom panel with the morning routine. mode: 'motivated' or 'unmotivated'.
    Returns (scene, camera, function giving the points that must stay below the captions)."""
    scene = new_panel_scene()
    bright = mode == "motivated"

    # World dark ambient
    world = bpy.data.worlds.new("RoomWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.03, 0.035, 0.045, 1.0)

    wall_mat = make_material("WallMat", (0.14, 0.15, 0.18), roughness=0.9)
    floor_mat = make_material("FloorMat", (0.18, 0.12, 0.08), roughness=0.6)
    bed_mat = make_material("BedMat", (0.25, 0.32, 0.45), roughness=0.85)
    blanket_mat = make_material("BlanketMat", (0.35, 0.42, 0.55), roughness=0.9)
    pillow_mat = make_material("PillowMat", (0.80, 0.82, 0.86), roughness=0.9)
    wood_mat = make_material("WoodMat", (0.28, 0.17, 0.09), roughness=0.55)
    glass_mat = make_material("GlassMat", (0.55, 0.75, 0.90), roughness=0.15, emission=0.15, alpha=0.22)
    lamp_glow = make_material("LampGlow", (1.0, 0.85, 0.55), emission=2.5)
    water_mat = make_material("WaterMat", (0.70, 0.88, 1.0), roughness=0.2, emission=1.0, alpha=0.55)
    win_sky = make_material(
        "WinSky", (0.45, 0.65, 0.95) if bright else (0.08, 0.10, 0.18), emission=1.2 if bright else 0.35,
    )

    # Room shell: the floor runs out past the camera so the frame never shows its edge
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, -3.0, 0))
    floor = bpy.context.active_object
    floor.scale = (18.0, 12.0, 1.0)
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 1.5, 2.2))
    back_wall = bpy.context.active_object
    back_wall.rotation_euler = (math.radians(90), 0, 0)
    back_wall.scale = (18.0, 4.6, 1.0)
    back_wall.data.materials.append(wall_mat)

    # Zone 1: Bed + pillow + blanket + window
    add_box((BED_X, 0.5, 0.28), (1.9, 1.1, 0.56), bed_mat)
    add_box((BED_X - 0.72, 0.5, BED_TOP + 0.04), (0.38, 0.8, 0.10), pillow_mat)
    blanket = add_box((BED_X + 0.38, 0.5, 0.62), (1.1, 1.12, 0.13), blanket_mat)
    slide_from, slide_to = BLANKET_SLIDE[mode]
    blanket.keyframe_insert(data_path="location", frame=slide_from)
    blanket.keyframe_insert(data_path="scale", frame=slide_from)
    blanket.location = (BED_X - 0.25, 0.5, 0.60)   # thrown back toward the pillow
    blanket.scale = (0.50, 1.12, 0.16)
    blanket.keyframe_insert(data_path="location", frame=slide_to)
    blanket.keyframe_insert(data_path="scale", frame=slide_to)

    # Window (kept below the caption zone)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(BED_X + 0.3, 1.46, 1.62))
    win = bpy.context.active_object
    win.rotation_euler = (math.radians(90), 0, 0)
    win.scale = (1.2, 0.9, 1.0)
    win.data.materials.append(win_sky)

    # Zone 2: Workout mat
    add_box((MAT_X, 0.3, 0.02), (1.7, 0.9, 0.04), make_material("YogaMat", (0.28, 0.16, 0.32)))

    # Zone 3: Desk + chair + warm lamp. Thin corner legs leave room for the knees.
    add_box((DESK_X, 0.4, DESK_TOP - 0.04), (1.4, 0.8, 0.08), wood_mat)
    for dx in (-0.62, 0.62):
        for dy in (-0.33, 0.33):
            add_box((DESK_X + dx, 0.4 + dy, (DESK_TOP - 0.08) / 2), (0.07, 0.07, DESK_TOP - 0.08), wood_mat)
    add_box((CHAIR_X, 0.4, SEAT_TOP - 0.03), (0.45, 0.45, 0.06), wood_mat)
    for dx in (-0.18, 0.18):
        for dy in (-0.18, 0.18):
            add_box((CHAIR_X + dx, 0.4 + dy, (SEAT_TOP - 0.06) / 2), (0.05, 0.05, SEAT_TOP - 0.06), wood_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(DESK_X + 0.42, 0.4, DESK_TOP + 0.16))
    bpy.context.active_object.data.materials.append(lamp_glow)

    # Zone 4: Glass shower stall, with water that starts when the figure steps in
    add_box((SHOWER_X, 0.4, 1.05), (1.1, 0.9, 2.1), glass_mat)
    add_box((SHOWER_X + 0.25, 0.4, 2.02), (0.30, 0.16, 0.05), wood_mat)
    for i in range(9):
        dx = -0.20 + 0.05 * i
        dy = 0.07 * math.sin(i * 2.4)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=1.95, location=(SHOWER_X + 0.25 + dx, 0.4 + dy, 1.02))
        stream = bpy.context.active_object
        stream.rotation_euler = (0, math.radians(-4 + i), 0)
        stream.data.materials.append(water_mat)
        show_between(stream, SHOWER_ARRIVAL[mode], None)

    # Lighting: brighter warm key when motivated, moody dim blue-grey when not
    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.5, 3.2))
    key_light = bpy.context.active_object
    key_light.data.size = 10.0
    key_light.data.energy = 260.0 if bright else 95.0
    key_light.data.color = (1.0, 0.96, 0.90) if bright else (0.65, 0.75, 0.95)
    key_light.rotation_euler = (math.radians(65), 0, 0)

    # Character
    routine = ROUTINES[mode]

    def pose(frame):
        return joints_of(routine(frame))

    figure = FusedFigure(scene, "Figure")
    figure.bake(pose, FIRST_FRAME, LAST_FRAME)

    # Smooth side-scrolling camera tracking the character
    bpy.ops.object.camera_add(location=(BED_X, -6.2, 1.12))
    cam = bpy.context.active_object
    cam.data.lens = 54
    cam.rotation_euler = (math.radians(89.3), 0, 0)
    scene.camera = cam
    pelvis_x = [routine(f)["x"] for f in range(FIRST_FRAME, LAST_FRAME + 1)]
    window = 18
    for i, frame in enumerate(range(FIRST_FRAME, LAST_FRAME + 1)):
        nearby = pelvis_x[max(0, i - window): i + window + 1]
        cam.location.x = sum(nearby) / len(nearby)
        cam.keyframe_insert(data_path="location", frame=frame)

    # Captions locked in the panel's top safe zone
    add_captions(scene, cam, captions)

    def watched(frame):
        joints = pose(frame)
        return {"head": joints["head"] + UP * HEAD_RADIUS, "hand": max(joints["hand_l"], joints["hand_r"], key=lambda p: p.z)}

    return scene, cam, watched


def stack(top, bottom, target, still=False):
    """Stack the two panels into one 1080x1920 frame with a thin divider."""
    graph = "[0:v][1:v]vstack=inputs=2,drawbox=x=0:y=ih/2-2:w=iw:h=4:color=black:t=fill[v]"
    command = ["ffmpeg", "-v", "error", "-y", "-i", top, "-i", bottom, "-filter_complex", graph, "-map", "[v]"]
    if still:
        command += ["-frames:v", "1"]
    else:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "60"]
    subprocess.run(command + [target], check=True)


def output_path_from_args(default):
    """Output path passed after '--' on the Blender command line."""
    path = default
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if len(sys.argv) > idx + 1:
            path = sys.argv[idx + 1]
    return os.path.abspath(path)


def render_split_screen(name, builders, output_path):
    """Render two panels and stack them. `builders` is (top, bottom); each is a function
    returning (scene, camera, watched points function). Honours SHORTS_CHUNK (one slice of
    the frame range), SHORTS_STILL (one frame, as a PNG) and SHORTS_CHECK (safe-zone check)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    first, last = chunk_range(FIRST_FRAME, LAST_FRAME)
    still_frame = os.environ.get("SHORTS_STILL")
    checking = os.environ.get("SHORTS_CHECK")
    # The process id keeps concurrent renders from overwriting each other's panel files.
    tag = (os.environ.get("SHORTS_CHUNK") or "all").replace("/", "of") + f"_{os.getpid()}"
    all_clear = True
    panel_files = []

    for position, build in zip(("top", "bottom"), builders):
        scene, cam, watched = build()
        if checking:
            all_clear &= safe_zone_check(scene, cam, watched, FIRST_FRAME, LAST_FRAME, f"{name} {position}")
            continue
        if still_frame:
            panel_file = os.path.abspath(f"temp/{name}_{position}_still_{tag}.png")
            scene.frame_set(int(still_frame))
            set_still_output(scene, panel_file)
            bpy.ops.render.render(write_still=True)
        else:
            panel_file = os.path.abspath(f"temp/{name}_{position}_{tag}.mp4")
            scene.frame_start, scene.frame_end = first, last
            set_video_output(scene, panel_file)
            bpy.ops.render.render(animation=True)
        panel_files.append(panel_file)

    if checking:
        sys.exit(0 if all_clear else 1)
    stack(panel_files[0], panel_files[1], output_path, still=bool(still_frame))
    for panel_file in panel_files:
        os.remove(panel_file)
    print(f"Rendered with Blender {bpy.app.version_string}: {output_path}")
