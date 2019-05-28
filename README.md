## List of hardware
* ESP32-PICO-KIT 
* HTU21D Digital Relative Humidity Sensor
* Breadboard
* 4 female-to-male jumper wires
* Raspberry Pi with Bluetooth
* Xiaomi Smart Temperature & Humidity Sensor

**_TODO:_ Add photos of hardware**


## Hardware setup
#### ESP32
#### Wiring schemes
| ESP32 | HTU21D |
| ----- | ------ |
| 3V3   | VIN    |
| GND   | GND    |
| 18    | SDA    |
| 19    | SCL    |

**_TODO:_ Add final picture of setup**

#### Raspberry Pi
Just connect it to power supply and install Raspbian or Noobs on it.


## Programming ESP32
You need ESP-IDF (Espressif IoT Development Framework) to program your ESP32.
Install it with the following instructions:
```
mkdir ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
git checkout 3bf56cdd1
```
Set up IDF_PATH before running any other command:
```
export IDF_PATH=~/esp/esp-idf
```
The python packages required by ESP-IDF are located in IDF_PATH/requirements.txt. You can install them by running:
```
python -m pip install --user -r $IDF_PATH/requirements.txt
```
##### Note
Please check the version of the Python interpreter that you will be using with ESP-IDF. For this, run the command python --version and depending on the result, you might want to use python2, python2.7 or similar instead of just python, e.g.

See [this](https://docs.espressif.com/projects/esp-idf/en/latest/get-started/index.html) guide for more info.

Now you can flash your ESP:
```
git clone name_of_rep_with_example
cd name_of_rep_with_example
make flash
```


## Programming Raspberry Pi
There is a script in repo called main.py. You need at least **python3.4**. Install the following packages:
```
sudo apt-get install libglib2.0-dev
pip3 install bluepy btlewrap tb-mqtt-client
```
Run `sudo python3 main.py` and enjoy :::::::::)

