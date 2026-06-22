from machine import Pin, PWM
from umqtt.simple import MQTTClient
import network
import time

# WiFi
SSID = "Wokwi-GUEST"
PASSWORD = ""

# MQTT
MQTT_CLIENT_ID = "esp32-cochera"
MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_TOPIC = b"cochera/control"

# Servo
servo = PWM(Pin(18), freq=50)

def mover_servo(angulo):
    duty = int(26 + (angulo / 180) * 102)
    servo.duty(duty)

def abrir_cochera():
    print("Abriendo cochera...")
    mover_servo(90)

def cerrar_cochera():
    print("Cerrando cochera...")
    mover_servo(0)

def recibir_mensaje(topic, msg):
    print("Mensaje recibido:", msg)

    if msg == b"ABRIR":
        abrir_cochera()

    elif msg == b"CERRAR":
        cerrar_cochera()

# Conectar WiFi
print("Conectando WiFi...")
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(SSID, PASSWORD)

while not wifi.isconnected():
    time.sleep(0.1)

print("WiFi conectado")

# Conectar MQTT
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
client.set_callback(recibir_mensaje)

print("Conectando MQTT...")
client.connect()

client.subscribe(MQTT_TOPIC)

print("Suscrito a:", MQTT_TOPIC)

while True:
    client.check_msg()
    time.sleep(0.1)