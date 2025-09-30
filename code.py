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
import json
import board
import digitalio
import pwmio
from adafruit_motor import servo
from analogio import AnalogIn
import wifi
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# -------------------- Configuración --------------------
CO_WINDOW_S      = 5.0    # ventana para considerar "ambos sensores"
BTN_DEBOUNCE_S   = 0.05
BTN_LONGPRESS_S  = 1.2
BLINK_MS         = 500    # parpadeo para 2/3
SERVO_ON_S       = 2.0    # tiempo de giro para bajar reja
RUN_SPEED        = 1.0    # 0..1 para servo continuo
SAMPLE_DELAY     = 0.002  # más rápido para seguir envolvente de audio

# MQTT / WiFi
DISCOVERY_TOPIC = "descubrir"
WIFI_SSID = "wfrre-Docentes"          # <- completar
WIFI_PASSWORD = "20$tscFrre.24"  # <- completar
MQTT_BROKER = "10.13.100.154"  # <- completar con la IPv4 del broker
MQTT_PORT = 1883
NOMBRE_EQUIPO = "Dame5"
MQTT_BASE_TOPIC = f"sensores/{NOMBRE_EQUIPO}"
PUBLISH_INTERVAL_S = 10.0  # Solo para micrófono
PUB_INTERVAL = PUBLISH_INTERVAL_S  # alias para función publish()

# Mic analógico (parámetros de detección)
MIC_CALIBRATE_S   = 3.0    # duración de auto-calibración al armar
MIC_FACTOR        = 2.5    # umbral = piso_de_ruido * factor
MIC_ABS_MIN       = 800.0  # umbral mínimo absoluto (unidades ADC de 16 bits)
MIC_DC_ALPHA      = 0.002  # filtro muy lento para DC (seguimiento del offset)
MIC_ENV_ATTACK    = 0.20   # ataque de envolvente (subidas)
MIC_ENV_DECAY     = 0.05   # decaimiento de envolvente (bajadas)
MIC_NOISE_ALPHA   = 0.02   # promedio exponencial durante calibración

# Logs (frecuencia)
WAIT_LOG_MS       = 500    # cada cuánto loguear "esperando confirmación"
MIC_LOG_MS        = 100    # cada cuánto loguear lectura de mic mientras no supera umbral

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
def servo_open_gate():  gate.throttle = -RUN_SPEED

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

# Control de estado de la puerta
gate_was_activated = False        # True si la puerta se cerró por una alarma

# Logs temporizados
wait_log_next_ms = blink_change_ms
mic_log_next_ms = blink_change_ms

# Cola para eventos del tracker
tracker_event_queue = []  # Lista para almacenar eventos del tracker
MAX_QUEUE_SIZE = 50       # Máximo de eventos en cola

print("t0: desarmada (0)")

# -------------------- Conexión WiFi + MQTT --------------------
def _wifi_connect():
    try:
        print(f"Conectando a WiFi '{WIFI_SSID}' ...")
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
        print(f"WiFi OK | IP: {wifi.radio.ipv4_address}")
        return True
    except Exception as e:
        print(f"[WiFi] error: {e}")
        return False

_wifi_ok = _wifi_connect()
_socket_pool = socketpool.SocketPool(wifi.radio) if _wifi_ok else None

def _on_mqtt_connect(client, userdata, flags, rc):
    client.publish(DISCOVERY_TOPIC, json.dumps({"equipo": NOMBRE_EQUIPO, "magnitudes": ["mic_adc", "tracker"]}))
    print("[MQTT] Conectado al broker")

def _mqtt_make_client():
    try:
        client = MQTT.MQTT(
            broker=MQTT_BROKER,
            port=MQTT_PORT,
            socket_pool=_socket_pool,
            is_ssl=False,
        )
        client.on_connect = _on_mqtt_connect
        client.connect()
        return client
    except Exception as e:
        print(f"[MQTT] error de conexión: {e}")
        return None

mqtt_client = _mqtt_make_client() if _wifi_ok else None
last_pub = 0.0

