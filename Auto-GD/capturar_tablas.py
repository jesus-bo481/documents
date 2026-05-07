"""
Auto-GD — Fase 2: Capturar tablas del Excel como imágenes
         Fase 3: Insertar imágenes en el Word antes del caption
"""

import os
import sys
import shutil
import tempfile
import time
from pathlib import Path
from datetime import datetime

import win32com.client
import win32con
import win32clipboard
import pythoncom
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import docx.opc.constants


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

IMG_DIR = Path(r"C:\Users\JesúsAndrésBustilloO\Documents\Auto-GD\output\imagenes")

TABLA_MAP = [
    # Regulación DC — cols B:M, sin fila TOTAL
    {
        "hoja":       "Arreglo mppts SM",
        "rango":      "B2:M32",
        "tabla":      "reg_dc_inv1",
        "ancla_word": "regulación DC inversor 1",
    },
    {
        "hoja":       "Arreglo mppts SM",
        "rango":      "B36:M66",
        "tabla":      "reg_dc_inv2",
        "ancla_word": "regulación DC inversor 2",
    },
    {
        "hoja":       "Arreglo mppts SM",
        "rango":      "B70:M100",
        "tabla":      "reg_dc_inv3",
        "ancla_word": "regulación DC inversor 3",
    },
    # Pérdidas DC — cols B:K
    {
        "hoja":       "Pérdidas DC",
        "rango":      "B2:K34",
        "tabla":      "perd_dc_inv1",
        "ancla_word": "pérdidas DC inversor 1",
    },
    {
        "hoja":       "Pérdidas DC",
        "rango":      "B35:K67",
        "tabla":      "perd_dc_inv2",
        "ancla_word": "pérdidas DC inversor 2",
    },
    {
        "hoja":       "Pérdidas DC",
        "rango":      "B68:K103",
        "tabla":      "perd_dc_inv3",
        "ancla_word": "pérdidas DC inversor 3",
    },
    # AC
    {
        "hoja":       "Regulación AC",
        "rango":      "B2:M11",
        "tabla":      "reg_ac",
        "ancla_word": "regulación AC",
    },
    {
        "hoja":       "Pérdidas AC",
        "rango":      "B2:I10",
        "tabla":      "perd_ac",
        "ancla_word": "pérdidas de energía AC",
    },
]

# Ancho máximo de imagen en el Word (pulgadas)
IMG_MAX_WIDTH_IN = 6.0


# ─────────────────────────────────────────────────────────────────
# FASE 2: Capturar rangos del Excel como imágenes PNG
# ─────────────────────────────────────────────────────────────────
def _clipboard_bitmap_a_png(img_path: str):
    """
    Lee el bitmap CF_DIB del portapapeles y lo guarda como PNG.
    Fallback cuando chart.Paste() falla (ej. celdas fusionadas).
    """
    from PIL import Image
    import io, struct

    win32clipboard.OpenClipboard()
    try:
        data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
    finally:
        win32clipboard.CloseClipboard()

    # CF_DIB es un BITMAPINFOHEADER + datos de píxeles; PIL lo lee vía BMP con cabecera
    # Anteponer la cabecera de fichero BMP (14 bytes)
    header_size = struct.unpack_from("<I", data, 0)[0]
    file_size   = 14 + len(data)
    pixel_offset = 14 + header_size

    bmp_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset)
    bmp_data   = bmp_header + data

    img = Image.open(io.BytesIO(bmp_data))
    img.save(img_path, "PNG")


def _capturar_rango(xl, wb, hoja_nombre: str, rango_str: str, img_path: str):
    """
    Captura un rango como PNG.
    Método primario: CopyPicture → chart temporal → Export.
    Fallback: CopyPicture(xlBitmap) → portapapeles CF_DIB → PIL → PNG.
    """
    ws  = wb.Worksheets(hoja_nombre)
    rng = ws.Range(rango_str)

    # ── Método primario: via chart temporal ───────────────────────
    try:
        rng.CopyPicture(Appearance=1, Format=2)   # xlScreen, xlBitmap
        chart_obj = ws.ChartObjects().Add(0, 0, rng.Width, rng.Height)
        chart     = chart_obj.Chart
        chart.Paste()
        chart.Export(img_path, "PNG")
        chart_obj.Delete()
        return
    except Exception:
        pass   # intentar fallback

    # ── Fallback: leer CF_DIB directo del portapapeles ───────────
    # Activar hoja para que Select() funcione
    ws.Activate()
    rng.Select()
    xl.Selection.CopyPicture(Appearance=1, Format=2)   # xlBitmap
    time.sleep(0.3)
    _clipboard_bitmap_a_png(img_path)


