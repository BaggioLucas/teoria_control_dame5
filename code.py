import time
import board
import digitalio

# Definimos los pines GPIO para cada segmento de los displays
display1_pins = [board.GP4, board.GP5, board.GP8, board.GP6, board.GP7, board.GP3, board.GP2]
"""gp2 = G
GP3 = F
GP4 = A
GP5 = B
GP6 = D
GP7 = E
GP8 = C"""
# Configuramos los pines GPIO como salidas
display1_segments = [digitalio.DigitalInOut(pin) for pin in display1_pins]


for segment in display1_segments:
    segment.direction = digitalio.Direction.OUTPUT

# Definimos los patrones de segmentos para cada dígito (0-9)
digit_patterns = [
    (0, 0, 0, 0, 0, 0, 1),  # 0
    (1, 0, 0, 1, 1, 1, 1),  # 1
    (0, 0, 1, 0, 0, 1, 0),  # 2
    (0, 0, 0, 0, 1, 1, 0),  # 3
    (1, 0, 0, 1, 1, 0, 0),  # 4
    (0, 1, 0, 0, 1, 0, 0),  # 5
    (0, 1, 0, 0, 0, 0, 0),  # 6
    (0, 0, 0, 1, 1, 1, 1),  # 7
    (0, 0, 0, 0, 0, 0, 0),  # 8
    (0, 0, 0, 0, 1, 0, 0)   # 9
]

# Función para mostrar un dígito en un display
def display_digit(display_segments, digit):
    for pin, state in zip(display_segments, digit_patterns[digit]):
        pin.value = state


while True:
    for i in range(10):# Muestra la humedad actual
        time.sleep(1)
        #cifra_unidades = 0
        display_digit(display1_segments, i)