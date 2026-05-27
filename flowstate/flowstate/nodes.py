"""Node definitions for FlowState workflow orchestrator."""

from enum import Enum
from typing import Dict, Any, Optional, List
import json


class NodeType(Enum):
    TRIGGER = "trigger"
    ACTION = "action"
    CONDITION = "condition"
    OUTPUT = "output"


class Node:
    """Base class for all nodes in the workflow."""
    
    def __init__(self, node_id: str, node_type: NodeType, title: str, 
                 x: int = 0, y: int = 0):
        self.node_id = node_id
        self.node_type = node_type
        self.title = title
        self.x = x
        self.y = y
        self.inputs: List[Dict[str, Any]] = []
        self.outputs: List[Dict[str, Any]] = []
        self.properties: Dict[str, Any] = {}
        
    def add_input(self, name: str, data_type: str, required: bool = False):
        """Add an input to the node."""
        self.inputs.append({
            "name": name,
            "type": data_type,
            "required": required
        })
        
    def add_output(self, name: str, data_type: str):
        """Add an output to the node."""
        self.outputs.append({
            "name": name,
            "type": data_type
        })
        
    def set_property(self, key: str, value: Any):
        """Set a property for the node."""
        self.properties[key] = value
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "properties": self.properties
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """Create node from dictionary representation."""
        node = cls(
            data["node_id"],
            NodeType(data["node_type"]),
            data["title"],
            data["x"],
            data["y"]
        )
        node.inputs = data.get("inputs", [])
        node.outputs = data.get("outputs", [])
        node.properties = data.get("properties", {})
        return node


class TriggerNode(Node):
    """Node that triggers a workflow."""
    
    def __init__(self, node_id: str, title: str, x: int = 0, y: int = 0):
        super().__init__(node_id, NodeType.TRIGGER, title, x, y)


class ActionNode(Node):
    """Node that performs an action."""
    
    def __init__(self, node_id: str, title: str, x: int = 0, y: int = 0):
        super().__init__(node_id, NodeType.ACTION, title, x, y)


class ConditionNode(Node):
    """Node that evaluates a condition."""
    
    def __init__(self, node_id: str, title: str, x: int = 0, y: int = 0):
        super().__init__(node_id, NodeType.CONDITION, title, x, y)
        self.add_output("true", "boolean")
        self.add_output("false", "boolean")


class OutputNode(Node):
    """Node that outputs data."""
    
    def __init__(self, node_id: str, title: str, x: int = 0, y: int = 0):
        super().__init__(node_id, NodeType.OUTPUT, title, x, y)


# Predefined node types
PREDEFINED_NODES = {
    "file_trigger": {
        "name": "File Trigger",
        "type": NodeType.TRIGGER,
        "description": "Triggers when a file is created or modified",
        "inputs": [],
        "outputs": [{"name": "file_path", "type": "string"}],
        "properties": {"path": "", "event": "modified"}
    },
    "excel_reader": {
        "name": "Excel Reader",
        "type": NodeType.ACTION,
        "description": "Reads data from an Excel file",
        "inputs": [{"name": "file_path", "type": "string"}],
        "outputs": [{"name": "data", "type": "dict"}],
        "properties": {"sheet_name": "Sheet1"}
    },
    "email_sender": {
        "name": "Email Sender",
        "type": NodeType.ACTION,
        "description": "Sends an email",
        "inputs": [{"name": "recipient", "type": "string"}, 
                  {"name": "subject", "type": "string"},
                  {"name": "body", "type": "string"}],
        "outputs": [{"name": "status", "type": "boolean"}],
        "properties": {"smtp_server": "smtp.gmail.com", "port": 587}
    },
    "google_drive_uploader": {
        "name": "Google Drive Uploader",
        "type": NodeType.ACTION,
        "description": "Uploads a file to Google Drive",
        "inputs": [{"name": "file_path", "type": "string"}],
        "outputs": [{"name": "file_id", "type": "string"}],
        "properties": {"folder_id": ""}
    },
    "condition": {
        "name": "Condition",
        "type": NodeType.CONDITION,
        "description": "Evaluates a condition",
        "inputs": [{"name": "value1", "type": "any"},
                   {"name": "value2", "type": "any"}],
        "outputs": [{"name": "true", "type": "boolean"},
                    {"name": "false", "type": "boolean"}],
        "properties": {"operator": "==", "value": ""}
    },
    "file_output": {
        "name": "File Output",
        "type": NodeType.OUTPUT,
        "description": "Writes data to a file",
        "inputs": [{"name": "data", "type": "any"},
                   {"name": "file_path", "type": "string"}],
        "outputs": [],
        "properties": {"path": "", "format": "json"}
    }
}