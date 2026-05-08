;; ============================================================================
;; COMANDO: MFILLET
;; ============================================================================
;; DESCRIPCIÓN:
;; Crea filetes (redondeos) automáticamente en los puntos de intersección
;; entre líneas horizontales y verticales. Procesa pares de líneas una a una.
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: MFILLET
;; 2. Selecciona todas las líneas HORIZONTALES (pueden ser 1 o más)
;;    - Presiona ENTER o clic derecho cuando termines de seleccionar
;; 3. Selecciona todas las líneas VERTICALES (DEBE ser la MISMA cantidad)
;;    - Presiona ENTER o clic derecho cuando termines de seleccionar
;; 4. El programa automáticamente:
;;    - Aparea línea horizontal 1 con línea vertical 1
;;    - Aparea línea horizontal 2 con línea vertical 2
;;    - Y así sucesivamente...
;;    - Crea un filete en cada intersección
;;
;; REQUISITOS:
;; ✓ Las líneas horizontales DEBEN intersectarse con las verticales
;; ✓ La cantidad de líneas horizontales DEBE ser igual a la de verticales
;; ✓ Los filetes se crean con el radio configurado en AutoCAD (variable FILLETRAD)
;;
;; EJEMPLO:
;; Si seleccionas:
;; - 4 líneas horizontales
;; - 4 líneas verticales
;; Resultado: 4 filetes, uno por cada pareja
;;
;; CAMBIAR RADIO DEL FILETE:
;; En la consola de AutoCAD, escribe: FILLETRAD
;; Luego ingresa el radio deseado (ej: 0.5)
;;
;; NOTAS:
;; - El radio del filete se toma de la variable FILLETRAD
;; - Si no hay intersección exacta, algunos filetes pueden no crearse
;; - Se recomienda que las líneas sean exactas y perpendiculares
;; - Verifica que la cantidad de líneas sea igual en ambos grupos
;; ============================================================================

(defun c:MFILLET (/ ssH ssV hLines vLines len i ent1 ent2)

  (vl-load-com)

  ;; Mostrar instrucciones
  (alert "CREAR FILETES EN INTERSECCIONES\n\n"
         "Paso 1: Selecciona TODAS las líneas HORIZONTALES\n"
         "Paso 2: Selecciona TODAS las líneas VERTICALES\n\n"
         "⚠️ IMPORTANTE: Ambos grupos deben tener la MISMA cantidad de líneas")

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 1: SELECCIONAR LÍNEAS HORIZONTALES║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; Seleccionar horizontales
  (prompt "\n🔴 Selecciona TODAS las líneas HORIZONTALES (ENTER para terminar): ")
  (setq ssH (ssget))

  (if (null ssH)
    (progn
      (alert "Error: No seleccionaste líneas horizontales.")
      (exit)
    )
  )

  (princ (strcat "\n✓ Líneas horizontales seleccionadas: " (itoa (sslength ssH))))

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 2: SELECCIONAR LÍNEAS VERTICALES ║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; Seleccionar verticales
  (prompt "\n🔵 Selecciona TODAS las líneas VERTICALES (ENTER para terminar): ")
  (setq ssV (ssget))

  (if (null ssV)
    (progn
      (alert "Error: No seleccionaste líneas verticales.")
      (exit)
    )
  )

  (princ (strcat "\n✓ Líneas verticales seleccionadas: " (itoa (sslength ssV))))

  ;; Verificar que existan selecciones
  (if (and ssH ssV)
    (progn

      ;; función interna para convertir selection set a lista
      (defun ss->list (ss / i lst)
        (setq i 0 lst '())
        (repeat (sslength ss)
          (setq lst (cons (ssname ss i) lst))
          (setq i (1+ i))
        )
        (reverse lst)
      )

      ;; Convertir a listas
      (setq hLines (ss->list ssH))
      (setq vLines (ss->list ssV))

      ;; VALIDACIÓN CRÍTICA: mismo número de líneas
      (if (/= (length hLines) (length vLines))
        (progn
          (alert (strcat "❌ ERROR: Cantidades diferentes\n\n"
                         "Líneas horizontales: " (itoa (length hLines)) "\n"
                         "Líneas verticales: " (itoa (length vLines)) "\n\n"
                         "Deben ser iguales. Intenta de nuevo."))
          (exit)
        )
        (progn

          ;; ─────────────────────────────────────────────────────────────────
          ;; CREAR FILETES EN PARES
          ;; ─────────────────────────────────────────────────────────────────

          (princ "\n╔════════════════════════════════════════╗")
          (princ "\n║ PASO 3: CREANDO FILETES               ║")
          (princ "\n╚════════════════════════════════════════╝")

          (setq len (length hLines))
          (setq i 0)

          (princ (strcat "\n⏳ Creando " (itoa len) " filetes..."))

          ;; Procesar cada pareja
          (repeat len

            (setq ent1 (nth i hLines))
            (setq ent2 (nth i vLines))

            (princ (strcat "\n  [" (itoa (+ i 1)) "/" (itoa len) "]"))

            ;; Ejecutar comando FILLET para esta pareja
            (command "_.FILLET" ent1 ent2)

            (setq i (1+ i))
          )

          ;; ─────────────────────────────────────────────────────────────────
          ;; FINALIZACIÓN
          ;; ─────────────────────────────────────────────────────────────────

          (alert (strcat "╔════════════════════════════════════════╗\n"
                         "║     ✓ FILETES COMPLETADOS EXITOSAMENTE║\n"
                         "╚════════════════════════════════════════╝\n\n"
                         "Filetes creados: " (itoa len) "\n\n"
                         "Radio del filete: " (rtos (getvar "FILLETRAD") 2 3) " unidades\n\n"
                         "Para cambiar el radio, usa el comando FILLETRAD"))

          (princ "\n✓ Operación completada.")
        )
      )
    )
    (alert "❌ Error: No se seleccionaron líneas.")
  )

  (princ)
)
