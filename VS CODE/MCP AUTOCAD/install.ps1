# MCP AutoCAD — Instalacion de dependencias
Write-Host "=== MCP AutoCAD - Instalacion ===" -ForegroundColor Cyan

# Instalar dependencias con uv
uv pip install mcp ezdxf

Write-Host "`n=== Verificando instalacion ===" -ForegroundColor Cyan
uv run python -c "import mcp; print('mcp OK')"
uv run python -c "import ezdxf; print('ezdxf OK')"

Write-Host "`n=== Ejecutando tests ===" -ForegroundColor Cyan
uv run python tests/test_geometry.py

Write-Host "`n=== Instalacion completada ===" -ForegroundColor Green
