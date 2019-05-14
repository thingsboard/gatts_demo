from btlewrap.bluepy import BluepyBackend
from tb_device_mqtt import TBDeviceMqttClient, TBPublishInfo
from bluepy.btle import DefaultDelegate, Peripheral, Scanner
from tb_gateway_mqtt import TBGatewayMqttClient
import time

SERVER = "demo.thingsboard.io"
ACCESS_TOKEN = "DmCbB394rtwuIwUMt8Bz"
DEVICE = "gw"

gateway = TBGatewayMqttClient(SERVER, ACCESS_TOKEN)
gateway.connect()
gateway.gw_connect_device(DEVICE)


def bytes_to_int(bytes):
    result = 0
    for i in reversed(bytes):
        result = (result << 8) + i
    return result 

class EspDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        telemetry = { "ts": int(round(time.time() * 1000)), \
                      "values": { "counter" : bytes_to_int(data) } }
        gateway.gw_send_telemetry(DEVICE, telemetry)
        print("Received data:", data)

class SensorDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        telemetry = { "ts": int(round(time.time() * 1000)), \
                      "values" : { "temperature" : float(data[2:6]), \
                               "humidity" : float(data[9:13]) } }
        gateway.gw_send_telemetry(DEVICE, telemetry)
        print("Received data:", data)


class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print("Discovered device", dev.addr)
        elif isNewData:
            print("Received new data from", dev.addr)

known_devices = { "ESP_GATTS_DEMO" : "none", "MJ_HT_V1" : "none" } 

scanner = Scanner().withDelegate(ScanDelegate())
devices = scanner.scan(10)

for dev in devices:
    print("Device {} ({}), RSSI={} dB".format(dev.addr, dev.addrType, dev.rssi))
    for (adtype, desc, value) in dev.getScanData():
        print("  {} = {}".format(desc, value))
        if desc == "Complete Local Name" and value in known_devices:
                known_devices[value] = dev.addr

sensor = Peripheral()
esp = Peripheral()

while True:
    if (known_devices["MJ_HT_V1"] != "none"):
        try:
            sensor.connect(known_devices["MJ_HT_V1"]) 
            sensor.withDelegate(SensorDelegate())
            sensor.writeCharacteristic(0x10, b'\x01\x00', True)
            sensor.waitForNotifications(1)
            sensor.disconnect()

        except:
            print("Exception caught")

    if (known_devices["ESP_GATTS_DEMO"] != "none"): 
        esp.connect(known_devices["ESP_GATTS_DEMO"])
        esp.withDelegate(EspDelegate())
        esp_service = esp.getServiceByUUID("000000ff-0000-1000-8000-00805f9b34fb")
        esp_char = esp_service.getCharacteristics("0000ff00-0000-1000-8000-00805f9b34fb")[0]
        char_value = str(esp_char.read(), 'utf-8') 
        esp.waitForNotifications(1)
        esp.disconnect();

        telemetry = { "ts": int(round(time.time() * 1000)), \
                      "values" : { "esp_char" : char_value } }
        gateway.gw_send_telemetry(DEVICE, telemetry)


gateway.gw_disconnect_device(DEVICE)
gateway.disconnect()
