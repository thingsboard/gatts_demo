from . import ExtensionInterface

# Extracts data from ESP test device and sends it to TB. Both polling and notifications
# are supported.
class Extension(ExtensionInterface.ExtensionInterface):
    def __init__(self):
        ExtensionInterface.ExtensionInterface.__init__(self, noti_supported=True)
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