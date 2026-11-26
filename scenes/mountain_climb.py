# Render command (Blender; Eevee needs a display, so wrap in xvfb-run on headless machines):
# xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/mountain_climb.mp4
#
# Render one slice for parallel rendering (the workflow does this, then joins the slices):
# SHORTS_CHUNK=2/6 xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/part_02.mp4
#
# Preview a single frame instead of the full video:
# SHORTS_STILL=300 xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/preview.png
#
# Print where the peak, flag and head sit in the frame (caption safe-zone check), no render:
# SHORTS_CHECK=1 blender -b -P scenes/mountain_climb.py

import os
import sys
import math
import random
import bpy
from mathutils import Vector, noise
from bpy_extras.object_utils import world_to_camera_view

# Parse output filepath passed after '--'
output_path = "output/mountain_climb.mp4"
if "--" in sys.argv:
    idx = sys.argv.index("--")
    if len(sys.argv) > idx + 1:
        output_path = sys.argv[idx + 1]
output_path = os.path.abspath(output_path)
still_frame = os.environ.get("SHORTS_STILL")

# 1. Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# 2. Render & Output Settings (1080x1920, 60fps, Eevee)
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items else 'BLENDER_EEVEE'
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.fps = 60
scene.frame_start = 1
scene.frame_end = 540  # 9 seconds at 60fps

# Blender 5.0 split the output choice in two: media type first, then the format.
if hasattr(scene.render.image_settings, "media_type"):
    scene.render.image_settings.media_type = 'VIDEO'
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
scene.render.filepath = output_path

# Anti-aliasing samples per frame (Blender's default is 64). Without a GPU (CI, cloud
# containers) Eevee runs on software OpenGL and render time grows with this number.
scene.eevee.taa_render_samples = 16
if os.environ.get("SHORTS_SAMPLES"):
    scene.eevee.taa_render_samples = int(os.environ["SHORTS_SAMPLES"])

# Soft glow around strongly emissive elements only (trail, flag, stars). The threshold
# sits above 1.0 so the caption (emission 1.0) stays razor-sharp. Bloom exists in Eevee
# up to Blender 4.1.
if hasattr(scene.eevee, "use_bloom"):
    scene.eevee.use_bloom = True
    scene.eevee.bloom_threshold = 1.4
    scene.eevee.bloom_knee = 0.1
    scene.eevee.bloom_intensity = 0.06
    scene.eevee.bloom_radius = 5.5

# Standard view transform: emission 1.0 is exactly white, so the caption is pure #FFFFFF
# (Blender's default AgX would render it light grey).
scene.view_settings.view_transform = 'Standard'

MIST_COLOR = (0.085, 0.125, 0.21, 1.0)
ZENITH_COLOR = (0.008, 0.012, 0.025, 1.0)

# 3. Starry Night Sky World
world = bpy.data.worlds.new("NightSky")
scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()

# Dark zenith fading into a band of mist along the horizon
coord = wnodes.new("ShaderNodeTexCoord")
sky_split = wnodes.new("ShaderNodeSeparateXYZ")
wlinks.new(coord.outputs["Generated"], sky_split.inputs["Vector"])
horizon = wnodes.new("ShaderNodeMapRange")
horizon.inputs["From Min"].default_value = -0.05
horizon.inputs["From Max"].default_value = 0.20
horizon.inputs["To Min"].default_value = 1.0
horizon.inputs["To Max"].default_value = 0.0
horizon.interpolation_type = 'SMOOTHSTEP'  # no visible band edge
wlinks.new(sky_split.outputs["Z"], horizon.inputs["Value"])
sky_mix = wnodes.new("ShaderNodeMixRGB")
sky_mix.inputs["Color1"].default_value = ZENITH_COLOR
sky_mix.inputs["Color2"].default_value = (MIST_COLOR[0] * 0.45, MIST_COLOR[1] * 0.45, MIST_COLOR[2] * 0.45, 1.0)
wlinks.new(horizon.outputs["Result"], sky_mix.inputs["Fac"])

