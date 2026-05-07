"""
Auto-GD — Fase 2+3: Copiar tabla de Excel y pegar como imagen en Word.

Flujo por cada tabla:
  1. Excel COM: seleccionar rango → CopyPicture al portapapeles
  2. Word  COM: buscar párrafo caption → eliminar imagen placeholder previa
               → pegar imagen del portapapeles justo antes del caption
"""

import os
import shutil
import time
import pythoncom
from pathlib import Path

import win32com.client as win32


# ─────────────────────────────────────────────────────────────────
# CONFIGURACIÓN — ajustar por proyecto
# ─────────────────────────────────────────────────────────────────
EXCEL_CALCULO = (
    r"C:\Users\JesúsAndrésBustilloO\Documents\Auto-GD\output"
    r"\PRGD-CALCULO-LA_MARTINA_1-20260331.xlsm"
)

WORD_BASE = (
    r"C:\Users\JesúsAndrésBustilloO\Documents\GD\Proyectos"
    r"\MARTINA 1 Y 2\MARTINA_1\04. Editables\02. Memoria Retie"
    r"\PRGD-MEMORIA ENEL.docx"
)

WORD_SALIDA = (
    r"C:\Users\JesúsAndrésBustilloO\Documents\Auto-GD\output"
    r"\PRGD-MEMORIA-LA_MARTINA_1-20260331.docx"
)

TABLA_MAP = [
    # Regulación DC — cols B:M, sin fila TOTAL
    {"hoja": "Arreglo mppts SM", "rango": "B2:M32",   "tabla": "reg_dc_inv1", "ancla_word": "regulación DC inversor 1"},
    {"hoja": "Arreglo mppts SM", "rango": "B36:M66",  "tabla": "reg_dc_inv2", "ancla_word": "regulación DC inversor 2"},
    {"hoja": "Arreglo mppts SM", "rango": "B70:M100", "tabla": "reg_dc_inv3", "ancla_word": "regulación DC inversor 3"},
    # Pérdidas DC — cols B:K
    {"hoja": "Pérdidas DC", "rango": "B2:K34",   "tabla": "perd_dc_inv1", "ancla_word": "pérdidas DC inversor 1"},
    {"hoja": "Pérdidas DC", "rango": "B35:K67",  "tabla": "perd_dc_inv2", "ancla_word": "pérdidas DC inversor 2"},
    {"hoja": "Pérdidas DC", "rango": "B68:K103", "tabla": "perd_dc_inv3", "ancla_word": "pérdidas DC inversor 3"},
    # AC
    {"hoja": "Regulación AC", "rango": "B2:M11", "tabla": "reg_ac",   "ancla_word": "regulación AC"},
    {"hoja": "Pérdidas AC",   "rango": "B2:I10", "tabla": "perd_ac",  "ancla_word": "pérdidas de energía AC"},
]


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def _buscar_caption(doc, ancla: str) -> int | None:
    """
    Devuelve el índice (1-based) del primer párrafo cuyo texto contiene
    'ancla' (insensible a mayúsculas).  None si no se encuentra.
    """
    ancla_low = ancla.lower()
    for i in range(1, doc.Paragraphs.Count + 1):
        if ancla_low in doc.Paragraphs(i).Range.Text.strip().lower():
            return i
    return None


def _eliminar_placeholder(doc, caption_idx: int) -> int:
    """
    Busca InlineShapes en los hasta 3 párrafos ANTES del caption y
    elimina el párrafo completo si contiene una imagen.
    Devuelve el nuevo índice del caption (puede haber bajado en 1).
    """
    for offset in range(1, 4):
        prev_idx = caption_idx - offset
        if prev_idx < 1:
            break
        prev_range = doc.Paragraphs(prev_idx).Range
        p_start = prev_range.Start
        p_end   = prev_range.End

        for j in range(doc.InlineShapes.Count, 0, -1):
            s = doc.InlineShapes(j)
            if p_start <= s.Range.Start and s.Range.End <= p_end + 1:
                # Eliminar el párrafo completo que contiene el placeholder
                prev_range.Delete()
                print(f"      Placeholder eliminado (era {offset} párrafo(s) antes del caption)")
                return caption_idx - 1   # el caption subió un índice

    return caption_idx


def _pegar_antes_caption(wd, doc, caption_idx: int):
    """
    Pega el contenido del portapapeles como imagen justo antes del
    párrafo indicado.  La imagen queda en su propio párrafo.
    """
    caption_start = doc.Paragraphs(caption_idx).Range.Start
    insert_rng = doc.Range(caption_start, caption_start)
    insert_rng.Select()

    # Pegar imagen del portapapeles
    wd.Selection.Paste()

    # Añadir salto de párrafo DESPUÉS de la imagen para separar del caption
    # (el cursor queda al final del contenido pegado)
    wd.Selection.TypeParagraph()


# ─────────────────────────────────────────────────────────────────
# PROCESO PRINCIPAL
# ─────────────────────────────────────────────────────────────────
def ejecutar(excel_path: str, word_base: str, word_salida: str, tabla_map: list):
    Path(word_salida).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(word_base, word_salida)
    print(f"Word base copiado a:\n  {word_salida}\n")

    pythoncom.CoInitialize()

    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    wd = win32.Dispatch("Word.Application")
    wd.Visible = False
    wd.DisplayAlerts = 0   # wdAlertsNone

    try:
        wb  = xl.Workbooks.Open(os.path.abspath(excel_path))
        xl.Calculate()
        time.sleep(2)

        doc = wd.Documents.Open(os.path.abspath(word_salida))

        for entrada in tabla_map:
            hoja      = entrada["hoja"]
            rango_str = entrada["rango"]
            tabla_id  = entrada["tabla"]
            ancla     = entrada["ancla_word"]

            print(f"[{tabla_id}]")

            # ── 1. Copiar rango como imagen desde Excel ───────────
            try:
                ws = wb.Worksheets(hoja)
                ws.Activate()
                ws.Range(rango_str).CopyPicture(Appearance=1, Format=2)
                time.sleep(0.4)   # dar tiempo al portapapeles
                print(f"  Excel: rango {hoja}!{rango_str} copiado")
            except Exception as e:
                print(f"  [ERROR Excel] {e}")
                continue

            # ── 2. Buscar caption en Word ─────────────────────────
            caption_idx = _buscar_caption(doc, ancla)
            if caption_idx is None:
                print(f"  [ERROR Word] No se encontró: '{ancla}'")
                continue
            print(f"  Word: caption en párrafo {caption_idx} — «{doc.Paragraphs(caption_idx).Range.Text.strip()[:55]}»")

            # ── 3. Eliminar imagen placeholder previa ─────────────
            caption_idx = _eliminar_placeholder(doc, caption_idx)

            # ── 4. Pegar antes del caption ────────────────────────
            try:
                _pegar_antes_caption(wd, doc, caption_idx)
                print(f"  OK: imagen pegada antes del caption")
            except Exception as e:
                print(f"  [ERROR al pegar] {e}")

        doc.Save()
        doc.Close()
        wb.Close(SaveChanges=False)
        print(f"\n✓ Word guardado en:\n  {word_salida}")

    finally:
        try:
            xl.Quit()
        except Exception:
            pass
        try:
            wd.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Auto-GD — Fase 2+3: Excel → portapapeles → Word ===\n")
    ejecutar(EXCEL_CALCULO, WORD_BASE, WORD_SALIDA, TABLA_MAP)
    print("\n=== Proceso completado ===")
