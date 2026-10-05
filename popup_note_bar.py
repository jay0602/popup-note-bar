"""Popup Note Bar - a keyboard-first floating note panel for Windows."""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(os, "add_dll_directory"):
    frozen_root = Path(sys._MEIPASS)
    for folder in (frozen_root, frozen_root / "PyQt6", frozen_root / "PyQt6" / "Qt6" / "bin"):
        if folder.exists():
            os.add_dll_directory(str(folder))

from PyQt6.QtCore import QEvent, QPoint, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from note_store import Note, NoteStore


APP_NAME = "彈出記事欄"
APP_VERSION = "1.0.0"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PopupNoteBar"
HOTKEY_ID = 0x504E
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002


def make_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#F7C948"))
    painter.setPen(QColor("#6B4F00"))
    painter.drawRoundedRect(5, 5, size - 10, size - 10, 10, 10)
    painter.setPen(QColor("#183B56"))
    painter.setFont(QFont("Segoe UI", max(12, size // 3), QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    painter.end()
    return QIcon(pixmap)


class DragBar(QWidget):
    def __init__(self, window: "NoteWindow"):
        super().__init__()
        self.window = window
        self.origin: QPoint | None = None
        self.setObjectName("dragBar")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.origin)

    def mouseReleaseEvent(self, event):
        self.origin = None


class NoteWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.store = NoteStore(DATA_DIR / "notes.json")
        self.store.load()
        self.settings = QSettings("OpenSourceTools", "PopupNoteBar")
        self.current_id: str | None = None
        self.loading_note = False
        self.quitting = False
        self.hotkey_registered = False

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(make_icon())
        self.resize(760, 500)
        self.setMinimumSize(560, 340)
        self.build_ui()
        self.build_tray()
        self.restore_preferences()
        self.refresh_notes()

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_current)
        self.editor.textChanged.connect(lambda: self.save_timer.start(350))
        self.title_edit.textChanged.connect(lambda: self.save_timer.start(350))

        QShortcut(QKeySequence("Ctrl+Alt+N"), self).activated.connect(self.toggle_visible)

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = DragBar(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 10, 10)
        title = QLabel("彈出記事欄")
        title.setFont(QFont("Microsoft JhengHei UI", 12, QFont.Weight.Bold))
        hint = QLabel("Ctrl + Alt + N")
        hint.setObjectName("hotkeyHint")
        self.pin_box = QCheckBox("置頂")
        self.pin_box.setChecked(True)
        self.pin_box.toggled.connect(self.apply_window_flags)
        hide_btn = QPushButton("—")
        hide_btn.setFixedSize(34, 28)
        hide_btn.clicked.connect(self.hide)
        header_layout.addWidget(title)
        header_layout.addWidget(hint)
        header_layout.addStretch()
        header_layout.addWidget(self.pin_box)
        header_layout.addWidget(hide_btn)
        outer.addWidget(header)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        sidebar = QWidget()
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 12, 8, 12)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋記事…")
        self.search_edit.textChanged.connect(self.refresh_notes)
        add_btn = QPushButton("＋ 新記事")
        add_btn.clicked.connect(self.add_note)
        self.note_list = QListWidget()
        self.note_list.currentItemChanged.connect(self.select_note)
        side_layout.addWidget(self.search_edit)
        side_layout.addWidget(add_btn)
        side_layout.addWidget(self.note_list, 1)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(12, 12, 14, 12)
        top = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("記事標題")
        self.title_edit.setObjectName("titleEdit")
        delete_btn = QPushButton("刪除")
        delete_btn.setObjectName("dangerButton")
        delete_btn.clicked.connect(self.delete_note)
        top.addWidget(self.title_edit, 1)
        top.addWidget(delete_btn)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("把現在不想忘記的事寫在這裡…")
        self.editor.setAcceptRichText(False)
        bottom = QHBoxLayout()
        self.status = QLabel("所有內容只保存在這台電腦")
        self.auto_hide_box = QCheckBox("失焦後自動收起")
        self.auto_hide_box.toggled.connect(self.save_preferences)
        bottom.addWidget(self.status)
        bottom.addStretch()
        bottom.addWidget(self.auto_hide_box)
        editor_layout.addLayout(top)
        editor_layout.addWidget(self.editor, 1)
        editor_layout.addLayout(bottom)

        splitter.addWidget(sidebar)
        splitter.addWidget(editor_panel)
        splitter.setSizes([230, 530])
        outer.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)

    def build_tray(self):
        self.tray = QSystemTrayIcon(make_icon(), self)
        menu = QMenu()
        show_action = QAction("顯示／隱藏", self)
        show_action.triggered.connect(self.toggle_visible)
        new_action = QAction("新增記事", self)
        new_action.triggered.connect(self.add_note_and_show)
        data_action = QAction("開啟資料夾", self)
        data_action.triggered.connect(lambda: os.startfile(DATA_DIR))
        quit_action = QAction("結束", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(new_action)
        menu.addSeparator()
        menu.addAction(data_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.setToolTip(f"{APP_NAME}－Ctrl + Alt + N")
        self.tray.show()

    def restore_preferences(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.pin_box.setChecked(self.settings.value("always_on_top", True, type=bool))
        self.auto_hide_box.setChecked(self.settings.value("auto_hide", False, type=bool))
        self.apply_window_flags()

    def save_preferences(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("always_on_top", self.pin_box.isChecked())
        self.settings.setValue("auto_hide", self.auto_hide_box.isChecked())

    def apply_window_flags(self):
        visible = self.isVisible()
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self.pin_box.isChecked():
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.save_preferences()
        if visible:
            self.show()

    def refresh_notes(self, *_):
        selected = self.current_id
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for note in self.store.search(self.search_edit.text()):
            item = QListWidgetItem(note.title)
            preview = " ".join(note.content.split())[:55]
            item.setToolTip(preview or "空白記事")
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            self.note_list.addItem(item)
            if note.id == selected:
                self.note_list.setCurrentItem(item)
        self.note_list.blockSignals(False)
        if self.note_list.currentItem() is None and self.note_list.count():
            self.note_list.setCurrentRow(0)
            self.select_note(self.note_list.currentItem(), None)

    def select_note(self, current: QListWidgetItem | None, _previous):
        if current is None:
            return
        self.save_timer.stop() if hasattr(self, "save_timer") else None
        note = self.store.get(current.data(Qt.ItemDataRole.UserRole))
        if note is None:
            return
        self.loading_note = True
        self.current_id = note.id
        self.title_edit.setText(note.title)
        self.editor.setPlainText(note.content)
        self.loading_note = False

    def save_current(self):
        if self.loading_note or not self.current_id:
            return
        note = self.store.update(self.current_id, self.title_edit.text(), self.editor.toPlainText())
        if note:
            self.status.setText("已自動儲存")
            self.refresh_notes()

    def add_note(self):
        self.save_current()
        note = self.store.add()
        self.current_id = note.id
        self.search_edit.clear()
        self.refresh_notes()
        self.select_note(self.note_list.currentItem(), None)
        self.title_edit.selectAll()
        self.title_edit.setFocus()

    def add_note_and_show(self):
        self.show_panel()
        self.add_note()

    def delete_note(self):
        if not self.current_id:
            return
        answer = QMessageBox.question(
            self,
            "刪除記事",
            "確定永久刪除目前的記事？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.delete(self.current_id)
            self.current_id = None
            self.refresh_notes()

    def toggle_visible(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show_panel()

    def show_panel(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.editor.setFocus()

    def tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_visible()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if self.auto_hide_box.isChecked():
                QTimer.singleShot(250, self.hide_if_inactive)

    def hide_if_inactive(self):
        if not self.isActiveWindow() and not self.tray.contextMenu().isVisible():
            self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == "win32" and not self.hotkey_registered:
            hwnd = int(self.winId())
            self.hotkey_registered = bool(
                ctypes.windll.user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_ALT, ord("N"))
            )
            if not self.hotkey_registered:
                self.status.setText("快捷鍵已被其他程式使用；仍可從系統匣開啟")

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.toggle_visible()
                return True, 0
        return super().nativeEvent(event_type, message)

    def closeEvent(self, event):
        if self.quitting:
            self.save_current()
            self.save_preferences()
            if self.hotkey_registered and sys.platform == "win32":
                ctypes.windll.user32.UnregisterHotKey(int(self.winId()), HOTKEY_ID)
            event.accept()
        else:
            event.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "程式仍在系統匣執行。按 Ctrl + Alt + N 可再次叫出。")

    def quit_app(self):
        self.quitting = True
        self.close()
        QApplication.quit()


STYLE = """
QWidget#root { background: #F7F9FC; color: #243447; }
QWidget#dragBar { background: #183B56; }
QWidget#dragBar QLabel, QWidget#dragBar QCheckBox { color: white; }
QLabel#hotkeyHint { color: #C7DCE9; padding-left: 8px; }
QLineEdit, QTextEdit, QListWidget {
    background: white; border: 1px solid #CBD5E1; border-radius: 7px;
    padding: 7px; selection-background-color: #2F6B8A;
}
QLineEdit#titleEdit { font-size: 17px; font-weight: 600; }
QTextEdit { font: 11pt "Microsoft JhengHei UI"; }
QListWidget::item { padding: 9px 7px; border-bottom: 1px solid #EEF2F6; }
QListWidget::item:selected { background: #DCECF5; color: #183B56; }
QPushButton {
    background: #2F6B8A; color: white; border: 0; border-radius: 6px;
    padding: 7px 12px; font-weight: 600;
}
QPushButton:hover { background: #24556E; }
QPushButton#dangerButton { background: #B54747; }
QPushButton#dangerButton:hover { background: #8F3838; }
QSplitter::handle { background: #E4EAF0; width: 1px; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(make_icon())
    window = NoteWindow()
    window.show_panel()
    if "--smoke-test" in sys.argv or os.environ.get("POPUP_NOTE_SMOKE_TEST") == "1":
        QTimer.singleShot(1500, window.quit_app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