bg = wnodes.new("ShaderNodeBackground")
wlinks.new(sky_mix.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
out = wnodes.new("ShaderNodeOutputWorld")
wlinks.new(bg.outputs["Background"], out.inputs["Surface"])

# Add subtle stars in the sky dome
star_mat = bpy.data.materials.new("StarMat")
star_mat.use_nodes = True
s_bsdf = star_mat.node_tree.nodes.get("Principled BSDF")
s_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
s_bsdf.inputs["Emission Strength"].default_value = 3.0

random.seed(42)
for _ in range(180):
    theta = random.uniform(-math.pi * 0.45, math.pi * 0.45)
    phi = random.uniform(0.15, 0.85)
    dist = 95.0
    sx = dist * math.sin(theta)
    sy = dist * math.cos(theta) * math.cos(phi)
    sz = dist * math.sin(phi) + 10.0
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.08, 0.18), location=(sx, sy, sz))
    star = bpy.context.active_object
    star.data.materials.append(star_mat)

# 4. Lighting (Cool Moonlight)
bpy.ops.object.light_add(type='SUN', location=(10, -10, 30))
sun = bpy.context.active_object
sun.data.energy = 2.8
sun.data.color = (0.78, 0.86, 1.0)
sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(-35))

# 5. Procedural 3D Mountain: sharp creased ridge, multi-octave rock, snow on the gentle faces
def ridged(x, y, octaves, seed):
    """Ridged multi-octave noise in 0..1: each octave folds Perlin noise into sharp creases."""
    total, norm, amp, freq = 0.0, 0.0, 1.0, 1.0
    for _ in range(octaves):
        fold = 1.0 - abs(noise.noise(Vector((x * freq, y * freq, seed))))
        total += amp * fold * fold
        norm += amp
        amp *= 0.5
        freq *= 2.1
    return total / norm


def mountain_height(x, y):
    # Ridge peaks near y = 4.0 and slopes steeply down toward negative y. The |x|^1.45
    # profile gives the crest a crease instead of a rounded top.
    ridge = math.exp(-((abs(x) * 0.22) ** 1.45)) * (14.0 - abs(y - 4.0) * 0.48)
    # Detail fades out along the crest line so the trail and the climber have footing.
    rough = min(1.0, abs(x) * 0.35 + 0.12)
    crag = (
        0.55 * math.sin(x * 1.4 + y * 0.7)
        + 0.30 * math.cos(x * 2.9 - y * 1.8)
        + 0.15 * math.sin(x * 5.5 + y * 4.2)
    )
    spurs = (ridged(x * 0.33, y * 0.33, 5, 7.3) - 0.5) * 2.6      # large rock creases
    chips = (ridged(x * 1.25 + 11.0, y * 1.25 - 5.0, 3, 2.1) - 0.5) * 0.30  # small facets
    return max(-8.0, ridge + (crag + spurs + chips) * rough)


nx, ny = 220, 260
x_min, x_max = -18.0, 18.0
y_min, y_max = -34.0, 10.0

verts = []
faces = []
for j in range(ny):
    y = y_min + (y_max - y_min) * (j / (ny - 1))
    for i in range(nx):
        x = x_min + (x_max - x_min) * (i / (nx - 1))
        z = mountain_height(x, y)
        verts.append((x, y, z))

for j in range(ny - 1):
    for i in range(nx - 1):
        v0 = j * nx + i
        v1 = v0 + 1
        v2 = v0 + nx + 1
        v3 = v0 + nx
        faces.append((v0, v1, v2, v3))

m_mesh = bpy.data.meshes.new("MountainMesh")
m_mesh.from_pydata(verts, [], faces)
m_mesh.update()
for p in m_mesh.polygons:
    p.use_smooth = False  # flat shading: crisp facets

mountain = bpy.data.objects.new("Mountain", m_mesh)
scene.collection.objects.link(mountain)

snow_mat = bpy.data.materials.new("SnowMat")
snow_mat.use_nodes = True
mnodes = snow_mat.node_tree.nodes
mlinks = snow_mat.node_tree.links
sn_bsdf = mnodes.get("Principled BSDF")
sn_bsdf.inputs["Roughness"].default_value = 0.85

