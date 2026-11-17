#!/usr/bin/env python3
"""A Windows 11-style Notepad clone for Linux, built with PyQt6."""

from __future__ import annotations

import base64
import codecs
import locale
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QByteArray,
    QRectF,
    QSettings,
    QSizeF,
    Qt,
    QUrl,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPageLayout,
    QPageSize,
    QPainter,
    QPalette,
    QPixmap,
    QShortcut,
    QTextCursor,
    QTextDocument,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStatusBar,
    QVBoxLayout,
)

APP_NAME = "Notepad"
ORGANIZATION_NAME = "NotepadLinux"
DEFAULT_FONT_SIZE = 11
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
FILE_FILTER = "Text Documents (*.txt);;All Files (*)"

# A 64x64 notepad icon: white page, folded corner and ruled lines.
ICON_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAC7UlE"
    "QVR4nO2bT0gUURzHP2/cXUyNwhRdTRGDYNFdBDtIpwo6dcn00KGDp8BbFy9elr14yYO3wi4epJOS1+gQ"
    "dU6QMoggD5WarEp/TTab10GNYXWf45t1Z3b2fWBh4b3f+/32u/N73zcDA4bKRhQaSI8/ugWMlrAWt0QR"
    "convywOZTMb2uphKgFdAb0tTAwC2FLzbgOwvy2vOY9FYa5M4JxF7la6sre9+kSzw83OvVxEiqsGWpgbu"
    "3rkJwLOFVR5OzXvJpUe2ihtXerneEwfg8ZOnvF/6BIIe6s7Pp9NpTyK4/js/fPmhm8Mz+blbW+Okkt1O"
    "EbQvS+UV4ORC82ndHJ45LHcq2QXA6zeLPTvVTYuxWGwwl8vZwA6wDWwCW0et7VqAq8lm0rdTvP34zW1I"
    "UehqP8O1VPOhYw4REiOZiZn76XuDuVwuAtTtfbLAhmp91wJEqgT9fe3097mNKA0FRNjfExqB3yiuhNJu"
    "6SdEKtlFKtlNJBpNjGQmZmKxmPN31atiQyEAKEWoVsWFRgAoKIKyzUMlABzZDgcInQBwUATVOcG1CwSJ"
    "5eVVnr946WpuJBpNEGudBfoPHS9mYaXg8qWU67kXO9t2j81SdBaaU3YCdLTF6WiLu54/OT3Hytr6n0Lj"
    "odwDjoMRwO8C/MYI4HcBfqPtAraUbG1tF7MWbWpqqrFEwad7SrQEsKXkwdQs2c2vWkmLTWP9WYaHBrRE"
    "MC2gE2QJwfDQQOW2AOyKUFd7Sjc8MFR8C1S8AGVrg1763knZ2qAX63NiWkAnKAg26GsLgLHB0FDxApSt"
    "DeajuyeUrQ3mo2uLpgV0goJgg/mUtAXA2GBoqHgBAm2DxTruqgi0DRbrjk+FaQGdoFLZYGBbAIwNhgYj"
    "gN8F+I0RwO8C/MYI4HcBfmME8LsAv6l4AZRH4ZW1dSan50pVy4nw/zW7AqgEGANGnQtIaVv2XzsipRQg"
    "T/YuRRshhRDSqrJ2hLD2X50Z87Ukg8EQWP4B9MbxMo1sGhkAAAAASUVORK5CYII="
)

DEFAULT_HEADER = "&f"
DEFAULT_FOOTER = "Page &p"
PAPER_SIZES = (
    ("Letter", QPageSize.PageSizeId.Letter),
    ("A4", QPageSize.PageSizeId.A4),
    ("A3", QPageSize.PageSizeId.A3),
    ("Legal", QPageSize.PageSizeId.Legal),
    ("Executive", QPageSize.PageSizeId.Executive),
)
PAPER_LOOKUP = dict(PAPER_SIZES)


