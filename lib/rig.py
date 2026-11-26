"""Shared rig for stick-figure shorts: canvas setup, an IK-posed stick figure,
floor reflections and volumetric glows. See CLAUDE.md for the visual rules."""

from manim import *
import numpy as np

FLOOR_Y = -2.2
REFLECTION_OPACITY = 0.18
WARM_WHITE = "#FFE8C2"
FIRE_RED = "#FF2A00"
FIRE_ORANGE = "#FF4500"
TITLE_Y = 4.8

HIP_HEIGHT = 1.36
TORSO = 1.10
NECK = 0.52
HEAD_RADIUS = 0.30
THIGH = SHIN = 0.72
UPPER_ARM = FOREARM = 0.46


def setup_canvas():
    """1080x1920 vertical canvas at 60fps on pure black."""
    config.pixel_width = 1080
    config.pixel_height = 1920
    config.frame_width = 9.0
    config.frame_height = 16.0
    config.frame_rate = 60
    config.background_color = "#000000"


def title_text(text, y=TITLE_Y, font_size=30):
    return Text(text.upper(), font="DejaVu Sans", weight=BOLD, font_size=font_size, color=WHITE).move_to([0, y, 0])


def scale_opacity(mobject, factor):
    """Multiply every fill and stroke opacity in a mobject, keeping its tapering."""
    for m in mobject.family_members_with_points():
        m.set_fill(opacity=m.get_fill_opacity() * factor)
        m.set_stroke(opacity=m.get_stroke_opacity() * factor)
    return mobject


def make_reflection(mobject, floor_y=FLOOR_Y, opacity=REFLECTION_OPACITY):
    """Upside-down copy mirrored in the floor plane."""
    ref = mobject.copy()
    ref.clear_updaters()
    ref.stretch(-1, dim=1, about_point=np.array([0, floor_y, 0]))
    return scale_opacity(ref, opacity)


