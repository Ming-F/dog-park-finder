#!/usr/bin/env python3
"""宠物友好公园查询：定位 → 周边搜索公园 → 叠加本地已核实规则 → 判定能否遛狗。

数据源（按优先级降级）：
  1. 地图服务 key（高德/腾讯）周边搜索 → 稳定返回周边公园（名称/地址/坐标）
  2. 本地 data/places.json（京沪 38 处已核实）→ 命中时叠加详细遛狗规则
  3. IP 定位（ip-api.com）+ 逆地理（Photon）→ 拿到城市/区
  4. 无 key 降级 → 仅用本地数据 + 城市中心

用法（agent 主要用 --json）：
    python3 query_parks.py                     # 自动 IP 定位 + 周边搜索
    python3 query_parks.py --city 上海          # 指定城市
    python3 query_parks.py --lat 39.9 --lon 116.4
    python3 query_parks.py --place "朝阳区"      # 地名转坐标
    python3 query_parks.py --rule 需登记 --limit 5
    python3 query_parks.py --category 郊野公园
    python3 query_parks.py --json

地图 key 配置：优先读环境变量 AMAP_KEY / TENCENT_MAP_KEY，
其次读 skill 根目录 config.json 的 {"amapKey": "...", "tencentKey": "..."}。
两家都配置时默认用高德；可用 --provider amap|tencent 指定。

合规红线：绝不编造规则；未核实的公园一律标注「规则以园方现场公示为准」。
"""
import sys
import os
import json
import math
import argparse
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data", "places.json")
CONFIG = os.path.join(ROOT, "config.json")
sys.path.insert(0, HERE)

import locate  # noqa: E402

UA = "dog-park-finder-skill/1.0 (personal use)"

CITY_CENTERS = {
    "北京": (39.9087, 116.3975), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668), "杭州": (30.2741, 120.1551),
    "武汉": (30.5928, 114.3055), "重庆": (29.5630, 106.5516),
    "南京": (32.0603, 118.7969), "西安": (34.3416, 108.9398),
    "天津": (39.3434, 117.3616), "苏州": (31.2989, 120.5853),
    "长沙": (28.2282, 112.9388),
}

RADIUS_KM = 8.0
PARK_KEYWORD = "公园"

# 城市 → 养犬/公园政策提示（与 references/policy.md 一致，标注日期）
CITY_POLICY = {
    "北京": "北京市公园条例修订草案（2025-11 二审）拟规定：禁止烈性犬、大型犬进入任何公园，禁止携犬进入历史名园；其他公园由管理单位决定是否允许携犬及允许进入的区域、时段。",
    "上海": "上海实行养犬登记制度（《上海市养犬管理条例》），需办犬证+免疫；部分公园/绿地设宠物友好试点，规则以现场公示为准。",
}
DEFAULT_POLICY = "各地养犬政策差异较大，规则以当地养犬管理条例与园方现场公示为准；烈性犬、大型犬在多数城市核心区/公园受限。"


def _pick_policy(city):
    """按城市匹配政策提示，未收录城市给通用提示。"""
    if not city:
        return DEFAULT_POLICY
    for k, v in CITY_POLICY.items():
        if k in city:
            return v
    return DEFAULT_POLICY


