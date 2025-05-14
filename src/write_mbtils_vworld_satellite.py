import sqlite3, os

def encode_tile(path):
    with open(path, 'rb') as f:
        return f.read()

def init_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE metadata (name TEXT, value TEXT);
    CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);
    CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);
    """)
    metadata = [
        ('name', 'Korea Map'),
        ('format', 'png'),
        ('type', 'baselayer'),
        ('version', '1.0'),
        ('description', 'OSM tiles for Korea'),
        ('minzoom', '5'),
        ('maxzoom', '17'),
        ('bounds', '124.5,33.0,131.0,39.6'),
        ('center', '127.0,36.3,7'),
    ]
    cursor.executemany("INSERT INTO metadata VALUES (?, ?)", metadata)
    conn.commit()
    return conn

def insert_tile(conn, z, x, y, data):
    y_mbtiles = (2 ** z - 1) - y
    conn.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?)", (z, x, y_mbtiles, data))

def walk_tiles(tile_dir, mbtiles_path):
    conn = init_db(mbtiles_path)

    for z in os.listdir(tile_dir):
        if not z.isdigit():
            continue
        for x in os.listdir(os.path.join(tile_dir, z)):
            if not x.isdigit():
                continue
            for y_file in os.listdir(os.path.join(tile_dir, z, x)):
                if not y_file.endswith(".png"):
                    continue
                y = y_file.replace(".png", "")
                full_path = os.path.join(tile_dir, z, x, y_file)
                try:
                    tile_data = encode_tile(full_path)
                    insert_tile(conn, int(z), int(x), int(y), tile_data)
                except Exception as e:
                    print(f"[✗] {z}/{x}/{y} - {e}")

    conn.commit()
    conn.close()
    print(f"[✓] 변환 완료: {mbtiles_path}")

if __name__ == "__main__":
    input_folder = r"/vworld_satellite_korea_by_zoom"
    output_file = r"/vworld_satellite_korea.mbtiles"
    walk_tiles(input_folder, output_file)
