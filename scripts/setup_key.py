#!/usr/bin/env python3
"""key 配置助手：校验并写入地图服务 key，测试周边搜索是否可用。

用法：
    python3 setup_key.py guide                   # 输出「点一下就到位」的申请直达链接
    python3 setup_key.py amap <你的高德key>      # 配置高德
    python3 setup_key.py tencent <你的腾讯key>   # 配置腾讯
    python3 setup_key.py test                    # 测试已配置的 key
    python3 setup_key.py status                  # 查看当前配置状态
"""
import sys
import os
import json
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CONFIG = os.path.join(ROOT, "config.json")
UA = "dog-park-finder-skill/1.0 (personal use)"


def _http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_cfg():
    if os.path.exists(CONFIG):
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cfg(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("已写入配置：" + CONFIG)


def test_amap(key):
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {"key": key, "address": "北京天安门", "city": "北京"}
    d = _http_json(url + "?" + urllib.parse.urlencode(params), timeout=15)
    if d.get("status") == "1":
        return True, "高德 key 有效（地理编码接口可用）"
    return False, "高德 key 无效或未开通 Web 服务：" + (d.get("info") or "未知错误")


def test_tencent(key):
    url = "https://apis.map.qq.com/ws/geocoder/v1/"
    params = {"key": key, "address": "北京天安门"}
    d = _http_json(url + "?" + urllib.parse.urlencode(params), timeout=15)
    if d.get("status") == 0:
        return True, "腾讯 key 有效（地理编码接口可用）"
    return False, "腾讯 key 无效或未开通 WebService：" + (d.get("message") or "未知错误")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("status",):
        cfg = load_cfg()
        amap = cfg.get("amapKey", "")
        tencent = cfg.get("tencentKey", "")
        print("当前配置状态：")
        print("  高德 amapKey：  " + ("已配置（" + amap[:6] + "…）" if amap else "未配置"))
        print("  腾讯 tencentKey：" + ("已配置（" + tencent[:6] + "…）" if tencent else "未配置"))
        if not amap and not tencent:
            print("\n尚无 key。申请入口：")
            print("  高德：https://lbs.amap.com/dev/#/  → 控制台 → 应用管理 → 创建应用 → 添加「Web服务」key")
            print("  腾讯：https://lbs.qq.com/  → 控制台 → 应用管理 → 创建应用 → 添加 key（勾选 WebService API）")
            print("\n拿到 key 后运行：python3 setup_key.py amap <key> 或 python3 setup_key.py tencent <key>")
        return 0

    if args[0] == "test":
        cfg = load_cfg()
        ok = False
        if cfg.get("amapKey"):
            good, msg = test_amap(cfg["amapKey"])
            print(msg)
            ok = ok or good
        if cfg.get("tencentKey"):
            good, msg = test_tencent(cfg["tencentKey"])
            print(msg)
            ok = ok or good
        if not ok:
            print("未发现可用 key。")
            return 1
        return 0

    if args[0] == "guide":
        print("申请地图 key 只需两步（推荐高德，免费）：")
        print("")
        print("【高德】点这个直达链接（打开后登录 → 实名认证 → 创建应用 → 添加 Key，服务平台选「Web服务」）：")
        print("  https://lbs.amap.com/dev/#/")
        print("")
        print("【腾讯】备选直达链接（登录认证 → 创建应用 → 添加 key，勾选 WebService API）：")
        print("  https://lbs.qq.com/dev/console/home")
        print("")
        print("拿到 key 后，直接把 key 粘贴给我（或运行下面命令），我帮你校验并配好：")
        print("  python3 setup_key.py amap <key>    # 或 tencent <key>")
        return 0

    if args[0] in ("amap", "tencent") and len(args) >= 2:
        key = args[1].strip()
        provider = args[0]
        if provider == "amap":
            good, msg = test_amap(key)
        else:
            good, msg = test_tencent(key)
        print(msg)
        if not good:
            print("\n请确认：")
            print("  1) key 是否复制完整（无多余空格）；")
            print("  2) 应用类型是否选择了「Web服务」/「WebService API」；")
            print("  3) key 是否已启用（有些平台需手动启用）。")
            return 1
        cfg = load_cfg()
        if provider == "amap":
            cfg["amapKey"] = key
        else:
            cfg["tencentKey"] = key
        save_cfg(cfg)
        print("配置成功！现在运行 query_parks.py 即可用周边搜索。")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
