"""Cheap shot geometry used to prune candidates before they are simulated.

Simulating one candidate shot costs milliseconds; deciding that the cue ball
cannot possibly reach the object ball, or that the object ball cannot possibly
reach the pocket, costs microseconds.  Everything in this module is pure
geometry on stationary ball positions -- no physics, no allocation in the hot
loops -- so the search can spend its whole budget on shots that are actually
plausible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from entities.table import Table
from utils.constants import BALL_RADIUS, RESTITUTION_CUSHION
from utils.vector import Vec2


# Two balls touch when their centres are this far apart, so a path is blocked
# when an obstacle centre lies closer than this to the line of travel.
CLEARANCE = BALL_RADIUS * 2.0

# Beyond this cut angle the object ball barely moves towards the pocket and
# the shot is not worth a simulation slot.
MAX_CUT_ANGLE = math.radians(75.0)
MIN_CUT_COS = math.cos(MAX_CUT_ANGLE)

# Centre-to-centre distance between cue ball and object ball at contact.
CONTACT_DISTANCE = BALL_RADIUS * 2.0


Obstacle = tuple[int, float, float]   # (number, x, y)


@dataclass(frozen=True)
class PotShot:
    """A geometrically plausible way to send one ball into one pocket."""

    target_number: int
    pocket_index: int
    ghost_x: float
    ghost_y: float
    aim_angle: float
    cut_cos: float
    cue_distance: float
    object_distance: float
    difficulty: float
    is_bank: bool = False

    @property
    def ghost(self) -> Vec2:
        return Vec2(self.ghost_x, self.ghost_y)


def active_obstacles(snapshot) -> list[Obstacle]:
    """All balls still on the table, as cheap (number, x, y) tuples."""
    return [(b.number, b.x, b.y) for b in snapshot.balls if not b.pocketed]


def path_is_clear(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    obstacles: Sequence[Obstacle],
    ignore: Iterable[int] = (),
    clearance: float = CLEARANCE,
) -> bool:
    """True when no obstacle centre lies within *clearance* of segment a->b."""
    skip = set(ignore)
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    limit_sq = clearance * clearance

    if seg_len_sq < 1e-9:
        return True

    for number, ox, oy in obstacles:
        if number in skip:
            continue

        # Project the obstacle centre onto the segment, clamped to its ends.
        t = ((ox - ax) * dx + (oy - ay) * dy) / seg_len_sq
        if t <= 0.0:
            cx, cy = ax, ay
        elif t >= 1.0:
            cx, cy = bx, by
        else:
            cx = ax + t * dx
            cy = ay + t * dy

        gap_x = ox - cx
        gap_y = oy - cy
        if gap_x * gap_x + gap_y * gap_y < limit_sq:
            return False

    return True


def pot_shots(
    cue_x: float,
    cue_y: float,
    targets: Sequence[Obstacle],
    table: Table,
    obstacles: Sequence[Obstacle],
) -> list[PotShot]:
    """Every plausible (target, pocket) pot from this cue position.

    Returned easiest-first.  A pot survives only if the object ball has a clear
    run to the pocket, the cue ball has a clear run to the ghost-ball position,
    the ghost position is on the table, and the cut angle is playable.
    """
    left, right = table.left, table.right
    top, bottom = table.top, table.bottom

    found: list[PotShot] = []

    for number, tx, ty in targets:
        for pocket_index, pocket in enumerate(table.pockets):
            px, py = pocket.pos.x, pocket.pos.y

            to_pocket_x = px - tx
            to_pocket_y = py - ty
            object_distance = math.hypot(to_pocket_x, to_pocket_y)
            if object_distance < 1e-6:
                continue
            to_pocket_x /= object_distance
            to_pocket_y /= object_distance

            # Ghost ball: where the cue ball centre must be at contact.
            ghost_x = tx - to_pocket_x * CONTACT_DISTANCE
            ghost_y = ty - to_pocket_y * CONTACT_DISTANCE
            if not (left <= ghost_x <= right and top <= ghost_y <= bottom):
                continue

            aim_x = ghost_x - cue_x
            aim_y = ghost_y - cue_y
            cue_distance = math.hypot(aim_x, aim_y)
            if cue_distance < 1e-6:
                continue
            aim_x /= cue_distance
            aim_y /= cue_distance

            # Cut angle between the cue ball's approach and the object ball's
            # departure.  A negative cosine means we would be cutting it
            # backwards, which is impossible.
            cut_cos = aim_x * to_pocket_x + aim_y * to_pocket_y
            if cut_cos < MIN_CUT_COS:
                continue

            # The object ball must be able to reach the pocket. The cue ball is
            # ignored here: at contact it sits behind the object ball, and its
            # resting position is not where it will be when the ball sets off.
            if not path_is_clear(
                tx, ty, px, py, obstacles, ignore=(number, 0)
            ):
                continue

            # The cue ball must be able to reach the ghost position. The target
            # itself is ignored -- it sits one contact-distance away by
            # construction and would otherwise always register as a blocker.
            if not path_is_clear(
                cue_x, cue_y, ghost_x, ghost_y, obstacles, ignore=(number, 0)
            ):
                continue

            found.append(
                PotShot(
                    target_number=number,
                    pocket_index=pocket_index,
                    ghost_x=ghost_x,
                    ghost_y=ghost_y,
                    aim_angle=math.atan2(aim_y, aim_x),
                    cut_cos=cut_cos,
                    cue_distance=cue_distance,
                    object_distance=object_distance,
                    difficulty=pot_difficulty(cue_distance, object_distance, cut_cos),
                )
            )

    found.sort(key=lambda shot: (shot.difficulty, shot.target_number, shot.pocket_index))
    return found


def pot_difficulty(cue_distance: float, object_distance: float, cut_cos: float) -> float:
    """Lower is easier.

    Aiming error grows with how far the cue ball travels, and the margin for
    error at the pocket shrinks with both the object ball's run and the cut
    angle -- a thin cut converts a small aiming error into a large one.
    """
    return object_distance / max(cut_cos, 0.05) + 0.35 * cue_distance


def clear_line_of_sight(
    from_x: float,
    from_y: float,
    to_x: float,
    to_y: float,
    obstacles: Sequence[Obstacle],
    ignore: Iterable[int] = (),
) -> bool:
    """Convenience wrapper used by placement search."""
    return path_is_clear(from_x, from_y, to_x, to_y, obstacles, ignore)


# ---------------------------------------------------------------------------
# Bank shots
#
# To bank a ball off a rail into a pocket, aim the object ball at a virtual
# image of that pocket on the far side of the rail; the ball reaches the rail,
# rebounds, and arrives at the real pocket.
#
# The image is NOT a plain mirror.  A cushion here keeps the ball's velocity
# along the rail but returns only RESTITUTION_CUSHION of the component into
# it, so the ball leaves at a shallower angle than it arrived.  Covering less
# distance across the table per unit along it is the same as aiming at a
# pocket image pushed 1/e further out, which is what _mirror_across() builds.
# A plain mirror aims these shots several degrees too steep and almost all of
# them miss.
#
# Both legs of the path have to be clear, and the bounce point has to land on
# solid cushion rather than in a pocket mouth.
# ---------------------------------------------------------------------------


def _mirror_across(line: float, coordinate: float) -> float:
    """The pocket image that accounts for the cushion's restitution."""
    return line - (coordinate - line) / RESTITUTION_CUSHION

