from flask import Flask, Response, abort
import sqlite3
import argparse
import os

# ✅ argparse로 포트와 파일 경로 받기
parser = argparse.ArgumentParser()
parser.add_argument('--map_port', type=int, default=8091, help='Port to run the server on')
parser.add_argument('--mbtiles', type=str, default="./vworld_korea.mbtiles", help='Path to MBTiles file')
args = parser.parse_args()

app = Flask(__name__)
MBTILES_PATH = args.mbtiles

# ✅ 타일 데이터 조회
def get_tile(z, x, y):
    conn = sqlite3.connect(MBTILES_PATH)
    cursor = conn.cursor()
    flipped_y = (2 ** z - 1) - y  # MBTiles Y축 반전
    cursor.execute("""
        SELECT tile_data FROM tiles
        WHERE zoom_level=? AND tile_column=? AND tile_row=?
    """, (z, x, flipped_y))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# ✅ 타일 요청 라우팅
@app.route("/tiles/vworld_korea/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    tile_data = get_tile(z, x, y)
    if tile_data:
        return Response(tile_data, mimetype='image/png')
    else:
        return abort(404)

# ✅ 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=args.map_port)