def capturar_imagenes(excel_path: str, tabla_map: list, img_dir: Path) -> dict:
    """
    Abre el Excel con COM, captura cada rango como PNG.
    Devuelve {tabla_id: path_imagen}.
    """
    img_dir.mkdir(parents=True, exist_ok=True)

    pythoncom.CoInitialize()
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    try:
        wb = xl.Workbooks.Open(os.path.abspath(excel_path))
        xl.Calculate()
        time.sleep(2)

        imagenes = {}
        for entrada in tabla_map:
            hoja_nombre = entrada["hoja"]
            rango_str   = entrada["rango"]
            tabla_id    = entrada["tabla"]
            img_path    = str(img_dir / f"{tabla_id}.png")

            try:
                _capturar_rango(xl, wb, hoja_nombre, rango_str, img_path)
                imagenes[tabla_id] = img_path
                print(f"  [OK] {tabla_id} → {img_path}")
            except Exception as e:
                print(f"  [ERROR] {tabla_id} ({hoja_nombre} {rango_str}): {e}")

        wb.Close(SaveChanges=False)
        return imagenes

    finally:
        xl.Quit()
        pythoncom.CoUninitialize()


# ─────────────────────────────────────────────────────────────────
# FASE 3: Insertar imágenes en el Word antes del caption
# ─────────────────────────────────────────────────────────────────
def _texto_parrafo(p) -> str:
    """Devuelve el texto completo de un párrafo normalizado a minúsculas."""
    return "".join(run.text for run in p.runs).strip().lower()


def _insertar_imagen_antes_parrafo(doc: Document, parrafo_idx: int, img_path: str):
    """
    Inserta un párrafo con imagen ANTES del párrafo indicado por índice.
    La imagen se centra y no supera IMG_MAX_WIDTH_IN pulgadas.
    """
    from PIL import Image as PILImage
    with PILImage.open(img_path) as im:
        w_px, h_px = im.size
        dpi = im.info.get("dpi", (96, 96))[0]

    w_in = w_px / dpi
    h_in = h_px / dpi

    if w_in > IMG_MAX_WIDTH_IN:
        factor = IMG_MAX_WIDTH_IN / w_in
        w_in   = IMG_MAX_WIDTH_IN
        h_in   = h_in * factor

    # Crear un nuevo párrafo XML con la imagen
    new_p = OxmlElement("w:p")

    # Alineación centrada
    pPr = OxmlElement("w:pPr")
    jc  = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    pPr.append(jc)
    new_p.append(pPr)

    # Insertar el párrafo ANTES del párrafo ancla
    ancla_p = doc.paragraphs[parrafo_idx]._element
    ancla_p.addprevious(new_p)

    # Ahora agregar la imagen al nuevo párrafo con python-docx
    # Buscamos el párrafo recién insertado (es el antecesor inmediato)
    idx_real = None
    for i, p in enumerate(doc.paragraphs):
        if p._element is new_p:
            idx_real = i
            break

    if idx_real is not None:
        p_obj = doc.paragraphs[idx_real]
        run   = p_obj.add_run()
        run.add_picture(img_path, width=Inches(w_in))


def insertar_imagenes_en_word(
    word_base: str,
    word_salida: str,
    imagenes: dict,
    tabla_map: list,
):
    """
    Copia el Word base a salida, busca cada ancla_word en los párrafos
    e inserta la imagen correspondiente justo antes del párrafo caption.
    """
    Path(word_salida).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(word_base, word_salida)

    doc = Document(word_salida)

    # Construir índice de anclas: ancla_word → índice de párrafo
    anclas_pendientes = {
        entrada["ancla_word"].lower(): entrada["tabla"]
        for entrada in tabla_map
    }

    # Recolectar qué párrafos contienen cada ancla (puede haber varias ocurrencias;
    # tomamos la primera)
    insertar = {}   # tabla_id → parrafo_idx
    for i, p in enumerate(doc.paragraphs):
        texto = _texto_parrafo(p)
        for ancla, tabla_id in anclas_pendientes.items():
            if ancla in texto and tabla_id not in insertar:
                insertar[tabla_id] = i
                print(f"  [Word] Ancla '{ancla}' → párrafo {i}: «{texto[:60]}»")

    if not insertar:
        print("[ADVERTENCIA] No se encontró ninguna ancla en el Word.")
        doc.save(word_salida)
        return

    # Insertar en orden INVERSO de índice para no desplazar los índices
    for tabla_id, parrafo_idx in sorted(insertar.items(), key=lambda x: x[1], reverse=True):
        img_path = imagenes.get(tabla_id)
        if not img_path or not Path(img_path).exists():
            print(f"  [ADVERTENCIA] Imagen no encontrada para {tabla_id}, se omite.")
            continue
        try:
            _insertar_imagen_antes_parrafo(doc, parrafo_idx, img_path)
            print(f"  [OK] Imagen {tabla_id} insertada antes del párrafo {parrafo_idx}")
        except Exception as e:
            print(f"  [ERROR] {tabla_id}: {e}")

    doc.save(word_salida)
    print(f"\n✓ Word guardado en:\n  {word_salida}")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Auto-GD — Fase 2+3: Capturar tablas e insertar en Word ===\n")

    print(">> Fase 2: Capturando imágenes del Excel…")
    imagenes = capturar_imagenes(EXCEL_CALCULO, TABLA_MAP, IMG_DIR)
    print(f"   {len(imagenes)} imágenes capturadas.\n")

    print(">> Fase 3: Insertando imágenes en el Word…")
    insertar_imagenes_en_word(WORD_BASE, WORD_SALIDA, imagenes, TABLA_MAP)

    print("\n=== Proceso completado ===")
