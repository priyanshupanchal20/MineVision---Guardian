# MLX90640 test (Raspberry Pi I2C, not ESP32)

```bash
sudo apt install python3-pip i2c-tools
sudo i2cdetect -y 1    # expect 0x33
pip install adafruit-circuitpython-mlx90640
python3 02_mlx90640.py
```

| | |
|---|---|
| Wiring | VIN 3V3, GND, SDA GPIO2, SCL GPIO3 |
| Expected | 24 lines of 32 temperatures; palm in FOV raises a patch > 30 °C |
| Fail: no 0x33 | I2C off, 5 V instead of 3.3 V (can kill sensor), long wires |
| Fail: CRC | Lower I2C to 100 kHz, shorter cable |

Do not claim person identification from this array.