# Snow settles on gentle faces, bare rock shows on steep ones
geo = mnodes.new("ShaderNodeNewGeometry")
normal_split = mnodes.new("ShaderNodeSeparateXYZ")
mlinks.new(geo.outputs["True Normal"], normal_split.inputs["Vector"])
slope = mnodes.new("ShaderNodeValToRGB")
slope.color_ramp.elements[0].position = 0.50
slope.color_ramp.elements[0].color = (0.085, 0.095, 0.125, 1.0)  # rock
slope.color_ramp.elements[1].position = 0.74
slope.color_ramp.elements[1].color = (0.74, 0.80, 0.90, 1.0)     # snow
mlinks.new(normal_split.outputs["Z"], slope.inputs["Fac"])
mlinks.new(slope.outputs["Color"], sn_bsdf.inputs["Base Color"])

# Atmospheric mist: thicker with distance from the camera and toward the valley floor
cam_data = mnodes.new("ShaderNodeCameraData")
far = mnodes.new("ShaderNodeMapRange")
far.inputs["From Min"].default_value = 10.0
far.inputs["From Max"].default_value = 60.0
mlinks.new(cam_data.outputs["View Z Depth"], far.inputs["Value"])
pos_split = mnodes.new("ShaderNodeSeparateXYZ")
mlinks.new(geo.outputs["Position"], pos_split.inputs["Vector"])
low = mnodes.new("ShaderNodeMapRange")
low.inputs["From Min"].default_value = 10.0
low.inputs["From Max"].default_value = -3.0
low.inputs["To Min"].default_value = 0.25
low.inputs["To Max"].default_value = 1.0
mlinks.new(pos_split.outputs["Z"], low.inputs["Value"])
mist_amount = mnodes.new("ShaderNodeMath")
mist_amount.operation = 'MULTIPLY'
mlinks.new(far.outputs["Result"], mist_amount.inputs[0])
mlinks.new(low.outputs["Result"], mist_amount.inputs[1])
mist_cap = mnodes.new("ShaderNodeMath")
mist_cap.operation = 'MULTIPLY'
mist_cap.inputs[1].default_value = 0.8
mlinks.new(mist_amount.outputs["Value"], mist_cap.inputs[0])
mist_glow = mnodes.new("ShaderNodeEmission")
mist_glow.inputs["Color"].default_value = MIST_COLOR
mist_glow.inputs["Strength"].default_value = 1.0
mist_mix = mnodes.new("ShaderNodeMixShader")
mlinks.new(mist_cap.outputs["Value"], mist_mix.inputs["Fac"])
mlinks.new(sn_bsdf.outputs["BSDF"], mist_mix.inputs[1])
mlinks.new(mist_glow.outputs["Emission"], mist_mix.inputs[2])
mlinks.new(mist_mix.outputs["Shader"], mnodes.get("Material Output").inputs["Surface"])
mountain.data.materials.append(snow_mat)

# 6. Glowing Golden Trail: winds up the ridge to the climber, thinning toward the valley
trail_pts = []
steps = 420
for s in range(steps):
    t = s / (steps - 1)
    ty = -30.0 + t * 32.0  # From bottom valley (-30) up to the climber (+2.0)
    settle = 1.0 - max(0.0, min(1.0, (t - 0.90) / 0.10)) ** 2  # straighten onto the crest at the top
    tx = 0.85 * math.sin(t * 14.0) * (1.0 - 0.3 * t) * settle
    tz = mountain_height(tx, ty) + 0.07
    trail_pts.append((tx, ty, tz, t))

curve_data = bpy.data.curves.new("GoldenTrail", type='CURVE')
curve_data.dimensions = '3D'
curve_data.bevel_depth = 0.07
curve_data.bevel_resolution = 4
curve_data.use_fill_caps = True
spline = curve_data.splines.new('POLY')
spline.points.add(len(trail_pts) - 1)
for idx, pt in enumerate(trail_pts):
    spline.points[idx].co = (pt[0], pt[1], pt[2], 1.0)
    spline.points[idx].radius = 0.28 + 0.72 * pt[3] ** 0.8  # taper: thin in the valley, full at the top

trail_obj = bpy.data.objects.new("GoldenTrailObj", curve_data)
scene.collection.objects.link(trail_obj)