def _http_json(url, timeout=15, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_config():
    """读取地图 key：环境变量优先，其次 config.json。"""
    cfg = {"amap": "", "tencent": ""}
    cfg["amap"] = os.environ.get("AMAP_KEY", "")
    cfg["tencent"] = os.environ.get("TENCENT_MAP_KEY", "")
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                j = json.load(f)
            cfg["amap"] = cfg["amap"] or j.get("amapKey", "")
            cfg["tencent"] = cfg["tencent"] or j.get("tencentKey", "")
        except Exception:
            pass
    return cfg


def load_local():
    if not os.path.exists(DATA):
        return {"places": [], "policyNote": ""}
    with open(DATA, "r", encoding="utf-8") as f:
        d = json.load(f)
    return {"places": d.get("places", []), "policyNote": d.get("policyNote", "")}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def geocode(query):
    """地名/区名 → 坐标。先本地城市表，再 Photon。"""
    for name, (la, lo) in CITY_CENTERS.items():
        if name in query:
            return {"lat": la, "lon": lo, "label": name + "（城市中心）", "approx": True}
    try:
        url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": query, "limit": 1})
        d = _http_json(url, timeout=15)
        feats = d.get("features") or []
        if not feats:
            return {"error": "找不到地点：" + query}
        p = feats[0]["properties"]
        c = feats[0]["geometry"]["coordinates"]
        city = (p.get("city") or "").replace("市", "")
        district = p.get("district") or ""
        label = "、".join(x for x in [p.get("name"), district, city] if x)
        return {"lat": c[1], "lon": c[0], "label": label, "approx": False}
    except Exception as e:
        return {"error": "地理编码不可用：" + str(e)}


# ---------------- 周边搜索：高德 / 腾讯 ----------------

def _search_amap(key, lat, lon, radius, limit):
    """高德周边搜索（POI 关键词=公园，类型=风景名胜/公园广场）。返回公园列表。"""
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": key,
        "location": f"{lon},{lat}",
        "keywords": PARK_KEYWORD,
        "radius": int(radius * 1000),
        "sortrule": "distance",
        "offset": min(limit, 25),
        "page": 1,
        "extensions": "base",
    }
    d = _http_json(url + "?" + urllib.parse.urlencode(params), timeout=15)
    if d.get("status") != "1":
        return {"error": "高德搜索失败：" + (d.get("info") or "未知")}
    pois = d.get("pois") or []
    out = []
    for p in pois:
        loc = (p.get("location") or "").split(",")
        if len(loc) != 2:
            continue
        lon2, lat2 = float(loc[0]), float(loc[1])
        out.append({
            "name": p.get("name", ""),
            "lat": lat2, "lon": lon2,
            "city": "", "district": "",
            "address": (p.get("address") or ""),
            "type": (p.get("type") or ""),
            "dist_km": round(haversine_km(lat, lon, lat2, lon2), 2),
        })
    out.sort(key=lambda x: x["dist_km"])
    return out


def _search_tencent(key, lat, lon, radius, limit):
    """腾讯位置服务周边搜索。返回公园列表。"""
    url = "https://apis.map.qq.com/ws/place/v1/search"
    params = {
        "key": key,
        "keyword": PARK_KEYWORD,
        "boundary": f"nearby({lat},{lon},{int(radius * 1000)})",
        "orderby": "_distance",
        "page_size": min(limit, 20),
        "page_index": 1,
    }
    d = _http_json(url + "?" + urllib.parse.urlencode(params), timeout=15)
    if d.get("status") != 0:
        return {"error": "腾讯搜索失败：" + (d.get("message") or "未知")}
    out = []
    for p in d.get("data") or []:
        loc = p.get("location") or {}
        lat2, lon2 = loc.get("lat"), loc.get("lng")
        if lat2 is None or lon2 is None:
            continue
        out.append({
            "name": p.get("title", ""),
            "lat": lat2, "lon": lon2,
            "city": "", "district": "",
            "address": (p.get("address") or ""),
            "type": (p.get("category") or ""),
            "dist_km": round(haversine_km(lat, lon, lat2, lon2), 2),
        })
    out.sort(key=lambda x: x["dist_km"])
    return out


def search_parks(cfg, lat, lon, radius, limit, provider=None):
    """按可用 key 顺序尝试周边搜索。返回公园列表或 {error}。"""
    if provider == "amap" or (not provider and cfg.get("amap")):
        if cfg.get("amap"):
            r = _search_amap(cfg["amap"], lat, lon, radius, limit)
            if "error" not in r:
                return r
            last_err = r["error"]
    if provider == "tencent" or (not provider and cfg.get("tencent")):
        if cfg.get("tencent"):
            r = _search_tencent(cfg["tencent"], lat, lon, radius, limit)
            if "error" not in r:
                return r
            last_err = r["error"]
    return {"error": last_err if "last_err" in dir() else "未配置地图 key"}


