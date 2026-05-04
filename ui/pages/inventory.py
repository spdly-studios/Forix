# forix/ui/pages/inventory.py
"""
Forix — Inventory Page (v2 — full-featured)

New features over v1:
  • Stats bar        — total items / units / low-stock / out-of-stock at a glance
  • Sort bar         — sort by name, qty (asc/desc), category, last updated
  • Grid / List view — toggle between card grid and compact table list
  • Quick ±1 buttons — increment/decrement stock directly on the card face
  • Detail panel     — click any card to open a right-side slide-in panel with
                       all fields, description, and full stock-adjustment history
  • Bulk select mode — checkbox per card; toolbar shows bulk Delete / Export CSV
  • CSV export       — exports the current filtered view to a chosen file
  • Stock history    — every ±N adjustment is logged to stock_log table with
                       optional note and timestamp
"""

import csv
import datetime
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.database import InventoryItem, StockLog, get_session
import design as D

log = logging.getLogger("forix.inventory")

_CARD_W  = 220
_CARD_IMG = 170
_CARD_H  = _CARD_IMG + 145
_PANEL_W = 320

_SS_SEARCH = (
    f"QLineEdit{{background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_3}px;}}"
    f"QLineEdit:focus{{border-color:{D.COLOR_ACC};}}"
)
_SS_COMBO = (
    f"QComboBox{{background:{D.COLOR_SURF};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_3}px;}}"
    f"QComboBox:hover{{border-color:{D.COLOR_ACC};}}"
    f"QComboBox::drop-down{{border:none;width:20px;}}"
    f"QComboBox QAbstractItemView{{background:{D.COLOR_SURF2};"
    f"border:1px solid {D.COLOR_BDR2};border-radius:{D.R_MD}px;"
    f"color:{D.COLOR_TXT};selection-background-color:{D.COLOR_ACC_TINT};"
    f"selection-color:{D.COLOR_ACC};outline:none;}}"
)
_SS_INPUT = (
    f"QLineEdit,QSpinBox{{background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};"
    f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;"
    f"padding:0 {D.SP_2}px;min-height:{D.H_BTN}px;}}"
    f"QLineEdit:focus,QSpinBox:focus{{border-color:{D.COLOR_ACC};}}"
    f"QSpinBox::up-button,QSpinBox::down-button{{border:none;width:16px;}}"
)
_SS_TABLE = (
    f"QTableWidget{{background:{D.COLOR_SURF};border:none;"
    f"gridline-color:{D.COLOR_BDR};color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;}}"
    f"QTableWidget::item{{padding:0 {D.SP_2}px;border:none;}}"
    f"QTableWidget::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_TXT};}}"
    f"QTableWidget::item:alternate{{background:{D.COLOR_SURF2};}}"
    f"QHeaderView::section{{background:{D.COLOR_SURF2};color:{D.COLOR_TXT2};"
    f"font-size:{D.FSIZE_XS}pt;font-weight:700;border:none;"
    f"border-bottom:1px solid {D.COLOR_BDR2};padding:{D.SP_1}px {D.SP_2}px;}}"
)


def _placeholder(w, h, cat):
    palettes = [
        ("#6366f1","#4338ca"),("#a855f7","#7c3aed"),("#3b82f6","#1d4ed8"),
        ("#10b981","#047857"),("#f59e0b","#b45309"),("#ef4444","#b91c1c"),
    ]
    idx = ord((cat or "?")[0].upper()) % len(palettes)
    c1, c2 = palettes[idx]
    pm = QPixmap(w, h); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0,0,w,h); g.setColorAt(0,QColor(c1)); g.setColorAt(1,QColor(c2))
    p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen); p.drawRect(0,0,w,h)
    f = QFont(D.FONT_UI, int(h*0.28)); f.setBold(True)
    p.setFont(f); p.setPen(QColor(255,255,255,80))
    p.drawText(0,0,w,h,Qt.AlignmentFlag.AlignCenter,(cat or "?")[0].upper())
    p.end(); return pm


