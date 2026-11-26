# Render command:
# manim -qh --resolution 1080,1920 --fps 60 --media_dir temp scenes/tug_of_war.py TugOfWar && cp temp/videos/tug_of_war/1920p60/TugOfWar.mp4 output/

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manim import *
import numpy as np

from lib.rig import (
    FLOOR_Y, WARM_WHITE, FIRE_RED, FIRE_ORANGE,
    StickFigure, make_radial_glow, make_reflection, pose_to, setup_canvas, title_text,
)

setup_canvas()

ROPE_COLOR = "#CFCFCF"
START_X = 2.3


def tug_pose(effort):
    """Braced tug-of-war stance. effort 1 = heaving back, 0 = being dragged forward."""
    return dict(
        lean=-(0.12 + 0.42 * effort),
        crouch=0.30 + 0.12 * effort,
        hip_shift=-(0.05 + 0.30 * effort),
        feet=(-0.35, 0.50),
        grip=((0.35, 1.72), (0.80, 1.72)),
    )


SLUMP = dict(lean=0.50, crouch=0.30, hip_shift=-0.12, feet=(-0.30, 0.30), head_tilt=0.45,
             grip=((0.20, 0.82), (0.36, 0.84)))
HOLD = dict(lean=0.04, crouch=0.05, grip=((0.32, 1.50), (0.66, 1.50)))
REACH = dict(lean=0.10, crouch=0.08, feet=(-0.40, 0.42), grip=((0.34, 1.50), (0.86, 1.50)))
HAUL = dict(lean=-0.14, crouch=0.10, feet=(-0.22, 0.26), grip=((0.06, 1.50), (0.40, 1.50)))


