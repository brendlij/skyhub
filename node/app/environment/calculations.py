import math


def dew_point_celsius(temperature_c: float, humidity_percent: float) -> float:
    humidity = max(1e-6, min(100.0, humidity_percent))
    a = 17.62
    b = 243.12
    gamma = math.log(humidity / 100.0) + (a * temperature_c) / (b + temperature_c)
    return (b * gamma) / (a - gamma)
