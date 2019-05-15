from btlewrap.bluepy import BluepyBackend
from tb_device_mqtt import TBDeviceMqttClient, TBPublishInfo
from bluepy.btle import DefaultDelegate, Peripheral, Scanner
from tb_gateway_mqtt import TBGatewayMqttClient
import time
import sys
import traceback

#---------------------------------------------------------------------------------------------------

# Generic interface to allow getting data from different BLE sensors
class BtDeviceInterface:
    def __init__(self, noti_supported=False):
        self.noti_supported = noti_supported

    def poll(self, bt_device):
        pass

    def start_notify(self, bt_device):
        pass

    def stop_notify(self):
        pass

    def handle_notify(self, handle, data):
        pass

    def notify_started(self):
        return False

    def notify_supported(self):
        return self.noti_supported

# Extracts data from MI sensor and sends it to TB
class MiTempHumiditySensor(BtDeviceInterface):
    def __init__(self):
        # Full-blown notifications are not supported: MI device will disconnect after a 
        # few notifications sent.
        # So it is better to use poll mechanism instead
        BtDeviceInterface.__init__(self)

    def poll(self, bt_device):
        telemetry = {}
        class MI_Delegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)

            def handleNotification(self, handle, data):
                print("Received data:", data)
                telemetry = { "temperature" : float(data[2:6]), "humidity" : float(data[9:13]) }

        bt_device.withDelegate(MI_Delegate())

        # This is a required part of MI sensor protocol.
        # Without it, notification will not be delivered.
        # For some reason the characteristic is not advertised, meaning it is not possible to use
        # UUID here. Instead a write operation is performed by handle.
        bt_device.writeCharacteristic(0x10, b'\x01\x00', True)
        bt_device.waitForNotifications(1)
        return telemetry

# Extracts data from ESP test device and sends it to TB. Both polling and notifications
# are supported.
class EspGattDemoDevice(BtDeviceInterface):
    def __init__(self):
        BtDeviceInterface.__init__(self, noti_supported=True)
        self.noti_started = False

    def poll(self, bt_device):

        # Example of getting values using direct 'read' mechanism

        esp_service = bt_device.getServiceByUUID("000000ff-0000-1000-8000-00805f9b34fb")
        esp_char = esp_service.getCharacteristics("0000ff00-0000-1000-8000-00805f9b34fb")[0]
        char_value = str(esp_char.read(), 'utf-8')

        return { "esp_char" : char_value }

    def start_notify(self, bt_device):
        # No need in a special preparation before notification starts
        self.noti_started = True

    def stop_notify(self):
        # No need in a special preparation before notification starts
        self.noti_started = False

    def notify_started(self):
        return self.noti_started

    def handle_notify(self, handle, data):
        # Helper routine
        def bytes_to_int(bytes):
            result = 0
            for i in reversed(bytes):
                result = (result << 8) + i
            return result

        decoded = bytes_to_int(data)
        print("Received GATT data from ESP:", data, "decoded:", decoded)
        return { "counter_noti": decoded }

# Contains devices that we should connect to and extract data. 
# Some aux data is written in runtime
known_devices = {
    "MJ_HT_V1": {
        "handler": MiTempHumiditySensor,
        "scanned": {}
    },
    "ESP_GATTS_DEMO": {
        "handler": EspGattDemoDevice,
        "scanned": {}
    },
}

#---------------------------------------------------------------------------------------------------

# Scan for known devices

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print("Discovered BT device:", dev.addr)
        elif isNewData:
            print("Received new data from:", dev.addr)

print("Scanning BLE devices...")
scanner = Scanner().withDelegate(ScanDelegate())
devices = scanner.scan(10.0)

for dev in devices:
    print("Device {} ({}), RSSI={} dB".format(dev.addr, dev.addrType, dev.rssi))
    for (adtype, desc, value) in dev.getScanData():
        print("  {} = {}".format(desc, value))
        if desc == "Complete Local Name" and value in known_devices:
            print("    known device found:", value)
            known_devices[value]["scanned"][dev.addr] = { 
                "inst": known_devices[value]["handler"](),
                "periph": Peripheral(),
                "tb_name": value + "_" + dev.addr
            }

#---------------------------------------------------------------------------------------------------

TB_SERVER = "demo.thingsboard.io"
TB_ACCESS_TOKEN = "DmCbB394rtwuIwUMt8Bz"

gateway = TBGatewayMqttClient(TB_SERVER, TB_ACCESS_TOKEN)
gateway.connect()

# Starts notifications threads for each discovered device that support the notification mechanism

while True:
    for type, type_data in known_devices.items():
        for dev_addr, dev_data in type_data["scanned"].items():
            try:
                instance = dev_data["inst"]
                ble_periph = dev_data["periph"]
                tb_dev_name = dev_data["tb_name"]

                telemetry = {}

                print("Connecting to device:", tb_dev_name)
                ble_periph.connect(dev_addr)

                if instance.notify_supported():
                    if instance.notify_started() == False:
                        instance.start_notify(ble_periph)

                    class NotiDelegate(DefaultDelegate):
                        def __init__(self):
                            DefaultDelegate.__init__(self)
                            self.dev_instance = instance
                            self.telemetry = {}

                        def handleNotification(self, handle, data):
                            print("Received notifications for handle:", handle)
                            self.telemetry = self.dev_instance.handle_notify(handle, data)
                            
                    print("Getting notification from:", tb_dev_name)

                    deleagate = NotiDelegate()
                    ble_periph.withDelegate(deleagate)
                    ble_periph.waitForNotifications(1)
                    print("Data received:", deleagate.telemetry)
                    
                    telemetry.update(deleagate.telemetry)

                print("Polling data from:", tb_dev_name)
                poll_telemetry = instance.poll(ble_periph)
                print("Data received:", poll_telemetry)

                telemetry.update(poll_telemetry)

                gateway.gw_connect_device(tb_dev_name)
                gateway_pkt = { "ts": int(round(time.time() * 1000)), "values" : telemetry }
                print("Sending data to TB:", gateway_pkt)
                gateway.gw_send_telemetry(tb_dev_name, gateway_pkt)
                gateway.gw_disconnect_device(tb_dev_name)
            except KeyboardInterrupt:
                print("Exiting the application")
                sys.exit()
            except Exception as e: 
                print("Exception caught:", e)
            finally:
                print("Disconnecting from device")
                ble_periph.disconnect()

    time.sleep(1)