def classify_rule(rule_level):
    table = {
        "禁止携犬": {"can": False, "verdict": "不能遛狗",
                     "reason": "该公园明确禁止携犬进入。", "advice": "建议改去附近其他宠物友好公园。"},
        "需登记": {"can": True, "verdict": "可遛狗（需登记）",
                   "reason": "可携犬入园，但需出示养犬登记证、有效期内疫苗证明，并可能签写入园免责声明。",
                   "advice": "出门前带齐登记证与疫苗证明。"},
        "需牵绳": {"can": True, "verdict": "可遛狗（需牵绳）",
                   "reason": "宠物友好，需全程牵绳、随身清理粪便、不影响他人。",
                   "advice": "带牵引绳与拾便袋。"},
        "限体型": {"can": True, "verdict": "可遛狗（限小型犬）",
                   "reason": "仅限体重不超标的宠物进入限定区域。",
                   "advice": "确认自家宠物体型是否符合，并看清限定区域范围。"},
        "分区管理": {"can": True, "verdict": "可遛狗（分区）",
                     "reason": "宠物友好，按犬只体型分区，大小犬互不打扰。",
                     "advice": "按自家宠物体型进入对应分区。"},
        "封闭乐园": {"can": True, "verdict": "可遛狗（封闭乐园）",
                     "reason": "为封闭式宠物乐园，设施友好，可在指定范围内活动。",
                     "advice": "遵循乐园内的设施与文明提示。"},
        "柔性管理": {"can": True, "verdict": "可遛狗（柔性管理）",
                     "reason": "宠物友好试点，由工作人员引导，在游客较少的时段开放特定草坪。",
                     "advice": "留意现场引导与开放时段，错峰前往。"},
    }
    return table.get(rule_level, {"can": True, "verdict": "规则待确认",
                                  "reason": "暂无该公园的核实遛狗规则。",
                                  "advice": "以园方现场公示为准，一般要求牵绳并清理粪便。"})


def build_result(place, dist_km, verified, extra=None):
    extra = extra or {}
    rule = classify_rule(place.get("ruleLevel", ""))
    return {
        "name": place.get("name", extra.get("name", "")),
        "city": place.get("city", ""),
        "district": place.get("district", ""),
        "category": place.get("category", ""),
        "address": place.get("address", extra.get("address", "")),
        "openTime": place.get("openTime", ""),
        "ruleLevel": place.get("ruleLevel", ""),
        "rules": place.get("rules", ""),
        "tips": place.get("tips", ""),
        "source": place.get("source", ""),
        "verified": verified,           # 是否本地已核实数据命中（vs 实时搜索未知）
        "official": bool(place.get("official", False)),  # 是否官方核实（vs 媒体整理）
        "dist_km": round(dist_km, 2),
        "can": rule["can"],
        "verdict": rule["verdict"],
        "reason": rule["reason"],
        "advice": rule["advice"],
    }


