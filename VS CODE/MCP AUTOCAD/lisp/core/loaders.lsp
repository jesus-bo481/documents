;; ============================================================================
;; LOADERS — Carga todos los módulos del sistema MCP AutoCAD
;; Ejecutar una sola vez al iniciar sesión en AutoCAD LT:
;;   (load "C:/ruta/a/MCP AUTOCAD/lisp/core/loaders.lsp")
;; ============================================================================

(defun load-module (path nombre)
  (if (findfile path)
    (progn
      (load path)
      (princ (strcat "\n✓ " nombre)))
    (princ (strcat "\n✗ NO ENCONTRADO: " nombre " (" path ")"))))

(setq BASE "C:/Users/JesúsAndrésBustilloO/Documents/VS CODE/MCP AUTOCAD/lisp/")

;; Core — cargar primero
(load-module (strcat BASE "core/geometry_core.lsp") "geometry_core")
(load-module (strcat BASE "core/solar_layout.lsp")  "solar_layout")

;; Tools
(load-module (strcat BASE "tools/strings_draw.lsp")   "strings_draw")
(load-module (strcat BASE "tools/metrado.lsp")         "metrado")
(load-module (strcat BASE "tools/rename_strings.lsp")  "rename_strings")
(load-module (strcat BASE "tools/paralelas.lsp")       "paralelas")
(load-module (strcat BASE "tools/mfillet.lsp")         "mfillet")
(load-module (strcat BASE "tools/cotas.lsp")           "cotas")

(princ "\n\n╔══════════════════════════════════════╗")
(princ "\n║  MCP AUTOCAD — Módulos cargados     ║")
(princ "\n║  Comandos disponibles:              ║")
(princ "\n║  SolarArrayV2  STRINGS_VERTICAL_PROY║")
(princ "\n║  METRADO_GUIADO RENOMBRAR_STRINGS   ║")
(princ "\n║  PARALELASPRO  MFILLET  COTA_SMART  ║")
(princ "\n╚══════════════════════════════════════╝")
(princ)
