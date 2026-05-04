# forix/ui/widgets/stat_tile.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
import design as D


class StatTile(QFrame):
    def __init__(self, label: str, value: str, color: str = None, parent=None):
        super().__init__(parent)
        self._color = color or D.COLOR_ACC
        self.setObjectName("card")
        self.setFixedHeight(76)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame#card {{"
            f"  background: {D.COLOR_SURF};"
            f"  border: none;"
            f"  border-top: 2px solid {self._color};"
            f"  border-radius: {D.R_LG}px;"
            f"}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(D.SP_4, D.SP_3, D.SP_4, D.SP_2)
        lay.setSpacing(1)

        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"font-size: {D.FSIZE_XL}pt; font-weight: 800; color: {self._color};"
            f" background: transparent; border: none;"
        )
        lay.addWidget(self._val)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-size: {D.FSIZE_XS}pt; font-weight: 700; color: {D.COLOR_TXT2};"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        lay.addWidget(lbl)

    def set_value(self, v: str):
        self._val.setText(v)