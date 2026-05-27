"""Dark-themed PyQt6 canvas for FlowState workflow orchestrator."""

import math
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsPathItem, QGraphicsEllipseItem,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainter, QPainterPath,
    QFont, QLinearGradient, QRadialGradient,
)

from flowstate.nodes import Node, NodeType

# ── Theme ─────────────────────────────────────────────────────────────────────
_C = {
    "bg":          QColor(0x09, 0x09, 0x12),
    "grid_major":  QColor(0x1a, 0x1a, 0x2e, 100),
    "grid_minor":  QColor(0x14, 0x14, 0x20, 60),
    "node_body":   QColor(0x12, 0x12, 0x1e),
    "node_border": QColor(0x2a, 0x2a, 0x44),
    "node_sel":    QColor(0x00, 0xff, 0x88),
    "text":        QColor(0xe8, 0xe8, 0xf0),
    "text_dim":    QColor(0x70, 0x70, 0x90),
    "port_in":     QColor(0x00, 0xcf, 0xff),
    "port_out":    QColor(0x00, 0xff, 0x88),
    NodeType.TRIGGER:   QColor(0x00, 0xa8, 0xff),
    NodeType.ACTION:    QColor(0x00, 0xd4, 0x6a),
    NodeType.CONDITION: QColor(0xff, 0xd7, 0x00),
    NodeType.OUTPUT:    QColor(0xb4, 0x4e, 0xff),
}

NODE_W      = 190
HEADER_H    = 30
PORT_R      = 6
PORT_SPACE  = 22
BODY_VPAD   = 10
CORNER_R    = 8
FONT_TITLE  = QFont("Consolas", 9, QFont.Weight.Bold)
FONT_PORT   = QFont("Consolas", 7)


# ── Port item ─────────────────────────────────────────────────────────────────

class PortItem(QGraphicsEllipseItem):
    """A single input or output port circle on a node."""

    def __init__(self, is_output: bool, index: int, label: str, parent: "NodeItem"):
        super().__init__(-PORT_R, -PORT_R, PORT_R * 2, PORT_R * 2, parent)
        self.is_output = is_output
        self.index = index
        self.label = label
        self.node_item = parent

        color = _C["port_out"] if is_output else _C["port_in"]
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(130), 1))
        self.setZValue(2)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self.brush().color().lighter(140)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        color = _C["port_out"] if self.is_output else _C["port_in"]
        self.setBrush(QBrush(color))
        super().hoverLeaveEvent(event)


# ── Node item ─────────────────────────────────────────────────────────────────

