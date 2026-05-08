;; ============================================================================
;; SOLAR LAYOUT — Motor de distribución refactorizado
;; Depende de: geometry_core.lsp
;; Versión modularizada de solar_array_layout_v1.15.lsp
;;
;; Mejoras sobre v1.15:
;; - Usa prefijo gc: para funciones geométricas (módulo compartido)
;; - Espaciado H/V configurable vía parámetros (no hardcoded)
;; - Layer por GD generado automáticamente
;; - Nombre del layer configurable
;; ============================================================================

;; ── Motor principal de distribución ─────────────────────────────────────────
;; Parámetros:
;;   blockName   : nombre del bloque INSERT
;;   blockScale  : lista (sx sy sz)
;;   offX offY   : offset de inserción vs esquina inferior izquierda
;;   puntos      : polígono límite
;;   espH espV   : espaciados H y V entre mesas
;;   cantGD      : mesas por GD (0 = llenar todo)
;;   numGDs      : cantidad de grupos
;;   bw bh       : ancho y alto del bloque
;;   polyObs     : obstáculos poligonales
;;   circObs     : obstáculos circulares (cx cy r)
;;   layerPfx    : prefijo del layer (ej: "GD")

(defun sl:run (blockName blockScale offX offY
               puntos espH espV
               cantGD numGDs
               bw bh polyObs circObs
               layerPfx /
               bounds mnX mnY mxX mxY
               gdIdx yBase yActual xActual
               totalMesas contGD lastTopY salir ix iy
               layerName)

  (setq bounds (gc:bbox puntos))
  (setq mnX (car  (car  bounds))
        mnY (cadr (car  bounds))
        mxX (car  (cadr bounds))
        mxY (cadr (cadr bounds)))

  (setq totalMesas 0 lastTopY mnY gdIdx 0)

  (while (< gdIdx numGDs)
    (setq yBase (if (= gdIdx 0) (+ mnY espV) (+ lastTopY 6.0)))
    (setq layerName (strcat layerPfx (itoa (+ gdIdx 1))))

    ;; Crear layer para este GD
    (command "_LAYER" "_Make" layerName "")
    (setvar "CLAYER" layerName)

    (princ (strcat "\n[" layerName "]"))

    (setq contGD 0 yActual yBase salir nil)

    (while (and (not salir)
                (<= (+ yActual bh) (- mxY espV)))

      (setq xActual (+ mnX espH))

      (while (and (not salir)
                  (<= (+ xActual bw) (- mxX espH)))

        (if (and (> cantGD 0) (>= contGD cantGD))
          (setq salir T)
          (progn
            (if (gc:can-place xActual yActual bw bh puntos polyObs circObs)
              (progn
                (setq ix (- xActual offX) iy (- yActual offY))
                (entmake (list
                  (cons 0  "INSERT")
                  (cons 8  layerName)
                  (cons 2  blockName)
                  (cons 10 (list ix iy 0.0))
                  (cons 41 (car   blockScale))
                  (cons 42 (cadr  blockScale))
                  (cons 43 (caddr blockScale))
                  (cons 50 0.0)))
                (setq contGD    (+ contGD 1))
                (setq totalMesas (+ totalMesas 1))
                (if (> (+ yActual bh) lastTopY)
                  (setq lastTopY (+ yActual bh)))
                (if (= (rem contGD 5) 0)
                  (princ (strcat "  " (itoa contGD))))))
            (setq xActual (+ xActual bw espH))))
        )
      )
      (setq yActual (+ yActual bh espV))
    )

    (princ (strcat "\n  " layerName ": " (itoa contGD) " mesas"))
    (setq gdIdx (+ gdIdx 1))
  )

  (princ (strcat "\n\nTOTAL: " (itoa totalMesas) " mesas"))
  totalMesas)


