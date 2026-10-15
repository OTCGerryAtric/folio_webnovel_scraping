@echo off
rem Opens Folio, the books in your browser. Pin a shortcut to this to the taskbar.
cd /d "%~dp0"
".venv\Scripts\python.exe" scrape.py serve %*
