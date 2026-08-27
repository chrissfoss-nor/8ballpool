# =============================================================================
# vector.py — Lightweight 2-D vector class used throughout the physics engine
# and rendering code.  No numpy dependency — just pure Python math.
# =============================================================================

import math


class Vec2:
    """Immutable-style 2-D vector with all the operations needed for pool physics.

    Instances are mutable (x, y are plain attributes) so callers can update
    position/velocity in place, but every arithmetic operator returns a *new*
    Vec2 rather than modifying self.  This mirrors the behaviour of pygame's
    Vector2 while staying dependency-free.
    """

    __slots__ = ("x", "y")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    def copy(self) -> "Vec2":
        """Return a shallow copy of this vector."""
        return Vec2(self.x, self.y)

    # ------------------------------------------------------------------
    # Arithmetic operators  (all return new Vec2)
    # ------------------------------------------------------------------

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        """Scale vector by a scalar."""
        return Vec2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Vec2":
        """Support scalar * Vec2."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> "Vec2":
        """Divide vector by a scalar.  Raises ZeroDivisionError if scalar == 0."""
        return Vec2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "Vec2":
        """Negate the vector."""
        return Vec2(-self.x, -self.y)

    def __iadd__(self, other: "Vec2") -> "Vec2":
        self.x += other.x
        self.y += other.y
        return self

    def __isub__(self, other: "Vec2") -> "Vec2":
        self.x -= other.x
        self.y -= other.y
        return self

    def __imul__(self, scalar: float) -> "Vec2":
        self.x *= scalar
        self.y *= scalar
        return self

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec2):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return f"Vec2({self.x:.3f}, {self.y:.3f})"

    # ------------------------------------------------------------------
    # Length / magnitude
    # ------------------------------------------------------------------

    def length_sq(self) -> float:
        """Squared magnitude — cheaper than length() when only comparing."""
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        """Euclidean magnitude of the vector."""
        return math.sqrt(self.length_sq())

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def normalize(self) -> "Vec2":
        """Return a unit vector in the same direction.

        Returns Vec2(0, 0) for the zero vector to avoid division by zero.
        """
        mag = self.length()
        if mag < 1e-9:
            return Vec2(0.0, 0.0)
        return Vec2(self.x / mag, self.y / mag)

    # ------------------------------------------------------------------
    # Dot product
    # ------------------------------------------------------------------

    def dot(self, other: "Vec2") -> float:
        """Scalar dot product."""
        return self.x * other.x + self.y * other.y

    # ------------------------------------------------------------------
    # Distance helpers
    # ------------------------------------------------------------------

    def distance_to(self, other: "Vec2") -> float:
        """Euclidean distance from this point to *other*."""
        return (other - self).length()

    def distance_sq_to(self, other: "Vec2") -> float:
        """Squared distance — avoids a sqrt when you only need comparisons."""
        return (other - self).length_sq()

    # ------------------------------------------------------------------
    # Angle helpers
    # ------------------------------------------------------------------

    def angle(self) -> float:
        """Angle of this vector in radians, measured CCW from the +x axis."""
        return math.atan2(self.y, self.x)

    @staticmethod
    def from_angle(angle_rad: float, length: float = 1.0) -> "Vec2":
        """Create a vector from a polar angle (radians) and optional length."""
        return Vec2(math.cos(angle_rad) * length, math.sin(angle_rad) * length)

    def rotate(self, angle_rad: float) -> "Vec2":
        """Return a new vector rotated by *angle_rad* radians CCW."""
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------

    def reflect(self, normal: "Vec2") -> "Vec2":
        """Reflect this vector across a surface described by *normal* (unit vector).

        Uses the formula:  v' = v - 2*(v·n)*n
        """
        factor = 2.0 * self.dot(normal)
        return Vec2(self.x - factor * normal.x, self.y - factor * normal.y)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_tuple(self) -> tuple:
        """Return (x, y) as a plain Python tuple (handy for pygame calls)."""
        return (self.x, self.y)

    def to_int_tuple(self) -> tuple:
        """Return (int(x), int(y)) — required by many pygame drawing functions."""
        return (int(self.x), int(self.y))
