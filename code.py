# ===== Alarma 1 puerta – Pico 2W + KY-033 + KY-038(D0) + 7seg(1 díg) + Servo =====
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
# Sensor mic KY-038 D0 -> GP22 (activo cuando supera umbral del potenciómetro)
# Sensor tracker KY-033 -> GP14 (tu mapeo: 0 = disparo / "line present")
# Servo continuo -> GP18
# Display 7 seg (cátodo común) -> GP4,5,8,6,7,3,2

import time
import board
import digitalio
import pwmio
from adafruit_motor import servo

# -------------------- Configuración --------------------
CO_WINDOW_S      = 5.0    # ventana para considerar "ambos sensores"
BTN_DEBOUNCE_S   = 0.05
BTN_LONGPRESS_S  = 1.2
BLINK_MS         = 500    # parpadeo para 2/3
SERVO_ON_S       = 2.0    # tiempo de giro para bajar reja
RUN_SPEED        = 1.0    # 0..1 para servo continuo
SAMPLE_DELAY     = 0.01

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

# Mic digital D0
mic = digitalio.DigitalInOut(board.GP22)
mic.direction = digitalio.Direction.INPUT
MIC_ACTIVE = 0      # la mayoría de módulos tiran LOW cuando superan umbral (ajustá si es 1)

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
mic_last = mic.value
mic_change_t = now()

last_trk_event_t = None
last_mic_event_t = None

# Intrusión
alarm_code = 0   # 0 (nada), 2, 3, 4
blink_on = True
blink_change_ms = time.monotonic() * 1000

# Servo control
servo_until = 0.0

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
                    servo_stop()
                    display_digit(1)
                    print("[ARMADA] display=1 (monitorizando)")
                else:
                    sys_state = DISARMED
                    alarm_code = 0
                    last_trk_event_t = None
                    last_mic_event_t = None
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
                    servo_stop()
                    display_digit(1)
                    print("[RESET] alarma -> display=1 (sigue armada)")

    # --------------- LECTURA SENSORES ---------------
    cur_trk = trk.value
    if cur_trk != trk_last:
        trk_change_t = t
        trk_last = cur_trk
        # flanco activo
        if cur_trk == TRK_ACTIVE and sys_state == ARMED:
            last_trk_event_t = t
            print("[EVENTO] Tracker")

    cur_mic = mic.value
    if cur_mic != mic_last:
        mic_change_t = t
        mic_last = cur_mic
        if cur_mic == MIC_ACTIVE and sys_state == ARMED:
            last_mic_event_t = t
            print("[EVENTO] Mic")

    # --------------- LÓGICA DE ALARMA ---------------
    if sys_state == ARMED:
        new_code = alarm_code

        # ¿coinciden ambos dentro de la ventana?
        if last_trk_event_t and last_mic_event_t:
            if abs(last_trk_event_t - last_mic_event_t) <= CO_WINDOW_S:
                new_code = 4  # confirmada por ambos

        # Si aún no es 4, ver sólo uno
        if new_code != 4:
            # sólo tracker dentro de ventana sin mic
            if last_trk_event_t and (not last_mic_event_t or (t - last_mic_event_t) > CO_WINDOW_S):
                # pero solo si el evento de tracker es reciente
                if (t - last_trk_event_t) <= CO_WINDOW_S:
                    new_code = 2
            # sólo mic dentro de ventana sin tracker
            if last_mic_event_t and (not last_trk_event_t or (t - last_trk_event_t) > CO_WINDOW_S):
                if (t - last_mic_event_t) <= CO_WINDOW_S:
                    new_code = 3

        # Si cambió el código de alarma, actualizo y muevo servo
        if new_code in (2,3,4) and new_code != alarm_code:
            alarm_code = new_code
            servo_close_gate()
            servo_until = t + SERVO_ON_S
            print(f"[ALARMA] code={alarm_code}  -> Servo ON")

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