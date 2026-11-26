"""Shared helpers for Blender (3D) shorts. See "3D Scene Standards" in CLAUDE.md.

Provides the render setup, the fused capsule stick figure, camera-locked captions,
slice rendering (SHORTS_CHUNK) and the caption safe-zone check."""

import math
import os

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

LIMB_RADIUS = 0.05
HEAD_RADIUS = 0.17
THIGH, SHIN = 0.46, 0.44
SPINE_LENGTH = 0.56
UPPER_ARM, FOREARM = 0.30, 0.28
HIP_HALF, SHOULDER_HALF = 0.09, 0.10
NECK_GAP = 0.08  # gap between the neck and the floating head
OUTLINE_THICKNESS = 0.022
UP = Vector((0.0, 0.0, 1.0))

HUD_DISTANCE = 1.0
HUD_CENTER = 0.78       # caption centre, as a fraction of the half-height above centre
SAFE_ZONE_FLOOR = 0.80  # frame height (0 = bottom, 1 = top) where the caption zone starts
BOLD_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------- render

def setup_render(scene, width, height, fps=60):
    """Eevee, H.264 MP4, 16 samples, Standard view transform, bloom on strong emitters only."""
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps

    scene.eevee.taa_render_samples = int(os.environ.get("SHORTS_SAMPLES", "16"))
    # Emission 1.0 must be exactly white (Blender's default AgX renders it light grey).
    scene.view_settings.view_transform = "Standard"
    # Bloom threshold above 1.0: captions stay razor-sharp, only strong emitters glow.
    if hasattr(scene.eevee, "use_bloom"):
        scene.eevee.use_bloom = True
        scene.eevee.bloom_threshold = 1.4
        scene.eevee.bloom_knee = 0.1
        scene.eevee.bloom_intensity = 0.06
        scene.eevee.bloom_radius = 5.5


def set_video_output(scene, path):
    if hasattr(scene.render.image_settings, "media_type"):  # Blender 5.0+
        scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.filepath = os.path.abspath(path)


def set_still_output(scene, path):
    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.abspath(path)


def chunk_range(first, last):
    """Frame range of the slice named by SHORTS_CHUNK="i/N" (the whole range if unset)."""
    chunk = os.environ.get("SHORTS_CHUNK")
    if not chunk:
        return first, last
    index, count = (int(v) for v in chunk.split("/"))
    total = last - first + 1
    return first + (total * (index - 1)) // count, first + (total * index) // count - 1


# ------------------------------------------------------------------------ materials

def make_material(name, color, roughness=0.7, emission=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "NONE"
    return mat


def character_materials():
    white = make_material("CharWhite", (1.0, 1.0, 1.0), roughness=0.4, emission=0.65)
    outline = make_material("CharOutline", (0.01, 0.01, 0.01), roughness=1.0)
    outline.use_backface_culling = True
    return white, outline


# --------------------------------------------------------------------------- figure

def make_capsule(name, length, materials, radius=LIMB_RADIUS, segments=20, rings=6):
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
    for mat in materials:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.rotation_mode = "QUATERNION"
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


class FusedFigure:
    """Stick figure in the 2D style. Every segment is an animated capsule. A geometry-nodes
    modifier gathers the capsules into one body object and a voxel remesh fuses them into
    a single skin each frame, so the outline traces the whole silhouette and the joints
    show no seams. (A Boolean union does the same job but drops the body on some poses.)
    The round head floats above the neck.

    Drive it with `bake(pose, first, last)`, where `pose(frame)` returns world-space
    joints: pelvis, neck, head, hip_l/r, knee_l/r, foot_l/r, sh_l/r, elbow_l/r, hand_l/r."""

    VOXEL_SIZE = 0.011

    def __init__(self, scene, name="Climber"):
        self.scene = scene
        white, outline = character_materials()
        limbs = bpy.data.collections.new(name + "Limbs")
        scene.collection.children.link(limbs)
        self.parts = {}
        for seg_name, _start, _end, length in SEGMENTS:
            part = make_capsule(name + seg_name, length, (white, outline))
            self.parts[seg_name] = part
            limbs.objects.link(part)
            part.hide_render = True  # only the fused body is rendered

        mesh = bpy.data.meshes.new(name + "Body")
        mesh.materials.append(white)
        mesh.materials.append(outline)
        self.body = bpy.data.objects.new(name + "Body", mesh)
        scene.collection.objects.link(self.body)

        tree = bpy.data.node_groups.new(name + "GatherLimbs", "GeometryNodeTree")
        tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gather = tree.nodes.new("GeometryNodeCollectionInfo")
        gather.inputs["Collection"].default_value = limbs
        gather.transform_space = "RELATIVE"
        realize = tree.nodes.new("GeometryNodeRealizeInstances")
        result = tree.nodes.new("NodeGroupOutput")
        tree.links.new(gather.outputs[0], realize.inputs[0])
        tree.links.new(realize.outputs[0], result.inputs[0])
        join = self.body.modifiers.new("GatherLimbs", type="NODES")
        join.node_group = tree

        skin = self.body.modifiers.new("Fuse", type="REMESH")
        skin.mode = "VOXEL"
        skin.voxel_size = self.VOXEL_SIZE
        skin.adaptivity = 0.0
        skin.use_smooth_shade = True
        self._add_outline(self.body)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_RADIUS, segments=32, ring_count=16)
        self.head = bpy.context.active_object
        self.head.name = name + "Head"
        for poly in self.head.data.polygons:
            poly.use_smooth = True
        self.head.data.materials.append(white)
        self.head.data.materials.append(outline)
        self._add_outline(self.head)

    @staticmethod
    def _add_outline(obj):
        mod = obj.modifiers.new("Outline", type="SOLIDIFY")
        mod.thickness = OUTLINE_THICKNESS
        mod.offset = 1.0
        mod.use_flip_normals = True
        mod.material_offset = 1

    def bake(self, pose, first, last):
        """One key per frame on every segment."""
        for frame in range(first, last + 1):
            joints = pose(frame)
            for seg_name, start, end, _length in SEGMENTS:
                part = self.parts[seg_name]
                part.location = joints[start]
                part.rotation_quaternion = (joints[end] - joints[start]).to_track_quat("Z", "Y")
                part.keyframe_insert(data_path="location", frame=frame)
                part.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            self.head.location = joints["head"]
            self.head.keyframe_insert(data_path="location", frame=frame)


