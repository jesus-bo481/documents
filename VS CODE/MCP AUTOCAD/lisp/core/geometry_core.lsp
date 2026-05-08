;; ============================================================================
;; GEOMETRY CORE — Módulo geométrico compartido
;; Migrado y modularizado desde solar_array_layout_v1.15.lsp
;; Estas funciones son la base de todos los demás módulos.
;; Cargar con: (load "...lisp/core/geometry_core.lsp")
;; ============================================================================

;; ── Ray casting (point-in-polygon) ──────────────────────────────────────────
(defun gc:pip (px py pts / n i j xi yi xj yj cnt)
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

;; ── Bounding box ────────────────────────────────────────────────────────────
(defun gc:bbox (pts / mnX mxX mnY mxY pt)
  (setq mnX (car  (car pts)) mxX mnX
        mnY (cadr (car pts)) mxY mnY)
  (foreach pt pts
    (if (< (car  pt) mnX) (setq mnX (car  pt)))
    (if (> (car  pt) mxX) (setq mxX (car  pt)))
    (if (< (cadr pt) mnY) (setq mnY (cadr pt)))
    (if (> (cadr pt) mxY) (setq mxY (cadr pt))))
  (list (list mnX mnY) (list mxX mxY)))

;; ── Extracción de vértices de polilínea ─────────────────────────────────────
(defun gc:poly-pts (ent / data pts item)
  (setq data (entget ent) pts '())
  (foreach item data
    (if (= (car item) 10)
      (setq pts (append pts (list (cdr item))))))
  pts)

;; ── Discretizar círculo en polígono de N lados ──────────────────────────────
(defun gc:circle-to-poly (cx cy r n / pts step k ang)
  (setq pts '() step (/ (* 2.0 pi) n) k 0)
  (while (< k n)
    (setq ang (* k step))
    (setq pts (append pts
      (list (list (+ cx (* r (cos ang)))
                  (+ cy (* r (sin ang)))
                  0.0))))
    (setq k (+ k 1)))
  pts)

;; ── Colisión rectángulo-círculo (punto más cercano) ─────────────────────────
(defun gc:rect-circle-hit (x1 y1 x2 y2 ccx ccy cr / nearX nearY dist)
  (setq nearX (max x1 (min ccx x2))
        nearY (max y1 (min ccy y2))
        dist  (sqrt (+ (* (- ccx nearX) (- ccx nearX))
                       (* (- ccy nearY) (- ccy nearY)))))
  (< dist cr))

;; ── Validación completa de posición de bloque ────────────────────────────────
;; bx,by = esquina inferior izquierda | bw,bh = ancho y alto
;; boundary = lista de puntos del polígono límite
;; polyObs = lista de polígonos obstáculo (lista de listas de puntos)
;; circObs = lista de (cx cy r)
(defun gc:can-place (bx by bw bh boundary polyObs circObs /
    x1 y1 x2 y2 cx cy ok obsIdx obsPts vi vx vy circ ccx ccy cr)

  (setq x1 bx y1 by x2 (+ bx bw) y2 (+ by bh)
        cx (+ bx (/ bw 2.0)) cy (+ by (/ bh 2.0)))

  ;; 1) Las 4 esquinas + centro dentro del límite
  (setq ok
    (and (gc:pip x1 y1 boundary)
         (gc:pip x2 y1 boundary)
         (gc:pip x2 y2 boundary)
         (gc:pip x1 y2 boundary)
         (gc:pip cx cy boundary)))

  ;; 2) Colisión con obstáculos poligonales
  (if (and ok polyObs)
    (progn
      (setq obsIdx 0)
      (while (and ok (< obsIdx (length polyObs)))
        (setq obsPts (nth obsIdx polyObs))
        (if (or (gc:pip x1 y1 obsPts) (gc:pip x2 y1 obsPts)
                (gc:pip x2 y2 obsPts) (gc:pip x1 y2 obsPts)
                (gc:pip cx cy obsPts))
          (setq ok nil))
        (if ok
          (progn
            (setq vi 0)
            (while (and ok (< vi (length obsPts)))
              (setq vx (car (nth vi obsPts)) vy (cadr (nth vi obsPts)))
              (if (and (> vx x1)(< vx x2)(> vy y1)(< vy y2))
                (setq ok nil))
              (setq vi (+ vi 1)))))
        (setq obsIdx (+ obsIdx 1)))))

  ;; 3) Colisión con obstáculos circulares
  (if (and ok circObs)
    (progn
      (setq obsIdx 0)
      (while (and ok (< obsIdx (length circObs)))
        (setq circ (nth obsIdx circObs)
              ccx (car circ) ccy (cadr circ) cr (caddr circ))
        (if (gc:rect-circle-hit x1 y1 x2 y2 ccx ccy cr)
          (setq ok nil))
        (setq obsIdx (+ obsIdx 1)))))

  ok)

(princ "\n[geometry_core.lsp cargado — prefijo gc:]")
(princ)
