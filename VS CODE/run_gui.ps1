$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
$env:PYTHONIOENCODING = "utf-8"
python "C:\Users\JESSAN~1\DOCUME~1\VSCODE~1\Auto-GD\gui.py"
