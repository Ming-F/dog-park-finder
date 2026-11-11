#!/usr/bin/env python3
"""定位模块：根据 IP 定位到城市 + 粗坐标，或用 Photon 逆地理把坐标精确到区。

供 query_parks.py 导入，也可独立运行调试：
    python3 locate.py            # IP 定位
    python3 locate.py 39.9087 116.3975   # 逆地理
"""
import sys
import json
import urllib.request
import urllib.parse

IP_API = "http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,lat,lon,query"
PHOTON_REVERSE = "https://photon.komoot.io/reverse"
UA = "dog-park-finder-skill/1.0 (personal use)"

# 英文城市名 → 中文（ip-api 的 regionName 常是英文）
EN_CITY = {
    "Beijing": "北京", "Shanghai": "上海", "Tianjin": "天津", "Chongqing": "重庆",
    "Guangzhou": "广州", "Shenzhen": "深圳", "Chengdu": "成都", "Hangzhou": "杭州",
    "Wuhan": "武汉", "Nanjing": "南京", "Xian": "西安", "Suzhou": "苏州",
    "Changsha": "长沙", "Zhengzhou": "郑州", "Qingdao": "青岛", "Jinan": "济南",
    "Dalian": "大连", "Xiamen": "厦门", "Fuzhou": "福州", "Hefei": "合肥",
}

# 直辖市/主要城市名单（用于判断一个字符串是不是"城市"而非"区"）
MAJOR_CITIES = {"北京", "上海", "天津", "重庆", "广州", "深圳", "成都", "杭州", "武汉",
                "南京", "西安", "苏州", "长沙", "郑州", "青岛", "济南", "大连", "厦门",
                "福州", "合肥", "沈阳", "昆明", "哈尔滨", "长春", "石家庄", "太原",
                "南昌", "南宁", "贵阳", "兰州", "海口", "乌鲁木齐", "呼和浩特", "银川", "西宁", "拉萨"}


def _http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _norm_city(name):
    """把任意城市名归一为不带「市」的中文城市名。区/县名无法判断时原样返回。"""
    if not name:
        return ""
    n = name.strip()
    if n in EN_CITY:
        return EN_CITY[n]
    n = n.replace("市", "").replace("特别行政区", "")
    return n


def locate_by_ip():
    """返回 {city, region, country, lat, lon, source, ip, in_china}；失败返回 {error}。"""
    try:
        d = _http_json(IP_API, timeout=12)
        if d.get("status") != "success":
            return {"error": d.get("message") or "IP 定位失败"}
        region = d.get("regionName") or ""
        city_raw = d.get("city") or ""
        country = d.get("country") or ""
        country_code = d.get("countryCode") or ""
        # 优先用 regionName（城市级），映射英文→中文；否则用 city。
        if region:
            city = _norm_city(region)
        else:
            city = _norm_city(city_raw)
        # 判断是否定位到中国（countryCode==CN 或 country 含"中国/China"）
        in_china = country_code == "CN" or "中国" in country or "China" in country
        return {
            "city": city,
            "region": region,
            "country": country,
            "countryCode": country_code,
            "in_china": in_china,
            "lat": d.get("lat"),
            "lon": d.get("lon"),
            "source": "ip-api.com",
            "ip": d.get("query", "")
        }
    except Exception as e:
        return {"error": "IP 定位不可用：" + str(e)}


def reverse(lat, lon):
    """坐标 → 城市/区。返回 {city, district, region, country, name, error?}。"""
    try:
        url = PHOTON_REVERSE + "?" + urllib.parse.urlencode({"lat": lat, "lon": lon})
        d = _http_json(url, timeout=15)
        features = d.get("features") or []
        if not features:
            return {"error": "逆地理无结果"}
        p = features[0].get("properties", {})
        city_raw = (p.get("city") or "").replace("市", "")
        # Photon 对中国的 city 字段可能是区名（如"普陀区"），真正的城市可能在 state。
        # 若 city 带"区/县"且 state 是城市，则用 state 作城市、city 作区。
        district = p.get("district") or ""
        state = (p.get("state") or "").replace("市", "")
        if state and state in MAJOR_CITIES:
            city = state
            district = district or city_raw
        else:
            city = city_raw
        return {
            "city": city,
            "district": district,
            "region": state or "",
            "country": p.get("country") or "",
            "name": p.get("name") or ""
        }
    except Exception as e:
        return {"error": "逆地理不可用：" + str(e)}


def locate():
    """综合定位：IP 定位拿城市，再用 Photon 逆地理补充区。返回统一结构。"""
    result = locate_by_ip()
    if "error" in result:
        return result
    # 逆地理只用于补充「区」，不覆盖 IP 定位得到的城市（IP 的城市级更可信）。
    if result.get("lat") is not None and result.get("lon") is not None:
        rev = reverse(result["lat"], result["lon"])
        if "error" not in rev:
            if rev.get("district"):
                result["district"] = rev["district"]
            # 仅当 IP 定位没拿到城市、且逆地理拿到了有效城市时才补
            if not result.get("city") and rev.get("city"):
                result["city"] = rev["city"]
    return result


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        print(json.dumps(reverse(float(sys.argv[1]), float(sys.argv[2])), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(locate(), ensure_ascii=False, indent=2))
