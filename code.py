# ===== Alarma 1 puerta – Pico 2W + KY-033 + KY-038(AO) + 7seg(1 díg) + Servo =====
# Estados de display:
#   0 -> desarmada (t0)
#   1 -> armada (monitorizando)
#   2 -> intrusión SOLO tracker (parpadea)
#   3 -> intrusión SOLO micrófono (parpadea)
#   4 -> intrusión confirmada por ambos (fijo)
#
# Botón KY-004 (GP17):
#   - Pulsación LARGA -> togglear ARMAR/DESARMAR
#   - Pulsación CORTA (si hay intrusión) -> reset intrusión (mantiene armado)
#
# Sensor mic KY-038 AO -> GP26/ADC0 (umbral por software con auto-calibración)
# Sensor tracker KY-033 -> GP14 (tu mapeo: 0 = disparo / "line present")
# Servo continuo -> GP18
# Display 7 seg (cátodo común) -> GP4,5,8,6,7,3,2

import time
import board
import digitalio
import pwmio
from adafruit_motor import servo
from analogio import AnalogIn

# -------------------- Configuración --------------------
CO_WINDOW_S      = 5.0    # ventana para considerar "ambos sensores"
BTN_DEBOUNCE_S   = 0.05
BTN_LONGPRESS_S  = 1.2
BLINK_MS         = 500    # parpadeo para 2/3
SERVO_ON_S       = 2.0    # tiempo de giro para bajar reja
RUN_SPEED        = 1.0    # 0..1 para servo continuo
SAMPLE_DELAY     = 0.002  # más rápido para seguir envolvente de audio

# Mic analógico (parámetros de detección)
MIC_CALIBRATE_S   = 3.0    # duración de auto-calibración al armar
MIC_FACTOR        = 2.5    # umbral = piso_de_ruido * factor
MIC_ABS_MIN       = 800.0  # umbral mínimo absoluto (unidades ADC de 16 bits)
MIC_DC_ALPHA      = 0.002  # filtro muy lento para DC (seguimiento del offset)
MIC_ENV_ATTACK    = 0.20   # ataque de envolvente (subidas)
MIC_ENV_DECAY     = 0.05   # decaimiento de envolvente (bajadas)
MIC_NOISE_ALPHA   = 0.02   # promedio exponencial durante calibración

# -------------------- Display 7 segmentos --------------------
display_pins = [board.GP4, board.GP5, board.GP8, board.GP6, board.GP7, board.GP3, board.GP2]
segments = [digitalio.DigitalInOut(p) for p in display_pins]
for s in segments:
    s.direction = digitalio.Direction.OUTPUT

digits = [
    (1,1,1,1,1,1,0),  # 0
    (0,1,1,0,0,0,0),  # 1
    (1,1,0,1,1,0,1),  # 2
    (1,1,1,1,0,0,1),  # 3
    (0,1,1,0,0,1,1),  # 4
    (1,0,1,1,0,1,1),  # 5
    (1,0,1,1,1,1,1),  # 6
    (1,1,1,0,0,0,0),  # 7
    (1,1,1,1,1,1,1),  # 8
    (1,1,1,1,0,1,1),  # 9
]
def display_digit(d: int):
    d = max(0, min(9, d))
    for pin, st in zip(segments, digits[d]):
        pin.value = st

def display_blank():
    for pin in segments:
        pin.value = 0

# -------------------- Entradas / Actuadores --------------------
# Botón (pull-up)
button = digitalio.DigitalInOut(board.GP17)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

# Mic analógico AO -> ADC0
mic_adc = AnalogIn(board.GP26)

# Tracker (KY-033)
trk = digitalio.DigitalInOut(board.GP14)
trk.direction = digitalio.Direction.INPUT
trk.pull = digitalio.Pull.DOWN
TRK_ACTIVE = 0      # tu mapeo: 0 = "line present" => disparo

# Servo continuo
pwm = pwmio.PWMOut(board.GP18, frequency=50)
gate = servo.ContinuousServo(pwm, min_pulse=1000, max_pulse=2000)
def servo_stop():       gate.throttle = 0.0
def servo_close_gate(): gate.throttle = RUN_SPEED
def servo_open_gate(): gate.throttle = -RUN_SPEED

# -------------------- Estados lógicos --------------------
DISARMED = 0
ARMED    = 1

