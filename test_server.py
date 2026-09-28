"""Run self-checks for Sticky Notes MCP tools against test database."""
import os
import shutil
from pathlib import Path

# Setup test DB environment variable
SCRATCH_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\cache\scratch"))
ORIG_DB = Path(os.path.expandvars(
    r"%LOCALAPPDATA%\Packages\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe\LocalState\plum.sqlite"
))
TEST_DB = SCRATCH_DIR / "test_plum_mcp.sqlite"

shutil.copy2(ORIG_DB, TEST_DB)
if ORIG_DB.with_name("plum.sqlite-wal").exists():
    shutil.copy2(ORIG_DB.with_name("plum.sqlite-wal"), TEST_DB.with_name("test_plum_mcp.sqlite-wal"))
if ORIG_DB.with_name("plum.sqlite-shm").exists():
    shutil.copy2(ORIG_DB.with_name("plum.sqlite-shm"), TEST_DB.with_name("test_plum_mcp.sqlite-shm"))

os.environ["STICKY_NOTES_DB_PATH"] = str(TEST_DB)

# Import tools directly
from server import (
    clean_text,
    create_note,
    delete_note,
    export_notes,
    get_note,
    get_stats,
    list_notes,
    restore_note,
    search_notes,
    update_note,
)

print("[1] Testing clean_text...")
sample_raw = (
    "\\id=11111111-2222-3333-4444-555555555555\\b Bold Title\\b0\n"
    "\\id=22222222-3333-4444-5555-666666666666\\l Item 1\n"
    "\\id=33333333-4444-5555-6666-777777777777\\strike Struck out\\strike0"
)
cleaned = clean_text(sample_raw)
assert "**Bold Title**" in cleaned, f"Expected bold markdown, got: {cleaned}"
assert "- Item 1" in cleaned, f"Expected bullet markdown, got: {cleaned}"
assert "~~Struck out~~" in cleaned, f"Expected strike markdown, got: {cleaned}"
print("    clean_text OK!")

print("[2] Testing list_notes with filters...")
all_notes = list_notes(limit=10)
assert len(all_notes) > 0, "No notes returned"
green_notes = list_notes(limit=10, theme="Green")
for n in green_notes:
    assert n["theme"].lower() == "green"
print(f"    list_notes OK! Found {len(all_notes)} notes total, {len(green_notes)} green notes.")

print("[3] Testing get_note...")
first_id = all_notes[0]["id"]
single_note = get_note(first_id)
assert single_note["id"] == first_id
assert "text" in single_note and "theme" in single_note
print("    get_note OK!")

print("[4] Testing search_notes...")
res = search_notes("e")
print(f"    search_notes OK! Found {len(res)} matching notes.")

print("[5] Testing create_note...")
created = create_note(
    text="Belanja Bulanan\n- Telur 1kg\n- Beras 5kg\n- Kopi Kapal Api",
    theme="Pink",
    is_open=True,
    is_always_on_top=True
)
assert created["success"] is True
new_id = created["id"]
print(f"    create_note OK! New Note ID: {new_id}")

print("[6] Testing get_note on newly created note...")
fetched = get_note(new_id)
assert "Belanja Bulanan" in fetched["text"]
assert fetched["theme"] == "Pink"
assert fetched["is_open"] is True
assert fetched["is_always_on_top"] is True
print("    get_note on new note OK!")

print("[7] Testing update_note with append_text...")
appended = update_note(new_id, append_text="- Susu UHT 1L", theme="Purple")
assert appended["success"] is True
fetched_appended = get_note(new_id)
assert "- Susu UHT 1L" in fetched_appended["text"]
assert "Belanja Bulanan" in fetched_appended["text"]
assert fetched_appended["theme"] == "Purple"
print("    update_note (append_text) OK!")

print("[8] Testing get_stats...")
stats = get_stats()
assert stats["active_notes"] > 0
assert "themes" in stats
print(f"    get_stats OK! Active: {stats['active_notes']}, Open: {stats['open_on_desktop']}, Themes: {stats['themes']}")

print("[9] Testing export_notes (Markdown & JSON)...")
exp_md = export_notes(export_format="markdown", output_dir=str(SCRATCH_DIR))
assert exp_md["success"] is True
assert Path(exp_md["file_path"]).exists()

exp_json = export_notes(export_format="json", output_dir=str(SCRATCH_DIR))
assert exp_json["success"] is True
assert Path(exp_json["file_path"]).exists()
print(f"    export_notes OK! Exported {exp_md['count']} notes.")

print("[10] Testing soft delete_note & restore_note...")
del_res = delete_note(new_id, permanent=False)
assert del_res["success"] is True
assert get_note(new_id)["is_deleted"] is True

restore_res = restore_note(new_id)
assert restore_res["success"] is True
assert get_note(new_id)["is_deleted"] is False
print("    soft delete & restore OK!")

print("[11] Testing permanent delete_note...")
perm_del = delete_note(new_id, permanent=True)
assert perm_del["success"] is True
assert "error" in get_note(new_id)
print("    permanent delete_note OK!")

print("\nALL 11 MCP TESTS PASSED SUCCESSFULLY!")