#: A cushion returns only part of the speed it receives, and the path is longer
#: than a direct pot, so banks are ranked well below direct shots.
BANK_DIFFICULTY_MULTIPLIER = 2.2


def _rail_lines(table: Table) -> list[tuple[str, float]]:
    """The four mirror lines, in ball-centre coordinates."""
    return [
        ("x", table.left + BALL_RADIUS),
        ("x", table.right - BALL_RADIUS),
        ("y", table.top + BALL_RADIUS),
        ("y", table.bottom - BALL_RADIUS),
    ]


def _bounce_is_on_solid_cushion(table: Table, axis: str, bx: float, by: float) -> bool:
    """False when the bounce point falls in a pocket mouth instead of a rail."""
    corner_half = BALL_RADIUS * 2.0
    side_half = BALL_RADIUS * 2.22
    for pocket in table.pockets:
        if pocket.kind == "corner":
            corner_half = pocket.mouth_half_width
        else:
            side_half = pocket.mouth_half_width

    # Keep a ball's width away from a jaw, or the shot clips it instead of
    # rebounding cleanly.
    margin = BALL_RADIUS

    if axis == "x":
        # Left or right rail: only the two corner mouths interrupt it.
        return (
            by > table.top + corner_half + margin
            and by < table.bottom - corner_half - margin
        )

    # Top or bottom rail: two corner mouths plus the side pocket in the middle.
    if bx <= table.left + corner_half + margin:
        return False
    if bx >= table.right - corner_half - margin:
        return False
    if abs(bx - table.center.x) <= side_half + margin:
        return False
    return True