gold_mat = bpy.data.materials.new("GoldGlow")
gold_mat.use_nodes = True
g_bsdf = gold_mat.node_tree.nodes.get("Principled BSDF")
g_bsdf.inputs["Base Color"].default_value = (1.0, 0.72, 0.15, 1.0)
g_bsdf.inputs["Emission Color"].default_value = (1.0, 0.68, 0.12, 1.0)
g_bsdf.inputs["Emission Strength"].default_value = 4.5
trail_obj.data.materials.append(gold_mat)

# Summit Red Flag at peak (x=0, y=4.0)
peak_z = mountain_height(0.0, 4.0)
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.9, location=(0.0, 4.0, peak_z + 0.45))
pole = bpy.context.active_object
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.22, 4.0, peak_z + 0.75))
flag = bpy.context.active_object
flag.scale = (0.4, 0.04, 0.24)
red_mat = bpy.data.materials.new("FlagRed")
red_mat.use_nodes = True
r_bsdf = red_mat.node_tree.nodes.get("Principled BSDF")
r_bsdf.inputs["Base Color"].default_value = (0.95, 0.12, 0.12, 1.0)
r_bsdf.inputs["Emission Color"].default_value = (0.95, 0.12, 0.12, 1.0)
r_bsdf.inputs["Emission Strength"].default_value = 2.0
flag.data.materials.append(red_mat)

# 7. Articulated 3D Outlined Stick Figure near Summit (x=0, y=2.0)
char_x, char_y = 0.0, 2.0
char_z = mountain_height(char_x, char_y)

white_mat = bpy.data.materials.new("CharWhite")
white_mat.use_nodes = True
w_bsdf = white_mat.node_tree.nodes.get("Principled BSDF")
w_bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
w_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
w_bsdf.inputs["Emission Strength"].default_value = 0.65

outline_mat = bpy.data.materials.new("CharOutline")
outline_mat.use_nodes = True
outline_mat.use_backface_culling = True
o_bsdf = outline_mat.node_tree.nodes.get("Principled BSDF")
o_bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
o_bsdf.inputs["Roughness"].default_value = 1.0

