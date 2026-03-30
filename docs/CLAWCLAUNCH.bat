@echo off
pip show PySimpleGUI >nul 2>&1 || pip install PySimpleGUI --quiet --user
start pythonw docs\app.py
