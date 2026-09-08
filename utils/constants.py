# =============================================================================
# constants.py — All tunable game constants in one place.
# Every other module imports from here so physics feel can be tweaked easily.
# =============================================================================

# ---------------------------------------------------------------------------
# Window / display
# ---------------------------------------------------------------------------
WINDOW_W = 1280        # Window width in pixels
WINDOW_H = 800         # Window height in pixels
FPS      = 60          # Target frames per second

# ---------------------------------------------------------------------------
# Table geometry (pixels)
# The felt is the green playing surface. Cushions surround it.
# Wood border surrounds the cushions.
# ---------------------------------------------------------------------------
TABLE_OFFSET_X       = 110   # Left edge of felt from window left
TABLE_OFFSET_Y       = 160   # Top edge of felt from window top.
                             # Centres the table in the band left between the
                             # HUD strip and the power bar: at 115 the wooden
                             # rail started at y=65 and ran under the HUD.
TABLE_W              = 1060  # Felt width  (2 : 1 ratio with TABLE_H)
TABLE_H              = 530   # Felt height
CUSHION_THICKNESS    = 30    # Cushion band width (pixels)
WOOD_THICKNESS       = 20    # Wood border beyond cushion

# Pocket sizes
# WPA-style pocket mouths are specified relative to a 2.25" pool ball:
# corners are about 4.5" wide, side pockets about 5.0" wide.  The pixel
# openings below are derived from BALL_RADIUS so table feel stays in scale.

# ---------------------------------------------------------------------------
# Ball
# ---------------------------------------------------------------------------
BALL_RADIUS = 14   # pixels — all balls the same size
BALL_DIAMETER = BALL_RADIUS * 2

STANDARD_BALL_DIAMETER_IN = 2.25
STANDARD_CORNER_POCKET_MOUTH_IN = 4.50
STANDARD_SIDE_POCKET_MOUTH_IN   = 5.00

POCKET_CORNER_MOUTH_WIDTH = BALL_DIAMETER * (
    STANDARD_CORNER_POCKET_MOUTH_IN / STANDARD_BALL_DIAMETER_IN
)
POCKET_SIDE_MOUTH_WIDTH = BALL_DIAMETER * (
    STANDARD_SIDE_POCKET_MOUTH_IN / STANDARD_BALL_DIAMETER_IN
)
POCKET_CAPTURE_MARGIN = BALL_RADIUS * 0.20

POCKET_CORNER_VISUAL_RADIUS = POCKET_CORNER_MOUTH_WIDTH / 2.0
POCKET_SIDE_VISUAL_RADIUS   = POCKET_SIDE_MOUTH_WIDTH / 2.0
POCKET_CORNER_COLLISION_RADIUS = POCKET_CORNER_VISUAL_RADIUS + POCKET_CAPTURE_MARGIN
POCKET_SIDE_COLLISION_RADIUS   = POCKET_SIDE_VISUAL_RADIUS + POCKET_CAPTURE_MARGIN

# Backwards-compatible aliases for modules that only need a generic value.
POCKET_VISUAL_RADIUS    = POCKET_CORNER_VISUAL_RADIUS
POCKET_COLLISION_RADIUS = POCKET_CORNER_COLLISION_RADIUS

# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
NUM_SUBSTEPS       = 4      # Physics sub-steps per frame (stability)

# Gravity has to be expressed in the same length unit as everything else the
# physics touches, which is pixels. TABLE_W spans the 2.54 m playing surface
# of a 9-foot table, so that conversion is what sets the scale. Hard-coding
# 980 here -- g in cm/s² -- made every friction deceleration roughly four
# times too weak, and balls took eleven seconds to settle after an ordinary
# shot.
PIXELS_PER_METRE   = TABLE_W / 2.54          # ≈ 417 px/m
GRAVITY            = 9.81 * PIXELS_PER_METRE # px/s²

# Friction coefficients (multiplied by GRAVITY to get deceleration in px/s²)
FRICTION_SLIDING   = 0.20   # Kinetic/sliding friction just after cue hit
FRICTION_ROLLING   = 0.018  # Rolling friction once speed is low

# Speed thresholds
ROLLING_THRESHOLD  = 200.0  # px/s — below this, rolling friction is used
STOP_THRESHOLD     = 4.0    # px/s — below this a ball is treated as stopped

# Restitution (1.0 = perfectly elastic, 0.0 = perfectly inelastic)
RESTITUTION_BALL    = 0.96  # Ball-ball collisions keep most energy
RESTITUTION_CUSHION = 0.75  # Cushion absorbs more energy

