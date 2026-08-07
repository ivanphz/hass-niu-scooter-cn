"""Support for NIU Scooters sensors."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    AVAILABLE_SENSORS,
    CONF_MONITORED_VARIABLES,
    CONF_SCOOTER_ID,
    DEFAULT_MONITORED_VARIABLES,
    DEFAULT_SCOOTER_ID,
    DOMAIN,
    REGIONS,
    SENSOR_TYPE_BAT,
    SENSOR_TYPE_DIST,
    SENSOR_TYPE_MOTO,
    SENSOR_TYPE_OVERALL,
    SENSOR_TYPE_POS,
    SENSOR_TYPE_TRACK,
    get_conf,
)
from .coordinator import NiuDataCoordinator

PI = 3.1415926535897932384626  # 圆周率
ee = 0.00669342162296594323  # 偏心率平方
a = 6378245.0  # 长半轴

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "BatteryCharge": [
        "battery_charge",
        "%",
        "batteryCharging",
        SENSOR_TYPE_BAT,
        SensorDeviceClass.BATTERY,
        "mdi:battery-charging-50",
        SensorStateClass.MEASUREMENT,
    ],
    "Isconnected": [
        "is_connected",
        "",
        "isConnected",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:connection",
        None,
    ],
    "TimesCharged": [
        "times_charged",
        "x",
        "chargedTimes",
        SENSOR_TYPE_BAT,
        None,
        "mdi:battery-charging-wireless",
        SensorStateClass.TOTAL,
    ],
    "temperatureDesc": [
        "temp_descr",
        "",
        "temperatureDesc",
        SENSOR_TYPE_BAT,
        None,
        "mdi:thermometer-alert",
        None,
    ],
    "Temperature": [
        "temperature",
        "°C",
        "temperature",
        SENSOR_TYPE_BAT,
        SensorDeviceClass.TEMPERATURE,
        "mdi:thermometer",
        SensorStateClass.MEASUREMENT,
    ],
    "BatteryGrade": [
        "battery_grade",
        "%",
        "gradeBattery",
        SENSOR_TYPE_BAT,
        SensorDeviceClass.BATTERY,
        "mdi:car-battery",
        SensorStateClass.MEASUREMENT,
    ],
    "CurrentSpeed": [
        "current_speed",
        "km/h",
        "nowSpeed",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:speedometer",
        SensorStateClass.MEASUREMENT,
    ],
    "ScooterConnected": [
        "scooter_connected",
        "",
        "isConnected",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:motorbike-electric",
        None,
    ],
    "IsCharging": [
        "is_charging",
        "",
        "isCharging",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:battery-charging",
        None,
    ],
    "IsLocked": [
        "is_locked",
        "",
        "lockStatus",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:lock",
        None,
    ],
    "TimeLeft": [
        "time_left",
        "h",
        "leftTime",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:av-timer",
        SensorStateClass.MEASUREMENT,
    ],
    "EstimatedMileage": [
        "estimated_mileage",
        "km",
        "estimatedMileage",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:map-marker-distance",
        SensorStateClass.MEASUREMENT,
    ],
    "centreCtrlBatt": [
        "centre_ctrl_batt",
        "%",
        "centreCtrlBattery",
        SENSOR_TYPE_MOTO,
        SensorDeviceClass.BATTERY,
        "mdi:car-cruise-control",
        SensorStateClass.MEASUREMENT,
    ],
    "HDOP": [
        "hdp",
        "",
        "hdop",
        SENSOR_TYPE_MOTO,
        None,
        "mdi:map-marker",
        SensorStateClass.MEASUREMENT,
    ],
    "Longitude": [
        "long",
        "",
        "lng",
        SENSOR_TYPE_POS,
        None,
        "mdi:map-marker",
        SensorStateClass.MEASUREMENT,
    ],
    "Latitude": [
        "lat",
        "",
        "lat",
        SENSOR_TYPE_POS,
        None,
        "mdi:map-marker",
        SensorStateClass.MEASUREMENT,
    ],
    "Distance": [
        "distance",
        "m",
        "distance",
        SENSOR_TYPE_DIST,
        None,
        "mdi:map-marker-distance",
        SensorStateClass.MEASUREMENT,
    ],
    "RidingTime": [
        "riding_time",
        "s",
        "ridingTime",
        SENSOR_TYPE_DIST,
        None,
        "mdi:map-clock",
        SensorStateClass.MEASUREMENT,
    ],
    "totalMileage": [
        "total_mileage",
        "km",
        "totalMileage",
        SENSOR_TYPE_OVERALL,
        None,
        "mdi:map-marker-distance",
        SensorStateClass.TOTAL,
    ],
    "DaysInUse": [
        "bind_days_count",
        "days",
        "bindDaysCount",
        SENSOR_TYPE_OVERALL,
        None,
        "mdi:calendar-today",
        SensorStateClass.TOTAL,
    ],
    "LastTrackStartTime": [
        "last_track_start_time",
        "",
        "startTime",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:clock-start",
        None,
    ],
    "LastTrackEndTime": [
        "last_track_end_time",
        "",
        "endTime",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:clock-end",
        None,
    ],
    "LastTrackDistance": [
        "last_track_distance",
        "m",
        "distance",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:map-marker-distance",
        SensorStateClass.MEASUREMENT,
    ],
    "LastTrackAverageSpeed": [
        "last_track_average_speed",
        "km/h",
        "avespeed",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:speedometer",
        SensorStateClass.MEASUREMENT,
    ],
    "LastTrackRidingtime": [
        "last_track_riding_time",
        "",
        "ridingtime",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:timelapse",
        None,
    ],
    "LastTrackThumb": [
        "last_track_thumb",
        "",
        "track_thumb",
        SENSOR_TYPE_TRACK,
        None,
        "mdi:map",
        None,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NIU sensors based on a config entry."""
    coordinator: NiuDataCoordinator = config_entry.runtime_data.coordinator

    # 用 get_conf 而不是直接读 data：原版只读 data，导致在「选项」里
    # 改传感器勾选后完全不生效（options 里的值被无视了）。
    monitored_variables = get_conf(
        config_entry, CONF_MONITORED_VARIABLES, DEFAULT_MONITORED_VARIABLES
    )

    entities = []
    for sensor in monitored_variables:
        if sensor not in SENSOR_TYPES:
            _LOGGER.warning("忽略未知传感器: %s", sensor)
            continue
        sensor_config = SENSOR_TYPES[sensor]
        entities.append(
            NiuSensor(
                coordinator,
                sensor,
                sensor_config[0],
                sensor_config[1],
                sensor_config[2],
                sensor_config[3],
                sensor_config[4],
                sensor_config[5],
                sensor_config[6],
                config_entry,
            )
        )

    async_add_entities(entities)