sys_state = DISARMED
display_digit(0)

# Tiempos y flancos
now = time.monotonic
btn_last = button.value
btn_change_t = now()
btn_down_t = None
btn_handled = False

trk_last = trk.value
trk_change_t = now()

# Eventos y ventana
last_trk_event_t = None
last_mic_event_t = None

# Intrusión
alarm_code = 0   # 0 (nada), 2, 3, 4
blink_on = True
blink_change_ms = time.monotonic() * 1000

# Servo control
servo_until = 0.0

# Nuevo: estados de pendiente y bloqueo de sensores
pending_type = None           # None | 'trk' | 'mic'
pending_deadline_t = None     # timestamp límite para doble confirmación
sensors_locked = False        # True tras accionar servo (2/3 por timeout o 4 confirmada)

# Nuevo: estado de mic analógico (envolvente / umbral)
mic_dc = float(mic_adc.value)     # componente lenta (offset)
mic_env = 0.0                     # envolvente de amplitud
mic_noise_est = 0.0               # estimador de piso de ruido (sobre env)
mic_thresh = None                 # umbral dinámico
mic_over_prev = False             # estado anterior (para flanco)
mic_cal_end_t = 0.0               # fin de calibración (cuando sys_state->ARMED)

print("t0: desarmada (0)")

