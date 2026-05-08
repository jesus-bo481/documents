;; ============================================================================
;; COMANDO: METRADO_GUIADO
;; ============================================================================
;; DESCRIPCIÓN:
;; Realiza un metrado (medición) guiado de cables positivos y negativos
;; para cada string de cada inversor. Exporta resultados a un archivo CSV.
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: METRADO_GUIADO
;; 2. Ingresa cantidad de inversores (ej: 5)
;; 3. Ingresa cantidad de strings por inversor (ej: 4)
;; 4. Para cada string, selecciona:
;;    - Primero: cable POSITIVO (haz clic en él)
;;    - Luego: cable NEGATIVO (haz clic en él)
;; 5. Los resultados se guardan en: C:\Temp\metrado_guiado_strings.csv
;;
;; FORMATO DEL ARCHIVO CSV GENERADO:
;; STRING | POSITIVO_M | NEGATIVO_M | TOTAL_M
;; I1S1   | 45.50      | 45.50      | 91.00
;; I1S2   | 42.30      | 42.30      | 84.60
;;
;; EJEMPLO:
;; Si tienes 2 inversores con 3 strings cada uno:
;; - Inversor 1: I1S1, I1S2, I1S3
;; - Inversor 2: I2S1, I2S2, I2S3
;;
;; NOTAS:
;; - Asegúrate que la carpeta C:\Temp\ existe
;; - Los cables deben ser líneas o polilíneas
;; - Las medidas se toman en las unidades actuales del dibujo
;; ============================================================================

(defun c:METRADO_GUIADO (/ nInv nStr inv str
                           tag entPos entNeg
                           objPos objNeg
                           lenPos lenNeg
                           results item
                           file filepath)

  (vl-load-com)

  ;; Mostrar instrucciones iniciales
  (alert "METRADO GUIADO DE STRINGS\n\nResponde las preguntas y luego selecciona los cables cuando se pida.")

  (setq results '())

  ;; INPUTS
  (setq nInv (getint "\nIngrese cantidad de inversores: "))
  (setq nStr (getint "\nIngrese cantidad de strings por inversor: "))

  ;; Validar entradas
  (if (or (<= nInv 0) (<= nStr 0))
    (progn
      (alert "Error: Los valores deben ser mayores a 0.")
      (exit)
    )
  )

  ;; LOOP PRINCIPAL
  (setq inv 1)

  (while (<= inv nInv)

    (setq str 1)

    (while (<= str nStr)

      ;; Crear identificador del string (ej: I1S1, I1S2, etc.)
      (setq tag
        (strcat
          "I"
          (itoa inv)
          "S"
          (itoa str)
        )
      )

      (princ
        (strcat
          "\n════════════════════════════════"
          "\n--- MEDIENDO STRING: "
          tag
          " ---"
          "\n════════════════════════════════"
        )
      )

      ;; CABLE POSITIVO
      (setq entPos
        (car
          (entsel
            (strcat
              "\n🔴 Seleccione cable POSITIVO para "
              tag
              ": "
            )
          )
        )
      )

      ;; CABLE NEGATIVO
      (setq entNeg
        (car
          (entsel
            (strcat
              "\n⚫ Seleccione cable NEGATIVO para "
              tag
              ": "
            )
          )
        )
      )

      ;; MEDIR LONGITUDES
      (if (and entPos entNeg)
        (progn
          (setq objPos (vlax-ename->vla-object entPos))
          (setq objNeg (vlax-ename->vla-object entNeg))

          (setq lenPos (vlax-get objPos 'Length))
          (setq lenNeg (vlax-get objNeg 'Length))

          ;; Guardar resultados
          (setq results
            (append results
              (list
                (list
                  tag
                  lenPos
                  lenNeg
                  (+ lenPos lenNeg)
                )
              )
            )
          )

          ;; Mostrar en consola
          (princ
            (strcat
              "\n✓ "
              tag
              " | POSITIVO: "
              (rtos lenPos 2 2)
              " m | NEGATIVO: "
              (rtos lenNeg 2 2)
              " m | TOTAL: "
              (rtos (+ lenPos lenNeg) 2 2)
              " m"
            )
          )
        )
        (alert (strcat "Error: No se seleccionaron los cables para " tag))
      )

      (setq str (1+ str))
    )

    (setq inv (1+ inv))
  )

  ;; EXPORTAR CSV
  (setq filepath "C:/Temp/metrado_guiado_strings.csv")
  
  ;; Intentar crear carpeta si no existe
  (if (not (findfile "C:/Temp/"))
    (progn
      (alert "Advertencia: La carpeta C:\\Temp\\ no existe.\nCrea la carpeta manualmente antes de continuar.")
    )
  )

  ;; Crear archivo CSV
  (setq file (open filepath "w"))

  ;; Encabezado CSV
  (write-line "STRING,POSITIVO_M,NEGATIVO_M,TOTAL_M" file)

  ;; Escribir datos
  (foreach item results
    (write-line
      (strcat
        (nth 0 item) ","
        (rtos (nth 1 item) 2 2) ","
        (rtos (nth 2 item) 2 2) ","
        (rtos (nth 3 item) 2 2)
      )
      file
    )
  )

  (close file)

  ;; Mensaje final
  (princ
    (strcat
      "\n\n╔════════════════════════════════════════╗"
      "\n║  ✓ METRADO COMPLETADO EXITOSAMENTE   ║"
      "\n╚════════════════════════════════════════╝"
      "\n\nArchivo exportado en:"
      "\n" filepath
      "\n\nTotal de strings medidos: " (itoa (length results))
    )
  )

  (princ)
)