def bank_shots(
    cue_x: float,
    cue_y: float,
    targets: Sequence[Obstacle],
    table: Table,
    obstacles: Sequence[Obstacle],
) -> list[PotShot]:
    """One-cushion bank shots, easiest first."""
    left, right = table.left, table.right
    top, bottom = table.top, table.bottom

    found: list[PotShot] = []

    for number, tx, ty in targets:
        for pocket_index, pocket in enumerate(table.pockets):
            px, py = pocket.pos.x, pocket.pos.y

            for axis, line in _rail_lines(table):
                # Image of the pocket behind the rail.
                if axis == "x":
                    mirror_x, mirror_y = _mirror_across(line, px), py
                else:
                    mirror_x, mirror_y = px, _mirror_across(line, py)

                leg_x = mirror_x - tx
                leg_y = mirror_y - ty
                total_length = math.hypot(leg_x, leg_y)
                if total_length < 1e-6:
                    continue
                leg_x /= total_length
                leg_y /= total_length

                # Where the ball meets the rail.
                if axis == "x":
                    span = mirror_x - tx
                    if abs(span) < 1e-6:
                        continue
                    t = (line - tx) / span
                else:
                    span = mirror_y - ty
                    if abs(span) < 1e-6:
                        continue
                    t = (line - ty) / span
                if not (0.02 < t < 0.98):
                    continue

                bounce_x = tx + (mirror_x - tx) * t
                bounce_y = ty + (mirror_y - ty) * t
                if not _bounce_is_on_solid_cushion(table, axis, bounce_x, bounce_y):
                    continue

                # How far the ball actually rolls: out to the rail, then in to
                # the pocket.  The distance to the image is longer than that.
                path_length = math.hypot(bounce_x - tx, bounce_y - ty) + math.hypot(
                    px - bounce_x, py - bounce_y
                )

                # Ghost ball sits behind the object ball on the line towards
                # the mirrored pocket.
                ghost_x = tx - leg_x * CONTACT_DISTANCE
                ghost_y = ty - leg_y * CONTACT_DISTANCE
                if not (left <= ghost_x <= right and top <= ghost_y <= bottom):
                    continue

                aim_x = ghost_x - cue_x
                aim_y = ghost_y - cue_y
                cue_distance = math.hypot(aim_x, aim_y)
                if cue_distance < 1e-6:
                    continue
                aim_x /= cue_distance
                aim_y /= cue_distance

                cut_cos = aim_x * leg_x + aim_y * leg_y
                if cut_cos < MIN_CUT_COS:
                    continue

                # Both legs of the object ball's path, then the cue ball's own.
                if not path_is_clear(
                    tx, ty, bounce_x, bounce_y, obstacles, ignore=(number, 0)
                ):
                    continue
                if not path_is_clear(
                    bounce_x, bounce_y, px, py, obstacles, ignore=(number, 0)
                ):
                    continue
                if not path_is_clear(
                    cue_x, cue_y, ghost_x, ghost_y, obstacles, ignore=(number, 0)
                ):
                    continue

                found.append(
                    PotShot(
                        target_number=number,
                        pocket_index=pocket_index,
                        ghost_x=ghost_x,
                        ghost_y=ghost_y,
                        aim_angle=math.atan2(aim_y, aim_x),
                        cut_cos=cut_cos,
                        cue_distance=cue_distance,
                        object_distance=path_length,
                        difficulty=pot_difficulty(cue_distance, path_length, cut_cos)
                        * BANK_DIFFICULTY_MULTIPLIER,
                        is_bank=True,
                    )
                )

    found.sort(key=lambda shot: (shot.difficulty, shot.target_number, shot.pocket_index))
    return found
