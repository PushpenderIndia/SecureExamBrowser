"""
core/proctor/intro.py
─────────────────────────────────────────────────────────────────────────────
Native PySide6 intro/permissions screen that strictly matches intro.html,
including every Font Awesome glyph.

Required font files – place both in  assets/fonts/ :
  fa-solid-900.otf    (or .ttf)
  fa-regular-400.otf  (or .ttf)

Download: https://fontawesome.com/download  →  "Font Awesome 6 Free"
The webfonts/ folder inside that archive contains the files listed above.

Public surface
──────────────
  IntroWidget           – full intro screen  (QWidget)
  WebcamGuidelinesModal – in-widget dark overlay (owned by IntroWidget)
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..resources import resource_path
from .checks import CheckResult, CheckStatus, ScreenMonitor

# ── Palette ───────────────────────────────────────────────────────────────────

_TEXT   = "#ffffff"
_MUTED  = "#a1aab5"
_LINK   = "#4b7bec"
_GREEN  = "#00e676"
_BORDER = "rgba(255, 255, 255, 26)"   # ≈ 10 % white

# ── Font Awesome 6 glyph codepoints ──────────────────────────────────────────

class _FA:
    """Unicode codepoints for every glyph used in this screen."""
    # solid
    BORDER_ALL          = 0xF84C
    VIDEO               = 0xF03D
    DESKTOP             = 0xF108
    ARROW_UP_FROM_BRAC  = 0xE09A
    SERVER              = 0xF233   # virtual-machine / hardware check
    CHECK_CIRCLE        = 0xF058   # success checkmark (solid)
    CHEVRON_DOWN        = 0xF078
    CHEVRON_UP          = 0xF077
    IMAGE_PORTRAIT      = 0xF3E0
    HOUSE               = 0xF015   # fa-house (free) – private place
    LIGHTBULB           = 0xF0EB
    EXPAND              = 0xF065
    # regular  (same codepoint, different font file)
    SUN                 = 0xF185
    CIRCLE_CHECK        = 0xF058   # caption check (regular)


# ── Font loading (deferred until first IntroWidget is constructed) ─────────────

_FA_SOLID   = ""
_FA_REGULAR = ""
_FA_LOADED  = False


def _load_fa_fonts() -> None:
    """Register Font Awesome TTF files with Qt.  Safe to call multiple times."""
    global _FA_SOLID, _FA_REGULAR, _FA_LOADED
    if _FA_LOADED:
        return
    _FA_LOADED = True
    for attr, filenames in (
        ("_FA_SOLID",   ["fa-solid-900.ttf",   "fa-solid-900.otf"]),
        ("_FA_REGULAR", ["fa-regular-400.ttf", "fa-regular-400.otf"]),
    ):
        for filename in filenames:
            path = str(resource_path("assets", "fonts", filename))
            fid = QFontDatabase.addApplicationFont(path)
            if fid >= 0:
                families = QFontDatabase.applicationFontFamilies(fid)
                print(f"[FA] loaded {filename!r} → families={families}")
                if families:
                    globals()[attr] = families[0]
                    break
            else:
                print(f"[FA] failed to load {path!r}")
    print(f"[FA] _FA_SOLID={_FA_SOLID!r}  _FA_REGULAR={_FA_REGULAR!r}")


def _icon(
    codepoint: int,
    pt_size: int = 14,
    *,
    solid: bool = True,
    color: str = _MUTED,
    fixed_width: int | None = None,
) -> QLabel:
    """Return a QLabel that renders a single Font Awesome glyph."""
    lbl = QLabel(chr(codepoint))
    family = _FA_SOLID if solid else _FA_REGULAR
    if family:
        font = QFont(family, pt_size)
        font.setWeight(QFont.Weight.Black if solid else QFont.Weight.Normal)
        lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color};")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if fixed_width is not None:
        lbl.setFixedWidth(fixed_width)
    return lbl


# ── Webcam guidelines modal ───────────────────────────────────────────────────

class _GuidelineCard(QWidget):
    """Single cell in the 2×2 guidelines grid."""

    def __init__(self, icon_cp: int, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._illustration(icon_cp))
        layout.addSpacing(24)
        layout.addWidget(self._caption_row(caption))

    def _illustration(self, icon_cp: int) -> QWidget:
        container = QWidget()
        container.setFixedHeight(100)
        hl = QHBoxLayout(container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(_icon(icon_cp, 40, color=_TEXT))
        return container

    def _caption_row(self, caption: str) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(_icon(_FA.CIRCLE_CHECK, 16, solid=False, color=_MUTED))
        lbl = QLabel(caption)
        lbl.setStyleSheet(f"color: {_TEXT}; font-size: 14px;")
        hl.addWidget(lbl)
        return row


class WebcamGuidelinesModal(QWidget):
    """Full-overlay webcam best-practice panel."""

    accepted = Signal()

    _GUIDELINES: list[tuple[int, str]] = [
        (_FA.IMAGE_PORTRAIT, "Avoid virtual background"),
        (_FA.HOUSE,          "Find a private place"),
        (_FA.LIGHTBULB,      "Use proper light source"),
        (_FA.EXPAND,         "Your face visible in the webcam"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 17, 23, 179))
        painter.end()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._card())

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("wgCard")
        card.setMaximumWidth(640)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        card.setStyleSheet("""
            QFrame#wgCard {
                background: #20242b;
                border: 1px solid rgba(255,255,255,26);
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        layout.addWidget(self._body())
        layout.addWidget(self._footer())
        return card

    def _header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-bottom: 1px solid rgba(255,255,255,26);")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(24, 20, 24, 20)
        lbl = QLabel("For best results make sure")
        lbl.setStyleSheet(f"color: {_TEXT}; font-size: 16px; font-weight: 600; border: none;")
        hl.addWidget(lbl)
        hl.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_MUTED};
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,20);
                color: {_TEXT};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        hl.addWidget(close_btn)
        return w

    def _body(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(24, 32, 24, 48)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(40)
        for idx, (icon_cp, caption) in enumerate(self._GUIDELINES):
            grid.addWidget(_GuidelineCard(icon_cp, caption), idx // 2, idx % 2)
        return w

    def _footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-top: 1px solid rgba(255,255,255,26);")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(24, 16, 24, 16)
        hl.addStretch()
        btn = QPushButton("Continue")
        btn.setFixedHeight(40)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet("""
            QPushButton {
                background: #bbf0cd;
                color: #0d1117;
                border: none;
                border-radius: 6px;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #9cdbaf; }
        """)
        btn.clicked.connect(self._on_continue)
        hl.addWidget(btn)
        return w

    def _on_continue(self) -> None:
        self.hide()
        self.accepted.emit()


# ── Clickable header helper ───────────────────────────────────────────────────

class _ClickableHeader(QWidget):
    """Transparent row widget that emits ``clicked`` on any mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit()


# ── Accordion row ─────────────────────────────────────────────────────────────

class _AccordionRow(QFrame):
    """
    Single permission item with a click-to-toggle accordion body.

    Parameters
    ----------
    icon_cp     : Font Awesome solid codepoint for the left icon.
    label       : Row title text.
    body_text   : Description shown when the row is expanded.
    checked     : Show a green fa-check-circle after the title.
    expanded    : Start in the open (expanded) state.
    live_check  : Show a live status badge next to the title.
    grant_access: Add a "Grant Access" button inside the body.
    """

    opened = Signal()   # fired whenever this row transitions to expanded

    def __init__(
        self,
        icon_cp: int,
        label: str,
        *,
        body_text: str = "",
        checked: bool = False,
        expanded: bool = False,
        live_check: bool = False,
        grant_access: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._chevron: QLabel | None = None
        self._body_panel: QWidget | None = None
        self.grant_btn: QPushButton | None = None
        self._status_lbl: QLabel | None = None
        self._anim: QPropertyAnimation | None = None

        self.setObjectName("accordionRow")
        self.setStyleSheet("""
            QFrame#accordionRow {
                background: rgba(255,255,255,8);
                border: 1px solid rgba(255,255,255,26);
                border-radius: 8px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = self._build_header(icon_cp, label, checked, live_check)
        hdr.clicked.connect(self._toggle)
        root.addWidget(hdr)

        if body_text:
            self._body_panel = self._build_body(body_text, grant_access)
            # Keep the panel in the layout always; height is the only thing
            # that changes.  Rows that start collapsed get max-height=0.
            self._body_panel.setMaximumHeight(0 if not expanded else 16777215)
            root.addWidget(self._body_panel)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_status(self, result: CheckResult) -> None:
        """Update the live-check status badge."""
        if self._status_lbl is None:
            return
        if result.status is CheckStatus.PASSED:
            self._status_lbl.setText("✓ Passed")
            self._status_lbl.setStyleSheet(
                f"color: {_GREEN}; font-size: 12px; font-weight: 600;"
            )
        elif result.status is CheckStatus.FAILED:
            self._status_lbl.setText("✗ Failed")
            self._status_lbl.setStyleSheet(
                "color: #ff5252; font-size: 12px; font-weight: 600;"
            )
        else:
            self._status_lbl.setText("Checking…")
            self._status_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        if result.message:
            self._status_lbl.setToolTip(result.message)

    # ── Toggle / collapse ─────────────────────────────────────────────────────

    def collapse(self) -> None:
        """Close this row unconditionally (used by the exclusive-open logic)."""
        if not self._expanded:
            return
        self._expanded = False
        if self._chevron is not None:
            self._chevron.setText(chr(_FA.CHEVRON_DOWN))
        self._animate_body(expanding=False)

    def _toggle(self) -> None:
        if self._body_panel is None:
            return
        self._expanded = not self._expanded
        if self._chevron is not None:
            self._chevron.setText(
                chr(_FA.CHEVRON_UP if self._expanded else _FA.CHEVRON_DOWN)
            )
        self._animate_body(expanding=self._expanded)
        if self._expanded:
            self.opened.emit()

    def _animate_body(self, expanding: bool) -> None:
        panel = self._body_panel
        if panel is None:
            return

        # Stop any in-flight animation at its current position
        if self._anim is not None:
            self._anim.stop()

        if expanding:
            # Measure natural height with max-height unconstrained, then
            # reset to 0 so the animation starts from the top.
            panel.setMaximumHeight(16777215)
            natural_h = panel.sizeHint().height()
            panel.setMaximumHeight(0)
            start_h, end_h = 0, natural_h
        else:
            # Collapse from wherever the panel currently sits (handles mid-
            # animation reversal gracefully).
            start_h = panel.height() or panel.sizeHint().height()
            end_h = 0

        self._anim = QPropertyAnimation(panel, b"maximumHeight", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.setStartValue(start_h)
        self._anim.setEndValue(end_h)

        if expanding:
            # Remove the cap once fully open so the body can reflow freely.
            self._anim.finished.connect(lambda: panel.setMaximumHeight(16777215))

        self._anim.start()

    # ── Row sections ──────────────────────────────────────────────────────────

    def _build_header(
        self, icon_cp: int, label: str, checked: bool, live_check: bool
    ) -> _ClickableHeader:
        hdr = _ClickableHeader()
        hdr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.setSpacing(0)

        hl.addWidget(_icon(icon_cp, 14, color=_MUTED, fixed_width=20))
        hl.addSpacing(12)

        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 15px; font-weight: 500;"
        )
        hl.addWidget(title_lbl)

        if checked:
            success = _icon(_FA.CHECK_CIRCLE, 14, color=_GREEN)
            success.setContentsMargins(8, 0, 0, 0)
            hl.addWidget(success)

        if live_check:
            self._status_lbl = QLabel("Checking…")
            self._status_lbl.setContentsMargins(12, 0, 0, 0)
            self._status_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
            hl.addWidget(self._status_lbl)

        hl.addStretch()

        self._chevron = _icon(
            _FA.CHEVRON_UP if self._expanded else _FA.CHEVRON_DOWN,
            14, color=_MUTED,
        )
        hl.addWidget(self._chevron)
        return hdr

    def _build_body(self, body_text: str, grant_access: bool) -> QWidget:
        wrapper = QWidget()
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # Thin separator line between header and body
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,13); border: none;")
        vl.addWidget(sep)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(52, 14, 20, 18)
        cl.setSpacing(14)

        desc = QLabel(body_text)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_MUTED}; font-size: 13px; line-height: 1.5;")
        cl.addWidget(desc)

        if grant_access:
            self.grant_btn = QPushButton("Grant Access")
            self.grant_btn.setFixedHeight(38)
            self.grant_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.grant_btn.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            self.grant_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_GREEN};
                    color: #000000;
                    border: none;
                    border-radius: 6px;
                    padding: 0 20px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: #00c853; }}
            """)
            cl.addWidget(self.grant_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        vl.addWidget(content)
        return wrapper


# ── Pagination dots ───────────────────────────────────────────────────────────

class _PaginationDots(QWidget):
    """Matches the  .pagination  div."""

    def __init__(self, total: int, active: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        for i in range(total):
            dot = QFrame()
            dot.setFixedSize(24, 6)
            colour = "#ffffff" if i == active else "rgba(255,255,255,51)"
            dot.setStyleSheet(
                f"background: {colour}; border-radius: 3px; border: none;"
            )
            hl.addWidget(dot)


# ── Left pane ─────────────────────────────────────────────────────────────────

class _LeftPane(QWidget):
    """Matches .left-pane  (logo + heading  |  test card + platform links)."""

    def __init__(self, parent: QWidget | None = None, *, config=None) -> None:
        super().__init__(parent)
        self._config = config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 20, 0)
        layout.setSpacing(0)

        layout.addWidget(self._logo())
        layout.addSpacing(16)
        layout.addWidget(self._heading())
        layout.addStretch()
        layout.addWidget(self._test_card())
        layout.addSpacing(24)
        layout.addWidget(self._platform_links())

    def _logo(self) -> QLabel:
        lbl = QLabel()
        lbl.setFixedHeight(75)
        lbl.setMaximumWidth(240)
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        pix = QPixmap(str(resource_path("assets", "proctor", "images", "logo.png")))
        if not pix.isNull():
            lbl.setPixmap(
                pix.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            lbl.setText("CodeChef")
            lbl.setStyleSheet(f"color: {_TEXT}; font-size: 22px; font-weight: 700;")
        return lbl

    def _heading(self) -> QLabel:
        lbl = QLabel(
            "Here are few important things to know before taking the test"
        )
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(420)
        lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 40px; font-weight: 700; letter-spacing: -1px;"
        )
        return lbl

    def _test_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("testCard")
        card.setMaximumWidth(400)
        card.setStyleSheet("""
            QFrame#testCard {
                background: rgba(255,255,255,13);
                border: 1px solid rgba(255,255,255,26);
                border-radius: 12px;
            }
        """)
        hl = QHBoxLayout(card)
        hl.setContentsMargins(16, 16, 16, 16)
        hl.setSpacing(16)

        logo_lbl = QLabel()
        logo_lbl.setFixedSize(36, 36)
        pix = QPixmap(str(resource_path("assets", "proctor", "images", "logo1.png")))
        if not pix.isNull():
            logo_lbl.setPixmap(
                pix.scaled(
                    36, 36,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        hl.addWidget(logo_lbl)

        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel("CodeChef Desktop App Test")
        title.setStyleSheet(f"color: {_TEXT}; font-size: 14px; font-weight: 600;")
        dm = self._config.duration_minutes if self._config and self._config.duration_minutes else None
        dur_text = f"Test duration: {dm} minutes" if dm else "Test duration: N/A"
        dur = QLabel(dur_text)
        dur.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        info.addWidget(title)
        info.addWidget(dur)
        hl.addLayout(info)
        hl.addStretch()
        return card

    def _platform_links(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)

        powered = QLabel('Powered by <b style="color:#ffffff;">CodeChef</b>')
        powered.setTextFormat(Qt.TextFormat.RichText)
        powered.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        vl.addWidget(powered)

        links_row = QHBoxLayout()
        links_row.setSpacing(16)
        for text in ("Platform Help", "Execution Environment", "FAQ"):
            lbl = QLabel(
                f'<a href="#" style="color:{_LINK}; text-decoration:none;">{text}</a>'
            )
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setStyleSheet("font-size: 12px;")
            links_row.addWidget(lbl)
        links_row.addStretch()
        vl.addLayout(links_row)
        return w


# ── Right pane ────────────────────────────────────────────────────────────────

class _RightPane(QWidget):
    """
    Matches .right-pane  (top bar  |  permissions card  |  bottom controls).

    Signals
    -------
    grant_access_clicked:  User clicked "Grant Access".
    quit_clicked:          User clicked "Quit App".
    """

    grant_access_clicked = Signal()
    quit_clicked = Signal()

    _ACCORDION_ROWS: list[dict] = [
        dict(
            icon_cp=_FA.BORDER_ALL,
            label="Close Additional Applications",
            body_text=(
                "Before starting, close all other open applications — including "
                "other browsers, screen-sharing tools, and communication apps. "
                "This prevents interruptions and ensures exam integrity."
            ),
            checked=True,
        ),
        dict(
            icon_cp=_FA.VIDEO,
            label="Allow Webcam Access",
            body_text=(
                "This helps verify it's you taking the test, just like an "
                "in-person exam. Webcam access is only active during the exam "
                "duration and your privacy is fully respected."
            ),
            expanded=True,
            grant_access=True,
        ),
        dict(
            icon_cp=_FA.DESKTOP,
            label="Check for Multiple Monitors",
            body_text=(
                "Only a single display is permitted during this exam. Please "
                "disconnect any additional monitors before proceeding. "
                "The status badge above updates automatically."
            ),
            live_check=True,
        ),
        dict(
            icon_cp=_FA.ARROW_UP_FROM_BRAC,
            label="Allow Screen Sharing",
            body_text=(
                "Screen sharing lets the proctoring system verify your activity "
                "during the exam. No recordings are stored after your session ends."
            ),
        ),
        dict(
            icon_cp=_FA.SERVER,
            label="Virtual Machine Check",
            body_text=(
                "Running the exam inside a virtual machine or emulated environment "
                "is not permitted. Your device has been scanned and verified as "
                "native hardware."
            ),
            live_check=True,
        ),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._screen_row: _AccordionRow | None = None
        self._vm_row: _AccordionRow | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._top_bar())
        layout.addSpacing(24)
        layout.addWidget(self._permissions_card(), 1)
        layout.addSpacing(24)
        layout.addWidget(self._bottom_controls())

    # ── Live-check result setters ──────────────────────────────────────────────

    def set_screen_check_result(self, result: CheckResult) -> None:
        if self._screen_row is not None:
            self._screen_row.set_status(result)

    def set_vm_check_result(self, result: CheckResult) -> None:
        if self._vm_row is not None:
            self._vm_row.set_status(result)

    # ── Builders ──────────────────────────────────────────────────────────────

    def _top_bar(self) -> QWidget:
        bar = QWidget()
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(16)
        hl.addStretch()
        hl.addWidget(_icon(_FA.SUN, 16, solid=False, color=_MUTED))

        lang = QFrame()
        lang.setObjectName("langSelector")
        lang.setStyleSheet(f"""
            QFrame#langSelector {{
                background: rgba(255,255,255,13);
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
        """)
        lang_l = QHBoxLayout(lang)
        lang_l.setContentsMargins(16, 8, 16, 8)
        lang_l.setSpacing(8)
        eng = QLabel("English")
        eng.setStyleSheet(f"color: {_TEXT}; font-size: 14px;")
        lang_l.addWidget(eng)
        lang_l.addWidget(_icon(_FA.CHEVRON_DOWN, 12, color=_TEXT))
        hl.addWidget(lang)
        return bar

    def _permissions_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("permCard")
        card.setStyleSheet("""
            QFrame#permCard {
                background: rgba(30,36,45,153);
                border: 1px solid rgba(255,255,255,20);
                border-radius: 16px;
            }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 40, 40, 40)
        cl.setSpacing(0)

        title = QLabel("Permissions")
        title.setStyleSheet(f"color: {_TEXT}; font-size: 24px; font-weight: 600;")
        cl.addWidget(title)
        cl.addSpacing(12)

        subtitle = QLabel(
            "Please review these Integrity Guidelines to ensure compliance and "
            "avoid unintended violations. Any suspicious activity may be flagged "
            "and reported to the hiring team."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {_MUTED}; font-size: 14px;")
        cl.addWidget(subtitle)
        cl.addSpacing(32)
        cl.addWidget(self._accordion())
        cl.addStretch()
        return card

    def _accordion(self) -> QWidget:
        container = QWidget()
        vl = QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(12)

        rows: list[_AccordionRow] = []
        for kwargs in self._ACCORDION_ROWS:
            row = _AccordionRow(**kwargs, parent=container)

            if row.grant_btn is not None:
                row.grant_btn.clicked.connect(self.grant_access_clicked)

            if kwargs.get("label") == "Check for Multiple Monitors":
                self._screen_row = row
            elif kwargs.get("label") == "Virtual Machine Check":
                self._vm_row = row

            vl.addWidget(row)
            rows.append(row)

        # Exclusive open: when any row opens, collapse all the others.
        for row in rows:
            others = [r for r in rows if r is not row]
            row.opened.connect(lambda _=None, peers=others: [r.collapse() for r in peers])

        return container

    def _bottom_controls(self) -> QWidget:
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.addWidget(_PaginationDots(3, active=0))
        hl.addStretch()

        quit_btn = QPushButton("Quit App")
        quit_btn.setFixedHeight(44)
        quit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        quit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {_TEXT};
                border: 1px solid rgba(255,255,255,51);
                border-radius: 6px;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,13); }}
        """)
        quit_btn.clicked.connect(self.quit_clicked)

        start_btn = QPushButton("Start Test")
        start_btn.setEnabled(False)
        start_btn.setFixedHeight(44)
        start_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,25);
                color: rgba(255,255,255,77);
                border: none;
                border-radius: 6px;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
            }
        """)

        hl.addWidget(quit_btn)
        hl.addSpacing(16)
        hl.addWidget(start_btn)
        return w


