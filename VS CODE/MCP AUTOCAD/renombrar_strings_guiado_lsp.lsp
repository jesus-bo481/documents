;; ============================================================================
;; COMANDO: RENOMBRAR_STRINGS_GUIADO
;; ============================================================================
;; DESCRIPCIÓN:
;; Renombra automáticamente textos en el dibujo asignándoles etiquetas de
;; inversores y strings (ej: I1S1, I1S2, I2S1, etc.)
;; Se ejecuta de forma guiada, pidiendo seleccionar cada texto uno por uno.
;;
;; CÓMO USAR:
;; 1. Escribe en la consola: RENOMBRAR_STRINGS_GUIADO
;; 2. Ingresa cantidad de inversores (ej: 3)
;; 3. Ingresa cantidad de strings por inversor (ej: 4)
;; 4. Para cada string, selecciona el texto a renombrar (haz clic)
;; 5. El texto se actualiza automáticamente con el nombre generado
;;
;; SECUENCIA AUTOMÁTICA:
;; Si tienes 2 inversores con 3 strings cada uno:
;; - I1S1 → Primer inversor, String 1
;; - I1S2 → Primer inversor, String 2
;; - I1S3 → Primer inversor, String 3
;; - I2S1 → Segundo inversor, String 1
;; - I2S2 → Segundo inversor, String 2
;; - I2S3 → Segundo inversor, String 3
;;
;; TOTAL DE TEXTOS A RENOMBRAR:
;; Fórmula: Cantidad de Inversores × Strings por Inversor
;; Ejemplo: 2 inversores × 3 strings = 6 textos
;;
;; REQUISITOS:
;; ✓ Los textos deben existir en el dibujo (TEXT o MTEXT)
;; ✓ Deben ser seleccionables con un clic
;; ✓ No importa el contenido anterior del texto
;;
;; TIPOS DE TEXTOS SOPORTADOS:
;; ✓ TEXT (texto simple)
;; ✓ MTEXT (texto multilínea)
;; ✓ TEXTO DINÁMICO
;;
;; FLUJO DE TRABAJO RECOMENDADO:
;; 1. Crea todos los textos (pueden estar vacíos)
;; 2. Coloca los textos en sus posiciones (cerca de los strings)
;; 3. Ejecuta este comando
;; 4. Selecciona cada texto en orden
;;
;; NOTAS:
;; - Si no seleccionas texto para un string, se omite sin error
;; - Puedes saltarte strings presionando ESC (sin seleccionar)
;; - Todos los textos se asignan automáticamente en secuencia
;; - La estructura de nombres es: I + Número Inversor + S + Número String
;;
;; EJEMPLO PRÁCTICO:
;; Tienes 1 inversor con 4 strings:
;; Paso 1: Ingresa 1 (un inversor)
;; Paso 2: Ingresa 4 (cuatro strings)
;; Paso 3-6: Selecciona 4 textos que se renombrarán como:
;;   - I1S1
;;   - I1S2
;;   - I1S3
;;   - I1S4
;; ============================================================================

(defun c:RENOMBRAR_STRINGS_GUIADO (/ nInv nStr inv str entTxt objTxt nuevoTag totalTxts contador)

  (vl-load-com)

  ;; Mostrar instrucciones
  (alert "RENOMBRAR STRINGS AUTOMÁTICAMENTE\n\n"
         "Este comando renombra textos secuencialmente.\n\n"
         "Formato de nombres: I{Inversor}S{String}\n"
         "Ejemplo: I1S1, I1S2, I2S1, I2S2, etc.")

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ CONFIGURACIÓN INICIAL                 ║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; Inputs
  (setq nInv (getint "\nIngresa cantidad de INVERSORES: "))

  (if (or (null nInv) (<= nInv 0))
    (progn
      (alert "Error: Ingresa un número válido de inversores.")
      (exit)
    )
  )

  (setq nStr (getint "\nIngresa cantidad de STRINGS POR INVERSOR: "))

  (if (or (null nStr) (<= nStr 0))
    (progn
      (alert "Error: Ingresa un número válido de strings.")
      (exit)
    )
  )

  ;; Calcular total
  (setq totalTxts (* nInv nStr))

  (princ (strcat "\n✓ Inversores: " (itoa nInv)))
  (princ (strcat "\n✓ Strings por inversor: " (itoa nStr)))
  (princ (strcat "\n✓ TOTAL de textos a renombrar: " (itoa totalTxts)))

  (princ "\n╔════════════════════════════════════════╗")
  (princ "\n║ SELECCIONAR Y RENOMBRAR TEXTOS        ║")
  (princ "\n╚════════════════════════════════════════╝")

  ;; LOOP PRINCIPAL
  (setq contador 0)
  (setq inv 1)

  (while (<= inv nInv)
    (setq str 1)

    (while (<= str nStr)

      ;; Crear nombre automático
      (setq nuevoTag
        (strcat "I" (itoa inv) "S" (itoa str))
      )

      (setq contador (1+ contador))

      ;; Pedir selección
      (princ
        (strcat
          "\n["
          (itoa contador)
          "/"
          (itoa totalTxts)
          "] 🏷️  Selecciona texto a renombrar como → "
          nuevoTag
          ": "
        )
      )

      ;; Seleccionar texto
      (setq entTxt (car (entsel)))

      ;; Procesar selección
      (if entTxt
        (progn
          ;; Intentar obtener el objeto de texto
          (setq objTxt (vlax-ename->vla-object entTxt))

          ;; Verificar si tiene propiedad TextString
          (if (vlax-property-available-p objTxt 'TextString)
            (progn
              ;; Cambiar contenido del texto
              (vla-put-TextString objTxt nuevoTag)

              ;; Confirmar en consola
              (princ (strcat "\n✓ Renombrado a: " nuevoTag))
            )
            (progn
              ;; No es un texto válido
              (princ "\n❌ Error: El objeto seleccionado no es un TEXTO válido.")
              (princ "\n   Tipos válidos: TEXT, MTEXT")
            )
          )
        )
        (progn
          ;; No se seleccionó nada
          (princ "\n⚠️  No se seleccionó texto, se omite.")
        )
      )

      (setq str (1+ str))
    )

    (setq inv (1+ inv))
  )

  ;; ─────────────────────────────────────────────────────────────────
  ;; FINALIZACIÓN
  ;; ─────────────────────────────────────────────────────────────────

  (alert (strcat "╔════════════════════════════════════════╗\n"
                 "║  ✓ RENOMBRADO COMPLETADO EXITOSAMENTE ║\n"
                 "╚════════════════════════════════════════╝\n\n"
                 "Textos procesados: " (itoa totalTxts) "\n\n"
                 "Estructura de nombres:\n"
                 "I = Inversor | S = String\n\n"
                 "Ejemplos:\n"
                 "I1S1 = Inversor 1, String 1\n"
                 "I2S3 = Inversor 2, String 3\n"
                 "I" (itoa nInv) "S" (itoa nStr) " = Último"))

  (princ "\n✓ Operación finalizada correctamente.")
  (princ)
)
