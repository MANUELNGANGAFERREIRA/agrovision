"""Backend geoespacial do AgroVision Angola.
Calcula NDVI a partir de bandas científicas Sentinel-2 L2A (Planetary Computer).
"""
from __future__ import annotations
import base64, io, math, os
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import requests
import rasterio
from rasterio.mask import mask
from rasterio.warp import transform_geom, reproject, Resampling
from rasterio.io import MemoryFile
from rasterio.features import geometry_mask
from shapely.geometry import shape, mapping
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
app = FastAPI(title="AgroVision Angola API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class AnalysisRequest(BaseModel):
    field_id: str = ""
    field_name: str = "Talhão"
    polygon: dict[str, Any]
    date: date
    cloud_max: float = Field(default=35, ge=0, le=100)

class CompareRequest(BaseModel):
    field_id: str = ""
    field_name: str = "Talhão"
    polygon: dict[str, Any]
    date_before: date
    date_after: date
    cloud_max: float = Field(default=35, ge=0, le=100)

class DataUnavailable(Exception): pass

def _validate_polygon(geojson: dict):
    try:
        geom = shape(geojson)
        if geom.geom_type != "Polygon" or geom.is_empty or not geom.is_valid or geom.area <= 0:
            raise ValueError("Polígono inválido.")
        minx, miny, maxx, maxy = geom.bounds
        if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
            raise ValueError("Coordenadas fora dos limites geográficos.")
        return geom
    except Exception as exc:
        raise ValueError(f"Limites geográficos inválidos: {exc}")

def _search_item(poly, target_date: date, cloud_max: float):
    # Janela temporal centrada na data pedida. O resultado real informa a data capturada.
    start = target_date - timedelta(days=15)
    end = target_date + timedelta(days=15)
    payload = {
        "collections": ["sentinel-2-l2a"],
        "intersects": mapping(poly),
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": 30,
        "query": {"eo:cloud_cover": {"lte": cloud_max}},
    }
    try:
        response = requests.post(STAC, json=payload, timeout=45)
        response.raise_for_status()
        features = response.json().get("features", [])
    except requests.RequestException as exc:
        raise DataUnavailable(f"Não foi possível consultar o catálogo Sentinel-2: {exc}")
    if not features:
        raise DataUnavailable("Não foi encontrada imagem Sentinel-2 no intervalo de ±15 dias com o limite de nuvens escolhido.")
    # Preferir menor distância temporal e, em empate, menor cobertura de nuvens.
    def rank(item):
        dt = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00")).date()
        return (abs((dt-target_date).days), float(item["properties"].get("eo:cloud_cover", 100)))
    return min(features, key=rank)

def _signed_href(href: str) -> str:
    try:
        r = requests.get(SIGN, params={"href": href}, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("href") or href
    except requests.RequestException as exc:
        raise DataUnavailable(f"Não foi possível obter acesso temporário ao raster: {exc}")

def _asset(item, *keys):
    for key in keys:
        if key in item.get("assets", {}):
            return item["assets"][key]["href"]
    raise DataUnavailable("A imagem encontrada não contém as bandas necessárias (B04, B08 e SCL).")

def _band_scale_offset(item, key):
    metadata = item.get("assets", {}).get(key, {}).get("raster:bands", [{}])
    band = metadata[0] if metadata else {}
    return float(band.get("scale", 1.0)), float(band.get("offset", 0.0))

def _read_masked(href: str, geom_geojson: dict, out_shape=None, reference=None, categorical=False):
    signed = _signed_href(href)
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="2", GDAL_HTTP_TIMEOUT="45"):
            with rasterio.open(signed) as src:
                geom = transform_geom("EPSG:4326", src.crs, geom_geojson)
                if reference is None:
                    arr, transform = mask(src, [geom], crop=True, filled=False, all_touched=False)
                    return arr[0], transform, src.crs, src.res
                # SCL é reamostrada para a grelha de 10 m do B04.
                dst = np.zeros(out_shape, dtype=np.uint8)
                reproject(source=rasterio.band(src, 1), destination=dst,
                          src_transform=src.transform, src_crs=src.crs,
                          dst_transform=reference["transform"], dst_crs=reference["crs"],
                          resampling=Resampling.nearest)
                return dst
    except DataUnavailable:
        raise
    except Exception as exc:
        raise DataUnavailable(f"Falha ao ler o raster científico: {exc}")

def _png_overlay(ndvi, valid, transform, crs):
    # Pré-visualização transparente, classificada a partir dos valores NDVI calculados.
    rgba = np.zeros((ndvi.shape[0], ndvi.shape[1], 4), dtype=np.uint8)
    bands = [(-1.0, 0.0, (155, 105, 65)), (0.0, 0.2, (205, 180, 90)),
             (0.2, 0.4, (220, 205, 90)), (0.4, 0.6, (135, 185, 90)),
             (0.6, 0.8, (65, 150, 75)), (0.8, 1.01, (20, 105, 55))]
    for lo, hi, color in bands:
        m = valid & (ndvi >= lo) & (ndvi < hi)
        rgba[m, :3] = color
        rgba[m, 3] = 205
    image = Image.fromarray(rgba, "RGBA")
    buff = io.BytesIO(); image.save(buff, format="PNG")
    # B04/Sentinel-2 em UTM: obter bounds geográficos a partir da transformação.
    from rasterio.warp import transform_bounds
    h, w = ndvi.shape
    left, bottom, right, top = rasterio.transform.array_bounds(h, w, transform)
    bounds = transform_bounds(crs, "EPSG:4326", left, bottom, right, top, densify_pts=21)
    return base64.b64encode(buff.getvalue()).decode("ascii"), list(bounds)

def calculate_ndvi_statistics(red_data: np.ndarray, nir_data: np.ndarray, quality: np.ndarray):
    """NDVI pixel-by-pixel and zonal statistics; quality=False excludes invalid/cloud pixels."""
    red_data = np.asarray(red_data, dtype=np.float32)
    nir_data = np.asarray(nir_data, dtype=np.float32)
    quality = np.asarray(quality, dtype=bool)
    denom = nir_data + red_data
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir_data - red_data) / denom
    valid = quality & np.isfinite(ndvi) & np.isfinite(red_data) & np.isfinite(nir_data) & (denom > 0) & (ndvi >= -1) & (ndvi <= 1)
    if not np.any(valid):
        raise ValueError("Não existem píxeis válidos para calcular estatísticas.")
    vals = ndvi[valid]
    classes = {
        "sem_vegetacao_ou_agua": int(np.sum(valid & (ndvi < 0.0))),
        "vegetacao_baixa": int(np.sum(valid & (ndvi >= 0.0) & (ndvi < 0.2))),
        "vegetacao_moderada": int(np.sum(valid & (ndvi >= 0.2) & (ndvi < 0.5))),
        "vegetacao_densa": int(np.sum(valid & (ndvi >= 0.5)))
    }
    return ndvi, valid, {"mean": float(np.mean(vals)), "min": float(np.min(vals)), "max": float(np.max(vals)), "count": int(valid.sum()), "classes": classes}

