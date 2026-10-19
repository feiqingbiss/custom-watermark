import sys
import os
import copy
import math
import random
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QListWidget, 
                               QListWidgetItem, QFileDialog, QLineEdit, 
                               QSlider, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                               QGraphicsItem, QGraphicsRectItem, QFontComboBox, 
                               QFormLayout, QColorDialog, QMessageBox, QComboBox, 
                               QCheckBox, QSpinBox, QButtonGroup, QRadioButton,
                               QScrollArea, QGroupBox, QGridLayout, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QSize, QSizeF, QThread, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import (QPixmap, QIcon, QDragEnterEvent, QDropEvent, QFont, QColor, 
                           QImage, QPainter, QPen, QBrush, QPainterPath, QKeySequence, 
                           QShortcut, QFontMetrics, QCursor, QPolygonF, QImageReader)
from PIL import Image, ImageDraw, ImageFont, ImageOps

STYLE_SHEET = """
QMainWindow { background-color: #f5f6f7; }
QPushButton { background-color: #ffffff; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; padding: 2px 6px; min-height: 24px; font-size: 12px; font-family: "Microsoft YaHei"; }
QPushButton:hover { background-color: #f0f0f0; border-color: #1890ff; color: #1890ff; }
QPushButton:checked { background-color: #e6f7ff; border-color: #1890ff; color: #1890ff; }
QPushButton:disabled { background-color: #f5f5f5; color: #bbb; border-color: #d9d9d9; }
QPushButton#btn_primary { background-color: #1890ff; color: white; border: none; }
QPushButton#btn_primary:hover { background-color: #40a9ff; }
QPushButton#btn_danger { background-color: #ff4d4f; color: white; border: none; }
QPushButton#btn_danger:hover { background-color: #ff7875; }
QPushButton#btn_small { padding: 0px; font-size: 12px; border-radius: 2px; }
QLineEdit, QComboBox, QFontComboBox { border: 1px solid #d9d9d9; border-radius: 4px; padding: 2px 6px; background: white; height: 26px; font-size: 12px; font-family: "Microsoft YaHei"; }
QSpinBox { border: 1px solid #d9d9d9; border-radius: 4px; padding: 2px 6px; padding-right: 20px; background: white; height: 26px; font-size: 12px; font-family: "Microsoft YaHei"; }
QSlider::groove:horizontal { border: none; height: 4px; background: #e6f7ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #1890ff; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QListWidget { border: 1px solid #e8e8e8; background: white; border-radius: 4px; font-size: 12px; font-family: "Microsoft YaHei"; color: #333; }
QListWidget::item { padding: 4px; border-bottom: 1px solid #f0f0f0; }
QListWidget::item:hover { background-color: #f5f5f5; }
QListWidget::item:selected { background-color: #e6f7ff; color: #1890ff; border-bottom: 1px solid #e6f7ff; }
QGraphicsView { border: none; background-color: #e6e6e6; }
QGroupBox { border: 1px solid #e8e8e8; border-radius: 4px; margin-top: 16px; padding-top: 22px; font-size: 13px; font-weight: bold; color: #333; font-family: "Microsoft YaHei"; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 6px; left: 10px; top: 2px; }
QScrollArea { border: none; background: white; }
QWidget#right_panel { background: white; border-radius: 4px; }
QCheckBox { font-size: 12px; font-family: "Microsoft YaHei"; color: #333; }
QRadioButton { font-size: 12px; font-family: "Microsoft YaHei"; color: #333; }
QLabel { font-size: 12px; font-family: "Microsoft YaHei"; color: #555; }
"""


class WatermarkData:
    def __init__(self):
        self.type = 'text'
        self.text = "测试水印"
        self.font_family = "Microsoft YaHei"
        self.is_bold = False
        self.is_italic = False
        self.color = "#000000"
        self.pil_img = None

        self.opacity = 0.5
        self.size_ratio = 0.08

        self.layout_mode = 'single'
        self.x_ratio = 0.5
        self.y_ratio = 0.5
        self.rotation = 0

        self.tile_x = 0
        self.tile_y = 0
        self.tile_spacing = 0.05
        # 平铺整体偏移（比例，模 step_x/step_y 回绕）
        self.tile_offset_x = 0.0
        self.tile_offset_y = 0.0

        self.random_count = 5
        # 随机整体偏移（比例，模 bg_w/bg_h 回绕）
        self.random_offset_x = 0.0
        self.random_offset_y = 0.0
        self.random_seed = 42

        self.border_enable = False
        self.border_color = "#ffffff"
        self.border_width = 2
        self.shadow_enable = False

        self.mask_shape = 'none'
        self.mask_rects = []


