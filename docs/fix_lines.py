#!/usr/bin/env python3
"""Fix encoding corruption in app_native.py"""
with open('app_native.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the corrupted imp dict block with correct Chinese
old_block = '                    imp_map = {chr(20302)+"低": 1, chr(20013)+"中": 2, chr(39640)+"高": 3, chr(20851)+"关键": 4}\n                    imp_val = vals2.get("add_imp", "中")\n'
new_block = '                    imp_map = {"\u4f4e": 1, "\u4e2d": 2, "\u9ad8": 3, "\u5173\u952e": 4}\n                    imp_val = vals2.get("add_imp", "\u4e2d")\n'

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Fixed using Unicode escape block")
else:
    # Try to find and replace using the exact bytes from the file
    # The corrupted block has these unicode code points corrupted
    # We look for the pattern and replace
    import re
    pattern = r'imp_map = \{chr\(\d+\)\+"\u[a-f0-9]+": 1.*?imp = imp_map\.get\(imp_val, 2\)'
    if re.search(pattern, content):
        content = re.sub(pattern, new_block, content)
        print("Fixed using regex")
    else:
        print("Pattern not found. Searching for corrupted section...")
        idx = content.find('imp_map')
        if idx >= 0:
            print("Found 'imp_map' at index", idx)
            print("Context:", repr(content[idx:idx+300]))
        else:
            print("'imp_map' not found in file")

with open('app_native.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done!")
