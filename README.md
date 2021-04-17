# Bluepy-Python-Thesis

This repository contains Bluetooth 4.0 (BLE) Python programs to scan and connect to the SensorTile device and enable BLE notification used in my bachelor thesis. The library used is [bluepy](https://github.com/IanHarvey/bluepy), a Python interface to Bluetooth LE on Linux.

## 1. Scan bluetooth devices

In [1. Scan bluetooth devices](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/1.%20Scan%20bluetooth%20devices), the program [scan_only_sensortile_salvataggio_file.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/1.%20Scan%20bluetooth%20devices/scan_only_sensortile_salvataggio_file.py) receives the advertising data of nearby Bluetooth devices and filters the SensorTile advertising data using the SensorTile MacAddres `c0:83:1d:31:45:48`. The data are saved in [bluepyscanlog.txt](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/1.%20Scan%20bluetooth%20devices/bluepyscanlog.txt) file.
To run this code `cd '.\1. Scan bluetooth devices\'` and `python scan_only_sensortile_salvataggio_file.py`.

## 2. Identify sensortile services and characteristics

In [2. Identify sensortile services and characteristics](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/2.%20Identify%20sensortile%20services%20and%20characteristics), the program [characteristic_and_service.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/2.%20Identify%20sensortile%20services%20and%20characteristics/characteristic_and_service.py) receives the UUIDs of the SensorTile Bluetooth services and associated characteristics and saves them in the [Lista dei servizi e caratteristiche SensorTile.txt](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/2.%20Identify%20sensortile%20services%20and%20characteristics/Lista%20dei%20servizi%20e%20caratteristiche%20SensorTile.txt) file.
To run this code `cd '.\2. Identify sensortile services and characteristics\'` and `python characteristic_and_service.py`.

## 3. Notification enable and data save

In [3. Notification enable and data save](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/3.%20Notification%20enable%20and%20data%20save), the program [gestione_notifiche.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/3.%20Notification%20enable%20and%20data%20save/gestione_notifiche.py) enables or disables, depending on the user's choice, notifications relating to the characteristic of the temperature and pressure sensor and the characteristics of the accelerometer, gyroscope and magnetometer sensor. The data (not decrypted) are saved in the [Dati sensori.txt](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/3.%20Notification%20enable%20and%20data%20save/Dati%20sensori.txt) file. The handles needed to enable notifications were found by trial and error.
To run this code `cd '.\3. Notification enable and data save\'` and `python gestione_notifiche.py`.

## 4. Notification enable and MATLAB data save

In [4. Notification enable and MATLAB data save](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/4.%20Notification%20enable%20and%20MATLAB%20data%20save), the program [gestione_notifiche_MATLAB.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/4.%20Notification%20enable%20and%20MATLAB%20data%20save/gestione_notifiche_MATLAB.py) enables or disables, epending on the user's choice, notifications relating to the characteristic of the temperature and pressure sensor and the characteristics of the accelerometer, gyroscope and magnetometer sensor.
The program saves the decrypted data in the [Dati sensori.txt](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/4.%20Notification%20enable%20and%20MATLAB%20data%20save/Dati%20sensori.txt) file. The 3 files created are "Accelerometro MATLAB.txt", "Giroscopio  MATLAB.txt" and "Magnetometro  MATLAB.txt" in which the data are written in a table according to the form `timestamp \t X-axis value \t Y-axis value \t Z-axis value \t\n` to be used later in MATLAB to make graphs. Changelog from [3. Notification enable and data save](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/3.%20Notification%20enable%20and%20data%20save): the handles needed to enable notifications were now found via software. The data sent by the SensorTile has been decrypted.
To run this code `cd '.\4. Notification enable and MATLAB data save\'` and `python gestione_notifiche_MATLAB.py`.

## 5. Notification enable and MATLAB data save 2.0

In [5. Notification enable and MATLAB data save 2.0](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/5.%20Notification%20enable%20and%20MATLAB%20data%20save%202.0), the program [gestione_notifiche_MATLAB.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/5.%20Notification%20enable%20and%20MATLAB%20data%20save%202.0/gestione_notifiche_MATLAB.py) enables or disables, epending on the user's choice, notifications relating to the characteristic of the temperature and pressure sensor and the characteristics of the accelerometer, gyroscope, magnetometer sensor and sensor fusion.
The program saves the decrypted data in the [Dati sensori.txt](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/4.%20Notification%20enable%20and%20MATLAB%20data%20save/Dati%20sensori.txt) file. The 3 files created are "Accelerometro MATLAB.txt", "Giroscopio  MATLAB.txt" and "Magnetometro  MATLAB.txt" in which the data are written in a table according to the form `timestamp \t X-axis value \t Y-axis value \t Z-axis value \t\n` to be used later in MATLAB to make graphs. Changelog from [4. Notification enable and MATLAB data save](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/4.%20Notification%20enable%20and%20MATLAB%20data%20save): the user can activate the sensor fusion (compact) notification.
To run this code `cd '.\5. Notification enable and MATLAB data save 2.0\'` and `python gestione_notifiche_MATLAB.py`.

## 6. Pitch and roll notification

In [6. Pitch and roll notification](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/6.%20Pitch%20and%20roll%20notification), the program [Ricezione_pitch_roll.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/6.%20Pitch%20and%20roll%20notification/Ricezione_pitch_roll.py) enables or disables, depending on the user's choice, notifications relating to the characteristic of the temperature and pressure sensor, to the characteristic of the accelerometer, gyroscope and magnetometer sensor, to the characteristic of the sensor fusion or to the characteristic of pitch and roll.
The program saves the decrypted data in the "Dati sensori.txt" file. The 5 files created are "Accelerometro.txt.", "Giroscopio.txt", "Magnetometro.txt", "Sensor Fusion.txt" and "Pitch e Roll.txt" in which the data is written in tabular form according to theform `timestamp \t X-axis value \t Y-axis value \t Z-axis value \t\n` to be used later in MATLAB to make graphs. Changelog from [5. Notification enable and MATLAB data save 2.0](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/5.%20Notification%20enable%20and%20MATLAB%20data%20save%202.0): activation of notifications of the new pitch and roll feature (uuid = 00EE0000000111e1ac360002a5d5c51b).
To run this code `cd '.\6. Pitch and roll notification\'` and `python Ricezione_pitch_roll.py`.

## 7. Ricezione notifiche (programma finale)

In [7. Ricezione notifiche (programma finale)](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/7.%20Ricezione%20notifiche%20(programma%20finale)), the program [Ricezione_notifiche.py](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/7.%20Ricezione%20notifiche%20(programma%20finale)/Ricezione_notifiche.py) enables or disables, depending on the user's choice, notifications relating to the characteristic of the temperature and pressure sensor, to the characteristic of the accelerometer, gyroscope and magnetometer sensor, to the characteristic of the sensor fusion or to the characteristic of pitch and roll.
The program saves the decrypted data in the "Dati sensori.txt" file. The 5 files created are "Accelerometro.txt.", "Giroscopio.txt", "Magnetometro.txt", "Sensor Fusion.txt" and "Pitch e Roll.txt" in which the data is written in tabular form according to theform `timestamp \t X-axis value \t Y-axis value \t Z-axis value \t\n` to be used later in MATLAB to make graphs. Changelog from [6. Pitch and roll notification](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/tree/master/6.%20Pitch%20and%20roll%20notification): if the SensorTile disconnects, the program continues to search for it until it becomes "visible" again.
To run this code `cd '.\7. Ricezione notifiche (programma finale)\'` and `python Ricezione_notifiche.py`.

## Results

The figure below shows a comparison between the filtered pitch data, in blue, and the data simply obtained from the formulas in which are used the accelerometer axis values, in red.

![](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/pitch.png)

The figure below shows a comparison between the filtered roll data, in blue, and the data simply obtained from the formulas in which are used the accelerometer axis values, in red.

![](https://github.com/MatteoOrlandini/Bluepy-Python-Thesis/blob/master/roll.png)