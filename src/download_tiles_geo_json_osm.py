import os
import math
import requests
import time
import geopandas as gpd
from shapely.geometry import Point
from concurrent.futures import ThreadPoolExecutor, as_completed

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OUTPUT_DIR = "osm_tiles_korea_by_zoom"
FAILED_LOG = "failed_osm_tiles.txt"
MAX_WORKERS = 4
HEADERS = {
    "User-Agent": "MyTileDownloader/1.0 (tkatlqdbr@nate.com)"
}

# 대한민국 전체 범위
MIN_LAT, MAX_LAT = 33.0, 39.6
MIN_LON, MAX_LON = 124.5, 131.0
ZOOM_MIN, ZOOM_MAX = 5, 17

# ✅ GeoJSON 경로 수정하세요
CITY_GDF = gpd.read_file("D:/oss2map2/oss2map/data/korea_city_boundaries.geojson")

# Geo 판별 함수
def is_in_city(lat, lon):
    point = Point(lon, lat)
    return CITY_GDF.contains(point).any()

def is_land(lat, lon):
    return 33.0 <= lat <= 39.6 and 124.5 <= lon <= 131.5

def is_mountain(lat, lon):
    # 간단한 임시 규칙: 강원도·제주도 위도 경도 범위 내 산악
    return (37.0 <= lat <= 38.8 and 127.5 <= lon <= 129.5) or (33.2 <= lat <= 33.6 and 126.2 <= lon <= 126.7)

def get_max_zoom(lat, lon):
    if is_in_city(lat, lon):
        print("city~~")
        return 17  # 도시
    elif is_mountain(lat, lon):
        print("mountain~~")
        return 14  # 산지
    elif is_land(lat, lon):
        print("nongchon")
        return 14  # 농촌
    else:
        print("sea!!~~~!!")
        return 12  # 바다

# 좌표 변환
def deg2num(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

def num2deg(x, y, zoom):
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

def download_tile(z, x, y):
    url = TILE_URL.format(z=z, x=x, y=y)
    tile_dir = os.path.join(OUTPUT_DIR, str(z), str(x))
    tile_path = os.path.join(tile_dir, f"{y}.png")

    if os.path.exists(tile_path):
        return

    os.makedirs(tile_dir, exist_ok=True)

    try:
        time.sleep(0.01)
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(tile_path, "wb") as f:
                f.write(r.content)
            print(f"[✓] {z}/{x}/{y}")
        else:
            raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        with open(FAILED_LOG, "a") as log:
            log.write(f"{z},{x},{y} - {e}\n")
        print(f"[✗] {z}/{x}/{y} - {e}")

def main():
    for z in range(ZOOM_MIN, ZOOM_MAX + 1):
        x_start, y_start = deg2num(MAX_LAT, MIN_LON, z)
        x_end, y_end = deg2num(MIN_LAT, MAX_LON, z)
        print(f"\n[Zoom {z}] x: {x_start}~{x_end}, y: {y_start}~{y_end}")

        tasks = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for x in range(x_start, x_end + 1):
                for y in range(y_start, y_end + 1):
                    lat, lon = num2deg(x + 0.5, y + 0.5, z)
                    max_zoom = get_max_zoom(lat, lon)
                    if z <= max_zoom:
                        tasks.append(executor.submit(download_tile, z, x, y))

            for future in as_completed(tasks):
                _ = future.result()

if __name__ == "__main__":
    main()
