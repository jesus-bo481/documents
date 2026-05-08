;; ============================================================================
;; SOLAR PANEL ARRAY LAYOUT v1.15
;; - Soporta obstaculos tipo CIRCLE, LWPOLYLINE y POLYLINE
;; - Circulos se aproximan a poligono de 24 lados
;; - Colision bloque-circulo con distancia centro + margen
;; ============================================================================

(defun c:SolarArray (/
    bloqueEnt bloqueData blockName blockScale
    insX insY offX offY blockWidth blockHeight
    pt1 pt2 pt3
    poliEnt poliData puntos
    tieneObstaculos obstaculos obsCirculos
    numObstaculos i obstEnt obstData obstTipo
    numGDs cantidadDeseada espacioH espacioV)

  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)
  (princ "\n===== SOLAR ARRAY v1.15 =====\n")

  ;; ── PASO 1: Bloque ──────────────────────────────────────────────────────
  (setq bloqueEnt (car (entsel "\n[1] Clic en el BLOQUE de mesa: ")))
  (if (null bloqueEnt) (progn (princ "\nERROR: sin bloque") (setvar "CMDECHO" 1) (exit)))
  (setq bloqueData (entget bloqueEnt))
  (if (not (equal (cdr (assoc 0 bloqueData)) "INSERT"))
    (progn (princ "\nERROR: debe ser INSERT") (setvar "CMDECHO" 1) (exit)))
  (setq blockName  (cdr (assoc 2  bloqueData)))
  (setq blockScale (list
    (if (assoc 41 bloqueData) (cdr (assoc 41 bloqueData)) 1.0)
    (if (assoc 42 bloqueData) (cdr (assoc 42 bloqueData)) 1.0)
    (if (assoc 43 bloqueData) (cdr (assoc 43 bloqueData)) 1.0)))
  (setq insX (car  (cdr (assoc 10 bloqueData))))
  (setq insY (cadr (cdr (assoc 10 bloqueData))))
  (princ (strcat "\n✓ Bloque: " blockName))

  ;; ── PASO 1.5/1.6: Medir bbox con 3 clics ───────────────────────────────
  (setq pt1 (getpoint "\n[1.5] Esquina SUP-IZQ del bloque: "))
  (if (null pt1) (progn (princ "\nERROR") (setvar "CMDECHO" 1) (exit)))
  (setq pt2 (getpoint "\n      Esquina SUP-DER del bloque: "))
  (if (null pt2) (progn (princ "\nERROR") (setvar "CMDECHO" 1) (exit)))
  (setq pt3 (getpoint "\n      Esquina INF-IZQ del bloque: "))
  (if (null pt3) (progn (princ "\nERROR") (setvar "CMDECHO" 1) (exit)))

  (setq blockWidth  (abs (- (car  pt2) (car  pt1))))
  (setq blockHeight (abs (- (cadr pt1) (cadr pt3))))
  (setq offX (- (car  pt3) insX))
  (setq offY (- (cadr pt3) insY))

  (if (< blockWidth  0.001) (progn (princ "\nERROR ancho")  (setvar "CMDECHO" 1) (exit)))
  (if (< blockHeight 0.001) (progn (princ "\nERROR alto")   (setvar "CMDECHO" 1) (exit)))
  (princ (strcat "\n✓ " (rtos blockWidth 2 2) "m x " (rtos blockHeight 2 2) "m"))

  ;; ── PASO 2: Poligono limite ──────────────────────────────────────────────
  (setq poliEnt (car (entsel "\n[2] Clic en el POLIGONO limite: ")))
  (if (null poliEnt) (progn (princ "\nERROR") (setvar "CMDECHO" 1) (exit)))
  (setq poliData (entget poliEnt))
  (if (not (or (equal (cdr (assoc 0 poliData)) "LWPOLYLINE")
               (equal (cdr (assoc 0 poliData)) "POLYLINE")))
    (progn (princ "\nERROR: debe ser POLILINEA") (setvar "CMDECHO" 1) (exit)))
  (setq puntos (get-poly-pts poliEnt))
  (if (< (length puntos) 3) (progn (princ "\nERROR: poligono invalido") (setvar "CMDECHO" 1) (exit)))
  (princ "\n✓ Poligono limite OK")

  ;; ── PASO 2.5: Obstaculos (CIRCLE o POLILINEA) ───────────────────────────
  ;; obstaculos  = lista de listas de puntos (poligonos aproximados)
  ;; obsCirculos = lista de (cx cy radio) para verificacion exacta
  (setq obstaculos '())
  (setq obsCirculos '())
  (setq tieneObstaculos (getint "\n[2.5] Hay obstaculos? [0=No / 1=Si]: "))
  (if (null tieneObstaculos) (setq tieneObstaculos 0))

  (if (= tieneObstaculos 1)
    (progn
      (setq numObstaculos (getint "\n      Cuantos obstaculos?: "))
      (if (null numObstaculos) (setq numObstaculos 0))
      (setq i 0)
      (while (< i numObstaculos)
        (setq obstEnt (car (entsel
          (strcat "\n      Clic obstaculo " (itoa (+ i 1)) "/" (itoa numObstaculos)
                  " (CIRCULO o POLILINEA): "))))
        (if (not (null obstEnt))
          (progn
            (setq obstData (entget obstEnt))
            (setq obstTipo (cdr (assoc 0 obstData)))
            (cond
              ;; --- CIRCULO ---
              ((equal obstTipo "CIRCLE")
               (setq cCX (car  (cdr (assoc 10 obstData))))
               (setq cCY (cadr (cdr (assoc 10 obstData))))
               (setq cR  (cdr (assoc 40 obstData)))
               ;; Guardar como circulo exacto
               (setq obsCirculos (append obsCirculos (list (list cCX cCY cR))))
               ;; Tambien aproximar como poligono para pip
               (setq obstaculos (append obstaculos
                 (list (circle-to-poly cCX cCY cR 24))))
               (princ (strcat "\n✓ Circulo " (itoa (+ i 1))
                              " r=" (rtos cR 2 2))))

              ;; --- POLILINEA ---
              ((or (equal obstTipo "LWPOLYLINE")
                   (equal obstTipo "POLYLINE"))
               (setq obstaculos (append obstaculos (list (get-poly-pts obstEnt))))
               (princ (strcat "\n✓ Poligono " (itoa (+ i 1)))))

              ;; --- OTRO TIPO ---
              (T (princ (strcat "\n⚠ Tipo " obstTipo " no soportado, omitido")))
            )
          )
          (princ (strcat "\n⚠ Obstaculo " (itoa (+ i 1)) " omitido"))
        )
        (setq i (+ i 1))
      )
      (princ (strcat "\n✓ " (itoa (length obstaculos)) " obstaculos + "
                     (itoa (length obsCirculos)) " circulos"))
    )
  )

  ;; ── PASO 3 y 4 ──────────────────────────────────────────────────────────
  (setq numGDs (getint "\n[3] Cuantos GRUPOS (GDs)?: "))
  (if (null numGDs) (setq numGDs 1))
  (if (< numGDs 1)  (setq numGDs 1))

  (setq cantidadDeseada (getint "\n[4] Mesas por GD [0=llenar todo]: "))
  (if (null cantidadDeseada) (setq cantidadDeseada 0))
  (if (< cantidadDeseada 0)  (setq cantidadDeseada 0))

  (setq espacioH 0.5)
  (setq espacioV 2.5)

  (princ "\n\n[PROCESANDO]...")
  (solar-run-v15 blockName blockScale offX offY
                 puntos espacioH espacioV
                 cantidadDeseada numGDs
                 blockWidth blockHeight obstaculos obsCirculos)

  (princ "\n===== COMPLETADO =====\n")
  (setvar "CMDECHO" 1)
  (princ)
)

;; ============================================================================
;; CONVERTIR CIRCULO A POLIGONO DE N LADOS
;; ============================================================================
(defun circle-to-poly (cx cy r n / pts ang step k)
  (setq pts '())
  (setq step (/ (* 2.0 pi) n))
  (setq k 0)
  (while (< k n)
    (setq ang (* k step))
    (setq pts (append pts (list (list (+ cx (* r (cos ang)))
                                      (+ cy (* r (sin ang)))
                                      0.0))))
    (setq k (+ k 1))
  )
  pts
)

;; ============================================================================
;; DISTRIBUCION PRINCIPAL
;; ============================================================================
(defun solar-run-v15 (blockName blockScale offX offY
                      puntos espacioH espacioV
                      cantidadDeseada numGDs
                      blockWidth blockHeight obstaculos obsCirculos /
                      bounds mnX mnY mxX mxY
                      gdIdx yBase yActual xActual
                      totalMesas contGD lastTopY salir ix iy)

  (setq bounds (sa-bbox puntos))
  (setq mnX (car  (car  bounds)))
  (setq mnY (cadr (car  bounds)))
  (setq mxX (car  (cadr bounds)))
  (setq mxY (cadr (cadr bounds)))

  (setq totalMesas 0)
  (setq lastTopY   mnY)
  (setq gdIdx      0)

  (while (< gdIdx numGDs)
    (if (= gdIdx 0)
      (setq yBase (+ mnY espacioV))
      (setq yBase (+ lastTopY 6.0))
    )

    (princ (strcat "\n[GD " (itoa (+ gdIdx 1)) "/" (itoa numGDs) "]"))

    (setq contGD  0)
    (setq yActual yBase)
    (setq salir   nil)

    (while (and (not salir)
                (<= (+ yActual blockHeight) (- mxY espacioV)))

      (setq xActual (+ mnX espacioH))

      (while (and (not salir)
                  (<= (+ xActual blockWidth) (- mxX espacioH)))

        (if (and (> cantidadDeseada 0) (>= contGD cantidadDeseada))
          (setq salir T)
          (progn
            (if (bloque-ok-v15 xActual yActual blockWidth blockHeight
                               puntos obstaculos obsCirculos)
              (progn
                (setq ix (- xActual offX))
                (setq iy (- yActual offY))
                (entmake (list
                  (cons 0  "INSERT")
                  (cons 8  "0")
                  (cons 2  blockName)
                  (cons 10 (list ix iy 0.0))
                  (cons 41 (car   blockScale))
                  (cons 42 (cadr  blockScale))
                  (cons 43 (caddr blockScale))
                  (cons 50 0.0)))
                (setq contGD    (+ contGD 1))
                (setq totalMesas (+ totalMesas 1))
                (if (> (+ yActual blockHeight) lastTopY)
                  (setq lastTopY (+ yActual blockHeight)))
                (if (= (rem contGD 5) 0)
                  (princ (strcat "\n  -> " (itoa contGD))))
              )
            )
            (setq xActual (+ xActual blockWidth espacioH))
          )
        )
      )
      (setq yActual (+ yActual blockHeight espacioV))
    )

    (princ (strcat "\n  GD " (itoa (+ gdIdx 1)) ": " (itoa contGD) " mesas"))
    (setq gdIdx (+ gdIdx 1))
  )

  (princ (strcat "\n\nTOTAL: " (itoa totalMesas) " mesas"))
)

;; ============================================================================
;; VALIDACION COMPLETA DEL BLOQUE
;; bx,by = esquina inferior izquierda del bloque
;; ============================================================================
(defun bloque-ok-v15 (bx by bw bh puntos obstaculos obsCirculos /
    x1 y1 x2 y2 cx cy ok obsIdx obsPts vx vy
    circ ccx ccy cr dist halfDiag)

  (setq x1 bx)
  (setq y1 by)
  (setq x2 (+ bx bw))
  (setq y2 (+ by bh))
  (setq cx (+ bx (/ bw 2.0)))
  (setq cy (+ by (/ bh 2.0)))

  ;; 1) Las 4 esquinas Y el centro DENTRO del poligono limite
  (setq ok
    (and (sa-pip x1 y1 puntos)
         (sa-pip x2 y1 puntos)
         (sa-pip x2 y2 puntos)
         (sa-pip x1 y2 puntos)
         (sa-pip cx cy puntos)))

  ;; 2) Colision con obstaculos tipo POLIGONO
  (if (and ok (> (length obstaculos) 0))
    (progn
      (setq obsIdx 0)
      (while (and ok (< obsIdx (length obstaculos)))
        (setq obsPts (nth obsIdx obstaculos))

        ;; a) esquinas del bloque dentro del obstaculo
        (if (or (sa-pip x1 y1 obsPts)
                (sa-pip x2 y1 obsPts)
                (sa-pip x2 y2 obsPts)
                (sa-pip x1 y2 obsPts)
                (sa-pip cx cy obsPts))
          (setq ok nil)
        )

        ;; b) vertices del obstaculo dentro del bloque
        (if ok
          (progn
            (setq vi 0)
            (while (and ok (< vi (length obsPts)))
              (setq vx (car  (nth vi obsPts)))
              (setq vy (cadr (nth vi obsPts)))
              (if (and (> vx x1) (< vx x2)
                       (> vy y1) (< vy y2))
                (setq ok nil))
              (setq vi (+ vi 1))
            )
          )
        )

        (setq obsIdx (+ obsIdx 1))
      )
    )
  )

  ;; 3) Colision con obstaculos tipo CIRCULO (verificacion exacta)
  ;; El bloque colisiona con el circulo si la distancia del centro del circulo
  ;; al punto mas cercano del bloque es menor que el radio
  (if (and ok (> (length obsCirculos) 0))
    (progn
      (setq obsIdx 0)
      (while (and ok (< obsIdx (length obsCirculos)))
        (setq circ (nth obsIdx obsCirculos))
        (setq ccx (car   circ))
        (setq ccy (cadr  circ))
        (setq cr  (caddr circ))

        ;; Punto mas cercano del rectangulo al centro del circulo
        (setq nearX (max x1 (min ccx x2)))
        (setq nearY (max y1 (min ccy y2)))
        (setq dist (sqrt (+ (* (- ccx nearX) (- ccx nearX))
                            (* (- ccy nearY) (- ccy nearY)))))

        (if (< dist cr)
          (setq ok nil)
        )

        (setq obsIdx (+ obsIdx 1))
      )
    )
  )

  ok
)

