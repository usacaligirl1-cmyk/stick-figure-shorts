# Render command (Blender; Eevee needs a display, so wrap in xvfb-run on headless machines):
# xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/mountain_climb.mp4
#
# Preview a single frame instead of the full video:
# SHORTS_STILL=300 xvfb-run -a blender -b -P scenes/mountain_climb.py -- output/preview.png

import os
import sys
import math
import random
import bpy
from mathutils import Vector

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

# Soft glow around emissive elements (bloom exists in Eevee up to Blender 4.1)
if hasattr(scene.eevee, "use_bloom"):
    scene.eevee.use_bloom = True
    scene.eevee.bloom_intensity = 0.06
    scene.eevee.bloom_radius = 5.5

# 3. Starry Night Sky World
world = bpy.data.worlds.new("NightSky")
scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()

bg = wnodes.new("ShaderNodeBackground")
bg.inputs["Color"].default_value = (0.008, 0.012, 0.025, 1.0)
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

# 5. Procedural 3D Snowy Mountain Ridge
def mountain_height(x, y):
    # Ridge peaks near y = 4.0, slopes steeply downward toward negative y
    ridge = math.exp(-((x * 0.22) ** 2)) * (14.0 - abs(y - 4.0) * 0.48)
    crag = (
        0.55 * math.sin(x * 1.4 + y * 0.7)
        + 0.30 * math.cos(x * 2.9 - y * 1.8)
        + 0.15 * math.sin(x * 5.5 + y * 4.2)
    ) * min(1.0, abs(x) * 0.35 + 0.15)
    return max(-8.0, ridge + crag)

nx, ny = 90, 110
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
    p.use_smooth = True

mountain = bpy.data.objects.new("Mountain", m_mesh)
scene.collection.objects.link(mountain)

snow_mat = bpy.data.materials.new("SnowMat")
snow_mat.use_nodes = True
sn_bsdf = snow_mat.node_tree.nodes.get("Principled BSDF")
sn_bsdf.inputs["Base Color"].default_value = (0.72, 0.78, 0.88, 1.0)
sn_bsdf.inputs["Roughness"].default_value = 0.85
mountain.data.materials.append(snow_mat)

# 6. Glowing Golden Trail Climbing Up the Ridge
trail_pts = []
steps = 120
for s in range(steps):
    t = s / (steps - 1)
    ty = -30.0 + t * 32.0  # From bottom valley (-30) up to character (+2.0)
    tx = 0.85 * math.sin(t * 14.0) * (1.0 - 0.3 * t)
    tz = mountain_height(tx, ty) + 0.06
    trail_pts.append((tx, ty, tz))

curve_data = bpy.data.curves.new("GoldenTrail", type='CURVE')
curve_data.dimensions = '3D'
curve_data.bevel_depth = 0.06
curve_data.bevel_resolution = 4
spline = curve_data.splines.new('POLY')
spline.points.add(len(trail_pts) - 1)
for idx, pt in enumerate(trail_pts):
    spline.points[idx].co = (pt[0], pt[1], pt[2], 1.0)

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

char_root = bpy.data.objects.new("StickCharacter", None)
char_root.location = (char_x, char_y, char_z)
scene.collection.objects.link(char_root)

# Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(0, 0, 1.18))
head = bpy.context.active_object
head.parent = char_root
add_outlined_part(head)

# Torso
bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=0.58, location=(0, 0, 0.75))
torso = bpy.context.active_object
torso.parent = char_root
add_outlined_part(torso)

# Legs (seated/tired pose)
for side in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.048, depth=0.52, location=(side * 0.11, -0.18, 0.36))
    leg = bpy.context.active_object
    leg.rotation_euler = (math.radians(55), 0, 0)
    leg.parent = char_root
    add_outlined_part(leg)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.46, location=(side * 0.14, -0.12, 0.68))
    arm = bpy.context.active_object
    arm.rotation_euler = (math.radians(35), side * math.radians(-12), 0)
    arm.parent = char_root
    add_outlined_part(arm)

# Exhausted slump animation (frames 1 -> 180)
char_root.location = (char_x, char_y, char_z + 0.18)
char_root.keyframe_insert(data_path="location", frame=1)
char_root.location = (char_x, char_y, char_z - 0.05)
char_root.keyframe_insert(data_path="location", frame=160)

head.location = (0, -0.08, 1.12)
head.keyframe_insert(data_path="location", frame=1)
head.location = (0, -0.14, 1.02)
head.keyframe_insert(data_path="location", frame=160)

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

# Camera Pullback Keyframes: Close-up (1-200) -> Epic Pullback (200-540)
cam.location = (0.85, -1.4, char_z + 1.25)
cam.keyframe_insert(data_path="location", frame=1)
cam.location = (0.75, -1.7, char_z + 1.15)
cam.keyframe_insert(data_path="location", frame=200)
cam.location = (0.0, -33.0, 9.5)
cam.keyframe_insert(data_path="location", frame=540)

target.location = (0.0, 2.0, char_z + 0.55)
target.keyframe_insert(data_path="location", frame=200)
target.location = (0.0, -8.0, 1.5)
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
t_bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
t_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
t_bsdf.inputs["Emission Strength"].default_value = 2.5

# The HUD sits on a plane this far in front of the lens. With the vertical frame
# fitted to the sensor, half the visible height/width at that distance is:
HUD_DISTANCE = 1.0
HUD_HALF_HEIGHT = HUD_DISTANCE * (cam.data.sensor_width / 2) / cam.data.lens
HUD_HALF_WIDTH = HUD_HALF_HEIGHT * scene.render.resolution_x / scene.render.resolution_y
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
    # Camera looks down its local -Z; +Y is up in the frame.
    obj.location = (0.0, HUD_HALF_HEIGHT * 0.60, -HUD_DISTANCE)
    # Scale the caption to fill 86% of the frame width.
    bpy.context.view_layer.update()
    width = obj.dimensions.x
    scale = (HUD_HALF_WIDTH * 2 * 0.86) / width if width > 0 else 0.05
    obj.scale = (scale, scale, scale)
    return obj


txt1 = create_hud_text("It feels like I've gotten nowhere.", "CaptionStruggle")
txt2 = create_hud_text("Look how far you've come.", "CaptionReveal")

# Switch caption at frame 205
txt1.hide_render = False
txt1.keyframe_insert(data_path="hide_render", frame=1)
txt1.hide_render = True
txt1.keyframe_insert(data_path="hide_render", frame=205)
txt2.hide_render = True
txt2.keyframe_insert(data_path="hide_render", frame=1)
txt2.hide_render = False
txt2.keyframe_insert(data_path="hide_render", frame=205)

# 9. Render
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
