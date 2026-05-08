;; ============================================================================
;; COMANDO: STRINGS_VERTICAL_PROY
;; ============================================================================
;; DESCRIPCIÓN:
;; Dibuja automáticamente las líneas horizontales (strings) y las verticales
;; proyectadas en las mesas de paneles fotovoltaicos. Alterna colores para
;; visualización clara.
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: STRINGS_VERTICAL_PROY
;; 2. Responde las preguntas en orden:
;;    a) Selecciona esquina SUPERIOR de la mesa (haz clic)
;;    b) Selecciona esquina INFERIOR de la mesa (haz clic)
;;    c) Ingresa cantidad de mesas (ej: 5)
;;    d) Ingresa lado de verticales: L (izquierda) o R (derecha)
;;    e) Selecciona origen común horizontal (haz clic)
;;    f) Para cada mesa, selecciona su límite derecho (haz clic)
;;
;; PARÁMETROS:
;; - Líneas por mesa: 4 (fijas)
;; - Separación entre líneas: 0.01 unidades
;; - Proyección de bajada: 3.0 unidades bajo la mesa
;;
;; EJEMPLO PRÁCTICO:
;; Si tienes 3 mesas con 4 strings cada una:
;; - Líneas totales: 12 (3 mesas × 4 strings)
;; - Se crean 12 líneas horizontales con sus verticales espejo
;;
;; COLORES GENERADOS:
;; - Color 1 (Rojo): líneas pares
;; - Color 5 (Cian): líneas impares
;;
;; NOTAS:
;; - Las líneas horizontales conectan el origen con el límite de cada mesa
;; - Las verticales se crean proyectadas desde cada línea
;; - La separación pequeña (0.01) es para visualización técnica
;; - Al final, las líneas vuelven a "BYLAYER"
;; ============================================================================

