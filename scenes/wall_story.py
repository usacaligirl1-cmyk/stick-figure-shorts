# Render command:
# manim -qh --resolution 1080,1920 --fps 60 --media_dir temp scenes/wall_story.py WallStory && cp temp/videos/wall_story/1920p60/WallStory.mp4 output/

from manim import *
import numpy as np

config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0
config.frame_rate = 60
config.background_color = "#000000"

FLOOR_Y = -2.2
REFLECTION_OPACITY = 0.18
WARM_WHITE = "#FFE8C2"


def scale_opacity(mobject, factor):
    """Multiply every fill and stroke opacity in a mobject, keeping its tapering."""
    for m in mobject.family_members_with_points():
        m.set_fill(opacity=m.get_fill_opacity() * factor)
        m.set_stroke(opacity=m.get_stroke_opacity() * factor)
    return mobject


def make_reflection(mobject, floor_y=FLOOR_Y, opacity=REFLECTION_OPACITY):
    """Upside-down copy mirrored in the floor plane."""
    ref = mobject.copy()
    ref.stretch(-1, dim=1, about_point=np.array([0, floor_y, 0]))
    return scale_opacity(ref, opacity)


class StickFigure(VGroup):
    def __init__(self, x=0.0, y=FLOOR_Y, facing=1, **pose):
        super().__init__()
        self.base_x = x
        self.floor_y = y
        self.facing = facing
        self.build_pose(**pose)

    def build_pose(self, lean=0.0, head_tilt=0.0, arm_raise=0.0, reach_wall=0.0, hug=0.0):
        self.submobjects = []
        f = self.facing
        hip = np.array([self.base_x, self.floor_y + 1.35, 0.0])
        shoulder = hip + np.array([f * (0.12 * lean + 0.15 * hug), 1.15 - 0.12 * abs(lean), 0.0])
        head_center = shoulder + np.array([f * (0.08 * lean + 0.18 * head_tilt), 0.52 - 0.08 * abs(head_tilt), 0.0])

        # Legs
        l_foot = np.array([self.base_x - 0.35, self.floor_y, 0.0])
        r_foot = np.array([self.base_x + 0.35, self.floor_y, 0.0])
        l_knee = (hip + l_foot) / 2 + np.array([f * 0.08, 0.05, 0.0])
        r_knee = (hip + r_foot) / 2 + np.array([f * 0.12, 0.05, 0.0])

        # Arms
        if hug > 0.01:
            hand_1 = shoulder + np.array([f * 0.85, 0.05, 0.0])
            elbow_1 = shoulder + np.array([f * 0.45, -0.15, 0.0])
            hand_2 = shoulder + np.array([f * 0.75, -0.25, 0.0])
            elbow_2 = shoulder + np.array([f * 0.40, -0.35, 0.0])
        elif reach_wall > 0.01:
            hand_1 = shoulder + np.array([f * (0.78 * reach_wall), 0.25 * reach_wall, 0.0])
            elbow_1 = shoulder + np.array([f * (0.42 * reach_wall), -0.05, 0.0])
            hand_2 = shoulder + np.array([f * (0.72 * reach_wall), -0.10, 0.0])
            elbow_2 = shoulder + np.array([f * (0.38 * reach_wall), -0.25, 0.0])
        else:
            hand_1 = shoulder + np.array([f * (0.45 + 0.55 * arm_raise), -0.35 + 0.75 * arm_raise, 0.0])
            elbow_1 = shoulder + np.array([f * 0.28, -0.25 + 0.35 * arm_raise, 0.0])
            hand_2 = shoulder + np.array([-f * 0.22, -0.55 + 0.25 * arm_raise, 0.0])
            elbow_2 = shoulder + np.array([-f * 0.16, -0.28, 0.0])

        stroke_cfg = dict(color=WHITE, stroke_width=14, cap_style=CapStyleType.ROUND, joint_type=LineJointType.ROUND)

        torso = Line(hip, shoulder, **stroke_cfg)
        leg_l = VMobject(**stroke_cfg).set_points_as_corners([hip, l_knee, l_foot])
        leg_r = VMobject(**stroke_cfg).set_points_as_corners([hip, r_knee, r_foot])
        arm_1 = VMobject(**stroke_cfg).set_points_as_corners([shoulder, elbow_1, hand_1])
        arm_2 = VMobject(**stroke_cfg).set_points_as_corners([shoulder, elbow_2, hand_2])
        head = Circle(radius=0.30, color=WHITE, fill_color=WHITE, fill_opacity=1.0, stroke_width=0).move_to(head_center)

        body = VGroup(leg_l, leg_r, torso, arm_2, arm_1, head)

        # Layered halo: wide faint strokes underneath the body
        glow = VGroup()
        for width, op in ((46, 0.035), (32, 0.06), (22, 0.09)):
            layer = body.copy().set_stroke(WHITE, width=width, opacity=op)
            layer[-1].set_fill(WHITE, opacity=op)
            glow.add(layer)

        self.add(glow, body)
        return self

    def reflection(self, opacity=REFLECTION_OPACITY):
        """Mirrored copy. The body is drawn as a solid dimmed colour (identical to
        translucent white on the black canvas) so overlapping limbs do not brighten."""
        ref = self.copy()
        ref.stretch(-1, dim=1, about_point=np.array([0, self.floor_y, 0]))
        glow, body = ref[0], ref[1]
        scale_opacity(glow, opacity)
        body.set_color(interpolate_color(BLACK, WHITE, opacity))
        return ref


def pose_to(char, ref, x=None, **pose):
    """Animations that move a character (and its reflection) smoothly into a new pose."""
    if x is not None:
        char.base_x = x
    target = StickFigure(x=char.base_x, y=char.floor_y, facing=char.facing, **pose)
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


