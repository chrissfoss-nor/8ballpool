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
POCKET_VISUAL_RADIUS    = 18   # Drawn circle radius
POCKET_COLLISION_RADIUS = 22   # Physics detection radius (slightly larger)

# ---------------------------------------------------------------------------
# Ball
# ---------------------------------------------------------------------------
BALL_RADIUS = 14   # pixels — all balls the same size

# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
NUM_SUBSTEPS       = 4      # Physics sub-steps per frame (stability)
GRAVITY            = 980.0  # px/s² (scaled to table pixel dimensions)

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
# Cue / shot
# ---------------------------------------------------------------------------
MAX_SHOT_IMPULSE    = 2200.0  # px/s at full power (1.0)
MIN_SHOT_IMPULSE    = 80.0    # px/s at minimum power (anything > 0)
POWER_DRAG_DISTANCE = 200     # pixels of right-click drag = full power
CUE_LENGTH          = 260     # px — visual length of the cue stick
CUE_WIDTH_BASE      = 7       # px — thick end width
CUE_WIDTH_TIP       = 3       # px — thin tip width
CUE_GAP_BASE        = 18      # px — minimum gap cue tip to ball centre
CUE_GAP_POWER       = 40      # px — extra gap added at full power

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