class NiuSensor(SensorEntity):
    """Representation of a NIU sensor."""

    def __init__(
        self,
        coordinator: NiuDataCoordinator,
        sensor_name: str,
        sensor_id: str,
        unit_of_measurement: str,
        id_name: str,
        sensor_type: str,
        device_class: SensorDeviceClass | None,
        icon: str,
        state_class: SensorStateClass | None,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._sensor_name = sensor_name
        self._sensor_id = sensor_id
        # 空字符串会让 HA 抱怨单位无效，统一规约成 None
        self._unit_of_measurement = unit_of_measurement or None
        self._id_name = id_name
        self._sensor_type = sensor_type
        self._device_class = device_class
        self._icon = icon
        self._state_class = state_class
        self._config_entry = config_entry

        scooter_id = config_entry.data.get(CONF_SCOOTER_ID, DEFAULT_SCOOTER_ID)

        # 实体 ID 保持与原版一致，避免升级后历史数据断档
        self._attr_unique_id = f"niu_scooter_{scooter_id}_{sensor_id}"
        self._attr_name = f"NIU Scooter {scooter_id} {sensor_name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"niu_scooter_{scooter_id}_{coordinator.sn}")},
            name=f"NIU Scooter {scooter_id}",
            manufacturer="NIU",
            model="Electric Scooter",
            configuration_url=REGIONS[coordinator.region]["account_base_url"],
        )

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class."""
        return self._state_class

    def _convert_position(self, lng: Any, lat: Any) -> tuple[float, float] | None:
        """把坐标转成 WGS-84。国际服本来就是 WGS-84，原样返回。"""
        try:
            lng_f = float(lng)
            lat_f = float(lat)
        except (TypeError, ValueError):
            return None
        if lng_f == 0.0 and lat_f == 0.0:
            return None
        if not self.coordinator.gcj02:
            return lng_f, lat_f
        return gcj02_to_wgs84(lng_f, lat_f)

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None

        raw_value = self.coordinator.get_data_by_type(self._sensor_type, self._id_name)

        if self._sensor_type == SENSOR_TYPE_POS and self._id_name in ("lng", "lat"):
            if self._id_name == "lng":
                lng, lat = raw_value, self.coordinator.get_position_data("lat")
            else:
                lng, lat = self.coordinator.get_position_data("lng"), raw_value

            converted = self._convert_position(lng, lat)
            if converted is None:
                # 车辆离线时坐标为 0，属正常情况，不该刷 warning
                _LOGGER.debug("坐标为空或为零，跳过转换")
                return raw_value
            return converted[0] if self._id_name == "lng" else converted[1]

        return raw_value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        if not (self._sensor_type == SENSOR_TYPE_MOTO and self._id_name == "isConnected"):
            return None

        try:
            converted = self._convert_position(
                self.coordinator.get_position_data("lng"),
                self.coordinator.get_position_data("lat"),
            )
            longitude, latitude = converted if converted else (None, None)

            return {
                "bmsId": self.coordinator.get_battery_data("bmsId") or "N/A",
                "latitude": latitude,
                "longitude": longitude,
                "gsm": self.coordinator.get_motor_data("gsm") or "N/A",
                "gps": self.coordinator.get_motor_data("gps") or "N/A",
                "time": self.coordinator.get_distance_data("time") or 0,
                "range": self.coordinator.get_motor_data("estimatedMileage") or 0,
                "battery": self.coordinator.get_battery_data("batteryCharging") or 0,
                "battery_grade": self.coordinator.get_battery_data("gradeBattery") or 0,
                "centre_ctrl_batt": self.coordinator.get_motor_data("centreCtrlBattery") or 0,
                "region": self.coordinator.region,
            }
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("获取 %s 的附加属性失败: %s", self._attr_name, err)
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


# ---------------------------------------------------------------------------
# GCJ-02 (火星坐标) -> WGS-84
# 仅国内服需要：小牛国内 API 返回的经纬度是加密偏移过的，
# 直接喂给 HA 地图会偏移几百米。国际服返回的已经是 WGS-84。
# ---------------------------------------------------------------------------


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    lat = float(lat)
    lng = float(lng)

    if out_of_china(lng, lat):
        return lng, lat

    dlat = transformlat(lng - 105.0, lat - 35.0)
    dlng = transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


def out_of_china(lng: float, lat: float) -> bool:
    lat = float(lat)
    lng = float(lng)
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def transformlat(lng: float, lat: float) -> float:
    lat = float(lat)
    lng = float(lng)
    ret = (
        -100.0
        + 2.0 * lng
        + 3.0 * lat
        + 0.2 * lat * lat
        + 0.1 * lng * lat
        + 0.2 * math.sqrt(abs(lng))
    )
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def transformlng(lng: float, lat: float) -> float:
    lat = float(lat)
    lng = float(lng)
    ret = (
        300.0
        + lng
        + 2.0 * lat
        + 0.1 * lng * lng
        + 0.1 * lng * lat
        + 0.1 * math.sqrt(abs(lng))
    )
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret
