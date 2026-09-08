# =============================================================================
# shot_animation.py — The wind-up between choosing a shot and striking it.
#
# A shot used to happen the instant it was decided: the cue vanished and the
# ball was already moving.  That reads fine for your own shots, where you chose
# the line yourself, but it makes the AI's shots impossible to follow — the
# table simply rearranges itself.
#
# So a shot now runs through three phases before the ball is touched:
#
#   hold    the cue sits still on the line it is going to play, long enough to
#           read where it is aimed
#   pull    the cue draws back, further the harder the shot
#   strike  it comes forward into the ball, fast, and the ball is struck at the
#           exact moment the tip arrives
#
# The class owns nothing but time.  It reports how far the cue should sit from
# its resting position, and says when the tip has reached the ball; the game
# applies the impulse at that moment.  Nothing here touches pygame, physics, or
# the cue itself, which is what makes the timing straightforward to test.
# =============================================================================

from utils.constants import (
    SHOT_AIM_HOLD_SECONDS,
    SHOT_PULL_SECONDS,
    SHOT_STRIKE_SECONDS,
    CUE_PULL_BASE,
    CUE_PULL_POWER,
)


class ShotAnimation:
    """The cue's wind-up, measured in seconds and pixels of offset.

    Parameters
    ----------
    power : float
        Shot power in [0, 1].  A harder shot is drawn further back.
    reach : float
        How far past its resting position the tip travels to touch the ball.
        The game works this out from the cue's rest gap and the ball radius.
    aim_hold : float | None
        Seconds to sit still on the aiming line first.  The AI uses the full
        hold so its aim can be read; your own shots skip it, because you have
        been looking down that line the whole time already.
    """

    def __init__(
        self,
        power: float,
        reach: float = 0.0,
        aim_hold: float | None = None,
    ):
        power = max(0.0, min(1.0, power))
        self.hold_seconds = SHOT_AIM_HOLD_SECONDS if aim_hold is None else max(0.0, aim_hold)
        self.pull_seconds = SHOT_PULL_SECONDS
        self.strike_seconds = SHOT_STRIKE_SECONDS
        self.pull_distance = CUE_PULL_BASE + power * CUE_PULL_POWER
        self.reach = reach
        self.elapsed = 0.0

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------

    @property
    def total_seconds(self) -> float:
        return self.hold_seconds + self.pull_seconds + self.strike_seconds

    @property
    def struck(self) -> bool:
        """True once the tip has reached the ball."""
        return self.elapsed >= self.total_seconds

    def update(self, dt: float) -> bool:
        """Advance by *dt* seconds.  Returns True on the frame it strikes."""
        if self.struck:
            return True
        self.elapsed += dt
        return self.struck

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    @property
    def offset(self) -> float:
        """Pixels to add to the cue's resting gap from the ball.

        Positive is drawn back, negative is through the ball's resting gap and
        into it.
        """
        time_left = self.elapsed

        if time_left < self.hold_seconds:
            return 0.0
        time_left -= self.hold_seconds

        if time_left < self.pull_seconds:
            # Eased out: quick off the mark, settling at the top of the swing.
            fraction = time_left / self.pull_seconds
            return self.pull_distance * (1.0 - (1.0 - fraction) ** 2)
        time_left -= self.pull_seconds

        # Eased in: the cue is slowest at the top and fastest at the ball,
        # which is what makes the strike read as a hit rather than a slide.
        fraction = min(1.0, time_left / self.strike_seconds) if self.strike_seconds else 1.0
        target = -self.reach
        return self.pull_distance + (target - self.pull_distance) * fraction * fraction
