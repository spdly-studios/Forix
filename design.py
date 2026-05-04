# forix/design.py
"""
╔══════════════════════════════════════════════════════════════════════╗
║             FORIX — SINGLE SOURCE OF TRUTH FOR ALL UI               ║
║                                                                      ║
║  Every color, size, radius, font, spacing value lives here.         ║
║  No other file may hardcode a hex string, px value, or font name.   ║
║  All UI files do:  import design as D  then use D.COLOR_BG etc.     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WINDOW LAYOUT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIN_MIN_W       = 1100
WIN_MIN_H       = 700
WIN_DEFAULT_W   = 1360
WIN_DEFAULT_H   = 860

SIDEBAR_W       = 216   # expanded width
SIDEBAR_W_MIN   = 52    # icon-only collapsed width
SIDEBAR_H_HDR   = 56    # header area height
SIDEBAR_H_BTN   = 38    # nav button height
SIDEBAR_H_FOOT  = 32    # footer area height

HEADER_H        = 52    # top page header bar
STATUSBAR_H     = 24    # bottom status bar

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SPACING  (px – use these for setContentsMargins / setSpacing)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SP_1  =  4
SP_2  =  8
SP_3  = 12
SP_4  = 16
SP_5  = 20
SP_6  = 24
SP_8  = 32

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BORDER RADIUS  (px)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
R_SM =  4
R_MD =  8
R_LG = 12

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMPONENT HEIGHTS  (px)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
H_BTN_SM = 26
H_BTN    = 30
H_BTN_LG = 36
H_INPUT  = 30
H_ROW    = 30    # table / list row

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TYPOGRAPHY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FONT_UI   = "Segoe UI"      # primary sans (Windows)
FONT_MONO = "Consolas"      # mono fallback

# sizes in pt (QFont uses pt by default)
FSIZE_XS   = 8
FSIZE_SM   = 9
FSIZE_BASE = 10
FSIZE_MD   = 11
FSIZE_LG   = 13
FSIZE_XL   = 16
FSIZE_2XL  = 20
FSIZE_PAGE = 15

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COLOR PALETTE  (dark zinc/indigo)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Backgrounds
COLOR_BG        = "#09090b"   # zinc-950 – page / window fill
COLOR_SURF      = "#18181b"   # zinc-900 – cards, panels, inputs
COLOR_SURF2     = "#27272a"   # zinc-800 – elevated, table alt row
COLOR_SURF3     = "#3f3f46"   # zinc-700 – hover
COLOR_SURF4     = "#52525b"   # zinc-600 – pressed / strong

# Borders
COLOR_BDR       = "#2e2e33"   # subtle divider
COLOR_BDR2      = "#3f3f46"   # standard border
COLOR_BDR3      = "#52525b"   # strong / focused border

# Brand – indigo
COLOR_ACC       = "#6366f1"   # indigo-500
COLOR_ACC_DK    = "#4f46e5"   # indigo-600
COLOR_ACC_XDK   = "#4338ca"   # indigo-700
COLOR_ACC_LT    = "#e0e7ff"   # indigo-100
COLOR_ACC2      = "#a855f7"   # purple-500  (secondary accent)

# Tints – use for selected/hover backgrounds on dark surfaces (rgba)
COLOR_ACC_TINT  = "rgba(99,102,241,0.13)"
COLOR_ACC_TINT2 = "rgba(99,102,241,0.24)"
COLOR_ACC_TINTB = "rgba(99,102,241,0.40)"
COLOR_ACC2_TINT = "rgba(168,85,247,0.13)"
COLOR_ACC2_TNTB = "rgba(168,85,247,0.40)"
COLOR_OK_TINT   = "rgba(16,185,129,0.13)"
COLOR_OK_TNTB   = "rgba(16,185,129,0.40)"
COLOR_WRN_TINT  = "rgba(245,158,11,0.13)"
COLOR_WRN_TNTB  = "rgba(245,158,11,0.40)"
COLOR_ERR_TINT  = "rgba(239,68,68,0.13)"
COLOR_ERR_TNTB  = "rgba(239,68,68,0.40)"
COLOR_INF_TINT  = "rgba(59,130,246,0.13)"

# Semantic
COLOR_OK        = "#10b981"   # emerald-500
COLOR_OK_DK     = "#059669"
COLOR_WRN       = "#f59e0b"   # amber-500
COLOR_WRN_DK    = "#d97706"
COLOR_ERR       = "#ef4444"   # red-500
COLOR_ERR_DK    = "#dc2626"
COLOR_ERR_XDK   = "#b91c1c"
COLOR_INF       = "#3b82f6"   # blue-500

# Text
COLOR_TXT       = "#f4f4f5"   # zinc-100
COLOR_TXT2      = "#a1a1aa"   # zinc-400
COLOR_TXT_HEAD  = "#ffffff"
COLOR_TXT_DIS   = "#71717a"   # zinc-500
COLOR_TXT_ON_ACC= "#ffffff"

# Absolute
COLOR_WHITE     = "#ffffff"
COLOR_BLACK     = "#000000"

# Accent disabled state
COLOR_ACC_DIS   = "#312e81"
COLOR_ACC_DIS_B = "#3730a3"

# Sidebar (slightly darker than page for contrast)
COLOR_SB        = "#0d0d10"
COLOR_SB_BDR    = "#1c1c21"
COLOR_SB_LBL    = "#4b5563"
COLOR_SB_TXT    = "#6b7280"
COLOR_SB_TXTH   = "#e4e4e7"
COLOR_SB_TXTA   = "#ffffff"
COLOR_SB_HOVER  = "#18181b"
COLOR_SB_ACTIVE = "#27272a"

# Project type accent colours
CTYPE_ARDUINO   = "#f59e0b"
CTYPE_KICAD     = "#3b82f6"
CTYPE_PYTHON    = "#6366f1"
CTYPE_NODE      = "#10b981"
CTYPE_WEB       = "#ec4899"
CTYPE_CAD       = "#8b5cf6"
CTYPE_EMBEDDED  = "#f97316"
CTYPE_DOC       = "#6b7280"
CTYPE_DATA      = "#06b6d4"
CTYPE_GENERIC   = "#71717a"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BACKWARD-COMPAT ALIASES  (so old  import theme as T  still works)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Layout
WINDOW_MIN_W      = WIN_MIN_W
WINDOW_MIN_H      = WIN_MIN_H
SIDEBAR_WIDTH     = SIDEBAR_W
SIDEBAR_WIDTH_MIN = SIDEBAR_W_MIN

# Spacing
space_xs  = SP_1
space_sm  = SP_2
space_md  = SP_3
space_lg  = SP_4
space_xl  = SP_6
space_2xl = SP_8

# Radii
radius_sm = R_SM
radius_md = R_MD
radius_lg = R_LG

# Heights
btn_height_sm = H_BTN_SM
btn_height_md = H_BTN
btn_height_lg = H_BTN_LG

# Fonts (px approximations for old code that used font_* in QSS)
font_family = f"'{FONT_UI}', 'Segoe UI', Arial, sans-serif"
font_mono   = f"'{FONT_MONO}', Consolas, 'Courier New', monospace"
font_xs     = 10
font_sm     = 10
font_base   = 10
font_md     = 11
font_lg     = 13
font_xl     = 16
font_xxl    = 20
font_page   = 14

# Colors (old names)
bg_page         = COLOR_BG
bg_dialog       = COLOR_SURF
surface         = COLOR_SURF
surface_raised  = COLOR_SURF2
surface_hover   = COLOR_SURF3
surface_pressed = COLOR_SURF4
border          = COLOR_BDR2
border_strong   = COLOR_BDR3
border_focus    = COLOR_ACC
accent          = COLOR_ACC
accent_dark     = COLOR_ACC_DK
accent_xdark    = COLOR_ACC_XDK
accent_light    = COLOR_ACC_LT
accent_mid      = COLOR_ACC_LT
accent2         = COLOR_ACC2
accent2_light   = "#f3e8ff"
accent2_mid     = "#d8b4fe"
accent_tint         = COLOR_ACC_TINT
accent_tint_strong  = COLOR_ACC_TINT2
accent_tint_border  = COLOR_ACC_TINTB
accent2_tint        = COLOR_ACC2_TINT
accent2_tint_border = COLOR_ACC2_TNTB
success_tint        = COLOR_OK_TINT
success_tint_border = COLOR_OK_TNTB
warn_tint           = COLOR_WRN_TINT
warn_tint_border    = COLOR_WRN_TNTB
danger_tint         = COLOR_ERR_TINT
danger_tint_border  = COLOR_ERR_TNTB
info_tint           = COLOR_INF_TINT
danger_strong  = COLOR_ERR_DK
danger_deep    = COLOR_ERR_XDK
accent_disabled     = COLOR_ACC_DIS
accent_disabled_bdr = COLOR_ACC_DIS_B
text_primary    = COLOR_TXT
text_secondary  = COLOR_TXT2
text_heading    = COLOR_TXT_HEAD
text_on_accent  = COLOR_TXT_ON_ACC
text_disabled   = COLOR_TXT_DIS
text_placeholder= COLOR_TXT_DIS
success         = COLOR_OK
success_light   = "#d1fae5"
success_mid     = "#6ee7b7"
warn            = COLOR_WRN
warn_light      = "#fef3c7"
warn_mid        = "#fcd34d"
danger          = COLOR_ERR
danger_light    = "#fee2e2"
danger_mid      = "#fca5a5"
info            = COLOR_INF
info_light      = "#dbeafe"
white           = COLOR_WHITE
black           = COLOR_BLACK
sidebar_bg          = COLOR_SB
sidebar_border      = COLOR_SB_BDR
sidebar_label_color = COLOR_SB_LBL
sidebar_text        = COLOR_SB_TXT
sidebar_text_hover  = COLOR_SB_TXTH
sidebar_text_active = COLOR_SB_TXTA
sidebar_item_hover  = COLOR_SB_HOVER
sidebar_item_active = COLOR_SB_ACTIVE
type_arduino  = CTYPE_ARDUINO
type_kicad    = CTYPE_KICAD
type_python   = CTYPE_PYTHON
type_node     = CTYPE_NODE
type_web      = CTYPE_WEB
type_cad      = CTYPE_CAD
type_embedded = CTYPE_EMBEDDED
type_document = CTYPE_DOC
type_data     = CTYPE_DATA
type_generic  = CTYPE_GENERIC

COLORS: dict = {
    "bg": COLOR_BG, "surface": COLOR_SURF, "surface2": COLOR_SURF2,
    "surface3": COLOR_SURF3, "border": COLOR_BDR2, "border_focus": COLOR_ACC,
    "accent": COLOR_ACC, "accent_dark": COLOR_ACC_DK, "accent_light": COLOR_ACC_LT,
    "accent2": COLOR_ACC2, "warn": COLOR_WRN, "danger": COLOR_ERR,
    "success": COLOR_OK, "info": COLOR_INF,
    "text": COLOR_TXT, "text_dim": COLOR_TXT2, "text_bright": COLOR_TXT_HEAD,
    "text_on_accent": COLOR_TXT_ON_ACC, "sidebar_bg": COLOR_SB, "sidebar_text": COLOR_SB_TXT,
}