# ---------------------------------------------------------------------------
# Spin (english)
#
# Only the cue ball carries spin: it is the only ball a tip ever touches, and
# an object ball is assumed to pick up natural roll the instant it is struck.
# That keeps every object-ball path exactly what it was before spin existed,
# so the pot geometry and the shot powers tuned against it still hold.
#
# The tip offset is measured in ball radii from the centre of the cue ball:
# (0, 0) is a centre-ball hit and the length is capped at SPIN_MAX_TIP_OFFSET,
# beyond which a real tip miscues.
#
# Vertical offset is expressed as a *deviation from natural roll* rather than
# as an absolute angular velocity, because the friction model already treats a
# struck ball as rolling from the first frame.  A centre-ball hit therefore
# behaves exactly as it always has, and the gains below say how far the two
# extremes bend away from it:
#
#   tip_y = +0.5  ->  roll =  1.25 * speed  (follow: 0.36 * speed after a full hit)
#   tip_y =  0.0  ->  roll =  1.00 * speed  (natural roll, unchanged behaviour)
#   tip_y = -0.5  ->  roll = -1.25 * speed  (draw: 0.36 * speed back off a full hit)
#
# The two extremes are the real thing: a tip half a radius off centre spins a
# ball at 2.5 * offset * speed, which is 1.25 * speed either way.  Only the
# middle of the range is bent, to keep a centre-ball hit rolling the way this
# engine has always treated it, and that is why the two gains differ.
# ---------------------------------------------------------------------------
SPIN_MAX_TIP_OFFSET = 0.5    # radii — furthest from centre the tip may strike
SPIN_FOLLOW_GAIN    = 0.5    # roll gain per radius of top spin
SPIN_DRAW_GAIN      = 4.5    # roll gain per radius of bottom spin
SPIN_SIDE_GAIN      = 1.4    # edge speed (px/s per px/s of shot) per radius of side

# Cloth friction acting on the slip between a ball's roll and its travel.
# A sphere's slip decays 3.5x faster than the speed it feeds into the centre
# of mass, which is what makes a stunned ball settle into a roll rather than
# skid forever.
SPIN_SLIP_RATIO     = 3.5
SPIN_SIDE_DECAY     = 1.8    # per second — side spin bleeds into the cloth

# A rail grabs the ball: what survives the bounce is the deviation from
# natural roll, damped, plus part of the side spin, which also kicks the ball
# sideways along the cushion as it leaves.
CUSHION_ROLL_RETENTION = 0.5
CUSHION_SPIN_RETENTION = 0.55
CUSHION_SPIN_GAIN      = 0.30

# Side spin rubs against the object ball at contact and throws it off the
# aiming line — the reason a cut played with english does not go where the
# ghost ball says it will.
SPIN_THROW_GAIN        = 0.05
SPIN_THROW_RETENTION   = 0.80

SPIN_NUDGE_STEP        = 0.10  # radii per key press on the spin controls

# ---------------------------------------------------------------------------
# Cue / shot
# ---------------------------------------------------------------------------
MAX_SHOT_IMPULSE    = 2200.0  # px/s at full power (1.0)
MIN_SHOT_IMPULSE    = 0.0     # px/s at zero power
POWER_SCROLL_STEP   = 0.05    # power delta per wheel notch / key press
POWER_DRAG_DISTANCE = 200     # pixels of right-click drag = full power
CUE_LENGTH          = 260     # px — visual length of the cue stick
CUE_WIDTH_BASE      = 7       # px — thick end width
CUE_WIDTH_TIP       = 3       # px — thin tip width
CUE_GAP_BASE        = 18      # px — minimum gap cue tip to ball centre
CUE_GAP_POWER       = 40      # px — extra gap added at full power

# The wind-up before the ball is struck (game/shot_animation.py).  A shot used
# to happen the instant it was decided, which makes the AI's shots impossible
# to follow: the table just rearranges itself.  The hold is what gives you time
# to read where it is aiming before it plays.
SHOT_AIM_HOLD_SECONDS = 0.45  # cue sits still on the aiming line (AI shots)
SHOT_PULL_SECONDS     = 0.30  # drawing the cue back
SHOT_STRIKE_SECONDS   = 0.07  # coming forward into the ball
CUE_PULL_BASE         = 22    # px drawn back at zero power
CUE_PULL_POWER        = 78    # px of extra draw at full power