def add_outlined_part(obj, thickness=0.022):
    obj.data.materials.append(white_mat)
    obj.data.materials.append(outline_mat)
    mod = obj.modifiers.new("Outline", type='SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.material_offset = 1

# The figure follows the 2D shorts: thick rounded limbs with a spherical cap at every
# joint (shoulders, elbows, hips, knees), fused into one seamless body, and a round head
# floating just above the neck.
LIMB_RADIUS = 0.05
HEAD_RADIUS = 0.17
THIGH, SHIN = 0.46, 0.44
SPINE_LENGTH = 0.56
UPPER_ARM, FOREARM = 0.30, 0.28
HIP_HALF, SHOULDER_HALF = 0.09, 0.10
STAND_HEIGHT = 0.76  # hip height above the snow when standing (knees slightly bent)
SEAT_HEIGHT = 0.07   # hip height above the snow when seated
UP = Vector((0.0, 0.0, 1.0))


def make_capsule(name, length, radius=LIMB_RADIUS, segments=20, rings=6):
    """Closed capsule from the origin along +Z: a cylinder with a hemispherical cap at
    each end, so two segments that share a joint meet in a clean sphere."""
    profile = []
    for i in range(1, rings + 1):  # bottom cap, pole to equator
        a = -math.pi / 2 + (math.pi / 2) * i / rings
        profile.append((radius * math.cos(a), radius * math.sin(a)))
    for i in range(rings):         # top cap, equator toward pole
        a = (math.pi / 2) * i / rings
        profile.append((radius * math.cos(a), length + radius * math.sin(a)))
    points = [(0.0, 0.0, -radius)]
    for r, z in profile:
        for k in range(segments):
            ang = 2 * math.pi * k / segments
            points.append((r * math.cos(ang), r * math.sin(ang), z))
    points.append((0.0, 0.0, length + radius))
    top = len(points) - 1

    def at(ring, k):
        return 1 + ring * segments + (k % segments)

    polys = [(0, at(0, k + 1), at(0, k)) for k in range(segments)]
    for ring in range(len(profile) - 1):
        for k in range(segments):
            polys.append((at(ring, k), at(ring, k + 1), at(ring + 1, k + 1), at(ring + 1, k)))
    polys += [(top, at(len(profile) - 1, k), at(len(profile) - 1, k + 1)) for k in range(segments)]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], polys)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(white_mat)
    mesh.materials.append(outline_mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.rotation_mode = 'QUATERNION'
    return obj


def bend(root, tip, upper, lower, toward):
    """Two-segment limb from root toward tip, folded toward `toward`.
    Returns (middle joint, reachable tip)."""
    span = tip - root
    reach = max(min(span.length, upper + lower - 1e-3), abs(upper - lower) + 1e-3)
    direction = span.normalized() if span.length > 1e-6 else -UP
    along = (upper**2 - lower**2 + reach**2) / (2 * reach)
    height = math.sqrt(max(upper**2 - along**2, 0.0))
    side = toward - toward.dot(direction) * direction
    side = side.normalized() if side.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    return root + direction * along + side * height, root + direction * reach


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def on_snow(x, y, lift=0.0):
    return Vector((x, y, mountain_height(x, y) + LIMB_RADIUS + 0.01 + lift))


# Performance: limp up the last steps (frames 1-90), turn around (90-125),
# sit down on the ridge (125-180), then let the head drop (to 200).
WALK_START_Y = 0.80
STAND_Y = 1.85
STEP = (STAND_Y - WALK_START_Y) / 3.0
SIT_BACK = 0.25
POSE_END_FRAME = 200


def pose(frame):
    """World-space joint positions of the climber at a frame."""
    f = float(frame)
    turn = smoothstep(90, 125, f)
    heading = math.pi * turn  # 0 = facing uphill (+Y), pi = facing the camera (-Y)
    fwd = Vector((math.sin(heading), math.cos(heading), 0.0))
    right = Vector((math.cos(heading), -math.sin(heading), 0.0))

    if f <= 90:
        # Three slow steps; the right leg is the sore one, so the body sinks onto it
        # and the left foot hurries through its swing.
        u = (f - 1.0) / 89.0
        k = min(2, int(u * 3.0))
        tau = u * 3.0 - k
        r_plants = [WALK_START_Y - 0.12, WALK_START_Y + STEP + 0.16, WALK_START_Y + STEP + 0.16, STAND_Y + 0.04]
        l_plants = [WALK_START_Y + 0.08, WALK_START_Y + 0.08, STAND_Y - 0.19, STAND_Y - 0.19]
        swing_r = smoothstep(0.10, 0.95, tau) if k in (0, 2) else 0.0
        swing_l = smoothstep(0.0, 0.70, tau) if k == 1 else 0.0
        foot_r = on_snow(0.10, lerp(r_plants[k], r_plants[k + 1], swing_r), 0.10 * math.sin(math.pi * swing_r))
        foot_l = on_snow(-0.10, lerp(l_plants[k], l_plants[k + 1], swing_l), 0.10 * math.sin(math.pi * swing_l))
        on_sore_leg = k == 1
        dip = (0.055 if on_sore_leg else 0.015) * math.sin(math.pi * tau)
        sway = (0.035 if on_sore_leg else -0.03) * math.sin(math.pi * tau)
        py = lerp(WALK_START_Y, STAND_Y, u)
        pelvis = Vector((sway, py, mountain_height(0.0, py) + STAND_HEIGHT - dip))
        lean = math.radians(30.0 + 5.0 * math.sin(math.pi * tau))
        head_tilt = math.radians(24.0)
        arm_swing = math.cos(math.pi * (k + tau))
        rest = 0.0
    else:
        base = Vector((0.0, STAND_Y, 0.0))
        sit = smoothstep(141, 172, f)
        step_l = smoothstep(125, 137, f)
        step_r = smoothstep(133, 145, f)
        spread = lerp(0.10, 0.19, smoothstep(125, 145, f))
        shuffle = math.sin(2.0 * math.pi * turn) if turn < 1.0 else 0.0
        spot_l = base - right * spread + fwd * (lerp(-0.19, 0.0, turn) + 0.25 * step_l)
        spot_r = base + right * spread + fwd * (lerp(0.04, 0.0, turn) + 0.25 * step_r)
        foot_l = on_snow(spot_l.x, spot_l.y, 0.05 * max(0.0, shuffle) + 0.07 * math.sin(math.pi * step_l))
        foot_r = on_snow(spot_r.x, spot_r.y, 0.05 * max(0.0, -shuffle) + 0.07 * math.sin(math.pi * step_r))
        seat = base - fwd * (SIT_BACK * sit)
        pelvis = Vector((seat.x, seat.y, mountain_height(seat.x, seat.y) + lerp(STAND_HEIGHT, SEAT_HEIGHT, sit)))
        lean = math.radians(lerp(30.0, 14.0, smoothstep(95, 172, f)) + 26.0 * math.sin(math.pi * sit))
        head_tilt = math.radians(lerp(24.0, 52.0, smoothstep(168, 198, f)))
        arm_swing = -(1.0 - smoothstep(90, 105, f))
        rest = smoothstep(150, 176, f)  # hands settle onto the knees

    joints = {"pelvis": pelvis}
    joints["hip_l"] = pelvis - right * HIP_HALF
    joints["hip_r"] = pelvis + right * HIP_HALF
    joints["knee_l"], joints["foot_l"] = bend(joints["hip_l"], foot_l, THIGH, SHIN, fwd + UP * 0.8 - right * 0.25)
    joints["knee_r"], joints["foot_r"] = bend(joints["hip_r"], foot_r, THIGH, SHIN, fwd + UP * 0.8 + right * 0.25)

    neck = pelvis + (UP * math.cos(lean) + fwd * math.sin(lean)) * SPINE_LENGTH
    joints["neck"] = neck
    for tag, sign in (("l", -1.0), ("r", 1.0)):
        shoulder = neck + right * (sign * SHOULDER_HALF)
        hanging = shoulder - UP * 0.54 + fwd * (-sign * 0.12 * arm_swing) + right * (sign * 0.05)
        on_knee = joints["knee_" + tag] + UP * (LIMB_RADIUS * 2.0 + 0.005) + fwd * 0.02
        elbow_hint = (-fwd + right * (sign * 0.3) - UP * 0.2).lerp(right * sign - fwd * 0.5 + UP * 0.1, rest)
        joints["sh_" + tag] = shoulder
        joints["elbow_" + tag], joints["hand_" + tag] = bend(
            shoulder, hanging.lerp(on_knee, rest), UPPER_ARM, FOREARM, elbow_hint
        )

    look = lean + head_tilt
    joints["head"] = neck + (UP * math.cos(look) + fwd * math.sin(look)) * (HEAD_RADIUS + 0.08)
    return joints


# name, start joint, end joint, length
SEGMENTS = [
    ("Spine", "pelvis", "neck", SPINE_LENGTH),
    ("Pelvis", "hip_l", "hip_r", HIP_HALF * 2),
    ("Collar", "sh_l", "sh_r", SHOULDER_HALF * 2),
    ("ThighL", "hip_l", "knee_l", THIGH),
    ("ShinL", "knee_l", "foot_l", SHIN),
    ("ThighR", "hip_r", "knee_r", THIGH),
    ("ShinR", "knee_r", "foot_r", SHIN),
    ("UpperArmL", "sh_l", "elbow_l", UPPER_ARM),
    ("ForearmL", "elbow_l", "hand_l", FOREARM),
    ("UpperArmR", "sh_r", "elbow_r", UPPER_ARM),
    ("ForearmR", "elbow_r", "hand_r", FOREARM),
]

# Every segment is its own animated capsule. The spine is the visible body: a Boolean
# union fuses all the other capsules into it each frame, so the outline traces the whole
# silhouette and no seams or rings show at the joints.
limb_collection = bpy.data.collections.new("ClimberLimbs")
scene.collection.children.link(limb_collection)
parts = {}
for name, _start, _end, length in SEGMENTS:
    part = make_capsule(name, length)
    parts[name] = part
    if name == "Spine":
        scene.collection.objects.link(part)
    else:
        limb_collection.objects.link(part)
        part.hide_render = True

body = parts["Spine"]
fuse = body.modifiers.new("FuseLimbs", type='BOOLEAN')
fuse.operation = 'UNION'
fuse.operand_type = 'COLLECTION'
fuse.collection = limb_collection
fuse.solver = 'EXACT'
outline = body.modifiers.new("Outline", type='SOLIDIFY')
outline.thickness = 0.022
outline.offset = 1.0
outline.use_flip_normals = True
outline.material_offset = 1

bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_RADIUS, segments=32, ring_count=16)
head = bpy.context.active_object
head.name = "Head"
for poly in head.data.polygons:
    poly.use_smooth = True
