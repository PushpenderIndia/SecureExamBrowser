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

from PySide6.QtCore import Qt, Signal, Slot
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
        # Both FA files share the family name "Font Awesome 6 Free"; weight
        # is the only way Qt can select the correct variant.
        font.setWeight(QFont.Weight.Black if solid else QFont.Weight.Normal)
        lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color};")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if fixed_width is not None:
        lbl.setFixedWidth(fixed_width)
    return lbl


# ── Webcam guidelines modal ───────────────────────────────────────────────────

class _GuidelineCard(QWidget):
    """
    Single cell in the 2×2 guidelines grid  (matches .guideline-item in CSS).

    Layout:  illustration div (100 px tall icon)
             caption row  (fa-regular circle-check  +  text)
    """

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
        """100 px tall container with the centred large icon."""
        container = QWidget()
        container.setFixedHeight(100)
        hl = QHBoxLayout(container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(_icon(icon_cp, 40, color=_TEXT))
        return container

    def _caption_row(self, caption: str) -> QWidget:
        """fa-regular fa-circle-check  +  caption text, centred."""
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
    """
    Full-overlay webcam best-practice panel (matches the #webcam-modal div).

    Lives as a persistent child of IntroWidget, resized to fill it entirely.
    Uses paintEvent for the semi-transparent dark backdrop so it works
    reliably as a non-top-level widget.

    Signals
    -------
    accepted:  User clicked "Continue".
    """

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

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(13, 17, 23, 179))   # rgba(13,17,23,0.7)
        painter.end()

    # ── UI ────────────────────────────────────────────────────────────────────

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
        lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 16px; font-weight: 600; border: none;"
        )
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


# ── Accordion row ─────────────────────────────────────────────────────────────

