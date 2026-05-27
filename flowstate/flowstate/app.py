"""FlowState — Visual Workflow Orchestrator (S0LF0RG3 dark theme)."""

import sys
import os
import ast
import json
import uuid
from typing import Optional

# Allow running as `python app.py` from inside the package directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QMenuBar, QMenu, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QLabel, QDockWidget,
    QScrollArea, QFrame, QTextEdit, QTabWidget, QLineEdit,
    QFormLayout, QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QAction, QFont, QColor

from flowstate.canvas import WorkflowCanvas
from flowstate.nodes import Node, NodeType, PREDEFINED_NODES
from flowstate.generator import CodeGenerator, generate_tests_for_workflow
from flowstate.runner import WorkflowRunner, run_pytest_tests


# ── Global stylesheet ─────────────────────────────────────────────────────────

DARK_STYLE = """
QWidget {
    background-color: #0f0f1a;
    color: #e0e0f0;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px;
}
QMainWindow {
    background-color: #09090f;
}
QMenuBar {
    background-color: #0f0f1a;
    color: #a0a0c0;
    border-bottom: 1px solid #1a1a2e;
    padding: 2px 4px;
}
QMenuBar::item:selected {
    background-color: #1a1a2e;
    color: #00ff88;
}
QMenu {
    background-color: #12121e;
    color: #d0d0e8;
    border: 1px solid #2a2a44;
}
QMenu::item:selected {
    background-color: #1e1e32;
    color: #00ff88;
}
QToolBar {
    background-color: #0f0f1a;
    border-bottom: 1px solid #1a1a2e;
    spacing: 4px;
    padding: 4px 8px;
}
QToolBar QToolButton {
    background-color: #18182a;
    color: #a0a0c0;
    border: 1px solid #2a2a44;
    border-radius: 4px;
    padding: 4px 10px;
    margin: 1px;
}
QToolBar QToolButton:hover {
    background-color: #22223a;
    color: #e0e0f0;
    border-color: #00ff88;
}
QToolBar QToolButton:pressed {
    background-color: #00ff8820;
}
QDockWidget {
    color: #a0a0c0;
    font-size: 11px;
}
QDockWidget::title {
    background-color: #0f0f1a;
    border-bottom: 1px solid #1a1a2e;
    padding: 6px 8px;
    color: #00cfff;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QDockWidget QWidget {
    background-color: #0f0f1a;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background: #0f0f1a;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2a44;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #3a3a60; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #0f0f1a;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #2a2a44;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background: #3a3a60; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QStatusBar {
    background-color: #09090f;
    color: #50507a;
    border-top: 1px solid #1a1a2e;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #1a1a2e;
    background-color: #0f0f1a;
}
QTabBar::tab {
    background-color: #0f0f1a;
    color: #60607a;
    border: 1px solid #1a1a2e;
    border-bottom: none;
    padding: 5px 14px;
    margin-right: 2px;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #12121e;
    color: #00cfff;
    border-top: 2px solid #00cfff;
}
QTabBar::tab:hover:!selected {
    color: #a0a0c0;
}
QTextEdit {
    background-color: #09090f;
    color: #c8c8e8;
    border: none;
    font-family: Consolas, monospace;
    font-size: 12px;
    selection-background-color: #00cfff40;
    padding: 8px;
}
QLineEdit {
    background-color: #12121e;
    color: #d0d0e8;
    border: 1px solid #2a2a44;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus {
    border-color: #00cfff;
}
QLabel {
    color: #8080a0;
    background: transparent;
}
QSplitter::handle {
    background-color: #1a1a2e;
}
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }
"""

# Node type button colors (header accent matching canvas theme)
_TYPE_STYLE = {
    NodeType.TRIGGER:   ("#00a8ff", "#001830"),
    NodeType.ACTION:    ("#00d46a", "#001a0e"),
    NodeType.CONDITION: ("#ffd700", "#1a1400"),
    NodeType.OUTPUT:    ("#b44eff", "#150022"),
}


# ── Worker thread for LLM generation ─────────────────────────────────────────

class _GenWorker(QThread):
    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, generator, workflow_data):
        super().__init__()
        self.generator = generator
        self.workflow_data = workflow_data

    def run(self):
        try:
            code = self.generator.generate_workflow_code(self.workflow_data)
            self.result.emit(code)
        except Exception as e:
            self.error.emit(str(e))


