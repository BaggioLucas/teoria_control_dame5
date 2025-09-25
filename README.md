### Sistema de seguridad automático – Raspberry Pi Pico 2W

Sistema de asistencia al sereno para turno nocturno. Opera por defecto en modo automático y acepta intervención humana mediante un botón de control. Implementa doble validación de intrusión con ventana de confirmación y señalización por display de 7 segmentos.

---

## Escenario y comportamiento
- **Estado inicial (0)**: alarma desarmada. El display muestra 0.
- **Armar (1)**: mantener presionado el botón KY-004 (long press). Se calibra el micrófono durante `MIC_CALIBRATE_S` segundos y queda monitorizando.
- **Detección por sensores**:
  - **Tracker KY-033** (digital) y **micrófono KY-038** (AO analógico) por oficina.
  - Reglas de decisión (con ventana de doble confirmación `CO_WINDOW_S`):
    - Solo micrófono sobre umbral → display parpadea en 3.
    - Solo tracker activo → display parpadea en 2.
    - Ambos dentro de `CO_WINDOW_S` → display 4 fijo (confirmada).
- **Acción del servo**:
  - Si llega doble confirmación → acciona servo inmediatamente con código 4.
  - Si no llega el segundo sensor en `CO_WINDOW_S` → acciona servo con el código simple (2 o 3) al expirar la ventana.
  - Tras accionar, los sensores quedan bloqueados hasta reset/desarme.
- **Reset corto**: pulsación breve mientras está armado y con alarma (2/3/4) limpia la condición, mantiene armado (display 1) y re-calibra el micrófono.
- **Desarmar (0)**: mantener presionado el botón (long press). El display vuelve a 0 y los servos se detienen/abren.

### Estados del display (1 dígito)
- **0**: desarmada.
- **1**: armada sin eventos.
- **2**: intrusión solo tracker (parpadeo).
- **3**: intrusión solo micrófono (parpadeo).
- **4**: intrusión confirmada por tracker + mic (fijo).

---

## Hardware requerido
- **Raspberry Pi Pico 2W** (CircuitPython)
- **KY-033** (tracker/reflectivo)
- **KY-038** (usar salida analógica AO; D0 no se usa)
- **Display 7 segmentos** 1 dígito, cátodo común (con resistencias de segmento)
- **Servo de rotación continua** (alimentación acorde a modelo)
- **Botón KY-004**
- Cables, protoboard y fuente 5V/3.3V según servo (masa común con la Pico)

---

---

## Software
- Plataforma: **CircuitPython** en la Pico 2W.
- Archivo principal: `code.py` (copiar a la raíz del dispositivo `CIRCUITPY`).
- Librerías usadas (en `CIRCUITPY/lib/`):
  - `adafruit_motor/servo`
  - `analogio`
  - `digitalio`
  - `pwmio`

Pasos rápidos:
1) Instalar CircuitPython en la Pico 2W.
2) Crear carpeta `lib` en `CIRCUITPY` si no existe.
3) Copiar las librerías requeridas dentro de `CIRCUITPY/lib/`.
4) Copiar `code.py` a la raíz de `CIRCUITPY`.

---

## Parámetros configurables (en `code.py`)
- **Ventanas y tiempos**
  - `CO_WINDOW_S = 5.0` ventana para doble confirmación.
  - `SERVO_ON_S = 2.0` tiempo de giro del servo al accionar.
  - `BTN_DEBOUNCE_S = 0.05` antibounce botón.
  - `BTN_LONGPRESS_S = 1.2` umbral de pulsación larga.
  - `BLINK_MS = 500` período de parpadeo para 2/3.
  - `SAMPLE_DELAY = 0.002` retardo de muestreo del mic.
- **Servo**
  - `RUN_SPEED = 1.0` velocidad (0..1) del servo continuo al cerrar la reja.
- **Micrófono (KY-038 AO)**
  - `MIC_CALIBRATE_S = 3.0` duración de auto-calibración al armar.
  - `MIC_FACTOR = 2.5` sensibilidad: umbral = piso_ruido × factor.
  - `MIC_ABS_MIN = 800.0` umbral absoluto mínimo.
  - `MIC_DC_ALPHA = 0.002` constante del filtro de DC.
  - `MIC_ENV_ATTACK = 0.20` ataque de envolvente.
  - `MIC_ENV_DECAY = 0.05` decaimiento de envolvente.
  - `MIC_NOISE_ALPHA = 0.02` promedio exponencial para estimar ruido.

### Cómo se estima el umbral del mic (KY-038 AO)
1) Se muestrea el ADC (0..65535) y se separa el componente DC con un filtro lento.
2) Se calcula `amp = abs(muestra - DC)` y se construye una envolvente con ataque/decay.
3) Durante `MIC_CALIBRATE_S` al armar, se promedia la envolvente para estimar el piso de ruido.
4) Al finalizar, se fija el umbral: `umbral = max(piso * MIC_FACTOR, MIC_ABS_MIN)`.
   - Mayor `MIC_FACTOR` → menos sensible (requiere ruido mayor).
   - `MIC_ABS_MIN` garantiza un piso si el ambiente es muy silencioso.

---

## Flujo de uso
1) Encender la Pico con `code.py` en `CIRCUITPY` → display en 0.
2) Mantener botón presionado (long press) para armar → display 1 y comienza la calibración del mic por `MIC_CALIBRATE_S`.
3) Ante primer sensor:
   - Tracker: display parpadea en 2.
   - Mic: display parpadea en 3.
4) Durante `CO_WINDOW_S`:
   - Si llega el segundo sensor → display 4 fijo y servo ON inmediatamente.
   - Si no llega → al expirar la ventana, servo ON con 2 o 3.
5) Sensores quedan bloqueados hasta reset/desarme.
6) Reset corto (short press) si está armado y en alarma (2/3/4): limpia alarma, vuelve a 1 y re-calibra mic.
7) Long press para desarmar: display 0, el servo se detiene/abre y sistema inactivo.

---

## Logs por consola (reales en `code.py`)
- `[MIC] calibrado: noise_est=..., thresh=...`
- `[EVENTO] Tracker`
- `[EVENTO] Mic (analog > thresh)`
- `[ALARMA] code=4 -> Servo ON (confirmada)`
- `[ALARMA] code=2|3 -> Servo ON (timeout ventana)`
- `[RESET] alarma -> display=1 (sigue armada) + recalib mic`
- `[ARMADA] display=1 (monitorizando) + calib mic ...s`
- `[DESARMADA] display=0`
- `[SERVO] OFF`

---