class _AccordionRow(QFrame):
    """
    Single permission item (matches .accordion-item in CSS).

    Parameters
    ----------
    icon_cp:   Font Awesome solid codepoint for the left icon.
    label:     Row title text.
    checked:   Show a green fa-check-circle after the title.
    expanded:  Show the body panel and use fa-chevron-up instead of down.
    body_text: Text inside the expanded body (ignored when expanded=False).
    """

    def __init__(
        self,
        icon_cp: int,
        label: str,
        *,
        checked: bool = False,
        expanded: bool = False,
        body_text: str = "",
        live_check: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.grant_btn: QPushButton | None = None
        self._status_lbl: QLabel | None = None
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
        root.addWidget(self._header(icon_cp, label, checked, expanded, live_check))
        if expanded and body_text:
            root.addWidget(self._body(body_text))

    def set_status(self, result: CheckResult) -> None:
        """Update the live-check status badge (only meaningful when live_check=True)."""
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
            self._status_lbl.setStyleSheet(
                f"color: {_MUTED}; font-size: 12px;"
            )
        if result.message:
            self._status_lbl.setToolTip(result.message)

    # ── row sections ──────────────────────────────────────────────────────────

    def _header(
        self, icon_cp: int, label: str, checked: bool, expanded: bool,
        live_check: bool = False,
    ) -> QWidget:
        """Matches .accordion-header  (icon + title [+ check]  |  chevron)."""
        hdr = QWidget()
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
        hl.addWidget(
            _icon(_FA.CHEVRON_UP if expanded else _FA.CHEVRON_DOWN, 14, color=_MUTED)
        )
        return hdr

    def _body(self, body_text: str) -> QWidget:
        """Matches .accordion-body  (description + Grant Access button)."""
        body = QWidget()
        vl = QVBoxLayout(body)
        vl.setContentsMargins(52, 0, 20, 20)   # 52 px left matches CSS
        vl.setSpacing(16)

        desc = QLabel(body_text)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_MUTED}; font-size: 13px; line-height: 1.5;")
        vl.addWidget(desc)

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
        vl.addWidget(self.grant_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return body


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 20, 0)   # padding-right: 20px
        layout.setSpacing(0)

        layout.addWidget(self._logo())
        layout.addSpacing(16)
        layout.addWidget(self._heading())
        layout.addStretch()                       # justify-content: space-between
        layout.addWidget(self._test_card())
        layout.addSpacing(24)
        layout.addWidget(self._platform_links())

    # ── builders ──────────────────────────────────────────────────────────────

    def _logo(self) -> QLabel:
        """Matches .avatar  (240 × 75, left-aligned, transparent bg)."""
        lbl = QLabel()
        lbl.setFixedHeight(75)
        lbl.setMaximumWidth(240)
        lbl.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        pix = QPixmap(str(resource_path("assets", "proctor", "images", "logo.png")))
        if not pix.isNull():
            lbl.setPixmap(
                pix.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            lbl.setText("CodeChef")
            lbl.setStyleSheet(
                f"color: {_TEXT}; font-size: 22px; font-weight: 700;"
            )
        return lbl

    def _heading(self) -> QLabel:
        """Matches  h1  (40 px, 700 weight, max-width 420 px)."""
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
        """Matches .test-card."""
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
        pix = QPixmap(
            str(resource_path("assets", "proctor", "images", "logo1.png"))
        )
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
        title.setStyleSheet(
            f"color: {_TEXT}; font-size: 14px; font-weight: 600;"
        )
        dur = QLabel("Test duration: 75 minutes")
        dur.setStyleSheet(f"color: {_MUTED}; font-size: 12px;")
        info.addWidget(title)
        info.addWidget(dur)
        hl.addLayout(info)
        hl.addStretch()
        return card

    def _platform_links(self) -> QWidget:
        """Matches .platform-links."""
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
    grant_access_clicked:  User clicked the "Grant Access" button.
    quit_clicked:          User clicked "Quit App".
    """

    grant_access_clicked = Signal()
    quit_clicked = Signal()

    _ACCORDION_ROWS = [
        dict(
            icon_cp=_FA.BORDER_ALL,
            label="Close additional applications",
            checked=True,
        ),
        dict(
            icon_cp=_FA.VIDEO,
            label="Allow Webcam Access",
            expanded=True,
            body_text=(
                "This helps me verify it's you taking the test — just like in an "
                "in-person exam. Don't worry, your privacy is respected, and access "
                "is only for the test duration."
            ),
        ),
        dict(icon_cp=_FA.DESKTOP, label="Check for Multiple Monitors", live_check=True),
        dict(icon_cp=_FA.ARROW_UP_FROM_BRAC, label="Allow Screen Sharing"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._screen_row: _AccordionRow | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._top_bar())
        layout.addSpacing(24)
        layout.addWidget(self._permissions_card(), 1)
        layout.addSpacing(24)
        layout.addWidget(self._bottom_controls())

    # ── builders ──────────────────────────────────────────────────────────────

    def _top_bar(self) -> QWidget:
        """Matches .top-bar  (justify-content: flex-end → sun + lang both on right)."""
        bar = QWidget()
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(16)   # gap: 16px

        hl.addStretch()     # push everything to the right end
        hl.addWidget(_icon(_FA.SUN, 16, solid=False, color=_MUTED))

        # language selector widget
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
        """Matches .permissions-container."""
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
        title.setStyleSheet(
            f"color: {_TEXT}; font-size: 24px; font-weight: 600;"
        )
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
        vl.setSpacing(16)
        for kwargs in self._ACCORDION_ROWS:
            row = _AccordionRow(**kwargs, parent=container)
            if row.grant_btn is not None:
                row.grant_btn.clicked.connect(self.grant_access_clicked)
            if kwargs.get("live_check"):
                self._screen_row = row
            vl.addWidget(row)
        return container

    def set_screen_check_result(self, result: CheckResult) -> None:
        if self._screen_row is not None:
            self._screen_row.set_status(result)

    def _bottom_controls(self) -> QWidget:
        """Matches .bottom-controls  (pagination  |  Back + Start Test)."""
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

    Visually identical to intro.html.  Appears instantly on launch (no WebEngine
    overhead) while index.html and its ML models pre-load in the background.

    Signals
    -------
    quit_requested:     "Quit App" clicked — close without a password prompt.
    continue_requested: Webcam guidelines accepted — switch to the WebView.
    """

    quit_requested     = Signal()
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        _load_fa_fonts()
        super().__init__(parent)
        self._build()

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._modal.resize(self.size())

    # ── UI ────────────────────────────────────────────────────────────────────

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

        layout.addWidget(_LeftPane(self), 10)         # flex: 1
        layout.addWidget(self._right_pane, 12)        # flex: 1.2

        # Persistent overlay modal – sized to fill self in resizeEvent
        self._modal = WebcamGuidelinesModal(self)
        self._modal.accepted.connect(self.continue_requested)

        # Screen monitor – run initial check then watch for changes
        self._screen_monitor = ScreenMonitor(self)
        self._right_pane.set_screen_check_result(self._screen_monitor.check())
        self._screen_monitor.result_changed.connect(self._on_screen_check_changed)

    @Slot(object)
    def _on_screen_check_changed(self, result: CheckResult) -> None:
        self._right_pane.set_screen_check_result(result)

    # ── Slot ──────────────────────────────────────────────────────────────────

    def _on_grant_access(self) -> None:
        self._modal.resize(self.size())
        self._modal.raise_()
        self._modal.show()
