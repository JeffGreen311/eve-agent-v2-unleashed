"""
DJ Mixer Control Tools
======================
Eve Agent tools for controlling the SolForge DJ mixer via WebSocket.
Commands are relayed through server.py to the browser-based DJ mixer HTML,
which handles Web MIDI communication with the Numark Mixtrack Platinum FX.

Architecture:
  Eve Agent (tool call) → server.py WebSocket relay → DJ Mixer HTML → Web MIDI → Hardware
"""

import json
import logging
import asyncio
from typing import Any, Dict, Optional, Set

from .base import Tool

logger = logging.getLogger(__name__)

# Consistent error when no browser has the DJ mixer open
_NO_CLIENT_MSG = (
    "DJ mixer not connected. The user needs to open the DJ tab in Eve Portal "
    "(or pop it out to a new window). The DJ mixer runs in the browser — "
    "there is no backend DJ service to start. Once the page is open, "
    "it auto-connects via WebSocket and you can send commands."
)


class DJMixerBroadcaster:
    """Manages WebSocket connections to DJ mixer browser clients."""

    def __init__(self):
        self.clients: Set = set()
        self._state = {
            "deckA": {"playing": False, "bpm": 0, "trackName": "", "volume": 1.0},
            "deckB": {"playing": False, "bpm": 0, "trackName": "", "volume": 1.0},
            "crossfader": 0.5,
        }

    async def broadcast(self, msg: dict):
        """Send a command to all connected DJ mixer clients."""
        if not self.clients:
            logger.warning("No DJ mixer clients connected")
            return False
        data = json.dumps(msg)
        dead = set()
        for ws in self.clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self.clients -= dead
        return len(self.clients) > 0

    def update_state(self, state: dict):
        """Update tracked deck state from browser."""
        self._state.update(state)

    @property
    def state(self):
        return dict(self._state)

    @property
    def connected(self):
        return len(self.clients) > 0


# Singleton broadcaster — shared between tools and WebSocket endpoints
dj_broadcaster = DJMixerBroadcaster()


class DJControlTool(Tool):
    """Control DJ mixer decks: play, pause, cue, sync, load tracks."""
    name = "dj_control"
    description = (
        "Control the SolForge DJ mixer. Send transport commands to decks. "
        "Commands: play, pause, cue, sync, load_track. "
        "Use deck 'A' (Deck 1) or 'B' (Deck 2). "
        "For load_track, the currently selected library track is loaded."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "deck": {
                    "type": "string",
                    "description": "Deck 'A' (left/Deck 1) or 'B' (right/Deck 2)",
                    "enum": ["A", "B"],
                },
                "command": {
                    "type": "string",
                    "description": "Transport command",
                    "enum": ["play", "pause", "cue", "sync", "load_track"],
                },
            },
            "required": ["deck", "command"],
        }

    async def execute(self, deck: str = "A", command: str = "play", **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        msg = {"type": "dj_command", "command": command, "deck": dk}
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "action": command, "deck": deck.upper()}


class DJMixerTool(Tool):
    """Adjust DJ mixer levels: volume, EQ, filter, crossfader, gain."""
    name = "dj_mixer"
    description = (
        "Adjust DJ mixer levels. Set volume (0-1), EQ bands (hi/mid/lo, -12 to +12 dB), "
        "filter (-100 to +100, negative=LP, positive=HP), crossfader (0=A, 1=B), "
        "pitch (-8 to +8 percent)."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "deck": {
                    "type": "string",
                    "description": "Deck 'A' or 'B' (not needed for crossfader)",
                    "enum": ["A", "B"],
                },
                "control": {
                    "type": "string",
                    "description": "What to adjust",
                    "enum": ["volume", "eq_hi", "eq_mid", "eq_lo", "filter", "crossfader", "pitch", "gain"],
                },
                "value": {
                    "type": "number",
                    "description": "Value to set (range depends on control type)",
                },
            },
            "required": ["control", "value"],
        }

    async def execute(self, control: str = "volume", value: float = 0, deck: str = "A", **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        msg = {"type": "dj_command", "command": "set_" + control, "deck": dk, "value": value}
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "control": control, "value": value, "deck": deck.upper()}


class DJFxTool(Tool):
    """Toggle DJ effects and adjust FX wet/dry mix."""
    name = "dj_fx"
    description = (
        "Toggle DJ effects on/off or adjust FX parameters. "
        "8 FX slots per deck: 0=ECHO, 1=REVERB, 2=FLANGER, 3=PHASER, "
        "4=DISTORTION, 5=BITCRUSHER, 6=CHORUS, 7=GATE. "
        "Use command 'toggle_fx' with slot number, or 'set_fx_wet' with value 0-1."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "deck": {"type": "string", "enum": ["A", "B"]},
                "command": {
                    "type": "string",
                    "enum": ["toggle_fx", "set_fx_wet", "set_echo_time", "set_reverb_size", "set_phaser_rate"],
                },
                "slot": {
                    "type": "integer",
                    "description": "FX slot 0-7 (for toggle_fx)",
                },
                "value": {
                    "type": "number",
                    "description": "Parameter value (0-1 for wet, 50-1000ms for echo, etc.)",
                },
            },
            "required": ["deck", "command"],
        }

    async def execute(self, deck: str = "A", command: str = "toggle_fx",
                      slot: int = None, value: float = None, **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        msg = {"type": "dj_command", "command": command, "deck": dk}
        if slot is not None:
            msg["slot"] = slot
        if value is not None:
            msg["value"] = value
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "command": command, "deck": deck.upper(), "slot": slot, "value": value}


