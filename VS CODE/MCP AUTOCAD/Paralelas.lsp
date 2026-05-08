;; ============================================================================
;; COMANDO: PARALELASPRO
;; ============================================================================
;; DESCRIPCIÓN:
;; Crea múltiples líneas paralelas a partir de una línea base seleccionada.
;; Las paralelas se distribuyen de forma simétrica y equidistante.
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: PARALELASPRO
;; 2. Selecciona una línea o polilínea base (haz clic en ella)
;; 3. Ingresa la cantidad de paralelas a crear (ej: 4)
;; 4. El programa crea las líneas automáticamente distribuidas simétricamente
;;
;; PARÁMETROS:
;; - Separación entre paralelas: 0.01 unidades (fija)
;; - Distribución: simétrica alrededor de la línea original
;; - Línea base: se mantiene, se crean líneas paralelas adicionales
;;
;; EJEMPLO 1: 1 Paralela
;; Original: ───────────
;; Resultado:
;;    ───────────  (paralela)
;; ───────────  (original)
;;
;; EJEMPLO 2: 4 Paralelas (simétricas)
;; Resultado:
;;  ───────────  (a 0.015 del centro)
;; ───────────   (a 0.005 del centro)
;; ───────────   (a -0.005 del centro)
;; ───────────   (a -0.015 del centro)
;;
;; TIPOS DE OBJETOS SOPORTADOS:
;; ✓ LINE (línea simple)
;; ✓ LWPOLYLINE (polilínea ligera)
;; ✓ 2DPOLYLINE (polilínea 2D)
;;
;; NOTAS:
;; - Todas las paralelas están a la misma distancia entre sí
;; - La separación es muy pequeña (0.01) para visualización técnica
;; - Las paralelas se crean perpendiculares a la línea base
;; - Si ingresas 0 o número negativo, no se crean paralelas
;; - La línea original se mantiene intacta
;;
;; CASOS DE USO EN PROYECTOS FOTOVOLTAICOS:
;; - Crear mallas de distribución simétricas
;; - Generar múltiples rutas de cableado
;; - Proyectar arrays de paneles
;; - Crear líneas de referencia para mediciones
;; ============================================================================

(defun c:PARALELASPRO (/ ent obj num sep mitad i dist offsets)

  (vl-load-com)

  ;; Mostrar instrucciones
  (alert "CREAR LÍNEAS PARALELAS\n\n"
         "Selecciona una línea o polilínea base.\n"
         "Especifica cuántas paralelas crear.\n"
         "Se distribuirán simétricamente con separación de 0.01 unidades.")

  ;; separación fija entre paralelas
  (setq sep 0.01)

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ SELECCIONAR LÍNEA BASE                ║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; seleccionar objeto
  (setq ent (car (entsel "\n📍 Selecciona línea o polilínea BASE: ")))

  (if ent
    (progn
      (setq obj (vlax-ename->vla-object ent))

      ;; validar tipo de objeto
      (if (member (vla-get-ObjectName obj)
                  '("AcDbLine" "AcDbPolyline" "AcDb2dPolyline"))
        (progn

          (princ "\n╔════════════════════════════════════════╗")
          (princ "\n║ CONFIGURAR PARALELAS                  ║")
          (princ "\n╚════════════════════════════════════════╝")

          ;; pedir número de paralelas
          (setq num (getint "\nIngresa CANTIDAD de paralelas a crear: "))

          (if (> num 0)
            (progn

              ;; calcular mitad para distribución simétrica
              (setq mitad (/ num 2.0))

              (princ (strcat "\n✓ Creando " (itoa num) " paralelas..."))
              (princ "\n⏳ Procesando:"))

              ;; crear offsets iterativamente
              (setq i 0)
              (while (< i num)

                ;; distancia centrada (simétrica)
                ;; La fórmula distribuye las líneas simétricamente
                (setq dist (* sep (- (+ i 0.5) mitad)))

                ;; crear offset (paralela)
                (vlax-invoke obj 'Offset dist)

                (princ ".")  ;; Mostrar progreso

                (setq i (1+ i))
              )

              ;; ─────────────────────────────────────────────────────────────────
              ;; MOSTRAR RESULTADOS
              ;; ─────────────────────────────────────────────────────────────────

              (alert (strcat "╔════════════════════════════════════════╗\n"
                             "║   ✓ PARALELAS CREADAS EXITOSAMENTE   ║\n"
                             "╚════════════════════════════════════════╝\n\n"
                             "Cantidad de paralelas: " (itoa num) "\n"
                             "Separación entre líneas: " (rtos sep 2 3) " unidades\n"
                             "Distribución: Simétrica\n\n"
                             "Cálculo de distancia:\n"
                             "dist = separación × (índice - mitad)\n\n"
                             "Línea base: Se mantiene intacta"))

              (princ (strcat "\n\n✓ Se crearon " (itoa num) " líneas paralelas correctamente."))
            )
            (alert "❌ Error: Ingresa una cantidad mayor a 0.")
          )
        )
        (alert "❌ Error: Debes seleccionar una LÍNEA o POLILÍNEA válida.\n\n"
               "Tipos soportados:\n"
               "✓ LINE (línea simple)\n"
               "✓ LWPOLYLINE (polilínea ligera)\n"
               "✓ 2DPOLYLINE (polilínea 2D)")
      )
    )
    (alert "❌ Operación cancelada: No seleccionaste ningún objeto.")
  )

  (princ)
)
