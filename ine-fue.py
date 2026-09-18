"""Serie INE — permisos de edificación (FUE): superficie y viviendas prefabricadas.

Fuente: INE, "Base edificación <año>" (Base_lineal_<año>.xlsx), pestaña Bases de datos de
https://www.ine.gob.cl/estadisticas-por-tema/industria-energia-y-construccion/permisos-de-edificacion
Leyenda de `clasificacion_desglose` (Anexo B del Instructivo FUE, jun-2025):
  A acero · B hormigón armado · C albañilería ladrillo · D albañilería armada/bloques · E madera ·
  F adobe/tierra · G prefabricada estructura metálica · H prefabricada de madera ·
  I placas o paneles prefabricados. Códigos de dos letras (AA, BA, …) = "otras construcciones" (cuadro C-2).

Salvedades que el sitio publica junto a la serie:
  - Las VIT con subsidio no requieren permiso DOM (Glosa 06) → no están en el FUE. Esta serie mide el
    prefabricado del mercado regular; DITEC mide el subsidiado. No se suman.
  - La clasificación la declara el solicitante del permiso.
  - Superficie: se suman las dos materialidades declaradas (desglose 1 y 2).
  - Viviendas: sólo OBRA NUEVA con destino habitacional (cod_destino 101–112: casas y edificios;
    1000–1700 son salud, cultura, culto, etc. y quedan fuera; REGULARIZACIÓN OBRA NUEVA queda fuera).
    Se publican dos cotas: `viv_prefab` (materialidad principal, desglose 1, es prefabricada) y
    `viv_prefab_alta` (cualquiera de las dos materialidades declaradas es prefabricada).
  - Concentración: `permisos_prefab` y `top10_share` (parte de las viviendas prefab en los 10 permisos
    mayores) para que se lea que la serie la mueven pocos conjuntos.
  - Control de leyenda: las letras G/H/I no están definidas en el glosario de cada base (se toman del
    instructivo jun-2025); `control_leyenda` publica el material de muro predominante por letra y año.

Uso:  python scripts/ine-fue.py 2018 2024   → escribe src/data/ine-fue.json
Requiere las bases descargadas en $INE_DIR (por defecto ./ine-bases) como base-<año>.zip.
"""
import collections
import io
import json
import os
import sys
import zipfile

import openpyxl

PREFAB = ("G", "H", "I")
REGIONES = {1: "Tarapacá", 2: "Antofagasta", 3: "Atacama", 4: "Coquimbo", 5: "Valparaíso",
            6: "O'Higgins", 7: "Maule", 8: "Biobío", 9: "La Araucanía", 10: "Los Lagos",
            11: "Aysén", 12: "Magallanes", 13: "Metropolitana", 14: "Los Ríos", 15: "Arica y Parinacota",
            16: "Ñuble"}


