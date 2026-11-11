#!/usr/bin/env python3
"""实时天气 + 当前时间：为遛狗路线规划提供「当下」上下文。

供 recommend_routes.py / agent 调用，也可独立运行：
    python3 weather.py 31.23 121.47        # 指定坐标
    python3 weather.py --city 北京          # 按城市中心
返回：当前温度、天气、风速、是否白天、未来数小时温度，以及「是否适合遛狗」的客观提示。

数据源：open-meteo（免费，无需 key）。
"""
import sys
import os
import json
import math
import datetime
import urllib.request
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
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

# WMO 天气代码 → 中文描述
WMO = {
    0: "晴", 1: "基本晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
}


def _http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def weather_text(code):
    return WMO.get(code, "未知")


def get_weather(lat, lon):
    """返回 {temperature, weatherCode, weatherText, windKmh, isDay, hourly[], error?}。"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m,is_day",
        "hourly": "temperature_2m,weather_code",
        "timezone": "auto",
        "forecast_days": 1,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    try:
        d = _http_json(url, timeout=15)
        cur = d.get("current") or {}
        hourly_time = (d.get("hourly") or {}).get("time") or []
        hourly_temp = (d.get("hourly") or {}).get("temperature_2m") or []
        hourly_code = (d.get("hourly") or {}).get("weather_code") or []
        # 只取当前时刻之后的数小时（未来）
        now = datetime.datetime.now()
        future = []
        for i, t in enumerate(hourly_time):
            try:
                dt = datetime.datetime.fromisoformat(t)
            except Exception:
                continue
            if dt >= now - datetime.timedelta(hours=1):
                future.append({
                    "time": t,
                    "temperature": hourly_temp[i] if i < len(hourly_temp) else None,
                    "weatherText": weather_text(hourly_code[i]) if i < len(hourly_code) else "未知",
                })
            if len(future) >= 6:
                break
        return {
            "temperature": cur.get("temperature_2m"),
            "weatherCode": cur.get("weather_code"),
            "weatherText": weather_text(cur.get("weather_code")),
            "windKmh": cur.get("wind_speed_10m"),
            "isDay": cur.get("is_day"),
            "futureHours": future,
            "timezone": d.get("timezone", ""),
        }
    except Exception as e:
        return {"error": "天气获取失败：" + str(e)}


def main():
    args = sys.argv[1:]
    lat = lon = None
    if len(args) >= 2:
        try:
            lat, lon = float(args[0]), float(args[1])
        except ValueError:
            lat = lon = None
    elif args and args[0] == "--city" and len(args) >= 2 and args[1] in CITY_CENTERS:
        lat, lon = CITY_CENTERS[args[1]]
    if lat is None:
        loc = locate.locate()
        if "error" in loc:
            print(json.dumps({"error": loc["error"]}, ensure_ascii=False))
            return 1
        lat, lon = loc.get("lat"), loc.get("lon")

    w = get_weather(lat, lon)
    if "error" in w:
        print(json.dumps(w, ensure_ascii=False))
        return 1

    # 客观提示（不替 agent 做最终判断，只给事实）
    hints = []
    if w.get("isDay") == 0:
        hints.append("现在是夜间，注意部分公园可能关闭或光线不足")
    if w.get("temperature") is not None and w["temperature"] < 5:
        hints.append("气温偏低，短毛/老年犬注意保暖")
    if w.get("temperature") is not None and w["temperature"] > 30:
        hints.append("气温偏高，注意中暑，建议清晨/傍晚")
    code = w.get("weatherCode")
    if code in (61, 63, 65, 80, 81, 82, 95, 96, 99):
        hints.append("有雨/雷暴，建议改室内或避开")

    out = {
        "now": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "weather": w,
        "hints": hints,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