def _load_img(path, w, h, cat):
    if path and Path(path).is_file():
        pm = QPixmap(path)
        if not pm.isNull():
            sc = pm.scaled(w,h,Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
            x = max(0,(sc.width()-w)//2); y = max(0,(sc.height()-h)//2)
            return sc.copy(x,y,w,h)
    return _placeholder(w,h,cat)


class _Card(QWidget):
    sig_edit   = pyqtSignal(int)
    sig_delete = pyqtSignal(int)
    sig_adjust = pyqtSignal(int,int)
    sig_select = pyqtSignal(int,bool)
    sig_open   = pyqtSignal(int)

    def __init__(self, data, sel_mode=False, parent=None):
        super().__init__(parent)
        self._d = data; self._hovered = False
        self._selected = False; self._sel_mode = sel_mode
        self.setFixedSize(_CARD_W, _CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)

    def set_select_mode(self, on):
        self._sel_mode = on
        if not on: self._selected = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        d = self._d; w,h = self.width(),self.height()
        iw,ih = w,_CARD_IMG; r = float(D.R_LG)

        bg = QColor(D.COLOR_SURF3 if self._selected else
                    D.COLOR_SURF2 if self._hovered else D.COLOR_SURF)
        path = QPainterPath(); path.addRoundedRect(0,0,w,h,r,r)
        p.fillPath(path,QBrush(bg))
        bdr = QColor(D.COLOR_ACC if (self._selected or self._hovered) else D.COLOR_BDR2)
        p.setPen(QPen(bdr, 1.5 if self._selected else 1.0)); p.drawPath(path)

        img = _load_img(d.get("image_path"),iw,ih,d.get("category","?"))
        clip = QPainterPath()
        clip.moveTo(r,0); clip.lineTo(iw-r,0); clip.quadTo(iw,0,iw,r)
        clip.lineTo(iw,ih); clip.lineTo(0,ih); clip.lineTo(0,r)
        clip.quadTo(0,0,r,0); clip.closeSubpath()
        p.save(); p.setClipPath(clip); p.drawPixmap(0,0,img)
        fade = QLinearGradient(0,ih*0.5,0,ih)
        fade.setColorAt(0,QColor(0,0,0,0)); fade.setColorAt(1,QColor(9,9,11,200))
        p.fillRect(0,0,iw,ih,QBrush(fade)); p.restore()

        if self._sel_mode:
            cbx=10; cby=ih-30; cbsz=20
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(D.COLOR_ACC if self._selected else D.COLOR_SURF2)))
            p.drawRoundedRect(cbx,cby,cbsz,cbsz,4,4)
            if self._selected:
                p.setPen(QPen(QColor(D.COLOR_WHITE),2.0))
                p.drawLine(cbx+4,cby+10,cbx+8,cby+14)
                p.drawLine(cbx+8,cby+14,cbx+16,cby+6)

        if d.get("is_low"):
            rp = QPainterPath(); rp.moveTo(0,0); rp.lineTo(36,0)
            rp.lineTo(0,36); rp.closeSubpath()
            p.fillPath(rp,QBrush(QColor(D.COLOR_WRN)))

        qty=d.get("quantity",0); unit=d.get("unit","pcs")
        btxt=f"{qty} {unit}"
        bfont=QFont(D.FONT_UI,D.FSIZE_XS); bfont.setBold(True); p.setFont(bfont)
        fm=p.fontMetrics(); bpad=6
        bw=fm.horizontalAdvance(btxt)+bpad*2; bh=fm.height()+4
        bx=w-bw-D.SP_2; by=D.SP_2
        bbg=QColor(D.COLOR_ERR if d.get("is_low") else D.COLOR_ACC); bbg.setAlpha(220)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bbg))
        p.drawRoundedRect(bx,by,bw,bh,4,4)
        p.setPen(QColor(D.COLOR_WHITE))
        p.drawText(bx,by,bw,bh,Qt.AlignmentFlag.AlignCenter,btxt)

        tx=D.SP_3; ty=ih+D.SP_2; tfw=w-D.SP_3*2
        cat=(d.get("category") or "").capitalize()
        cfont=QFont(D.FONT_UI,D.FSIZE_XS); cfont.setBold(True); p.setFont(cfont)
        cfm=p.fontMetrics(); cw=cfm.horizontalAdvance(cat)+10; ch=cfm.height()+4
        cbg=QColor(D.COLOR_ACC); cbg.setAlpha(30)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(cbg))
        p.drawRoundedRect(tx,ty,cw,ch,3,3)
        p.setPen(QColor(D.COLOR_ACC)); p.drawText(tx,ty,cw,ch,Qt.AlignmentFlag.AlignCenter,cat)

        ty+=ch+D.SP_1
        nfont=QFont(D.FONT_UI,D.FSIZE_MD); nfont.setBold(True); p.setFont(nfont)
        p.setPen(QColor(D.COLOR_TXT_HEAD))
        el=p.fontMetrics().elidedText(d.get("name",""),Qt.TextElideMode.ElideRight,tfw)
        p.drawText(tx,ty,tfw,p.fontMetrics().height()+2,
                   Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop,el)

        ty+=p.fontMetrics().height()+2
        desc=(d.get("description") or "").strip()
        if desc:
            dfont=QFont(D.FONT_UI,D.FSIZE_XS); p.setFont(dfont)
            p.setPen(QColor(D.COLOR_TXT2))
            de=p.fontMetrics().elidedText(desc,Qt.TextElideMode.ElideRight,tfw)
            p.drawText(tx,ty,tfw,p.fontMetrics().height(),Qt.AlignmentFlag.AlignLeft,de)
            ty+=p.fontMetrics().height()+D.SP_1

        loc=d.get("location","")
        if loc:
            lfont=QFont(D.FONT_UI,D.FSIZE_XS); p.setFont(lfont)
            p.setPen(QColor(D.COLOR_TXT_DIS))
            le=p.fontMetrics().elidedText(f"📍 {loc}",Qt.TextElideMode.ElideRight,tfw)
            p.drawText(tx,ty,tfw,p.fontMetrics().height(),Qt.AlignmentFlag.AlignLeft,le)
            ty+=p.fontMetrics().height()+D.SP_1

        if d.get("is_low"):
            wfont=QFont(D.FONT_UI,D.FSIZE_XS); wfont.setBold(True); p.setFont(wfont)
            p.setPen(QColor(D.COLOR_WRN))
            p.drawText(tx,ty,tfw,p.fontMetrics().height(),Qt.AlignmentFlag.AlignLeft,"⚠  Low stock")

        btn_y=h-32; btn_h=24; btn_w=32
        for bi,(lbl,col_alpha) in enumerate([("−",40),("＋",40)]):
            bxx=tx+bi*(btn_w+4)
            bb2=QColor(D.COLOR_SURF3); bb2.setAlpha(col_alpha)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bb2))
            p.drawRoundedRect(bxx,btn_y,btn_w,btn_h,D.R_SM,D.R_SM)
            p.setPen(QColor(D.COLOR_TXT2))
            p.setFont(QFont(D.FONT_UI,D.FSIZE_SM))
            p.drawText(bxx,btn_y,btn_w,btn_h,Qt.AlignmentFlag.AlignCenter,lbl)

        p.end()

    def enterEvent(self,_): self._hovered=True; self.update()
    def leaveEvent(self,_): self._hovered=False; self.update()

    def mousePressEvent(self,e):
        if e.button()!=Qt.MouseButton.LeftButton: return
        x,y=e.position().x(),e.position().y()
        btn_y=_CARD_H-32; btn_h=24
        if btn_y<=y<=btn_y+btn_h and D.SP_3<=x<=D.SP_3+32:
            self.sig_adjust.emit(self._d["id"],-1); return
        if btn_y<=y<=btn_y+btn_h and D.SP_3+36<=x<=D.SP_3+68:
            self.sig_adjust.emit(self._d["id"],1); return
        if self._sel_mode:
            self._selected=not self._selected
            self.sig_select.emit(self._d["id"],self._selected); self.update()
        else:
            self.sig_open.emit(self._d["id"])

    def mouseDoubleClickEvent(self,_):
        if not self._sel_mode: self.sig_edit.emit(self._d["id"])

    def _ctx(self,pos):
        menu=QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};"
            f"border-radius:{D.R_MD}px;color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;padding:4px;}}"
            f"QMenu::item{{padding:6px 20px;border-radius:{D.R_SM}px;}}"
            f"QMenu::item:selected{{background:{D.COLOR_ACC_TINT};color:{D.COLOR_ACC};}}"
            f"QMenu::separator{{background:{D.COLOR_BDR2};height:1px;margin:4px 8px;}}"
        )
        ea=menu.addAction("✎  Edit"); menu.addSeparator()
        ia=menu.addAction("＋  Add stock"); da=menu.addAction("－  Remove stock")
        menu.addSeparator(); xa=menu.addAction("🗑  Delete")
        act=menu.exec(self.mapToGlobal(pos)); iid=self._d["id"]
        if   act==ea: self.sig_edit.emit(iid)
        elif act==ia: self.sig_adjust.emit(iid,1)
        elif act==da: self.sig_adjust.emit(iid,-1)
        elif act==xa: self.sig_delete.emit(iid)