class DJHotCueTool(Tool):
    """Set, trigger, or clear hot cues on DJ decks."""
    name = "dj_hotcue"
    description = (
        "Manage hot cues on DJ decks. Trigger (jump to) a cue, or clear it. "
        "4 hot cues per deck (0-3). Triggering an unset cue sets it at current position."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "deck": {"type": "string", "enum": ["A", "B"]},
                "action": {"type": "string", "enum": ["trigger", "clear"]},
                "cue": {"type": "integer", "description": "Hot cue index 0-3"},
            },
            "required": ["deck", "action", "cue"],
        }

    async def execute(self, deck: str = "A", action: str = "trigger", cue: int = 0, **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        cmd = "trigger_hotcue" if action == "trigger" else "clear_hotcue"
        msg = {"type": "dj_command", "command": cmd, "deck": dk, "cue": cue}
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "action": action, "deck": deck.upper(), "cue": cue}


class DJLoopTool(Tool):
    """Control loops on DJ decks."""
    name = "dj_loop"
    description = (
        "Control loops on DJ decks. "
        "Commands: loop_in, loop_out, toggle_loop, halve_loop, double_loop, "
        "auto_loop (set loop at current position for N beats: 1, 2, 4, or 8)."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "deck": {"type": "string", "enum": ["A", "B"]},
                "command": {
                    "type": "string",
                    "enum": ["loop_in", "loop_out", "toggle_loop", "halve_loop", "double_loop", "auto_loop"],
                },
                "beats": {
                    "type": "integer",
                    "description": "For auto_loop: 1, 2, 4, or 8 beats",
                },
            },
            "required": ["deck", "command"],
        }

    async def execute(self, deck: str = "A", command: str = "toggle_loop",
                      beats: int = None, **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        msg = {"type": "dj_command", "command": command, "deck": dk}
        if beats is not None:
            msg["beats"] = beats
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "command": command, "deck": deck.upper(), "beats": beats}


class DJTransitionTool(Tool):
    """Perform DJ transitions: smooth crossfade, drop cut, echo out."""
    name = "dj_transition"
    description = (
        "Perform compound DJ transitions between decks. "
        "Types: 'smooth' (gradual crossfade), 'drop' (bass-cut snap), "
        "'echo_out' (echo fade on outgoing deck)."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["smooth", "drop", "echo_out"],
                    "description": "Transition type",
                },
                "from_deck": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "Outgoing deck",
                },
                "duration": {
                    "type": "number",
                    "description": "Duration in seconds (for smooth transition, default 4)",
                },
            },
            "required": ["type", "from_deck"],
        }

    async def execute(self, type: str = "smooth", from_deck: str = "A",
                      duration: float = 4.0, **kwargs) -> Dict[str, Any]:
        dk = 0 if from_deck.upper() == "A" else 1
        msg = {
            "type": "dj_command",
            "command": "transition",
            "transition_type": type,
            "from_deck": dk,
            "duration": duration,
        }
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        to_deck = "B" if from_deck.upper() == "A" else "A"
        return {"success": True, "transition": type, "from": from_deck.upper(), "to": to_deck, "duration": duration}


class DJStateTool(Tool):
    """Get current state of the DJ mixer."""
    name = "dj_state"
    description = (
        "Get the current state of the DJ mixer: what's playing on each deck, "
        "BPM, track names, volume levels, crossfader position, effects enabled."
    )

    def get_parameters(self) -> Dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> Dict[str, Any]:
        state = dj_broadcaster.state
        state["connected"] = dj_broadcaster.connected
        state["clients"] = len(dj_broadcaster.clients)
        if not dj_broadcaster.connected:
            state["hint"] = _NO_CLIENT_MSG
        return {"success": True, **state}


class DJBrowseTool(Tool):
    """Browse and navigate the DJ music library."""
    name = "dj_browse"
    description = (
        "Browse the music library in the DJ mixer. "
        "Commands: 'navigate' (enter directory), 'back' (go up), "
        "'select' (select a file by index), 'load' (load selected to deck)."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["navigate", "back", "select", "load"],
                },
                "path": {
                    "type": "string",
                    "description": "Directory path (for navigate)",
                },
                "index": {
                    "type": "integer",
                    "description": "Item index in library list (for select)",
                },
                "deck": {
                    "type": "string",
                    "enum": ["A", "B"],
                    "description": "Target deck (for load)",
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str = "navigate", path: str = None,
                      index: int = None, deck: str = "A", **kwargs) -> Dict[str, Any]:
        dk = 0 if deck.upper() == "A" else 1
        msg = {"type": "dj_command", "command": "browse_" + command, "deck": dk}
        if path:
            msg["path"] = path
        if index is not None:
            msg["index"] = index
        sent = await dj_broadcaster.broadcast(msg)
        if not sent:
            return {"success": False, "error": _NO_CLIENT_MSG}
        return {"success": True, "browse": command, "path": path, "deck": deck.upper()}