(defun c:STRINGS_VERTICAL_PROY (/ pSup pInf yCentro
                                  nMesas i
                                  x0 x1 pFin
                                  sep totalLineas
                                  alturaTotal yInicio
                                  lineasMesa k y
                                  xVert yBajada
                                  lado signo)

  (vl-load-com)

  ;; Mostrar instrucciones
  (alert "DIBUJO DE STRINGS Y VERTICALES PROYECTADAS\n\n"
         "Paso 1: Selecciona las esquinas de una mesa\n"
         "Paso 2: Especifica cantidad de mesas\n"
         "Paso 3: Selecciona puntos límite para cada mesa\n\n"
         "Sistema de colores: Rojo/Cian alternados para visualizar strings")

  (setq sep 0.01)           ;; Separación entre líneas
  (setq lineasMesa 4)       ;; 4 strings por mesa (fijo)

  ;; ─────────────────────────────────────────────────────────────────
  ;; PASO 1: DIMENSIONES DE LA MESA
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 1: DIMENSIONES DE LA MESA        ║")
  (princ "\n╚════════════════════════════════════════╝")

  (setq pSup (getpoint "\n📍 Selecciona esquina SUPERIOR de la mesa: "))
  (if (null pSup)
    (progn
      (alert "Operación cancelada.")
      (exit)
    )
  )

  (setq pInf (getpoint "\n📍 Selecciona esquina INFERIOR de la mesa: "))
  (if (null pInf)
    (progn
      (alert "Operación cancelada.")
      (exit)
    )
  )

  ;; Calcular centro vertical
  (setq yCentro (/ (+ (cadr pSup) (cadr pInf)) 2.0))

  ;; ─────────────────────────────────────────────────────────────────
  ;; PASO 2: CANTIDAD DE MESAS Y LADO
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 2: CONFIGURACIÓN                 ║")
  (princ "\n╚════════════════════════════════════════╝")

  (setq nMesas (getint "\nIngresa cantidad de MESAS: "))
  (if (or (null nMesas) (<= nMesas 0))
    (progn
      (alert "Error: La cantidad de mesas debe ser mayor a 0.")
      (exit)
    )
  )

  ;; lado de verticales
  (setq lado
    (strcase
      (getstring "\nLado de verticales [L=Izquierda / R=Derecha]: ")
    )
  )

  (if (= lado "L")
    (setq signo -1)
    (setq signo 1)
  )

  (princ (strcat "\n✓ Configuración: "
                  (itoa nMesas)
                  " mesas × "
                  (itoa lineasMesa)
                  " strings = "
                  (itoa (* nMesas lineasMesa))
                  " líneas totales"))

  ;; ─────────────────────────────────────────────────────────────────
  ;; PASO 3: ORIGEN COMÚN Y CÁLCULOS
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 3: PUNTOS DE REFERENCIA          ║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; origen común
  (setq x0
    (car
      (getpoint "\n📍 Selecciona origen común HORIZONTAL: ")
    )
  )

  ;; cálculo global de posiciones
  (setq totalLineas (* nMesas lineasMesa))
  (setq alturaTotal (* (- totalLineas 1) sep))
  (setq yInicio (+ yCentro (/ alturaTotal 2.0)))

  ;; proyección mínima (3 unidades bajo la mesa)
  (setq yBajada (- yInicio 3.0))

  (princ (strcat "\n✓ Total de líneas: " (itoa totalLineas)))
  (princ (strcat "\n✓ Proyección de bajada: " (rtos yBajada 2 2)))

  ;; ─────────────────────────────────────────────────────────────────
  ;; PASO 4: DIBUJAR LÍNEAS HORIZONTALES
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 4: DIBUJANDO LÍNEAS HORIZONTALES ║")
  (princ "\n╚════════════════════════════════════════╝")

  (setq i 0)

  (while (< i nMesas)

    (setq pFin
      (getpoint
        (strcat
          "\n📍 Selecciona límite de MESA "
          (itoa (+ i 1))
          ": "
        )
      )
    )

    (setq x1 (car pFin))

    (setq k 0)

    ;; Dibujar 4 líneas horizontales por mesa
    (while (< k lineasMesa)

      (setq y
        (- yInicio (* (+ (* i lineasMesa) k) sep))
      )

      ;; alternar colores: rojo (1) y cian (5)
      (if (= (rem k 2) 0)
        (setvar "CECOLOR" "1")    ;; Rojo
        (setvar "CECOLOR" "5")    ;; Cian
      )

      ;; Dibujar línea horizontal
      (command "_LINE"
        (list x0 y)
        (list x1 y)
        ""
      )

      (princ ".")  ;; Mostrar progreso

      (setq k (1+ k))
    )

    (setq i (1+ i))
  )

  (princ "\n✓ Líneas horizontales completadas")

  ;; ─────────────────────────────────────────────────────────────────
  ;; PASO 5: DIBUJAR LÍNEAS VERTICALES PROYECTADAS
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ PASO 5: DIBUJANDO VERTICALES PROYECTADAS ║")
  (princ "\n╚════════════════════════════════════════╝")

  (setq k 0)

  (while (< k totalLineas)

    (setq y
      (- yInicio (* k sep))
    )

    ;; posición espejo según lado (L=izquierda, R=derecha)
    (setq xVert
      (+ x0 (* signo (+ 0.05 (* k sep))))
    )

    ;; alternar color
    (if (= (rem k 2) 0)
      (setvar "CECOLOR" "1")    ;; Rojo
      (setvar "CECOLOR" "5")    ;; Cian
    )

    ;; Dibujar línea vertical solamente
    (command "_LINE"
      (list xVert y)
      (list xVert yBajada)
      ""
    )

    (princ ".")  ;; Mostrar progreso

    (setq k (1+ k))
  )

  ;; Restablecer color a BYLAYER
  (setvar "CECOLOR" "BYLAYER")

  ;; ─────────────────────────────────────────────────────────────────
  ;; FINALIZACIÓN
  ;; ─────────────────────────────────────────────────────────────────

  (princ "\n✓ Líneas verticales completadas")

  (alert (strcat "╔════════════════════════════════════════╗\n"
                 "║     ✓ DIBUJO COMPLETADO EXITOSAMENTE  ║\n"
                 "╚════════════════════════════════════════╝\n\n"
                 "Líneas horizontales: " (itoa (* nMesas lineasMesa)) "\n"
                 "Líneas verticales proyectadas: " (itoa totalLineas) "\n\n"
                 "Colores: Rojo (pares) / Cian (impares)"))

  (princ)
)
