"""Déficit habitacional cuantitativo Censo 2024 por región y comuna (metodología oficial completa).

Fuente: Minvu CECT, "Tablas Estadísticas" de https://centrodeestudios.minvu.gob.cl/deficit-habitacional-censo-2024/
(xlsx en catalogo.minvu.cl, id 081c61c7739dc70094c000faf4c6d1f3), hoja "2024 2002 Completa".
Cifras ajustadas por el INE el 4-dic-2025 (491.804 → 491.904).
Uso: python scripts/deficit-censo.py <ruta xlsx>  → src/data/deficit-censo-2024.json
"""
import json
import os
import sys

import openpyxl

COLS = {"viviendas": (3, 4), "hogares": (5, 6), "irrecuperables": (7, 8), "allegados": (9, 10),
        "nucleosHacinados": (15, 16), "hacinamientoNoAmpliable": (17, 18), "total": (19, 20)}


def fila(r):
    out = {}
    for k, (c02, c24) in COLS.items():
        out[k] = {"2002": r[c02], "2024": r[c24]}
    return out


def main():
    wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
    ws = wb["2024 2002 Completa"]
    rows = list(ws.iter_rows(values_only=True))
    pais = fila(rows[7])
    regiones, comunas = [], []
    for r in rows[9:]:
        if r[0] is None:
            continue
        if r[1] is None and r[2] is None:
            regiones.append({"region": r[0].strip(), **fila(r)})
        elif r[2] is not None:
            comunas.append({"region": r[0].strip(), "comuna": r[1].strip(), "codigo": int(r[2]), **fila(r)})
    for x in regiones + [pais]:
        h = x["hogares"]["2024"]; t = x["total"]["2024"]
        x["pctHogares2024"] = round(100 * t / h, 1) if h else None
    salida = {
        "fuente": "Minvu CECT, Déficit Habitacional Cuantitativo Censo 2024 (metodología oficial completa), tablas estadísticas; INE ajuste 4-dic-2025",
        "consulta": "2026-09-17", "pais": pais, "regiones": regiones, "comunas": comunas,
    }
    dst = os.path.join(os.path.dirname(__file__), "..", "src", "data", "deficit-censo-2024.json")
    json.dump(salida, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("país 2024:", pais["total"]["2024"], "| regiones:", len(regiones), "| comunas:", len(comunas))
    for x in regiones:
        print(f'  {x["region"]:20} {x["total"]["2024"]:>8,}  {x["pctHogares2024"]} %')


if __name__ == "__main__":
    main()
