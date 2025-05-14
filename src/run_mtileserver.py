from flask import Flask, send_file, abort
import sqlite3
import os

app = Flask(__name__)
MBTILES_PATH = r"./korea.mbtiles"

def get_tile(z, x, y):
    conn = sqlite3.connect(MBTILES_PATH)
    cursor = conn.cursor()

    # MBTiles는 y축이 뒤집힘
    flipped_y = (2 ** z - 1) - y

    cursor.execute("""
        SELECT tile_data FROM tiles
        WHERE zoom_level=? AND tile_column=? AND tile_row=?
    """, (z, x, flipped_y))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    else:
        return None

@app.route("/tiles/korea/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    tile_data = get_tile(z, x, y)
    if tile_data:
        return tile_data, 200, {'Content-Type': 'image/png'}
    else:
        return abort(404)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
