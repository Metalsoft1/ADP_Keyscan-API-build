from pathlib import Path

p = Path("tools/export_adp_directory.py")
text = p.read_text(encoding="utf-8")

# Replace tabs with 4 spaces
text = text.replace("\t", "    ")

p.write_text(text, encoding="utf-8")

print("Tabs converted to spaces.")