while True:
    t = now()
    ms = t * 1000.0

    # --------------- LECTURA BOTÓN (short / long) ---------------
    cur_btn = button.value
    if cur_btn != btn_last:
        btn_change_t = t
        btn_last = cur_btn
        if cur_btn is False:         # se presionó
            btn_down_t = t
            btn_handled = False
    # estable tras debounce
    if (t - btn_change_t) >= BTN_DEBOUNCE_S:
        # LONG PRESS -> toggle armado/desarmado
        if (btn_down_t is not None) and (not btn_handled) and (button.value is False):
            if (t - btn_down_t) >= BTN_LONGPRESS_S:
                btn_handled = True
                if sys_state == DISARMED:
                    sys_state = ARMED
                    alarm_code = 0
                    last_trk_event_t = None
                    last_mic_event_t = None
                    pending_type = None
                    pending_deadline_t = None
                    sensors_locked = False
                    servo_stop()
                    display_digit(1)
                    # iniciar calibración de mic
                    mic_dc = float(mic_adc.value)
                    mic_env = 0.0
                    mic_noise_est = 0.0
                    mic_thresh = None
                    mic_over_prev = False
                    mic_cal_end_t = t + MIC_CALIBRATE_S
                    print("[ARMADA] display=1 (monitorizando) + calib mic {:.1f}s".format(MIC_CALIBRATE_S))
                else:
                    sys_state = DISARMED
                    alarm_code = 0
                    last_trk_event_t = None
                    last_mic_event_t = None
                    pending_type = None
                    pending_deadline_t = None
                    sensors_locked = False
                    servo_open_gate()
                    servo_stop()
                    display_digit(0)
                    print("[DESARMADA] display=0")
        # SHORT PRESS -> reset alarma si existe
        if (btn_down_t is not None) and (cur_btn is True) and (not btn_handled):
            press_dt = t - btn_down_t
            btn_down_t = None
            if press_dt >= BTN_DEBOUNCE_S and press_dt < BTN_LONGPRESS_S:
                # Reset sólo si hay alarma y estamos armados
                if sys_state == ARMED and alarm_code in (2,3,4):
                    alarm_code = 0
                    pending_type = None
                    pending_deadline_t = None
                    sensors_locked = False
                    last_trk_event_t = None
                    last_mic_event_t = None
                    servo_open_gate()
                    servo_stop()
                    display_digit(1)
                    # rearmar calibración rápida del mic (opcional)
                    mic_dc = float(mic_adc.value)
                    mic_env = 0.0
                    mic_noise_est = 0.0
                    mic_thresh = None
                    mic_over_prev = False
                    mic_cal_end_t = t + MIC_CALIBRATE_S
                    print("[RESET] alarma -> display=1 (sigue armada) + recalib mic")

    # --------------- MIC ANALÓGICO: ENVOLVENTE + UMBRAL ---------------
    # Leer ADC (0..65535), separar DC lento y amplitud, y construir envolvente
    sample = float(mic_adc.value)
    mic_dc += (sample - mic_dc) * MIC_DC_ALPHA
    amp = abs(sample - mic_dc)
    if amp > mic_env:
        mic_env += (amp - mic_env) * MIC_ENV_ATTACK
    else:
        mic_env += (amp - mic_env) * MIC_ENV_DECAY

    # Calibración del piso de ruido al estar armada
    if sys_state == ARMED:
        if t <= mic_cal_end_t:
            # estimar piso de ruido sobre la envolvente
            if mic_noise_est == 0.0:
                mic_noise_est = mic_env
            else:
                mic_noise_est += (mic_env - mic_noise_est) * MIC_NOISE_ALPHA
            # aún sin umbral definitivo
            mic_thresh = None
        elif mic_thresh is None:
            # fijar umbral dinámico una vez termina la calibración
            mic_thresh = max(mic_noise_est * MIC_FACTOR, MIC_ABS_MIN)
            print("[MIC] calibrado: noise_est={:.0f}, thresh={:.0f}".format(mic_noise_est, mic_thresh))
    else:
        mic_thresh = None  # sin armar, no evaluamos

    # Detección por mic: flanco de cruce de umbral (solo si armada y no bloqueado)
    mic_over = False
    if sys_state == ARMED and (mic_thresh is not None):
        mic_over = mic_env >= mic_thresh
    mic_rising = (mic_over and not mic_over_prev)
    mic_over_prev = mic_over

    # --------------- LECTURA TRACKER + GENERACIÓN DE EVENTOS ---------------
    cur_trk = trk.value
    if cur_trk != trk_last:
        trk_change_t = t
        trk_last = cur_trk
        # flanco activo
        if cur_trk == TRK_ACTIVE and sys_state == ARMED and not sensors_locked:
            last_trk_event_t = t
            print("[EVENTO] Tracker")
            if pending_type == 'mic' and (t - last_mic_event_t) <= CO_WINDOW_S:
                # doble confirmación -> 4 (fijo) y accionar servo
                alarm_code = 4
                servo_close_gate(); servo_until = t + SERVO_ON_S
                sensors_locked = True
                print("[ALARMA] code=4 -> Servo ON (confirmada)")
            elif pending_type is None:
                # primer evento (solo tracker): pendiente 2 (parpadeo), sin servo
                pending_type = 'trk'
                pending_deadline_t = t + CO_WINDOW_S
                alarm_code = 2

    # Mic evento (flanco) si no está bloqueado
    if mic_rising and sys_state == ARMED and not sensors_locked:
        last_mic_event_t = t
        print("[EVENTO] Mic (analog > thresh)")
        if pending_type == 'trk' and (t - last_trk_event_t) <= CO_WINDOW_S:
            # doble confirmación -> 4 (fijo) y accionar servo
            alarm_code = 4
            servo_close_gate(); servo_until = t + SERVO_ON_S
            sensors_locked = True
            print("[ALARMA] code=4 -> Servo ON (confirmada)")
        elif pending_type is None:
            # primer evento (solo mic): pendiente 3 (parpadeo), sin servo
            pending_type = 'mic'
            pending_deadline_t = t + CO_WINDOW_S
            alarm_code = 3

    # --------------- LÓGICA DE TIMEOUT (2/3) ---------------
    if sys_state == ARMED and not sensors_locked:
        if pending_type is not None and pending_deadline_t is not None and t >= pending_deadline_t:
            # venció ventana sin segunda confirmación -> accionar servo con el código actual (2 o 3)
            servo_close_gate(); servo_until = t + SERVO_ON_S
            sensors_locked = True
            print(f"[ALARMA] code={alarm_code} -> Servo ON (timeout ventana)")

    # --------------- SERVO HOLD ---------------
    if servo_until > 0.0 and t >= servo_until:
        servo_stop()
        servo_until = 0.0
        print("[SERVO] OFF")

    # --------------- DISPLAY ----------------
    if sys_state == DISARMED:
        display_digit(0)
    else:
        if alarm_code == 0:
            display_digit(1)  # armada sin eventos
        elif alarm_code == 4:
            display_digit(4)  # fijo
        else:
            # parpadeo para 2 o 3
            if (ms - blink_change_ms) >= BLINK_MS:
                blink_change_ms = ms
                blink_on = not blink_on
            if blink_on:
                display_digit(alarm_code)  # 2 o 3
            else:
                display_blank()

    time.sleep(SAMPLE_DELAY)
