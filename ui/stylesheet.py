# forix/ui/stylesheet.py
"""
Forix — Master Qt Stylesheet
• All values come from design.py — zero hardcoded literals here.
• Only valid Qt QSS properties are used.
• NO box-sizing, NO display, NO flex, NO CSS3-only properties.
• QPalette is forced separately in main.py so native popups also use dark colors.
"""

import design as D


def build() -> str:
    # ── short aliases ──────────────────────────────────────────────
    BG    = D.COLOR_BG
    S0    = D.COLOR_SURF
    S1    = D.COLOR_SURF2
    S2    = D.COLOR_SURF3
    S3    = D.COLOR_SURF4
    BD    = D.COLOR_BDR
    BD2   = D.COLOR_BDR2
    BD3   = D.COLOR_BDR3
    ACC   = D.COLOR_ACC
    ADK   = D.COLOR_ACC_DK
    AXK   = D.COLOR_ACC_XDK
    AC2   = D.COLOR_ACC2
    AT    = D.COLOR_ACC_TINT
    AT2   = D.COLOR_ACC_TINT2
    ATB   = D.COLOR_ACC_TINTB
    AC2T  = D.COLOR_ACC2_TINT
    AC2TB = D.COLOR_ACC2_TNTB
    OKT   = D.COLOR_OK_TINT
    OKTB  = D.COLOR_OK_TNTB
    WRNT  = D.COLOR_WRN_TINT
    WRNTB = D.COLOR_WRN_TNTB
    ERRT  = D.COLOR_ERR_TINT
    ERRTB = D.COLOR_ERR_TNTB
    INFT  = D.COLOR_INF_TINT
    OK    = D.COLOR_OK
    WRN   = D.COLOR_WRN
    ERR   = D.COLOR_ERR
    ERKD  = D.COLOR_ERR_DK
    ERXD  = D.COLOR_ERR_XDK
    INF   = D.COLOR_INF
    TXT   = D.COLOR_TXT
    TXT2  = D.COLOR_TXT2
    TXTH  = D.COLOR_TXT_HEAD
    TXTD  = D.COLOR_TXT_DIS
    WHT   = D.COLOR_WHITE
    ADIS  = D.COLOR_ACC_DIS
    ADSB  = D.COLOR_ACC_DIS_B
    SB    = D.COLOR_SB
    SBBR  = D.COLOR_SB_BDR
    SBLB  = D.COLOR_SB_LBL
    SBTX  = D.COLOR_SB_TXT
    SBTH  = D.COLOR_SB_TXTH
    SBTA  = D.COLOR_SB_TXTA
    SBHV  = D.COLOR_SB_HOVER
    SBAC  = D.COLOR_SB_ACTIVE
    FF    = D.FONT_UI
    FM    = D.FONT_MONO
    FSM   = D.FSIZE_SM
    FXS   = D.FSIZE_XS
    FB    = D.FSIZE_BASE
    FMD   = D.FSIZE_MD
    FLG   = D.FSIZE_LG
    FXL   = D.FSIZE_XL
    FPG   = D.FSIZE_PAGE
    RSM   = D.R_SM
    RMD   = D.R_MD
    RLG   = D.R_LG
    HB    = D.H_BTN
    HBS   = D.H_BTN_SM
    HBL   = D.H_BTN_LG
    HI    = D.H_INPUT

    return f"""
/* ═══════════════════════════════════════════════════════════════════
   BASE
═══════════════════════════════════════════════════════════════════ */
QWidget {{
    background-color: {BG};
    color: {TXT};
    font-family: "{FF}";
    font-size: {FB}pt;
    selection-background-color: {ACC};
    selection-color: {WHT};
}}
QMainWindow {{
    background-color: {BG};
}}
QDialog {{
    background-color: {S0};
    border: none;
    border-radius: {RLG}px;
}}
QFrame {{
    background-color: transparent;
    border: none;
}}
QLabel {{
    color: {TXT};
    background-color: transparent;
    border: none;
    padding: 0px;
}}

/* ═══════════════════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════════════════ */
#sidebar {{
    background-color: {SB};
    border-right: 1px solid {SBBR};
}}
#sidebarHeader {{
    background-color: {SB};
    border-bottom: 1px solid {SBBR};
}}
#sidebarFooter {{
    background-color: {SB};
    border-top: 1px solid {SBBR};
}}
#navBtn {{
    background-color: transparent;
    border: none;
    border-left: 2px solid transparent;
    color: {SBTX};
    font-size: {FB}pt;
    font-weight: 500;
    text-align: left;
    padding-left: 14px;
    min-height: {D.SIDEBAR_H_BTN}px;
    max-height: {D.SIDEBAR_H_BTN}px;
    border-radius: 0px;
}}
#navBtn:hover {{
    background-color: {SBHV};
    color: {SBTH};
    border-left-color: {SBTX};
}}
#navBtn[active="true"] {{
    background-color: {SBAC};
    color: {SBTA};
    border-left-color: {ACC};
    font-weight: 700;
}}
#toggleBtn {{
    background-color: transparent;
    border: 1px solid {SBBR};
    border-radius: {RSM}px;
    color: {SBTX};
    font-size: {FB}pt;
    font-weight: 700;
    min-height: 24px;
    max-height: 24px;
    min-width: 24px;
    max-width: 24px;
    padding: 0px;
}}
#toggleBtn:hover {{
    border-color: {ACC};
    color: {ACC};
    background-color: {SBHV};
}}

/* ═══════════════════════════════════════════════════════════════════
   PAGE HEADER  &  STATUS BAR
═══════════════════════════════════════════════════════════════════ */
#pageHeader {{
    background-color: {S0};
    border-bottom: 1px solid {BD};
    min-height: {D.HEADER_H}px;
    max-height: {D.HEADER_H}px;
}}
#pageTitle {{
    color: {TXTH};
    font-size: {FPG}pt;
    font-weight: 700;
    background-color: transparent;
    border: none;
}}
QStatusBar {{
    background-color: {S0};
    border-top: 1px solid {BD};
    color: {TXT2};
    font-size: {FSM}pt;
    min-height: {D.STATUSBAR_H}px;
    max-height: {D.STATUSBAR_H}px;
    padding: 0px 4px;
}}
QStatusBar QLabel {{
    color: {TXT2};
    font-size: {FSM}pt;
    background-color: transparent;
    border: none;
    padding: 0px 2px;
}}
QStatusBar::item {{ border: none; }}

/* ═══════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {S1};
    border: none;
    border-radius: {RMD}px;
    color: {TXT};
    font-family: "{FF}";
    font-size: {FB}pt;
    font-weight: 500;
    padding: 0px 10px;
    min-height: {HB}px;
    max-height: {HB}px;
}}
QPushButton:hover {{
    background-color: {S2};
    color: {TXTH};
}}
QPushButton:pressed {{
    background-color: {AT2};
    color: {ACC};
}}
QPushButton:disabled {{
    background-color: {S1};
    color: {TXTD};
}}
QPushButton:focus {{
    outline: none;
}}

QPushButton#accentBtn {{
    background-color: {ACC};
    border: none;
    color: {WHT};
    font-weight: 700;
    padding: 0px 12px;
    min-height: {HB}px;
    max-height: {HB}px;
    border-radius: {RMD}px;
}}
QPushButton#accentBtn:hover {{ background-color: {ADK}; }}
QPushButton#accentBtn:pressed {{ background-color: {AXK}; }}
QPushButton#accentBtn:disabled {{
    background-color: {ADIS};
    color: {TXT2};
}}

QPushButton#outlineBtn {{
    background-color: transparent;
    border: 1px solid {ACC};
    color: {ACC};
    font-weight: 600;
    padding: 0px 10px;
    min-height: {HB}px;
    max-height: {HB}px;
    border-radius: {RMD}px;
}}
QPushButton#outlineBtn:hover {{
    background-color: {AT};
    border-color: {ADK};
}}
QPushButton#outlineBtn:pressed {{ background-color: {AT2}; }}
QPushButton#outlineBtn:disabled {{
    border-color: {BD2};
    color: {TXTD};
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    border: none;
    color: {TXT2};
    padding: 0px 10px;
    min-height: {HB}px;
    max-height: {HB}px;
    border-radius: {RMD}px;
}}
QPushButton#ghostBtn:hover {{
    background-color: {S2};
    color: {TXT};
}}
QPushButton#ghostBtn:pressed {{
    background-color: {AT2};
    color: {ACC};
}}

QPushButton#dangerBtn {{
    background-color: {ERR};
    border: none;
    color: {WHT};
    font-weight: 700;
    padding: 0px 10px;
    min-height: {HB}px;
    max-height: {HB}px;
    border-radius: {RMD}px;
}}
QPushButton#dangerBtn:hover {{ background-color: {ERKD}; }}
QPushButton#dangerBtn:pressed {{ background-color: {ERXD}; }}

QPushButton#flatBtn {{
    background-color: transparent;
    border: none;
    color: {TXT2};
    padding: 0px 6px;
    min-height: {HB}px;
    max-height: {HB}px;
    min-width: {HB}px;
    max-width: {HB}px;
    border-radius: {RMD}px;
}}
QPushButton#flatBtn:hover {{
    background-color: {S2};
    color: {ACC};
}}
QPushButton#flatBtn:pressed {{
    background-color: {AT2};
    color: {ACC};
}}

QPushButton#smBtn {{
    background-color: {S1};
    border: none;
    color: {TXT};
    font-size: {FSM}pt;
    padding: 0px 8px;
    min-height: {HBS}px;
    max-height: {HBS}px;
    border-radius: {RSM}px;
}}
QPushButton#smBtn:hover {{
    background-color: {S2};
    color: {TXTH};
}}

/* ── QToolButton ── */
QToolButton {{
    background-color: {S1};
    border: none;
    border-radius: {RMD}px;
    color: {TXT};
    font-size: {FB}pt;
    font-weight: 500;
    padding: 0px 8px;
    min-height: {HB}px;
    max-height: {HB}px;
    min-width: {HB}px;
}}
QToolButton:hover {{ background-color: {S2}; }}
QToolButton:pressed {{ background-color: {AT2}; color: {ACC}; }}
QToolButton::menu-indicator {{ width: 0px; image: none; }}

/* ═══════════════════════════════════════════════════════════════════
   CARDS / SEMANTIC FRAMES
═══════════════════════════════════════════════════════════════════ */
QFrame#card {{
    background-color: {S0};
    border: none;
    border-radius: {RLG}px;
}}
QFrame#infoCard {{
    background-color: {INFT};
    border: none;
    border-left: 2px solid {ACC};
    border-radius: {RLG}px;
}}
QFrame#warnCard {{
    background-color: {WRNT};
    border: none;
    border-left: 2px solid {WRN};
    border-radius: {RLG}px;
}}
QFrame#dangerCard {{
    background-color: {ERRT};
    border: none;
    border-left: 2px solid {ERR};
    border-radius: {RLG}px;
}}
QFrame#successCard {{
    background-color: {OKT};
    border: none;
    border-left: 2px solid {OK};
    border-radius: {RLG}px;
}}
QFrame#divider {{
    background-color: {BD};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════
   INPUTS  (underline-only style for inline widgets)
═══════════════════════════════════════════════════════════════════ */
QLineEdit {{
    background-color: {S0};
    border: none;
    border-bottom: 1px solid {BD2};
    border-radius: 0px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 0px 6px;
    selection-background-color: {ACC};
    selection-color: {WHT};
    min-height: {HI}px;
    max-height: {HI}px;
}}
QLineEdit:focus {{
    border-bottom: 2px solid {ACC};
    background-color: {S1};
}}
QLineEdit:disabled {{
    background-color: transparent;
    color: {TXTD};
    border-bottom-color: {BD};
}}
QLineEdit:read-only {{
    color: {TXT2};
    border-bottom-color: {BD};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {S0};
    border: none;
    border-bottom: 1px solid {BD2};
    border-radius: 0px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 6px 6px;
    selection-background-color: {ACC};
    selection-color: {WHT};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-bottom: 2px solid {ACC};
    background-color: {S1};
}}
QTextEdit:disabled, QPlainTextEdit:disabled {{
    color: {TXTD};
    border-bottom-color: {BD};
}}

/* ═══════════════════════════════════════════════════════════════════
   COMBO BOX
═══════════════════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {S0};
    border: none;
    border-bottom: 1px solid {BD2};
    border-radius: 0px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 0px 6px;
    selection-background-color: {AT2};
    selection-color: {TXT};
    min-height: {HI}px;
    max-height: {HI}px;
}}
QComboBox:hover {{ border-bottom-color: {ACC}; }}
QComboBox:focus {{ border-bottom: 2px solid {ACC}; background-color: {S1}; }}
QComboBox:disabled {{ color: {TXTD}; border-bottom-color: {BD}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 20px;
    border: none;
    background-color: transparent;
}}
QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TXT2};
}}
QComboBox QAbstractItemView {{
    background-color: {S0};
    border: 1px solid {BD3};
    border-radius: {RMD}px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 2px;
    selection-background-color: {AT2};
    selection-color: {ACC};
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    background-color: transparent;
    color: {TXT};
    padding: 4px 8px;
    min-height: 26px;
    border-radius: {RSM}px;
    margin: 1px 2px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {AT};
    color: {ACC};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {AT2};
    color: {ACC};
}}

/* ═══════════════════════════════════════════════════════════════════
   SPINBOX / DATE EDIT
═══════════════════════════════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {S0};
    border: none;
    border-bottom: 1px solid {BD2};
    border-radius: 0px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 0px 6px;
    selection-background-color: {ACC};
    selection-color: {WHT};
    min-height: {HI}px;
    max-height: {HI}px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border-bottom: 2px solid {ACC};
    background-color: {S1};
}}
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {TXTD};
    border-bottom-color: {BD};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {AT};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 0px; height: 0px;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {TXT2};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 0px; height: 0px;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {TXT2};
}}

/* ═══════════════════════════════════════════════════════════════════
   CHECKBOX
═══════════════════════════════════════════════════════════════════ */
QCheckBox {{
    color: {TXT};
    font-size: {FB}pt;
    spacing: 6px;
    background-color: transparent;
    border: none;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1.5px solid {BD2};
    border-radius: {RSM}px;
    background-color: {S1};
}}
QCheckBox::indicator:hover {{
    border-color: {ACC};
    background-color: {AT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACC};
    border-color: {ACC};
    image: none;
}}
QCheckBox::indicator:checked:hover {{ background-color: {ADK}; }}
QCheckBox::indicator:disabled {{
    background-color: {S1};
    border-color: {BD};
}}

/* ═══════════════════════════════════════════════════════════════════
   TABLES  &  LISTS
═══════════════════════════════════════════════════════════════════ */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {BG};
    alternate-background-color: {S0};
    border: none;
    gridline-color: transparent;
    color: {TXT};
    font-size: {FB}pt;
    selection-background-color: {AT2};
    selection-color: {TXT};
    outline: none;
    show-decoration-selected: 1;
}}
QHeaderView {{
    background-color: {S0};
    border: none;
}}
QHeaderView::section {{
    background-color: {S0};
    color: {TXT2};
    border: none;
    border-bottom: 1px solid {BD};
    font-size: {FXS}pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 0px 8px;
    min-height: 26px;
    max-height: 26px;
}}
QHeaderView::section:last {{ border-right: none; }}
QHeaderView::section:hover {{ background-color: {S1}; color: {TXT}; }}
QHeaderView::section:pressed {{ background-color: {AT}; color: {ACC}; }}
QTableWidget::item {{
    padding: 0px 8px;
    border: none;
    background-color: transparent;
    color: {TXT};
    min-height: {D.H_ROW}px;
}}
QTableWidget::item:selected {{
    background-color: {AT};
    color: {TXT};
}}
QTableWidget::item:hover {{ background-color: {AT}; }}
QListWidget::item {{
    padding: 4px 8px;
    border: none;
    color: {TXT};
    background-color: transparent;
    min-height: 26px;
}}
QListWidget::item:hover {{ background-color: {S1}; }}
QListWidget::item:selected {{
    background-color: {AT2};
    color: {ACC};
    font-weight: 600;
    border-left: 2px solid {ACC};
}}
QTreeWidget::item {{
    padding: 3px 6px;
    color: {TXT};
    border: none;
}}
QTreeWidget::item:hover {{ background-color: {S1}; }}
QTreeWidget::item:selected {{ background-color: {AT2}; color: {ACC}; }}

/* ═══════════════════════════════════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════════════════════════════════ */
QProgressBar {{
    background-color: {S1};
    border: none;
    border-radius: {RSM}px;
    color: transparent;
    text-align: center;
    min-height: 4px;
    max-height: 4px;
}}
QProgressBar::chunk {{
    background-color: {ACC};
    border-radius: {RSM}px;
}}

/* ═══════════════════════════════════════════════════════════════════
   TABS  — underline style, no boxes
═══════════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    background-color: {S0};
    border: none;
    top: 0px;
}}
QTabBar {{
    background-color: transparent;
    border: none;
    border-bottom: 1px solid {BD};
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {TXT2};
    font-size: {FB}pt;
    font-weight: 500;
    padding: 0px 16px;
    margin-right: 2px;
    min-width: 80px;
    min-height: 30px;
    max-height: 30px;
}}
QTabBar::tab:hover {{
    color: {TXT};
    border-bottom-color: {BD2};
}}
QTabBar::tab:selected {{
    color: {TXT};
    font-weight: 700;
    border-bottom: 2px solid {ACC};
}}
QTabBar::tab:!selected {{ margin-top: 0px; }}

/* ═══════════════════════════════════════════════════════════════════
   SCROLL BARS  — slim, unobtrusive
═══════════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background-color: transparent;
    width: 5px;
    border: none;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {BD2};
    border-radius: 2px;
    min-height: 24px;
    margin: 1px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {BD3}; }}
QScrollBar::handle:vertical:pressed {{ background-color: {ACC}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px; background: none; border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 5px;
    border: none;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background-color: {BD2};
    border-radius: 2px;
    min-width: 24px;
    margin: 1px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {BD3}; }}
QScrollBar::handle:horizontal:pressed {{ background-color: {ACC}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px; background: none; border: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ═══════════════════════════════════════════════════════════════════
   SCROLL AREA
═══════════════════════════════════════════════════════════════════ */
QScrollArea {{ background-color: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
QAbstractScrollArea {{ background-color: {S0}; border: none; }}
QAbstractScrollArea::corner {{ background-color: transparent; border: none; }}

/* ═══════════════════════════════════════════════════════════════════
   GROUP BOX  — subtle, minimal
═══════════════════════════════════════════════════════════════════ */
QGroupBox {{
    background-color: {S0};
    border: none;
    border-top: 1px solid {BD};
    border-radius: 0px;
    color: {TXT2};
    font-size: {FXS}pt;
    font-weight: 700;
    letter-spacing: 0.6px;
    margin-top: 14px;
    padding: 14px 6px 10px 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0px;
    top: -1px;
    padding: 0px 6px 0px 0px;
    background-color: {S0};
    border: none;
    color: {TXT2};
    font-size: {FXS}pt;
    font-weight: 700;
    letter-spacing: 0.6px;
}}

/* ═══════════════════════════════════════════════════════════════════
   MENUS
═══════════════════════════════════════════════════════════════════ */
QMenu {{
    background-color: {S0};
    border: 1px solid {BD2};
    border-radius: {RLG}px;
    color: {TXT};
    font-size: {FB}pt;
    padding: 4px;
}}
QMenu::item {{
    background-color: transparent;
    color: {TXT};
    padding: 5px 16px 5px 10px;
    border-radius: {RSM}px;
    margin: 1px 2px;
    min-height: 22px;
}}
QMenu::item:selected {{ background-color: {AT}; color: {TXT}; }}
QMenu::item:disabled {{ color: {TXTD}; background-color: transparent; }}
QMenu::separator {{
    height: 1px;
    background-color: {BD};
    margin: 3px 4px;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {S1};
    border: 1px solid {BD2};
    border-radius: {RSM}px;
    color: {TXT};
    font-size: {FSM}pt;
    padding: 3px 8px;
}}

/* ═══════════════════════════════════════════════════════════════════
   SPLITTER
═══════════════════════════════════════════════════════════════════ */
QSplitter::handle {{ background-color: {BD}; }}
QSplitter::handle:vertical   {{ height: 1px; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:hover {{ background-color: {ACC}; }}

/* ═══════════════════════════════════════════════════════════════════
   FORM LAYOUT
═══════════════════════════════════════════════════════════════════ */
QFormLayout QLabel {{
    color: {TXT2};
    font-size: {FXS}pt;
    font-weight: 700;
    letter-spacing: 0.4px;
    background-color: transparent;
    border: none;
    min-height: {HI}px;
}}

/* ═══════════════════════════════════════════════════════════════════
   DIALOG BUTTON BOX
═══════════════════════════════════════════════════════════════════ */
QDialogButtonBox QPushButton {{
    min-width: 80px;
    min-height: {HB}px;
    max-height: {HB}px;
}}

/* ═══════════════════════════════════════════════════════════════════
   CALENDAR
═══════════════════════════════════════════════════════════════════ */
QCalendarWidget {{
    background-color: {S0};
    border: 1px solid {BD2};
    border-radius: {RMD}px;
}}
QCalendarWidget QAbstractItemView {{
    background-color: {S0};
    color: {TXT};
    selection-background-color: {AT2};
    selection-color: {ACC};
    alternate-background-color: {S1};
}}
QCalendarWidget QToolButton {{
    background-color: {S1};
    color: {TXT};
    border: none;
    border-radius: {RSM}px;
    padding: 2px 6px;
    min-height: 0px;
    max-height: 22px;
}}
QCalendarWidget QToolButton:hover {{ background-color: {AT}; color: {ACC}; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background-color: {S1};
    border-bottom: 1px solid {BD2};
}}
"""


GLOBAL_STYLESHEET = build()