add_outlined_part(head)

# Bake the performance: one key per frame on every segment
for frame in range(1, POSE_END_FRAME + 1):
    joints = pose(frame)
    for name, start, end, _length in SEGMENTS:
        part = parts[name]
        part.location = joints[start]
        part.rotation_quaternion = (joints[end] - joints[start]).to_track_quat('Z', 'Y')
        part.keyframe_insert(data_path="location", frame=frame)
        part.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    head.location = joints["head"]
    head.keyframe_insert(data_path="location", frame=frame)

# 8. Top Caption Text Objects Attached to Camera
bpy.ops.object.camera_add(location=(0.0, -1.6, char_z + 1.35))
cam = bpy.context.active_object
cam.data.lens = 28
scene.camera = cam

# Camera Track-To Target
target = bpy.data.objects.new("CamTarget", None)
target.location = (0.0, 2.2, char_z + 0.5)
scene.collection.objects.link(target)

track = cam.constraints.new(type='TRACK_TO')
track.target = target
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Camera: follow the climb in close-up (1-200), then the epic pullback (200-540).
# The aim points are chosen so the head, flag and summit always stay below the caption's
# safe zone (the top 20% of the frame); SHORTS_CHECK=1 verifies it.
cam.location = (0.85, -1.6, char_z + 1.05)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (0.75, -1.7, char_z + 1.15)
cam.keyframe_insert(data_path="location", frame=200)
cam.location = (0.0, -33.0, 9.5)
cam.keyframe_insert(data_path="location", frame=540)

