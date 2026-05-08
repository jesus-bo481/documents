$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
$token = $env:GITHUB_TOKEN
$dir = "C:\Users\JESSAN~1\DOCUME~1"

git -C $dir remote set-url origin "https://jesus-bo481:$token@github.com/jesus-bo481/documents.git"
git -C $dir add -f "VS CODE/Auto-GD/auto_gd.py"
git -C $dir add -f "VS CODE/Auto-GD/capturar_tablas.py"
git -C $dir add -f "VS CODE/Auto-GD/gui.py"
git -C $dir add -f "VS CODE/Auto-GD/test_verificacion.py"
git -C $dir commit -m "backup: Auto-GD actualizado"
git -C $dir push origin main
Write-Output "Push completado."