def _match_local(places, name):
    for p in places:
        if p.get("name") == name or p.get("shortName") == name or name.startswith(p.get("shortName", "")) or (p.get("shortName") and p.get("shortName") in name):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description="宠物友好公园查询")
    ap.add_argument("--city")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--place")
    ap.add_argument("--rule")
    ap.add_argument("--category")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--radius", type=float, default=RADIUS_KM)
    ap.add_argument("--provider", choices=["amap", "tencent"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    local = load_local()
    local_places = local["places"]

    # 1. 确定位置
    lat, lon, loc_label, loc_method = args.lat, args.lon, "", ""
    if args.place:
        g = geocode(args.place)
        if "error" in g:
            print(json.dumps({"error": g["error"]}, ensure_ascii=False) if args.json else g["error"])
            return 1
        lat, lon, loc_label, loc_method = g["lat"], g["lon"], g["label"], "地名定位（" + g["label"] + "）"
    elif args.lat is not None and args.lon is not None:
        loc_label, loc_method = f"{args.lat},{args.lon}", "用户坐标"
    elif args.city and args.city in CITY_CENTERS:
        lat, lon = CITY_CENTERS[args.city]
        loc_label, loc_method = args.city, f"按 {args.city} 城市中心"
    else:
        loc = locate.locate()
        if "error" in loc:
            lat, lon = CITY_CENTERS["北京"]
            loc_label, loc_method = "北京", "定位失败，回退北京中心"
        elif loc.get("in_china") is False:
            # 定位到国外（常见：走了代理/海外节点），不硬塞国内公园结果，明确提示。
            out = {
                "error": "未定位到国内城市（当前网络出口可能在海外：" + (loc.get("country") or "未知") + "）。",
                "hint": "请告诉我你所在的城市，例如「帮我查上海的」「我在朝阳区」，或直接用 --city / --place 指定。",
                "detail": {"ipCountry": loc.get("country"), "ipCity": loc.get("city")},
            }
            print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else (out["error"] + "\n" + out["hint"]))
            return 1
        else:
            lat, lon = loc.get("lat"), loc.get("lon")
            loc_label = loc.get("city") or "未知"
            loc_method = f"IP 定位（{loc.get('city')}/{loc.get('district') or '—'}，来源 {loc.get('source')}）"
        if args.city and args.city in CITY_CENTERS:
            lat, lon = CITY_CENTERS[args.city]
            loc_label, loc_method = args.city, f"按 {args.city} 城市中心"

    # 按城市匹配政策提示
    policy_note = _pick_policy(loc_label)

    # 2. 周边搜索
    parks = search_parks(cfg, lat, lon, args.radius, max(args.limit * 3, 20), provider=args.provider)
    search_err = None
    if isinstance(parks, dict) and "error" in parks:
        search_err = parks["error"]
        parks = []

    # 3. 合并本地已核实数据
    results, seen = [], set()
    for pk in parks:
        name = pk["name"]
        if not name or name in seen:
            continue
        seen.add(name)
        matched = _match_local(local_places, name)
        if matched:
            place = dict(matched)
            place["latitude"], place["longitude"] = pk["lat"], pk["lon"]
            results.append(build_result(place, pk["dist_km"], True, extra=pk))
        else:
            results.append(build_result({}, pk["dist_km"], False, extra=pk))

    # 4. 无 key 或搜索失败：用本地数据兜底（按坐标距离排序取最近，不依赖城市名字符串）
    if not results or search_err:
        # 计算本地所有公园到查询点的距离
        cand = []
        for p in local_places:
            d = haversine_km(lat, lon, p.get("latitude", lat), p.get("longitude", lon))
            cand.append((d, p))
        cand.sort(key=lambda x: x[0])
        # 用户明确指定城市时，优先该城市；否则取距离最近的（跨城市也按距离排，前 limit 个）
        if args.city:
            city = args.city
            cand = [x for x in cand if x[1].get("city") == city] + [x for x in cand if x[1].get("city") != city]
        for d, p in cand:
            results.append(build_result(p, d, True))

    # 5. 筛选
    if args.rule:
        results = [r for r in results if r["ruleLevel"] == args.rule]
    if args.category:
        results = [r for r in results if r["category"] == args.category]

    # 去重（同名保留 verified）
    dedup = {}
    for r in results:
        key = r["name"]
        if key not in dedup or (r["verified"] and not dedup[key]["verified"]):
            dedup[key] = r
    results = sorted(dedup.values(), key=lambda x: x["dist_km"])[: args.limit]

    # 6. 输出
    output = {
        "query": {"location": loc_label, "method": loc_method,
                  "lat": round(lat, 6), "lon": round(lon, 6), "radius_km": args.radius},
        "provider": "amap" if cfg.get("amap") and (args.provider != "tencent") else ("tencent" if cfg.get("tencent") else "local"),
        "searchWarning": search_err,
        "policyNote": policy_note,
        "count": len(results),
        "parks": results,
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    print(f"📍 查询位置：{loc_method}")
    if search_err:
        print(f"⚠️ 周边实时搜索不可用（{search_err}），以下为本地已核实公园。")
    if policy_note:
        print(f"⚠️ 政策提示：{policy_note}\n")
    if not results:
        print("未找到公园。可尝试 --city 指定城市，或配置地图 key 以启用周边搜索。")
        return 0
    for r in results:
        flag = "✅" if r["verified"] else "🔍"
        can = "✓ 可遛狗" if r["can"] else "✗ 不能遛狗"
        print(f"{flag} {r['name']}（{r['dist_km']} 公里）{can}")
        if r["ruleLevel"]:
            print(f"   限制：{r['ruleLevel']}｜开放：{r['openTime'] or '未知'}")
            print(f"   规则：{r['rules']}")
            if r["source"]:
                print(f"   来源：{r['source']}（{'官方核实' if r['official'] else '媒体整理'}）")
        else:
            print(f"   规则：{r['reason']}")
            if r["address"]:
                print(f"   地址：{r['address']}")
        if r["tips"]:
            print(f"   贴士：{r['tips']}")
        if not r["verified"] and not r["ruleLevel"]:
            print("   ⚠️ 未经核实，规则以园方现场公示为准。")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
