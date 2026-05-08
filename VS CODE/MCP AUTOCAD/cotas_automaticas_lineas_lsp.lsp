;; ============================================================================
;; COMANDO: COTA_SMART
;; ============================================================================
;; DESCRIPCIÓN:
;; Crea cotas automáticas para líneas, polilíneas, arcos y círculos seleccionados
;; Evita duplicar cotas con la misma distancia y ángulo
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: COTA_SMART
;; 2. Selecciona los elementos a cotizar (LINEAs, POLILÍNEAs, ARCs, CIRCLEs)
;; 3. El programa crea cotas alineadas automáticamente
;;
;; TIPOS DE ELEMENTOS SOPORTADOS:
;; - LINE (Líneas): Cota alineada a la línea
;; - LWPOLYLINE (Polilínea): Cota de cada segmento
;; - ARC (Arcos): Dimensión radial
;; - CIRCLE (Círculos): Dimensión radial
;;
;; NOTAS:
;; - Las cotas se crean perpendiculares a los elementos
;; - No duplica cotas si tienen igual distancia y ángulo
;; - Tolerancia de comparación: 0.01 unidades
;; ============================================================================

(defun c:COTA_SMART (/ ss i ent obj tipo
                     p1 p2 ang mid ptCota
                     dist j n len clave
                     listaCotas tol)

  (vl-load-com)

  ;; Mostrar instrucciones al usuario
  (alert "COTA_SMART\n\nSelecciona líneas, polilíneas, arcos o círculos.\nLas cotas se crearán automáticamente sin duplicados.")

  (setq dist 0)
  (setq tol 0.01)
  (setq listaCotas '())

  ;; función para comparar si ya existe
  (defun tramo-existe (clave lista / existe)
    (setq existe nil)
    (foreach item lista
      (if (equal item clave tol)
        (setq existe T)
      )
    )
    existe
  )

  (setq ss (ssget '((0 . "LINE,LWPOLYLINE,ARC,CIRCLE"))))

  (if ss
    (progn
      (setq i 0)

      (while (< i (sslength ss))

        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (setq tipo (cdr (assoc 0 (entget ent))))

        ;; LINEA
        (if (= tipo "LINE")
          (progn
            (setq p1 (cdr (assoc 10 (entget ent))))
            (setq p2 (cdr (assoc 11 (entget ent))))
            (setq len (distance p1 p2))
            (setq ang (angle p1 p2))

            (setq clave
              (list
                (rtos len 2 2)
                (rtos ang 2 2)
              )
            )

            (if (not (tramo-existe clave listaCotas))
              (progn
                (setq listaCotas (cons clave listaCotas))

                (setq mid
                  (list
                    (/ (+ (car p1) (car p2)) 2.0)
                    (/ (+ (cadr p1) (cadr p2)) 2.0)
                  )
                )

                (setq ptCota
                  (polar mid (+ ang (/ pi 2)) dist)
                )

                (command "_DIMALIGNED" p1 p2 ptCota)
              )
            )
          )
        )

        ;; POLILINEA - se cota cada segmento
        (if (= tipo "LWPOLYLINE")
          (progn
            (setq n (fix (vlax-curve-getEndParam obj)))
            (setq j 0)

            (while (< j n)

              (setq p1 (vlax-curve-getPointAtParam obj j))
              (setq p2 (vlax-curve-getPointAtParam obj (+ j 1)))

              (setq len (distance p1 p2))
              (setq ang (angle p1 p2))

              (setq clave
                (list
                  (rtos len 2 2)
                  (rtos ang 2 2)
                )
              )

              (if (not (tramo-existe clave listaCotas))
                (progn
                  (setq listaCotas (cons clave listaCotas))

                  (setq mid
                    (list
                      (/ (+ (car p1) (car p2)) 2.0)
                      (/ (+ (cadr p1) (cadr p2)) 2.0)
                    )
                  )

                  (setq ptCota
                    (polar mid (+ ang (/ pi 2)) dist)
                  )

                  (command "_DIMALIGNED" p1 p2 ptCota)
                )
              )

              (setq j (1+ j))
            )
          )
        )

        ;; ARC - dimensión radial
        (if (= tipo "ARC")
          (command "_DIMRADIUS" ent)
        )

        ;; CIRCLE - dimensión radial
        (if (= tipo "CIRCLE")
          (command "_DIMRADIUS" ent)
        )

        (setq i (1+ i))
      )

      (alert (strcat "✓ Cotas creadas correctamente\n"
                     "Total de cotas sin duplicados creadas"))
    )
    (alert "No se seleccionaron elementos válidos.\nSelecciona líneas, polilíneas, arcos o círculos.")
  )

  (princ)
)
