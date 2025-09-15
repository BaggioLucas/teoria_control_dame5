import time
import board
import digitalio
import pwmio
from adafruit_motor import servo

# ----- Display 7 segmentos -----
display1_pins = [board.GP4, board.GP5, board.GP8, board.GP6, board.GP7, board.GP3, board.GP2]
display1_segments = [digitalio.DigitalInOut(p) for p in display1_pins]
for s in display1_segments:
    s.direction = digitalio.Direction.OUTPUT

digit_patterns = [
    (1,1,1,1,1,1,0),  # 0
    (0,1,1,0,0,0,0),  # 1
    (1,1,0,1,1,0,1),  # 2
    (1,1,1,1,0,0,1),  # 3
    (0,1,1,0,0,1,1),  # 4
    (1,0,1,1,0,1,1),  # 5
    (1,0,1,1,1,1,1),  # 6
    (1,1,1,0,0,0,0),  # 7
    (1,1,1,1,1,1,1),  # 8
    (1,1,1,1,0,1,1)   # 9
]

def display_digit(d):
    for pin, state in zip(display1_segments, digit_patterns[d]):
        pin.value = state

# ----- Entradas (ALIMENTAR DESDE 3V3/GND, NO DESDE GPIOS) -----
# Botón: GP17 con pull-up interno; botón entre GP17 y GND
button_in = digitalio.DigitalInOut(board.GP17)
button_in.direction = digitalio.Direction.INPUT
button_in.pull = digitalio.Pull.UP   # reposo = HIGH; presionado = LOW

# KY-038 D0 en GP22 (si hace falta, usar Pull.UP)
sound_in = digitalio.DigitalInOut(board.GP22)
sound_in.direction = digitalio.Direction.INPUT

# Sensor de línea en GP14 con pull-down (tu mapeo: 1 => "No line", 0 => "Line")
line_in = digitalio.DigitalInOut(board.GP14)
line_in.direction = digitalio.Direction.INPUT
line_in.pull = digitalio.Pull.DOWN

# ----- SERVO CONTINUO en GP18 -----
pwm = pwmio.PWMOut(board.GP18, frequency=50)
# Ajusta min_pulse/max_pulse si no se detiene en 0.0
my_servo = servo.ContinuousServo(pwm, min_pulse=1000, max_pulse=2000)

RUN_SPEED = 1.0  # velocidad de giro (0..1)

# ----- Estado inicial -----
contador = 0
display_digit(contador)

BTN_STABLE  = 0.06
SND_STABLE  = 0.02
LINE_STABLE = 0.04
SAMPLE_DELAY = 0.008

now = time.monotonic()

btn_idle = True
btn_last = button_in.value
btn_last_change = now
btn_armed = True

snd_idle = sound_in.value
snd_last = snd_idle
snd_last_change = now
snd_armed = True

line_idle = line_in.value
line_last = line_idle
line_last_change = now
line_armed = True

print("Inicio. button:", btn_last, " sound:", snd_idle, " line:", line_idle)

while True:
    now = time.monotonic()

    # ----- BOTÓN -----
    cur_btn = button_in.value
    if cur_btn != btn_last:
        btn_last_change = now
        btn_last = cur_btn
    if (now - btn_last_change) >= BTN_STABLE:
        if btn_armed and (cur_btn == False) and (btn_idle == True):
            contador = (contador + 1) % 10
            display_digit(contador)
            print("Evento: Botón ->", contador)
            btn_armed = False
        elif (not btn_armed) and (cur_btn == btn_idle):
            btn_armed = True

    # ----- SONIDO -----
    cur_snd = sound_in.value
    if cur_snd != snd_last:
        snd_last_change = now
        snd_last = cur_snd
    if (now - snd_last_change) >= SND_STABLE:
        if snd_armed and cur_snd != snd_idle:
            contador = (contador - 1) % 10
            display_digit(contador)
            print("Evento: Sonido ->", contador)
            snd_armed = False
        elif (not snd_armed) and cur_snd == snd_idle:
            snd_armed = True

    # ----- LÍNEA -----
    cur_line = line_in.value
    if cur_line != line_last:
        line_last_change = now
        line_last = cur_line
    if (now - line_last_change) >= LINE_STABLE:
        if line_armed and (cur_line != line_idle):
            if cur_line == 1:
                print("No line present")
            else:
                print("Line present")
            line_armed = False
        elif (not line_armed) and (cur_line == line_idle):
            line_armed = True

    # ----- SERVO CONTINUO -----
    if cur_line == 0:
        my_servo.throttle = RUN_SPEED   # gira mientras hay línea
    else:
        my_servo.throttle = 0.0         # se detiene si no hay línea

    time.sleep(SAMPLE_DELAY)
}