"""
Test de verificacion: pone TODAS las longitudes de strings DC y AC en 1
para confirmar que el pipeline escribe y captura en los lugares correctos.
"""
import sys
sys.path.insert(0, r"C:\Users\JesúsAndrésBustilloO\Documents\Auto-GD")

from auto_gd import leer_metrado, llenar_excel, PROYECTO, EXCEL_METRADO, EXCEL_BASE, EXCEL_SALIDA
from capturar_tablas import ejecutar, WORD_BASE, WORD_SALIDA, TABLA_MAP

# ── Fase 1: llenar Excel con todo en 1 ───────────────────────────
metrado_real = leer_metrado(EXCEL_METRADO)
metrado_test = {k: (1.0, 1.0) for k in metrado_real}
print(f"Strings en metrado: {len(metrado_test)} → todos con longitud pos=1, neg=1\n")

proyecto_test = dict(PROYECTO)
proyecto_test["long_ac_inv"]   = [1, 1, 1]
proyecto_test["paneles_serie"] = 1
print(f"Longitudes AC inversores: {proyecto_test['long_ac_inv']}")
print(f"Paneles en serie: {proyecto_test['paneles_serie']}\n")

print("=== Fase 1: llenando Excel ===")
llenar_excel(metrado_test, proyecto_test, EXCEL_BASE, EXCEL_SALIDA)

# ── Fase 2+3: capturar e insertar en Word ────────────────────────
print("\n=== Fase 2+3: capturando tablas e insertando en Word ===\n")
ejecutar(EXCEL_SALIDA, WORD_BASE, WORD_SALIDA, TABLA_MAP,
         paneles_serie=proyecto_test["paneles_serie"])

print("\n=== Verificacion completada ===")
print(f"Abre el Word y confirma que las tablas muestran 1 en todas las longitudes:")
print(f"  {WORD_SALIDA}")