target.location = (0.0, 1.2, char_z + 0.45)
target.keyframe_insert(data_path="location", frame=1)
target.location = (0.0, 1.9, char_z + 0.85)
target.keyframe_insert(data_path="location", frame=90)
target.location = (0.0, 2.0, char_z + 0.80)
target.keyframe_insert(data_path="location", frame=200)
target.location = (0.0, -8.0, 5.8)
target.keyframe_insert(data_path="location", frame=540)

# Smooth Bezier interpolation for camera motion
def action_fcurves(action):
    """F-curves of an action, across Blender versions: legacy actions expose
    `action.fcurves`; layered actions (the only kind from 5.0) keep them in channelbags."""
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    curves = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                curves.extend(bag.fcurves)
    return curves


for obj in (cam, target):
    if obj.animation_data and obj.animation_data.action:
        for fcurve in action_fcurves(obj.animation_data.action):
            for kp in fcurve.keyframe_points:
                kp.interpolation = 'BEZIER'

# 3D Text HUD parented to Camera
text_mat = bpy.data.materials.new("TextWhite")
text_mat.use_nodes = True
t_bsdf = text_mat.node_tree.nodes.get("Principled BSDF")
# Pure emission at strength 1.0 (below the bloom threshold) on a black base, so scene
# lighting adds nothing and the letters stay razor-sharp with no glow.
t_bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
t_bsdf.inputs["Roughness"].default_value = 1.0
t_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
t_bsdf.inputs["Emission Strength"].default_value = 1.0

# The HUD sits on a plane this far in front of the lens. With the vertical frame
# fitted to the sensor, half the visible height/width at that distance is:
HUD_DISTANCE = 1.0
HUD_HALF_HEIGHT = HUD_DISTANCE * (cam.data.sensor_width / 2) / cam.data.lens
HUD_HALF_WIDTH = HUD_HALF_HEIGHT * scene.render.resolution_x / scene.render.resolution_y
HUD_CENTER = 0.78     # caption centre, as a fraction of the half-height above centre
SAFE_ZONE_FLOOR = 0.80  # frame height (0 = bottom, 1 = top) where the caption zone starts
cam.data.clip_start = 0.1
cam.data.clip_end = 500.0

