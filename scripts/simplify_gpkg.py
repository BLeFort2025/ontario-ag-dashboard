import geopandas as gpd

# 1) Read original GPKG
gdf = gpd.read_file("../data/Ontario_Census_Divisions_simp.gpkg")

# 2) Ensure WGS84
if gdf.crs is None or gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

# 3) Simplify geometries (tolerance = 0.05 for max speed)
gdf["geometry"] = gdf.geometry.simplify(tolerance=0.05, preserve_topology=True)

# 4) Keep only the columns your app uses
gdf = gdf[["Municipality_Clean", "geometry"]]

# 5) Export to GeoJSON
gdf.to_file("../data/divisions_simp.geojson", driver="GeoJSON")
print("✅ Wrote simplified GeoJSON to data/divisions_simp.geojson")