# ------------------------------------------------------------------------- captions

def hud_extents(scene, cam):
    """Half-width and half-height of the visible frame on the caption plane."""
    half_long = HUD_DISTANCE * (cam.data.sensor_width / 2) / cam.data.lens
    width, height = scene.render.resolution_x, scene.render.resolution_y
    if width >= height:
        return half_long, half_long * height / width
    return half_long * width / height, half_long


def add_hud_text(scene, cam, body, name, max_width=0.70, max_height=0.13):
    """Uppercase bold white caption, parented to the camera so it is locked in the frame,
    centred in the top safe zone. Sized so its longest line fills `max_width` of the frame
    width, unless that would make the block taller than `max_height` of the frame height."""
    cam.data.clip_start = min(cam.data.clip_start, 0.1)
    material = bpy.data.materials.get("CaptionWhite")
    if material is None:
        # Black base + emission 1.0 (below the bloom threshold): pure white, no glow.
        material = make_material("CaptionWhite", (0.0, 0.0, 0.0), roughness=1.0)
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0

    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = body.upper()
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    if os.path.exists(BOLD_FONT_PATH):
        curve.font = bpy.data.fonts.load(BOLD_FONT_PATH, check_existing=True)
    obj = bpy.data.objects.new(name, curve)
    scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = cam

    half_width, half_height = hud_extents(scene, cam)
    obj.location = (0.0, half_height * HUD_CENTER, -HUD_DISTANCE)  # camera looks down -Z
    bpy.context.view_layer.update()
    scale = (half_width * 2 * max_width) / max(obj.dimensions.x, 1e-6)
    scale = min(scale, (half_height * 2 * max_height) / max(obj.dimensions.y, 1e-6))
    obj.scale = (scale, scale, scale)
    return obj


def show_between(obj, first, last, scene_first=1):
    """Render the object only from frame `first` up to (not including) `last`."""
    obj.hide_render = first > scene_first
    obj.keyframe_insert(data_path="hide_render", frame=scene_first)
    obj.hide_render = False
    obj.keyframe_insert(data_path="hide_render", frame=first)
    if last is not None:
        obj.hide_render = True
        obj.keyframe_insert(data_path="hide_render", frame=last)


def safe_zone_check(scene, cam, points, first, last, label=""):
    """Project `points(frame)` -> {name: Vector} through the camera for the whole range and
    report the highest one. Returns True when everything stays below the caption zone."""
    worst = (0.0, first, "")
    for frame in range(first, last + 1, 3):
        scene.frame_set(frame)
        for name, point in points(frame).items():
            height = world_to_camera_view(scene, cam, point).y
            if height > worst[0]:
                worst = (height, frame, name)
    ok = worst[0] < SAFE_ZONE_FLOOR
    print(f"CHECK {'OK' if ok else 'VIOLATION'} {label}: highest point is the {worst[2]} at "
          f"{worst[0]:.3f} of frame height (frame {worst[1]}); caption zone starts at {SAFE_ZONE_FLOOR}")
    return ok
