#!/usr/bin/env python3
"""
Session Management for EveUnleashed

Provides persistent session storage with:
- SQLite database for metadata and search
- JSONL files for append-only message history
- Full-text search across sessions
- Session branching and resume capabilities
"""

import os
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager


class SessionManager:
    """
    Manages persistent sessions with SQLite + JSONL storage.
    
    Storage structure:
        ~/.eve_unleashed/sessions/
        ├── sessions.db           # SQLite metadata
        └── {uuid}/
            └── messages.jsonl    # Append-only message log
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path.home() / ".eve_unleashed")
        self.sessions_dir = self.base_dir / "sessions"
        self.db_path = self.sessions_dir / "sessions.db"
        
        # Ensure directories exist
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
        
        # Current active session
        self.current_session_id: Optional[str] = None
        self._message_count = 0
    
    @contextmanager
    def _get_db(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize the SQLite database schema"""
        with self._get_db() as conn:
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT,
                    summary TEXT,
                    project_path TEXT,
                    model TEXT,
                    message_count INTEGER DEFAULT 0,
                    token_count INTEGER DEFAULT 0,
                    parent_session_id TEXT,
                    branch_point INTEGER,
                    tags TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Messages table (for search indexing, not primary storage)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_calls TEXT,
                    tool_results TEXT,
                    timestamp TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id 
                ON messages(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated 
                ON sessions(updated_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_status 
                ON sessions(status)
            """)
            
            # Full-text search virtual table
            # Check if FTS table exists before creating
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='messages_fts'
            """)
            if not cursor.fetchone():
                conn.execute("""
                    CREATE VIRTUAL TABLE messages_fts USING fts5(
                        content,
                        session_id UNINDEXED,
                        content='messages',
                        content_rowid='id'
                    )
                """)
                # Triggers for FTS sync
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                        INSERT INTO messages_fts(rowid, content, session_id) 
                        VALUES (new.id, new.content, new.session_id);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                        INSERT INTO messages_fts(messages_fts, rowid, content, session_id) 
                        VALUES('delete', old.id, old.content, old.session_id);
                    END
                """)
    
    def create_session(
        self, 
        project_path: Optional[str] = None, 
        model: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        branch_point: Optional[int] = None
    ) -> str:
        """
        Create a new session.
        
        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid.uuid4())[:8]  # Use short UUID for readability
        now = datetime.now().isoformat()
        
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO sessions 
                (id, created_at, updated_at, project_path, model, parent_session_id, branch_point)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, now, now, project_path, model, parent_session_id, branch_point))
        
        # Create session directory
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Create empty messages file
        (session_dir / "messages.jsonl").touch()
        
        self.current_session_id = session_id
        self._message_count = 0
        
        return session_id
    
    def save_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_results: Optional[List[Dict]] = None,
        token_count: int = 0,
        session_id: Optional[str] = None
    ) -> int:
        """
        Save a message to the current session.
        
        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            tool_calls: Optional tool call data
            tool_results: Optional tool result data
            token_count: Estimated token count
            session_id: Optional session ID (uses current if not provided)
            
        Returns:
            Message index in session
        """
        sid = session_id or self.current_session_id
        if not sid:
            raise ValueError("No active session. Create one first.")
        
        now = datetime.now().isoformat()
        
        # Append to JSONL file
        message_data = {
            "role": role,
            "content": content,
            "timestamp": now,
            "token_count": token_count
        }
        if tool_calls:
            message_data["tool_calls"] = tool_calls
        if tool_results:
            message_data["tool_results"] = tool_results
        
        jsonl_path = self.sessions_dir / sid / "messages.jsonl"
        with open(jsonl_path, 'a') as f:
            f.write(json.dumps(message_data) + '\n')
        
        # Also store in SQLite for search
        with self._get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO messages 
                (session_id, role, content, tool_calls, tool_results, timestamp, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                sid, role, content,
                json.dumps(tool_calls) if tool_calls else None,
                json.dumps(tool_results) if tool_results else None,
                now, token_count
            ))
            message_id = cursor.lastrowid
            
            # Update session metadata
            conn.execute("""
                UPDATE sessions 
                SET updated_at = ?, message_count = message_count + 1, token_count = token_count + ?
                WHERE id = ?
            """, (now, token_count, sid))
        
        self._message_count += 1
        
        # Auto-generate title after 3 messages
        if self._message_count == 3:
            self._auto_generate_title(sid)
        
        return message_id
    
    def _auto_generate_title(self, session_id: str):
        """Generate a title from the first user message"""
        messages = self.load_messages(session_id, limit=5)
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Take first 50 chars or first sentence
                title = content[:50].split('\n')[0]
                if len(title) < len(content):
                    title = title.rstrip('.!?') + "..."
                self.update_title(session_id, title)
                break
    
    def load_messages(
        self, 
        session_id: Optional[str] = None, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Load messages from a session's JSONL file.
        
        Args:
            session_id: Session ID (uses current if not provided)
            limit: Maximum messages to return
            offset: Number of messages to skip
            
        Returns:
            List of message dictionaries
        """
        sid = session_id or self.current_session_id
        if not sid:
            return []
        
        jsonl_path = self.sessions_dir / sid / "messages.jsonl"
        if not jsonl_path.exists():
            return []
        
        messages = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
        
        # Apply offset and limit
        if offset:
            messages = messages[offset:]
        if limit:
            messages = messages[:limit]
        
        return messages
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a session and set it as current.
        
        Returns:
            Session metadata dict or None if not found
        """
        with self._get_db() as conn:
            cursor = conn.execute("""
                SELECT * FROM sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            self.current_session_id = session_id
            self._message_count = row['message_count'] or 0
            
            return dict(row)
    
    def list_sessions(
        self, 
        limit: int = 10, 
        status: str = 'active',
        project_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List recent sessions.
        
        Args:
            limit: Maximum sessions to return
            status: Filter by status (active, archived, deleted)
            project_path: Filter by project path
            
        Returns:
            List of session metadata dicts
        """
        with self._get_db() as conn:
            query = "SELECT * FROM sessions WHERE status = ?"
            params: List[Any] = [status]
            
            if project_path:
                query += " AND project_path = ?"
                params.append(project_path)
            
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def search_sessions(
        self, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Full-text search across all sessions.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of dicts with session_id, content snippet, and metadata
        """
        results = []
        
        with self._get_db() as conn:
            # Search using FTS5
            cursor = conn.execute("""
                SELECT 
                    m.session_id,
                    m.role,
                    snippet(messages_fts, 0, '>>>', '<<<', '...', 32) as snippet,
                    m.timestamp,
                    s.title,
                    s.project_path
                FROM messages_fts
                JOIN messages m ON messages_fts.rowid = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            for row in cursor.fetchall():
                results.append({
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "snippet": row["snippet"],
                    "timestamp": row["timestamp"],
                    "title": row["title"],
                    "project_path": row["project_path"]
                })
        
        return results
    
    def update_title(self, session_id: str, title: str):
        """Update session title"""
        with self._get_db() as conn:
            conn.execute("""
                UPDATE sessions SET title = ?, updated_at = ?
                WHERE id = ?
            """, (title, datetime.now().isoformat(), session_id))
    
    def update_status(self, session_id: str, status: str):
        """Update session status (active, archived, deleted)"""
        with self._get_db() as conn:
            conn.execute("""
                UPDATE sessions SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, datetime.now().isoformat(), session_id))
    
    def branch_session(
        self, 
        session_id: Optional[str] = None, 
        at_message: Optional[int] = None
    ) -> str:
        """
        Create a new session branched from an existing one.
        
        Args:
            session_id: Session to branch from (uses current if not provided)
            at_message: Message index to branch at (uses latest if not provided)
            
        Returns:
            New session ID
        """
        sid = session_id or self.current_session_id
        if not sid:
            raise ValueError("No session to branch from")
        
        # Get original session info
        original = self.load_session(sid)
        if not original:
            raise ValueError(f"Session not found: {sid}")
        
        # Load messages up to branch point
        messages = self.load_messages(sid)
        if at_message is not None:
            messages = messages[:at_message]
        
        branch_point = len(messages)
        
        # Create new session
        new_session_id = self.create_session(
            project_path=original.get("project_path"),
            model=original.get("model"),
            parent_session_id=sid,
            branch_point=branch_point
        )
        
        # Copy messages to new session
        for msg in messages:
            self.save_message(
                role=msg["role"],
                content=msg.get("content", ""),
                tool_calls=msg.get("tool_calls"),
                tool_results=msg.get("tool_results"),
                token_count=msg.get("token_count", 0),
                session_id=new_session_id
            )
        
        # Update title
        if original.get("title"):
            self.update_title(new_session_id, f"{original['title']} (branch)")
        
        return new_session_id
    
    def get_session_info(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get session metadata"""
        sid = session_id or self.current_session_id
        if not sid:
            return None
        
        with self._get_db() as conn:
            cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def export_session(
        self, 
        session_id: Optional[str] = None, 
        format: str = "markdown"
    ) -> str:
        """
        Export a session to markdown or JSON.
        
        Args:
            session_id: Session to export
            format: Export format (markdown, json)
            
        Returns:
            Exported content as string
        """
        sid = session_id or self.current_session_id
        if not sid:
            raise ValueError("No session to export")
        
        info = self.get_session_info(sid)
        messages = self.load_messages(sid)
        
        if format == "json":
            return json.dumps({
                "session": info,
                "messages": messages
            }, indent=2)
        
        # Markdown format
        lines = []
        lines.append(f"# Session: {info.get('title') or sid}")
        lines.append(f"\n**Created**: {info.get('created_at')}")
        lines.append(f"**Project**: {info.get('project_path') or 'N/A'}")
        lines.append(f"**Model**: {info.get('model') or 'N/A'}")
        lines.append(f"**Messages**: {info.get('message_count', 0)}")
        lines.append("\n---\n")
        
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")[:19]  # Trim microseconds
            
            lines.append(f"## {role} ({timestamp})")
            lines.append(f"\n{content}\n")
            
            if msg.get("tool_calls"):
                lines.append("**Tool Calls:**")
                lines.append(f"```json\n{json.dumps(msg['tool_calls'], indent=2)}\n```\n")
        
        return "\n".join(lines)
    
    def get_most_recent_session(self) -> Optional[str]:
        """Get the most recent active session ID"""
        sessions = self.list_sessions(limit=1)
        if sessions:
            return sessions[0]["id"]
        return None
    
    def delete_session(self, session_id: str, hard: bool = False):
        """
        Delete a session.
        
        Args:
            session_id: Session to delete
            hard: If True, permanently delete. If False, soft delete (mark as deleted).
        """
        if hard:
            # Remove from database
            with self._get_db() as conn:
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            
            # Remove session directory
            session_dir = self.sessions_dir / session_id
            if session_dir.exists():
                import shutil
                shutil.rmtree(session_dir)
        else:
            # Soft delete
            self.update_status(session_id, "deleted")
    
    @property
    def short_id(self) -> str:
        """Get short display ID for current session"""
        if self.current_session_id:
            return self.current_session_id[:6]
        return ""