;; ── Comando interactivo (reemplaza c:SolarArray de v1.15) ───────────────────
(defun c:SolarArrayV2 (/
    bloqueEnt bloqueData blockName blockScale
    insX insY offX offY bw bh
    pt1 pt2 pt3
    poliEnt puntos
    obstaculos circObs tieneObs numObs i
    obstEnt obstData obstTipo cCX cCY cR
    numGDs cantGD espH espV)

  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
  (princ "\n===== SOLAR ARRAY v2 (modular) =====")

  ;; Bloque mesa
  (setq bloqueEnt (car (entsel "\n[1] Clic en el BLOQUE de mesa: ")))
  (if (null bloqueEnt) (progn (setvar "CMDECHO" 1) (exit)))
  (setq bloqueData (entget bloqueEnt))
  (if (not (equal (cdr (assoc 0 bloqueData)) "INSERT"))
    (progn (princ "\nERROR: debe ser INSERT") (setvar "CMDECHO" 1) (exit)))

  (setq blockName  (cdr (assoc 2 bloqueData))
        blockScale (list
          (if (assoc 41 bloqueData) (cdr (assoc 41 bloqueData)) 1.0)
          (if (assoc 42 bloqueData) (cdr (assoc 42 bloqueData)) 1.0)
          (if (assoc 43 bloqueData) (cdr (assoc 43 bloqueData)) 1.0))
        insX (car  (cdr (assoc 10 bloqueData)))
        insY (cadr (cdr (assoc 10 bloqueData))))
  (princ (strcat "\n✓ Bloque: " blockName))

  ;; Medir bbox (3 clics)
  (setq pt1 (getpoint "\n[1.5] Esquina SUP-IZQ: ")
        pt2 (getpoint "\n      Esquina SUP-DER: ")
        pt3 (getpoint "\n      Esquina INF-IZQ: "))
  (setq bw (abs (- (car pt2) (car pt1)))
        bh (abs (- (cadr pt1) (cadr pt3)))
        offX (- (car pt3) insX)
        offY (- (cadr pt3) insY))
  (princ (strcat "\n✓ " (rtos bw 2 2) "m × " (rtos bh 2 2) "m"))

  ;; Polígono límite
  (setq poliEnt (car (entsel "\n[2] Clic en el POLÍGONO límite: ")))
  (if (null poliEnt) (progn (setvar "CMDECHO" 1) (exit)))
  (setq puntos (gc:poly-pts poliEnt))
  (if (< (length puntos) 3) (progn (princ "\nERROR: polígono inválido") (setvar "CMDECHO" 1) (exit)))
  (princ "\n✓ Polígono límite OK")

  ;; Obstáculos
  (setq obstaculos '() circObs '())
  (setq tieneObs (getint "\n[2.5] Hay obstáculos? [0=No / 1=Si]: "))
  (if (= tieneObs 1)
    (progn
      (setq numObs (getint "\n      Cuántos?: ") i 0)
      (while (< i numObs)
        (setq obstEnt (car (entsel (strcat "\n      Obstáculo " (itoa (+ i 1)) ": "))))
        (if obstEnt
          (progn
            (setq obstData (entget obstEnt)
                  obstTipo (cdr (assoc 0 obstData)))
            (cond
              ((equal obstTipo "CIRCLE")
               (setq cCX (car (cdr (assoc 10 obstData)))
                     cCY (cadr (cdr (assoc 10 obstData)))
                     cR (cdr (assoc 40 obstData)))
               (setq circObs (append circObs (list (list cCX cCY cR))))
               (setq obstaculos (append obstaculos (list (gc:circle-to-poly cCX cCY cR 24)))))
              ((or (equal obstTipo "LWPOLYLINE")(equal obstTipo "POLYLINE"))
               (setq obstaculos (append obstaculos (list (gc:poly-pts obstEnt)))))
              (T (princ (strcat "\n⚠ " obstTipo " no soportado"))))))
        (setq i (+ i 1)))))

  ;; Parámetros de layout
  (setq numGDs  (getint "\n[3] Cuántos GDs?: "))
  (setq cantGD  (getint "\n[4] Mesas por GD [0=todo]: "))
  (setq espH    (getreal "\n[5] Espacio horizontal entre mesas [0.5]: "))
  (setq espV    (getreal "\n[6] Espacio vertical entre mesas [2.5]: "))
  (if (null numGDs) (setq numGDs 1))
  (if (null cantGD) (setq cantGD 0))
  (if (null espH) (setq espH 0.5))
  (if (null espV) (setq espV 2.5))

  (princ "\n\n[PROCESANDO]...")
  (sl:run blockName blockScale offX offY
          puntos espH espV cantGD numGDs bw bh
          obstaculos circObs "GD")

  (princ "\n===== COMPLETADO =====")
  (setvar "CMDECHO" 1)
  (princ))

(princ "\n[solar_layout.lsp cargado — SolarArrayV2]")
(princ)
