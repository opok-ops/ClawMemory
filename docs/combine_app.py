#!/usr/bin/env python3
"""Combine app_native.py parts"""
with open('app_native.py', 'r', encoding='utf-8') as f:
    part1 = f.read()
with open('app_native_tail.py', 'r', encoding='utf-8') as f:
    part2 = f.read()

# Find cut point: look for the partial imp = dict line
marker = 'imp = {'
idx = part1.find(marker)
if idx == -1:
    print("Marker not found. Last 300 chars of part1:")
    print(repr(part1[-300:]))
else:
    # Find where that dict block ends (look for newline after incomplete line)
    end_line = part1.find('\n', idx)
    if end_line == -1:
        end_line = len(part1)
    fixed = part1[:idx] + part2
    with open('app_native.py', 'w', encoding='utf-8') as f:
        f.write(fixed)
    print(f"Combined successfully. Total length: {len(fixed)}")