;; ============================================================================
;; RAY CASTING
;; ============================================================================
(defun sa-pip (px py pts / n i j xi yi xj yj cnt)
  (setq n (length pts) cnt 0 i 0)
  (while (< i n)
    (setq j  (if (= i (- n 1)) 0 (+ i 1))
          xi (car  (nth i pts))
          yi (cadr (nth i pts))
          xj (car  (nth j pts))
          yj (cadr (nth j pts)))
    (if (and (or (and (> yi py) (<= yj py))
                 (and (> yj py) (<= yi py)))
             (not (equal yi yj 1.0e-10))
             (< px (+ xi (* (/ (- py yi) (- yj yi)) (- xj xi)))))
      (setq cnt (+ cnt 1)))
    (setq i (+ i 1)))
  (= (rem cnt 2) 1))

;; ============================================================================
;; OBTENER PUNTOS DE POLILINEA
;; ============================================================================
(defun get-poly-pts (ent / data pts item)
  (setq data (entget ent) pts '())
  (foreach item data
    (if (= (car item) 10)
      (setq pts (append pts (list (cdr item))))))
  pts)

;; ============================================================================
;; BOUNDING BOX
;; ============================================================================
(defun sa-bbox (pts / mnX mxX mnY mxY pt)
  (setq mnX (car (car pts)) mxX mnX
        mnY (cadr (car pts)) mxY mnY)
  (foreach pt pts
    (if (< (car  pt) mnX) (setq mnX (car  pt)))
    (if (> (car  pt) mxX) (setq mxX (car  pt)))
    (if (< (cadr pt) mnY) (setq mnY (cadr pt)))
    (if (> (cadr pt) mxY) (setq mxY (cadr pt))))
  (list (list mnX mnY 0) (list mxX mxY 0)))

;; ============================================================================
(princ "\n╔══════════════════════════════════════════════════╗")
(princ "\n║  SOLAR ARRAY v1.15 - CIRCULOS Y POLIGONOS       ║")
(princ "\n║  Soporta: CIRCLE, LWPOLYLINE, POLYLINE          ║")
(princ "\n║  Comando: SOLARARRAY                            ║")
(princ "\n╚══════════════════════════════════════════════════╝\n")
(princ)
