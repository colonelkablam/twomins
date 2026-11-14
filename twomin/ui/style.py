"""One place for the look: tokens, type scale, font, QSS.

Design rules
  * One hero per screen: the picker's question, the actions screen's task name, the timer's clock.
  * Colours mean states, never decoration: pollen = starting, calm = stop, leaf = done,
    flow = flow. Everything else is ink and greys.
  * Structure carries meaning: dashed boxes are optional, a pollen bar marks the selected row.
  * Key hints are a quiet footer, not instructions in the content.
"""
from __future__ import annotations

from pathlib import Path

# ---- colour tokens
INK = "#17181f"        # window background
RAISED = "#21222c"     # inputs, selected rows, buttons
LINE = "#31333f"       # borders
TEXT = "#eceaf2"
MUTED = "#9193a5"
FAINT = "#646679"      # key-hint footer
POLLEN = "#f2b134"     # starting: countdown, start button, focus ring
LEAF = "#5cc98a"       # whole task done
CALM = "#7fb3e6"       # stop: resting is allowed (never red)
DANGER = "#e08a8a"     # deleting data (Settings → reset) and nothing else
FLOW = "#a78bfa"       # flow: its own reward
FLOW_INK = "#211a36"
FLOW_RAISED = "#2e2550"

# Older names, still imported elsewhere.
BG, PANEL, FG, ACCENT, GOOD = INK, RAISED, TEXT, POLLEN, LEAF

# ---- type: one family, one scale (pt)
FONT = "Atkinson Hyperlegible Next"
FONT_FILE = Path(__file__).parent.parent / "assets" / "AtkinsonHyperlegibleNext.ttf"
GEAR_SVG = Path(__file__).parent.parent / "assets" / "gear.svg"
KEYS, META, BODY, PROMPT, HERO, CLOCK = 9.5, 10.5, 11.5, 13.5, 20, 40


def load_fonts() -> None:
    """Register the bundled font. Call once after QApplication exists; falls back silently."""
    from PySide6.QtGui import QFontDatabase
    QFontDatabase.addApplicationFont(str(FONT_FILE))


def keys(*pairs: tuple[str, str]) -> str:
    """Footer key hints as rich text: the key brighter, the action faint, generous gaps."""
    return "&nbsp;&nbsp;&nbsp;&nbsp;".join(
        f'<span style="color:{MUTED}">{k}</span>&nbsp;{action}' for k, action in pairs)


