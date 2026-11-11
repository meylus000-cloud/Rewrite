from __future__ import annotations
import json
import sys
import random
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QAction, QPixmap, QPainter, QIcon, QImage
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon, QStyle
)

BASE = Path(__file__).resolve().parent
RESOURCE = Path(getattr(sys, "_MEIPASS", BASE))
ASSET = RESOURCE / "assets" / "sprites" / "rewrite_idle_walk.png"

def read_config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {"idle_sleep_seconds": 300, "movement_enabled": True,
                "movement_speed": 3, "subtitle_typewriter_ms": 28}

def load_safri():
    p = BASE / "Rewrite.safri"
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""

class Subtitle(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(440, 104)
        self.label = QLabel("", self)
        self.label.setGeometry(14, 10, 412, 82)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "QLabel { color: #f5efff; background: transparent; "
            "font: 15px 'Segoe UI'; }"
        )
        self.setStyleSheet("background: rgba(15, 5, 35, 225);"
                           "border: 2px solid #8d39ff; border-radius: 13px;")
        self.full_text = ""
        self.index = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._type_next)

    def show_text(self, text, interval=28):
        self.full_text = text
        self.index = 0
        self.label.setText("")
        self.timer.stop()
        self.timer.start(max(8, int(interval)))
        self.show()
        self.raise_()

    def _type_next(self):
        self.index += 1
        self.label.setText(self.full_text[:self.index])
        if self.index >= len(self.full_text):
            self.timer.stop()

class Character(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(160, 160)
        self.frames = []
        self.sheet = QPixmap(str(ASSET))
        if not self.sheet.isNull():
            for i in range(4):
                self.frames.append(self.sheet.copy(i * 128, 0, 128, 128))
        self.frame = 0
        self.drag_offset = None
        self.sleeping = False
        self.sleep_edge = "right"
        self.direction = 1
        self.last_activity = 0
        self.moving = True
        self.animation = QTimer(self)
        self.animation.timeout.connect(self.tick)
        self.animation.start(130)
        self.idle = QTimer(self)
        self.idle.timeout.connect(self.check_idle)
        self.idle.start(1000)
        self.move_to_default()
        self.show()

    def virtual_geometry(self):
        rect = QRect()
        for screen in QApplication.screens():
            rect = rect.united(screen.geometry())
        return rect if not rect.isNull() else QApplication.primaryScreen().geometry()

    def move_to_default(self):
        r = self.virtual_geometry()
        self.move(r.left() + max(10, r.width() // 2 - 80),
                  r.bottom() - self.height() + 4)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self.frames:
            pix = self.frames[self.frame % len(self.frames)]
            if self.direction < 0:
                pix = QPixmap.fromImage(pix.toImage().mirrored(True, False))
            p.drawPixmap(8, 8, 144, 144, pix)

    def tick(self):
        if self.sleeping:
            return
        self.frame = (self.frame + 1) % 4
        if self.app.config.get("movement_enabled", True) and self.moving and not self.drag_offset:
            r = self.virtual_geometry()
            x = self.x() + self.direction * int(self.app.config.get("movement_speed", 3))
            left, right = r.left(), r.right() - self.width()
            if x <= left or x >= right:
                self.direction *= -1
                x = max(left, min(right, x))
            self.move(x, self.y())
        self.update()

    def check_idle(self):
        if self.sleeping:
            return
        self.last_activity += 1
        limit = int(self.app.config.get("idle_sleep_seconds", 300))
        if limit > 0 and self.last_activity >= limit:
            self.sleep()

    def reset_idle(self):
        self.last_activity = 0

    def sleep(self):
        if self.sleeping:
            return
        r = self.virtual_geometry()
        cx = self.x() + self.width() // 2
        cy = self.y() + self.height() // 2
        distances = {
            "left": abs(cx - r.left()),
            "right": abs(r.right() - cx),
            "top": abs(cy - r.top()),
            "bottom": abs(r.bottom() - cy)
        }
        self.sleep_edge = min(distances, key=distances.get)
        self.sleeping = True
        self.app.subtitle.show_text("М-м... Трохи відпочину. Поклич мене, якщо знадоблюся.",
                                    self.app.config.get("subtitle_typewriter_ms", 28))
        self.animation.stop()
        self.hide()

    def wake(self):
        if not self.sleeping:
            self.show()
            return
        r = self.virtual_geometry()
        positions = {
            "left": QPoint(r.left() - self.width() + 8, r.center().y() - 80),
            "right": QPoint(r.right() - 8, r.center().y() - 80),
            "top": QPoint(r.center().x() - 80, r.top() - self.height() + 8),
            "bottom": QPoint(r.center().x() - 80, r.bottom() - 8)
        }
        self.move(positions[self.sleep_edge])
        self.sleeping = False
        self.show()
        self.animation.start(130)
        self.reset_idle()
        self.app.subtitle.show_text("Я тут! Що робимо?",
                                    self.app.config.get("subtitle_typewriter_ms", 28))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.reset_idle()
        elif event.button() == Qt.MouseButton.RightButton:
            self.app.show_character_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None
        self.reset_idle()

    def mouseDoubleClickEvent(self, event):
        self.reset_idle()
        self.app.subtitle.show_text("Хе-хе! Це поки тестова репліка. Мій голосовий модуль ще розробляється.",
                                    self.app.config.get("subtitle_typewriter_ms", 28))

class RewriteApp:
    def __init__(self):
        self.qt = QApplication(sys.argv)
        self.qt.setQuitOnLastWindowClosed(False)
        self.config = read_config()
        self.safri = load_safri()
        self.subtitle = Subtitle()
        self.character = Character(self)
        self.tray = QSystemTrayIcon(self.qt.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Sonic Rewrite")
        menu = QMenu()
        wake = QAction("Покликати Rewrite", menu)
        wake.triggered.connect(self.character.wake)
        sleep = QAction("Відправити спати", menu)
        sleep.triggered.connect(self.character.sleep)
        say = QAction("Тестова репліка", menu)
        say.triggered.connect(lambda: self.subtitle.show_text("Я тут. Голосовий модуль буде додано на наступному етапі."))
        quit_action = QAction("Вийти", menu)
        quit_action.triggered.connect(self.qt.quit)
        menu.addAction(wake)
        menu.addAction(sleep)
        menu.addAction(say)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        if self.config.get("show_subtitles_on_start", True):
            self.subtitle.show_text("Привіт! Я — Rewrite. Поки що я вчуся жити на твоєму робочому столі.",
                                    self.config.get("subtitle_typewriter_ms", 28))

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.character.wake()

    def show_character_menu(self, pos):
        menu = QMenu()
        menu.addAction("Прокинутися", self.character.wake)
        menu.addAction("Заснути", self.character.sleep)
        menu.addAction("Сказати тестову фразу",
                       lambda: self.subtitle.show_text("Що будемо робити далі?"))
        menu.addSeparator()
        menu.addAction("Вихід", self.qt.quit)
        menu.exec(pos)

    def run(self):
        return self.qt.exec()

if __name__ == "__main__":
    app = RewriteApp()
    sys.exit(app.run())