class NodeItem(QGraphicsItem):
    """Custom-painted node with header band, ports, and label."""

    def __init__(self, node: Node, parent=None):
        super().__init__(parent)
        self.node = node
        self.input_ports: List[PortItem] = []
        self.output_ports: List[PortItem] = []

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setPos(node.x, node.y)
        self.setZValue(1)

        self._build_ports()

    # ── geometry ──────────────────────────────────────────────────────────────

    def _body_height(self) -> int:
        rows = max(len(self.node.inputs), len(self.node.outputs), 1)
        return HEADER_H + BODY_VPAD + rows * PORT_SPACE + BODY_VPAD

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_W, self._body_height())

    # ── ports ─────────────────────────────────────────────────────────────────

    def _build_ports(self):
        for p in self.input_ports + self.output_ports:
            p.setParentItem(None)
        self.input_ports.clear()
        self.output_ports.clear()

        for i, inp in enumerate(self.node.inputs or []):
            p = PortItem(False, i, inp.get("name", f"in{i}"), self)
            p.setPos(0, HEADER_H + BODY_VPAD + i * PORT_SPACE + PORT_SPACE // 2)
            self.input_ports.append(p)

        for i, out in enumerate(self.node.outputs or []):
            p = PortItem(True, i, out.get("name", f"out{i}"), self)
            p.setPos(NODE_W, HEADER_H + BODY_VPAD + i * PORT_SPACE + PORT_SPACE // 2)
            self.output_ports.append(p)

    # ── paint ─────────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self._body_height()
        w = NODE_W
        selected = self.isSelected()
        type_color: QColor = _C.get(self.node.node_type, QColor(0x44, 0x44, 0x66))

        # ── body shadow ──
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(QRectF(3, 3, w, h), CORNER_R, CORNER_R)
        painter.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 80)))

        # ── body fill ──
        body_path = QPainterPath()
        body_path.addRoundedRect(QRectF(0, 0, w, h), CORNER_R, CORNER_R)
        painter.fillPath(body_path, QBrush(_C["node_body"]))

        # ── header fill ──
        header_path = QPainterPath()
        header_path.addRoundedRect(QRectF(0, 0, w, HEADER_H), CORNER_R, CORNER_R)
        # clip bottom of header to straight edge
        clip = QPainterPath()
        clip.addRect(QRectF(0, 0, w, HEADER_H))
        actual_header = header_path.intersected(clip)
        # add a straight bottom rect to avoid gap
        actual_header.addRect(QRectF(0, HEADER_H - CORNER_R, w, CORNER_R))

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, type_color.darker(110))
        grad.setColorAt(1, type_color.darker(160))
        painter.fillPath(actual_header, QBrush(grad))

        # ── border ──
        border_color = _C["node_sel"] if selected else _C["node_border"]
        border_w = 2 if selected else 1
        painter.setPen(QPen(border_color, border_w))
        painter.drawPath(body_path)

        # ── type badge ──
        badge_rect = QRectF(8, 7, 16, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
        painter.drawRoundedRect(badge_rect, 3, 3)
        badge_char = {"trigger": "▶", "action": "⚡", "condition": "◆", "output": "■"}.get(
            self.node.node_type.value, "●"
        )
        painter.setPen(QPen(_C["text"]))
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_char)

        # ── title ──
        painter.setPen(QPen(_C["text"]))
        painter.setFont(FONT_TITLE)
        title_rect = QRectF(30, 0, w - 38, HEADER_H)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.node.title)

        # ── port labels ──
        painter.setFont(FONT_PORT)
        for i, inp in enumerate(self.node.inputs or []):
            y = HEADER_H + BODY_VPAD + i * PORT_SPACE + PORT_SPACE // 2
            painter.setPen(QPen(_C["port_in"].lighter(120)))
            painter.drawText(QRectF(PORT_R + 4, y - 8, NODE_W // 2 - 8, 16),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             inp.get("name", ""))

        for i, out in enumerate(self.node.outputs or []):
            y = HEADER_H + BODY_VPAD + i * PORT_SPACE + PORT_SPACE // 2
            painter.setPen(QPen(_C["port_out"].lighter(110)))
            painter.drawText(QRectF(NODE_W // 2, y - 8, NODE_W // 2 - PORT_R - 4, 16),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             out.get("name", ""))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.x = int(self.pos().x())
            self.node.y = int(self.pos().y())
            if self.scene():
                for conn in self.scene().items():
                    if isinstance(conn, ConnectionPath):
                        if (conn.src_node is self or conn.dst_node is self):
                            conn.update_path()
        return super().itemChange(change, value)


# ── Connection bezier ─────────────────────────────────────────────────────────

class ConnectionPath(QGraphicsPathItem):
    """Bezier curve connecting an output port to an input port."""

    def __init__(self, src_node: NodeItem, src_idx: int,
                 dst_node: NodeItem, dst_idx: int):
        super().__init__()
        self.src_node = src_node
        self.src_idx = src_idx
        self.dst_node = dst_node
        self.dst_idx = dst_idx

        pen = QPen(_C["port_in"], 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(0)
        self.update_path()

    def _port_scene_pos(self, node: NodeItem, is_output: bool, idx: int) -> QPointF:
        ports = node.output_ports if is_output else node.input_ports
        if idx < len(ports):
            return ports[idx].scenePos()
        # fallback: center
        br = node.boundingRect()
        x = node.scenePos().x() + (br.width() if is_output else 0)
        y = node.scenePos().y() + br.height() / 2
        return QPointF(x, y)

    def update_path(self):
        src = self._port_scene_pos(self.src_node, True, self.src_idx)
        dst = self._port_scene_pos(self.dst_node, False, self.dst_idx)

        dx = max(abs(dst.x() - src.x()) * 0.5, 80)
        path = QPainterPath(src)
        path.cubicTo(
            QPointF(src.x() + dx, src.y()),
            QPointF(dst.x() - dx, dst.y()),
            dst
        )
        self.setPath(path)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isSelected()
        pen = QPen(_C["node_sel"] if selected else _C["port_in"],
                   3 if selected else 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())


# ── Temp connection line (while dragging) ─────────────────────────────────────

class TempConnection(QGraphicsPathItem):
    def __init__(self):
        super().__init__()
        pen = QPen(_C["port_out"], 2, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setZValue(10)

    def update_line(self, src: QPointF, dst: QPointF):
        dx = max(abs(dst.x() - src.x()) * 0.5, 60)
        path = QPainterPath(src)
        path.cubicTo(
            QPointF(src.x() + dx, src.y()),
            QPointF(dst.x() - dx, dst.y()),
            dst
        )
        self.setPath(path)


# ── Main canvas ───────────────────────────────────────────────────────────────

class WorkflowCanvas(QGraphicsView):
    node_added      = pyqtSignal(object)          # Node
    node_selected   = pyqtSignal(object)          # Node | None
    connection_added = pyqtSignal(str, str)       # src_id, dst_id

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._scene.setSceneRect(-2000, -2000, 6000, 6000)
        self._scene.setBackgroundBrush(QBrush(_C["bg"]))

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.node_items: Dict[str, NodeItem] = {}
        self.connections: List[ConnectionPath] = []

        self._drag_port: Optional[PortItem] = None
        self._temp_conn: Optional[TempConnection] = None

        self.setStyleSheet("background: #09090f; border: none;")

    # ── dot grid background ───────────────────────────────────────────────────

    def drawBackground(self, painter: QPainter, rect):
        super().drawBackground(painter, rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        grid_minor = 20
        grid_major = 100

        left = int(rect.left()) - (int(rect.left()) % grid_minor)
        top  = int(rect.top())  - (int(rect.top())  % grid_minor)

        # minor dots
        painter.setPen(QPen(_C["grid_minor"], 0.5))
        x = left
        while x < rect.right():
            y = top
            while y < rect.bottom():
                if (x % grid_major != 0) or (y % grid_major != 0):
                    painter.drawPoint(QPointF(x, y))
                y += grid_minor
            x += grid_minor

        # major dots
        painter.setPen(QPen(_C["grid_major"], 1.5))
        x = left - (left % grid_major)
        while x < rect.right():
            y = top - (top % grid_major)
            while y < rect.bottom():
                painter.drawPoint(QPointF(x, y))
                y += grid_major
            x += grid_major

    # ── public API ────────────────────────────────────────────────────────────

    def add_node(self, node: Node) -> NodeItem:
        # Default position near canvas center if unset
        if node.x == 0 and node.y == 0:
            center = self.mapToScene(self.viewport().rect().center())
            node.x = int(center.x()) + len(self.node_items) * 40 - 200
            node.y = int(center.y()) - 60
        item = NodeItem(node)
        self._scene.addItem(item)
        self.node_items[node.node_id] = item
        self.node_added.emit(node)
        return item

    def remove_node(self, node_id: str):
        if node_id not in self.node_items:
            return
        item = self.node_items.pop(node_id)
        to_remove = [c for c in self.connections
                     if c.src_node is item or c.dst_node is item]
        for c in to_remove:
            self.connections.remove(c)
            self._scene.removeItem(c)
        self._scene.removeItem(item)

    def add_connection(self, source_id: str, target_id: str,
                       src_port: int = 0, dst_port: int = 0):
        if source_id not in self.node_items or target_id not in self.node_items:
            return
        src = self.node_items[source_id]
        dst = self.node_items[target_id]
        # Prevent duplicate connections on the same ports
        for existing in self.connections:
            if (existing.src_node is src and existing.dst_node is dst
                    and existing.src_idx == src_port and existing.dst_idx == dst_port):
                return
        conn = ConnectionPath(src, src_port, dst, dst_port)
        self._scene.addItem(conn)
        self.connections.append(conn)
        self.connection_added.emit(source_id, target_id)

    def get_workflow_data(self) -> dict:
        nodes = [item.node.to_dict() for item in self.node_items.values()]
        conns = [{"source_id": c.src_node.node.node_id,
                  "target_id": c.dst_node.node.node_id,
                  "src_port":  c.src_idx,
                  "dst_port":  c.dst_idx} for c in self.connections]
        return {"nodes": nodes, "connections": conns}

    def load_workflow_data(self, data: dict):
        for nid in list(self.node_items.keys()):
            self.remove_node(nid)
        self.node_selected.emit(None)
        from flowstate.nodes import Node
        for nd in data.get("nodes", []):
            self.add_node(Node.from_dict(nd))
        for cd in data.get("connections", []):
            self.add_connection(cd["source_id"], cd["target_id"],
                                cd.get("src_port", 0), cd.get("dst_port", 0))

    # ── mouse events ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, PortItem) and item.is_output:
                self._drag_port = item
                self._temp_conn = TempConnection()
                self._scene.addItem(self._temp_conn)
                src = item.scenePos()
                self._temp_conn.update_line(src, self.mapToScene(event.pos()))
                return
        super().mousePressEvent(event)
        # emit selection signal
        sel = self._scene.selectedItems()
        if sel and isinstance(sel[0], NodeItem):
            self.node_selected.emit(sel[0].node)
        else:
            self.node_selected.emit(None)

    def mouseMoveEvent(self, event):
        if self._drag_port and self._temp_conn:
            src = self._drag_port.scenePos()
            dst = self.mapToScene(event.pos())
            self._temp_conn.update_line(src, dst)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_port and self._temp_conn:
            self._scene.removeItem(self._temp_conn)
            self._temp_conn = None
            item = self.itemAt(event.pos())
            if isinstance(item, PortItem) and not item.is_output:
                src_node = self._drag_port.node_item
                dst_node = item.node_item
                if src_node is not dst_node:
                    self.add_connection(src_node.node.node_id, dst_node.node.node_id,
                                        self._drag_port.index, item.index)
            self._drag_port = None
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            had_node = any(isinstance(i, NodeItem) for i in self._scene.selectedItems())
            for item in self._scene.selectedItems():
                if isinstance(item, NodeItem):
                    self.remove_node(item.node.node_id)
                elif isinstance(item, ConnectionPath):
                    self.connections.remove(item)
                    self._scene.removeItem(item)
            if had_node:
                self.node_selected.emit(None)
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