QSS = f"""
QWidget {{
    background: {INK}; color: {TEXT};
    font-family: "{FONT}", "Adwaita Sans", "Cantarell", sans-serif; font-size: {BODY}pt;
}}

QLabel#hero {{ font-size: {HERO}pt; font-weight: 700; }}
QLabel#prompt {{ font-size: {PROMPT}pt; font-weight: 600; }}
QLabel#meta, QLabel#muted {{ color: {MUTED}; font-size: {META}pt; }}
QLabel#section {{ color: {MUTED}; font-size: {META}pt; font-weight: 600; }}
QLabel#keys, QLabel#hint {{ color: {FAINT}; font-size: {KEYS}pt; }}
QLabel#nudge {{ color: {POLLEN}; font-size: {META}pt; }}
QLabel#score {{ color: {MUTED}; font-size: {META}pt; }}

QLineEdit {{
    background: {RAISED}; border: 1px solid {LINE}; border-radius: 10px;
    padding: 9px 12px; selection-background-color: {POLLEN}; selection-color: {INK};
}}
QLineEdit:focus {{ border: 1px solid {POLLEN}; }}
QLineEdit#ask {{ font-size: {PROMPT}pt; padding: 11px 14px; }}
QLineEdit#optional {{ background: transparent; border: 1px dashed {LINE}; }}
QLineEdit#optional:focus {{ border: 1px solid {POLLEN}; }}
QLineEdit#tasktitle {{
    font-size: {HERO}pt; font-weight: 700; background: transparent;
    border: 1px solid transparent; border-radius: 8px; padding: 0 4px; margin-left: -5px;
}}
QLineEdit#tasktitle:hover {{ border: 1px dashed {LINE}; }}
QLineEdit#tasktitle:focus {{ background: {RAISED}; border: 1px solid {POLLEN}; }}

QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ border-radius: 8px; padding: 0; margin: 1px 0; border-left: 3px solid transparent; }}
QListWidget::item:selected {{ background: {RAISED}; border-left: 3px solid {POLLEN}; }}
QListWidget::item:hover:!selected {{ background: #1c1d26; }}
QWidget#row, QWidget#row QLabel {{ background: transparent; }}
QLabel#rowtitle {{ font-size: {BODY + 0.5}pt; font-weight: 600; }}
QLabel#rowmeta {{ color: {MUTED}; font-size: {META}pt; }}
QListWidget#past {{ font-size: {META}pt; color: {MUTED}; }}
QListWidget#past::item {{ padding: 3px 8px; }}
QListWidget#past::item:selected {{ color: {TEXT}; }}

QPushButton {{
    background: {RAISED}; border: 1px solid {LINE}; border-radius: 10px; padding: 8px 14px;
}}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton#primary {{ background: {POLLEN}; color: {INK}; font-weight: 700; border: none; padding: 9px 18px; }}
QPushButton#good {{ background: {LEAF}; color: {INK}; font-weight: 700; border: none; }}
QPushButton#stop {{ color: {CALM}; border: 1px solid {CALM}; }}
QPushButton#round {{ color: {POLLEN}; border: 1px solid {POLLEN}; }}
QPushButton#flow {{ background: {FLOW}; color: {FLOW_INK}; font-weight: 700; border: none; }}
QPushButton#quiet {{ background: transparent; border: none; color: {MUTED}; padding: 8px 4px; }}
QPushButton#chip {{
    background: transparent; color: {MUTED}; border: 1px dashed {LINE}; border-radius: 12px;
    padding: 3px 12px; font-size: {META}pt;
}}
QPushButton#chip:checked {{ color: {TEXT}; border: 1px solid {MUTED}; background: {RAISED}; }}
QPushButton#quiet:hover {{ color: {TEXT}; }}
QPushButton#gear {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
QPushButton#gear:hover {{ background: {RAISED}; }}
QPushButton#danger {{ color: {DANGER}; border: 1px solid {DANGER}; }}
QPushButton#danger:disabled {{ color: {FAINT}; border: 1px solid {LINE}; }}

/* Buttons with a keycap: the label takes the button's colour; the key sits in a small box */
QPushButton QLabel {{ background: transparent; }}
QPushButton QLabel#btntext {{ font-size: {BODY}pt; }}
QPushButton#good QLabel#btntext, QPushButton#flow QLabel#btntext {{ font-weight: 700; color: {INK}; }}
QPushButton#stop QLabel#btntext {{ color: {CALM}; }}
QPushButton#round QLabel#btntext {{ color: {POLLEN}; }}
QLabel#keycap {{
    font-size: {KEYS}pt; color: {MUTED}; border: 1px solid {LINE}; border-radius: 5px;
    padding: 1px 6px; min-width: 10px; min-height: 16px; max-height: 18px;
    qproperty-alignment: AlignCenter;
}}
QPushButton#good QLabel#keycap, QPushButton#flow QLabel#keycap {{
    color: {INK}; border: 1px solid rgba(23, 24, 31, 0.35);
}}
QPushButton#stop QLabel#keycap {{ color: {CALM}; border: 1px solid rgba(127, 179, 230, 0.45); }}
QPushButton#round QLabel#keycap {{ color: {POLLEN}; border: 1px solid rgba(242, 177, 52, 0.45); }}

QLabel#clock {{ font-size: {CLOCK}pt; font-weight: 700; color: {POLLEN}; }}
QLabel#step {{ font-size: {PROMPT}pt; font-weight: 600; }}
QLabel#task {{ color: {MUTED}; font-size: {META}pt; }}
QLabel#win {{ font-size: {PROMPT + 1}pt; font-weight: 700; color: {LEAF}; }}
QLabel#flow {{ color: {FLOW}; font-weight: 600; }}
QProgressBar {{ background: {RAISED}; border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background: {POLLEN}; border-radius: 2px; }}
QFrame#card {{ border: 1px solid {LINE}; border-radius: 14px; }}
"""

# Applied to the timer window itself when it enters flow. A widget's own sheet beats the app
# sheet regardless of specificity, so every background that must survive is restated here.
FLOW_QSS = f"""
QWidget {{ background: {FLOW_INK}; }}
QFrame#card {{ border: 1px solid {FLOW}; border-radius: 14px; }}
QLabel#clock {{ color: {FLOW}; }}
QLabel#flow {{ color: {FLOW}; font-weight: 600; }}
QPushButton {{ background: {FLOW_RAISED}; }}
QPushButton#good {{ background: {LEAF}; }}
QPushButton QLabel {{ background: transparent; }}
QLineEdit {{ background: {FLOW_RAISED}; border: 1px solid {FLOW}; }}
"""