# Función para agregar evento del tracker a la cola
def queue_tracker_event(event_type, timestamp):
    global tracker_event_queue
    event = {
        "type": event_type,  # "activation" o "deactivation"
        "timestamp": timestamp,
        "value": 1 if event_type == "activation" else 0
    }
    
    # Agregar a la cola
    tracker_event_queue.append(event)
    
    # Limitar tamaño de cola
    if len(tracker_event_queue) > MAX_QUEUE_SIZE:
        tracker_event_queue.pop(0)  # Remover el evento más antiguo
    
    print(f"[TRACKER] Evento encolado: {event_type} en {timestamp:.2f}s")

# Función para procesar la cola del tracker
def process_tracker_queue():
    global tracker_event_queue
    if mqtt_client is None or not tracker_event_queue:
        return
    
    try:
        # Procesar hasta 5 eventos por ciclo para no sobrecargar
        events_to_process = min(5, len(tracker_event_queue))
        for i in range(events_to_process):
            event = tracker_event_queue.pop(0)
            mqtt_client.publish(f"{MQTT_BASE_TOPIC}/tracker", str(event["value"]))
            print(f"[MQTT] pub tracker event: {event}")
    except Exception as e:
        print(f"[MQTT] tracker queue error: {e}")

# Publicación periódica (solo para micrófono)
def publish():
    global last_pub
    if mqtt_client is None:
        return
    now_ts = time.monotonic()
    if (now_ts - last_pub) >= PUB_INTERVAL:
        try:
            mqtt_client.publish(f"{MQTT_BASE_TOPIC}/mic_adc", str(mic_env))
            print(f"[MQTT] pub mic_adc={mic_env}")
            last_pub = now_ts
        except Exception as e:
            print(f"[MQTT] publish error: {e}")