class WallStory(Scene):
    def construct(self):
        floor_y = FLOOR_Y
        floor_point = np.array([0, floor_y, 0])

        # Floor subtle line
        floor_line = Line([-4.5, floor_y, 0], [4.5, floor_y, 0], color="#222222", stroke_width=2)
        self.add(floor_line)

        # Conflict fire: glow band along the floor
        fire_glow = VGroup(
            make_radial_glow([-2.2, floor_y + 0.2, 0], "#FF2A00", max_radius=2.6, peak_opacity=0.80),
            make_radial_glow([0.0, floor_y + 0.2, 0], "#FF4500", max_radius=3.0, peak_opacity=0.88),
            make_radial_glow([2.2, floor_y + 0.2, 0], "#FF2A00", max_radius=2.6, peak_opacity=0.80),
        ).set_z_index(-1)
        fire_strip = RoundedRectangle(
            width=8.2, height=0.3, corner_radius=0.14, stroke_width=0, fill_color="#FF3B00", fill_opacity=0.65
        ).move_to([0, floor_y + 0.15, 0])
        fire_group = VGroup(fire_glow, fire_strip)
        fire_ref = VGroup(make_reflection(fire_glow), make_reflection(fire_strip, opacity=0.30))

        # Typography (two lines centred on y = 4.8)
        title_1 = Text("WE BUILT THIS WALL TOGETHER.", font="DejaVu Sans", weight=BOLD, font_size=30, color=WHITE).move_to([0, 5.08, 0])
        title_2 = Text("LET'S TAKE IT DOWN TOGETHER.", font="DejaVu Sans", weight=BOLD, font_size=30, color=WHITE).move_to([0, 4.52, 0])

        # Characters
        left_char = StickFigure(x=-1.65, y=floor_y, facing=1, lean=0.8, arm_raise=0.85)
        right_char = StickFigure(x=1.65, y=floor_y, facing=-1, lean=0.6, arm_raise=0.55)
        left_ref = left_char.reflection()
        right_ref = right_char.reflection()

        self.add(fire_group, fire_ref, left_ref, right_ref, left_char, right_char)
        self.play(FadeIn(title_1, shift=DOWN * 0.15), run_time=0.8)

        # Act 1: Bricks stack in the centre while the two argue
        bricks = VGroup()
        brick_refs = VGroup()
        brick_w, brick_h = 1.25, 0.34
        num_bricks = 10

        for i in range(num_bricks):
            y_pos = floor_y + brick_h / 2 + i * (brick_h + 0.03)
            shade = "#7A7A7A" if i % 2 == 0 else "#636363"
            brick = RoundedRectangle(
                width=brick_w,
                height=brick_h,
                corner_radius=0.04,
                fill_color=shade,
                fill_opacity=1.0,
                stroke_color="#9E9E9E",
                stroke_width=2,
            ).move_to([0, y_pos + 1.2, 0])
            b_ref = make_reflection(brick, opacity=0.16)
            bricks.add(brick)
            brick_refs.add(b_ref)
            self.add(b_ref, brick)

            # Alternate character aggression
            angry = dict(lean=1.0, arm_raise=1.0)
            calm = dict(lean=0.5, arm_raise=0.4)
            left_pose, right_pose = (angry, calm) if i % 2 == 0 else (calm, angry)

            self.play(
                brick.animate(rate_func=rush_into).move_to([0, y_pos, 0]),
                b_ref.animate(rate_func=rush_into).move_to([0, 2 * floor_y - y_pos, 0]),
                *pose_to(left_char, left_ref, **left_pose),
                *pose_to(right_char, right_ref, **right_pose),
                run_time=0.28,
            )

        # Act 2: Fire dies, characters slump against the wall
        slump = dict(lean=0.35, head_tilt=0.8, reach_wall=0.75)
        self.play(
            FadeOut(fire_group),
            FadeOut(fire_ref),
            *pose_to(left_char, left_ref, x=-1.15, **slump),
            *pose_to(right_char, right_ref, x=1.15, **slump),
            run_time=1.4,
        )
        self.wait(0.6)

        # Act 3: Taking the wall down together under a warm spotlight
        spotlight = make_radial_glow([0, 0.2, 0], WARM_WHITE, max_radius=4.4, peak_opacity=0.62, layers=48)
        spot_ref = make_reflection(spotlight)
        self.play(
            FadeIn(title_2, shift=DOWN * 0.15),
            FadeIn(spotlight),
            FadeIn(spot_ref),
            run_time=0.8,
        )

        for idx in range(num_bricks - 1, -1, -1):
            direction = LEFT if idx % 2 == 0 else RIGHT
            tilt = 0.8 * idx / num_bricks  # heads lift as the wall comes down
            pull = dict(lean=0.5, head_tilt=tilt, reach_wall=1.0)
            rest = dict(lean=0.3, head_tilt=tilt, reach_wall=0.6)
            left_pose, right_pose = (pull, rest) if idx % 2 == 0 else (rest, pull)
            self.play(
                FadeOut(bricks[idx], shift=direction * 0.8 + DOWN * 0.3, scale=0.6),
                FadeOut(brick_refs[idx], shift=direction * 0.8 + UP * 0.3, scale=0.6),
                *pose_to(left_char, left_ref, **left_pose),
                *pose_to(right_char, right_ref, **right_pose),
                run_time=0.24,
            )

        # Act 4: Embrace in the warm glow
        self.play(
            *pose_to(left_char, left_ref, x=-0.38, hug=1.0),
            *pose_to(right_char, right_ref, x=0.38, hug=1.0),
            spotlight.animate.scale(1.15, about_point=floor_point),
            spot_ref.animate.scale(1.15, about_point=floor_point),
            run_time=1.2,
        )
        self.wait(0.8)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.6)
