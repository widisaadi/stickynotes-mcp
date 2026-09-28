"""Microsoft Sticky Notes MCP Server.
Provides full CRUD, search, stats, and export access to Windows Sticky Notes (plum.sqlite).
Compatible with Claude Desktop, Cursor, Hermes, Roo-Code, Windsurf, and any MCP client.
"""

import json
import os
import re
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

# .NET DateTime.Ticks epoch (0001-01-01 00:00:00 UTC)
TICKS_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)

# Standard Windows UWP Sticky Notes database location
DEFAULT_DB_PATH = Path(os.path.expandvars(
    r"%LOCALAPPDATA%\Packages\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe\LocalState\plum.sqlite"
))

# Valid Sticky Notes theme colors
VALID_THEMES = {"Yellow", "Green", "Pink", "Purple", "Blue", "Grey", "Charcoal"}

# ponytail: simple regex cleaner, handles 99% sticky format without bloated RTF parser
RE_LINE_ID = re.compile(r"^\\id=[a-f0-9-]+\s?", re.IGNORECASE)
RE_LIST_ITEM = re.compile(r"^\\l\s?", re.IGNORECASE)
RE_EXTRA_TAGS = re.compile(r"\\[a-zA-Z0-9]+", re.IGNORECASE)


def get_db_path() -> Path:
    """Resolve database path from environment variable or standard location."""
    env_path = os.getenv("STICKY_NOTES_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def ticks_to_iso(ticks: Optional[int]) -> Optional[str]:
    """Convert .NET DateTime.Ticks bigint to ISO 8601 UTC string."""
    if not ticks:
        return None
    try:
        dt = TICKS_EPOCH + timedelta(microseconds=ticks // 10)
        return dt.isoformat()
    except Exception:
        return str(ticks)


def now_ticks() -> int:
    """Current UTC timestamp as .NET DateTime.Ticks."""
    now = datetime.now(timezone.utc)
    return int((now - TICKS_EPOCH).total_seconds() * 10_000_000)


def clean_text(raw_text: Optional[str]) -> str:
    """Clean Sticky Notes RTF/block markup into readable Markdown."""
    if not raw_text:
        return ""
    lines = []
    for line in raw_text.splitlines():
        line = RE_LINE_ID.sub("", line)
        line = RE_LIST_ITEM.sub("- ", line)
        line = line.replace(r"\l0", "")
        line = line.replace(r"\b0", "**").replace(r"\b ", "**").replace(r"\b", "**")
        line = line.replace(r"\strike0", "~~").replace(r"\strike ", "~~").replace(r"\strike", "~~")
        line = line.replace(r"\i0", "*").replace(r"\i ", "*").replace(r"\i", "*")
        line = RE_EXTRA_TAGS.sub("", line)
        lines.append(line)
    return "\n".join(lines).strip()


def to_sticky_format(text: str) -> str:
    """Format plain multiline text into Sticky Notes paragraph block IDs."""
    lines = text.splitlines() if text else [""]
    formatted = []
    for line in lines:
        line_id = str(uuid.uuid4())
        formatted.append(f"\\id={line_id} {line}")
    return "\n".join(formatted)


def get_ro_connection() -> sqlite3.Connection:
    """Open read-only SQLite connection. Non-blocking with active Sticky Notes."""
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Sticky Notes database not found at: {db_path}")
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_rw_connection() -> sqlite3.Connection:
    """Open read-write SQLite connection with automatic backup before mutations."""
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Sticky Notes database not found at: {db_path}")

    # Automatic backup before mutation
    backup_path = db_path.with_name("plum.sqlite.mcp.bak")
    try:
        shutil.copy2(db_path, backup_path)
    except Exception:
        pass

    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


app = MCPServer(
    name="sticky-notes-mcp",
    version="1.0.0",
    description="MCP server for Windows Microsoft Sticky Notes"
)


@app.tool()
def list_notes(
    limit: int = 50,
    offset: int = 0,
    theme: Optional[str] = None,
    is_open: Optional[bool] = None,
    include_deleted: bool = False
) -> List[Dict[str, Any]]:
    """List Microsoft Sticky Notes with summary metadata, theme, and text preview.

    Args:
        limit: Maximum number of notes to return (default: 50).
        offset: Pagination offset (default: 0).
        theme: Filter by theme color (Yellow, Green, Pink, Purple, Blue, Grey, Charcoal).
        is_open: Filter by open/closed status on desktop.
        include_deleted: Include soft-deleted notes (default: False).
    """
    conn = get_ro_connection()
    try:
        c = conn.cursor()
        clauses = []
        params: List[Any] = []

        if not include_deleted:
            clauses.append("DeletedAt IS NULL")
        if theme:
            clauses.append("LOWER(Theme) = LOWER(?)")
            params.append(theme)
        if is_open is not None:
            clauses.append("IsOpen = ?")
            params.append(1 if is_open else 0)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT Id, Text, Theme, IsOpen, IsAlwaysOnTop, CreatedAt, UpdatedAt, DeletedAt
            FROM Note
            {where_sql}
            ORDER BY UpdatedAt DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        c.execute(query, tuple(params))
        rows = c.fetchall()
        results = []
        for r in rows:
            raw = r["Text"] or ""
            cleaned = clean_text(raw)
            preview = cleaned.split("\n")[0][:100] if cleaned else "(Empty Note)"
            results.append({
                "id": r["Id"],
                "preview": preview,
                "theme": r["Theme"] or "Yellow",
                "is_open": bool(r["IsOpen"]),
                "is_always_on_top": bool(r["IsAlwaysOnTop"]),
                "created_at": ticks_to_iso(r["CreatedAt"]),
                "updated_at": ticks_to_iso(r["UpdatedAt"]),
                "is_deleted": r["DeletedAt"] is not None
            })
        return results
    finally:
        conn.close()


@app.tool()
def get_note(note_id: str) -> Dict[str, Any]:
    """Get full content and details of a single Sticky Note by its UUID.

    Args:
        note_id: The UUID of the sticky note.
    """
    conn = get_ro_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT Id, Text, Theme, IsOpen, IsAlwaysOnTop, WindowPosition,
                   CreatedAt, UpdatedAt, DeletedAt, ParentId
            FROM Note
            WHERE Id = ?
        """, (note_id,))
        r = c.fetchone()
        if not r:
            return {"error": f"Note not found with ID: {note_id}"}

        raw = r["Text"] or ""
        return {
            "id": r["Id"],
            "text": clean_text(raw),
            "text_raw": raw,
            "theme": r["Theme"] or "Yellow",
            "is_open": bool(r["IsOpen"]),
            "is_always_on_top": bool(r["IsAlwaysOnTop"]),
            "created_at": ticks_to_iso(r["CreatedAt"]),
            "updated_at": ticks_to_iso(r["UpdatedAt"]),
            "deleted_at": ticks_to_iso(r["DeletedAt"]),
            "is_deleted": r["DeletedAt"] is not None
        }
    finally:
        conn.close()


@app.tool()
def search_notes(
    query: str,
    limit: int = 50,
    include_deleted: bool = False
) -> List[Dict[str, Any]]:
    """Search Sticky Notes by keyword or text pattern (case-insensitive).

    Args:
        query: Search term or keyword.
        limit: Maximum results to return (default: 50).
        include_deleted: Include soft-deleted notes in search results (default: False).
    """
    conn = get_ro_connection()
    try:
        c = conn.cursor()
        sql = """
            SELECT Id, Text, Theme, IsOpen, IsAlwaysOnTop, CreatedAt, UpdatedAt, DeletedAt
            FROM Note
            WHERE Text LIKE ?
        """
        if not include_deleted:
            sql += " AND DeletedAt IS NULL"
        sql += " ORDER BY UpdatedAt DESC LIMIT ?"

        c.execute(sql, (f"%{query}%", limit))
        rows = c.fetchall()
        results = []
        for r in rows:
            cleaned = clean_text(r["Text"])
            matching_lines = [line for line in cleaned.splitlines() if query.lower() in line.lower()]
            snippet = matching_lines[0][:150] if matching_lines else cleaned[:100]
            results.append({
                "id": r["Id"],
                "snippet": snippet,
                "theme": r["Theme"] or "Yellow",
                "is_open": bool(r["IsOpen"]),
                "updated_at": ticks_to_iso(r["UpdatedAt"]),
                "is_deleted": r["DeletedAt"] is not None
            })
        return results
    finally:
        conn.close()


@app.tool()
def create_note(
    text: str,
    theme: str = "Yellow",
    is_open: bool = True,
    is_always_on_top: bool = False
) -> Dict[str, Any]:
    """Create a new Microsoft Sticky Note.

    Args:
        text: Note content (supports multiline plain text or markdown lists).
        theme: Color theme (Yellow, Green, Pink, Purple, Blue, Grey, Charcoal). Default: Yellow.
        is_open: Display note window immediately on Windows desktop (default: True).
        is_always_on_top: Pin note always on top of other windows (default: False).
    """
    theme_normalized = theme.capitalize()
    if theme_normalized not in VALID_THEMES:
        theme_normalized = "Yellow"

    conn = get_rw_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT Id FROM User LIMIT 1")
        user_row = c.fetchone()
        user_id = user_row["Id"] if user_row else None

        note_id = str(uuid.uuid4())
        ticks = now_ticks()
        raw_text = to_sticky_format(text)

        c.execute("""
            INSERT INTO Note (
                Id, Text, WindowPosition, IsOpen, IsAlwaysOnTop,
                CreationNoteIdAnchor, Theme, IsFutureNote, RemoteId,
                ChangeKey, LastServerVersion, RemoteSchemaVersion,
                IsRemoteDataInvalid, PendingInsightsScan, Type,
                ParentId, CreatedAt, DeletedAt, UpdatedAt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id, raw_text, "ManagedPosition=",
            1 if is_open else 0,
            1 if is_always_on_top else 0,
            None, theme_normalized, 0, None,
            None, None, 0,
            0, 1, None,
            user_id, ticks, None, ticks
        ))
        conn.commit()
        return {
            "success": True,
            "id": note_id,
            "theme": theme_normalized,
            "is_open": is_open,
            "is_always_on_top": is_always_on_top,
            "created_at": ticks_to_iso(ticks),
            "text": text
        }
    finally:
        conn.close()


@app.tool()
def update_note(
    note_id: str,
    text: Optional[str] = None,
    append_text: Optional[str] = None,
    theme: Optional[str] = None,
    is_open: Optional[bool] = None,
    is_always_on_top: Optional[bool] = None
) -> Dict[str, Any]:
    """Update an existing note's text, append new lines, change theme, or toggle visibility.

    Args:
        note_id: The UUID of the note to update.
        text: Overwrite entire note text.
        append_text: Append new lines to existing text (ignored if 'text' is provided).
        theme: New color theme (Yellow, Green, Pink, Purple, Blue, Grey, Charcoal).
        is_open: Open (True) or minimize/close (False) the note on desktop.
        is_always_on_top: Pin (True) or unpin (False) always on top.
    """
    conn = get_rw_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT Id, Text, Theme, IsOpen, IsAlwaysOnTop FROM Note WHERE Id = ?", (note_id,))
        row = c.fetchone()
        if not row:
            return {"error": f"Note not found with ID: {note_id}"}

        updates = []
        params = []
        ticks = now_ticks()

        if text is not None:
            updates.append("Text = ?")
            params.append(to_sticky_format(text))
        elif append_text is not None:
            current_clean = clean_text(row["Text"])
            new_combined = f"{current_clean}\n{append_text}".strip()
            updates.append("Text = ?")
            params.append(to_sticky_format(new_combined))

        if theme is not None:
            theme_norm = theme.capitalize()
            if theme_norm in VALID_THEMES:
                updates.append("Theme = ?")
                params.append(theme_norm)

        if is_open is not None:
            updates.append("IsOpen = ?")
            params.append(1 if is_open else 0)

        if is_always_on_top is not None:
            updates.append("IsAlwaysOnTop = ?")
            params.append(1 if is_always_on_top else 0)

        if not updates:
            return {"message": "No updates requested."}

        updates.append("UpdatedAt = ?")
        params.append(ticks)
        params.append(note_id)

        sql = f"UPDATE Note SET {', '.join(updates)} WHERE Id = ?"
        c.execute(sql, tuple(params))
        conn.commit()

        return {
            "success": True,
            "id": note_id,
            "updated_at": ticks_to_iso(ticks)
        }
    finally:
        conn.close()


@app.tool()
def delete_note(note_id: str, permanent: bool = False) -> Dict[str, Any]:
    """Delete a Sticky Note. Defaults to soft-delete (recoverable). Set permanent=True for hard delete.

    Args:
        note_id: The UUID of the note to delete.
        permanent: If True, permanently removes from SQLite; if False, moves to trash.
    """
    conn = get_rw_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT Id FROM Note WHERE Id = ?", (note_id,))
        if not c.fetchone():
            return {"error": f"Note not found with ID: {note_id}"}

        if permanent:
            c.execute("DELETE FROM Note WHERE Id = ?", (note_id,))
        else:
            ticks = now_ticks()
            c.execute("UPDATE Note SET DeletedAt = ?, UpdatedAt = ? WHERE Id = ?", (ticks, ticks, note_id))

        conn.commit()
        return {
            "success": True,
            "id": note_id,
            "permanent": permanent
        }
    finally:
        conn.close()


@app.tool()
def restore_note(note_id: str) -> Dict[str, Any]:
    """Restore a soft-deleted Sticky Note back to active desktop notes.

    Args:
        note_id: The UUID of the note to restore.
    """
    conn = get_rw_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT Id, DeletedAt FROM Note WHERE Id = ?", (note_id,))
        row = c.fetchone()
        if not row:
            return {"error": f"Note not found with ID: {note_id}"}
        if row["DeletedAt"] is None:
            return {"message": "Note is already active (not deleted)."}

        ticks = now_ticks()
        c.execute("UPDATE Note SET DeletedAt = NULL, UpdatedAt = ? WHERE Id = ?", (ticks, note_id))
        conn.commit()
        return {"success": True, "id": note_id, "restored": True}
    finally:
        conn.close()


@app.tool()
def get_stats() -> Dict[str, Any]:
    """Get high-level summary statistics of Microsoft Sticky Notes database."""
    conn = get_ro_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM Note WHERE DeletedAt IS NULL")
        active_count = c.fetchone()[0]

        c.execute("SELECT count(*) FROM Note WHERE DeletedAt IS NOT NULL")
        deleted_count = c.fetchone()[0]

        c.execute("SELECT count(*) FROM Note WHERE DeletedAt IS NULL AND IsOpen = 1")
        open_count = c.fetchone()[0]

        c.execute("""
            SELECT Theme, count(*) FROM Note
            WHERE DeletedAt IS NULL
            GROUP BY Theme
        """)
        themes = {r[0] or "Yellow": r[1] for r in c.fetchall()}

        return {
            "active_notes": active_count,
            "open_on_desktop": open_count,
            "in_trash": deleted_count,
            "total_notes": active_count + deleted_count,
            "themes": themes,
            "database_path": str(get_db_path())
        }
    finally:
        conn.close()


@app.tool()
def export_notes(
    export_format: str = "markdown",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Export all active Sticky Notes to a Markdown file or JSON dump.

    Args:
        export_format: Export format - 'markdown' or 'json' (default: 'markdown').
        output_dir: Target directory path. Defaults to user's Documents folder.
    """
    conn = get_ro_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT Id, Text, Theme, IsOpen, IsAlwaysOnTop, CreatedAt, UpdatedAt
            FROM Note
            WHERE DeletedAt IS NULL
            ORDER BY UpdatedAt DESC
        """)
        rows = c.fetchall()

        notes = []
        for r in rows:
            raw = r["Text"] or ""
            notes.append({
                "id": r["Id"],
                "text": clean_text(raw),
                "theme": r["Theme"] or "Yellow",
                "is_open": bool(r["IsOpen"]),
                "is_always_on_top": bool(r["IsAlwaysOnTop"]),
                "created_at": ticks_to_iso(r["CreatedAt"]),
                "updated_at": ticks_to_iso(r["UpdatedAt"])
            })

        out_path = Path(output_dir) if output_dir else Path.home() / "Documents"
        out_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if export_format.lower() == "json":
            file_name = f"sticky_notes_export_{timestamp}.json"
            target_file = out_path / file_name
            target_file.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            file_name = f"sticky_notes_export_{timestamp}.md"
            target_file = out_path / file_name
            md_lines = ["# Microsoft Sticky Notes Export", f"*Exported on {datetime.now().isoformat()}*", ""]
            for n in notes:
                md_lines.append(f"## [{n['theme']}] {n['id']}")
                md_lines.append(f"- **Updated:** {n['updated_at']}")
                md_lines.append(f"- **Status:** {'Open on desktop' if n['is_open'] else 'Closed'}")
                md_lines.append("")
                md_lines.append(n["text"])
                md_lines.append("\n---\n")
            target_file.write_text("\n".join(md_lines), encoding="utf-8")

        return {
            "success": True,
            "format": export_format.lower(),
            "count": len(notes),
            "file_path": str(target_file)
        }
    finally:
        conn.close()


def main():
    """Main entrypoint running stdio MCP transport."""
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