def _as_bool(value, default: bool = False) -> bool:
    """Convert QSettings/string values to a boolean reliably."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    try:
        return bool(value)
    except (TypeError, ValueError):
        return default


def _clamp_size(size: int) -> int:
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(size)))


def _default_font_family() -> str:
    """Choose Courier New when available, otherwise Liberation Mono."""
    try:
        installed = {family.casefold(): family for family in QFontDatabase.families()}
    except Exception:
        installed = {}
    for candidate in ("Courier New", "Liberation Mono"):
        if candidate.casefold() in installed:
            return installed[candidate.casefold()]
    system_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    return system_font.family() or "Monospace"


def _read_text_file(path: Path) -> tuple[str, str, str]:
    """Read a text file, returning (text, encoding, preferred newline)."""
    data = path.read_bytes()

    if data.startswith(codecs.BOM_UTF32_LE) or data.startswith(codecs.BOM_UTF32_BE):
        text = data.decode("utf-32")
        encoding = "utf-32"
    elif data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        text = data.decode("utf-16")
        encoding = "utf-16"
    elif data.startswith(codecs.BOM_UTF8):
        text = data.decode("utf-8-sig")
        encoding = "utf-8-sig"
    else:
        try:
            text = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = None  # type: ignore[assignment]
            encoding = ""
            candidates = [locale.getpreferredencoding(False), "cp1252"]
            for candidate in candidates:
                try:
                    text = data.decode(candidate)
                    encoding = candidate
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if text is None:
                text = data.decode("latin-1")
                encoding = "latin-1"

    if "\r\n" in text:
        newline = "\r\n"
    elif "\r" in text:
        newline = "\r"
    else:
        newline = "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, encoding, newline


def _load_icon() -> QIcon:
    """Decode the embedded PNG icon."""
    try:
        raw = base64.b64decode(ICON_BASE64)
        pixmap = QPixmap()
        if pixmap.loadFromData(raw, "PNG"):
            return QIcon(pixmap)
    except Exception:
        pass
    return QIcon()


class FindDialog(QDialog):
    """A floating, non-modal find dialog."""

    def __init__(self, window: "NotepadWindow") -> None:
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Find")
        self.setModal(False)
        self.setMinimumWidth(360)

        self.find_edit = QLineEdit(self)
        self.find_edit.setClearButtonEnabled(True)

        self.match_case_check = QCheckBox("Match case", self)
        self.wrap_check = QCheckBox("Wrap around", self)
        self.wrap_check.setChecked(True)

        find_next_button = QPushButton("Find Next", self)
        find_next_button.setDefault(True)
        find_next_button.setAutoDefault(True)
        find_previous_button = QPushButton("Find Previous", self)
        close_button = QPushButton("Close", self)

        button_row = QHBoxLayout()
        button_row.addWidget(find_next_button)
        button_row.addWidget(find_previous_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Find what:", self))
        layout.addWidget(self.find_edit)
        layout.addWidget(self.match_case_check)
        layout.addWidget(self.wrap_check)
        layout.addLayout(button_row)

        find_next_button.clicked.connect(lambda: self.perform_find(True))
        find_previous_button.clicked.connect(lambda: self.perform_find(False))
        close_button.clicked.connect(self.close)
        self.find_edit.returnPressed.connect(lambda: self.perform_find(True))
        next_shortcut = QShortcut(QKeySequence("F3"), self)
        next_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        next_shortcut.activated.connect(lambda: self.perform_find(True))
        previous_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        previous_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        previous_shortcut.activated.connect(
            lambda: self.perform_find(False)
        )

    def sync_from_window(self) -> None:
        self.find_edit.setText(self.window_ref.find_term)
        self.match_case_check.setChecked(self.window_ref.search_match_case)
        self.wrap_check.setChecked(self.window_ref.search_wrap)
        self.find_edit.selectAll()
        self.find_edit.setFocus()

    def perform_find(self, forward: bool) -> None:
        term = self.find_edit.text()
        if not term:
            self.find_edit.setFocus()
            return
        match_case = self.match_case_check.isChecked()
        wrap = self.wrap_check.isChecked()
        self.window_ref.find_term = term
        self.window_ref.search_match_case = match_case
        self.window_ref.search_wrap = wrap
        if not self.window_ref.find_text(term, forward, match_case, wrap):
            QMessageBox.information(
                self, APP_NAME, f'Cannot find "{term}"'
            )

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.sync_from_window()


class ReplaceDialog(QDialog):
    """A floating, non-modal replace dialog."""

    def __init__(self, window: "NotepadWindow") -> None:
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Replace")
        self.setModal(False)
        self.setMinimumWidth(380)

        self.find_edit = QLineEdit(self)
        self.find_edit.setClearButtonEnabled(True)
        self.replace_edit = QLineEdit(self)
        self.replace_edit.setClearButtonEnabled(True)
        self.match_case_check = QCheckBox("Match case", self)

        replace_button = QPushButton("Replace", self)
        replace_button.setDefault(True)
        replace_button.setAutoDefault(True)
        replace_all_button = QPushButton("Replace All", self)
        close_button = QPushButton("Close", self)

        button_row = QHBoxLayout()
        button_row.addWidget(replace_button)
        button_row.addWidget(replace_all_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Find what:", self))
        layout.addWidget(self.find_edit)
        layout.addWidget(QLabel("Replace with:", self))
        layout.addWidget(self.replace_edit)
        layout.addWidget(self.match_case_check)
        layout.addLayout(button_row)

        replace_button.clicked.connect(self.replace_current)
        replace_all_button.clicked.connect(self.replace_all)
        close_button.clicked.connect(self.close)

    def sync_from_window(self) -> None:
        self.find_edit.setText(self.window_ref.find_term)
        self.match_case_check.setChecked(self.window_ref.search_match_case)
        self.find_edit.selectAll()
        self.find_edit.setFocus()

    def _read_fields(self) -> tuple[str, str, bool] | None:
        term = self.find_edit.text()
        replacement = self.replace_edit.text()
        match_case = self.match_case_check.isChecked()
        if not term:
            self.find_edit.setFocus()
            return None
        self.window_ref.find_term = term
        self.window_ref.search_match_case = match_case
        return term, replacement, match_case

    def replace_current(self) -> None:
        fields = self._read_fields()
        if fields is None:
            return
        term, replacement, match_case = fields
        replaced, found = self.window_ref.replace_current(
            term, replacement, match_case
        )
        if not replaced and not found:
            QMessageBox.information(self, APP_NAME, f'Cannot find "{term}"')

    def replace_all(self) -> None:
        fields = self._read_fields()
        if fields is None:
            return
        term, replacement, match_case = fields
        count = self.window_ref.replace_all_text(term, replacement, match_case)
        noun = "occurrence" if count == 1 else "occurrences"
        QMessageBox.information(
            self, "Replace All", f"Replaced {count} {noun}."
        )

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.sync_from_window()


class GoToDialog(QDialog):
    """A small modal dialog for jumping to a line number."""

    def __init__(self, window: "NotepadWindow") -> None:
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Go To Line")
        self.setModal(True)
        self.setMinimumWidth(300)

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Line number")
        self.line_edit.setFocus()

        go_button = QPushButton("Go To", self)
        go_button.setDefault(True)
        go_button.setAutoDefault(True)
        cancel_button = QPushButton("Cancel", self)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Line number:", self))
        input_layout.addWidget(self.line_edit, 1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(go_button)
        button_layout.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(input_layout)
        layout.addLayout(button_layout)

        go_button.clicked.connect(self.go_to_line)
        cancel_button.clicked.connect(self.reject)
        self.line_edit.returnPressed.connect(self.go_to_line)

    def go_to_line(self) -> None:
        count = self.window_ref.editor.blockCount()
        raw = self.line_edit.text().strip()
        try:
            line_number = int(raw)
        except ValueError:
            QMessageBox.warning(
                self, APP_NAME, "Line number must be a number."
            )
            self.line_edit.setFocus()
            self.line_edit.selectAll()
            return
        if line_number < 1 or line_number > count:
            QMessageBox.warning(
                self,
                APP_NAME,
                f"Line number out of range. Enter a number between 1 and {count}.",
            )
            self.line_edit.setFocus()
            self.line_edit.selectAll()
            return
        block = self.window_ref.editor.document().findBlockByNumber(
            line_number - 1
        )
        cursor = QTextCursor(block)
        self.window_ref.editor.setTextCursor(cursor)
        self.window_ref.editor.centerCursor()
        self.window_ref.editor.setFocus()
        self.accept()


class PageSetupDialog(QDialog):
    """Page setup options used by the Print command."""

    def __init__(self, window: "NotepadWindow") -> None:
        super().__init__(window)
        self.window_ref = window
        self.setWindowTitle("Page Setup")
        self.setModal(True)
        self.setMinimumWidth(430)

        self.paper_combo = QComboBox(self)
        for name, _page_id in PAPER_SIZES:
            self.paper_combo.addItem(name, name)
        index = self.paper_combo.findData(window.paper_size)
        self.paper_combo.setCurrentIndex(index if index >= 0 else 0)

        self.portrait_radio = QRadioButton("Portrait", self)
        self.landscape_radio = QRadioButton("Landscape", self)
        if window.page_orientation == "landscape":
            self.landscape_radio.setChecked(True)
        else:
            self.portrait_radio.setChecked(True)
        orientation_layout = QHBoxLayout()
        orientation_layout.addWidget(self.portrait_radio)
        orientation_layout.addWidget(self.landscape_radio)
        orientation_group = QGroupBox("Orientation", self)
        orientation_group.setLayout(orientation_layout)

        margins = window.page_margins
        self.top_spin = self._make_margin_spin(margins["top"])
        self.bottom_spin = self._make_margin_spin(margins["bottom"])
        self.left_spin = self._make_margin_spin(margins["left"])
        self.right_spin = self._make_margin_spin(margins["right"])
        margin_layout = QGridLayout()
        margin_layout.addWidget(QLabel("Top:", self), 0, 0)
        margin_layout.addWidget(self.top_spin, 0, 1)
        margin_layout.addWidget(QLabel("Bottom:", self), 0, 2)
        margin_layout.addWidget(self.bottom_spin, 0, 3)
        margin_layout.addWidget(QLabel("Left:", self), 1, 0)
        margin_layout.addWidget(self.left_spin, 1, 1)
        margin_layout.addWidget(QLabel("Right:", self), 1, 2)
        margin_layout.addWidget(self.right_spin, 1, 3)
        margin_group = QGroupBox("Margins (inches)", self)
        margin_group.setLayout(margin_layout)

        self.header_edit = QLineEdit(window.header_text, self)
        self.footer_edit = QLineEdit(window.footer_text, self)

        page_form = QFormLayout()
        page_form.addRow("Paper size:", self.paper_combo)

        header_footer_form = QFormLayout()
        header_footer_form.addRow("Header:", self.header_edit)
        header_footer_form.addRow("Footer:", self.footer_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(page_form)
        layout.addWidget(orientation_group)
        layout.addWidget(margin_group)
        layout.addLayout(header_footer_form)
        layout.addWidget(buttons)

    def _make_margin_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.0, 5.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setSuffix(" in")
        spin.setValue(value)
        return spin

    def values(self) -> dict:
        return {
            "paper_size": self.paper_combo.currentData(),
            "orientation": (
                "landscape" if self.landscape_radio.isChecked() else "portrait"
            ),
            "margins": {
                "top": self.top_spin.value(),
                "bottom": self.bottom_spin.value(),
                "left": self.left_spin.value(),
                "right": self.right_spin.value(),
            },
            "header": self.header_edit.text(),
            "footer": self.footer_edit.text(),
        }


class NotepadWindow(QMainWindow):
    """The main Notepad window."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings(ORGANIZATION_NAME, APP_NAME)
        self._settings_ready = False

        self.current_file: Path | None = None
        self.current_encoding = "utf-8"
        self.current_newline = "\n"

        self.find_term = ""
        self.search_match_case = False
        self.search_wrap = True
        self.find_dialog: FindDialog | None = None
        self.replace_dialog: ReplaceDialog | None = None

        self.paper_size = "Letter"
        self.page_orientation = "portrait"
        self.page_margins = {
            "top": 1.0,
            "bottom": 1.0,
            "left": 1.0,
            "right": 1.0,
        }
        self.header_text = DEFAULT_HEADER
        self.footer_text = DEFAULT_FOOTER

        self.default_font_family = _default_font_family()
        self.base_font = QFont(self.default_font_family)
        self.base_font.setPointSize(DEFAULT_FONT_SIZE)
        self.base_font.setStyleHint(QFont.StyleHint.Monospace)

        self.setWindowTitle("Untitled - Notepad")
        self.setWindowIcon(_load_icon())
        self.resize(900, 650)
        self.setMinimumSize(420, 280)
        self.setAcceptDrops(True)

        self._build_editor()
        self._build_status_bar()
        self._build_actions()
        self._build_menus()
        self._connect_signals()

        self.restore_settings()
        self.update_title()
        self.update_position_label()
        self.editor.setFocus()

    # ------------------------------------------------------------------ UI
    def _build_editor(self) -> None:
        self.editor = QPlainTextEdit(self)
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.editor.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.editor.setAcceptDrops(False)
        self.editor.viewport().setAcceptDrops(False)
        self.editor.setTabChangesFocus(False)
        self.editor.setStyleSheet(
            "QPlainTextEdit {"
            " background-color: #ffffff;"
            " color: #000000;"
            " selection-background-color: #0078d7;"
            " selection-color: #ffffff;"
            "}"
        )
        palette = self.editor.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#000000"))
        self.editor.setPalette(palette)
        self.editor.setFont(self.base_font)
        self.editor.document().setDefaultFont(self.base_font)
        self.setCentralWidget(self.editor)

    def _make_action(
        self,
        text: str,
        shortcut: str | None = None,
        slot=None,
        checkable: bool = False,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if checkable:
            action.setCheckable(True)
        if slot is not None:
            if checkable:
                action.toggled.connect(slot)
            else:
                action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        # File
        self.new_action = self._make_action("New", "Ctrl+N", self.new_file)
        self.new_window_action = self._make_action(
            "New Window", "Ctrl+Shift+N", self.new_window
        )
        self.open_action = self._make_action("Open...", "Ctrl+O", self.open_file)
        self.save_action = self._make_action("Save", "Ctrl+S", self.save_file)
        self.save_as_action = self._make_action(
            "Save As...", "Ctrl+Shift+S", self.save_file_as
        )
        self.page_setup_action = self._make_action(
            "Page Setup...", None, self.show_page_setup
        )
        self.print_action = self._make_action(
            "Print...", "Ctrl+P", self.show_print_dialog
        )
        self.exit_action = self._make_action("Exit", "Ctrl+Q", self.close)

        # Edit
        self.undo_action = self._make_action("Undo", "Ctrl+Z", self.editor.undo)
        self.redo_action = self._make_action("Redo", "Ctrl+Y", self.editor.redo)
        self.cut_action = self._make_action("Cut", "Ctrl+X", self.editor.cut)
        self.copy_action = self._make_action(
            "Copy", "Ctrl+C", self.editor.copy
        )
        self.paste_action = self._make_action(
            "Paste", "Ctrl+V", self.editor.paste
        )
        self.delete_action = self._make_action(
            "Delete", "Del", self.delete_selection
        )
        self.find_action = self._make_action(
            "Find...", "Ctrl+F", self.show_find_dialog
        )
        self.find_next_action = self._make_action(
            "Find Next", "F3", self.find_next
        )
        self.find_previous_action = self._make_action(
            "Find Previous", "Shift+F3", self.find_previous
        )
        self.replace_action = self._make_action(
            "Replace...", "Ctrl+H", self.show_replace_dialog
        )
        self.goto_action = self._make_action(
            "Go To...", "Ctrl+G", self.show_goto_dialog
        )
        self.goto_action.setEnabled(False)
        self.select_all_action = self._make_action(
            "Select All", "Ctrl+A", self.editor.selectAll
        )
        self.time_date_action = self._make_action(
            "Time/Date", "F5", self.insert_time_date
        )

        # Format
        self.word_wrap_action = self._make_action(
            "Word Wrap",
            None,
            self.on_word_wrap_toggled,
            checkable=True,
        )
        self.word_wrap_action.setChecked(True)
        self.font_action = self._make_action("Font...", None, self.choose_font)

        # View
        self.zoom_in_action = self._make_action(
            "Zoom In", "Ctrl+=", self.zoom_in
        )
        self.zoom_out_action = self._make_action(
            "Zoom Out", "Ctrl+-", self.zoom_out
        )
        self.zoom_reset_action = self._make_action(
            "Restore Default Zoom", "Ctrl+0", self.zoom_reset
        )
        self.status_bar_action = self._make_action(
            "Status Bar",
            None,
            self.on_status_bar_toggled,
            checkable=True,
        )
        self.status_bar_action.setChecked(True)

        # Help
        self.help_action = self._make_action("View Help", None, self.view_help)
        self.feedback_action = self._make_action(
            "Send Feedback", None, self.send_feedback
        )
        self.about_action = self._make_action(
            "About Notepad", None, self.show_about
        )

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.new_window_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.page_setup_action)
        file_menu.addAction(self.print_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addAction(self.delete_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.find_next_action)
        edit_menu.addAction(self.find_previous_action)
        edit_menu.addAction(self.replace_action)
        edit_menu.addAction(self.goto_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.time_date_action)

        format_menu = menu_bar.addMenu("Format")
        format_menu.addAction(self.word_wrap_action)
        format_menu.addAction(self.font_action)

        view_menu = menu_bar.addMenu("View")
        zoom_menu = view_menu.addMenu("Zoom")
        zoom_menu.addAction(self.zoom_in_action)
        zoom_menu.addAction(self.zoom_out_action)
        zoom_menu.addAction(self.zoom_reset_action)
        view_menu.addAction(self.status_bar_action)

        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction(self.help_action)
        help_menu.addAction(self.feedback_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        status_bar.setSizeGripEnabled(True)
        self.setStatusBar(status_bar)
        self.position_label = QLabel("Ln 1, Col 1", self)
        self.position_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.position_label.setContentsMargins(6, 0, 6, 0)
        self.position_label.setMinimumWidth(130)
        status_bar.addPermanentWidget(self.position_label, 1)

    def _connect_signals(self) -> None:
        self.editor.cursorPositionChanged.connect(self.update_position_label)
        self.editor.textChanged.connect(self.update_title)
        self.editor.document().modificationChanged.connect(self.update_title)

    # -------------------------------------------------------------- titles
    def display_name(self) -> str:
        return self.current_file.name if self.current_file else "Untitled"

    def update_title(self, *_args) -> None:
        marker = "*" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{marker}{self.display_name()} - Notepad")

    def update_position_label(self, *_args) -> None:
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        self.position_label.setText(f"Ln {line}, Col {column}")

    # ---------------------------------------------------------- save/open
    def maybe_save(self) -> bool:
        """Return True when it is safe to discard the current document."""
        if not self.editor.document().isModified():
            return True

        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"Do you want to save changes to {self.display_name()}?"
        )
        save_button = box.addButton(
            "Save", QMessageBox.ButtonRole.AcceptRole
        )
        discard_button = box.addButton(
            "Don't Save", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = box.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(save_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            return self.save_file()
        if clicked is discard_button:
            return True
        return False

    def new_file(self) -> None:
        if not self.maybe_save():
            return
        self.editor.clear()
        self.editor.document().clearUndoRedoStacks()
        self.editor.document().setModified(False)
        self.current_file = None
        self.current_encoding = "utf-8"
        self.current_newline = "\n"
        self.update_title()
        self.update_position_label()
        self.editor.setFocus()

    def new_window(self) -> None:
        if not self.maybe_save():
            return
        script = Path(__file__).resolve()
        python = sys.executable or "python3"
        try:
            subprocess.Popen(
                [python, str(script)],
                close_fds=True,
                start_new_session=True,
            )
        except OSError as error:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not open a new window:\n{error}",
            )

    def open_file(self) -> None:
        if not self.maybe_save():
            return
        start_dir = (
            str(self.current_file.parent)
            if self.current_file
            else str(Path.home())
        )
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open", start_dir, FILE_FILTER
        )
        if file_name:
            self.load_file(Path(file_name))

    def load_file(self, path: Path) -> bool:
        try:
            text, encoding, newline = _read_text_file(path)
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not open {path}:\n{error}",
            )
            return False

        self.editor.setPlainText(text)
        self.editor.document().clearUndoRedoStacks()
        self.editor.document().setModified(False)
        self.current_file = path
        self.current_encoding = encoding
        self.current_newline = newline
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        self.update_title()
        self.update_position_label()
        self.editor.setFocus()
        return True

    def save_file(self) -> bool:
        if self.current_file is None:
            return self.save_file_as()
        return self._write_to_path(self.current_file)

    def save_file_as(self) -> bool:
        if self.current_file is not None:
            initial = str(self.current_file)
        else:
            initial = str(Path.home() / "Untitled.txt")
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save As", initial, FILE_FILTER
        )
        if not file_name:
            return False
        return self._write_to_path(Path(file_name))

    def _write_to_path(self, path: Path) -> bool:
        try:
            text = self.editor.toPlainText()
            if self.current_newline != "\n":
                text = text.replace("\n", self.current_newline)
            data = text.encode(self.current_encoding)
            path.write_bytes(data)
        except (OSError, UnicodeError, LookupError, ValueError) as error:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not save {path}:\n{error}",
            )
            return False

        self.current_file = path
        self.editor.document().setModified(False)
        self.update_title()
        self.statusBar().showMessage(f"Saved {path.name}", 2500)
        return True

    # ---------------------------------------------------------- local edit
    def delete_selection(self) -> None:
        cursor = self.editor.textCursor()
        cursor.deleteChar()
        self.editor.setTextCursor(cursor)

    def insert_time_date(self) -> None:
        now = datetime.now()
        hour = now.hour % 12 or 12
        stamp = f"{hour}:{now.minute:02d} {now.strftime('%p')} {now.month}/{now.day}/{now.year}"
        cursor = self.editor.textCursor()
        cursor.insertText(stamp)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    # --------------------------------------------------------- find/replace
    def show_find_dialog(self) -> None:
        if self.find_dialog is None:
            self.find_dialog = FindDialog(self)
        if not self.find_dialog.isVisible():
            self.find_dialog.sync_from_window()
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()
        self.find_dialog.find_edit.setFocus()
        self.find_dialog.find_edit.selectAll()

    def show_replace_dialog(self) -> None:
        if self.replace_dialog is None:
            self.replace_dialog = ReplaceDialog(self)
        if not self.replace_dialog.isVisible():
            self.replace_dialog.sync_from_window()
        self.replace_dialog.show()
        self.replace_dialog.raise_()
        self.replace_dialog.activateWindow()
        self.replace_dialog.find_edit.setFocus()
        self.replace_dialog.find_edit.selectAll()

    def find_text(
        self,
        term: str,
        forward: bool = True,
        match_case: bool = False,
        wrap: bool = True,
    ) -> bool:
        if not term:
            return False
        document = self.editor.document()
        flags = QTextDocument.FindFlag(0)
        if match_case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        cursor = self.editor.textCursor()
        if forward:
            start = (
                cursor.selectionEnd()
                if cursor.hasSelection()
                else cursor.position()
            )
        else:
            start = (
                cursor.selectionStart()
                if cursor.hasSelection()
                else cursor.position()
            )

        result = document.find(term, start, flags)
        if result.isNull() and wrap:
            if forward:
                result = document.find(term, 0, flags)
            else:
                end_cursor = QTextCursor(document)
                end_cursor.movePosition(QTextCursor.MoveOperation.End)
                result = document.find(term, end_cursor.position(), flags)

        if result.isNull():
            return False
        self.editor.setTextCursor(result)
        self.editor.ensureCursorVisible()
        return True

    def find_next(self) -> None:
        if not self.find_term:
            self.show_find_dialog()
            return
        if not self.find_text(
            self.find_term,
            True,
            self.search_match_case,
            self.search_wrap,
        ):
            QMessageBox.information(
                self, APP_NAME, f'Cannot find "{self.find_term}"'
            )

    def find_previous(self) -> None:
        if not self.find_term:
            self.show_find_dialog()
            return
        if not self.find_text(
            self.find_term,
            False,
            self.search_match_case,
            self.search_wrap,
        ):
            QMessageBox.information(
                self, APP_NAME, f'Cannot find "{self.find_term}"'
            )

    def _selection_matches(self, term: str, match_case: bool) -> bool:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return False
        selected = cursor.selectedText().replace("\u2029", "\n")
        if match_case:
            return selected == term
        return selected.casefold() == term.casefold()

    def replace_current(
        self, term: str, replacement: str, match_case: bool
    ) -> tuple[bool, bool]:
        """Replace the current match, then find the next one.

        If the current selection is not a match, the next occurrence is found
        and replaced in the same action.  Returns (replaced, found_next).
        """
        if not term:
            return False, False

        if self._selection_matches(term, match_case):
            cursor = self.editor.textCursor()
            cursor.insertText(replacement)
            self.editor.setTextCursor(cursor)
        else:
            if not self.find_text(term, True, match_case, True):
                return False, False
            cursor = self.editor.textCursor()
            cursor.insertText(replacement)
            self.editor.setTextCursor(cursor)

        found_next = self.find_text(term, True, match_case, True)
        return True, found_next

    def replace_all_text(
        self, term: str, replacement: str, match_case: bool
    ) -> int:
        if not term:
            return 0
        text = self.editor.toPlainText()
        if match_case:
            count = text.count(term)
            new_text = text.replace(term, replacement)
        else:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            new_text, count = pattern.subn(lambda _m: replacement, text)
        if count == 0:
            return 0

        cursor = self.editor.textCursor()
        old_position = cursor.position()
        edit_cursor = QTextCursor(self.editor.document())
        edit_cursor.beginEditBlock()
        edit_cursor.select(QTextCursor.SelectionType.Document)
        edit_cursor.insertText(new_text)
        edit_cursor.endEditBlock()

        restored = QTextCursor(self.editor.document())
        restored.setPosition(min(old_position, self.editor.document().characterCount() - 1))
        self.editor.setTextCursor(restored)
        self.editor.ensureCursorVisible()
        return count

    # -------------------------------------------------------------- go to
    def show_goto_dialog(self) -> None:
        if self.word_wrap_action.isChecked():
            return
        dialog = GoToDialog(self)
        initial = self.editor.textCursor().blockNumber() + 1
        dialog.line_edit.setText(str(initial))
        dialog.line_edit.selectAll()
        dialog.exec()

    # --------------------------------------------------------------- font
    def choose_font(self) -> None:
        font, accepted = QFontDialog.getFont(
            self.base_font, self, "Font"
        )
        if not accepted:
            return
        size = font.pointSize()
        if size <= 0:
            size = DEFAULT_FONT_SIZE
        size = _clamp_size(size)
        font.setPointSize(size)
        self.base_font = QFont(font)
        self.current_point_size = size
        self.apply_editor_font()
        if self._settings_ready:
            self.save_settings()

    def apply_editor_font(self) -> None:
        font = QFont(self.base_font)
        font.setPointSize(_clamp_size(self.current_point_size))
        self.editor.setFont(font)
        self.editor.document().setDefaultFont(font)

    def zoom_in(self) -> None:
        self.set_zoom_size(self.current_point_size + 2)

    def zoom_out(self) -> None:
        self.set_zoom_size(self.current_point_size - 2)

    def zoom_reset(self) -> None:
        base_size = self.base_font.pointSize()
        if base_size <= 0:
            base_size = DEFAULT_FONT_SIZE
        self.set_zoom_size(base_size)

    def set_zoom_size(self, size: int) -> None:
        size = _clamp_size(size)
        if size == self.current_point_size:
            return
        self.current_point_size = size
        self.apply_editor_font()

    # -------------------------------------------------------------- format
    def on_word_wrap_toggled(self, enabled: bool) -> None:
        self.apply_word_wrap(enabled)
        if self._settings_ready:
            self.save_settings()

    def apply_word_wrap(self, enabled: bool) -> None:
        if enabled:
            self.editor.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.WidgetWidth
            )
            self.editor.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        else:
            self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            self.editor.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
        self.goto_action.setEnabled(not enabled)
        self.editor.update()

    def on_status_bar_toggled(self, visible: bool) -> None:
        self.statusBar().setVisible(visible)
        if self._settings_ready:
            self.save_settings()

    # ---------------------------------------------------------- page setup/print
    def show_page_setup(self) -> None:
        dialog = PageSetupDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            self.paper_size = values["paper_size"]
            self.page_orientation = values["orientation"]
            self.page_margins = dict(values["margins"])
            self.header_text = values["header"]
            self.footer_text = values["footer"]

    def _configure_printer_paper(self, printer: QPrinter) -> None:
        page_id = PAPER_LOOKUP.get(
            self.paper_size, QPageSize.PageSizeId.Letter
        )
        printer.setPageSize(QPageSize(page_id))
        orientation = (
            QPageLayout.Orientation.Landscape
            if self.page_orientation == "landscape"
            else QPageLayout.Orientation.Portrait
        )
        printer.setPageOrientation(orientation)

    def show_print_dialog(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self._configure_printer_paper(printer)
        printer.setDocName(self.display_name())
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.render_to_printer(printer)
        except Exception as error:  # Printing backends can fail in many ways.
            QMessageBox.critical(
                self, APP_NAME, f"Could not print the document:\n{error}"
            )

    def _expand_header_footer(self, template: str, page_number: int) -> str:
        now = datetime.now()
        values = {
            "f": self.display_name(),
            "p": str(page_number),
            "d": now.strftime("%m/%d/%Y"),
            "t": now.strftime("%I:%M %p"),
        }
        result: list[str] = []
        index = 0
        while index < len(template):
            character = template[index]
            if character == "&" and index + 1 < len(template):
                token = template[index + 1]
                if token == "&":
                    result.append("&")
                    index += 2
                    continue
                if token.lower() in values:
                    result.append(values[token.lower()])
                    index += 2
                    continue
            result.append(character)
            index += 1
        return "".join(result)

    def render_to_printer(self, printer: QPrinter) -> None:
        """Render the editor contents, plus headers and footers, to a printer."""
        document = QTextDocument()
        print_font = QFont(self.base_font)
        if print_font.pointSize() <= 0:
            print_font.setPointSize(DEFAULT_FONT_SIZE)
        document.setDefaultFont(print_font)
        document.documentLayout().setPaintDevice(printer)
        document.setDocumentMargin(0)
        document.setPlainText(self.editor.toPlainText())

        printer.setDocName(self.display_name())

        resolution = printer.resolution()
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        margin_left = int(self.page_margins["left"] * resolution)
        margin_top = int(self.page_margins["top"] * resolution)
        margin_right = int(self.page_margins["right"] * resolution)
        margin_bottom = int(self.page_margins["bottom"] * resolution)

        content = QRectF(
            margin_left,
            margin_top,
            max(1.0, page_rect.width() - margin_left - margin_right),
            max(1.0, page_rect.height() - margin_top - margin_bottom),
        )

        header_font = QFont(print_font)
        header_font.setPointSize(9)
        header_font.setBold(False)
        header_font.setItalic(False)
        header_band = (
            int(0.32 * resolution) if self.header_text.strip() else 0
        )
        footer_band = (
            int(0.32 * resolution) if self.footer_text.strip() else 0
        )
        body_height = content.height() - header_band - footer_band
        if body_height <= 1:
            header_band = 0
            footer_band = 0
            body_height = max(1.0, content.height())
        body = QRectF(
            content.left(),
            content.top() + header_band,
            max(1.0, content.width()),
            max(1.0, body_height),
        )

        document.setPageSize(QSizeF(body.width(), body.height()))
        page_count = max(1, document.pageCount())

        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError("the printer could not be opened")
        try:
            for page_index in range(page_count):
                if page_index > 0:
                    printer.newPage()
                painter.save()
                painter.setClipRect(body)
                painter.translate(
                    body.left(),
                    body.top() - page_index * body.height(),
                )
                document.drawContents(painter)
                painter.restore()

                painter.setFont(header_font)
                if header_band:
                    header = self._expand_header_footer(
                        self.header_text, page_index + 1
                    )
                    painter.drawText(
                        QRectF(
                            content.left(),
                            content.top(),
                            content.width(),
                            header_band,
                        ),
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignVCenter,
                        header,
                    )
                if footer_band:
                    footer = self._expand_header_footer(
                        self.footer_text, page_index + 1
                    )
                    painter.drawText(
                        QRectF(
                            content.left(),
                            body.bottom(),
                            content.width(),
                            footer_band,
                        ),
                        Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignVCenter,
                        footer,
                    )
        finally:
            painter.end()

    # ---------------------------------------------------------------- help
    def view_help(self) -> None:
        QDesktopServices.openUrl(QUrl("https://support.microsoft.com"))

    def send_feedback(self) -> None:
        QMessageBox.information(
            self, "Send Feedback", "Thank you for your feedback!"
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Notepad",
            "Notepad\nA simple text editor for Linux.\nBuilt with PyQt6.",
        )

    # --------------------------------------------------------- drag & drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if len(urls) == 1:
                url = urls[0]
                if url.isLocalFile():
                    try:
                        if Path(url.toLocalFile()).is_file():
                            event.acceptProposedAction()
                            return
                    except OSError:
                        pass
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if len(urls) == 1 and urls[0].isLocalFile():
                path = Path(urls[0].toLocalFile())
                if path.is_file():
                    if self.maybe_save():
                        self.load_file(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    # ------------------------------------------------------------ settings
    def restore_settings(self) -> None:
        settings = self.settings

        family_value = settings.value("font/family", "", type=str)
        families = {
            family.casefold(): family
            for family in QFontDatabase.families()
        }
        if family_value and family_value.casefold() in families:
            family = families[family_value.casefold()]
        else:
            family = self.default_font_family
        try:
            size = int(settings.value("font/size", DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            size = DEFAULT_FONT_SIZE
        size = _clamp_size(size)
        self.base_font = QFont(family)
        self.base_font.setPointSize(size)
        self.base_font.setBold(
            _as_bool(settings.value("font/bold", False))
        )
        self.base_font.setItalic(
            _as_bool(settings.value("font/italic", False))
        )
        if family.casefold() == self.default_font_family.casefold():
            self.base_font.setStyleHint(QFont.StyleHint.Monospace)
        self.current_point_size = size
        self.apply_editor_font()

        wrap = _as_bool(settings.value("view/word_wrap", True), True)
        status_visible = _as_bool(
            settings.value("view/status_bar", True), True
        )
        self.word_wrap_action.setChecked(wrap)
        self.status_bar_action.setChecked(status_visible)
        self.apply_word_wrap(wrap)
        self.statusBar().setVisible(status_visible)

        geometry = settings.value("window/geometry")
        restored_geometry = False
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            restored_geometry = self.restoreGeometry(geometry)
        elif isinstance(geometry, (bytes, bytearray)) and geometry:
            restored_geometry = self.restoreGeometry(QByteArray(geometry))
        if not restored_geometry:
            self.resize(900, 650)

        self._settings_ready = True

    def save_settings(self) -> None:
        if not self._settings_ready:
            return
        settings = self.settings
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue(
            "view/word_wrap", self.word_wrap_action.isChecked()
        )
        settings.setValue(
            "view/status_bar", self.status_bar_action.isChecked()
        )
        settings.setValue("font/family", self.base_font.family())
        size = self.base_font.pointSize()
        if size <= 0:
            size = DEFAULT_FONT_SIZE
        settings.setValue("font/size", size)
        settings.setValue("font/bold", self.base_font.bold())
        settings.setValue("font/italic", self.base_font.italic())
        settings.sync()

    # --------------------------------------------------------------- close
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self.maybe_save():
            self.close_auxiliary_dialogs()
            self.save_settings()
            event.accept()
        else:
            event.ignore()

    def close_auxiliary_dialogs(self) -> None:
        if self.find_dialog is not None:
            self.find_dialog.close()
        if self.replace_dialog is not None:
            self.replace_dialog.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    # Match the installed notepad.desktop so Wayland compositors can associate
    # the window with its launcher icon and startup notification.
    app.setDesktopFileName("notepad")
    QApplication.setWindowIcon(_load_icon())

    window = NotepadWindow()
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1]).expanduser()
        if candidate.is_file():
            window.load_file(candidate)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
