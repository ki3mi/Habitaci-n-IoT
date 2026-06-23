import network
import time
import dht
import machine
import json
from umqtt.simple import MQTTClient

# --- Driver I2C LCD Minimalista ---
class I2CLcd:
    def __init__(self, i2c, i2c_addr, num_lines, num_columns):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.i2c.writeto(self.i2c_addr, bytearray([0]))
        time.sleep_ms(20)
        for cmd in (0x33, 0x32, 0x28, 0x0C, 0x06, 0x01):
            self.hal_write_command(cmd)
            time.sleep_ms(2)
    def hal_write_command(self, cmd):
        self.hal_write_nibble(cmd & 0xF0, 0x08)
        self.hal_write_nibble((cmd << 4) & 0xF0, 0x08)
    def hal_write_data(self, data):
        self.hal_write_nibble(data & 0xF0, 0x09)
        self.hal_write_nibble((data << 4) & 0xF0, 0x09)
    def hal_write_nibble(self, nibble, mode):
        self.i2c.writeto(self.i2c_addr, bytearray([nibble | mode | 0x04]))
        self.i2c.writeto(self.i2c_addr, bytearray([nibble | mode]))
    def clear(self):
        self.hal_write_command(0x01)
        time.sleep_ms(2)
    def move_to(self, cursor_x, cursor_y):
        addr = cursor_x & 0x3F
        if cursor_y == 1: addr += 0x40
        self.hal_write_command(0x80 | addr)
    def putstr(self, string):
        for char in string:
            self.hal_write_data(ord(char))

# --- Configuración WiFi y MQTT ---
WIFI_SSID = 'Wokwi-GUEST'
WIFI_PASSWORD = ''
MQTT_BROKER = 'broker.mqttdashboard.com'
CLIENT_ID = 'esp32_wokwi_habitacion_con_lcd_123' 

# --- Tópicos MQTT ---
TOPIC_CLIMA = b'proyecto/cuarto/clima'
TOPIC_VENTANA = b'proyecto/cuarto/ventana'
TOPIC_MODO = b'proyecto/cuarto/modo_ventana' 
TOPIC_ESTADO_MODO = b'proyecto/cuarto/estado_modo' 
TOPIC_LUZ1 = b'proyecto/cuarto/luz/1'
TOPIC_LUZ2 = b'proyecto/cuarto/luz/2'
TOPIC_LUZ3 = b'proyecto/cuarto/luz/3'

# Configuración de Hardware ---
sensor_dht = dht.DHT22(machine.Pin(15))
servo_ventana = machine.PWM(machine.Pin(18), freq=50) 
led1 = machine.Pin(2, machine.Pin.OUT)
led2 = machine.Pin(4, machine.Pin.OUT)
led3 = machine.Pin(5, machine.Pin.OUT)
boton_modo = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP) # Botón físico

# Variables de Estado Globales
modo_ventana = 'MANUAL'
estado_ventana = 'CERRADA'

# Configuración de Pantalla LCD 16x2 vía I2C
i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)

direcciones = i2c.scan()
direccion_lcd = direcciones[0] if direcciones else 0x27 

lcd = I2CLcd(i2c, direccion_lcd, 2, 16) 

def mostrar_en_lcd(linea1, linea2=""):
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr(linea1[:16]) 
    lcd.move_to(0, 1)
    lcd.putstr(linea2[:16])

def mover_servo(angulo):
    global estado_ventana
    if angulo == 0:
        servo_ventana.duty(40)
        estado_ventana = 'CERRADA'
    elif angulo == 90:
        servo_ventana.duty(77)
        estado_ventana = 'ABIERTA'

# Estado inicial
mover_servo(0) 
led1.value(0)
led2.value(0)
led3.value(0)
mostrar_en_lcd("Iniciando...", "Conectando WiFi")

# --- Conexión WiFi ---
print("Conectando a WiFi...", end="")
wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.connect(WIFI_SSID, WIFI_PASSWORD)
while not wifi.isconnected():
    time.sleep(0.5)
    print(".", end="")
print("\n¡WiFi Conectado!")
mostrar_en_lcd("WiFi OK!", "Conectando MQTT")

# --- Función Callback MQTT ---
def sub_cb(topic, msg):
    global modo_ventana
    print("Mensaje recibido - Tópico: {}, Mensaje: {}".format(topic, msg))
    
    if topic == TOPIC_MODO:
        modo_ventana = msg.decode()
        cliente.publish(TOPIC_ESTADO_MODO, modo_ventana.encode()) # Confirmar a la web
        print("Modo cambiado a:", modo_ventana)
        
    elif topic == TOPIC_VENTANA and modo_ventana == 'MANUAL':
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
cliente.subscribe(TOPIC_VENTANA)
cliente.subscribe(TOPIC_MODO)
cliente.subscribe(TOPIC_LUZ1)
cliente.subscribe(TOPIC_LUZ2)
cliente.subscribe(TOPIC_LUZ3)
print("¡Conectado a MQTT y suscrito!")
mostrar_en_lcd("Sistema Listo", "Esperando sensor")

# --- Bucle Principal ---
ultimo_envio = time.time()
ultimo_estado_boton = 1

try:
    while True:
        try:
            cliente.check_msg()
        except OSError:
            pass # Prevenir cierres por desconexiones breves
        
        # --- Lectura del Botón Físico ---
        estado_boton = boton_modo.value()
        if estado_boton == 0 and ultimo_estado_boton == 1:
            # Alternar estado al presionar el botón
            modo_ventana = 'AUTO' if modo_ventana == 'MANUAL' else 'MANUAL'
            print("Botón presionado. Modo cambiado a:", modo_ventana)
            cliente.publish(TOPIC_ESTADO_MODO, modo_ventana.encode()) # Avisar a la web
            time.sleep(0.2) # Antirebote
        ultimo_estado_boton = estado_boton
        
        # --- Lectura y Control Periódico ---
        ahora = time.time()
        if ahora - ultimo_envio >= 2:
            try:
                sensor_dht.measure()
                t = sensor_dht.temperature()
                h = sensor_dht.humidity()
                
                # Lógica Automática (Si supera los 25°C se abre)
                if modo_ventana == 'AUTO':
                    if t >= 25.0 and estado_ventana != 'ABIERTA':
                        mover_servo(90)
                    elif t < 25.0 and estado_ventana != 'CERRADA':
                        mover_servo(0)
                
                # Actualizar LCD (Asegurar que el texto encaje en 16 caracteres)
                texto_temp = "T:{:.1f}C M:{}".format(t, modo_ventana[:4]) # M:AUTO o M:MANU
                texto_hum  = "H:{:.1f}% {}".format(h, "ABIERTA" if estado_ventana == 'ABIERTA' else "CERRADA")
                mostrar_en_lcd(texto_temp, texto_hum)
                
                # Publicar Clima
                payload = json.dumps({"temp": t, "hum": h})
                cliente.publish(TOPIC_CLIMA, payload.encode())
                
                ultimo_envio = ahora
            except OSError as e:
                mostrar_en_lcd("Error Sensor", "Revisar DHT22")
                
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("Desconectando...")
    cliente.disconnect()