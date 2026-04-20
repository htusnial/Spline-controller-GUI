"""
MetaMobility Design System
Centralized theme constants, stylesheets, and color palette.
"""

# ─── Color Palette ────────────────────────────────────────────────────────────
BG_DEEP       = "#0d1117"   # deepest background (window)
BG_BASE       = "#161b22"   # base background (panels)
BG_CARD       = "#161b22"   # card / group box background "#21262d"
BG_INPUT      = "#30363d"   # inputs, line edits
BORDER        = "#30363d"   # standard border
BORDER_FOCUS  = "#58a6ff"   # focus border

TEXT_PRIMARY   = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_DISABLED  = "#484f58"

ACCENT_BLUE    = "#58a6ff"
ACCENT_GREEN   = "#3fb950"
ACCENT_ORANGE  = "#d29922"
ACCENT_RED     = "#f85149"
ACCENT_PURPLE  = "#bc8cff"
ACCENT_CYAN    = "#39c5cf"

PLOT_BG        = "#0d1117"
PLOT_FG        = "#e6edf3"
PLOT_GRID      = "#21262d"

PLOT_LEFT_PEN  = "#58a6ff"   # blue  – Left leg
PLOT_RIGHT_PEN = "#f85149"   # red   – Right leg
PLOT_GREEN_PEN = "#3fb950"
PLOT_YELLOW_PEN = "#d29922"
PLOT_PURPLE_PEN = "#bc8cff"
PLOT_CYAN_PEN   = "#39c5cf"

# ─── App-wide stylesheet ──────────────────────────────────────────────────────
APP_STYLESHEET = f"""
/* ── Window & Base ── */
QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ── Group Boxes ── */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {ACCENT_BLUE};
    font-size: 12px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 8px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_BLUE};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
    outline: none;
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {TEXT_DISABLED};
    background-color: {BG_CARD};
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 6px 8px;
    color: {TEXT_PRIMARY};
    min-width: 100px;
}}
QComboBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_BLUE};
    color: {TEXT_PRIMARY};
    padding: 4px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 7px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: #3c444e;
    border-color: #8b949e;
}}
QPushButton:pressed {{
    background-color: {BG_CARD};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background-color: {BG_CARD};
    border-color: {BORDER};
}}

/* ── Labels ── */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
    selection-background-color: transparent;
    selection-color: {TEXT_PRIMARY};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background-color: {BG_CARD};
    padding: 4px;
}}
QTabBar::tab {{
    background-color: {BG_BASE};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 18px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 90px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border-bottom: 2px solid {ACCENT_BLUE};
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

/* ── Scroll Bars ── */
QScrollBar:vertical {{
    background-color: {BG_BASE};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #484f58;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Toolbar ── */
QToolBar {{
    background-color: {BG_DEEP};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 4px 8px;
}}
QToolBar QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: {TEXT_PRIMARY};
    padding: 5px 10px;
    font-weight: 500;
}}
QToolBar QToolButton:hover {{
    background-color: {BG_CARD};
    border-color: {BORDER};
}}

/* ── Status Bar ── */
QStatusBar {{
    background-color: {BG_DEEP};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    font-size: 12px;
    padding: 2px 8px;
}}

/* ── CheckBox ── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
"""

# ─── Button style helpers ─────────────────────────────────────────────────────
def btn_style(color: str, hover: str, pressed: str) -> str:
    return f"""
        QPushButton {{
            background-color: {color};
            border: none;
            border-radius: 6px;
            color: white;
            font-weight: 600;
            padding: 8px 20px;
            font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
        QPushButton:disabled {{ background-color: #30363d; color: #484f58; }}
    """

BTN_GREEN  = btn_style("#238636", "#2ea043", "#1a7f37")
BTN_RED    = btn_style("#da3633", "#f85149", "#b91c1c")
BTN_BLUE   = btn_style("#1f6feb", "#388bfd", "#1158c7")
BTN_ORANGE = btn_style("#9a6700", "#d29922", "#7d5700")
BTN_GHOST  = f"""
    QPushButton {{
        background-color: transparent;
        border: 1px solid {BORDER};
        border-radius: 6px;
        color: {TEXT_PRIMARY};
        padding: 7px 16px;
        font-weight: 500;
    }}
    QPushButton:hover {{ background-color: {BG_CARD}; border-color: #8b949e; }}
    QPushButton:pressed {{ background-color: {BG_INPUT}; }}
"""