# -*- coding: utf-8 -*-
###############################################################################
#
#  SymbolChooser.py - KiCad-style symbol selection dialog for placement.
#
###############################################################################
"""Placement dialog in the spirit of KiCad's "Choose Symbol" window:

* search box filtering the whole store as you type
* tree of recently-used symbols and library groups
* live SVG preview with connection pins marked and named
* pin table and description for the highlighted symbol
* Enter / double-click / Place button hands the choice to the existing
  StartDraw() cursor-placement flow (same path as the toolbar buttons)
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

from Schematics.Features.Utils.SymbolCatalog import (
    SymbolCatalog,
    SymbolEntry,
    SymbolPin,
)

# Session-wide "Recently used" list (keys, most recent first).
_recent_keys: list[str] = []

RECENT_LIMIT = 12


def note_recent(key: str) -> None:
    """Remember a placed symbol for the chooser's Recently used section."""
    if key in _recent_keys:
        _recent_keys.remove(key)
    _recent_keys.insert(0, key)
    del _recent_keys[RECENT_LIMIT:]


def recent_keys() -> list[str]:
    return list(_recent_keys)


class SymbolPreview(QtWidgets.QWidget):
    """Renders one symbol's SVG with its pins drawn as labelled dots."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._catalog: SymbolCatalog | None = None
        self._entry: SymbolEntry | None = None
        self._pins: list[SymbolPin] = []
        self._highlight: str | None = None
        self._renderer = QtSvg.QSvgRenderer()
        self.setMinimumSize(240, 170)

    def setSymbol(self, catalog: SymbolCatalog, entry: SymbolEntry | None) -> None:
        self._catalog = catalog
        self._entry = entry
        self._pins = []
        self._highlight = None
        if entry is not None:
            data, raw = catalog.load(entry)
            self._renderer.load(data.encode())
            self._pins = [SymbolPin(str(n), float(x), float(y)) for n, x, y in raw]
        else:
            self._renderer = QtSvg.QSvgRenderer()
        self.update()

    def setHighlight(self, pinName: str | None) -> None:
        self._highlight = pinName
        self.update()

    def _target_rect(self) -> QtCore.QRectF:
        """viewBox scaled to fit the widget, aspect preserved, centred."""
        vb = self._renderer.viewBoxF()
        if vb.isEmpty():
            return QtCore.QRectF()
        margin = 14.0
        avail_w = max(self.width() - 2 * margin, 1.0)
        avail_h = max(self.height() - 2 * margin, 1.0)
        scale = min(avail_w / vb.width(), avail_h / vb.height())
        w = vb.width() * scale
        h = vb.height() * scale
        x = (self.width() - w) / 2.0
        y = (self.height() - h) / 2.0
        return QtCore.QRectF(x, y, w, h)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#ffffff"))
        painter.setPen(QtGui.QColor("#b0b0b0"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._entry is None or not self._renderer.isValid():
            painter.setPen(QtGui.QColor("#808080"))
            painter.drawText(
                self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "No symbol",
            )
            painter.end()
            return

        vb = self._renderer.viewBoxF()
        target = self._target_rect()
        self._renderer.render(painter, target)

        # Pins in widget coordinates (renderer maps viewBox -> target).
        sx = target.width() / vb.width() if vb.width() else 1.0
        sy = target.height() / vb.height() if vb.height() else 1.0
        for pin in self._pins:
            px = target.left() + (pin.x - vb.left()) * sx
            py = target.top() + (pin.y - vb.top()) * sy
            highlighted = pin.name == self._highlight
            radius = 4.5 if highlighted else 3.0
            color = QtGui.QColor("#d97706") if highlighted else QtGui.QColor("#dc2626")
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.0))
            painter.setBrush(color)
            painter.drawEllipse(QtCore.QPointF(px, py), radius, radius)
            painter.setPen(QtGui.QColor("#404040"))
            painter.drawText(
                QtCore.QPointF(px + 6.0, py - 4.0), pin.name,
            )
        painter.end()


class SymbolChooser(QtWidgets.QDialog):
    """Search / browse / preview a symbol, then place it on the sheet."""

    def __init__(
        self,
        catalog: SymbolCatalog | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Place symbol")
        self.setModal(True)
        self.catalog = catalog if catalog is not None else SymbolCatalog()
        self._chosen: SymbolEntry | None = None

        # --- left: search + tree -------------------------------------
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search symbols…")
        self.search.setClearButtonEnabled(True)

        self.tree = QtWidgets.QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)

        left = QtWidgets.QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.search)
        left.addWidget(self.tree, 1)
        leftWidget = QtWidgets.QWidget(self)
        leftWidget.setLayout(left)

        # --- right: preview + pins + description ---------------------
        self.preview = SymbolPreview(self)

        self.pinTable = QtWidgets.QTableWidget(self)
        self.pinTable.setColumnCount(3)
        self.pinTable.setHorizontalHeaderLabels(["Pin", "X", "Y"])
        self.pinTable.horizontalHeader().setStretchLastSection(True)
        self.pinTable.verticalHeader().setVisible(False)
        self.pinTable.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.pinTable.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.pinTable.setMaximumHeight(150)

        self.description = QtWidgets.QLabel(self)
        self.description.setWordWrap(True)
        self.description.setTextFormat(QtCore.Qt.TextFormat.PlainText)

        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self.preview, 1)
        right.addWidget(QtWidgets.QLabel("Connection pins", self))
        right.addWidget(self.pinTable)
        right.addWidget(self.description)
        rightWidget = QtWidgets.QWidget(self)
        rightWidget.setLayout(right)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.addWidget(leftWidget)
        splitter.addWidget(rightWidget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        ).setText("Place")
        buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        ).setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._okButton = buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addWidget(buttons)

        self.search.textChanged.connect(self._applyFilter)
        self.tree.currentItemChanged.connect(self._showSelection)
        self.tree.itemDoubleClicked.connect(self._onDoubleClick)

        self._fill()
        self.search.setFocus()
        self.resize(760, 520)

    # ------------------------------------------------------------------
    def _fill(self) -> None:
        self.tree.clear()
        font = self.tree.font()

        recents: list[SymbolEntry] = []
        for key in recent_keys():
            standard, _, rest = key.partition("\\")
            group, _, name = rest.partition("\\")
            entry = self.catalog.find(name, group, standard)
            if entry is not None:
                recents.append(entry)
        if recents:
            recentItem = QtWidgets.QTreeWidgetItem(["Recently used"])
            recentItem.setData(0, QtCore.Qt.ItemDataRole.UserRole, None)
            recentItem.setFont(0, QtGui.QFont(font))
            self.tree.addTopLevelItem(recentItem)
            for entry in recents:
                child = QtWidgets.QTreeWidgetItem([entry.display_name])
                child.setData(0, QtCore.Qt.ItemDataRole.UserRole, entry)
                recentItem.addChild(child)
            recentItem.setExpanded(True)

        for group in self.catalog.groups():
            label = group if group else "(no group)"
            groupItem = QtWidgets.QTreeWidgetItem([label])
            groupItem.setData(0, QtCore.Qt.ItemDataRole.UserRole, None)
            self.tree.addTopLevelItem(groupItem)
            for entry in self.catalog.symbols_in(group):
                child = QtWidgets.QTreeWidgetItem([entry.display_name])
                child.setData(0, QtCore.Qt.ItemDataRole.UserRole, entry)
                groupItem.addChild(child)
            groupItem.setExpanded(True)

        # Select the first actual symbol.
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None and top.childCount() > 0:
                self.tree.setCurrentItem(top.child(0))
                break

    def _entryOf(self, item: QtWidgets.QTreeWidgetItem | None) -> SymbolEntry | None:
        if item is None:
            return None
        value = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        return value if isinstance(value, SymbolEntry) else None

    def _applyFilter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is None:
                continue
            anyVisible = False
            for j in range(top.childCount()):
                child = top.child(j)
                match = not needle or needle in child.text(0).lower()
                child.setHidden(not match)
                anyVisible = anyVisible or match
            # A group matches by its own name too; the pseudo-group with no
            # children (e.g. an empty "Recently used") follows its name.
            topMatch = not needle or needle in top.text(0).lower()
            top.setHidden(not (anyVisible or (top.childCount() == 0 and topMatch)))
            if needle and anyVisible:
                top.setExpanded(True)

    def _showSelection(
        self,
        current: QtWidgets.QTreeWidgetItem | None,
        _previous: QtWidgets.QTreeWidgetItem | None,
    ) -> None:
        entry = self._entryOf(current)
        self._chosen = entry
        self.preview.setSymbol(self.catalog, entry)
        if entry is None:
            self.pinTable.setRowCount(0)
            self.description.setText("")
            self._okButton.setEnabled(False)
            return
        pins = self.catalog.pins(entry)
        self.pinTable.setRowCount(len(pins))
        for row, pin in enumerate(pins):
            self.pinTable.setItem(row, 0, QtWidgets.QTableWidgetItem(pin.name))
            self.pinTable.setItem(row, 1, QtWidgets.QTableWidgetItem("%g" % pin.x))
            self.pinTable.setItem(row, 2, QtWidgets.QTableWidgetItem("%g" % pin.y))
        meta = self.catalog.meta(entry)
        parts: list[str] = []
        if meta.description:
            parts.append(meta.description)
        parts.append("%s%s" % (entry.group + "/" if entry.group else "", entry.name))
        self.description.setText("  ·  ".join(parts))
        self._okButton.setEnabled(True)

    def _onDoubleClick(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        if self._entryOf(item) is not None:
            self.accept()

    # ------------------------------------------------------------------
    def accept(self) -> None:
        if self._chosen is not None:
            note_recent(self._chosen.key)
        super().accept()

    def selectedEntry(self) -> SymbolEntry | None:
        return self._chosen