def procesar(anio, ruta_zip):
    z = zipfile.ZipFile(ruta_zip)
    nombre = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
    wb = openpyxl.load_workbook(io.BytesIO(z.read(nombre)), read_only=True)
    ws = next(s for s in wb.worksheets if "dificaci" in s.title)
    filas = ws.iter_rows(values_only=True)
    hdr = next(filas)
    ix = {h: i for i, h in enumerate(hdr)}
    m2 = collections.defaultdict(lambda: collections.Counter())      # region -> {codigo: m2}
    viv = collections.defaultdict(lambda: collections.Counter())     # region -> {codigo principal: unidades}
    viv_alta = collections.defaultdict(int)                          # region -> unidades con alguna mat. prefab
    permisos = collections.defaultdict(list)                         # region -> [unidades por permiso prefab]
    muro = {c: collections.Counter() for c in PREFAB}                # letra -> material de muro (grupo 1)
    for r in filas:
        reg = r[ix["Region"]]
        for k in ("1", "2"):
            c = r[ix["clasificacion_desglose" + k]]
            if c:
                m2[reg][c] += r[ix["sup_mat" + k]] or 0
        d = r[ix["cod_destino"]]
        try:
            d = int(d)
        except (TypeError, ValueError):
            continue
        if 101 <= d <= 112 and r[ix["tipo_permiso"]] == "OBRA NUEVA":
            u = r[ix["cantidad_unidad"]] or 0
            c1, c2 = r[ix["clasificacion_desglose1"]], r[ix["clasificacion_desglose2"]]
            viv[reg][c1] += u
            if c1 in PREFAB or c2 in PREFAB:
                viv_alta[reg] += u
            if c1 in PREFAB:
                permisos[reg].append(u)
                muro[c1][r[ix["material1_grupo1"]] or "—"] += 1
    out = {"anio": anio, "nacional": {}, "regiones": {}}

    def resumen(mm, vv, va, pp):
        tot_m2 = sum(mm.values()); tot_v = sum(vv.values())
        pre_m2 = sum(mm[c] for c in PREFAB); pre_v = sum(vv[c] for c in PREFAB)
        top = sorted(pp, reverse=True)[:10]
        return {"m2_total": round(tot_m2), "m2_prefab": round(pre_m2),
                "m2_prefab_G": round(mm["G"]), "m2_prefab_H": round(mm["H"]), "m2_prefab_I": round(mm["I"]),
                "pct_m2_prefab": round(100 * pre_m2 / tot_m2, 2) if tot_m2 else None,
                "viv_nuevas": tot_v, "viv_prefab": pre_v,
                "pct_viv_prefab": round(100 * pre_v / tot_v, 2) if tot_v else None,
                "viv_prefab_alta": va,
                "pct_viv_prefab_alta": round(100 * va / tot_v, 2) if tot_v else None,
                "permisos_prefab": len(pp),
                "top10_share": round(100 * sum(top) / pre_v, 1) if pre_v else None}

    nm, nv, nva, npp = collections.Counter(), collections.Counter(), 0, []
    for reg in sorted(m2):
        out["regiones"][str(reg)] = {"nombre": REGIONES.get(reg, str(reg)), **resumen(m2[reg], viv[reg], viv_alta[reg], permisos[reg])}
        nm.update(m2[reg]); nv.update(viv[reg]); nva += viv_alta[reg]; npp += permisos[reg]
    out["nacional"] = resumen(nm, nv, nva, npp)
    out["control_leyenda"] = {
        c: {"material_muro": (muro[c].most_common(1)[0][0] if muro[c] else None),
            "pct_permisos": (round(100 * muro[c].most_common(1)[0][1] / sum(muro[c].values()), 1) if muro[c] else None)}
        for c in PREFAB
    }
    return out


def main():
    a0, a1 = int(sys.argv[1]), int(sys.argv[2])
    base = os.environ.get("INE_DIR", "ine-bases")
    serie = []
    for anio in range(a0, a1 + 1):
        ruta = os.path.join(base, f"base-{anio}.zip")
        if not os.path.exists(ruta):
            print(f"falta {ruta}", file=sys.stderr); continue
        print(f"{anio} …", file=sys.stderr, flush=True)
        serie.append(procesar(anio, ruta))
    salida = {
        "fuente": "INE, Permisos de edificación (FUE), bases anuales; leyenda Anexo B Instructivo FUE jun-2025",
        "consulta": "2026-09-17",
        "nota": "VIT con subsidio no requieren permiso DOM (Glosa 06) y no están en el FUE. Clasificación declarada por el solicitante. Viviendas: obra nueva, destinos 101–112. viv_prefab = materialidad principal prefabricada; viv_prefab_alta = alguna de las dos materialidades declaradas.",
        "serie": serie,
    }
    dst = os.path.join(os.path.dirname(__file__), "..", "src", "data", "ine-fue.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    for s in serie:
        n = s["nacional"]
        print(f'{s["anio"]}: {n["pct_m2_prefab"]}% m² · {n["pct_viv_prefab"]}–{n["pct_viv_prefab_alta"]}% viv ({n["viv_prefab"]:,}–{n["viv_prefab_alta"]:,}/{n["viv_nuevas"]:,}) · {n["permisos_prefab"]} permisos, top10 {n["top10_share"]}% · {s["control_leyenda"]}')


if __name__ == "__main__":
    main()