class _DetailPanel(QWidget):
    sig_edit   = pyqtSignal(int)
    sig_close  = pyqtSignal()
    sig_adjust = pyqtSignal(int,int,str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._item_id=None
        self.setFixedWidth(_PANEL_W)
        self.setStyleSheet(f"background:{D.COLOR_SURF};border-left:1px solid {D.COLOR_BDR2};")
        lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        hdr=QWidget(); hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{D.COLOR_SURF2};border-bottom:1px solid {D.COLOR_BDR2};")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(D.SP_4,0,D.SP_2,0)
        self._title=QLabel("Item Details")
        self._title.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_MD}pt;"
                                   "font-weight:700;background:transparent;border:none;")
        hl.addWidget(self._title); hl.addStretch()
        eb=QPushButton("✎ Edit"); eb.setObjectName("ghostBtn"); eb.setFixedHeight(D.H_BTN)
        eb.clicked.connect(lambda: self.sig_edit.emit(self._item_id))
        cb=QPushButton("✕"); cb.setObjectName("ghostBtn"); cb.setFixedSize(D.H_BTN,D.H_BTN)
        cb.clicked.connect(self.sig_close)
        hl.addWidget(eb); hl.addWidget(cb); lay.addWidget(hdr)

        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_SURF};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_SURF};width:4px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};border-radius:2px;min-height:16px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        body=QWidget(); body.setStyleSheet(f"background:{D.COLOR_SURF};")
        bl=QVBoxLayout(body); bl.setContentsMargins(D.SP_4,D.SP_4,D.SP_4,D.SP_4); bl.setSpacing(D.SP_3)

        self._img_lbl=QLabel()
        self._img_lbl.setFixedHeight(140)
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{D.COLOR_SURF2};border-radius:{D.R_LG}px;border:none;")
        bl.addWidget(self._img_lbl)

        def _field(label,attr):
            rw=QWidget(); rw.setStyleSheet("background:transparent;border:none;")
            rl=QVBoxLayout(rw); rl.setContentsMargins(0,0,0,0); rl.setSpacing(2)
            lb=QLabel(label)
            lb.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                              "font-weight:700;letter-spacing:0.4px;background:transparent;border:none;")
            vl=QLabel("—"); vl.setWordWrap(True)
            vl.setStyleSheet(f"color:{D.COLOR_TXT};font-size:{D.FSIZE_SM}pt;background:transparent;border:none;")
            rl.addWidget(lb); rl.addWidget(vl); bl.addWidget(rw); setattr(self,attr,vl)

        _field("NAME","_v_name"); _field("DESCRIPTION","_v_desc")
        _field("CATEGORY","_v_cat"); _field("LOCATION","_v_loc")

        qc=QWidget(); qc.setStyleSheet(f"background:{D.COLOR_SURF2};border-radius:{D.R_MD}px;border:none;")
        qcl=QVBoxLayout(qc); qcl.setContentsMargins(D.SP_3,D.SP_3,D.SP_3,D.SP_3); qcl.setSpacing(D.SP_2)
        ql=QLabel("STOCK"); ql.setStyleSheet(
            f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;font-weight:700;"
            "letter-spacing:0.4px;background:transparent;border:none;")
        self._v_qty=QLabel("0"); self._v_qty.setStyleSheet(
            f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_2XL}pt;font-weight:800;background:transparent;border:none;")
        qcl.addWidget(ql); qcl.addWidget(self._v_qty)
        ar=QHBoxLayout(); ar.setSpacing(D.SP_2)
        self._adj_note=QLineEdit(); self._adj_note.setPlaceholderText("Note (optional)…")
        self._adj_note.setStyleSheet(_SS_INPUT); self._adj_note.setFixedHeight(D.H_BTN)
        ar.addWidget(self._adj_note,1)
        for delta,lbl,col in [(-1,"−",D.COLOR_ERR),(1,"＋",D.COLOR_OK)]:
            btn=QPushButton(lbl); btn.setFixedSize(34,D.H_BTN)
            btn.setStyleSheet(
                f"QPushButton{{background:{col};color:#fff;border:none;"
                f"border-radius:{D.R_SM}px;font-size:{D.FSIZE_MD}pt;font-weight:700;}}")
            btn.clicked.connect(lambda _,d=delta: self._do_adj(d))
            ar.addWidget(btn)
        qcl.addLayout(ar); bl.addWidget(qc)
        _field("LOW ALERT BELOW","_v_low")

        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); sep.setFixedHeight(1)
        bl.addWidget(sep)
        hl2=QLabel("Stock History")
        hl2.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;"
                           "font-weight:700;background:transparent;border:none;")
        bl.addWidget(hl2)
        self._hist_list=QWidget(); self._hist_list.setStyleSheet("background:transparent;border:none;")
        self._hist_lay=QVBoxLayout(self._hist_list)
        self._hist_lay.setContentsMargins(0,0,0,0); self._hist_lay.setSpacing(D.SP_1)
        bl.addWidget(self._hist_list); bl.addStretch()
        scroll.setWidget(body); lay.addWidget(scroll)

    def load(self,iid):
        self._item_id=iid
        s=get_session()
        try:
            item=s.query(InventoryItem).filter_by(id=iid).first()
            if not item: return
            self._title.setText(item.name)
            self._v_name.setText(item.name)
            self._v_desc.setText(item.description or "—")
            self._v_cat.setText((item.category or "—").capitalize())
            self._v_loc.setText(item.location or "—")
            lo=item.quantity<=item.low_threshold
            self._v_qty.setText(f"{item.quantity} {item.unit}")
            self._v_qty.setStyleSheet(
                f"color:{D.COLOR_ERR if lo else D.COLOR_TXT_HEAD};"
                f"font-size:{D.FSIZE_2XL}pt;font-weight:800;background:transparent;border:none;")
            self._v_low.setText(str(item.low_threshold))
            ip=getattr(item,"image_path",None) or ""
            if ip and Path(ip).is_file():
                pm=QPixmap(ip).scaled(_PANEL_W-D.SP_4*2,140,
                    Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                self._img_lbl.setPixmap(pm)
            else:
                pm=_placeholder(_PANEL_W-D.SP_4*2,140,item.category or "?")
                self._img_lbl.setPixmap(pm)
            logs=(s.query(StockLog).filter_by(item_id=iid)
                  .order_by(StockLog.created_at.desc()).limit(30).all())
            self._render_hist(logs)
        finally:
            s.close()

    def _render_hist(self,logs):
        while self._hist_lay.count():
            w=self._hist_lay.takeAt(0).widget()
            if w: w.deleteLater()
        if not logs:
            e=QLabel("No adjustments yet.")
            e.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;"
                             "background:transparent;border:none;")
            self._hist_lay.addWidget(e); return
        for lg in logs:
            row=QWidget(); row.setStyleSheet(
                f"background:{D.COLOR_SURF2};border-radius:{D.R_SM}px;border:none;")
            rl=QHBoxLayout(row); rl.setContentsMargins(D.SP_2,D.SP_1,D.SP_2,D.SP_1); rl.setSpacing(D.SP_2)
            sign="＋" if lg.delta>0 else "－"
            col=D.COLOR_OK if lg.delta>0 else D.COLOR_ERR
            dl=QLabel(f"{sign}{abs(lg.delta)}")
            dl.setStyleSheet(f"color:{col};font-size:{D.FSIZE_SM}pt;font-weight:700;"
                              "background:transparent;border:none;min-width:36px;")
            nl=QLabel(lg.note or "")
            nl.setStyleSheet(f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;background:transparent;border:none;")
            ts=lg.created_at.strftime("%d %b %H:%M") if lg.created_at else ""
            tl=QLabel(ts)
            tl.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;background:transparent;border:none;")
            rl.addWidget(dl); rl.addWidget(nl,1); rl.addWidget(tl)
            self._hist_lay.addWidget(row)

    def _do_adj(self,delta):
        if self._item_id is None: return
        note=self._adj_note.text().strip(); self._adj_note.clear()
        self.sig_adjust.emit(self._item_id,delta,note)


class ItemDialog(QDialog):
    def __init__(self,parent=None,item=None):
        super().__init__(parent)
        self._image_path=getattr(item,"image_path",None)
        self.setWindowTitle("Add Item" if not item else "Edit Item")
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags()&~Qt.WindowType.WindowContextHelpButtonHint)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        hdr=QWidget(); hdr.setFixedHeight(64)
        hdr.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {D.COLOR_ACC},stop:1 {D.COLOR_ACC_DK});")
        hl=QVBoxLayout(hdr); hl.setContentsMargins(D.SP_5,0,D.SP_5,0)
        t=QLabel("New Item" if not item else f"Editing — {item.name}")
        t.setStyleSheet("color:#fff;font-size:15px;font-weight:800;background:transparent;border:none;")
        s=QLabel("Fill in the item details below")
        s.setStyleSheet(f"color:rgba(255,255,255,0.7);font-size:{D.FSIZE_XS}pt;background:transparent;border:none;")
        hl.addWidget(t); hl.addWidget(s); root.addWidget(hdr)

        body=QWidget(); body.setStyleSheet(f"background:{D.COLOR_SURF};")
        bl=QVBoxLayout(body); bl.setContentsMargins(D.SP_5,D.SP_4,D.SP_5,D.SP_4); bl.setSpacing(D.SP_3)

        ir=QHBoxLayout(); ir.setSpacing(D.SP_3)
        self._prev=QLabel(); self._prev.setFixedSize(80,64)
        self._prev.setAlignment(Qt.AlignmentFlag.AlignCenter); self._prev.setScaledContents(True)
        self._refresh_prev(); ir.addWidget(self._prev)
        ib=QVBoxLayout(); ib.setSpacing(D.SP_1)
        pb=QPushButton("📷  Choose Image"); pb.setObjectName("ghostBtn"); pb.setFixedHeight(D.H_BTN); pb.clicked.connect(self._pick)
        cb=QPushButton("✕  Clear"); cb.setObjectName("ghostBtn"); cb.setFixedHeight(D.H_BTN_SM); cb.clicked.connect(self._clear)
        ib.addWidget(pb); ib.addWidget(cb); ib.addStretch()
        ir.addLayout(ib); ir.addStretch(); bl.addLayout(ir)

        div=QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); div.setFixedHeight(1); bl.addWidget(div)

        form=QFormLayout(); form.setSpacing(D.SP_3)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        def lbl(t):
            l=QLabel(t); l.setStyleSheet(
                f"color:{D.COLOR_TXT2};font-size:{D.FSIZE_XS}pt;font-weight:700;"
                "letter-spacing:0.4px;background:transparent;border:none;"); return l

        self.f_name=QLineEdit(item.name if item else ""); self.f_name.setPlaceholderText("e.g. Arduino Nano")
        self.f_desc=QLineEdit(item.description if item else ""); self.f_desc.setPlaceholderText("Short description")
        qr=QHBoxLayout(); qr.setSpacing(D.SP_2)
        self.f_qty=QSpinBox(); self.f_qty.setRange(0,99999); self.f_qty.setValue(item.quantity if item else 0)
        self.f_unit=QLineEdit(item.unit if item else "pcs"); self.f_unit.setFixedWidth(70); self.f_unit.setPlaceholderText("pcs")
        qr.addWidget(self.f_qty,3); qr.addWidget(QLabel("unit"),0); qr.addWidget(self.f_unit,1)
        qw=QWidget(); qw.setLayout(qr)
        self.f_cat=QLineEdit(item.category if item else "component"); self.f_cat.setPlaceholderText("component / tool…")
        self.f_loc=QLineEdit(item.location if item else ""); self.f_loc.setPlaceholderText("Drawer A, Shelf 2…")
        self.f_low=QSpinBox(); self.f_low.setRange(0,9999); self.f_low.setValue(item.low_threshold if item else 2)
        for w in [self.f_name,self.f_desc,self.f_qty,self.f_unit,self.f_cat,self.f_loc,self.f_low]:
            w.setStyleSheet(_SS_INPUT)
        form.addRow(lbl("Name *"),self.f_name); form.addRow(lbl("Description"),self.f_desc)
        form.addRow(lbl("Quantity"),qw); form.addRow(lbl("Category"),self.f_cat)
        form.addRow(lbl("Location"),self.f_loc); form.addRow(lbl("Alert below"),self.f_low)
        bl.addLayout(form); root.addWidget(body)

        footer=QWidget(); footer.setFixedHeight(54)
        footer.setStyleSheet(f"background:{D.COLOR_SURF};border-top:1px solid {D.COLOR_BDR};")
        fl=QHBoxLayout(footer); fl.setContentsMargins(D.SP_5,0,D.SP_5,0); fl.setSpacing(D.SP_2); fl.addStretch()
        can=QPushButton("Cancel"); can.setObjectName("ghostBtn"); can.setFixedSize(90,D.H_BTN); can.clicked.connect(self.reject)
        ok=QPushButton("Save" if item else "Add Item"); ok.setObjectName("accentBtn"); ok.setFixedSize(110,D.H_BTN); ok.clicked.connect(self.accept)
        fl.addWidget(can); fl.addWidget(ok); root.addWidget(footer)

    def _pick(self):
        p,_=QFileDialog.getOpenFileName(self,"Choose Image","","Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if p: self._image_path=p; self._refresh_prev()
    def _clear(self): self._image_path=None; self._refresh_prev()
    def _refresh_prev(self):
        if self._image_path and Path(self._image_path).is_file():
            pm=QPixmap(self._image_path).scaled(80,64,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
            self._prev.setPixmap(pm); self._prev.setText("")
            self._prev.setStyleSheet(f"background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};border-radius:{D.R_MD}px;")
        else:
            self._prev.setPixmap(QPixmap()); self._prev.setText("No image")
            self._prev.setStyleSheet(f"background:{D.COLOR_SURF2};border:1px solid {D.COLOR_BDR2};border-radius:{D.R_MD}px;color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;")
    def get_data(self):
        return {"name":self.f_name.text().strip(),"description":self.f_desc.text().strip(),
                "quantity":self.f_qty.value(),"unit":self.f_unit.text().strip() or "pcs",
                "category":self.f_cat.text().strip() or "component","location":self.f_loc.text().strip(),
                "low_threshold":self.f_low.value(),"image_path":self._image_path or ""}


class _StatsBar(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(f"background:{D.COLOR_SURF};border-bottom:1px solid {D.COLOR_BDR};")
        lay=QHBoxLayout(self); lay.setContentsMargins(D.SP_6,0,D.SP_6,0); lay.setSpacing(D.SP_6)
        self._vals={}
        for key,icon,label in [("total","📦","Total Items"),("units","🔢","Total Units"),
                                 ("low","⚠","Low Stock"),("out","🚫","Out of Stock")]:
            tile=QWidget(); tile.setStyleSheet("background:transparent;border:none;")
            tl=QHBoxLayout(tile); tl.setContentsMargins(0,0,0,0); tl.setSpacing(D.SP_1)
            ic=QLabel(icon); ic.setStyleSheet("background:transparent;border:none;font-size:12px;")
            val=QLabel("—"); val.setStyleSheet(f"color:{D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;font-weight:700;background:transparent;border:none;")
            desc=QLabel(label); desc.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_XS}pt;background:transparent;border:none;")
            tl.addWidget(ic); tl.addWidget(val); tl.addWidget(desc)
            self._vals[key]=val; lay.addWidget(tile)
        lay.addStretch()

    def update_stats(self,items):
        total=len(items); units=sum(i.get("quantity",0) for i in items)
        low=sum(1 for i in items if i.get("is_low") and i.get("quantity",0)>0)
        out=sum(1 for i in items if i.get("quantity",0)==0)
        self._vals["total"].setText(str(total)); self._vals["units"].setText(str(units))
        self._vals["low"].setText(str(low))
        self._vals["low"].setStyleSheet(f"color:{D.COLOR_WRN if low else D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;font-weight:700;background:transparent;border:none;")
        self._vals["out"].setText(str(out))
        self._vals["out"].setStyleSheet(f"color:{D.COLOR_ERR if out else D.COLOR_TXT_HEAD};font-size:{D.FSIZE_SM}pt;font-weight:700;background:transparent;border:none;")


class InventoryPage(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._all=[]; self._grid_view=True; self._sel_mode=False
        self._selected=set(); self._last_cols=-1; self._cached_filtered=[]
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        hdr=QWidget(); hdr.setObjectName("pageHeader"); hdr.setFixedHeight(56)
        hl=QHBoxLayout(hdr); hl.setContentsMargins(D.SP_6,0,D.SP_6,0); hl.setSpacing(D.SP_3)
        title=QLabel("Inventory"); title.setObjectName("pageTitle"); hl.addWidget(title)
        self._cnt=QLabel(""); self._cnt.setStyleSheet(f"color:{D.COLOR_TXT_DIS};font-size:{D.FSIZE_SM}pt;background:transparent;border:none;"); hl.addWidget(self._cnt)
        hl.addStretch()
        self._search=QLineEdit(); self._search.setPlaceholderText("🔍  Search…")
        self._search.setFixedSize(190,D.H_BTN_LG); self._search.setStyleSheet(_SS_SEARCH)
        self._search.textChanged.connect(self._filter); hl.addWidget(self._search)
        self._cat_cb=QComboBox(); self._cat_cb.setFixedSize(140,D.H_BTN_LG)
        self._cat_cb.setStyleSheet(_SS_COMBO); self._cat_cb.addItem("All Categories")
        self._cat_cb.currentTextChanged.connect(self._filter); hl.addWidget(self._cat_cb)
        self._sort_cb=QComboBox(); self._sort_cb.setFixedSize(155,D.H_BTN_LG)
        self._sort_cb.setStyleSheet(_SS_COMBO)
        for opt in ["Name A→Z","Name Z→A","Qty ↑","Qty ↓","Category","Last Updated"]:
            self._sort_cb.addItem(opt)
        self._sort_cb.currentTextChanged.connect(self._filter); hl.addWidget(self._sort_cb)
        self._low_btn=QPushButton("⚠  Low Stock"); self._low_btn.setObjectName("ghostBtn")
        self._low_btn.setCheckable(True); self._low_btn.setFixedHeight(D.H_BTN_LG)
        self._low_btn.toggled.connect(self._filter); hl.addWidget(self._low_btn)
        self._view_btn=QPushButton("☰  List"); self._view_btn.setObjectName("ghostBtn")
        self._view_btn.setFixedHeight(D.H_BTN_LG); self._view_btn.clicked.connect(self._toggle_view)
        hl.addWidget(self._view_btn)
        self._sel_btn=QPushButton("☑  Select"); self._sel_btn.setObjectName("ghostBtn")
        self._sel_btn.setCheckable(True); self._sel_btn.setFixedHeight(D.H_BTN_LG)
        self._sel_btn.toggled.connect(self._toggle_select); hl.addWidget(self._sel_btn)
        dv=QFrame(); dv.setFrameShape(QFrame.Shape.VLine); dv.setFixedWidth(1)
        dv.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); hl.addWidget(dv)
        self._export_btn=QPushButton("↓ CSV"); self._export_btn.setObjectName("ghostBtn")
        self._export_btn.setFixedHeight(D.H_BTN_LG); self._export_btn.clicked.connect(self._export_csv)
        hl.addWidget(self._export_btn)
        add=QPushButton("＋  Add Item"); add.setObjectName("accentBtn")
        add.setFixedHeight(D.H_BTN_LG); add.clicked.connect(self._add); hl.addWidget(add)
        root.addWidget(hdr)

        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{D.COLOR_BDR};border:none;"); root.addWidget(sep)

        self._stats=_StatsBar(); root.addWidget(self._stats)

        self._bulk_bar=QWidget(); self._bulk_bar.setFixedHeight(40)
        self._bulk_bar.setStyleSheet(f"background:{D.COLOR_ACC_TINT};border-bottom:1px solid {D.COLOR_ACC_TINTB};")
        bbl=QHBoxLayout(self._bulk_bar); bbl.setContentsMargins(D.SP_6,0,D.SP_6,0); bbl.setSpacing(D.SP_3)
        self._sel_lbl=QLabel("0 selected"); self._sel_lbl.setStyleSheet(
            f"color:{D.COLOR_ACC};font-size:{D.FSIZE_SM}pt;font-weight:700;background:transparent;border:none;")
        bbl.addWidget(self._sel_lbl); bbl.addStretch()
        bd=QPushButton("🗑  Delete Selected"); bd.setObjectName("ghostBtn"); bd.setFixedHeight(D.H_BTN); bd.clicked.connect(self._bulk_delete)
        bx=QPushButton("↓  Export Selected"); bx.setObjectName("ghostBtn"); bx.setFixedHeight(D.H_BTN); bx.clicked.connect(lambda: self._export_csv(True))
        bbl.addWidget(bd); bbl.addWidget(bx); self._bulk_bar.hide(); root.addWidget(self._bulk_bar)

        self._splitter=QSplitter(Qt.Orientation.Horizontal); self._splitter.setHandleWidth(0)
        self._splitter.setStyleSheet(f"QSplitter::handle{{background:{D.COLOR_BDR2};}}")

        self._scroll=QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{D.COLOR_BG};border:none;}}"
            f"QScrollBar:vertical{{background:{D.COLOR_BG};width:6px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{D.COLOR_SURF3};border-radius:3px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        self._gc=QWidget(); self._gc.setStyleSheet(f"background:{D.COLOR_BG};")
        self._grid=QGridLayout(self._gc); self._grid.setContentsMargins(D.SP_6,D.SP_5,D.SP_6,D.SP_8)
        self._grid.setSpacing(D.SP_4); self._grid.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._gc)

        self._table=QTableWidget(0,7)
        self._table.setHorizontalHeaderLabels(["Name","Qty","Unit","Category","Location","Status","Updated"])
        self._table.setStyleSheet(_SS_TABLE); self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False); self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(D.H_ROW)
        hh=self._table.horizontalHeader()
        for i in range(7): hh.setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self._table.doubleClicked.connect(lambda idx: self._open_panel(
            self._table.item(idx.row(),0).data(Qt.ItemDataRole.UserRole)))
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._table_ctx); self._table.hide()

        self._splitter.addWidget(self._scroll); self._splitter.addWidget(self._table)

        self._panel=_DetailPanel()
        self._panel.sig_edit.connect(self._edit_by_id)
        self._panel.sig_close.connect(self._close_panel)
        self._panel.sig_adjust.connect(self._adj_with_note)
        self._panel.hide(); self._splitter.addWidget(self._panel)
        self._splitter.setStretchFactor(0,1); self._splitter.setStretchFactor(1,1); self._splitter.setStretchFactor(2,0)
        root.addWidget(self._splitter)

    def refresh(self):
        try:
            s=get_session()
            try:
                items=s.query(InventoryItem).order_by(InventoryItem.name).all()
                self._all=[self._to_dict(i) for i in items]
                cats=sorted({i["category"] for i in self._all if i["category"]})
                cur=self._cat_cb.currentText()
                self._cat_cb.blockSignals(True); self._cat_cb.clear()
                self._cat_cb.addItem("All Categories")
                for c in cats: self._cat_cb.addItem(c)
                idx=self._cat_cb.findText(cur)
                if idx>=0: self._cat_cb.setCurrentIndex(idx)
                self._cat_cb.blockSignals(False)
            finally: s.close()
            self._filter()
        except Exception as exc: log.error("Inventory refresh: %s",exc)

    @staticmethod
    def _to_dict(item):
        d=item.to_dict(); d["image_path"]=getattr(item,"image_path",None) or ""
        d["updated_at"]=item.updated_at.isoformat() if item.updated_at else ""; return d

    def _sorted(self,items):
        opt=self._sort_cb.currentText()
        if   opt=="Name A→Z":     return sorted(items,key=lambda x:x["name"].lower())
        elif opt=="Name Z→A":     return sorted(items,key=lambda x:x["name"].lower(),reverse=True)
        elif opt=="Qty ↑":        return sorted(items,key=lambda x:x["quantity"])
        elif opt=="Qty ↓":        return sorted(items,key=lambda x:x["quantity"],reverse=True)
        elif opt=="Category":     return sorted(items,key=lambda x:x["category"].lower())
        elif opt=="Last Updated": return sorted(items,key=lambda x:x.get("updated_at",""),reverse=True)
        return items

    def _filter(self):
        try:
            q=self._search.text().lower().strip(); cat=self._cat_cb.currentText(); low=self._low_btn.isChecked()
            filtered=[i for i in self._all
                if (not q or q in i["name"].lower() or q in (i.get("description") or "").lower()
                    or q in (i.get("location") or "").lower() or q in (i.get("category") or "").lower())
                and (cat=="All Categories" or i["category"]==cat) and (not low or i["is_low"])]
            filtered=self._sorted(filtered)
            n=len(filtered); low_n=sum(1 for i in filtered if i["is_low"])
            self._cnt.setText(f"{n} item{'s' if n!=1 else ''}" + (f" · {low_n} low" if low_n else ""))
            self._stats.update_stats(filtered); self._cached_filtered=filtered
            if self._grid_view: self._render_grid(filtered)
            else: self._render_table(filtered)
        except Exception as exc: log.error("Filter: %s",exc)

    def _render_grid(self,items):
        while self._grid.count():
            w=self._grid.takeAt(0).widget()
            if w: w.deleteLater()
        if not items: return
        vw=self._scroll.viewport().width(); avail=(vw if vw>100 else self.width())-D.SP_6*2
        cols=max(1,avail//(_CARD_W+D.SP_4)); self._last_cols=cols
        for idx,data in enumerate(items):
            card=_Card(data,self._sel_mode,self._gc)
            card.sig_edit.connect(self._edit_by_id); card.sig_delete.connect(self._del)
            card.sig_adjust.connect(self._adj); card.sig_select.connect(self._on_select)
            card.sig_open.connect(self._open_panel)
            if data["id"] in self._selected: card._selected=True
            row,col=divmod(idx,cols); self._grid.addWidget(card,row,col)
        self._grid.setColumnStretch(cols,1)

    def _render_table(self,items):
        self._table.setRowCount(0)
        for item in items:
            row=self._table.rowCount(); self._table.insertRow(row)
            lo=item["is_low"]; ts=item.get("updated_at","")[:10]
            status="⚠ LOW" if lo else ("✗ OUT" if item["quantity"]==0 else "✓ OK")
            for col,val in enumerate([item["name"],str(item["quantity"]),item["unit"],
                                       item["category"],item.get("location",""),status,ts]):
                cell=QTableWidgetItem(val or ""); cell.setData(Qt.ItemDataRole.UserRole,item["id"])
                if col==5:
                    cm={"⚠ LOW":D.COLOR_WRN,"✗ OUT":D.COLOR_ERR,"✓ OK":D.COLOR_OK}
                    cell.setForeground(QColor(cm.get(status,D.COLOR_TXT)))
                self._table.setItem(row,col,cell)

    def _toggle_view(self):
        self._grid_view=not self._grid_view
        if self._grid_view: self._scroll.show(); self._table.hide(); self._view_btn.setText("☰  List")
        else: self._scroll.hide(); self._table.show(); self._view_btn.setText("⊞  Grid")
        self._filter()

    def _toggle_select(self,on):
        self._sel_mode=on; self._selected.clear(); self._bulk_bar.setVisible(on)
        self._sel_lbl.setText("0 selected")
        for i in range(self._grid.count()):
            w=self._grid.itemAt(i).widget()
            if isinstance(w,_Card): w.set_select_mode(on)

    def _on_select(self,iid,checked):
        if checked: self._selected.add(iid)
        else: self._selected.discard(iid)
        self._sel_lbl.setText(f"{len(self._selected)} selected")

    def _open_panel(self,iid): self._panel.load(iid); self._panel.show()
    def _close_panel(self): self._panel.hide()

    def resizeEvent(self,e):
        super().resizeEvent(e)
        if not self._grid_view: return
        vw=self._scroll.viewport().width(); avail=(vw if vw>100 else self.width())-D.SP_6*2
        new_cols=max(1,avail//(_CARD_W+D.SP_4))
        if new_cols!=self._last_cols: self._last_cols=new_cols; self._filter()

    def _add(self):
        try:
            dlg=ItemDialog(self)
            if dlg.exec()!=QDialog.DialogCode.Accepted: return
            data=dlg.get_data()
            if not data["name"]: QMessageBox.warning(self,"Required","Name is required."); return
            s=get_session()
            try:
                item=InventoryItem(name=data["name"],description=data["description"],
                    quantity=data["quantity"],unit=data["unit"],category=data["category"],
                    location=data["location"],low_threshold=data["low_threshold"])
                if hasattr(item,"image_path"): item.image_path=data.get("image_path","")
                s.add(item); s.commit(); s.refresh(item)
                if data["quantity"]>0:
                    s.add(StockLog(item_id=item.id,delta=data["quantity"],note="Initial stock")); s.commit()
            finally: s.close()
            self.refresh()
        except Exception as exc: log.error("Add: %s",exc)

    def _edit_by_id(self,iid):
        try:
            s=get_session()
            try:
                item=s.query(InventoryItem).filter_by(id=iid).first()
                if not item: return
                old_qty=item.quantity
                dlg=ItemDialog(self,item)
                if dlg.exec()!=QDialog.DialogCode.Accepted: return
                data=dlg.get_data()
                if not data["name"]: return
                for k,v in data.items():
                    if k=="image_path" and not hasattr(item,"image_path"): continue
                    setattr(item,k,v)
                s.commit()
                if data["quantity"]!=old_qty:
                    s.add(StockLog(item_id=iid,delta=data["quantity"]-old_qty,note="Edited")); s.commit()
            finally: s.close()
            self.refresh()
            if not self._panel.isHidden(): self._panel.load(iid)
        except Exception as exc: log.error("Edit: %s",exc)

    def _adj(self,iid,delta): self._adj_with_note(iid,delta,"")

    def _adj_with_note(self,iid,delta,note):
        try:
            s=get_session()
            try:
                item=s.query(InventoryItem).filter_by(id=iid).first()
                if item:
                    item.quantity=max(0,item.quantity+delta); s.commit()
                    s.add(StockLog(item_id=iid,delta=delta,note=note)); s.commit()
            finally: s.close()
            self.refresh()
            if not self._panel.isHidden(): self._panel.load(iid)
        except Exception as exc: log.error("Adj: %s",exc)

    def _del(self,iid):
        try:
            if QMessageBox.question(self,"Delete","Delete this item permanently?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes: return
            s=get_session()
            try:
                for lg in s.query(StockLog).filter_by(item_id=iid).all(): s.delete(lg)
                item=s.query(InventoryItem).filter_by(id=iid).first()
                if item: s.delete(item)
                s.commit()
            finally: s.close()
            if not self._panel.isHidden(): self._close_panel()
            self.refresh()
        except Exception as exc: log.error("Delete: %s",exc)

    def _bulk_delete(self):
        if not self._selected: return
        n=len(self._selected)
        if QMessageBox.question(self,"Bulk Delete",f"Delete {n} item{'s' if n>1 else ''} permanently?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes: return
        s=get_session()
        try:
            for iid in list(self._selected):
                for lg in s.query(StockLog).filter_by(item_id=iid).all(): s.delete(lg)
                item=s.query(InventoryItem).filter_by(id=iid).first()
                if item: s.delete(item)
            s.commit()
        finally: s.close()
        self._selected.clear(); self._sel_btn.setChecked(False); self.refresh()

    def _export_csv(self,selected_only=False):
        try:
            items=self._cached_filtered
            if selected_only and self._selected: items=[i for i in items if i["id"] in self._selected]
            if not items: QMessageBox.information(self,"Export","No items to export."); return
            path,_=QFileDialog.getSaveFileName(self,"Export CSV","inventory.csv","CSV Files (*.csv)")
            if not path: return
            fields=["id","name","description","quantity","unit","category","location","low_threshold","is_low","image_path"]
            with open(path,"w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
                for item in items: w.writerow({k:item.get(k,"") for k in fields})
            QMessageBox.information(self,"Exported",f"Exported {len(items)} items to:\n{path}")
        except Exception as exc: log.error("CSV: %s",exc); QMessageBox.warning(self,"Failed",str(exc))

    def _table_ctx(self,pos):
        row=self._table.rowAt(pos.y())
        if row<0: return
        iid=self._table.item(row,0).data(Qt.ItemDataRole.UserRole)
        menu=QMenu(self)
        ea=menu.addAction("✎  Edit"); menu.addSeparator()
        ia=menu.addAction("＋  Add stock"); da=menu.addAction("－  Remove stock")
        menu.addSeparator(); xa=menu.addAction("🗑  Delete")
        act=menu.exec(self._table.viewport().mapToGlobal(pos))
        if   act==ea: self._edit_by_id(iid)
        elif act==ia: self._adj(iid,1)
        elif act==da: self._adj(iid,-1)
        elif act==xa: self._del(iid)