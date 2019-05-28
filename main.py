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
        class MI_Delegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)
                self.telemetry = {}

            def handleNotification(self, handle, data):
                print("Received data:", data)
                self.telemetry = { "temperature" : float(data[2:6]), "humidity" : float(data[9:13]) }

        delegate = MI_Delegate()
        bt_device.withDelegate(delegate)

        # This is a required part of MI sensor protocol.
        # Without it, notification will not be delivered.
        # For some reason the characteristic is not advertised, meaning it is not possible to use
        # UUID here. Instead a write operation is performed by handle.
        bt_device.writeCharacteristic(0x10, b'\x01\x00', True)
        bt_device.waitForNotifications(1)
        return delegate.telemetry

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

        return { "esp_char" : char_value.strip('\u0000') }

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

# Test device: arbitrary sensor
class TestSensorDemoDevice(BtDeviceInterface):
    def __init__(self):
        BtDeviceInterface.__init__(self, noti_supported=True)
        self.noti_started = False

    def poll(self, bt_device):
        return { }

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
        print("Received GATT data from Test sensor:", data, "decoded:", decoded)
        return { "decoded_data": decoded }

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
    # TODO: add support for test sensors and random addresses
    # (which require new scan every time)
    # "TEST_SENSOR": {
    #     "handler": TestSensorDemoDevice,
    #     "scanned": {},
    #     "addr_type": "random"
    # }
}

#---------------------------------------------------------------------------------------------------

def ble_rescan(tb_gateway):
    # Scan for known devices

    class ScanDelegate(DefaultDelegate):
        def __init__(self):
            DefaultDelegate.__init__(self)

        def handleDiscovery(self, dev, isNewDev, isNewData):
            if isNewDev:
                print("Discovered BT device:", dev.addr)
            elif isNewData:
                print("Received new data from:", dev.addr)

    known_devices_found = False

    # Deactivate and clear existing devices before re-scanning
    for dev, dev_data in known_devices.items():
        for scanned, scanned_data in dev_data["scanned"].items():
            tb_name = scanned_data["tb_name"]

            tb_gateway.gw_connect_device(tb_name)
            tb_gateway.gw_send_attributes(tb_name, {"active": False})
            tb_gateway.gw_disconnect_device(tb_name)

        dev_data["scanned"].clear()

    while not known_devices_found:
        try:
            print("Scanning BLE devices...")
            scanner = Scanner().withDelegate(ScanDelegate())
            devices = scanner.scan(15.0)

            for dev in devices:
                print("Device {} ({}), RSSI={} dB".format(dev.addr, dev.addrType, dev.rssi))
                for (adtype, desc, value) in dev.getScanData():
                    print("  {} = {}".format(desc, value))
                    if desc == "Complete Local Name" and value in known_devices:
                        print("    [!] Known device found:", value)

                        tb_name = value + "_" + dev.addr.replace(':', '').upper()

                        known_devices[value]["scanned"][dev.addr] = {
                            "inst": known_devices[value]["handler"](),
                            "periph": Peripheral(),
                            "tb_name": tb_name
                        }

                        # Force TB to create a device
                        tb_gateway.gw_connect_device(tb_name)
                        tb_gateway.gw_send_attributes(tb_name, {"active": True})
                        tb_gateway.gw_disconnect_device(tb_name)

                        known_devices_found = True
        except Exception as e:
            print("Exception caught:", e)

#---------------------------------------------------------------------------------------------------

TB_SERVER = "localhost"
TB_ACCESS_TOKEN = "xLd56zXQhZiUIsq4zjMF"

gateway = TBGatewayMqttClient(TB_SERVER, TB_ACCESS_TOKEN)
gateway.connect()

ble_rescan(gateway)

while True:
    for type, type_data in known_devices.items():
        for dev_addr, dev_data in type_data["scanned"].items():
            try:
                instance = dev_data["inst"]
                ble_periph = dev_data["periph"]
                tb_dev_name = dev_data["tb_name"]

                telemetry = {}

                print("Connecting to device:", tb_dev_name)

                ble_periph.connect(dev_addr, "public")

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

                if not telemetry:
                    print("No data to send for current device")
                    continue

                gateway_pkt = { "ts": int(round(time.time() * 1000)), "values" : telemetry }

                print("Sending data to TB:", gateway_pkt)

                gateway.gw_connect_device(tb_dev_name)
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