while True:
    t = now()
    ms = t * 1000.0

    # --------------- MQTT loop + publicación periódica de datos puros ---------------
    if mqtt_client is not None:
        try:
            mqtt_client.loop()
        except Exception as e:
            print(f"[MQTT] loop error: {e}")
        publish()  # Solo micrófono por intervalos
        process_tracker_queue()  # Procesar cola del tracker

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
                    gate_was_activated = False  # Reset del estado de la puerta
                    servo_stop()
                    display_digit(1)
                    # iniciar calibración de mic
                    mic_dc = float(mic_adc.value)
                    mic_env = 0.0
                    mic_noise_est = 0.0
                    mic_thresh = None
                    mic_over_prev = False
                    mic_cal_end_t = t + MIC_CALIBRATE_S
                    # reset logs
                    wait_log_next_ms = ms
                    mic_log_next_ms = ms
                    print("[ARMADA] display=1 (monitorizando) + calib mic {:.1f}s".format(MIC_CALIBRATE_S))
                else:
                    sys_state = DISARMED
                    alarm_code = 0
                    last_trk_event_t = None
                    last_mic_event_t = None
                    pending_type = None
                    pending_deadline_t = None
                    sensors_locked = False
                    # Solo abrir si la puerta se había cerrado por una alarma
                    if gate_was_activated:
                        servo_open_gate()
                        servo_until = t + SERVO_ON_S
                        gate_was_activated = False  # Reset después de abrir
                        print("[DESARMADA] display=0 -> Servo OPEN (puerta se había cerrado)")
                    else:
                        servo_stop()
                        print("[DESARMADA] display=0 -> Sin activación previa, no abre servo")
                    display_digit(0)
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
                    # Solo abrir si la puerta se había cerrado por una alarma
                    if gate_was_activated:
                        servo_open_gate()
                        servo_until = t + SERVO_ON_S
                        gate_was_activated = False  # Reset después de abrir
                        print("[RESET] alarma -> Servo OPEN (puerta se había cerrado)")
                    else:
                        servo_stop()
                        print("[RESET] alarma -> Sin activación previa, no abre servo")
                    display_digit(1)
                    # rearmar calibración rápida del mic (opcional)
                    mic_dc = float(mic_adc.value)
                    mic_env = 0.0
                    mic_noise_est = 0.0
                    mic_thresh = None
                    mic_over_prev = False
                    mic_cal_end_t = t + MIC_CALIBRATE_S
                    # reset logs
                    wait_log_next_ms = ms
                    mic_log_next_ms = ms
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

    # Log del mic mientras está armado y aún no superó umbral (limitar frecuencia)
    if sys_state == ARMED and ms >= mic_log_next_ms and not sensors_locked:
        if mic_thresh is None:
            print("[MIC] calib env={:.0f}".format(mic_env))
        else:
            if not mic_over:
                ratio = (mic_env / mic_thresh) if mic_thresh > 0 else 0.0
                print("[MIC] env={:.0f} / thresh={:.0f} (ratio={:.2f})".format(mic_env, mic_thresh, ratio))
        mic_log_next_ms = ms + MIC_LOG_MS

    # --------------- LECTURA TRACKER + GENERACIÓN DE EVENTOS ---------------
    cur_trk = trk.value
    if cur_trk != trk_last:
        trk_change_t = t
        trk_last = cur_trk
        
        # Encolar evento del tracker inmediatamente
        if cur_trk == TRK_ACTIVE:
            queue_tracker_event("activation", t)
        else:
            queue_tracker_event("deactivation", t)
        
        # flanco activo para lógica de alarma
        if cur_trk == TRK_ACTIVE and sys_state == ARMED and not sensors_locked:
            last_trk_event_t = t
            print("[EVENTO] Tracker")
            if pending_type == 'mic' and (t - last_mic_event_t) <= CO_WINDOW_S:
                # doble confirmación -> 4 (fijo) y accionar servo
                alarm_code = 4
                servo_close_gate(); servo_until = t + SERVO_ON_S
                gate_was_activated = True  # Marcar que la puerta se cerró
                sensors_locked = True
                print("[ALARMA] code=4 -> Servo ON (confirmada)")
            elif pending_type is None:
                # primer evento (solo tracker): pendiente 2 (parpadeo), sin servo
                pending_type = 'trk'
                pending_deadline_t = t + CO_WINDOW_S
                alarm_code = 2
                # log inmediato de espera
                remaining = max(0.0, pending_deadline_t - t)
                print("[PENDIENTE] Esperando segunda confirmación (restan {:.1f}s)".format(remaining))
                wait_log_next_ms = ms + WAIT_LOG_MS

    # Mic evento (flanco) si no está bloqueado
    if mic_rising and sys_state == ARMED and not sensors_locked:
        last_mic_event_t = t
        print("[EVENTO] Mic (analog > thresh)")
        if pending_type == 'trk' and (t - last_trk_event_t) <= CO_WINDOW_S:
            # doble confirmación -> 4 (fijo) y accionar servo
            alarm_code = 4
            servo_close_gate(); servo_until = t + SERVO_ON_S
            gate_was_activated = True  # Marcar que la puerta se cerró
            sensors_locked = True
            print("[ALARMA] code=4 -> Servo ON (confirmada)")
        elif pending_type is None:
            # primer evento (solo mic): pendiente 3 (parpadeo), sin servo
            pending_type = 'mic'
            pending_deadline_t = t + CO_WINDOW_S
            alarm_code = 3
            # log inmediato de espera
            remaining = max(0.0, pending_deadline_t - t)
            print("[PENDIENTE] Esperando segunda confirmación (restan {:.1f}s)".format(remaining))
            wait_log_next_ms = ms + WAIT_LOG_MS

    # --------------- LÓGICA DE TIMEOUT (2/3) ---------------
    if sys_state == ARMED and not sensors_locked:
        # logs periódicos de espera mientras no vence la ventana
        if pending_type is not None and pending_deadline_t is not None and t < pending_deadline_t:
            if ms >= wait_log_next_ms:
                remaining = max(0.0, pending_deadline_t - t)
                src = "mic" if alarm_code == 3 else "trk"
                print("[PENDIENTE] {} -> esperando segunda confirmación (restan {:.1f}s)".format(src, remaining))
                wait_log_next_ms = ms + WAIT_LOG_MS
        # vencimiento de la ventana => accionar por 2/3
        if pending_type is not None and pending_deadline_t is not None and t >= pending_deadline_t:
            servo_close_gate(); servo_until = t + SERVO_ON_S
            gate_was_activated = True  # Marcar que la puerta se cerró
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