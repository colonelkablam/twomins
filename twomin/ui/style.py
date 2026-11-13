"""One place for the look. Tweak colours here."""

BG = "#1e1f24"
PANEL = "#272830"
FG = "#e8e8ec"
MUTED = "#9a9ba6"
ACCENT = "#f2b134"   # bee yellow
GOOD = "#5cc98a"     # whole task done
CALM = "#7fb3e6"     # stop: resting is allowed (never red)
FLOW = "#a78bfa"     # flow: its own reward
FLOW_BG = "#1f1a2e"
FLOW_PANEL = "#2b2442"

QSS = f"""
QWidget {{ background: {BG}; color: {FG}; font-size: 11pt; }}
QLabel#title {{ font-size: 15pt; font-weight: 600; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; }}
QLabel#hint {{ font-size: 9pt; }}
QLabel#task {{ color: {MUTED}; font-size: 10pt; }}
QLabel#clock {{ font-size: 34pt; font-weight: 700; color: {ACCENT}; }}
QLabel#step {{ font-size: 12pt; font-weight: 600; }}
QLabel#win {{ font-size: 14pt; font-weight: 700; color: {GOOD}; }}
QLineEdit {{
    background: {PANEL}; border: 1px solid #3a3b45; border-radius: 8px;
    padding: 8px 10px; selection-background-color: {ACCENT}; selection-color: #000;
}}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit#optional {{ color: {FG}; }}
QListWidget {{
    background: {PANEL}; border: 1px solid #3a3b45; border-radius: 8px; padding: 4px;
    outline: 0;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: #000; }}
QListWidget#past {{ font-size: 9pt; color: {MUTED}; background: transparent; border: none; padding: 0; }}
QListWidget#past::item {{ padding: 2px 6px; border-radius: 4px; }}
QListWidget#past::item:selected {{ background: {PANEL}; color: {FG}; }}
QPushButton {{
    background: {PANEL}; border: 1px solid #3a3b45; border-radius: 8px; padding: 7px 12px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton#primary {{ background: {ACCENT}; color: #000; font-weight: 700; border: none; }}
QPushButton#good {{ background: {GOOD}; color: #000; font-weight: 700; border: none; }}
QPushButton#stop {{ color: {CALM}; border: 1px solid {CALM}; }}
QPushButton#round {{ color: {ACCENT}; border: 1px solid {ACCENT}; }}
QPushButton#flow {{ background: {FLOW}; color: #14101f; font-weight: 700; border: none; }}
QLabel#flow {{ color: {FLOW}; font-weight: 600; }}
QProgressBar {{ background: {PANEL}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QFrame#card {{ border: 1px solid #3a3b45; border-radius: 12px; }}
"""

# Applied to the timer window itself when it enters flow. A widget's own sheet beats the app
# sheet regardless of specificity, so every background that must survive is restated here.
FLOW_QSS = f"""
QWidget {{ background: {FLOW_BG}; }}
QFrame#card {{ border: 1px solid {FLOW}; border-radius: 12px; }}
QLabel#clock {{ color: {FLOW}; }}
QLabel#flow {{ color: {FLOW}; font-weight: 600; }}
QPushButton {{ background: {FLOW_PANEL}; }}
QPushButton#good {{ background: {GOOD}; }}
QLineEdit {{ background: {FLOW_PANEL}; border: 1px solid {FLOW}; }}
"""