class TugOfWar(Scene):
    def construct(self):
        floor_y = FLOOR_Y
        floor_point = np.array([0, floor_y, 0])

        floor_line = Line([-4.5, floor_y, 0], [4.5, floor_y, 0], color="#222222", stroke_width=2)
        self.add(floor_line)

        # Conflict fire: a pit of red/orange glow between the two
        fire_glow = VGroup(
            make_radial_glow([-1.5, floor_y + 0.2, 0], FIRE_RED, max_radius=2.2, peak_opacity=0.70),
            make_radial_glow([0.0, floor_y + 0.2, 0], FIRE_ORANGE, max_radius=3.0, peak_opacity=0.90),
            make_radial_glow([1.5, floor_y + 0.2, 0], FIRE_RED, max_radius=2.2, peak_opacity=0.70),
        ).set_z_index(-1)
        fire_strip = RoundedRectangle(
            width=5.2, height=0.3, corner_radius=0.14, stroke_width=0, fill_color="#FF3B00", fill_opacity=0.65
        ).move_to([0, floor_y + 0.15, 0])
        fire_group = VGroup(fire_glow, fire_strip)
        fire_ref = VGroup(make_reflection(fire_glow), make_reflection(fire_strip, opacity=0.30))

        title_1 = title_text("We pulled against each other.", y=5.08)
        title_2 = title_text("Then we pulled closer.", y=4.52)

        # Characters, braced and facing each other
        left = StickFigure(x=-START_X, facing=1, **tug_pose(0.5))
        right = StickFigure(x=START_X, facing=-1, **tug_pose(0.5))
        left_ref, right_ref = left.reflection(), right.reflection()

        # Rope runs through all four hands, with a red knot marking the middle
        rope = VMobject(color=ROPE_COLOR, stroke_width=8, cap_style=CapStyleType.ROUND, joint_type=LineJointType.ROUND)
        knot = Circle(radius=0.11, stroke_width=0, fill_color="#FF3B00", fill_opacity=1.0)
        rope_ref = VGroup()

        def rope_points():
            return [left.back_hand(), left.front_hand(), right.front_hand(), right.back_hand()]

        def follow_hands(m):
            m.set_points_as_corners(rope_points())

        def follow_rope(m):
            pts = rope.get_points()
            m.move_to((pts[0] + pts[-1]) / 2)

        def mirror_rope(m):
            m.become(make_reflection(VGroup(rope, knot), opacity=0.16))

        follow_hands(rope)
        follow_rope(knot)
        mirror_rope(rope_ref)
        rope.add_updater(follow_hands)
        knot.add_updater(follow_rope)
        rope_ref.add_updater(mirror_rope)

        self.add(fire_group, fire_ref, left_ref, right_ref, rope_ref, left, right, rope, knot)
        self.play(FadeIn(title_1, shift=DOWN * 0.15), run_time=0.8)

        # Act 1: Tug of war. The whole line lurches back and forth over the fire.
        for dx in (-0.45, 0.40, -0.35, 0.50, -0.25, 0.0):
            left_effort, right_effort = (1.0, 0.0) if dx < 0 else (0.0, 1.0) if dx > 0 else (0.6, 0.6)
            flare = 1.10 if dx != 0 else 1.0
            self.play(
                *pose_to(left, left_ref, x=-START_X + dx, **tug_pose(left_effort)),
                *pose_to(right, right_ref, x=START_X + dx, **tug_pose(right_effort)),
                fire_glow.animate(rate_func=there_and_back).scale(flare, about_point=floor_point),
                fire_ref[0].animate(rate_func=there_and_back).scale(flare, about_point=floor_point),
                run_time=0.5,
            )

        # Act 2: Exhausted. The rope drops, the fire dies, both slump.
        rope.remove_updater(follow_hands)
        slack = rope.copy().set_points_as_corners(
            [[-1.9, floor_y + 0.05, 0], [-0.6, floor_y + 0.05, 0], [0.6, floor_y + 0.05, 0], [1.9, floor_y + 0.05, 0]]
        )
        self.play(
            Transform(rope, slack, rate_func=rush_into, run_time=0.45),
            FadeOut(fire_group),
            FadeOut(fire_ref),
            *pose_to(left, left_ref, **SLUMP),
            *pose_to(right, right_ref, **SLUMP),
            run_time=1.3,
        )
        self.wait(0.5)

        # Act 3: They pick the rope back up and pull each other closer.
        spotlight = make_radial_glow([0, 0.2, 0], WARM_WHITE, max_radius=3.6, peak_opacity=0.50, layers=48)
        spot_ref = make_reflection(spotlight)

        held_left = StickFigure(x=-START_X, facing=1, **HOLD)
        held_right = StickFigure(x=START_X, facing=-1, **HOLD)
        held_rope = rope.copy().set_points_as_corners(
            [held_left.back_hand(), held_left.front_hand(), held_right.front_hand(), held_right.back_hand()]
        )
        self.play(
            FadeIn(title_2, shift=DOWN * 0.15),
            FadeIn(spotlight),
            FadeIn(spot_ref),
            *pose_to(left, left_ref, **HOLD),
            *pose_to(right, right_ref, **HOLD),
            Transform(rope, held_rope),
            run_time=0.9,
        )
        rope.add_updater(follow_hands)

        xs = (1.95, 1.62, 1.32, 1.05)
        for x in xs:
            # Reach forward along the rope, then haul and step in.
            self.play(
                *pose_to(left, left_ref, **REACH),
                *pose_to(right, right_ref, **REACH),
                run_time=0.22,
            )
            self.play(
                *pose_to(left, left_ref, x=-x, **HAUL),
                *pose_to(right, right_ref, x=x, **HAUL),
                spotlight.animate.scale(1.05, about_point=floor_point),
                spot_ref.animate.scale(1.05, about_point=floor_point),
                run_time=0.30,
            )

        # Act 4: The rope is gone; hands meet and rise in the warm light.
        rope.clear_updaters()
        knot.clear_updaters()
        rope_ref.clear_updaters()
        together = dict(lean=0.03, feet=(-0.28, 0.24), grip=((-0.20, 1.55), (0.62, 3.12)))
        self.play(
            FadeOut(rope),
            FadeOut(knot),
            FadeOut(rope_ref),
            *pose_to(left, left_ref, x=-0.62, **together),
            *pose_to(right, right_ref, x=0.62, **together),
            spotlight.animate.scale(1.12, about_point=floor_point),
            spot_ref.animate.scale(1.12, about_point=floor_point),
            run_time=1.0,
        )
        self.wait(0.9)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.6)