# ── Node palette button ───────────────────────────────────────────────────────

class NodeButton(QPushButton):
    def __init__(self, node_key: str, node_def: dict, parent=None):
        super().__init__(parent)
        self.node_key = node_key
        ntype = node_def["type"]
        accent, bg = _TYPE_STYLE.get(ntype, ("#8888ff", "#101018"))
        badge = {"trigger": "▶", "action": "⚡", "condition": "◆", "output": "■"}.get(
            ntype.value if hasattr(ntype, "value") else str(ntype), "●"
        )
        self.setText(f"{badge}  {node_def['name']}")
        self.setToolTip(node_def.get("description", ""))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {accent};
                border: 1px solid {accent}44;
                border-left: 3px solid {accent};
                border-radius: 4px;
                padding: 6px 10px;
                text-align: left;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {accent}22;
                border-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: {accent}44;
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# ── Properties panel ─────────────────────────────────────────────────────────

class PropertiesPanel(QWidget):
    properties_changed = pyqtSignal(str, dict)  # node_id, new_props

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Optional[Node] = None
        self._fields: dict = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)

        self._title = QLabel("— no node selected —")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet("color: #404060; font-size: 11px; padding: 12px 0;")
        self._layout.addWidget(self._title)
        self._layout.addStretch()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                PropertiesPanel._clear_layout(item.layout())

    def load_node(self, node: Optional["Node"]):
        self._clear_layout(self._layout)
        self._fields.clear()
        self._node = node

        if node is None:
            lbl = QLabel("— no node selected —")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #404060; font-size: 11px; padding: 12px 0;")
            self._layout.addWidget(lbl)
            self._layout.addStretch()
            return

        ntype = node.node_type
        accent, _ = _TYPE_STYLE.get(ntype, ("#8888ff", "#101018"))
        badge = {"trigger": "▶", "action": "⚡", "condition": "◆", "output": "■"}.get(
            ntype.value, "●"
        )

        # Header
        header = QLabel(f"{badge}  {node.title}")
        header.setStyleSheet(f"""
            color: {accent};
            font-size: 13px;
            font-weight: bold;
            border-bottom: 1px solid {accent}44;
            padding: 4px 0 8px 0;
        """)
        self._layout.addWidget(header)

        # Type badge
        type_lbl = QLabel(ntype.value.upper())
        type_lbl.setStyleSheet(f"""
            color: {accent};
            background: {accent}18;
            border: 1px solid {accent}44;
            border-radius: 3px;
            font-size: 9px;
            padding: 2px 6px;
            letter-spacing: 1px;
        """)
        type_lbl.setFixedWidth(80)
        self._layout.addWidget(type_lbl)

        # Node ID (read-only)
        id_form = QFormLayout()
        id_form.setContentsMargins(0, 8, 0, 0)
        id_form.setSpacing(6)
        id_lbl = QLabel(node.node_id[:12] + "…")
        id_lbl.setStyleSheet("color: #404060; font-size: 10px;")
        id_form.addRow(QLabel("ID"), id_lbl)
        self._layout.addLayout(id_form)

        if not node.properties:
            no_props = QLabel("No configurable properties.")
            no_props.setStyleSheet("color: #404060; font-size: 11px; padding: 8px 0;")
            self._layout.addWidget(no_props)
        else:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #1a1a2e;")
            self._layout.addWidget(sep)

            form = QFormLayout()
            form.setContentsMargins(0, 4, 0, 4)
            form.setSpacing(8)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            for key, val in node.properties.items():
                field = QLineEdit(str(val))
                field.setPlaceholderText(str(val))
                field.textChanged.connect(lambda text, k=key: self._on_field_changed(k, text))
                label_text = key.replace("_", " ").title()
                lbl = QLabel(label_text)
                lbl.setMinimumWidth(60)
                lbl.setStyleSheet("color: #8080a0; font-size: 11px;")
                form.addRow(lbl, field)
                self._fields[key] = field
            self._layout.addLayout(form)

        self._layout.addStretch()

    def _on_field_changed(self, key: str, text: str):
        if self._node:
            self._node.properties[key] = text
            self.properties_changed.emit(self._node.node_id, self._node.properties)


# ── Main window ───────────────────────────────────────────────────────────────

class FlowStateMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowState — Visual Workflow Orchestrator")
        self.setGeometry(80, 80, 1400, 860)
        self.setMinimumSize(900, 600)

        self.canvas = WorkflowCanvas()
        self.code_generator = CodeGenerator()
        self.workflow_runner = WorkflowRunner()

        self.current_workflow_path = None
        self.generated_code = None
        self.generated_tests = None
        self._last_results = None
        self._gen_worker = None

        self._init_ui()
        self.canvas.node_selected.connect(self._on_node_selected)
        self.canvas.node_added.connect(lambda n: self._status(f"Added: {n.title}"))
        self.canvas.connection_added.connect(
            lambda s, t: self._status(f"Connected: {s[:8]}… → {t[:8]}…")
        )

    # ── UI construction ───────────────────────────────────────────────────────

    def _init_ui(self):
        # Central splitter: canvas + bottom panel
        v_split = QSplitter(Qt.Orientation.Vertical)
        v_split.addWidget(self.canvas)

        # Bottom panel — tabs: Generated Code / Output
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setMinimumHeight(120)

        code_tab = QWidget()
        code_tab_layout = QVBoxLayout(code_tab)
        code_tab_layout.setContentsMargins(0, 0, 0, 0)
        code_tab_layout.setSpacing(0)

        code_toolbar = QWidget()
        code_toolbar.setStyleSheet("background: #0f0f1a; border-bottom: 1px solid #1a1a2e;")
        code_tb_layout = QHBoxLayout(code_toolbar)
        code_tb_layout.setContentsMargins(6, 4, 6, 4)
        code_tb_layout.setSpacing(6)
        save_code_btn = self._tb_btn("💾 Save Code…", "Save generated code to .py file",
                                     self._save_generated_code)
        save_code_btn.setFixedWidth(130)
        code_tb_layout.addWidget(save_code_btn)
        code_tb_layout.addStretch()
        code_tab_layout.addWidget(code_toolbar)

        self._code_view = QTextEdit()
        self._code_view.setReadOnly(True)
        self._code_view.setPlaceholderText("Generated Python code will appear here...")
        code_tab_layout.addWidget(self._code_view)
        self._bottom_tabs.addTab(code_tab, "⚡ Generated Code")

        output_tab = QWidget()
        output_tab_layout = QVBoxLayout(output_tab)
        output_tab_layout.setContentsMargins(0, 0, 0, 0)
        output_tab_layout.setSpacing(0)

        output_toolbar = QWidget()
        output_toolbar.setStyleSheet("background: #0f0f1a; border-bottom: 1px solid #1a1a2e;")
        out_tb_layout = QHBoxLayout(output_toolbar)
        out_tb_layout.setContentsMargins(6, 4, 6, 4)
        out_tb_layout.setSpacing(6)
        save_results_btn = self._tb_btn("💾 Save Results…", "Save workflow results to JSON",
                                        self._save_results)
        save_results_btn.setFixedWidth(140)
        out_tb_layout.addWidget(save_results_btn)
        out_tb_layout.addStretch()
        output_tab_layout.addWidget(output_toolbar)

        self._output_view = QTextEdit()
        self._output_view.setReadOnly(True)
        self._output_view.setPlaceholderText("Workflow execution output...")
        output_tab_layout.addWidget(self._output_view)
        self._bottom_tabs.addTab(output_tab, "▶ Output")

        test_tab = QWidget()
        test_tab_layout = QVBoxLayout(test_tab)
        test_tab_layout.setContentsMargins(0, 0, 0, 0)
        test_tab_layout.setSpacing(0)

        test_toolbar = QWidget()
        test_toolbar.setStyleSheet("background: #0f0f1a; border-bottom: 1px solid #1a1a2e;")
        test_tb_layout = QHBoxLayout(test_toolbar)
        test_tb_layout.setContentsMargins(6, 4, 6, 4)
        test_tb_layout.setSpacing(6)
        run_tests_btn = self._tb_btn("▶ Run Tests", "Generate and run pytest tests (F6)",
                                     self._generate_and_run_tests)
        run_tests_btn.setFixedWidth(120)
        test_tb_layout.addWidget(run_tests_btn)
        test_tb_layout.addStretch()
        test_tab_layout.addWidget(test_toolbar)

        self._test_view = QTextEdit()
        self._test_view.setReadOnly(True)
        self._test_view.setPlaceholderText("Click '▶ Run Tests' to generate and run pytest tests...")
        test_tab_layout.addWidget(self._test_view)
        self._bottom_tabs.addTab(test_tab, "✓ Tests")

        v_split.addWidget(self._bottom_tabs)
        v_split.setSizes([600, 180])

        self.setCentralWidget(v_split)

        self._create_menu()
        self._create_toolbar()
        self._create_left_dock()
        self._create_right_dock()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status("Ready — drag nodes from the palette, connect output → input ports")

        self._status_label = QLabel("● FLOWSTATE")
        self._status_label.setStyleSheet("color: #00ff88; font-size: 10px; padding: 0 8px;")
        self._status_bar.addPermanentWidget(self._status_label)

    def _create_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        self._add_action(fm, "&New Workflow", "Ctrl+N", self.new_workflow)
        self._add_action(fm, "&Open…", "Ctrl+O", self.open_workflow)
        self._add_action(fm, "&Save", "Ctrl+S", self.save_workflow)
        self._add_action(fm, "Save &As…", "Ctrl+Shift+S", self.save_workflow_as)
        fm.addSeparator()
        self._add_action(fm, "E&xit", "Ctrl+Q", self.close)

        wm = mb.addMenu("&Workflow")
        self._add_action(wm, "&Generate Code", "Ctrl+G", self.generate_code)
        self._add_action(wm, "&Run Workflow", "F5", self.run_workflow)
        wm.addSeparator()
        self._add_action(wm, "Generate &Tests", "Ctrl+T", self._generate_and_run_tests)
        self._add_action(wm, "Run &Tests", "F6", self._generate_and_run_tests)

        vm = mb.addMenu("&View")
        self._add_action(vm, "Zoom &In", "Ctrl+=", lambda: self.canvas.scale(1.2, 1.2))
        self._add_action(vm, "Zoom &Out", "Ctrl+-", lambda: self.canvas.scale(1/1.2, 1/1.2))
        self._add_action(vm, "&Reset Zoom", "Ctrl+0", lambda: self.canvas.resetTransform())

    def _add_action(self, menu, label, shortcut, callback):
        act = QAction(label, self)
        act.setShortcut(shortcut)
        act.triggered.connect(callback)
        menu.addAction(act)
        return act

    def _create_toolbar(self):
        tb = self.addToolBar("Actions")
        tb.setMovable(False)
        tb.setFloatable(False)

        for label, tip, cb in [
            ("⚡ Generate", "Generate Python code (Ctrl+G)", self.generate_code),
            ("▶ Run",       "Run workflow (F5)",             self.run_workflow),
            ("✓ Tests",     "Generate + run tests (F6)", self._generate_and_run_tests),
        ]:
            btn = tb.addWidget(self._tb_btn(label, tip, cb))

        tb.addSeparator()

        for label, tip, cb in [
            ("+ Zoom",   "Zoom in",    lambda: self.canvas.scale(1.2, 1.2)),
            ("− Zoom",   "Zoom out",   lambda: self.canvas.scale(1/1.2, 1/1.2)),
            ("⌂ Reset",  "Reset zoom", lambda: self.canvas.resetTransform()),
        ]:
            tb.addWidget(self._tb_btn(label, tip, cb))

    def _tb_btn(self, label, tip, cb):
        btn = QPushButton(label)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #18182a;
                color: #a0a0c0;
                border: 1px solid #2a2a44;
                border-radius: 4px;
                padding: 5px 14px;
                margin: 2px;
            }
            QPushButton:hover {
                background: #22223a;
                color: #e0e0f0;
                border-color: #00ff88;
            }
            QPushButton:pressed { background: #00ff8820; }
        """)
        btn.clicked.connect(cb)
        return btn

    def _create_left_dock(self):
        dock = QDockWidget("NODE PALETTE", self)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Group by type
        groups = {
            NodeType.TRIGGER:   [],
            NodeType.ACTION:    [],
            NodeType.CONDITION: [],
            NodeType.OUTPUT:    [],
        }
        for key, nd in PREDEFINED_NODES.items():
            groups[nd["type"]].append((key, nd))

        group_labels = {
            NodeType.TRIGGER:   "TRIGGERS",
            NodeType.ACTION:    "ACTIONS",
            NodeType.CONDITION: "LOGIC",
            NodeType.OUTPUT:    "OUTPUTS",
        }

        for ntype, items in groups.items():
            if not items:
                continue
            accent, _ = _TYPE_STYLE.get(ntype, ("#8888ff", "#101018"))
            grp_lbl = QLabel(group_labels[ntype])
            grp_lbl.setStyleSheet(f"""
                color: {accent};
                font-size: 9px;
                letter-spacing: 2px;
                padding: 10px 4px 4px 4px;
                border-bottom: 1px solid {accent}33;
            """)
            layout.addWidget(grp_lbl)

            for key, nd in items:
                btn = NodeButton(key, nd)
                btn.clicked.connect(lambda _=False, k=key: self._add_predefined_node(k))
                layout.addWidget(btn)

        layout.addStretch()
        scroll.setWidget(container)
        dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(190)

    def _create_right_dock(self):
        dock = QDockWidget("PROPERTIES", self)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._props_panel = PropertiesPanel()
        scroll.setWidget(self._props_panel)
        dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setMinimumWidth(220)

    # ── node operations ───────────────────────────────────────────────────────

    def _add_predefined_node(self, node_key: str):
        if node_key not in PREDEFINED_NODES:
            return
        nd = PREDEFINED_NODES[node_key]
        node = Node(str(uuid.uuid4()), nd["type"], nd["name"])
        for inp in nd["inputs"]:
            node.add_input(inp["name"], inp["type"], inp.get("required", False))
        for out in nd["outputs"]:
            node.add_output(out["name"], out["type"])
        for k, v in nd["properties"].items():
            node.set_property(k, v)
        self.canvas.add_node(node)

    def _on_node_selected(self, node):
        self._props_panel.load_node(node)

    # ── workflow I/O ──────────────────────────────────────────────────────────

    def new_workflow(self):
        for nid in list(self.canvas.node_items.keys()):
            self.canvas.remove_node(nid)
        self.current_workflow_path = None
        self.generated_code = None
        self.setWindowTitle("FlowState — Visual Workflow Orchestrator")
        self._code_view.clear()
        self._output_view.clear()
        self._test_view.clear()
        self._status("New workflow")

    def open_workflow(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Workflow", "",
                                               "Workflow Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.canvas.load_workflow_data(data)
            self.current_workflow_path = path
            self.setWindowTitle(f"FlowState — {os.path.basename(path)}")
            self._status(f"Opened: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open: {e}")

    def save_workflow(self):
        if self.current_workflow_path:
            self._write_workflow(self.current_workflow_path)
        else:
            self.save_workflow_as()

    def save_workflow_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Workflow", "",
                                               "Workflow Files (*.json);;All Files (*)")
        if path:
            self._write_workflow(path)
            self.current_workflow_path = path
            self.setWindowTitle(f"FlowState — {os.path.basename(path)}")

    def _write_workflow(self, path: str):
        try:
            data = self.canvas.get_workflow_data()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._status(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    # ── code generation ───────────────────────────────────────────────────────

    def _save_results(self):
        if not self._last_results:
            self._status("⚠ No results to save — run the workflow first (F5)")
            return
        default = os.path.splitext(os.path.basename(
            self.current_workflow_path or "workflow"))[0] + "_results.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Results", default,
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            import json as _json
            ext = os.path.splitext(path)[1].lower()
            # Collect all list-of-dict data from results
            all_rows = []
            for v in self._last_results.values():
                if isinstance(v, dict):
                    for val in v.values():
                        if isinstance(val, list) and val and isinstance(val[0], dict):
                            all_rows = val
                            break
            if ext == ".csv" and all_rows:
                import csv
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(all_rows)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(self._last_results, f, indent=2, default=str)
            self._status(f"Results saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save results: {e}")

    def _save_generated_code(self):
        if not self.generated_code:
            self._status("⚠ No generated code to save — run Generate first (Ctrl+G)")
            return
        default = os.path.splitext(os.path.basename(
            self.current_workflow_path or "workflow"))[0] + ".py"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Generated Code", default, "Python Files (*.py);;All Files (*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.generated_code)
                self._status(f"Code saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def generate_code(self):
        wf = self.canvas.get_workflow_data()
        if not wf.get("nodes"):
            self._status("⚠ No nodes in workflow")
            return

        self._status("Generating code… (LLM running)")
        self._code_view.setPlainText("⏳ Generating code with LLM…")
        self._bottom_tabs.setCurrentIndex(0)

        self._gen_worker = _GenWorker(self.code_generator, wf)
        self._gen_worker.result.connect(self._on_code_generated)
        self._gen_worker.error.connect(self._on_gen_error)
        self._gen_worker.start()

    def _on_code_generated(self, code: str):
        self.generated_code = code
        self._code_view.setPlainText(code)
        self._status(f"Code generated — {len(code.splitlines())} lines")

    def _on_gen_error(self, err: str):
        self._code_view.setPlainText(f"# Generation failed:\n# {err}")
        self._status(f"⚠ Code generation failed: {err[:80]}")

    def run_workflow(self):
        if not self.generated_code:
            try:
                wf = self.canvas.get_workflow_data()
                if not wf.get("nodes"):
                    self._status("⚠ No nodes — nothing to run")
                    return
                self.generated_code = self.code_generator.generate_workflow_code(wf)
                self._code_view.setPlainText(self.generated_code)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return

        self._status("Running workflow…")
        self._bottom_tabs.setCurrentIndex(1)
        # Point runner's cwd at the workflow file's directory so relative output paths work
        if self.current_workflow_path:
            self.workflow_runner._output_dir = os.path.dirname(
                os.path.abspath(self.current_workflow_path))
        else:
            self.workflow_runner._output_dir = os.path.dirname(os.path.abspath(__file__))
        result = self.workflow_runner.execute_workflow_code(self.generated_code)

        if result["success"]:
            # Parse results dict from stdout for Save Results button
            import re as _re
            _m = _re.search(r"Workflow results: (\{.+\})", result["stdout"], _re.DOTALL)
            if _m:
                try:
                    self._last_results = ast.literal_eval(_m.group(1))
                except Exception:
                    self._last_results = None

            stdout = result["stdout"] or "(no output)"
            note = ""
            if "Stub implementation" in (self.generated_code or ""):
                note = (
                    "\n⚠ NOTE: Some nodes used stub implementations.\n"
                    "  Check the Generated Code tab — stubs return None.\n"
                    + "─" * 50 + "\n"
                )
            self._output_view.setPlainText(
                "✓ WORKFLOW EXECUTED SUCCESSFULLY\n"
                + "─" * 50 + "\n"
                + note
                + stdout
            )
            self._status("✓ Workflow executed successfully")
        else:
            self._output_view.setPlainText(
                "✗ WORKFLOW FAILED\n"
                + "─" * 50 + "\n"
                + (result["stderr"] or result["stdout"] or "(no output)")
            )
            self._status("✗ Workflow execution failed")

    def _generate_and_run_tests(self):
        """Generate tests then immediately run them."""
        if not self.generated_code:
            self._status("⚠ Generate code first (Ctrl+G)")
            return
        self.generate_tests()
        if self.generated_tests:
            self.run_tests()

    def generate_tests(self):
        if not self.generated_code:
            self._status("⚠ Generate code first (Ctrl+G)")
            return
        try:
            wf = self.canvas.get_workflow_data()
            self.generated_tests = generate_tests_for_workflow(wf, self.generated_code)
            self._test_view.setPlainText(self.generated_tests)
            self._bottom_tabs.setCurrentIndex(2)
            self._status(f"Tests generated — {len(self.generated_tests.splitlines())} lines")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def run_tests(self):
        if not self.generated_tests:
            self._status("⚠ Generate tests first (Ctrl+T)")
            return
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(self.generated_tests)
            tp = f.name
        result = run_pytest_tests(self.generated_tests, tp)
        os.unlink(tp)

        out = ("TESTS PASSED\n" if result["success"] else "TESTS FAILED\n")
        out += "-" * 50 + "\n" + (result["stdout"] or result["stderr"] or "(no output)")
        self._test_view.setPlainText(out)
        self._bottom_tabs.setCurrentIndex(2)
        self._status("✓ Tests passed" if result["success"] else "✗ Tests failed")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self.statusBar().showMessage(msg)

    def closeEvent(self, event):
        self.workflow_runner.cleanup()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FlowState")
    app.setApplicationVersion("2.0.0")
    app.setStyleSheet(DARK_STYLE)
    window = FlowStateMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
