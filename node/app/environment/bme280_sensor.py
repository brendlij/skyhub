from datetime import datetime, timezone

from app.environment.base import EnvironmentReading, EnvironmentSensor
from app.environment.calculations import dew_point_celsius


def unsigned_16(msb: int, lsb: int) -> int:
    return (msb << 8) | lsb


def signed_16(msb: int, lsb: int) -> int:
    value = unsigned_16(msb, lsb)
    return value - 65536 if value & 0x8000 else value


def signed_12(value: int) -> int:
    return value - 4096 if value & 0x800 else value


class BME280Sensor(EnvironmentSensor):
    driver = "bme280"

    def __init__(self, bus: int = 1, address: int = 0x77):
        try:
            from smbus2 import SMBus
        except ImportError as error:
            raise RuntimeError("smbus2 is required for BME280 support") from error

        self.address = address
        self.bus = SMBus(bus)
        self.t_fine = 0
        self.calibration = self._read_calibration()
        self._configure()

    def _read_calibration(self) -> dict:
        calib = self.bus.read_i2c_block_data(self.address, 0x88, 24)
        h1 = self.bus.read_byte_data(self.address, 0xA1)
        hcal = self.bus.read_i2c_block_data(self.address, 0xE1, 7)

        return {
            "dig_T1": unsigned_16(calib[1], calib[0]),
            "dig_T2": signed_16(calib[3], calib[2]),
            "dig_T3": signed_16(calib[5], calib[4]),
            "dig_P1": unsigned_16(calib[7], calib[6]),
            "dig_P2": signed_16(calib[9], calib[8]),
            "dig_P3": signed_16(calib[11], calib[10]),
            "dig_P4": signed_16(calib[13], calib[12]),
            "dig_P5": signed_16(calib[15], calib[14]),
            "dig_P6": signed_16(calib[17], calib[16]),
            "dig_P7": signed_16(calib[19], calib[18]),
            "dig_P8": signed_16(calib[21], calib[20]),
            "dig_P9": signed_16(calib[23], calib[22]),
            "dig_H1": h1,
            "dig_H2": signed_16(hcal[1], hcal[0]),
            "dig_H3": hcal[2],
            "dig_H4": signed_12((hcal[3] << 4) | (hcal[4] & 0x0F)),
            "dig_H5": signed_12((hcal[5] << 4) | (hcal[4] >> 4)),
            "dig_H6": hcal[6] - 256 if hcal[6] & 0x80 else hcal[6],
        }

    def _configure(self) -> None:
        self.bus.write_byte_data(self.address, 0xF2, 0x01)
        self.bus.write_byte_data(self.address, 0xF4, 0x27)
        self.bus.write_byte_data(self.address, 0xF5, 0xA0)

    def read(self) -> EnvironmentReading:
        data = self.bus.read_i2c_block_data(self.address, 0xF7, 8)
        raw_pressure = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temperature = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_humidity = (data[6] << 8) | data[7]

        temperature_c = self._compensate_temperature(raw_temperature)
        pressure_hpa = self._compensate_pressure(raw_pressure) / 100.0
        humidity_percent = self._compensate_humidity(raw_humidity)

        return EnvironmentReading(
            temperature_c=temperature_c,
            humidity_percent=humidity_percent,
            pressure_hpa=pressure_hpa,
            dew_point_c=dew_point_celsius(temperature_c, humidity_percent),
            captured_at=datetime.now(timezone.utc),
        )

    def _compensate_temperature(self, adc_t: int) -> float:
        cal = self.calibration
        var1 = (((adc_t >> 3) - (cal["dig_T1"] << 1)) * cal["dig_T2"]) >> 11
        var2 = (((((adc_t >> 4) - cal["dig_T1"]) * ((adc_t >> 4) - cal["dig_T1"])) >> 12) * cal["dig_T3"]) >> 14
        self.t_fine = var1 + var2
        return ((self.t_fine * 5 + 128) >> 8) / 100.0

    def _compensate_pressure(self, adc_p: int) -> float:
        cal = self.calibration
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * cal["dig_P6"]
        var2 += (var1 * cal["dig_P5"]) << 17
        var2 += cal["dig_P4"] << 35
        var1 = ((var1 * var1 * cal["dig_P3"]) >> 8) + ((var1 * cal["dig_P2"]) << 12)
        var1 = (((1 << 47) + var1) * cal["dig_P1"]) >> 33

        if var1 == 0:
            return 0.0

        pressure = 1048576 - adc_p
        pressure = (((pressure << 31) - var2) * 3125) // var1
        var1 = (cal["dig_P9"] * (pressure >> 13) * (pressure >> 13)) >> 25
        var2 = (cal["dig_P8"] * pressure) >> 19
        pressure = ((pressure + var1 + var2) >> 8) + (cal["dig_P7"] << 4)
        return pressure / 256.0

    def _compensate_humidity(self, adc_h: int) -> float:
        cal = self.calibration
        value = self.t_fine - 76800
        value = (((((adc_h << 14) - (cal["dig_H4"] << 20) - (cal["dig_H5"] * value)) + 16384) >> 15) *
                 (((((((value * cal["dig_H6"]) >> 10) * (((value * cal["dig_H3"]) >> 11) + 32768)) >> 10) + 2097152) *
                   cal["dig_H2"] + 8192) >> 14))
        value -= (((value >> 15) * (value >> 15)) >> 7) * cal["dig_H1"] >> 4
        value = max(0, min(value, 419430400))
        return (value >> 12) / 1024.0
