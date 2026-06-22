import network
import time
import dht
import machine
import json
from umqtt.simple import MQTTClient

# --- Configuración WiFi y MQTT ---
WIFI_SSID = 'Wokwi-GUEST'
WIFI_PASSWORD = ''
MQTT_BROKER = 'broker.mqttdashboard.com'
CLIENT_ID = 'esp32_wokwi_habitacion_123' # Puedes cambiar esto por un nombre único

# --- Tópicos MQTT ---
TOPIC_CLIMA = b'proyecto/cuarto/clima'
TOPIC_VENTANA = b'proyecto/cuarto/ventana'
TOPIC_LUZ1 = b'proyecto/cuarto/luz/1'
TOPIC_LUZ2 = b'proyecto/cuarto/luz/2'
TOPIC_LUZ3 = b'proyecto/cuarto/luz/3'

# --- Configuración de Hardware ---
sensor_dht = dht.DHT22(machine.Pin(15))
# El servo usa PWM. 50Hz es la frecuencia estándar para servos.
servo_ventana = machine.PWM(machine.Pin(18), freq=50) 
led1 = machine.Pin(2, machine.Pin.OUT)
led2 = machine.Pin(4, machine.Pin.OUT)
led3 = machine.Pin(5, machine.Pin.OUT)

def mover_servo(angulo):
    # En MicroPython con resolución de 10-bits (0-1023), 
    # duty 40 es aprox 0 grados, y duty 77 es aprox 90 grados.
    if angulo == 0:
        servo_ventana.duty(40)
    elif angulo == 90:
        servo_ventana.duty(77)

# Estado inicial del hardware
mover_servo(0) 
led1.value(0)
led2.value(0)
led3.value(0)

# --- Conexión WiFi ---
print("Conectando a WiFi...", end="")
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASSWORD)
while not wifi.isconnected():
    time.sleep(0.5)
    print(".", end="")
print("\n¡WiFi Conectado! IP:", wifi.ifconfig()[0])

# --- Función Callback para mensajes MQTT entrantes ---
def sub_cb(topic, msg):
    print("Mensaje recibido - Tópico: {}, Mensaje: {}".format(topic, msg))
    
    if topic == TOPIC_VENTANA:
        if msg == b'ABRIR':
            mover_servo(90)
        elif msg == b'CERRAR':
            mover_servo(0)
            
    elif topic == TOPIC_LUZ1:
        led1.value(1 if msg == b'ON' else 0)
    elif topic == TOPIC_LUZ2:
        led2.value(1 if msg == b'ON' else 0)
    elif topic == TOPIC_LUZ3:
        led3.value(1 if msg == b'ON' else 0)

# --- Conexión MQTT ---
print("Conectando a MQTT...")
cliente = MQTTClient(CLIENT_ID, MQTT_BROKER)
cliente.set_callback(sub_cb)
cliente.connect()

# Suscripciones
cliente.subscribe(TOPIC_VENTANA)
cliente.subscribe(TOPIC_LUZ1)
cliente.subscribe(TOPIC_LUZ2)
cliente.subscribe(TOPIC_LUZ3)
print("¡Conectado a MQTT (HiveMQ) y suscrito a los tópicos!")

# --- Bucle Principal ---
ultimo_envio = time.time()

try:
    while True:
        # Revisa si llegaron mensajes de la página web (no bloqueante)
        cliente.check_msg()
        
        # Publicar temperatura y humedad cada 2 segundos
        ahora = time.time()
        if ahora - ultimo_envio >= 2:
            try:
                sensor_dht.measure()
                t = sensor_dht.temperature()
                h = sensor_dht.humidity()
                
                # Crear formato JSON
                payload = json.dumps({"temp": t, "hum": h})
                cliente.publish(TOPIC_CLIMA, payload.encode())
                print("Publicado:", payload)
                
                ultimo_envio = ahora
            except OSError as e:
                print("Error al leer el sensor DHT22")
                
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("Desconectando...")
    cliente.disconnect()