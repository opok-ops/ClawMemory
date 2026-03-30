#!/usr/bin/env python3
"""Fix the 3 corrupted lines in app_native.py"""
with open('app_native.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find and fix the corrupted imp lines
fixed = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check for corruption markers: chr() calls with non-ASCII chars
    if 'chr(' in line and ('\u4f4e' in line or '\u4e2d' in line or '\u9ad8' in line or '\u5173' in line):
        # This line is corrupted, replace with correct version
        indent = len(line) - len(line.lstrip())
        spaces = ' ' * indent
        # Check if it's the "imp_map" line or the "imp_val" line
        if 'imp_map' in line or 'imp = {' in line:
            fixed.append(spaces + 'imp_map = {"\\u4f4e": 1, "\\u4e2d": 2, "\\u9ad8": 3, "\\u5173\\u952e": 4}\n')
            i += 1
            # Skip any continuation lines
            while i < len(lines) and (lines[i].strip().startswith('"') or lines[i].strip().startswith('}')):
                if lines[i].strip().startswith('}.'):
                    fixed.append(spaces + lines[i].replace('imp = imp_map.get(imp_val, 2)', 'imp = imp_map.get(imp_val, 2)'))
                    i += 1
                else:
                    i += 1
            continue
        elif 'imp_val' in line:
            # Fix imp_val with proper encoding
            fixed.append(spaces + 'imp_val = vals2.get("add_imp", "\\u4e2d")\n')
            i += 1
            continue
        elif '}.' in line or line.strip().startswith('}.'):
            # Skip this line
            i += 1
            continue
    fixed.append(line)
    i += 1

print(f"After fix: {len(fixed)} lines")

# Write back
with open('app_native.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print("Fixed!")

# Verify
with open('app_native.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for remaining corruption
bad = ['chr(', '\u4f4e1', '\u4e2d2', '\u9ad83', '\u5173\u952e4']
found = [b for b in bad if b in content]
if found:
    print(f"WARNING: Still have corruption: {found}")
else:
    print("No corruption found!")
print(f"File size: {len(content)} chars")
