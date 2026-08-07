"""Data coordinator for NIU integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from time import gmtime, strftime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NiuAPI, NiuAuthError, NiuConnectionError
from .const import (
    CONF_PASSWORD,
    CONF_PROXY,
    CONF_PROXY_PASSWORD,
    CONF_PROXY_USERNAME,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_SCOOTER_ID,
    CONF_USERNAME,
    DEFAULT_PROXY,
    DEFAULT_PROXY_PASSWORD,
    DEFAULT_PROXY_USERNAME,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCOOTER_ID,
    MAX_BACKOFF_FACTOR,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REGIONS,
    SENSOR_TYPE_BAT,
    SENSOR_TYPE_DIST,
    SENSOR_TYPE_MOTO,
    SENSOR_TYPE_OVERALL,
    SENSOR_TYPE_POS,
    SENSOR_TYPE_TRACK,
    TOKEN_MAX_AGE,
    get_conf,
    mask_proxy,
)

_LOGGER = logging.getLogger(__name__)


class NiuDataCoordinator(DataUpdateCoordinator):
    """NIU data coordinator。

    与原版的区别：
    1. 轮询间隔可配（默认 300 秒，原版写死 30 秒）。
    2. 连续失败时指数退避，不再以固定频率反复冲击服务端。
    3. 失败时抛 UpdateFailed 交给 HA 处理，不再自己 _LOGGER.error 造成日志刷屏。
    4. 四个子接口全部失败时正确标记为失败，不再返回一坨 None 却报告成功。
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        region = get_conf(config_entry, CONF_REGION, DEFAULT_REGION)
        if region not in REGIONS:
            _LOGGER.warning("未知区服 %s，回退到 %s", region, DEFAULT_REGION)
            region = DEFAULT_REGION

        interval = int(get_conf(config_entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        interval = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, interval))

        super().__init__(
            hass,
            _LOGGER,
            name="NIU Scooter",
            update_interval=timedelta(seconds=interval),
        )

        self.config_entry = config_entry
        self.region = region
        # 国内服返回火星坐标，需要转换；国际服不需要
        self.gcj02: bool = REGIONS[region]["gcj02"]

        self._base_interval = interval
        self._fail_streak = 0

        proxy = get_conf(config_entry, CONF_PROXY, DEFAULT_PROXY) or None
        self.api = NiuAPI(
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            region=region,
            proxy=proxy,
            proxy_username=get_conf(
                config_entry, CONF_PROXY_USERNAME, DEFAULT_PROXY_USERNAME
            )
            or None,
            proxy_password=get_conf(
                config_entry, CONF_PROXY_PASSWORD, DEFAULT_PROXY_PASSWORD
            )
            or None,
        )

        self.sn: str | None = None
        self.token: str | None = None
        self._token_ts: float = 0.0
        self._data_bat: dict[str, Any] | None = None
        self._data_moto: dict[str, Any] | None = None
        self._data_moto_info: dict[str, Any] | None = None
        self._data_track_info: dict[str, Any] | None = None

        _LOGGER.debug(
            "NIU coordinator 初始化: region=%s interval=%ss proxy=%s",
            region,
            interval,
            # 绝不能打印原始代理地址，可能含密码
            mask_proxy(self.api.proxy),
        )

    # ------------------------------------------------------------------
    # 退避
    # ------------------------------------------------------------------

    def _apply_backoff(self) -> None:
        self._fail_streak += 1
        factor = min(2 ** (self._fail_streak - 1), MAX_BACKOFF_FACTOR)
        new_interval = timedelta(seconds=self._base_interval * factor)
        if new_interval != self.update_interval:
            self.update_interval = new_interval
            _LOGGER.debug(
                "NIU 连续失败 %s 次，轮询间隔退避至 %s",
                self._fail_streak,
                new_interval,
            )

    def _reset_backoff(self) -> None:
        if self._fail_streak:
            _LOGGER.debug("NIU 恢复正常，轮询间隔复位到 %ss", self._base_interval)
            self._fail_streak = 0
            self.update_interval = timedelta(seconds=self._base_interval)

    def _invalidate_token(self) -> None:
        self.token = None
        self.sn = None
        self._token_ts = 0.0

    # ------------------------------------------------------------------
    # 主更新流程
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from NIU API."""
        try:
            await self._ensure_session()
            ok_count = await self._fetch_all()
        except NiuAuthError as err:
            self._invalidate_token()
            self._apply_backoff()
            raise UpdateFailed(f"NIU 认证失败: {err}") from err
        except NiuConnectionError as err:
            self._apply_backoff()
            raise UpdateFailed(f"连接 NIU API 失败: {err}") from err

        if ok_count == 0:
            # 登录成功但四个数据接口全挂，多半是 token 已失效或服务端异常，
            # 下一轮强制重新登录。
            self._invalidate_token()
            self._apply_backoff()
            raise UpdateFailed("NIU 所有数据接口均获取失败")

        self._reset_backoff()
        return {
            "battery": self._data_bat,
            "motor": self._data_moto,
            "overall": self._data_moto_info,
            "track": self._data_track_info,
        }

    async def _ensure_session(self) -> None:
        """确保持有可用的 token 和车辆 SN。"""
        expired = (
            self.token is None
            or self.sn is None
            or (time.time() - self._token_ts) > TOKEN_MAX_AGE
        )
        if not expired:
            return

        self.token = await self.hass.async_add_executor_job(self.api.get_token)
        self._token_ts = time.time()

        vehicles = await self.hass.async_add_executor_job(
            self.api.get_vehicles_info, self.token
        )
        scooter_id = self.config_entry.data.get(CONF_SCOOTER_ID, DEFAULT_SCOOTER_ID)
        try:
            items = vehicles["data"]["items"]
        except (KeyError, TypeError) as err:
            raise NiuConnectionError("车辆列表响应结构异常") from err

        if scooter_id >= len(items):
            raise NiuConnectionError(
                f"滑板车 ID {scooter_id} 超出范围（账号下共 {len(items)} 辆）"
            )
        self.sn = items[scooter_id]["sn_id"]

    async def _fetch_all(self) -> int:
        """拉取四个数据接口，返回成功的个数。

        单个接口失败不算致命（比如轨迹接口偶发抽风），保留上一轮的值即可；
        但全部失败要向上报错，否则 HA 会一直显示"正常"而数据全是空的。
        """
        jobs = (
            ("battery", self._update_battery_info),
            ("motor", self._update_motor_info),
            ("overall", self._update_overall_info),
            ("track", self._update_track_info),
        )
        ok = 0
        for name, job in jobs:
            try:
                await job()
                ok += 1
            except NiuAuthError:
                # 鉴权问题要冒泡上去触发重新登录
                raise
            except (NiuConnectionError, KeyError, TypeError) as err:
                _LOGGER.debug("NIU %s 接口获取失败: %s", name, err)
        return ok

    async def _update_battery_info(self) -> None:
        self._data_bat = await self.hass.async_add_executor_job(
            self.api.get_battery_info, self.sn, self.token
        )

    async def _update_motor_info(self) -> None:
        self._data_moto = await self.hass.async_add_executor_job(
            self.api.get_motor_info, self.sn, self.token
        )

    async def _update_overall_info(self) -> None:
        self._data_moto_info = await self.hass.async_add_executor_job(
            self.api.get_overall_info, self.sn, self.token
        )

    async def _update_track_info(self) -> None:
        self._data_track_info = await self.hass.async_add_executor_job(
            self.api.get_track_info, self.sn, self.token
        )

    # ------------------------------------------------------------------
    # 取数（字段名沿用小牛 API 原样，含其自带的 postion 拼写）
    # ------------------------------------------------------------------

    def get_battery_data(self, field: str) -> Any:
        if not self._data_bat or "data" not in self._data_bat:
            return None
        try:
            return self._data_bat["data"]["batteries"]["compartmentA"].get(field)
        except (KeyError, TypeError):
            return None

    def get_motor_data(self, field: str) -> Any:
        if not self._data_moto or "data" not in self._data_moto:
            return None
        return self._data_moto["data"].get(field)

    def get_distance_data(self, field: str) -> Any:
        if not self._data_moto or "data" not in self._data_moto:
            return None
        last_track = self._data_moto["data"].get("lastTrack")
        if not isinstance(last_track, dict):
            return None
        return last_track.get(field)

    def get_position_data(self, field: str) -> Any:
        if not self._data_moto or "data" not in self._data_moto:
            return None
        # "postion" 是小牛 API 自己的拼写错误，不是笔误
        position = self._data_moto["data"].get("postion")
        if not isinstance(position, dict):
            return None
        return position.get(field)

    def get_overall_data(self, field: str) -> Any:
        if not self._data_moto_info or "data" not in self._data_moto_info:
            return None
        return self._data_moto_info["data"].get(field)

    def get_track_data(self, field: str) -> Any:
        if not self._data_track_info or "data" not in self._data_track_info:
            return None
        tracks = self._data_track_info["data"]
        if not tracks:
            return None
        latest = tracks[0]

        try:
            if field in ("startTime", "endTime"):
                return datetime.fromtimestamp(latest[field] / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            if field == "ridingtime":
                return strftime("%H:%M:%S", gmtime(latest[field]))
            if field == "track_thumb":
                return self.api.rewrite_thumb_url(latest.get(field))
        except (KeyError, TypeError, ValueError, OSError) as err:
            _LOGGER.debug("解析轨迹字段 %s 失败: %s", field, err)
            return None

        return latest.get(field)

    def get_data_by_type(self, sensor_type: str, field: str) -> Any:
        """按传感器分组分发到对应的取数方法。"""
        dispatch = {
            SENSOR_TYPE_BAT: self.get_battery_data,
            SENSOR_TYPE_MOTO: self.get_motor_data,
            SENSOR_TYPE_DIST: self.get_distance_data,
            SENSOR_TYPE_POS: self.get_position_data,
            SENSOR_TYPE_OVERALL: self.get_overall_data,
            SENSOR_TYPE_TRACK: self.get_track_data,
        }
        getter = dispatch.get(sensor_type)
        return getter(field) if getter else None
