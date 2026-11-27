# Split-screen short. Top: "WHAT PEOPLE DON'T SEE", the unglamorous daily grind.
# Bottom: "WHAT PEOPLE SEE", the trophy moment on stage.
#
# Render command (Blender; Eevee needs a display, so wrap in xvfb-run on headless machines;
# the two panels are stacked with ffmpeg, which must be on the PATH):
# xvfb-run -a blender -b -P scenes/what_people_see.py -- output/what_people_see.mp4
#
# Render one slice for parallel rendering (the workflow does this, then joins the slices):
# SHORTS_CHUNK=2/6 xvfb-run -a blender -b -P scenes/what_people_see.py -- output/part_02.mp4
#
# Preview a single frame instead of the full video:
# SHORTS_STILL=300 xvfb-run -a blender -b -P scenes/what_people_see.py -- output/preview.png
#
# Check that nothing enters the caption zone (no render):
# SHORTS_CHECK=1 blender -b -P scenes/what_people_see.py

import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.blender_rig import HEAD_RADIUS, UP, FusedFigure, make_material, smoothstep  # noqa: E402
from lib.side_view import (  # noqa: E402
    FIRST_FRAME, FOOT_Z, LAST_FRAME, add_box, add_captions, build_morning_room, chain, joints_of, mix,
    new_panel_scene, output_path_from_args, render_split_screen, stand, walk,
)

TOP_CAPTIONS = [("WHAT PEOPLE\nDON'T SEE", 1, None)]
BOTTOM_CAPTIONS = [("WHAT PEOPLE SEE", 1, None)]

# ----------------------------------------------------------------------------- stage
STAGE_Y = 0.3
ENTRANCE_X = -3.1
PODIUM_X = 1.0
PODIUM_HEIGHT = 0.22
STEP_X = PODIUM_X - 0.72        # where the figure stops before stepping up
MARK_X = PODIUM_X - 0.12        # where it stands on the podium
PEDESTAL_X = PODIUM_X + 0.36
TROPHY_REST_Z = PODIUM_HEIGHT + 1.22  # trophy base height while it waits on the pedestal

# For the first 17 seconds the stage is empty: the trophy waits under the lights while the
# grind happens upstairs. Then the figure walks on, and the glory lasts a few seconds.
WALK_START, WALK_END, STEP_END, GRAB, LIFT_END = 1020, 1250, 1300, 1348, 1396


def on_podium(x, lean=3.0, head=4.0):
    pose = stand(x, y=STAGE_Y)
    pose.update(z=pose["z"] + PODIUM_HEIGHT, lean=lean, head=head,
                fl=(x - 0.03, FOOT_Z + PODIUM_HEIGHT), fr=(x + 0.03, FOOT_Z + PODIUM_HEIGHT))
    return pose


def reaching():
    """Both hands on the trophy's stem, still on its pedestal."""
    pose = on_podium(MARK_X, lean=12.0, head=10.0)
    grip = ("abs", PEDESTAL_X, TROPHY_REST_Z + 0.06)
    pose.update(hl=grip, hr=grip, eh=(-1.0, -0.4))
    return pose


def holding_high(bounce=0.0):
    """Trophy overhead; `bounce` (0..1) dips the knees and pumps the arms."""
    pose = on_podium(MARK_X, lean=-2.0, head=-14.0)
    pose["z"] -= 0.05 * bounce
    hands = ("abs", MARK_X + 0.04, pose["z"] + 0.56 + 0.50 + 0.05 * bounce)
    pose.update(hl=hands, hr=hands, eh=(1.0, 0.2))
    return pose


def champion(frame):
    f = float(frame)
    if f <= WALK_START:  # waiting in the wings, out of sight
        return stand(ENTRANCE_X, y=STAGE_Y)
    if f <= WALK_END:   # strolls in from the wings
        return walk(ENTRANCE_X, STEP_X, (f - WALK_START) / (WALK_END - WALK_START), steps=8,
                    y_from=STAGE_Y, y_to=STAGE_Y)
    if f <= STEP_END:   # one foot up, then the other
        ground = stand(STEP_X, y=STAGE_Y)
        half_up = stand(STEP_X + 0.30, y=STAGE_Y)
        half_up.update(z=half_up["z"] + PODIUM_HEIGHT * 0.5, lean=14.0,
                       fl=(MARK_X - 0.03, FOOT_Z + PODIUM_HEIGHT), fr=(STEP_X + 0.03, FOOT_Z))
        return chain(f, [(WALK_END, ground), (WALK_END + 18, half_up), (STEP_END, on_podium(MARK_X))])
    if f <= GRAB:
        return mix(on_podium(MARK_X), reaching(), smoothstep(STEP_END, GRAB, f))
    if f <= LIFT_END:
        return mix(reaching(), holding_high(), smoothstep(GRAB, LIFT_END, f))
    return holding_high(bounce=max(0.0, math.sin((f - LIFT_END) * 0.13)) ** 2)