def analyze_polygon(geojson: dict, target_date: date, cloud_max: float = 35):
    poly = _validate_polygon(geojson)
    item = _search_item(poly, target_date, cloud_max)
    assets = item["assets"]
    red_href = _asset(item, "B04", "red")
    nir_href = _asset(item, "B08", "nir")
    scl_href = _asset(item, "SCL", "scl")
    red, transform, crs, resolution = _read_masked(red_href, geojson)
    nir, nir_transform, nir_crs, _ = _read_masked(nir_href, geojson)
    # B04 e B08 têm resolução nominal de 10 m; alinhar por segurança.
    if red.shape != nir.shape or transform != nir_transform or crs != nir_crs:
        aligned = np.zeros(red.shape, dtype=np.float32)
        reproject(source=nir.filled(np.nan).astype(np.float32), destination=aligned,
                  src_transform=nir_transform, src_crs=nir_crs,
                  dst_transform=transform, dst_crs=crs, resampling=Resampling.bilinear)
        nir_data = aligned
    else:
        nir_data = nir.filled(np.nan).astype(np.float32)
    ref = {"transform": transform, "crs": crs}
    scl = _read_masked(scl_href, geojson, out_shape=red.shape, reference=ref, categorical=True)
    red_scale, red_offset = _band_scale_offset(item, "B04")
    nir_scale, nir_offset = _band_scale_offset(item, "B08")
    red_data = red.filled(np.nan).astype(np.float32) * red_scale + red_offset
    nir_data = nir_data * nir_scale + nir_offset
    # Aplicar scale/offset publicados nos metadados STAC antes do rácio NDVI.
    # Máscara do interior do polígono na grelha B04; só esses píxeis entram no denominador.
    geom_raster = transform_geom("EPSG:4326", crs, geojson)
    inside = geometry_mask([geom_raster], out_shape=red.shape, transform=transform,
                           invert=True, all_touched=False)
    # SCL: remover no-data, saturados, sombras, nuvens, cirrus e neve.
    clear = inside & ~np.isin(scl, [0, 1, 3, 8, 9, 10, 11])
    total = int(inside.sum())
    try:
        ndvi, valid, stats = calculate_ndvi_statistics(red_data, nir_data, clear)
    except ValueError:
        raise DataUnavailable("A imagem existe, mas não há píxeis válidos dentro do talhão depois da máscara de qualidade.")
    count = stats["count"]
    classes = stats["classes"]
    pct = {k: round(v/count*100, 2) for k,v in classes.items()}
    png, bounds = _png_overlay(ndvi, valid, transform, crs)
    captured = item["properties"].get("datetime")
    cloud = float(item["properties"].get("eo:cloud_cover", float("nan")))
    return {
        "source": "Microsoft Planetary Computer · Sentinel-2 L2A",
        "collection": "sentinel-2-l2a", "item_id": item.get("id"),
        "requested_date": target_date.isoformat(), "acquisition_datetime": captured,
        "days_from_requested": abs((datetime.fromisoformat(captured.replace("Z", "+00:00")).date()-target_date).days),
        "cloud_cover_scene_percent": round(cloud, 2),
        "resolution_m": 10, "band_red": "B04", "band_nir": "B08", "quality_band": "SCL",
        "ndvi_mean": round(stats["mean"], 4), "ndvi_min": round(stats["min"], 4),
        "ndvi_max": round(stats["max"], 4), "valid_pixels": count,
        "total_polygon_pixels": total, "valid_coverage_percent": round(count/total*100, 2) if total else 0,
        "class_pixel_counts": classes, "class_percentages": pct,
        "weighting": "Média aritmética dos píxeis válidos; grelha Sentinel-2 de 10 m. Píxeis seleccionados pelo centro dentro do polígono.",
        "overlay_png_base64": png, "overlay_bounds_wgs84": bounds
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AgroVision geospatial engine", "satellite_access": "public STAC; requires internet"}

@app.post("/api/ndvi/analyze")
def ndvi_analyze(req: AnalysisRequest):
    try:
        result = analyze_polygon(req.polygon, req.date, req.cloud_max)
        result["field_id"] = req.field_id; result["field_name"] = req.field_name
        return result
    except ValueError as exc: raise HTTPException(400, str(exc))
    except DataUnavailable as exc: raise HTTPException(503, str(exc))

@app.post("/api/ndvi/compare")
def ndvi_compare(req: CompareRequest):
    if req.date_before >= req.date_after:
        raise HTTPException(400, "A data inicial deve ser anterior à data final.")
    try:
        before = analyze_polygon(req.polygon, req.date_before, req.cloud_max)
        after = analyze_polygon(req.polygon, req.date_after, req.cloud_max)
        delta = round(after["ndvi_mean"] - before["ndvi_mean"], 4)
        if delta <= -0.10: status = "redução significativa; inspeccionar o talhão"
        elif delta >= 0.10: status = "aumento significativo do NDVI"
        else: status = "variação inferior a 0,10; sem alteração média forte detectada"
        return {"field_id": req.field_id, "field_name": req.field_name,
                "before": before, "after": after, "ndvi_mean_change": delta,
                "interpretation": status,
                "note": "Comparação de médias do talhão. Não identifica a causa nem substitui inspecção de campo."}
    except ValueError as exc: raise HTTPException(400, str(exc))
    except DataUnavailable as exc: raise HTTPException(503, str(exc))

# Serve the existing web application from the same local server.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=str(Path(__file__).resolve().parent), html=True), name="agrovision-web")
