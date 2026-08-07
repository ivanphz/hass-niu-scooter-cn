"""Constants for the NIU integration."""

from urllib.parse import quote

DOMAIN = "niu"

# --------------------------------------------------------------------------
# 配置项
# --------------------------------------------------------------------------
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCOOTER_ID = "scooter_id"
CONF_MONITORED_VARIABLES = "monitored_variables"
CONF_REGION = "region"
CONF_PROXY = "proxy"
CONF_PROXY_USERNAME = "proxy_username"
CONF_PROXY_PASSWORD = "proxy_password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCOOTER_ID = 0
DEFAULT_MONITORED_VARIABLES = ["BatteryCharge"]
DEFAULT_REGION = "cn"
DEFAULT_PROXY = ""
DEFAULT_PROXY_USERNAME = ""
DEFAULT_PROXY_PASSWORD = ""

# 轮询间隔（秒）。原版写死 30 秒，对云端 API 来说过于激进，
# 4 个接口 × 2 次/分钟 = 8 req/min 长期不停，容易触发服务端风控。
DEFAULT_SCAN_INTERVAL = 300
MIN_SCAN_INTERVAL = 60
MAX_SCAN_INTERVAL = 3600

# 失败退避：连续失败时把轮询间隔按 2^n 拉长，最多拉到基准值的 8 倍
MAX_BACKOFF_FACTOR = 8

# token 最长复用时间（秒），到点强制重新登录
TOKEN_MAX_AGE = 12 * 3600

# --------------------------------------------------------------------------
# API 路径
# 国内服与国际服这 6 条路径完全一致，只有主机名不同，所以放在区服表外面
# --------------------------------------------------------------------------
LOGIN_URI = "/v3/api/oauth2/token"
MOTOR_BATTERY_API_URI = "/v3/motor_data/battery_info"
MOTOR_INDEX_API_URI = "/v5/scooter/motor_data/index_info"
MOTOINFO_LIST_API_URI = "/v5/scooter/list"
MOTOINFO_ALL_API_URI = "/motoinfo/overallTally"
TRACK_LIST_API_URI = "/v5/track/list/v2"

APP_ID = "niu_ktdrr960"
# 上游 marcelwestrahome 主线已升到 4.10.4，原 hasscc 版写死在 4.6.48
APP_VERSION = "4.10.4"

# 轨迹缩略图的国内 CDN 域名，两个区服都需要重写掉
THUMB_CDN_HOST = "app-api.niucache.com"

# --------------------------------------------------------------------------
# 区服配置
#
# gcj02: 国内服返回的经纬度是火星坐标（GCJ-02），喂给 HA 地图前必须转成
#        WGS-84，否则位置会偏移几百米。国际服返回的本来就是 WGS-84。
# --------------------------------------------------------------------------
REGIONS = {
    "cn": {
        "label": "中国大陆 (account.niu.com)",
        "account_base_url": "https://account.niu.com",
        "api_base_url": "https://app-api.niu.com",
        "client_identifier": "Domestic",
        "language": "zh-CN",
        "timezone": "Asia/Shanghai",
        "gcj02": True,
        "thumb_host": "app-api.niu.com",
        "thumb_overseas_path": False,
    },
    "intl": {
        "label": "国际 (account-fk.niu.com)",
        "account_base_url": "https://account-fk.niu.com",
        "api_base_url": "https://app-api-fk.niu.com",
        "client_identifier": "Overseas",
        "language": "en-US",
        "timezone": "UTC",
        "gcj02": False,
        "thumb_host": "app-api-fk.niu.com",
        "thumb_overseas_path": True,
    },
}

REGION_OPTIONS = list(REGIONS.keys())

# 旧代码里 from .const import ACCOUNT_BASE_URL 的兼容别名。
# 新代码一律通过 REGIONS[region] 取，不要再用这两个。
ACCOUNT_BASE_URL = REGIONS[DEFAULT_REGION]["account_base_url"]
API_BASE_URL = REGIONS[DEFAULT_REGION]["api_base_url"]

# --------------------------------------------------------------------------
# 传感器分组
# --------------------------------------------------------------------------
SENSOR_TYPE_BAT = "BAT"
SENSOR_TYPE_MOTO = "MOTO"
SENSOR_TYPE_DIST = "DIST"
SENSOR_TYPE_OVERALL = "TOTAL"
SENSOR_TYPE_POS = "POSITION"
SENSOR_TYPE_TRACK = "TRACK"

AVAILABLE_SENSORS = [
    "BatteryCharge",
    "Isconnected",
    "TimesCharged",
    "temperatureDesc",
    "Temperature",
    "BatteryGrade",
    "CurrentSpeed",
    "ScooterConnected",
    "IsCharging",
    "IsLocked",
    "TimeLeft",
    "EstimatedMileage",
    "centreCtrlBatt",
    "HDOP",
    "Longitude",
    "Latitude",
    "Distance",
    "RidingTime",
    "totalMileage",
    "DaysInUse",
    "LastTrackStartTime",
    "LastTrackEndTime",
    "LastTrackDistance",
    "LastTrackAverageSpeed",
    "LastTrackRidingtime",
    "LastTrackThumb",
]