def sweep(frame, phase):
    """Slow side-to-side swing of a searchlight, in radians."""
    return math.radians(24.0) * math.sin(frame * 0.012 + phase)


def trophy_base(frame):
    """Where the trophy's base is: on the pedestal until grabbed, then in the hands."""
    if frame <= GRAB:
        return Vector((PEDESTAL_X, STAGE_Y, TROPHY_REST_Z))
    joints = joints_of(champion(frame))
    return (joints["hand_l"] + joints["hand_r"]) / 2 - UP * 0.06


TROPHY_HEIGHT = 0.36


def build_trophy(gold):
    root = bpy.data.objects.new("Trophy", None)
    bpy.context.scene.collection.objects.link(root)
    pieces = []
    bpy.ops.mesh.primitive_cylinder_add(radius=0.075, depth=0.035, location=(0, 0, 0.018))
    pieces.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=0.12, location=(0, 0, 0.09))
    pieces.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_cone_add(radius1=0.045, radius2=0.115, depth=0.21, location=(0, 0, 0.255))
    pieces.append(bpy.context.active_object)
    for side in (-1, 1):  # handles
        bpy.ops.mesh.primitive_torus_add(major_radius=0.055, minor_radius=0.012,
                                         location=(side * 0.125, 0, 0.27), rotation=(math.radians(90), 0, 0))
        pieces.append(bpy.context.active_object)
    for piece in pieces:
        for poly in piece.data.polygons:
            poly.use_smooth = True
        piece.data.materials.append(gold)
        piece.parent = root
    return root


