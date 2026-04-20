"""
MetaMobility Unified GUI – main entry point
============================================
Presents a home screen where the user can choose between:
  • Spline Controller   (gait-phase-based torque profile)
  • Biotorque Controller (TCN/TRT model-based assist)

A persistent top-bar lets the user switch back to the home screen
or jump between modes at any time without restarting.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QFrame, QSizePolicy,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QPen

import theme
from spline_panel    import SplineControllerPanel
from biotorque_panel import BiotorqueControllerPanel


# ─────────────────────────────────────────────────────────────────────────────
#  Home Screen
# ─────────────────────────────────────────────────────────────────────────────

class HomeScreen(QWidget):
    """Landing page – two big mode-selector cards."""

    spline_clicked    = None   # set by MainWindow after construction
    biotorque_clicked = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Hero header ───────────────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet(
            f"QFrame {{ background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:1,"
            f"stop:0 #0d1117, stop:1 #161b22); }}"
        )
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(60, 48, 60, 40)
        hero_layout.setSpacing(6)

        mm_label = QLabel("MetaMobility")
        mm_label.setTextInteractionFlags(Qt.NoTextInteraction)
        mm_label.setStyleSheet(
            f"color:{theme.TEXT_PRIMARY}; font-size:32px; font-weight:700; letter-spacing:1px;"
        )
        sub_label = QLabel("Exoskeleton Control Interface  ·  Select a controller mode to begin")
        sub_label.setTextInteractionFlags(Qt.NoTextInteraction)
        sub_label.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; font-size:14px; font-weight:400;"
        )

        hero_layout.addWidget(mm_label)
        hero_layout.addWidget(sub_label)
        root.addWidget(hero)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{theme.BORDER}; max-height:1px;")
        root.addWidget(sep)

        # ── Cards row ─────────────────────────────────────────────────────────
        cards_area = QWidget()
        cards_area.setStyleSheet(f"background:{theme.BG_BASE};")
        cards_layout = QHBoxLayout(cards_area)
        cards_layout.setContentsMargins(80, 60, 80, 60)
        cards_layout.setSpacing(40)

        cards_layout.addWidget(
            self._make_card(
                "⟲",
                "Spline Controller",
                "Gait Phase–Based Torque Profile",
                [
                    "Interactive cubic-Hermite spline editor",
                    "6 configurable control points (extension & flexion)",
                    "Real-time gait phase tracking & phase indicator",
                    "Live motor position, velocity, and command plots",
                    "TBE and CNN controller modes",
                ],
                theme.ACCENT_BLUE,
                "_on_spline",
            )
        )
        cards_layout.addWidget(
            self._make_card(
                "⚡",
                "Biotorque Controller",
                "TCN Model–Based Assist",
                [
                    "TensorRT inference pipeline (GPU-accelerated)",
                    "Configurable scale factor and delay",
                    "Live IMU, motor, and torque visualisation",
                    "Trial configuration with save / load support",
                    "Performance timing monitor (loop + inference)",
                ],
                theme.ACCENT_GREEN,
                "_on_biotorque",
            )
        )

        root.addWidget(cards_area, stretch=1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background:{theme.BG_DEEP}; border-top:1px solid {theme.BORDER}; }}"
        )
        footer.setFixedHeight(36)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.addStretch()
        ver = QLabel("MetaMobility Unified GUI  ·  v2.0")
        ver.setTextInteractionFlags(Qt.NoTextInteraction)
        ver.setStyleSheet(f"color:{theme.TEXT_DISABLED}; font-size:11px;")
        fl.addWidget(ver)
        root.addWidget(footer)

    def _make_card(
        self,
        icon_text: str,
        title: str,
        subtitle: str,
        bullets: list[str],
        accent: str,
        slot_name: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("modeCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setStyleSheet(
            f"QFrame#modeCard {{"
            f"  background:{theme.BG_CARD};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 12px;"
            f"}}"
            f"QFrame#modeCard:hover {{"
            f"  border: 1px solid {accent}88;"
            f"}}"
        )

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(36, 36, 36, 32)
        vbox.setSpacing(16)

        # Icon circle
        icon_lbl = QLabel(icon_text)
        icon_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(70, 70)
        icon_lbl.setStyleSheet(
            f"color:{accent}; font-size:32px;"
            f" background:{accent}18; border-radius:35px;"
            f" border: 1px solid {accent}44;"
        )
        vbox.addWidget(icon_lbl, alignment=Qt.AlignLeft)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        title_lbl.setStyleSheet(
            f"color:{theme.TEXT_PRIMARY}; font-size:22px; font-weight:700;"
        )
        vbox.addWidget(title_lbl)

        # Subtitle
        sub_lbl = QLabel(subtitle)
        sub_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        sub_lbl.setStyleSheet(
            f"color:{accent}; font-size:13px; font-weight:500;"
        )
        vbox.addWidget(sub_lbl)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background:{theme.BORDER}; max-height:1px;")
        vbox.addWidget(div)

        # Features list
        for b in bullets:
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("•")
            dot.setTextInteractionFlags(Qt.NoTextInteraction)
            dot.setStyleSheet(f"color:{accent}; font-size:16px; font-weight:700;")
            dot.setFixedWidth(12)
            txt = QLabel(b)
            txt.setTextInteractionFlags(Qt.NoTextInteraction)
            txt.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-size:13px;")
            txt.setWordWrap(True)
            row.addWidget(dot, alignment=Qt.AlignTop)
            row.addWidget(txt)
            vbox.addLayout(row)

        vbox.addStretch()

        # Launch button
        btn = QPushButton(f"Open {title}  →")
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {accent}22;"
            f"  border: 1px solid {accent}55;"
            f"  border-radius: 8px;"
            f"  color: {accent};"
            f"  font-weight: 700;"
            f"  font-size: 14px;"
            f"  padding: 12px 24px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {accent}44;"
            f"  border-color: {accent}aa;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {accent}66;"
            f"}}"
        )
        btn.setFixedHeight(48)
        btn.clicked.connect(lambda: getattr(self, slot_name)())
        vbox.addWidget(btn)

        return card

    def _on_spline(self):
        if callable(self.spline_clicked):
            self.spline_clicked()

    def _on_biotorque(self):
        if callable(self.biotorque_clicked):
            self.biotorque_clicked()


# ─────────────────────────────────────────────────────────────────────────────
#  Navigation Bar
# ─────────────────────────────────────────────────────────────────────────────

class NavBar(QFrame):
    """Persistent top bar with home / mode pills and status."""

    home_clicked      = None
    spline_clicked    = None
    biotorque_clicked = None

    PAGE_HOME      = 0
    PAGE_SPLINE    = 1
    PAGE_BIOTORQUE = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navBar")
        self.setFixedHeight(54)
        self.setStyleSheet(
            f"QFrame#navBar {{ background:{theme.BG_DEEP};"
            f" border-bottom: 1px solid {theme.BORDER}; }}"
        )
        self._active_page = self.PAGE_HOME
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)

        # Logo / brand
        brand = QLabel("MetaMobility")
        brand.setStyleSheet(
            f"color:{theme.TEXT_PRIMARY}; font-size:15px; font-weight:700; letter-spacing:0.5px;"
        )
        layout.addWidget(brand)

        # Divider
        d = QFrame()
        d.setFrameShape(QFrame.VLine)
        d.setStyleSheet(f"background:{theme.BORDER};")
        d.setFixedWidth(1)
        layout.addWidget(d)
        layout.addSpacing(8)

        # Nav pills
        self._btn_home      = self._nav_pill("  Home",            self.PAGE_HOME)
        self._btn_spline    = self._nav_pill("⟲  Spline Ctrl",   self.PAGE_SPLINE)
        self._btn_biotorque = self._nav_pill("⚡  Biotorque Ctrl", self.PAGE_BIOTORQUE)

        for btn in (self._btn_home, self._btn_spline, self._btn_biotorque):
            layout.addWidget(btn)

        layout.addStretch()

        # Status indicator
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{theme.TEXT_DISABLED}; font-size:10px;")
        self._status_msg = QLabel("Ready")
        self._status_msg.setStyleSheet(f"color:{theme.TEXT_SECONDARY}; font-size:12px;")
        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_msg)
        layout.addSpacing(4)

    def _nav_pill(self, text: str, page: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(34)
        btn.clicked.connect(lambda: self._on_nav(page))
        self._update_pill_style(btn, False)
        return btn

    def _update_pill_style(self, btn: QPushButton, active: bool):
        if active:
            btn.setStyleSheet(
                f"QPushButton {{ background:{theme.ACCENT_BLUE}18;"
                f" border:1px solid {theme.ACCENT_BLUE}66;"
                f" border-radius:6px; color:{theme.ACCENT_BLUE};"
                f" font-weight:600; font-size:13px; padding:0 14px; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background:transparent; border:none;"
                f" border-radius:6px; color:{theme.TEXT_SECONDARY};"
                f" font-size:13px; padding:0 14px; }}"
                f"QPushButton:hover {{ background:{theme.BG_CARD};"
                f" color:{theme.TEXT_PRIMARY}; }}"
            )

    def _on_nav(self, page: int):
        cb_map = {
            self.PAGE_HOME:      self.home_clicked,
            self.PAGE_SPLINE:    self.spline_clicked,
            self.PAGE_BIOTORQUE: self.biotorque_clicked,
        }
        if callable(cb_map.get(page)):
            cb_map[page]()

    def set_active_page(self, page: int):
        self._active_page = page
        for btn, p in (
            (self._btn_home, self.PAGE_HOME),
            (self._btn_spline, self.PAGE_SPLINE),
            (self._btn_biotorque, self.PAGE_BIOTORQUE),
        ):
            self._update_pill_style(btn, p == page)

    def set_status(self, msg: str, color: str = theme.TEXT_SECONDARY):
        self._status_msg.setText(msg)
        self._status_msg.setStyleSheet(f"color:{color}; font-size:12px;")
        dot_color = color
        self._status_dot.setStyleSheet(f"color:{dot_color}; font-size:10px;")


# ─────────────────────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────────────────────

class MetaMobilityApp(QMainWindow):

    PAGE_HOME      = 0
    PAGE_SPLINE    = 1
    PAGE_BIOTORQUE = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaMobility – Exoskeleton Control Interface")
        self.setMinimumSize(1280, 800)
        self.resize(1600, 960)

        # Apply app-wide stylesheet
        self.setStyleSheet(theme.APP_STYLESHEET)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        # Central container
        container = QWidget()
        container.setStyleSheet(f"background:{theme.BG_DEEP};")
        self.setCentralWidget(container)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Navigation bar ────────────────────────────────────────────────────
        self._nav = NavBar()
        self._nav.home_clicked      = lambda: self._switch_to(self.PAGE_HOME)
        self._nav.spline_clicked    = lambda: self._switch_to(self.PAGE_SPLINE)
        self._nav.biotorque_clicked = lambda: self._switch_to(self.PAGE_BIOTORQUE)
        vbox.addWidget(self._nav)

        # ── Stacked pages ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{theme.BG_BASE};")
        vbox.addWidget(self._stack, stretch=1)

        # Page 0 – Home
        self._home = HomeScreen()
        self._home.spline_clicked    = lambda: self._switch_to(self.PAGE_SPLINE)
        self._home.biotorque_clicked = lambda: self._switch_to(self.PAGE_BIOTORQUE)
        self._stack.addWidget(self._home)

        # Pages 1 & 2 – lazy-loaded on first access
        self._spline_panel    = None
        self._biotorque_panel = None

        # Placeholder widgets in the stack so indices are stable
        self._stack.addWidget(QWidget())  # idx 1 – replaced later
        self._stack.addWidget(QWidget())  # idx 2 – replaced later

        # ── Status bar ────────────────────────────────────────────────────────
        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background:{theme.BG_DEEP};"
            f" border-top:1px solid {theme.BORDER};"
            f" color:{theme.TEXT_SECONDARY}; font-size:12px; }}"
        )
        self.statusBar().showMessage("Ready  ·  Select a controller mode from the home screen")

        # Start on home
        self._switch_to(self.PAGE_HOME)

    # ── Page Switching ────────────────────────────────────────────────────────

    def _switch_to(self, page: int):
        if page == self.PAGE_SPLINE:
            self._ensure_spline()
        elif page == self.PAGE_BIOTORQUE:
            self._ensure_biotorque()

        self._stack.setCurrentIndex(page)
        self._nav.set_active_page(page)

        labels = {
            self.PAGE_HOME:      "Home  ·  Choose a controller mode",
            self.PAGE_SPLINE:    "Spline Controller  ·  Gait phase–based torque profile",
            self.PAGE_BIOTORQUE: "Biotorque Controller  ·  TCN model-based assist",
        }
        self.statusBar().showMessage(labels.get(page, ""))

    def _ensure_spline(self):
        if self._spline_panel is not None:
            return
        self._spline_panel = SplineControllerPanel()
        self._spline_panel.status_changed.connect(
            lambda msg, col: self._nav.set_status(f"[Spline] {msg}", col)
        )
        # Replace placeholder at index 1
        old = self._stack.widget(self.PAGE_SPLINE)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(self.PAGE_SPLINE, self._spline_panel)

    def _ensure_biotorque(self):
        if self._biotorque_panel is not None:
            return
        self._biotorque_panel = BiotorqueControllerPanel()
        self._biotorque_panel.status_changed.connect(
            lambda msg, col: self._nav.set_status(f"[Biotorque] {msg}", col)
        )
        old = self._stack.widget(self.PAGE_BIOTORQUE)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(self.PAGE_BIOTORQUE, self._biotorque_panel)

    # ── Close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Graceful shutdown of any running panels
        if self._spline_panel:
            self._spline_panel.shutdown()
        if self._biotorque_panel:
            self._biotorque_panel.shutdown()
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # High-DPI support
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass

    win = MetaMobilityApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()