def two_bone_ik(root, target, l1, l2, bend):
    """Joint and end point of a two-segment limb reaching from root toward target.
    `bend` (+1/-1) picks which side the middle joint folds to. Out-of-reach
    targets are clamped, so the limb straightens toward them."""
    d = target - root
    dist = float(np.linalg.norm(d))
    u = d / dist if dist > 1e-6 else np.array([0.0, -1.0, 0.0])
    reach = min(max(dist, abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3)
    a = (l1**2 - l2**2 + reach**2) / (2 * reach)
    h = np.sqrt(max(l1**2 - a**2, 0.0))
    perp = np.array([-u[1], u[0], 0.0])
    return root + u * a + perp * h * bend, root + u * reach


class StickFigure(VGroup):
    """Articulated stick figure posed with inverse kinematics.

    Pose parameters (all optional):
      lean       torso tilt in radians, positive toward the facing direction
      crouch     0..1, lowers the hips
      hip_shift  hip offset along the facing direction
      feet       (back, front) foot offsets from `x` along the facing direction
      head_tilt  extra forward tilt of the head, radians
      hands      ((dx, dy), (dx, dy)) back/front hand offsets from the shoulder
      grip       ((fx, h), (fx, h)) back/front hand targets measured from `x`
                 along the facing direction and up from the floor; overrides `hands`
    """

    def __init__(self, x=0.0, floor_y=FLOOR_Y, facing=1, **pose):
        super().__init__()
        self.base_x = x
        self.floor_y = floor_y
        self.facing = facing
        self.build_pose(**pose)

    def build_pose(self, lean=0.0, crouch=0.0, hip_shift=0.0, feet=(-0.35, 0.35), head_tilt=0.0,
                   hands=((-0.10, -0.86), (0.14, -0.84)), grip=None):
        self.submobjects = []
        f, x, fy = self.facing, self.base_x, self.floor_y

        def local(fx, h):
            return np.array([x + f * fx, fy + h, 0.0])

        hip = local(hip_shift, HIP_HEIGHT * (1 - 0.35 * crouch))
        spine = np.array([f * np.sin(lean), np.cos(lean), 0.0])
        shoulder = hip + TORSO * spine
        neck = np.array([f * np.sin(lean + head_tilt), np.cos(lean + head_tilt), 0.0])
        head_center = shoulder + NECK * neck

        foot_b, foot_f = local(feet[0], 0.0), local(feet[1], 0.0)
        knee_b, foot_b = two_bone_ik(hip, foot_b, THIGH, SHIN, bend=f)
        knee_f, foot_f = two_bone_ik(hip, foot_f, THIGH, SHIN, bend=f)

        if grip is not None:
            target_b, target_f = local(*grip[0]), local(*grip[1])
        else:
            target_b = shoulder + np.array([f * hands[0][0], hands[0][1], 0.0])
            target_f = shoulder + np.array([f * hands[1][0], hands[1][1], 0.0])
        elbow_b, hand_b = two_bone_ik(shoulder, target_b, UPPER_ARM, FOREARM, bend=-f)
        elbow_f, hand_f = two_bone_ik(shoulder, target_f, UPPER_ARM, FOREARM, bend=-f)

        stroke_cfg = dict(color=WHITE, stroke_width=14, cap_style=CapStyleType.ROUND, joint_type=LineJointType.ROUND)
        leg_b = VMobject(**stroke_cfg).set_points_as_corners([hip, knee_b, foot_b])
        leg_f = VMobject(**stroke_cfg).set_points_as_corners([hip, knee_f, foot_f])
        torso = Line(hip, shoulder, **stroke_cfg)
        arm_b = VMobject(**stroke_cfg).set_points_as_corners([shoulder, elbow_b, hand_b])
        arm_f = VMobject(**stroke_cfg).set_points_as_corners([shoulder, elbow_f, hand_f])
        head = Circle(radius=HEAD_RADIUS, color=WHITE, fill_color=WHITE, fill_opacity=1.0, stroke_width=0).move_to(head_center)

        body = VGroup(leg_b, leg_f, torso, arm_b, arm_f, head)

        # Layered halo: wide faint strokes underneath the body
        glow = VGroup()
        for width, op in ((46, 0.035), (32, 0.06), (22, 0.09)):
            layer = body.copy().set_stroke(WHITE, width=width, opacity=op)
            layer[-1].set_fill(WHITE, opacity=op)
            glow.add(layer)

        self.add(glow, body)
        return self

    # Live hand positions (valid mid-animation, since they read the drawn arms)
    def back_hand(self):
        return self[1][3].get_points()[-1].copy()

    def front_hand(self):
        return self[1][4].get_points()[-1].copy()

    def reflection(self, opacity=REFLECTION_OPACITY):
        """Mirrored copy. The body is a solid dimmed colour (identical to translucent
        white on the black canvas) so overlapping limbs do not brighten."""
        ref = self.copy()
        ref.stretch(-1, dim=1, about_point=np.array([0, self.floor_y, 0]))
        scale_opacity(ref[0], opacity)
        ref[1].set_color(interpolate_color(BLACK, WHITE, opacity))
        return ref


def pose_to(char, ref, x=None, **pose):
    """Animations that move a character (and its reflection) smoothly into a new pose."""
    if x is not None:
        char.base_x = x
    target = StickFigure(x=char.base_x, floor_y=char.floor_y, facing=char.facing, **pose)
    return [Transform(char, target), Transform(ref, target.reflection())]


def floor_disc(center, radius, floor_y, **style):
    """Disc clipped so nothing is drawn below the floor plane."""
    d = floor_y - center[1]
    if d >= radius:
        return None
    if d <= -radius:
        return Circle(radius=radius, **style).move_to(center)
    a = np.arcsin(d / radius)
    return Arc(radius=radius, start_angle=a, angle=PI - 2 * a, arc_center=center, **style)


def make_radial_glow(center, color, max_radius=3.5, peak_opacity=0.45, layers=40, floor_y=FLOOR_Y):
    """Concentric translucent discs. Per-layer opacity is solved so the stacked
    result falls off smoothly from `peak_opacity` at the centre to 0.0 at the rim."""
    center = np.array(center, dtype=float)
    glow = VGroup()
    stacked = 0.0
    for i in range(layers, 0, -1):
        r = max_radius * i / layers
        target = peak_opacity * (1 - (i - 1) / layers) ** 2
        op = 1 - (1 - target) / (1 - stacked)
        stacked = target
        disc = floor_disc(center, r, floor_y, stroke_width=0, fill_color=color, fill_opacity=op)
        if disc is not None:
            glow.add(disc)
    glow.set_z_index(-1)
    return glow