class SmartWatermarkItem(QGraphicsItem):
    def __init__(self, data, bg_width, bg_height):
        super().__init__()
        self.data = data
        self.bg_w = bg_width
        self.bg_h = bg_height

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.action_mode = None
        self.hs = 32
        self.el_rect = QRectF()
        self._text_pad = 6
        self._cached_pixmap = None
        self._cache_key = None
        self.update_content()

    def _view_scale(self):
        if self.scene():
            views = self.scene().views()
            if views:
                scale = abs(views[0].transform().m11())
                return scale if scale > 0.001 else 1.0
        return 1.0

    def _rebuild_pixmap_cache(self):
        try:
            pil_img = self.data.pil_img
            if pil_img is None:
                self._cached_pixmap = None
                return
            if pil_img.mode != "RGBA":
                pil_img = pil_img.convert("RGBA")
            else:
                pil_img = pil_img.copy()
            if self.data.border_enable:
                pil_img = ImageOps.expand(pil_img, border=self.data.border_width, fill=self.data.border_color)
            data_bytes = pil_img.tobytes("raw", "RGBA")
            qimg = QImage(data_bytes, pil_img.width, pil_img.height,
                          pil_img.width * 4, QImage.Format_RGBA8888).copy()
            self._cached_pixmap = QPixmap.fromImage(qimg)
        except Exception:
            self._cached_pixmap = None

    def update_content(self):
        self.prepareGeometryChange()
        if self.data.type == 'text':
            font = QFont(self.data.font_family)
            font.setBold(self.data.is_bold)
            font.setItalic(self.data.is_italic)
            font.setPixelSize(max(10, int(self.bg_w * self.data.size_ratio)))
            fm = QFontMetrics(font)

            br = fm.boundingRect(self.data.text)
            adv = fm.horizontalAdvance(self.data.text)
            text_w = max(br.width(), adv, 10)
            text_h = max(br.height(), fm.ascent() + fm.descent())

            pad = max(6, int(font.pixelSize() * 0.2))
            self._text_pad = pad
            self.el_rect = QRectF(0, 0, text_w + pad * 2, text_h + pad * 2)
        else:
            w = self.bg_w * self.data.size_ratio
            h = w * (self.data.pil_img.height / self.data.pil_img.width) if self.data.pil_img else w
            self.el_rect = QRectF(0, 0, w, h)

        if self.data.type == 'image' and self.data.pil_img is not None:
            key = (id(self.data.pil_img), self.data.border_enable,
                   self.data.border_width, self.data.border_color)
            if key != self._cache_key:
                self._rebuild_pixmap_cache()
                self._cache_key = key

        self.setTransformOriginPoint(self.el_rect.center())

    def boundingRect(self):
        if self.data.layout_mode == 'single':
            return self.el_rect.adjusted(-120, -120, 120, 120)
        # 平铺/随机：图案中心最远偏移约半个画布，3倍尺寸足够
        return QRectF(-self.bg_w, -self.bg_h, self.bg_w * 3, self.bg_h * 3)

    def paint(self, painter, option, widget):
        painter.save()
        try:
            if self.data.mask_rects:
                path = QPainterPath()
                path.setFillRule(Qt.WindingFill)
                has_valid_mask = False
                for r in self.data.mask_rects:
                    enabled = r[5] if len(r) > 5 else True
                    if not enabled:
                        continue
                    has_valid_mask = True
                    sx = r[0] * self.bg_w
                    sy = r[1] * self.bg_h
                    sw = r[2] * self.bg_w
                    sh = r[3] * self.bg_h
                    shape = r[4] if len(r) > 4 else 'rect'
                    if shape == 'rect':
                        path.addRect(sx, sy, sw, sh)
                    else:
                        path.addEllipse(sx, sy, sw, sh)
                if has_valid_mask:
                    try:
                        inv, _ = self.sceneTransform().inverted()
                        painter.setClipPath(inv.map(path))
                    except Exception:
                        pass

            painter.setRenderHint(QPainter.Antialiasing)
            painter.setOpacity(self.data.opacity)

            if self.data.layout_mode == 'tile':
                cols = self.data.tile_x if self.data.tile_x > 0 else max(1, int(self.bg_w / (self.el_rect.width() + self.bg_w * self.data.tile_spacing)))
                rows = self.data.tile_y if self.data.tile_y > 0 else max(1, int(self.bg_h / (self.el_rect.height() + self.bg_h * self.data.tile_spacing)))
                step_x = self.bg_w / cols
                step_y = self.bg_h / rows
                scale_factor = 1.0
                max_w = step_x * 0.8
                max_h = step_y * 0.8
                if self.el_rect.width() > max_w or self.el_rect.height() > max_h:
                    scale_factor = min(max_w / self.el_rect.width(), max_h / self.el_rect.height())

                # 整体偏移：模 step 回绕，保证铺满无缺口
                ox = (self.data.tile_offset_x * self.bg_w) % step_x
                oy = (self.data.tile_offset_y * self.bg_h) % step_y

                # 多绘一圈(-1 .. rows+1)，保证边缘连续
                for r in range(-1, rows + 1):
                    for c in range(-1, cols + 1):
                        px = c * step_x + step_x / 2 + ox
                        py = r * step_y + step_y / 2 + oy
                        # 粗略剔除完全在可视外的
                        half_w = self.el_rect.width() * scale_factor / 2 + step_x
                        half_h = self.el_rect.height() * scale_factor / 2 + step_y
                        if px < -half_w or px > self.bg_w + half_w:
                            continue
                        if py < -half_h or py > self.bg_h + half_h:
                            continue
                        painter.save()
                        painter.translate(px, py)
                        painter.rotate(self.data.rotation)
                        painter.scale(scale_factor, scale_factor)
                        painter.translate(-self.el_rect.width() / 2, -self.el_rect.height() / 2)
                        self.draw_element(painter)
                        painter.restore()

            elif self.data.layout_mode == 'random':
                seed = getattr(self.data, 'random_seed', 42)
                rng = random.Random(seed)
                ox = self.data.random_offset_x * self.bg_w
                oy = self.data.random_offset_y * self.bg_h
                for _ in range(self.data.random_count):
                    px = (rng.uniform(0, self.bg_w) + ox) % self.bg_w
                    py = (rng.uniform(0, self.bg_h) + oy) % self.bg_h
                    painter.save()
                    painter.translate(px, py)
                    painter.rotate(self.data.rotation)
                    painter.translate(-self.el_rect.width() / 2, -self.el_rect.height() / 2)
                    self.draw_element(painter)
                    painter.restore()
            else:
                self.draw_element(painter)
        finally:
            painter.restore()

        # 选中边框
        if self.isSelected():
            vs = self._view_scale()
            if self.data.layout_mode == 'single':
                hs = self.hs / vs
                rot_offset = 48 / vs
                line_w = max(1.0, 2.0 / vs)
                painter.save()
                painter.setOpacity(1.0)
                painter.setPen(QPen(QColor(24, 144, 255), line_w, Qt.SolidLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(self.el_rect)
                center = self.el_rect.center()
                rot_pt = QPointF(center.x(), self.el_rect.top() - rot_offset)
                painter.drawLine(QPointF(center.x(), self.el_rect.top()), rot_pt)
                painter.setPen(QPen(Qt.white, max(1.0, 2.0 / vs)))
                painter.setBrush(QBrush(QColor(24, 144, 255)))
                painter.drawEllipse(rot_pt, hs / 2, hs / 2)
                ar = hs * 0.3
                painter.setPen(QPen(Qt.white, max(1.0, 2.5 / vs)))
                painter.drawArc(QRectF(rot_pt.x() - ar, rot_pt.y() - ar, ar * 2, ar * 2), 45 * 16, 270 * 16)
                painter.drawLine(QPointF(rot_pt.x() + ar * 0.6, rot_pt.y() - ar),
                                 QPointF(rot_pt.x() + ar, rot_pt.y() - ar * 0.5))
                painter.drawLine(QPointF(rot_pt.x() + ar * 0.6, rot_pt.y() - ar),
                                 QPointF(rot_pt.x() + ar * 0.2, rot_pt.y() - ar * 0.8))
                scale_pt = self.el_rect.bottomRight()
                painter.setPen(QPen(Qt.white, max(1.0, 2.0 / vs)))
                painter.setBrush(QBrush(QColor(24, 144, 255)))
                painter.drawEllipse(scale_pt, hs / 2, hs / 2)
                sr = hs * 0.25
                painter.setPen(QPen(Qt.white, max(1.0, 2.5 / vs)))
                painter.drawLine(QPointF(scale_pt.x() - sr, scale_pt.y() - sr),
                                 QPointF(scale_pt.x() + sr, scale_pt.y() + sr))
                painter.drawLine(QPointF(scale_pt.x() - sr, scale_pt.y() - sr),
                                 QPointF(scale_pt.x() - sr + 4 / vs, scale_pt.y() - sr))
                painter.drawLine(QPointF(scale_pt.x() - sr, scale_pt.y() - sr),
                                 QPointF(scale_pt.x() - sr, scale_pt.y() - sr + 4 / vs))
                painter.drawLine(QPointF(scale_pt.x() + sr, scale_pt.y() + sr),
                                 QPointF(scale_pt.x() + sr - 4 / vs, scale_pt.y() + sr))
                painter.drawLine(QPointF(scale_pt.x() + sr, scale_pt.y() + sr),
                                 QPointF(scale_pt.x() + sr, scale_pt.y() + sr - 4 / vs))
                painter.restore()
            else:
                # 平铺/随机：虚线框整幅，指示可拖动
                painter.save()
                painter.setOpacity(0.7)
                painter.setPen(QPen(QColor(24, 144, 255), max(1.0, 2.0 / vs), Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(QRectF(0, 0, self.bg_w, self.bg_h))
                painter.restore()

    def draw_element(self, painter):
        if self.data.shadow_enable:
            painter.save()
            painter.translate(3, 3)
            self.draw_core(painter, is_shadow=True)
            painter.restore()
        self.draw_core(painter)

    def draw_core(self, painter, is_shadow=False):
        color = QColor(0, 0, 0, 150) if is_shadow else QColor(self.data.color)

        if self.data.type == 'text':
            font = QFont(self.data.font_family)
            font.setBold(self.data.is_bold)
            font.setItalic(self.data.is_italic)
            font.setPixelSize(max(10, int(self.bg_w * self.data.size_ratio)))
            painter.setFont(font)

            if self.data.border_enable and not is_shadow:
                fm = QFontMetrics(font)
                pad = self._text_pad
                adv = fm.horizontalAdvance(self.data.text)
                text_h = fm.ascent() + fm.descent()
                baseline_x = pad + (self.el_rect.width() - 2 * pad - adv) / 2.0
                baseline_y = pad + (self.el_rect.height() - 2 * pad - text_h) / 2.0 + fm.ascent()
                path = QPainterPath()
                path.addText(baseline_x, baseline_y, font, self.data.text)
                painter.setPen(QPen(QColor(self.data.border_color), self.data.border_width))
                painter.setBrush(QColor(self.data.color))
                painter.drawPath(path)
            else:
                painter.setPen(color)
                painter.drawText(self.el_rect, Qt.AlignCenter, self.data.text)
        else:
            if self.data.type == 'image' and self._cached_pixmap is not None:
                painter.drawPixmap(self.el_rect.toRect(), self._cached_pixmap)

    def get_handles(self):
        vs = self._view_scale()
        rot_offset = 48 / vs
        trans = self.sceneTransform()
        rot_pt = trans.map(QPointF(self.el_rect.center().x(), self.el_rect.top() - rot_offset))
        scale_pt = trans.map(self.el_rect.bottomRight())
        return rot_pt, scale_pt

    def hoverMoveEvent(self, event):
        views = self.scene().views() if self.scene() else []
        if views and getattr(views[0], 'drawing_mode', False):
            self.setCursor(Qt.CrossCursor)
            return super().hoverMoveEvent(event)
        if self.data.layout_mode == 'single':
            vs = self._view_scale()
            rot_pt, scale_pt = self.get_handles()
            pos = event.scenePos()
            hit_r = (self.hs * 0.9) / vs
            if (pos - rot_pt).manhattanLength() < hit_r:
                self.setCursor(Qt.CrossCursor)
            elif (pos - scale_pt).manhattanLength() < hit_r:
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        views = self.scene().views() if self.scene() else []
        if views and getattr(views[0], 'drawing_mode', False):
            event.ignore()
            return

        # 平铺 / 随机模式：拖动整体平移
        if self.data.layout_mode != 'single':
            self.setSelected(True)
            self.action_mode = 'pan'
            self.start_mouse_pos = event.scenePos()
            self.start_tile_ox = self.data.tile_offset_x
            self.start_tile_oy = self.data.tile_offset_y
            self.start_rand_ox = self.data.random_offset_x
            self.start_rand_oy = self.data.random_offset_y
            event.accept()
            return

        vs = self._view_scale()
        rot_pt, scale_pt = self.get_handles()
        pos = event.scenePos()
        hit_r = (self.hs * 0.9) / vs
        if (pos - rot_pt).manhattanLength() < hit_r:
            self.action_mode = 'rotate'
            center = self.mapToScene(self.transformOriginPoint())
            self.start_angle = math.degrees(math.atan2(
                event.scenePos().y() - center.y(),
                event.scenePos().x() - center.x()))
            self.start_rotation = self.rotation()
        elif (pos - scale_pt).manhattanLength() < hit_r:
            self.action_mode = 'scale'
            self.start_scale = self.scale()
            self.start_mouse_pos = event.scenePos()
        else:
            self.action_mode = 'move'
            self.start_mouse_pos = event.scenePos()
            self.origin_pos = self.pos()
        self.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event):
        views = self.scene().views() if self.scene() else []
        if views and getattr(views[0], 'drawing_mode', False):
            event.ignore()
            return

        # 平铺 / 随机模式：平移图案
        if self.data.layout_mode != 'single':
            if self.action_mode == 'pan':
                delta = event.scenePos() - self.start_mouse_pos
                if self.data.layout_mode == 'tile':
                    self.data.tile_offset_x = self.start_tile_ox + delta.x() / self.bg_w
                    self.data.tile_offset_y = self.start_tile_oy + delta.y() / self.bg_h
                else:
                    self.data.random_offset_x = self.start_rand_ox + delta.x() / self.bg_w
                    self.data.random_offset_y = self.start_rand_oy + delta.y() / self.bg_h
                self.update()
            event.accept()
            return

        if self.action_mode == 'move':
            delta = event.scenePos() - self.start_mouse_pos
            new_pos = self.origin_pos + delta
            new_center = new_pos + self.transformOriginPoint()
            cx = max(0.0, min(new_center.x(), self.bg_w))
            cy = max(0.0, min(new_center.y(), self.bg_h))
            new_pos = QPointF(cx - self.transformOriginPoint().x(),
                              cy - self.transformOriginPoint().y())
            self.setPos(new_pos)
            self.data.x_ratio = cx / self.bg_w
            self.data.y_ratio = cy / self.bg_h
        elif self.action_mode == 'rotate':
            center = self.mapToScene(self.transformOriginPoint())
            cur_angle = math.degrees(math.atan2(
                event.scenePos().y() - center.y(),
                event.scenePos().x() - center.x()))
            self.setRotation(self.start_rotation + (cur_angle - self.start_angle))
            self.data.rotation = self.rotation() % 360
        elif self.action_mode == 'scale':
            delta = event.scenePos() - self.start_mouse_pos
            factor = 1.0 + delta.x() / 200.0
            self.setScale(max(0.1, self.start_scale * factor))
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.action_mode == 'scale' and hasattr(self, 'start_scale'):
            old_center = self.mapToScene(self.transformOriginPoint())
            current_scale = self.scale()
            new_ratio = self.data.size_ratio * current_scale
            new_ratio = max(0.01, min(1.0, new_ratio))
            self.data.size_ratio = new_ratio
            self.setScale(1.0)
            self.update_content()
            new_center = self.mapToScene(self.transformOriginPoint())
            self.setPos(self.pos() + (old_center - new_center))
            center = self.mapToScene(self.transformOriginPoint())
            self.data.x_ratio = max(0.0, min(1.0, center.x() / self.bg_w))
            self.data.y_ratio = max(0.0, min(1.0, center.y() / self.bg_h))
            self.data.rotation = self.rotation() % 360
        self.action_mode = None
        event.accept()


class MaskGraphicsItem(QGraphicsRectItem):
    def __init__(self, rect, shape_type, bg_w, bg_h, confirmed=False, enabled=True):
        super().__init__(0, 0, rect.width(), rect.height())
        self.setPos(rect.topLeft())
        self.shape_type = shape_type
        self.bg_w = bg_w
        self.bg_h = bg_h
        self.confirmed = False
        self.enabled = enabled
        self.global_enabled = True
        self.setBrush(QBrush(Qt.transparent))
        self.hs = 20
        self._resizing = False
        self._moving = False
        self._confirm_timer = QTimer()
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(3000)
        self._confirm_timer.timeout.connect(self._auto_confirm)
        self.set_confirmed(confirmed)

    def stop_timer(self):
        self._confirm_timer.stop()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.update()

    def set_global_enabled(self, enabled):
        self.global_enabled = enabled
        self.update()

    def set_confirmed(self, confirmed):
        self.confirmed = confirmed
        if confirmed:
            self._confirm_timer.stop()
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.setAcceptedMouseButtons(Qt.NoButton)
            self.setAcceptHoverEvents(False)
            self.setSelected(False)
            self.unsetCursor()
            self.setZValue(50)
        else:
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.setAcceptedMouseButtons(Qt.AllButtons)
            self.setAcceptHoverEvents(True)
            self.setZValue(9999)
            self._reset_timer()
        self.update()

    def _reset_timer(self):
        if not self.confirmed:
            self._confirm_timer.start(3000)

    def _auto_confirm(self):
        if self.confirmed:
            return
        self.set_confirmed(True)
        if self.scene():
            views = self.scene().views()
            if views:
                views[0].sync_mask_data_to_model()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        is_effectively_enabled = self.enabled and self.global_enabled
        if not is_effectively_enabled:
            painter.setPen(QPen(QColor(180, 180, 180, 150), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            if self.shape_type == 'rect':
                painter.drawRect(self.rect())
            else:
                painter.drawEllipse(self.rect())
            return
        if self.confirmed:
            painter.setPen(QPen(QColor(0, 200, 0, 150), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            if self.shape_type == 'rect':
                painter.drawRect(self.rect())
            else:
                painter.drawEllipse(self.rect())
        else:
            painter.setPen(QPen(QColor(0, 255, 0), 3, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            if self.shape_type == 'rect':
                painter.drawRect(self.rect())
            else:
                painter.drawEllipse(self.rect())
            painter.setPen(QPen(Qt.white, 1))
            painter.setBrush(QBrush(QColor(0, 255, 0)))
            handle_rect = QRectF(self.rect().width() - self.hs / 2,
                                 self.rect().height() - self.hs / 2,
                                 self.hs, self.hs)
            painter.drawRect(handle_rect)
            painter.setPen(QPen(QColor(0, 255, 0), 1))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            painter.drawText(self.rect().topLeft() + QPointF(5, 18), "编辑中")

    def boundingRect(self):
        return self.rect().adjusted(-self.hs, -self.hs, self.hs, self.hs)

    def hoverMoveEvent(self, event):
        if event.pos().x() > self.rect().width() - self.hs and event.pos().y() > self.rect().height() - self.hs:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self._reset_timer()
        if event.pos().x() > self.rect().width() - self.hs and event.pos().y() > self.rect().height() - self.hs:
            self._resizing = True
            self._moving = False
        else:
            self._resizing = False
            self._moving = True
            self.drag_start_scene_pos = event.scenePos()
            self.drag_start_item_pos = self.pos()
        event.accept()

    def mouseMoveEvent(self, event):
        self._reset_timer()
        if getattr(self, '_resizing', False):
            w = max(10.0, event.pos().x())
            h = max(10.0, event.pos().y())
            max_w = max(10.0, self.bg_w - self.pos().x())
            max_h = max(10.0, self.bg_h - self.pos().y())
            self.setRect(0, 0, min(w, max_w), min(h, max_h))
        elif getattr(self, '_moving', False):
            delta = event.scenePos() - self.drag_start_scene_pos
            new_pos = self.drag_start_item_pos + delta
            nx = max(0.0, min(new_pos.x(), self.bg_w - self.rect().width()))
            ny = max(0.0, min(new_pos.y(), self.bg_h - self.rect().height()))
            self.setPos(QPointF(nx, ny))
        event.accept()

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._moving = False
        self._reset_timer()
        if self.scene():
            views = self.scene().views()
            if views:
                views[0].sync_mask_data_to_model()
        event.accept()


class CustomGraphicsView(QGraphicsView):
    files_dropped = Signal(list)
    mask_drawn = Signal(QRectF)
    mask_updated = Signal(list)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._scene = scene
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.mask_items = []
        self.drawing_mode = False
        self.start_pos = None
        self.temp_rect_item = None
        self._user_zoomed = False
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            editing = [m for m in self.mask_items if not m.confirmed]
            if editing:
                for m in editing:
                    m.set_confirmed(True)
                self.sync_mask_data_to_model()
                event.accept()
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(zoom_factor, zoom_factor)
        self._user_zoomed = True
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._user_zoomed:
            self._fit_to_view()

    def _fit_to_view(self):
        if not self._scene:
            return
        for item in self._scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.fitInView(item.boundingRect(), Qt.KeepAspectRatio)
                return

    def sync_mask_data_to_model(self, preview=False):
        rects = []
        for m_item in self.mask_items:
            scene_rect = m_item.mapRectToScene(m_item.rect())
            x1 = max(0.0, scene_rect.x()) / m_item.bg_w
            y1 = max(0.0, scene_rect.y()) / m_item.bg_h
            x2 = min(m_item.bg_w, scene_rect.right()) / m_item.bg_w
            y2 = min(m_item.bg_h, scene_rect.bottom()) / m_item.bg_h
            if x2 - x1 > 0.001 and y2 - y1 > 0.001:
                rects.append([x1, y1, x2 - x1, y2 - y1, m_item.shape_type, m_item.enabled])
        for item in self._scene.items():
            if isinstance(item, SmartWatermarkItem):
                item.data.mask_rects = copy.deepcopy(rects)
                item.update()
        if not preview:
            self.mask_updated.emit(rects)

    def mousePressEvent(self, event):
        self.setFocus()
        if self.drawing_mode and event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if isinstance(item, MaskGraphicsItem) and not item.confirmed:
                super().mousePressEvent(event)
                return
            self.start_pos = self.mapToScene(pos)
            self.temp_rect_item = QGraphicsRectItem(0, 0, 0, 0)
            self.temp_rect_item.setPos(self.start_pos)
            self.temp_rect_item.setPen(QPen(QColor(0, 255, 0), 3, Qt.SolidLine))
            self.temp_rect_item.setBrush(QBrush(QColor(0, 255, 0, 50)))
            self.temp_rect_item.setZValue(10000)
            self._scene.addItem(self.temp_rect_item)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing_mode and self.start_pos and self.temp_rect_item:
            cur_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, cur_pos).normalized()
            self.temp_rect_item.setPos(rect.topLeft())
            self.temp_rect_item.setRect(0, 0, rect.width(), rect.height())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode and self.start_pos and self.temp_rect_item:
            rect = QRectF(
                self.temp_rect_item.pos().x(),
                self.temp_rect_item.pos().y(),
                self.temp_rect_item.rect().width(),
                self.temp_rect_item.rect().height())
            self._scene.removeItem(self.temp_rect_item)
            self.temp_rect_item = None
            self.start_pos = None
            self.drawing_mode = False
            self.setCursor(Qt.ArrowCursor)
            if rect.width() > 10 and rect.height() > 10:
                self.mask_drawn.emit(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.files_dropped.emit([url.toLocalFile() for url in urls])
            event.acceptProposedAction()


class ImageProcessor:
    @staticmethod
    def apply_single_watermark_qt(qimage, wm, bg_w, bg_h):
        painter = QPainter(qimage)
        painter.setRenderHint(QPainter.Antialiasing)
        if wm.mask_rects:
            path = QPainterPath()
            path.setFillRule(Qt.WindingFill)
            has_valid_mask = False
            for r in wm.mask_rects:
                enabled = r[5] if len(r) > 5 else True
                if not enabled:
                    continue
                has_valid_mask = True
                sx, sy = r[0] * bg_w, r[1] * bg_h
                sw, sh = r[2] * bg_w, r[3] * bg_h
                shape = r[4] if len(r) > 4 else 'rect'
                if shape == 'rect':
                    path.addRect(sx, sy, sw, sh)
                else:
                    path.addEllipse(sx, sy, sw, sh)
            if has_valid_mask:
                painter.setClipPath(path)
        painter.setOpacity(wm.opacity)

        text_pad = 6
        if wm.type == 'text':
            font = QFont(wm.font_family)
            font.setBold(wm.is_bold)
            font.setItalic(wm.is_italic)
            font.setPixelSize(max(10, int(bg_w * wm.size_ratio)))
            fm = QFontMetrics(font)
            br = fm.boundingRect(wm.text)
            adv = fm.horizontalAdvance(wm.text)
            text_w = max(br.width(), adv, 10)
            text_h = max(br.height(), fm.ascent() + fm.descent())
            text_pad = max(6, int(font.pixelSize() * 0.2))
            el_rect = QRectF(0, 0, text_w + text_pad * 2, text_h + text_pad * 2)
        else:
            w = bg_w * wm.size_ratio
            h = w * (wm.pil_img.height / wm.pil_img.width) if wm.pil_img else w
            el_rect = QRectF(0, 0, w, h)

        cached_pixmap = None
        if wm.type == 'image' and wm.pil_img is not None:
            pil_img = wm.pil_img
            pil_img = pil_img.convert("RGBA") if pil_img.mode != "RGBA" else pil_img.copy()
            if wm.border_enable:
                pil_img = ImageOps.expand(pil_img, border=wm.border_width, fill=wm.border_color)
            data_bytes = pil_img.tobytes("raw", "RGBA")
            qimg_inner = QImage(data_bytes, pil_img.width, pil_img.height,
                                pil_img.width * 4, QImage.Format_RGBA8888).copy()
            cached_pixmap = QPixmap.fromImage(qimg_inner)

        def draw_core(is_shadow):
            color = QColor(0, 0, 0, 150) if is_shadow else QColor(wm.color)
            if wm.type == 'text':
                font = QFont(wm.font_family)
                font.setBold(wm.is_bold)
                font.setItalic(wm.is_italic)
                font.setPixelSize(max(10, int(bg_w * wm.size_ratio)))
                painter.setFont(font)
                if wm.border_enable and not is_shadow:
                    fm = QFontMetrics(font)
                    adv = fm.horizontalAdvance(wm.text)
                    text_h = fm.ascent() + fm.descent()
                    baseline_x = text_pad + (el_rect.width() - 2 * text_pad - adv) / 2.0
                    baseline_y = text_pad + (el_rect.height() - 2 * text_pad - text_h) / 2.0 + fm.ascent()
                    path = QPainterPath()
                    path.addText(baseline_x, baseline_y, font, wm.text)
                    painter.setPen(QPen(QColor(wm.border_color), wm.border_width))
                    painter.setBrush(QColor(wm.color))
                    painter.drawPath(path)
                else:
                    painter.setPen(color)
                    painter.drawText(el_rect, Qt.AlignCenter, wm.text)
            else:
                if cached_pixmap is not None:
                    painter.drawPixmap(el_rect.toRect(), cached_pixmap)

        def draw_element():
            if wm.shadow_enable:
                painter.save()
                painter.translate(3, 3)
                draw_core(True)
                painter.restore()
            draw_core(False)

        if wm.layout_mode == 'tile':
            cols = wm.tile_x if wm.tile_x > 0 else max(1, int(bg_w / (el_rect.width() + bg_w * wm.tile_spacing)))
            rows = wm.tile_y if wm.tile_y > 0 else max(1, int(bg_h / (el_rect.height() + bg_h * wm.tile_spacing)))
            step_x, step_y = bg_w / cols, bg_h / rows
            scale_factor = 1.0
            max_w, max_h = step_x * 0.8, step_y * 0.8
            if el_rect.width() > max_w or el_rect.height() > max_h:
                scale_factor = min(max_w / el_rect.width(), max_h / el_rect.height())

            ox = (getattr(wm, 'tile_offset_x', 0.0) * bg_w) % step_x
            oy = (getattr(wm, 'tile_offset_y', 0.0) * bg_h) % step_y

            for r in range(-1, rows + 1):
                for c in range(-1, cols + 1):
                    px = c * step_x + step_x / 2 + ox
                    py = r * step_y + step_y / 2 + oy
                    half_w = el_rect.width() * scale_factor / 2 + step_x
                    half_h = el_rect.height() * scale_factor / 2 + step_y
                    if px < -half_w or px > bg_w + half_w:
                        continue
                    if py < -half_h or py > bg_h + half_h:
                        continue
                    painter.save()
                    painter.translate(px, py)
                    painter.rotate(wm.rotation)
                    painter.scale(scale_factor, scale_factor)
                    painter.translate(-el_rect.width() / 2, -el_rect.height() / 2)
                    draw_element()
                    painter.restore()

        elif wm.layout_mode == 'random':
            rng = random.Random(getattr(wm, 'random_seed', 42))
            ox = getattr(wm, 'random_offset_x', 0.0) * bg_w
            oy = getattr(wm, 'random_offset_y', 0.0) * bg_h
            for _ in range(wm.random_count):
                px = (rng.uniform(0, bg_w) + ox) % bg_w
                py = (rng.uniform(0, bg_h) + oy) % bg_h
                painter.save()
                painter.translate(px, py)
                painter.rotate(wm.rotation)
                painter.translate(-el_rect.width() / 2, -el_rect.height() / 2)
                draw_element()
                painter.restore()
        else:
            painter.save()
            tx = max(0.0, min(1.0, wm.x_ratio)) * bg_w
            ty = max(0.0, min(1.0, wm.y_ratio)) * bg_h
            painter.translate(tx, ty)
            painter.rotate(wm.rotation)
            painter.translate(-el_rect.width() / 2, -el_rect.height() / 2)
            draw_element()
            painter.restore()
        painter.end()

    @staticmethod
    def process_image(file_path, out_path, wms):
        try:
            with Image.open(file_path) as img:
                frames = []
                for i in range(getattr(img, "n_frames", 1)):
                    img.seek(i)
                    frame = img.convert("RGBA")
                    data_bytes = frame.tobytes("raw", "RGBA")
                    qimg = QImage(data_bytes, frame.width, frame.height,
                                  frame.width * 4, QImage.Format_RGBA8888).copy()
                    for wm_orig in wms:
                        wm = copy.deepcopy(wm_orig)
                        if wm.type == 'text' and '{filename}' in wm.text:
                            wm.text = wm.text.replace('{filename}', os.path.basename(file_path))
                        ImageProcessor.apply_single_watermark_qt(qimg, wm, frame.width, frame.height)
                    qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
                    pil_img = Image.frombytes("RGBA", (qimg.width(), qimg.height()),
                                              bytes(qimg.constBits()))
                    frames.append(pil_img)
                if len(frames) > 1:
                    frames[0].save(out_path, save_all=True, append_images=frames[1:])
                else:
                    ext = os.path.splitext(out_path)[1].lower()
                    final_img = frames[0]
                    if ext in ('.jpg', '.jpeg', '.bmp'):
                        if final_img.mode == "RGBA":
                            bg = Image.new("RGB", final_img.size, (255, 255, 255))
                            bg.paste(final_img, (0, 0), final_img.split()[3])
                            final_img = bg
                        else:
                            final_img = final_img.convert("RGB")
                    final_img.save(out_path)
            return True, ""
        except Exception as e:
            return False, str(e)


class BatchWorker(QThread):
    progress = Signal(int)
    finished = Signal()

    def __init__(self, files, output_dir, wms):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.wms = wms
        self.errors = []

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        for i, file in enumerate(self.files):
            name, ext = os.path.splitext(os.path.basename(file))
            out_path = os.path.join(self.output_dir, f"{name}_wm{ext}")
            ok, err = ImageProcessor.process_image(file, out_path, self.wms)
            if not ok:
                self.errors.append(f"{os.path.basename(file)}: {err}")
            self.progress.emit(int((i + 1) / len(self.files) * 100))
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("专业图像水印工具")
        self.resize(1280, 850)
        self.setStyleSheet(STYLE_SHEET)
        self.setAcceptDrops(True)

        self.image_files = []
        self.output_dir = ""
        self.current_index = -1
        self.watermarks = []
        self.graphics_items = []
        self.bg_item = None

        self.global_mask_enabled = True
        self.global_mask_shape = 'none'
        self.global_mask_areas = []
        self._updating_selection = False
        self._pending_font = None

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(30)
        self._update_timer.timeout.connect(self._do_update_selected)

        self._thumb_hover_timer = QTimer(self)
        self._thumb_hover_timer.setSingleShot(True)
        self._thumb_hover_timer.setInterval(250)
        self._thumb_hover_timer.timeout.connect(self._apply_hover_thumb)
        self._pending_thumb_item = None

        self.init_ui()
        QShortcut(QKeySequence.Delete, self, self.delete_selected)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_selected)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_selected)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)

        top_bar = QHBoxLayout()
        self.btn_import = QPushButton("导入图片")
        self.btn_import.setObjectName("btn_primary")
        self.btn_import.clicked.connect(self.import_files)
        self.btn_output = QPushButton("输出目录")
        self.btn_output.clicked.connect(self.select_output)
        self.lbl_output = QLabel("未选择")
        self.btn_start = QPushButton("🚀 开始处理")
        self.btn_start.setObjectName("btn_primary")
        self.btn_start.clicked.connect(self.start_batch)
        top_bar.addWidget(self.btn_import)
        top_bar.addWidget(self.btn_output)
        top_bar.addWidget(self.lbl_output, 1)
        top_bar.addWidget(self.btn_start)
        main_layout.addLayout(top_bar)

        body_layout = QHBoxLayout()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.thumb_list = QListWidget()
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setFlow(QListWidget.TopToBottom)
        self.thumb_list.setWrapping(False)
        self.thumb_list.setResizeMode(QListWidget.Adjust)
        self.thumb_list.setMovement(QListWidget.Static)
        self.thumb_list.setIconSize(QSize(64, 64))
        self.thumb_list.setFixedWidth(90)
        self.thumb_list.setSpacing(2)
        self.thumb_list.itemEntered.connect(self._on_thumb_hover)
        self.thumb_list.currentRowChanged.connect(self.show_image)
        left_layout.addWidget(self.thumb_list)
        body_layout.addWidget(left_panel)

        self.scene = QGraphicsScene()
        self.view = CustomGraphicsView(self.scene)
        self.view.files_dropped.connect(self.handle_dropped_paths)
        self.view.mask_drawn.connect(self.finish_drawing_mask)
        self.view.mask_updated.connect(self.on_masks_updated)
        body_layout.addWidget(self.view, 1)

        self.right_panel = QWidget()
        self.right_panel.setObjectName("right_panel")
        self.right_panel.setMinimumWidth(320)
        self.right_panel.setMaximumWidth(400)
        self.right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        layer_ops = QHBoxLayout()
        layer_ops.addWidget(QLabel("<b>水印图层</b>"))
        self.btn_del = QPushButton("🗑 删除")
        self.btn_del.setObjectName("btn_danger")
        self.btn_del.setFixedSize(65, 26)
        self.btn_del.clicked.connect(self.delete_selected)
        layer_ops.addWidget(self.btn_del)
        layer_ops.setAlignment(Qt.AlignRight)
        right_layout.addLayout(layer_ops)

        self.wm_list = QListWidget()
        self.wm_list.setMinimumHeight(100)
        self.wm_list.setMaximumHeight(200)
        self.wm_list.currentRowChanged.connect(self.on_wm_selected)
        right_layout.addWidget(self.wm_list)

        add_layout = QHBoxLayout()
        add_layout.setSpacing(10)
        btn_add_wm = QPushButton("+ 新建文字")
        btn_add_wm.setObjectName("btn_primary")
        btn_add_wm.setFixedHeight(30)
        btn_add_wm.clicked.connect(self.add_text_wm)
        add_layout.addWidget(btn_add_wm)
        btn_add_img = QPushButton("+ 新建图片")
        btn_add_img.setObjectName("btn_primary")
        btn_add_img.setFixedHeight(30)
        btn_add_img.clicked.connect(self.add_image_wm)
        add_layout.addWidget(btn_add_img)
        right_layout.addLayout(add_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.settings_layout = QVBoxLayout(scroll_content)
        self.settings_layout.setSpacing(12)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)

        group_content = QGroupBox("内容与样式")
        form_content = QVBoxLayout(group_content)
        form_content.setSpacing(10)
        form_content.setContentsMargins(10, 10, 10, 10)
        form_content.addWidget(QLabel("文字:"))
        self.input_text = QLineEdit("测试水印")
        self.input_text.textChanged.connect(self.update_selected)
        form_content.addWidget(self.input_text)
        form_content.addWidget(QLabel("字体:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.font_combo.currentFontChanged.connect(self.update_selected)
        form_content.addWidget(self.font_combo)

        font_layout2 = QHBoxLayout()
        font_layout2.setSpacing(8)
        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedSize(36, 28)
        self.btn_bold.setStyleSheet("font-weight: bold;")
        self.btn_bold.clicked.connect(self.update_selected)
        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedSize(36, 28)
        self.btn_italic.setStyleSheet("font-style: italic;")
        self.btn_italic.clicked.connect(self.update_selected)
        self.btn_color = QPushButton("颜色")
        self.btn_color.setFixedSize(60, 28)
        self.btn_color.clicked.connect(self.choose_color)
        font_layout2.addWidget(self.btn_bold)
        font_layout2.addWidget(self.btn_italic)
        font_layout2.addWidget(self.btn_color)
        font_layout2.addStretch()
        form_content.addLayout(font_layout2)
        self.settings_layout.addWidget(group_content)

        # 排版模式
        group_layout = QGroupBox("排版模式")
        v_layout = QVBoxLayout(group_layout)
        v_layout.setSpacing(10)
        v_layout.setContentsMargins(10, 10, 10, 10)
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(20)
        self.rb_single = QRadioButton("单个")
        self.rb_tile = QRadioButton("平铺")
        self.rb_random = QRadioButton("随机")
        self.rb_single.setChecked(True)
        self.bg_mode = QButtonGroup(self)
        self.bg_mode.addButton(self.rb_single, 0)
        self.bg_mode.addButton(self.rb_tile, 1)
        self.bg_mode.addButton(self.rb_random, 2)
        self.bg_mode.buttonClicked.connect(self.on_mode_changed)
        mode_layout.addWidget(self.rb_single)
        mode_layout.addWidget(self.rb_tile)
        mode_layout.addWidget(self.rb_random)
        v_layout.addLayout(mode_layout)

        # 平铺参数
        self.tile_params_widget = QWidget()
        tile_form = QVBoxLayout(self.tile_params_widget)
        tile_form.setContentsMargins(0, 0, 0, 0)
        tile_form.setSpacing(6)
        spin_layout = QHBoxLayout()
        spin_layout.setSpacing(10)
        spin_layout.addWidget(QLabel("横:"))
        self.spin_tile_x = QSpinBox()
        self.spin_tile_x.setRange(0, 50)
        self.spin_tile_x.setSpecialValueText("自动")
        self.spin_tile_x.setFixedWidth(85)
        self.spin_tile_x.setFixedHeight(28)
        self.spin_tile_x.valueChanged.connect(self.update_selected)
        spin_layout.addWidget(self.spin_tile_x)
        spin_layout.addSpacing(15)
        spin_layout.addWidget(QLabel("竖:"))
        self.spin_tile_y = QSpinBox()
        self.spin_tile_y.setRange(0, 50)
        self.spin_tile_y.setSpecialValueText("自动")
        self.spin_tile_y.setFixedWidth(85)
        self.spin_tile_y.setFixedHeight(28)
        self.spin_tile_y.valueChanged.connect(self.update_selected)
        spin_layout.addWidget(self.spin_tile_y)
        spin_layout.addStretch()
        tile_form.addLayout(spin_layout)
        lbl_tile_tip = QLabel("💡 拖动水印可整体平移平铺网格")
        lbl_tile_tip.setStyleSheet("color: #888; font-size: 11px;")
        tile_form.addWidget(lbl_tile_tip)
        v_layout.addWidget(self.tile_params_widget)
        self.tile_params_widget.setVisible(False)

        # 随机参数
        self.random_params_widget = QWidget()
        rand_layout = QHBoxLayout(self.random_params_widget)
        rand_layout.setContentsMargins(0, 0, 0, 0)
        rand_layout.setSpacing(8)
        rand_layout.addWidget(QLabel("数量:"))
        self.spin_random_count = QSpinBox()
        self.spin_random_count.setRange(1, 100)
        self.spin_random_count.setValue(5)
        self.spin_random_count.setFixedWidth(70)
        self.spin_random_count.setFixedHeight(28)
        self.spin_random_count.valueChanged.connect(self.update_selected)
        rand_layout.addWidget(self.spin_random_count)
        self.btn_rerandom = QPushButton("🎲 重新随机")
        self.btn_rerandom.setFixedHeight(28)
        self.btn_rerandom.clicked.connect(self.on_rerandom)
        rand_layout.addWidget(self.btn_rerandom)
        rand_layout.addStretch()
        v_layout.addWidget(self.random_params_widget)
        self.random_params_widget.setVisible(False)

        lbl_rand_tip = QLabel("💡 拖动水印可整体平移随机布局")
        lbl_rand_tip.setStyleSheet("color: #888; font-size: 11px;")
        lbl_rand_tip.setVisible(False)
        self.lbl_rand_tip = lbl_rand_tip
        v_layout.addWidget(lbl_rand_tip)

        # 通用滑条
        grid_sliders = QGridLayout()
        grid_sliders.setSpacing(10)
        grid_sliders.setColumnStretch(1, 1)
        self.slider_size = self.create_slider(1, 50, 8)
        self.slider_size.valueChanged.connect(self.update_selected)
        grid_sliders.addWidget(QLabel("尺寸:"), 0, 0)
        grid_sliders.addWidget(self.slider_size, 0, 1)
        self.slider_rotation = self.create_slider(0, 360, 0)
        self.slider_rotation.valueChanged.connect(self.update_selected)
        grid_sliders.addWidget(QLabel("旋转:"), 1, 0)
        grid_sliders.addWidget(self.slider_rotation, 1, 1)
        self.slider_opacity = self.create_slider(0, 100, 50)
        self.slider_opacity.valueChanged.connect(self.update_selected)
        grid_sliders.addWidget(QLabel("透明:"), 2, 0)
        grid_sliders.addWidget(self.slider_opacity, 2, 1)
        v_layout.addLayout(grid_sliders)

        chk_layout = QHBoxLayout()
        chk_layout.setSpacing(25)
        self.chk_border = QCheckBox("边框")
        self.chk_border.clicked.connect(self.update_selected)
        self.chk_shadow = QCheckBox("阴影")
        self.chk_shadow.clicked.connect(self.update_selected)
        chk_layout.addWidget(self.chk_border)
        chk_layout.addWidget(self.chk_shadow)
        v_layout.addLayout(chk_layout)
        self.settings_layout.addWidget(group_layout)

        # 九宫格
        group_pos = QGroupBox("九宫格位置 (单个模式)")
        pos_layout = QGridLayout(group_pos)
        pos_layout.setSpacing(8)
        pos_layout.setContentsMargins(10, 10, 10, 10)
        positions = [
            ("左上", 0, 0), ("正上", 0, 1), ("右上", 0, 2),
            ("左中", 1, 0), ("正中", 1, 1), ("右中", 1, 2),
            ("左下", 2, 0), ("正下", 2, 1), ("右下", 2, 2)
        ]
        for text, i, j in positions:
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet("font-size: 12px; font-weight: normal; padding: 0px;")
            btn.clicked.connect(lambda checked, r=i, c=j: self.set_watermark_pos(r, c))
            pos_layout.addWidget(btn, i, j)
        self.settings_layout.addWidget(group_pos)

        # 区域选择
        group_mask = QGroupBox("区域选择 (限制范围)")
        form_mask = QVBoxLayout(group_mask)
        form_mask.setSpacing(10)
        form_mask.setContentsMargins(10, 10, 10, 10)
        mask_top_layout = QHBoxLayout()
        self.chk_global_mask = QCheckBox("启用区域限制")
        self.chk_global_mask.setChecked(True)
        self.chk_global_mask.setStyleSheet("font-weight: bold; color: #1890ff;")
        self.chk_global_mask.toggled.connect(self.on_global_mask_toggled)
        self.btn_clear_mask = QPushButton("清除所有")
        self.btn_clear_mask.setFixedSize(70, 28)
        self.btn_clear_mask.clicked.connect(self.clear_mask)
        mask_top_layout.addWidget(self.chk_global_mask)
        mask_top_layout.addStretch()
        mask_top_layout.addWidget(self.btn_clear_mask)
        form_mask.addLayout(mask_top_layout)
        mask_layout = QHBoxLayout()
        mask_layout.setSpacing(8)
        self.combo_mask = QComboBox()
        self.combo_mask.addItems(["不限制", "矩形区域", "圆形区域"])
        self.combo_mask.currentIndexChanged.connect(self.on_mask_shape_changed)
        self.btn_add_mask = QPushButton("添加框")
        self.btn_add_mask.setFixedSize(60, 28)
        self.btn_add_mask.clicked.connect(self.add_mask_area)
        mask_layout.addWidget(self.combo_mask, 1)
        mask_layout.addWidget(self.btn_add_mask)
        form_mask.addLayout(mask_layout)
        self.mask_list = QListWidget()
        self.mask_list.setMinimumHeight(120)
        self.mask_list.setMaximumHeight(200)
        form_mask.addWidget(self.mask_list)
        self.lbl_mask_tip = QLabel("提示: 勾选框控制区域是否生效。新框 3 秒无操作或回车后自动固定。")
        self.lbl_mask_tip.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_mask_tip.setWordWrap(True)
        form_mask.addWidget(self.lbl_mask_tip)
        self.settings_layout.addWidget(group_mask)
        self.settings_layout.addStretch()

        scroll.setWidget(scroll_content)
        right_layout.addWidget(scroll, 1)
        body_layout.addWidget(self.right_panel)
        main_layout.addLayout(body_layout)

    def create_slider(self, min_val, max_val, default_val):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_val, max_val)
        s.setValue(default_val)
        return s

    def _load_thumbnail(self, path, size=64):
        try:
            reader = QImageReader(path)
            if not reader.canRead():
                return QIcon()
            orig = reader.size()
            if orig.isValid() and orig.width() > 0 and orig.height() > 0:
                reader.setScaledSize(orig.scaled(size, size, Qt.KeepAspectRatio))
            img = reader.read()
            if img.isNull():
                pm = QPixmap(path)
                if pm.isNull():
                    return QIcon()
                pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return QIcon(pm)
            return QIcon(QPixmap.fromImage(img))
        except Exception:
            return QIcon()

    def _on_thumb_hover(self, item):
        if item is None:
            return
        self._pending_thumb_item = item
        if not self._thumb_hover_timer.isActive():
            self._thumb_hover_timer.start()

    def _apply_hover_thumb(self):
        item = self._pending_thumb_item
        if item is not None and self.thumb_list.currentItem() is not item:
            self.thumb_list.setCurrentItem(item)

    def _format_wm_name(self, wm, index):
        if wm.type == 'text':
            text = wm.text if wm.text else "(空)"
            if len(text) > 16:
                text = text[:15] + "…"
            return f"{index+1}. 文字: {text}"
        return f"{index+1}. 图片"

    def on_scene_selection_changed(self):
        if self._updating_selection:
            return
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], SmartWatermarkItem):
            try:
                idx = self.graphics_items.index(selected[0])
            except ValueError:
                return
            if self.wm_list.currentRow() != idx:
                self._updating_selection = True
                self.wm_list.setCurrentRow(idx)
                self.update_ui_from_wm(self.watermarks[idx])
                self._updating_selection = False

    def handle_dropped_paths(self, paths):
        files = []
        for path in paths:
            if os.path.isdir(path):
                for root, _, fs in os.walk(path):
                    for f in fs:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')):
                            files.append(os.path.join(root, f))
            elif path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')):
                files.append(path)
        if files:
            self.load_files(files)

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "Images (*.jpg *.png *.bmp *.tif *.tiff *.webp)")
        if files:
            self.load_files(files)

    def load_files(self, new_files):
        existing = set(self.image_files)
        added = []
        for f in new_files:
            if f not in existing:
                self.image_files.append(f)
                existing.add(f)
                added.append(f)
        if added:
            self.thumb_list.blockSignals(True)
            base_idx = len(self.image_files) - len(added)
            for i, f in enumerate(added):
                item = QListWidgetItem()
                item.setIcon(self._load_thumbnail(f, 64))
                item.setData(Qt.UserRole, base_idx + i)
                item.setToolTip(os.path.basename(f))
                self.thumb_list.addItem(item)
            self.thumb_list.blockSignals(False)
        if self.image_files:
            if self.current_index < 0 or self.current_index >= len(self.image_files):
                self.current_index = 0
            self.thumb_list.setCurrentRow(self.current_index)

    def show_image(self, index):
        if index < 0 or index >= len(self.image_files):
            return
        self.current_index = index
        self.refresh_scene()

    def copy_selected(self):
        row = self.wm_list.currentRow()
        if 0 <= row < len(self.watermarks):
            self.clipboard_wm = copy.deepcopy(self.watermarks[row])

    def paste_selected(self):
        if hasattr(self, 'clipboard_wm') and self.clipboard_wm:
            new_wm = copy.deepcopy(self.clipboard_wm)
            self.watermarks.append(new_wm)
            self.refresh_scene(len(self.watermarks) - 1)

    def delete_selected(self):
        row = self.wm_list.currentRow()
        if 0 <= row < len(self.watermarks):
            self.watermarks.pop(row)
            self.refresh_scene()

    def add_text_wm(self):
        if not self.bg_item:
            return
        wm = WatermarkData()
        wm.mask_shape = self.global_mask_shape
        wm.mask_rects = copy.deepcopy(self.global_mask_areas)
        self.watermarks.append(wm)
        self.refresh_scene(len(self.watermarks) - 1)

    def add_image_wm(self):
        if not self.bg_item:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not file_path:
            return
        try:
            img = Image.open(file_path).convert("RGBA")
            wm = WatermarkData()
            wm.type = 'image'
            wm.pil_img = img
            wm.mask_shape = self.global_mask_shape
            wm.mask_rects = copy.deepcopy(self.global_mask_areas)
            self.watermarks.append(wm)
            self.refresh_scene(len(self.watermarks) - 1)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法加载图片: {e}")

    def choose_color(self):
        row = self.wm_list.currentRow()
        if row < 0 or row >= len(self.watermarks):
            return
        color = QColorDialog.getColor(QColor(self.watermarks[row].color), self, "选择颜色")
        if color.isValid():
            self.watermarks[row].color = color.name()
            text_color = "white" if color.lightness() < 128 else "black"
            self.btn_color.setStyleSheet(
                f"background-color: {color.name()}; color: {text_color}; border: 1px solid #999;")
            self.update_selected()
            self.view.viewport().update()

    def on_mode_changed(self, btn):
        row = self.wm_list.currentRow()
        if row >= 0 and row < len(self.watermarks):
            wm = self.watermarks[row]
            if btn == self.rb_single:
                wm.layout_mode = 'single'
            elif btn == self.rb_tile:
                wm.layout_mode = 'tile'
            else:
                wm.layout_mode = 'random'

            self.tile_params_widget.setVisible(btn == self.rb_tile)
            self.random_params_widget.setVisible(btn == self.rb_random)
            self.lbl_rand_tip.setVisible(btn == self.rb_random)

            if row < len(self.graphics_items):
                g_item = self.graphics_items[row]
                if wm.layout_mode == 'single':
                    bg_rect = self.bg_item.boundingRect()
                    target_x = wm.x_ratio * bg_rect.width()
                    target_y = wm.y_ratio * bg_rect.height()
                    g_item.setPos(target_x - g_item.transformOriginPoint().x(),
                                  target_y - g_item.transformOriginPoint().y())
                    g_item.setRotation(wm.rotation)
                else:
                    g_item.setPos(0, 0)
                    g_item.setRotation(0)
                g_item.update()
            self.view.viewport().update()

    def on_rerandom(self):
        row = self.wm_list.currentRow()
        if row < 0 or row >= len(self.watermarks):
            return
        wm = self.watermarks[row]
        wm.random_seed = random.randint(0, 999999)
        if row < len(self.graphics_items):
            self.graphics_items[row].update()
        self.view.viewport().update()

    def set_watermark_pos(self, r, c):
        row = self.wm_list.currentRow()
        if row < 0 or row >= len(self.watermarks):
            return
        wm = self.watermarks[row]
        wm.x_ratio = (c + 0.5) / 3.0
        wm.y_ratio = (r + 0.5) / 3.0
        if row < len(self.graphics_items):
            g_item = self.graphics_items[row]
            bg_rect = self.bg_item.boundingRect()
            g_item.setPos(wm.x_ratio * bg_rect.width() - g_item.transformOriginPoint().x(),
                          wm.y_ratio * bg_rect.height() - g_item.transformOriginPoint().y())
            g_item.update()
            self.view.viewport().update()

    def on_global_mask_toggled(self, checked):
        self.global_mask_enabled = checked
        self.sync_masks_to_watermarks()
        for m in self.view.mask_items:
            m.set_global_enabled(checked)
        for g in self.graphics_items:
            g.update()
        self.view.viewport().update()
        self._refresh_mask_list()

    def sync_masks_to_watermarks(self):
        for wm in self.watermarks:
            wm.mask_shape = self.global_mask_shape if self.global_mask_enabled else 'none'
            wm.mask_rects = copy.deepcopy(self.global_mask_areas) if self.global_mask_enabled else []

    def on_masks_updated(self, rects):
        if rects == self.global_mask_areas:
            self._refresh_mask_list()
            return
        self.global_mask_areas = copy.deepcopy(rects)
        self.sync_masks_to_watermarks()
        self._refresh_mask_list()

    def _refresh_mask_list(self):
        current_row = self.mask_list.currentRow()
        self.mask_list.blockSignals(True)
        self.mask_list.clear()
        for i, m in enumerate(self.view.mask_items):
            row_widget = QWidget()
            h = QHBoxLayout(row_widget)
            h.setContentsMargins(6, 8, 6, 8)
            h.setSpacing(6)
            chk = QCheckBox()
            chk.setChecked(m.enabled)
            chk.setEnabled(self.global_mask_enabled)
            chk.stateChanged.connect(lambda state, idx=i: self.toggle_mask_enabled(idx, state == Qt.CheckState.Checked.value))
            shape_name = '矩形' if m.shape_type == 'rect' else '圆形'
            status = '已确认' if m.confirmed else '编辑中'
            lbl = QLabel(f"{i+1}. {shape_name} - {status}")
            lbl.setStyleSheet("font-size: 12px;")
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn_confirm = QPushButton("确认")
            btn_confirm.setObjectName("btn_small")
            btn_confirm.setFixedSize(56, 26)
            btn_confirm.clicked.connect(lambda checked=False, idx=i: self.confirm_mask(idx))
            btn_confirm.setEnabled(not m.confirmed)
            btn_edit = QPushButton("编辑")
            btn_edit.setObjectName("btn_small")
            btn_edit.setFixedSize(56, 26)
            btn_edit.clicked.connect(lambda checked=False, idx=i: self.edit_mask(idx))
            btn_edit.setEnabled(m.confirmed)
            h.addWidget(chk)
            h.addWidget(lbl, 1)
            h.addWidget(btn_confirm)
            h.addWidget(btn_edit)
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 46))
            self.mask_list.addItem(list_item)
            self.mask_list.setItemWidget(list_item, row_widget)
        self.mask_list.blockSignals(False)
        if 0 <= current_row < self.mask_list.count():
            self.mask_list.setCurrentRow(current_row)

    def toggle_mask_enabled(self, idx, enabled):
        if 0 <= idx < len(self.view.mask_items):
            self.view.mask_items[idx].set_enabled(enabled)
            self.view.sync_mask_data_to_model()
            self._refresh_mask_list()

    def confirm_mask(self, idx):
        if 0 <= idx < len(self.view.mask_items):
            self.view.mask_items[idx].set_confirmed(True)
            self.view.sync_mask_data_to_model()
            self._refresh_mask_list()

    def edit_mask(self, idx):
        if 0 <= idx < len(self.view.mask_items):
            for i, m in enumerate(self.view.mask_items):
                if i != idx and not m.confirmed:
                    m.set_confirmed(True)
            self.view.mask_items[idx].set_confirmed(False)
            self._refresh_mask_list()

    def clear_mask(self):
        for m in self.view.mask_items:
            m.stop_timer()
        self.view.mask_items.clear()
        self.global_mask_areas = []
        self.global_mask_shape = 'none'
        self.combo_mask.blockSignals(True)
        self.combo_mask.setCurrentIndex(0)
        self.combo_mask.blockSignals(False)
        self.view.drawing_mode = False
        self.view.setCursor(Qt.ArrowCursor)
        self.sync_masks_to_watermarks()
        self.refresh_scene(self.wm_list.currentRow())

    def add_mask_area(self):
        if not self.watermarks:
            QMessageBox.information(self, "提示", "请先添加一个水印图层。")
            return
        if not self.global_mask_enabled:
            self.chk_global_mask.setChecked(True)
        if self.global_mask_shape == 'none':
            self.global_mask_shape = 'rect'
            self.combo_mask.blockSignals(True)
            self.combo_mask.setCurrentIndex(1)
            self.combo_mask.blockSignals(False)
        for m in self.view.mask_items:
            if not m.confirmed:
                m.set_confirmed(True)
        self.view.sync_mask_data_to_model()
        self.view.drawing_mode = True
        self.view.setCursor(Qt.CrossCursor)
        self.view.setFocus()
        self._refresh_mask_list()

    def on_mask_shape_changed(self, *args):
        shape_map = {0: 'none', 1: 'rect', 2: 'ellipse'}
        new_shape = shape_map[self.combo_mask.currentIndex()]
        self.global_mask_shape = new_shape
        if new_shape == 'none':
            self.clear_mask()
            return
        changed = False
        for m in self.view.mask_items:
            if not m.confirmed:
                m.shape_type = new_shape
                m.update()
                changed = True
        if changed:
            self.view.sync_mask_data_to_model()
            self._refresh_mask_list()

    def finish_drawing_mask(self, rect):
        if not self.bg_item:
            return
        bg_rect = self.bg_item.boundingRect()
        x = max(0.0, min(rect.x(), bg_rect.width() - 1))
        y = max(0.0, min(rect.y(), bg_rect.height() - 1))
        x2 = max(0.0, min(rect.x() + rect.width(), bg_rect.width()))
        y2 = max(0.0, min(rect.y() + rect.height(), bg_rect.height()))
        w, h = x2 - x, y2 - y
        if w < 10 or h < 10:
            return
        shape = self.global_mask_shape
        if shape == 'none':
            shape = 'rect'
            self.global_mask_shape = 'rect'
            self.combo_mask.blockSignals(True)
            self.combo_mask.setCurrentIndex(1)
            self.combo_mask.blockSignals(False)
        for m in self.view.mask_items:
            if not m.confirmed:
                m.set_confirmed(True)
        mask_item = MaskGraphicsItem(QRectF(x, y, w, h), shape,
                                     bg_rect.width(), bg_rect.height(),
                                     confirmed=False, enabled=True)
        mask_item.set_global_enabled(self.global_mask_enabled)
        mask_item.setZValue(9999)
        self.scene.addItem(mask_item)
        self.view.mask_items.append(mask_item)
        self.view.drawing_mode = False
        self.view.setCursor(Qt.ArrowCursor)
        self.view.sync_mask_data_to_model()
        self._refresh_mask_list()

    def update_ui_from_wm(self, wm):
        widgets = [self.input_text, self.font_combo, self.btn_bold, self.btn_italic,
                   self.slider_size, self.slider_rotation, self.slider_opacity,
                   self.chk_border, self.chk_shadow, self.rb_single, self.rb_tile,
                   self.rb_random, self.spin_tile_x, self.spin_tile_y, self.combo_mask,
                   self.spin_random_count]
        for w in widgets:
            w.blockSignals(True)
        self.input_text.setText(wm.text)
        self.font_combo.setCurrentFont(QFont(wm.font_family))
        self.btn_bold.setChecked(wm.is_bold)
        self.btn_italic.setChecked(wm.is_italic)
        text_color = "white" if QColor(wm.color).lightness() < 128 else "black"
        self.btn_color.setStyleSheet(
            f"background-color: {wm.color}; color: {text_color}; border: 1px solid #999;")
        self.slider_size.setValue(int(wm.size_ratio * 100))
        self.slider_rotation.setValue(int(wm.rotation))
        self.slider_opacity.setValue(int(wm.opacity * 100))
        self.chk_border.setChecked(wm.border_enable)
        self.chk_shadow.setChecked(wm.shadow_enable)
        if wm.layout_mode == 'single':
            self.rb_single.setChecked(True)
            self.tile_params_widget.setVisible(False)
            self.random_params_widget.setVisible(False)
            self.lbl_rand_tip.setVisible(False)
        elif wm.layout_mode == 'tile':
            self.rb_tile.setChecked(True)
            self.tile_params_widget.setVisible(True)
            self.random_params_widget.setVisible(False)
            self.lbl_rand_tip.setVisible(False)
        else:
            self.rb_random.setChecked(True)
            self.tile_params_widget.setVisible(False)
            self.random_params_widget.setVisible(True)
            self.lbl_rand_tip.setVisible(True)
        self.spin_tile_x.setValue(wm.tile_x)
        self.spin_tile_y.setValue(wm.tile_y)
        self.spin_random_count.setValue(wm.random_count)
        shape_to_index = {'none': 0, 'rect': 1, 'ellipse': 2}
        self.combo_mask.setCurrentIndex(shape_to_index.get(self.global_mask_shape, 0))
        for w in widgets:
            w.blockSignals(False)
        self.view.drawing_mode = False
        self.view.setCursor(Qt.ArrowCursor)

    def on_wm_selected(self, row):
        # 切换水印时清掉未执行的节流更新，避免把旧值写到新水印
        self._update_timer.stop()
        self._pending_font = None
        if row < 0 or row >= len(self.watermarks):
            return
        wm = self.watermarks[row]
        if getattr(self, '_updating_selection', False):
            self.update_ui_from_wm(wm)
            return
        self._updating_selection = True
        self.scene.clearSelection()
        if row < len(self.graphics_items):
            self.graphics_items[row].setSelected(True)
        self.update_ui_from_wm(wm)
        self._updating_selection = False

    def update_selected(self, *args):
        if args and isinstance(args[0], QFont):
            self._pending_font = args[0]
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _do_update_selected(self):
        try:
            row = self.wm_list.currentRow()
            if row < 0 or row >= len(self.watermarks) or not self.bg_item:
                return
            wm = self.watermarks[row]
            wm.text = self.input_text.text()
            if self._pending_font is not None:
                wm.font_family = self._pending_font.family()
                self._pending_font = None
            else:
                wm.font_family = self.font_combo.currentFont().family()
            wm.is_bold = self.btn_bold.isChecked()
            wm.is_italic = self.btn_italic.isChecked()
            wm.size_ratio = self.slider_size.value() / 100.0
            wm.rotation = self.slider_rotation.value()
            wm.opacity = self.slider_opacity.value() / 100.0
            wm.border_enable = self.chk_border.isChecked()
            wm.shadow_enable = self.chk_shadow.isChecked()
            wm.tile_x = self.spin_tile_x.value()
            wm.tile_y = self.spin_tile_y.value()
            wm.random_count = self.spin_random_count.value()
            if row < len(self.graphics_items):
                g_item = self.graphics_items[row]
                old_center = g_item.mapToScene(g_item.transformOriginPoint())
                g_item.update_content()
                if wm.layout_mode == 'single':
                    new_center = g_item.mapToScene(g_item.transformOriginPoint())
                    g_item.setPos(g_item.pos() + (old_center - new_center))
                    bg_rect = self.bg_item.boundingRect()
                    center = g_item.mapToScene(g_item.transformOriginPoint())
                    cx = max(0.0, min(1.0, center.x() / bg_rect.width())) * bg_rect.width()
                    cy = max(0.0, min(1.0, center.y() / bg_rect.height())) * bg_rect.height()
                    wm.x_ratio = cx / bg_rect.width()
                    wm.y_ratio = cy / bg_rect.height()
                    if abs(cx - center.x()) > 0.5 or abs(cy - center.y()) > 0.5:
                        g_item.setPos(g_item.pos() + QPointF(cx - center.x(), cy - center.y()))
                    g_item.setRotation(wm.rotation)
                else:
                    g_item.setPos(0, 0)
                    g_item.setRotation(0)
                g_item.update()
            if row < self.wm_list.count():
                item = self.wm_list.item(row)
                new_text = self._format_wm_name(wm, row)
                if item.text() != new_text:
                    item.setText(new_text)
            self.view.viewport().update()
        except Exception as e:
            import traceback
            print(f"[_do_update_selected] 异常: {e}")
            traceback.print_exc()

    def refresh_scene(self, select_row=None):
        if self.current_index < 0 or self.current_index >= len(self.image_files):
            return
        self._updating_selection = True
        if self.view.temp_rect_item is not None:
            try:
                self.scene.removeItem(self.view.temp_rect_item)
            except Exception:
                pass
            self.view.temp_rect_item = None
        self.view.start_pos = None
        for m in self.view.mask_items:
            m.stop_timer()
        self.view.mask_items.clear()
        self.scene.clear()
        self.graphics_items.clear()

        pixmap = QPixmap(self.image_files[self.current_index])
        self.bg_item = QGraphicsPixmapItem(pixmap)
        self.bg_item.setZValue(-100)
        self.bg_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.bg_item)

        self.wm_list.blockSignals(True)
        self.wm_list.clear()
        for i, wm in enumerate(self.watermarks):
            item = QListWidgetItem(self._format_wm_name(wm, i))
            item.setSizeHint(QSize(0, 36))
            self.wm_list.addItem(item)
        self.wm_list.blockSignals(False)

        bg_rect = self.bg_item.boundingRect()
        if self.global_mask_areas:
            for area in self.global_mask_areas:
                mx, my, mw, mh = area[:4]
                shape = area[4] if len(area) > 4 else ('rect' if self.global_mask_shape == 'none' else self.global_mask_shape)
                enabled = area[5] if len(area) > 5 else True
                rect = QRectF(mx * bg_rect.width(), my * bg_rect.height(),
                              mw * bg_rect.width(), mh * bg_rect.height())
                mask_item = MaskGraphicsItem(rect, shape,
                                             bg_rect.width(), bg_rect.height(),
                                             confirmed=True, enabled=enabled)
                mask_item.set_global_enabled(self.global_mask_enabled)
                self.scene.addItem(mask_item)
                self.view.mask_items.append(mask_item)

        for wm in self.watermarks:
            g_item = SmartWatermarkItem(wm, bg_rect.width(), bg_rect.height())
            g_item.setZValue(100)
            if wm.layout_mode == 'single':
                xr = max(0.0, min(1.0, wm.x_ratio))
                yr = max(0.0, min(1.0, wm.y_ratio))
                wm.x_ratio, wm.y_ratio = xr, yr
                g_item.setPos(xr * bg_rect.width() - g_item.transformOriginPoint().x(),
                              yr * bg_rect.height() - g_item.transformOriginPoint().y())
                g_item.setRotation(wm.rotation)
            self.scene.addItem(g_item)
            self.graphics_items.append(g_item)

        padding = 1000
        self.scene.setSceneRect(bg_rect.adjusted(-padding, -padding, padding, padding))
        self.view.fitInView(bg_rect, Qt.KeepAspectRatio)
        self.view._user_zoomed = False
        self._refresh_mask_list()
        self._updating_selection = False

        if select_row is not None and 0 <= select_row < self.wm_list.count():
            self.wm_list.setCurrentRow(select_row)
        elif self.watermarks:
            self.wm_list.setCurrentRow(0)

    def select_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir = dir_path
            self.lbl_output.setText(f"输出目录: {dir_path}")

    def start_batch(self):
        if not self.image_files:
            QMessageBox.warning(self, "提示", "请先导入图片！")
            return
        if not self.output_dir:
            QMessageBox.information(self, "提示", "请先选择图片输出目录。")
            self.select_output()
            if not self.output_dir:
                return
        if not self.watermarks:
            QMessageBox.warning(self, "提示", "请至少添加一个水印图层！")
            return
        self.btn_start.setText("处理中...")
        self.btn_start.setEnabled(False)
        self.worker = BatchWorker(self.image_files, self.output_dir, self.watermarks)
        self.worker.progress.connect(lambda v: self.btn_start.setText(f"处理中... {v}%"))
        self.worker.finished.connect(self.batch_finished)
        self.worker.start()

    def batch_finished(self):
        self.btn_start.setText("🚀 开始处理")
        self.btn_start.setEnabled(True)
        errors = getattr(self.worker, 'errors', [])
        if errors:
            msg = "批量处理完成，但部分文件失败：\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... 共 {len(errors)} 个错误"
            QMessageBox.warning(self, "完成（有错误）", msg)
        else:
            QMessageBox.information(self, "完成", "批量水印处理完成！")


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
