# Render command:
# manim -qh --resolution 1080,1920 --fps 60 scenes/wall_story.py WallStory

from manim import *
import numpy as np

config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0
config.frame_rate = 60
config.background_color = "#000000"


class StickFigure(VGroup):
    def __init__(self, x=0.0, y=-2.2, facing=1, **kwargs):
        super().__init__(**kwargs)
        self.base_x = x
        self.floor_y = y
        self.facing = facing
        self.build_pose(lean=0.0, head_tilt=0.0, arm_raise=0.0, reach_wall=0.0, hug=0.0)

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
        glow = body.copy().set_stroke(WHITE, width=28, opacity=0.14)
        glow[-1].set_fill(WHITE, opacity=0.14).scale(1.18)

        self.add(glow, body)
        return self


def make_reflection(mobject, floor_y=-2.2, opacity=0.16):
    ref = mobject.copy()
    ref.stretch(-1, dim=1, about_point=np.array([0, floor_y, 0]))
    ref.set_opacity(opacity)
    return ref


def make_radial_glow(center, color, max_radius=3.5, peak_opacity=0.25, layers=14):
    glow = VGroup()
    for i in range(layers, 0, -1):
        r = max_radius * (i / layers)
        op = peak_opacity * ((1 - (i - 1) / layers) ** 2)
        c = Circle(radius=r, stroke_width=0, fill_color=color, fill_opacity=op).move_to(center)
        glow.add(c)
    return glow


class WallStory(Scene):
    def construct(self):
        floor_y = -2.2

        # Floor subtle line
        floor_line = Line([-4.5, floor_y, 0], [4.5, floor_y, 0], color="#222222", stroke_width=2)
        self.add(floor_line)

        # Fire glow band along floor
        fire_glow = VGroup(
            make_radial_glow([-2.2, floor_y + 0.2, 0], "#FF2A00", max_radius=2.6, peak_opacity=0.18),
            make_radial_glow([0.0, floor_y + 0.2, 0], "#FF4500", max_radius=3.0, peak_opacity=0.22),
            make_radial_glow([2.2, floor_y + 0.2, 0], "#FF2A00", max_radius=2.6, peak_opacity=0.18),
        )
        fire_strip = RoundedRectangle(width=8.2, height=0.35, corner_radius=0.15, stroke_width=0, fill_color="#FF3B00", fill_opacity=0.65).move_to([0, floor_y + 0.12, 0])
        fire_group = VGroup(fire_glow, fire_strip)
        fire_ref = make_reflection(fire_strip, floor_y=floor_y, opacity=0.22)

        # Typography
        title_1 = Text("WE BUILT THIS WALL TOGETHER.", font="DejaVu Sans", weight=BOLD, font_size=30, color=WHITE).move_to([0, 5.2, 0])
        title_2 = Text("LET'S TAKE IT DOWN TOGETHER.", font="DejaVu Sans", weight=BOLD, font_size=30, color=WHITE).move_to([0, 4.65, 0])

        # Characters
        left_char = StickFigure(x=-1.65, y=floor_y, facing=1)
        right_char = StickFigure(x=1.65, y=floor_y, facing=-1)
        left_char.build_pose(lean=0.8, arm_raise=0.85)
        right_char.build_pose(lean=0.6, arm_raise=0.55)

        left_ref = make_reflection(left_char, floor_y=floor_y)
        right_ref = make_reflection(right_char, floor_y=floor_y)

        self.add(fire_group, fire_ref, left_ref, right_ref, left_char, right_char)
        self.play(FadeIn(title_1, shift=DOWN * 0.15), run_time=0.8)

        # Act 1: Bricks stack in center (0.8s - 4.0s)
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

            # Alternate character aggression
            if i % 2 == 0:
                left_char.build_pose(lean=1.0, arm_raise=1.0)
                right_char.build_pose(lean=0.5, arm_raise=0.4)
            else:
                left_char.build_pose(lean=0.5, arm_raise=0.4)
                right_char.build_pose(lean=1.0, arm_raise=1.0)

            left_ref.become(make_reflection(left_char, floor_y=floor_y))
            right_ref.become(make_reflection(right_char, floor_y=floor_y))

            bricks.add(brick)
            self.play(brick.animate.move_to([0, y_pos, 0]), run_time=0.28, rate_func=rush_into)
            b_ref = make_reflection(brick, floor_y=floor_y, opacity=0.14)
            brick_refs.add(b_ref)
            self.add(b_ref)

        # Act 2: Fire extinguishes, characters slump against wall (4.0s - 6.0s)
        slumped_left = StickFigure(x=-1.15, y=floor_y, facing=1).build_pose(lean=0.35, head_tilt=0.8, reach_wall=0.75)
        slumped_right = StickFigure(x=1.15, y=floor_y, facing=-1).build_pose(lean=0.35, head_tilt=0.8, reach_wall=0.75)

        self.play(
            FadeOut(fire_group),
            FadeOut(fire_ref),
            Transform(left_char, slumped_left),
            Transform(right_char, slumped_right),
            Transform(left_ref, make_reflection(slumped_left, floor_y=floor_y)),
            Transform(right_ref, make_reflection(slumped_right, floor_y=floor_y)),
            run_time=1.4,
        )
        self.wait(0.6)

        # Act 3: Taking down the wall together (6.0s - 9.5s)
        self.play(FadeIn(title_2, shift=DOWN * 0.15), run_time=0.8)

        spotlight = make_radial_glow([0, 0.2, 0], WHITE, max_radius=4.2, peak_opacity=0.20, layers=16)
        self.add(spotlight)
        self.bring_to_front(left_char, right_char, bricks)

        for idx in range(num_bricks - 1, -1, -1):
            b = bricks[idx]
            br = brick_refs[idx]
            direction = LEFT if idx % 2 == 0 else RIGHT
            self.play(
                FadeOut(b, shift=direction * 0.8 + DOWN * 0.3, scale=0.6),
                FadeOut(br),
                run_time=0.24,
            )

        # Act 4: Embrace in warm white glow (9.5s - 12.0s)
        hug_left = StickFigure(x=-0.38, y=floor_y, facing=1).build_pose(hug=1.0)
        hug_right = StickFigure(x=0.38, y=floor_y, facing=-1).build_pose(hug=1.0)

        self.play(
            Transform(left_char, hug_left),
            Transform(right_char, hug_right),
            Transform(left_ref, make_reflection(hug_left, floor_y=floor_y)),
            Transform(right_ref, make_reflection(hug_right, floor_y=floor_y)),
            spotlight.animate.scale(1.15),
            run_time=1.2,
        )
        self.wait(0.8)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.6)