def build_stage(captions):
    """The trophy moment: a lit stage, a podium, a crowd and falling confetti."""
    scene = new_panel_scene()
    rng = random.Random(7)

    world = bpy.data.worlds.new("StageWorld")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.012, 0.010, 0.016, 1.0)

    boards = make_material("StageBoards", (0.16, 0.09, 0.05), roughness=0.45)
    curtain = make_material("Curtain", (0.34, 0.03, 0.05), roughness=0.9)
    fold = make_material("CurtainFold", (0.22, 0.02, 0.035), roughness=0.9)
    podium_mat = make_material("Podium", (0.50, 0.50, 0.56), roughness=0.5)
    gold = make_material("Gold", (1.0, 0.72, 0.16), roughness=0.3, emission=1.8)
    crowd_mat = make_material("Crowd", (0.012, 0.012, 0.016), roughness=1.0)

    # Stage floor (runs out past the camera) and curtain with vertical folds
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, -3.0, 0))
    floor = bpy.context.active_object
    floor.scale = (18.0, 12.0, 1.0)
    floor.data.materials.append(boards)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 1.5, 2.4))
    wall = bpy.context.active_object
    wall.rotation_euler = (math.radians(90), 0, 0)
    wall.scale = (18.0, 5.0, 1.0)
    wall.data.materials.append(curtain)
    for i in range(-14, 15):
        add_box((i * 0.55, 1.46, 2.4), (0.16, 0.05, 5.0), fold)

    # Podium, with a slim pedestal holding the trophy
    add_box((PODIUM_X, STAGE_Y, PODIUM_HEIGHT / 2), (1.25, 0.9, PODIUM_HEIGHT), podium_mat)
    pedestal_height = TROPHY_REST_Z - PODIUM_HEIGHT
    add_box((PEDESTAL_X, STAGE_Y, PODIUM_HEIGHT + pedestal_height / 2), (0.14, 0.14, pedestal_height), podium_mat)

    # Lighting: warm spotlight on the podium, cool fill, camera flashes from the crowd
    bpy.ops.object.light_add(type="SPOT", location=(PODIUM_X - 0.4, -2.6, 5.2))
    spot = bpy.context.active_object
    spot.data.energy = 2000.0
    spot.data.color = (1.0, 0.93, 0.80)
    spot.data.spot_size = math.radians(34)
    spot.data.spot_blend = 0.5
    spot.rotation_euler = (math.radians(30), 0, math.radians(-6))
    bpy.ops.object.light_add(type="AREA", location=(0.0, -4.0, 3.0))
    fill = bpy.context.active_object
    fill.data.size = 9.0
    fill.data.energy = 60.0
    fill.data.color = (0.55, 0.65, 1.0)
    fill.rotation_euler = (math.radians(62), 0, 0)
    # Two coloured searchlights sweep the curtain while the stage waits
    for x, colour, phase in ((-1.6, (0.45, 0.60, 1.0), 0.0), (2.6, (1.0, 0.55, 0.85), 2.1)):
        bpy.ops.object.light_add(type="SPOT", location=(x, -2.2, 4.6))
        beam = bpy.context.active_object
        beam.data.energy = 900.0
        beam.data.color = colour
        beam.data.spot_size = math.radians(22)
        beam.data.spot_blend = 0.6
        for frame in range(FIRST_FRAME, LAST_FRAME + 1, 20):
            beam.rotation_euler = (math.radians(52), 0, sweep(frame, phase))
            beam.keyframe_insert(data_path="rotation_euler", frame=frame)

    for i in range(16):
        bpy.ops.object.light_add(type="POINT", location=(rng.uniform(-1.4, 3.2), -2.9, rng.uniform(1.0, 1.5)))
        flash = bpy.context.active_object
        flash.data.color = (0.9, 0.95, 1.0)
        flash.data.energy = 0.0
        # A few flashes as the figure walks on, most once the trophy is up
        at = rng.randint(WALK_START + 60, GRAB) if i < 4 else rng.randint(LIFT_END, LAST_FRAME - 12)
        for frame, energy in ((at - 1, 0.0), (at + 1, 320.0), (at + 7, 0.0)):
            flash.data.energy = energy
            flash.data.keyframe_insert(data_path="energy", frame=frame)

    # Crowd: dark heads peeking over the bottom edge of the frame, bobbing as they cheer
    for i in range(16):
        x = -2.2 + i * 0.36 + rng.uniform(-0.06, 0.06)
        y = -3.3 + rng.uniform(-0.25, 0.25)
        height = rng.uniform(0.02, 0.16)
        person = bpy.data.objects.new("Fan", None)
        scene.collection.objects.link(person)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(x, y, 0.36))
        fan_head = bpy.context.active_object
        fan_head.data.materials.append(crowd_mat)
        fan_head.parent = person
        shoulders = add_box((x, y, -0.06), (0.46, 0.24, 0.50), crowd_mat)
        shoulders.parent = person
        # Gentle swaying while they wait...
        sway = rng.uniform(0, 6.28)
        for frame in range(FIRST_FRAME, LIFT_END - 20, 30):
            person.location = (0.04 * math.sin(frame * 0.02 + sway), 0.0, height + 0.015 * math.sin(frame * 0.035 + sway))
            person.keyframe_insert(data_path="location", frame=frame)
        # ...then bouncing as they cheer
        phase = rng.uniform(0, 14)
        frame = LIFT_END - 20 + phase
        person.location = (0.0, 0.0, height)
        person.keyframe_insert(data_path="location", frame=frame)
        while frame < LAST_FRAME:
            person.location.z = height + 0.10
            person.keyframe_insert(data_path="location", frame=frame + 7)
            person.location.z = height
            person.keyframe_insert(data_path="location", frame=frame + 14)
            frame += 14 + rng.uniform(0, 8)

    # Confetti: starts falling as the trophy goes up
    colours = [(1.0, 0.25, 0.3), (0.3, 0.7, 1.0), (1.0, 0.85, 0.2), (0.4, 1.0, 0.5), (1.0, 0.5, 0.9), (1.0, 1.0, 1.0)]
    confetti_mats = [make_material(f"Confetti{i}", c, roughness=0.6, emission=0.9) for i, c in enumerate(colours)]
    for i in range(190):
        bpy.ops.mesh.primitive_plane_add(size=0.055)
        piece = bpy.context.active_object
        piece.data.materials.append(confetti_mats[i % len(confetti_mats)])
        x, y = rng.uniform(-1.6, 3.4), rng.uniform(-1.4, 1.1)
        start = rng.uniform(LIFT_END - 30, LAST_FRAME - 60)
        fall = rng.uniform(110, 170)
        piece.location = (x, y, 4.4)
        piece.rotation_euler = (rng.uniform(0, 6), rng.uniform(0, 6), 0)
        piece.keyframe_insert(data_path="location", frame=start)
        piece.keyframe_insert(data_path="rotation_euler", frame=start)
        piece.location = (x + rng.uniform(-0.5, 0.5), y, 0.02)
        piece.rotation_euler = (rng.uniform(8, 22), rng.uniform(8, 22), rng.uniform(-6, 6))
        piece.keyframe_insert(data_path="location", frame=start + fall)
        piece.keyframe_insert(data_path="rotation_euler", frame=start + fall)
        for curve in piece.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"

    # Champion and trophy
    def pose(frame):
        return joints_of(champion(frame))

    figure = FusedFigure(scene, "Champion")
    figure.bake(pose, FIRST_FRAME, LAST_FRAME)
    trophy = build_trophy(gold)
    for frame in range(FIRST_FRAME, LAST_FRAME + 1):
        trophy.location = trophy_base(frame)
        trophy.keyframe_insert(data_path="location", frame=frame)

    # Static wide camera: the stage is a place, and the figure walks into it
    bpy.ops.object.camera_add(location=(0.30, -6.2, 1.30))
    cam = bpy.context.active_object
    cam.data.lens = 46
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    add_captions(scene, cam, captions)

    def watched(frame):
        joints = pose(frame)
        return {"head": joints["head"] + UP * HEAD_RADIUS, "trophy": trophy_base(frame) + UP * TROPHY_HEIGHT}

    return scene, cam, watched


render_split_screen(
    "what_people_see",
    (
        lambda: build_morning_room("unmotivated", TOP_CAPTIONS),
        lambda: build_stage(BOTTOM_CAPTIONS),
    ),
    output_path_from_args("output/what_people_see.mp4"),
)