BOLD_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
hud_font = bpy.data.fonts.load(BOLD_FONT_PATH) if os.path.exists(BOLD_FONT_PATH) else None


def create_hud_text(body, name):
    """Uppercase caption centred near the top of the frame, fixed to the camera."""
    curve = bpy.data.curves.new(name, type='FONT')
    curve.body = body.upper()
    curve.align_x = 'CENTER'
    curve.align_y = 'CENTER'
    if hud_font is not None:
        curve.font = hud_font
    obj = bpy.data.objects.new(name, curve)
    scene.collection.objects.link(obj)
    obj.data.materials.append(text_mat)
    obj.parent = cam
    # Camera looks down its local -Z; +Y is up in the frame. Being a child of the camera,
    # the caption is locked in place: centred in the top safe zone (top 20% of the frame).
    obj.location = (0.0, HUD_HALF_HEIGHT * HUD_CENTER, -HUD_DISTANCE)
    # Scale the caption so its longest line fills 70% of the frame width.
    bpy.context.view_layer.update()
    width = obj.dimensions.x
    scale = (HUD_HALF_WIDTH * 2 * 0.70) / width if width > 0 else 0.05
    obj.scale = (scale, scale, scale)
    return obj


txt1 = create_hud_text("WHEN YOU ARE\nABOUT TO GIVE UP", "Caption1")
txt2 = create_hud_text("THINK ABOUT HOW FAR\nYOU HAVE COME", "Caption2")

# Switch caption at frame 205
txt1.hide_render = False
txt1.keyframe_insert(data_path="hide_render", frame=1)
txt1.hide_render = True
txt1.keyframe_insert(data_path="hide_render", frame=205)
txt2.hide_render = True
txt2.keyframe_insert(data_path="hide_render", frame=1)
txt2.hide_render = False
txt2.keyframe_insert(data_path="hide_render", frame=205)

# Safe-zone check: nothing important may rise into the caption's zone.
if os.environ.get("SHORTS_CHECK"):
    flag_top = Vector((0.42, 4.0, peak_z + 0.9))
    summit = Vector((0.0, 4.0, peak_z))
    worst = (0.0, 0, "")
    for frame in range(scene.frame_start, scene.frame_end + 1, 3):
        scene.frame_set(frame)
        head_top = head.matrix_world.translation + UP * HEAD_RADIUS
        for label, point in (("flag", flag_top), ("summit", summit), ("head", head_top)):
            height = world_to_camera_view(scene, cam, point).y
            if height > worst[0]:
                worst = (height, frame, label)
        if frame % 45 == 1:
            print(f"CHECK frame {frame}: flag {world_to_camera_view(scene, cam, flag_top).y:.3f} "
                  f"head {world_to_camera_view(scene, cam, head_top).y:.3f}")
    verdict = "OK" if worst[0] < SAFE_ZONE_FLOOR else "VIOLATION"
    print(f"CHECK {verdict}: highest point is the {worst[2]} at {worst[0]:.3f} of frame height "
          f"(frame {worst[1]}); caption zone starts at {SAFE_ZONE_FLOOR}")
    sys.exit(0 if verdict == "OK" else 1)

# 9. Render
# SHORTS_CHUNK="i/N" renders only the i-th of N equal slices of the frame range, so
# the workflow can render slices on parallel runners and join them afterwards.
chunk = os.environ.get("SHORTS_CHUNK")
if chunk:
    chunk_index, chunk_count = (int(v) for v in chunk.split("/"))
    first_frame = scene.frame_start
    total_frames = scene.frame_end - scene.frame_start + 1
    scene.frame_start = first_frame + (total_frames * (chunk_index - 1)) // chunk_count
    scene.frame_end = first_frame + (total_frames * chunk_index) // chunk_count - 1
    print(f"Chunk {chunk_index}/{chunk_count}: frames {scene.frame_start}-{scene.frame_end}")

os.makedirs(os.path.dirname(output_path), exist_ok=True)
if still_frame:
    scene.frame_set(int(still_frame))
    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print(f"Rendered with Blender {bpy.app.version_string}: {output_path}")
