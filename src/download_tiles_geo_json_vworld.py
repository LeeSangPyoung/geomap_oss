import os
import math
import time
import argparse
import logging
import requests
import geopandas as gpd
from shapely.geometry import Point
from shapely.strtree import STRtree
from concurrent.futures import ThreadPoolExecutor, as_completed

# ✅ 설정
API_KEY = "FB583FE3-F692-3DEB-866F-6FB0E2A69F75"
BASE_URL = f"http://api.vworld.kr/req/wmts/1.0.0/{API_KEY}/Base/{{z}}/{{y}}/{{x}}.png"

OUTPUT_DIR = "vworld_tiles_korea_by_zoom"
FAILED_LOG = "failed_vworld_tiles.txt"
MAX_WORKERS = 10

# ✅ 대한민국 범위
MIN_LAT, MAX_LAT = 33.0, 39.6
MIN_LON, MAX_LON = 124.5, 131.0

# ✅ 요청 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "ko,en;q=0.9,en-US;q=0.8",
    "Connection": "keep-alive",
    "Referer": "http://localhost",
    "Origin": "http://localhost"
}

# ✅ GeoJSON 로드
CITY_GDF = gpd.read_file("../data/korea_city_boundaries.geojson")

# ✅ 위경도 <-> 타일 좌표 변환
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

# ✅ 타일 다운로드 함수
def download_tile(z, x, y):
    url = BASE_URL.format(z=z, x=x, y=y)
    tile_dir = os.path.join(OUTPUT_DIR, str(z), str(x))
    tile_path = os.path.join(tile_dir, f"{y}.png")

    if os.path.exists(tile_path):
        return

    os.makedirs(tile_dir, exist_ok=True)

    try:
        time.sleep(0.1)
        with requests.Session() as session:
            r = session.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and 'image/png' in r.headers.get('Content-Type', ''):
                with open(tile_path, "wb") as f:
                    f.write(r.content)
                print(f"[✓] {z}/{x}/{y}")
            else:
                raise Exception(f"Invalid response - status {r.status_code}")
    except Exception as e:
        with open(FAILED_LOG, "a") as log:
            log.write(f"{z},{x},{y} - {e}\n")
        print(f"[✗] {z}/{x}/{y} - {e}")

# ✅ main 함수
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min_zoom", type=int, default=5, help="최소 줌 레벨")
    parser.add_argument("--max_zoom", type=int, default=13, help="최대 줌 레벨")
    parser.add_argument("--region", nargs="+", required=True, help="지역 이름 리스트")
    args = parser.parse_args()

    zoom_min = args.min_zoom
    zoom_max = args.max_zoom
    region_names = args.region

    selected = CITY_GDF[CITY_GDF["CTP_KOR_NM"].isin(region_names)]
    if selected.empty:
        raise ValueError(f"선택한 지역을 찾을 수 없습니다: {region_names}")
    selected_tree = STRtree(selected.geometry)

    if os.path.exists(FAILED_LOG):
        os.remove(FAILED_LOG)

    for z in range(zoom_min, zoom_max + 1):
        x_start, y_start = deg2num(MAX_LAT, MIN_LON, z)
        x_end, y_end = deg2num(MIN_LAT, MAX_LON, z)
        print(f"\n[Zoom {z}] x: {x_start}~{x_end}, y: {y_start}~{y_end}")
        tasks = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for x in range(x_start, x_end + 1):
                for y in range(y_start, y_end + 1):
                    lat, lon = num2deg(x + 0.5, y + 0.5, z)
                    point = Point(lon, lat)

                    if z == zoom_min:
                        # 전국 전체 다운로드
                        tasks.append(executor.submit(download_tile, z, x, y))
                    else:
                        # 선택 지역만 다운로드
                        if len(selected_tree.query(point)) > 0:
                            tasks.append(executor.submit(download_tile, z, x, y))

            for future in as_completed(tasks):
                _ = future.result()

if __name__ == "__main__":
    main()