# ── Public API ────────────────────────────────────────────────────────────────

class IntroWidget(QWidget):
    """
    Native PySide6 intro/permissions screen.

    Signals
    -------
    quit_requested:     "Quit App" clicked — close without a password prompt.
    continue_requested: Webcam guidelines accepted — switch to the WebView.
    """

    quit_requested     = Signal()
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None, *, config=None) -> None:
        _load_fa_fonts()
        super().__init__(parent)
        self._config = config
        self._build()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._modal.resize(self.size())

    def _build(self) -> None:
        self.setStyleSheet("""
            IntroWidget {
                background: qradialgradient(
                    cx:0, cy:0, radius:1.4,
                    fx:0, fy:0,
                    stop:0 #1a232c,
                    stop:1 #0d1117
                );
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(40)

        self._right_pane = _RightPane(self)
        self._right_pane.quit_clicked.connect(self.quit_requested)
        self._right_pane.grant_access_clicked.connect(self._on_grant_access)

        layout.addWidget(_LeftPane(self, config=self._config), 10)
        layout.addWidget(self._right_pane, 12)

        # Persistent overlay modal
        self._modal = WebcamGuidelinesModal(self)
        self._modal.accepted.connect(self.continue_requested)

        # Screen monitor — run initial check then watch for changes
        self._screen_monitor = ScreenMonitor(self)
        self._right_pane.set_screen_check_result(self._screen_monitor.check())
        self._screen_monitor.result_changed.connect(self._on_screen_check_changed)

        # VM check — already cleared by app.py before the window opened;
        # show the result after a short delay so it feels like a real scan.
        QTimer.singleShot(900, self._complete_vm_check)

    @Slot(object)
    def _on_screen_check_changed(self, result: CheckResult) -> None:
        self._right_pane.set_screen_check_result(result)

    def _complete_vm_check(self) -> None:
        """Mark the VM row as passed (the real scan already ran in app.py)."""
        self._right_pane.set_vm_check_result(
            CheckResult(CheckStatus.PASSED, "No virtual machine detected")
        )

    def _on_grant_access(self) -> None:
        self._modal.resize(self.size())
        self._modal.raise_()
        self._modal.show()