# ---------------------------------------------------------------------------
# Colors (RGB)
# ---------------------------------------------------------------------------
COLOR_BACKGROUND  = (15,  20,  15)    # Dark surround
COLOR_WOOD        = (101, 67,  33)    # Wooden rail
COLOR_CUSHION     = (34,  80,  55)    # Dark green cushion
COLOR_FELT        = (53,  101, 77)    # Bright green felt
COLOR_FELT_DARK   = (45,  90,  65)    # Slightly darker felt (alternate bands)
COLOR_POCKET      = (8,   8,   8)     # Nearly-black pocket holes
COLOR_HEAD_STRING = (255, 255, 255)   # Head-string marker line
COLOR_AIM_LINE    = (255, 255, 255)   # Aiming guide line
COLOR_SHADOW      = (0,   0,   0)     # Ball shadow (blitted with alpha)
COLOR_POWER_BAR_BG   = (50,  50,  50)
COLOR_POWER_BAR_FILL = (220, 80,  40)
COLOR_HUD_BG      = (20,  25,  20)
COLOR_HUD_BORDER  = (80,  120, 80)
COLOR_TEXT        = (230, 230, 230)
COLOR_TURN_ARROW  = (255, 210, 50)
COLOR_FOUL_OVERLAY= (180, 40,  40)
COLOR_WIN_OVERLAY = (40,  160, 80)
COLOR_INVALID_GHOST = (200, 50, 50)   # Red ghost for invalid ball-in-hand
COLOR_TARGET_ARROW  = (255, 225, 90)  # Where the struck ball will travel
COLOR_RAIL_SIGHT    = (228, 220, 196)  # Ivory diamonds inlaid in the rails
COLOR_POCKET_RIM    = (24,  30,  24)   # Rim that gives the pocket its depth

# ---------------------------------------------------------------------------
# Table dressing
# ---------------------------------------------------------------------------
RAIL_SIGHT_SIZE     = 5     # Half-width of a rail diamond, in pixels
FELT_EDGE_STEPS     = 8     # Nested outlines that darken the felt at the rails
FELT_EDGE_DARKEN    = 0.55  # How dark the outermost felt edge goes (0-1)

# Ball colours indexed by ball number (0 = cue ball = white)
BALL_COLORS = {
    0:  (245, 245, 245),  # Cue ball — white
    1:  (220, 180,  30),  # Solid yellow
    2:  ( 30,  80, 200),  # Solid blue
    3:  (210,  40,  40),  # Solid red
    4:  (130,  40, 160),  # Solid purple
    5:  (220, 110,  20),  # Solid orange
    6:  ( 40, 150,  50),  # Solid green
    7:  (160,  50,  40),  # Solid maroon
    8:  ( 20,  20,  20),  # Eight ball — black
    9:  (220, 180,  30),  # Stripe yellow
    10: ( 30,  80, 200),  # Stripe blue
    11: (210,  40,  40),  # Stripe red
    12: (130,  40, 160),  # Stripe purple
    13: (220, 110,  20),  # Stripe orange
    14: ( 40, 150,  50),  # Stripe green
    15: (160,  50,  40),  # Stripe maroon
}

# ---------------------------------------------------------------------------
# HUD layout
# ---------------------------------------------------------------------------
HUD_HEIGHT          = 80    # Pixels reserved at top for player info
POWER_BAR_HEIGHT    = 30    # Pixels reserved at bottom for power indicator
POWER_BAR_W         = 400   # Width of the power bar widget
POWER_BAR_BORDER    = 3     # Border thickness around power bar

# ---------------------------------------------------------------------------
# Rack geometry
# ---------------------------------------------------------------------------
# The triangle rack apex is placed at the foot spot:
#   x = TABLE_OFFSET_X + TABLE_W * 0.75
#   y = TABLE_OFFSET_Y + TABLE_H * 0.5
# The cue ball starts at the head spot:
#   x = TABLE_OFFSET_X + TABLE_W * 0.25
#   y = TABLE_OFFSET_Y + TABLE_H * 0.5
RACK_BALL_SPACING   = BALL_RADIUS * 2 + 1   # Tiny gap prevents overlap explosion

# ---------------------------------------------------------------------------
# Aiming aid
# ---------------------------------------------------------------------------
AIM_LINE_DASH_LEN   = 12    # Length of each dash segment in the aim line
AIM_LINE_GAP_LEN    = 6     # Gap between dashes
AIM_LINE_ALPHA      = 140   # 0-255 transparency of aim line
GHOST_BALL_ALPHA    = 110   # Transparency of the ghost cue ball at contact
TARGET_ARROW_LEN    = 60    # Length of the object-ball direction arrow
