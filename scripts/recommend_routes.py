#!/usr/bin/env python3
"""遛狗路线推荐：根据位置预先推荐 3 条最佳路线；用户选择后可继续推荐新路线。

用法：
    python3 recommend_routes.py                     # 自动 IP 定位，推荐 3 条最佳路线
    python3 recommend_routes.py --city 北京          # 指定城市
    python3 recommend_routes.py --place "朝阳区"     # 指定位置
    python3 recommend_routes.py --park place_bj_laoshan   # 只看某个公园的路线
    python3 recommend_routes.py --exclude route_hcw_1      # 排除已选路线（选后再推荐）
    python3 recommend_routes.py --limit 3 --json

逻辑：优先推荐「距离近 + 有已核实路线」的公园；每个公园按路线长度/适用犬型给多条。
用户选了某条路线或某个公园后，排除已选，从其余路线里继续推荐。
"""
import sys
import os
import json
import math
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data", "places.json")
sys.path.insert(0, HERE)

import locate  # noqa: E402

CITY_CENTERS = {
    "北京": (39.9087, 116.3975), "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
    "成都": (30.5728, 104.0668), "杭州": (30.2741, 120.1551),
    "武汉": (30.5928, 114.3055), "重庆": (29.5630, 106.5516),
    "南京": (32.0603, 118.7969), "西安": (34.3416, 108.9398),
    "天津": (39.3434, 117.3616), "苏州": (31.2989, 120.5853),
    "长沙": (28.2282, 112.9388),
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def load_places():
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)["places"]


def resolve_location(args):
    """返回 (lat, lon, label, method)。"""
    if args.place:
        from query_parks import geocode  # 复用地理编码
        g = geocode(args.place)
        if "error" in g:
            return None, None, None, g["error"]
        return g["lat"], g["lon"], g["label"], "地名定位（" + g["label"] + "）"
    if args.lat is not None and args.lon is not None:
        return args.lat, args.lon, f"{args.lat},{args.lon}", "用户坐标"
    if args.city and args.city in CITY_CENTERS:
        lat, lon = CITY_CENTERS[args.city]
        return lat, lon, args.city, f"按 {args.city} 城市中心"
    loc = locate.locate()
    if "error" in loc:
        lat, lon = CITY_CENTERS["北京"]
        return lat, lon, "北京", "定位失败，回退北京中心"
    if loc.get("in_china") is False:
        return None, None, None, "未定位到国内城市（当前网络出口可能在海外），请告诉我你所在的城市"
    return loc.get("lat"), loc.get("lon"), loc.get("city") or "未知", \
        f"IP 定位（{loc.get('city')}/{loc.get('district') or '—'}，来源 {loc.get('source')}）"


def build_route(park, route, dist_km):
    """把一条路线 + 所属公园信息打包成统一结构。"""
    return {
        "routeId": route.get("id", ""),
        "routeName": route.get("name", ""),
        "parkId": park.get("id", ""),
        "parkName": park.get("name", ""),
        "city": park.get("city", ""),
        "district": park.get("district", ""),
        "dist_km": round(dist_km, 2),
        "distanceM": route.get("distanceM", 0),
        "distanceText": f"{round(route.get('distanceM', 0) / 1000, 1)} 公里",
        "durationMin": route.get("durationMin", 0),
        "surface": route.get("surface", ""),
        "level": route.get("level", ""),
        "start": route.get("start", ""),
        "via": route.get("via", ""),
        "end": route.get("end", ""),
        "tips": route.get("tips", ""),
        "ruleLevel": park.get("ruleLevel", ""),
        "openTime": park.get("openTime", ""),
    }


def main():
    ap = argparse.ArgumentParser(description="遛狗路线推荐")
    ap.add_argument("--city")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--place")
    ap.add_argument("--park", help="只看某个公园（placeId）")
    ap.add_argument("--exclude", action="append", default=[], help="排除的路线 routeId（可多次）")
    ap.add_argument("--limit", type=int, default=3, help="推荐条数（默认 3）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    places = load_places()
    lat, lon, label, method = resolve_location(args)
    if lat is None:
        print(json.dumps({"error": method}, ensure_ascii=False) if args.json else method)
        return 1

    # 收集所有「有路线」的公园，按距离排序
    park_rows = []
    for p in places:
        if not p.get("routes"):
            continue
        if args.park and p.get("id") != args.park:
            continue
        d = haversine_km(lat, lon, p.get("latitude", lat), p.get("longitude", lon))
        park_rows.append((d, p))
    park_rows.sort(key=lambda x: x[0])

    # 展开成单条路线，排除已选
    excluded = set(args.exclude)
    routes = []
    for d, p in park_rows:
        for r in p["routes"]:
            if r.get("id") in excluded:
                continue
            routes.append(build_route(p, r, d))

    # 默认按「距离近优先」，同公园内多条路线保持顺序
    routes.sort(key=lambda x: x["dist_km"])
    selected = routes[: args.limit]

    out = {
        "query": {"location": label, "method": method, "lat": round(lat, 6), "lon": round(lon, 6)},
        "count": len(selected),
        "totalAvailable": len(routes),
        "routes": selected,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    print(f"📍 查询位置：{method}")
    if not selected:
        print("附近暂无已核实的遛狗路线。可尝试 --city 指定城市，或配置地图 key 后启用全国搜索。")
        return 0
    print(f"为你推荐 {len(selected)} 条遛狗路线：\n")
    for i, r in enumerate(selected, 1):
        print(f"{i}. {r['routeName']}（{r['parkName']}，{r['dist_km']} 公里）")
        print(f"   路线：{r['start']} → {r['via']} → {r['end']}")
        print(f"   长度 {r['distanceText']} · 约 {r['durationMin']} 分钟 · {r['surface']} · {r['level']}")
        if r["tips"]:
            print(f"   贴士：{r['tips']}")
        print(f"   规则：{r['ruleLevel'] or '待确认'}｜开放：{r['openTime'] or '未知'}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