SENSOR_NAMES_ZH = {
    "BatteryCharge": "电池电量",
    "Isconnected": "连接状态",
    "TimesCharged": "充电次数",
    "temperatureDesc": "温度描述",
    "Temperature": "电池温度",
    "BatteryGrade": "电池等级",
    "CurrentSpeed": "当前速度",
    "ScooterConnected": "滑板车连接",
    "IsCharging": "充电状态",
    "IsLocked": "锁定状态",
    "TimeLeft": "剩余时间",
    "EstimatedMileage": "预估里程",
    "centreCtrlBatt": "中央控制器电池",
    "HDOP": "GPS精度",
    "Longitude": "经度",
    "Latitude": "纬度",
    "Distance": "距离",
    "RidingTime": "骑行时间",
    "totalMileage": "总里程",
    "DaysInUse": "使用天数",
    "LastTrackStartTime": "最后行程开始时间",
    "LastTrackEndTime": "最后行程结束时间",
    "LastTrackDistance": "最后行程距离",
    "LastTrackAverageSpeed": "最后行程平均速度",
    "LastTrackRidingtime": "最后行程骑行时间",
    "LastTrackThumb": "最后行程缩略图",
}


def get_conf(config_entry, key, default=None):
    """读取配置项：options 优先于 data。

    区服 / 代理 / 轮询间隔这三项既可能在初次配置时写进 data，
    也可能之后在「选项」里改，所以统一走这个函数取。
    """
    if config_entry.options and key in config_entry.options:
        return config_entry.options[key]
    return config_entry.data.get(key, default)


def normalize_proxy(value: str | None) -> str | None:
    """把用户随手填的代理地址规约成 requests 认得的形式。

    允许的输入（都会被修正）：
        1.2.3.4:18443              -> http://1.2.3.4:18443
        http://1.2.3.4:18443       -> 原样
        socks5://1.2.3.4:1080      -> socks5h://1.2.3.4:1080  (让 DNS 在代理端解析)
        http://user:pw@1.2.3.4:18443 -> 原样
        空 / 纯空白                -> None（直连）

    地址明显不合法时抛 ValueError，由 config_flow 转成界面上的错误提示。
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    if "://" not in value:
        # 只填了 host:port，默认按 HTTP 代理处理
        value = f"http://{value}"

    scheme, _, rest = value.partition("://")
    scheme = scheme.lower()

    if scheme not in ("http", "https", "socks4", "socks5", "socks5h"):
        raise ValueError(f"不支持的代理协议: {scheme}")

    # socks5 会在 HA 本地解析域名，走 socks5h 让代理端解析，
    # 否则国内域名在境外机器上可能解析到错误的 IP。
    if scheme == "socks5":
        scheme = "socks5h"

    if not rest:
        raise ValueError("代理地址缺少主机名")

    hostport = rest.rsplit("@", 1)[-1]
    if ":" not in hostport.strip("[]"):
        raise ValueError("代理地址缺少端口号")

    return f"{scheme}://{rest}"


def build_proxy_url(
    address: str | None,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """把地址 + 单独填写的账号密码拼成 requests 能用的代理 URL。

    账号密码走 quote() 编码，所以密码里带 @ : / # 都不会破坏 URL 结构。
    两个字段都留空时，保留地址里可能自带的凭据。
    """
    normalized = normalize_proxy(address)
    if not normalized:
        return None
    if not username and not password:
        return normalized

    scheme, _, rest = normalized.partition("://")
    hostport = rest.rpartition("@")[-1]
    user = quote(username or "", safe="")
    pwd = quote(password or "", safe="")
    return f"{scheme}://{user}:{pwd}@{hostport}"


def mask_proxy(value: str | None) -> str:
    """脱敏后的代理地址，专供日志使用。凭据一律换成 ***。"""
    if not value:
        return "无"
    try:
        scheme, sep, rest = value.partition("://")
        if not sep:
            return "***"
        if "@" in rest:
            return f"{scheme}://***:***@{rest.rpartition('@')[-1]}"
        return value
    except Exception:  # pragma: no cover
        return "***"


def scrub_secrets(text: str, *secrets: str | None) -> str:
    """从任意文本里擦掉敏感串。

    requests / urllib3 抛出的异常消息里有时会原样带上完整代理 URL，
    这些消息最终会经 UpdateFailed 落到 ERROR 日志，必须先过一遍。
    """
    for secret in secrets:
        if secret and len(secret) > 2:
            text = text.replace(secret, "***")
    return text
