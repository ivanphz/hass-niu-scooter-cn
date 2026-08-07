# Home Assistant NIU 滑板车集成（国内服增强版）

用于 Home Assistant 的小牛电动车自定义集成。在 [hasscc/home-assistant-niu-component](https://github.com/hasscc/home-assistant-niu-component) 基础上增加了**区服切换**、**代理支持**和**可配置轮询**，主要面向「车在国内服务器、Home Assistant 在境外」这种部署。

---

## 为什么有这个 fork

小牛的账号体系是分服的，两套服务器的接口路径完全一致，只有主机名不同：

| 区服 | 账号端点 | 数据端点 | 坐标系 |
| --- | --- | --- | --- |
| 中国大陆 | `account.niu.com` | `app-api.niu.com` | GCJ-02（火星坐标） |
| 国际 | `account-fk.niu.com` | `app-api-fk.niu.com` | WGS-84 |

上游两条分支各自只支持一边，且都把主机名写死在 `const.py` 里。本 fork 把区服做成运行时开关，一份代码同时支持两区，并解决了境外部署访问国内服务器的连通性问题。

`account.niu.com` 解析到阿里云北京机房，实测**境外绝大多数节点无法建立 TCP 连接**（仅港澳台部分节点可通），因此本 fork 内置了代理支持。

---

## 上游与授权

本项目是二次 fork，血缘如下：

```
marcelwestrahome/home-assistant-niu-component   ← fork 网络的根，国际服 (-fk)
  └── hasscc/home-assistant-niu-component       ← 国内服分支，重构为 DataUpdateCoordinator 架构
        └── 本仓库                                ← 区服抽象 + 代理 + 轮询治理
```

- **[marcelwestrahome/home-assistant-niu-component](https://github.com/marcelwestrahome/home-assistant-niu-component)** — 原始作者 Marcel Westra，异步化由 [@pikka97](https://github.com/pikka97) 完成。仍在维护，是双电池支持、轨迹缩略图渲染、动态 UA 的来源。
- **[hasscc/home-assistant-niu-component](https://github.com/hasscc/home-assistant-niu-component)** — 由 [@goxofy](https://github.com/goxofy) 从上游 fork 并重构，改用 `DataUpdateCoordinator`，加入国内端点、GCJ-02 坐标转换和中文翻译。**本仓库的直接基座。**

授权沿用 Apache License 2.0，见 [LICENSE](LICENSE)。`upstream/` 目录下保存的上游代码快照仅用于比对，版权归各自作者。

---

## 相对基座的改动

**新增能力**

- 区服开关（`cn` / `intl`），主机名、UA 的 `clientIdentifier`、坐标系、缩略图 CDN 重写目标全部随区服切换
- 代理支持，且**只作用于本集成**（`session.trust_env = False`，不读 `HTTP_PROXY` 环境变量，也不会污染 HA 其他集成的出站流量）
- 轮询间隔可配（默认 300 秒，原为写死 30 秒），连续失败时按 2ⁿ 指数退避，封顶 8 倍
- UA 从 `manager/4.6.48` 提升到 `manager/4.10.4`，与上游主线对齐
- 连接超时与读取超时分离（10s / 30s）

**修复的问题**

| 问题 | 表现 |
| --- | --- |
| `sensor.py` 只读 `config_entry.data` | 在「选项」里改传感器勾选完全不生效 |
| 子接口失败被静默吞掉 | 四个接口全挂时仍报告更新成功，实体显示「可用」但数据全空 |
| token 拿到后永不刷新 | token 过期后只能重启 HA 恢复 |
| `_LOGGER.error` + `raise` 双重记录 | 故障时日志被同一条错误刷屏 |
| `requests.Session` 未释放 | 反复重载集成会泄漏 socket |
| 空字符串单位 | HA 报无效单位警告 |
| 坐标为零时打 `warning` | 车辆离线属常态，不应刷日志 |

**实体 `unique_id` 保持与基座一致**，从 hasscc 版升级过来不会断历史数据。

---

## 安装

### HACS（推荐）

1. HACS → 集成 → 右上角 ⋯ → Custom repositories
2. Repository 填 `https://github.com/ivanphz/hass-niu-scooter-cn`，Type 选 `Integration`
3. ADD → 搜索 `NIU Scooter Integration` → 下载
4. 重启 Home Assistant

### 手动

把 `custom_components/niu` 整个目录复制到 HA 的 `config/custom_components/`，重启。

装好后：设置 → 设备与服务 → 添加集成 → 搜索 `NIU`。

---

## 配置

| 字段 | 说明 |
| --- | --- |
| 用户名/邮箱、密码 | 小牛 App 的账号密码。密码以 MD5 传输，不会明文出网 |
| 滑板车 ID | 一个账号多辆车时用，从 0 开始 |
| **服务器区域** | 国内买的车选「中国大陆」，海外版选「国际」。**账号分服，选错会认证失败** |
| **代理地址** | 留空即直连。见下方「代理配置」 |
| **轮询间隔** | 默认 300 秒。不建议低于 120 秒 |

配好之后：

- **选项** 里可以改传感器、轮询间隔、代理，改完自动重载
- **重新配置** 里可以改凭据、区服、代理

---

## 代理配置

**如果你的 HA 能直连 `account.niu.com`，代理框留空即可，这一节可以跳过。**

先花十秒确认到底需不需要，在 HA 宿主机上跑：

```bash
nc -vz -w 8 account.niu.com 443
```

通了就不用代理。超时就往下看。

### 代理地址填什么

三个字段，后两个可留空：

| 字段 | 填什么 |
| --- | --- |
| **代理地址** | `1.2.3.4:18443`、`http://1.2.3.4:18443`、`socks5://1.2.3.4:1080` 都行 |
| **代理用户名** | 代理需要认证时填，否则留空 |
| **代理密码** | 同上。UI 上掩码显示 |

地址写得随便一点也认，会自动规约：

| 你填的 | 实际生效 |
| --- | --- |
| `1.2.3.4:18443` | `http://1.2.3.4:18443` |
| `socks5://1.2.3.4:1080` | `socks5h://1.2.3.4:1080`（改成让代理端解析域名） |
| 留空 | 直连 |

账号密码由集成内部做 URL 编码后拼进地址，**密码可以包含 `@` `:` `/` `#` 等特殊字符**。地址里直接写成 `socks5://user:pass@host:port` 也认，此时两个凭据字段留空即可。

地址不合法时表单会当场报错，不用等到连接超时才发现。

> SOCKS5 需要 `PySocks`，已写进 `manifest.json` 的 requirements，HA 会自动安装。

### 关于凭据安全

三点需要知道：

**存储是明文。** 代理地址和凭据存在 `/config/.storage/core.config_entries`，未加密。你的小牛账号密码本来就存在同一个文件里，所以暴露面没有变大，但**备份 `/config` 时要当作敏感数据处理**。

**日志已脱敏。** 代理凭据不会出现在任何日志里——包括 `requests` / `urllib3` 自己抛出的、消息中原样带完整代理 URL 的异常，落盘前都会过一遍擦除。日志里只会看到 `http://***:***@1.2.3.4:18443`。

**传输是明文。** HTTP 代理的 Basic 认证只是 base64，SOCKS5 的用户名密码认证（RFC 1929）连 base64 都没有。所以代理密码防的是「有人扫到你开放的端口」，**防不住 HA→中转机这一跳上的窃听者**。

因此推荐 **IP 白名单 + 密码同时启用**：白名单挡未授权来源，密码在白名单失效时兜底（比如你的出口 IP 变了、或同机房其他机器伪造）。单用任何一个都有盲区。

### 方案 A：tinyproxy + IP 白名单（最省事，推荐）

在**能访问 `account.niu.com` 的机器**上（国内服务器，或实测可通的香港机）：

```bash
apt update && apt install -y tinyproxy

# 改两行配置
sed -i 's/^Port .*/Port 18443/' /etc/tinyproxy/tinyproxy.conf
echo "Allow 你的HA公网IP" >> /etc/tinyproxy/tinyproxy.conf

systemctl restart tinyproxy
```

HA 里代理地址填：`你的中转机IP:18443`

`Allow` 是 IP 白名单，tinyproxy 默认已有 `Allow 127.0.0.1`，追加一行即可。

再叠一层密码（推荐）：

```bash
echo "BasicAuth niu 你的密码" >> /etc/tinyproxy/tinyproxy.conf
systemctl restart tinyproxy
```

HA 里「代理用户名」填 `niu`，「代理密码」填你设的密码，地址仍然是 `中转机IP:18443`。

验证：

```bash
# 在 HA 宿主机上
curl -x http://中转机IP:18443 -sv -o /dev/null --connect-timeout 8 \
  https://account.niu.com/v3/api/oauth2/token 2>&1 | grep -E "Connected|onnect"
```

### 方案 B：gost + 密码（HA 出口 IP 会变时用）

```bash
docker run -d --name niu-proxy --restart always -p 18443:8080 \
  ginuerzh/gost -L "http://niu:换成你的密码@:8080"
```

HA 里代理地址填 `中转机IP:18443`，用户名 `niu`，密码填你设的那个。

想用 SOCKS5 就把 `-L` 换成：

```bash
-L "socks5://niu:换成你的密码@:8080"
```

HA 里地址改成 `socks5://中转机IP:18443`，用户名密码照填。

### 方案 C：nginx L4 透传 + hosts（代理框留空）

TCP 层按 SNI 转发，不解密，TLS 端到端仍是小牛的证书。HA 侧不填代理，改 hosts 即可。

中转机上（需要 `stream_ssl_preread` 模块，Ubuntu 的 `nginx-full` 自带，用 `nginx -V 2>&1 | grep -o stream_ssl_preread` 验证）：

```nginx
# /etc/nginx/nginx.conf —— 顶层 stream 块，与 http 平级
stream {
    resolver 223.5.5.5 valid=300s;

    map $ssl_preread_server_name $niu_upstream {
        account.niu.com   account.niu.com:443;
        app-api.niu.com   app-api.niu.com:443;
        default           "";
    }

    server {
        listen 443;
        ssl_preread on;
        proxy_pass $niu_upstream;
        proxy_connect_timeout 10s;
        proxy_timeout 60s;

        allow  你的HA公网IP;
        deny   all;
    }
}
```

HA 侧（Docker Compose）：

```yaml
services:
  homeassistant:
    extra_hosts:
      - "account.niu.com:中转机IP"
      - "app-api.niu.com:中转机IP"
```

裸机部署就直接写 `/etc/hosts`。

**约束**：hosts 只能改 IP 不能改端口，所以中转机的 443 必须空出来。国内云厂商对未备案域名的 80/443 有巡检，这里没有域名解析落到该机器上，理论上不触发，但需知悉。

### 中转机选哪台

| 位置 | 可通性 | 代价 |
| --- | --- | --- |
| 国内云服务器 | 必通 | 需实名 |
| 香港 | **必须先实测** | 无实名 |
| 其他境外 | 基本不通 | — |

香港机不能想当然。实测数据显示香港住宅宽带节点可通（50–60ms），但机房 IP 段未必在放行名单内。**先开按小时计费的机器跑一遍 `nc -vz -w 8 account.niu.com 443`，通了再包月。**

---

## 故障排查

### 日志里出现 `ConnectTimeoutError`

TCP 握手就没完成，与账号密码无关，别反复试密码。按顺序查：

```bash
nslookup account.niu.com                        # 应得到阿里云北京的 IP
nc -vz -w 8 account.niu.com 443                 # 通不通
mtr -T -P 443 -r -c 20 account.niu.com          # 断在哪一跳
```

在 HA **容器内**再跑一遍，容器的 DNS 和路由未必和宿主一致：

```bash
docker exec -it homeassistant sh -c \
  'curl -sv -o /dev/null --connect-timeout 8 https://account.niu.com/v3/api/oauth2/token' 2>&1 | tail -20
```

如果境外不通但国内通 → 配代理。

### 认证失败但网络是通的

多半是区服选错。国内「小牛电动」App 注册的账号选「中国大陆」，国际 NIU App 选「国际」。

### 地图上位置偏移几百米

区服选成「国际」了。国内 API 返回 GCJ-02 坐标，必须选「中国大陆」才会启用坐标转换。

### 传感器改了不生效

本 fork 已修复。如果仍有问题，试试「重新配置」而不是「选项」。

---

## 仓库设置要求（HACS）

HACS 除了检查文件，还会检查 GitHub 仓库本身。以下两项在仓库设置里配，不是文件：

- **描述**：仓库首页右侧 About 的齿轮里填，HACS 界面会直接显示它
- **Topics**：同一处添加，用于 HACS 商店内的搜索

`hacs.json` 只允许这些键：`name`、`content_in_root`、`zip_release`、`filename`、`hide_default_branch`、`country`、`homeassistant`、`hacs`、`persistent_directory`。`authors` / `repository` / `issues` 由 HACS 从 GitHub 直接读取，写进去会导致校验失败。

> 这些检查针对的是「提交进 HACS 默认商店」。作为自用的 custom repository，不通过也照样能装。

## 维护：跟踪上游

`.github/workflows/upstream-check.yml` 每周一自动检查两个上游仓库，有变动就把快照提交到 `upstream/`，并开一个带完整 diff 的 Issue。

**需要在 Settings → Actions → General → Workflow permissions 里选 "Read and write permissions"**，否则无法提交和开 Issue。也可以在 Actions 页手动触发。

快照里 `manifest.json` 和 `__init__.py` 带 `.txt` 后缀，这是有意为之：hassfest 会把任何含这两个文件的目录当作集成校验，快照目录会因「域名与目录名不符」而让 CI 报错。其余 `.py` 保持原扩展名，diff 里仍有语法高亮。

每次运行会先 `rm -rf` 再重建快照目录，所以上游删掉的文件会自动从快照中消失，手工改动也会被覆盖。

快照有变动但增删行数均为 0（纯重命名、权限变更之类）时，只提交快照、不开 Issue。判据取自 `git diff --numstat` 的前两列，而非解析 `git diff --shortstat` 的英文措辞。

收到 Issue 后的判断顺序：

1. 改的是 API 路径、`app_id`、UA 或鉴权方式吗？→ **两区共用，必须跟**
2. 改的是 `-fk` 相关的东西吗？→ 与国内服无关，忽略
3. `SENSOR_TYPES` 有新增或改名吗？→ 值得吸收
4. 其他修复 → 按需

因为本仓库已重构过架构，**不要用上游文件直接覆盖**，diff 只作参考。

---

## 已知未实现

- **双电池**：上游 marcelwestra 有 `compartmentB` 支持，本仓库只读 `compartmentA`。单电池车型不受影响
- **轨迹缩略图渲染**：`LastTrackThumb` 只提供 URL，没有 `camera.py` 实体

需要的话从上游移植，改动量不大。

---

## 致谢

- [Marcel Westra](https://github.com/marcelwestrahome) 与 [@pikka97](https://github.com/pikka97) — 原始集成
- [@goxofy](https://github.com/goxofy) / [hasscc](https://github.com/hasscc) — 国内服分支与架构重构
