"""Catálogo VIT desde las fichas publicadas por DITEC (minvu.gob.cl/construccion-industrializada/).

Cada ficha (PDF con texto, 2025) trae el oficio de aprobación de DITEC con una tabla de campos fijos.
Este script la parsea y escribe src/data/vit-fichas.json. Lo que no encuentra queda null: nunca se
infiere. Uso: python scripts/fichas-vit.py <carpeta con los PDF>
"""
import json
import os
import re
import sys

import fitz

CAMPOS = [
    "Propietario del Proyecto", "Empresa Industrializadora", "RES EX Autorización Industrializadora",
    "Nombre del Proyecto de Vivienda Tipo", "Programa para el cual se desarrolló", "Tipología",
    "Zona Térmica para la cual se desarrolló", "Itemizado Técnico aplicable", "Cuadro Normativo aplicable",
    "Superficie/m2", "Sistema constructivo", "Materialidad", "Clasificación de Suelo y Zona Sísmica",
    "N° de pisos", "Terminaciones",
]
CLAVE = {
    "Propietario del Proyecto": "propietario", "Empresa Industrializadora": "empresa",
    "RES EX Autorización Industrializadora": "resExEmpresa", "Nombre del Proyecto de Vivienda Tipo": "nombre",
    "Programa para el cual se desarrolló": "programa", "Tipología": "tipologia",
    "Zona Térmica para la cual se desarrolló": "zonaTermica", "Itemizado Técnico aplicable": "itemizado",
    "Cuadro Normativo aplicable": "cuadroNormativo", "Superficie/m2": "superficie",
    "Sistema constructivo": "sistema", "Materialidad": "materialidad",
    "Clasificación de Suelo y Zona Sísmica": "sueloSismica", "N° de pisos": "pisos", "Terminaciones": "terminaciones",
}


def norm(s):
    return re.sub(r"\s+", " ", s.replace("ﬁ", "fi")).strip()


def parsear(ruta):
    d = fitz.open(ruta)
    paginas = [p.get_text() for p in d]
    todo = "\n".join(paginas)
    out = {"archivo": os.path.basename(ruta), "paginas": len(paginas)}
    # Oficios: número y fecha (puede haber más de uno: aprobación + modificación)
    out["oficios"] = []
    for m in re.finditer(r"ORD\.?\s*N[°º]\s*:?\s*(\d+)\s*\n", todo):
        f = re.search(r"Santiago,\s*([^\n]+)", todo[m.end():m.end() + 2500])
        out["oficios"].append({"ord": m.group(1), "fecha": norm(f.group(1)) if f else None})
    out["verificadoManual"] = False  # R4: cada ficha se coteja a mano contra el PDF antes de publicar
    # Tabla de aprobación: los rótulos aparecen en líneas propias (a veces con ":"), el valor en
    # las líneas siguientes hasta el próximo rótulo. El orden de lectura del PDF varía, así que se
    # busca en todo el texto y no en un segmento.
    lineas = [norm(l) for l in todo.split("\n") if norm(l)]
    # Para cada rótulo pueden existir varias apariciones (la ficha comercial repite "Sistema
    # constructivo"); se toma la más cercana al ancla de la tabla (la línea "RES EX Autorización").
    aparic = {c: [i for i, l in enumerate(lineas) if re.match(re.escape(c.lower()[:20]), l.lower())] for c in CAMPOS}
    ancla = (aparic["RES EX Autorización Industrializadora"] or aparic["Nombre del Proyecto de Vivienda Tipo"] or [0])[0]
    pos = {c: min(v, key=lambda i: abs(i - ancla)) for c, v in aparic.items() if v}
    orden = sorted(pos.items(), key=lambda x: x[1])
    for j, (c, i) in enumerate(orden):
        fin = orden[j + 1][1] if j + 1 < len(orden) else min(i + 4, len(lineas))
        fin = min(fin, i + 4)
        resto = re.sub(re.escape(c), "", lineas[i], flags=re.I).strip(" :")
        vals = [x for x in lineas[i + 1:fin] if not re.match(r"^(ORD|CÓDIGO|OFICIO|“Proyecto|\d\.$)", x, re.I)]
        val = " ".join(([resto] if resto else []) + vals).strip(" :")
        out[CLAVE[c]] = val or None
    for c in CLAVE.values():
        out.setdefault(c, None)
    cods = [norm(x) for x in re.findall(r"\n\s*(0?0\s*[–-]\s*DITEC[^\n]+)", todo)]
    out["codigosAprobacion"] = cods or None
    m = re.search(r"ZONAS? TÉRMICAS? EN DONDE SE PUEDE IMPLEMENTAR:\s*([^\n]+)", todo)
    out["zonasFicha"] = norm(m.group(1)) if m else None
    sup = re.findall(r"SUPERFICIE VIVIENDA (BASE|AMPLIADA)[^\d]*([\d.,]+)\s*m2", todo, re.I)
    out["superficieFicha"] = {k.lower(): v for k, v in sup} or None
    m = re.search(r"Desarrollada por ([^\n]+)", todo)
    out["desarrolladaPor"] = norm(m.group(1)) if m else None
    out["condiciones"] = bool(re.search(r"ensayos de permeabilidad", todo))
    return out


# ---------------------------------------------------------------------------------------------
# COTEJO MANUAL (17-sep-2026): las 24 fichas se leyeron contra el PDF (página del oficio con la
# tabla). Lo que sigue corrige lo que el parser sacó mal o truncado. Clave = número de ficha.
# ---------------------------------------------------------------------------------------------
COTEJO = {
    1: {"nombre": "VIVIENDA INDUSTRIALIZADA TIPO MINVU-PATAGUAL 01", "oficios": [{"ord": "46", "fecha": "10 enero 2023"}]},
    2: {"superficie": "52 m² (base) + 9,84 m² (ampliación proyectada) = 61,84 m² + sombreador 3,66 m²"},
    5: {"oficios": [{"ord": "1755", "fecha": "02 noviembre 2023 (reemplaza y rectifica el ORD 11 del 26-10-2023)"}]},
    6: {"nombre": "VIT RURAL ÑANDÚ", "materialidad": "Madera", "codigosAprobacion": ["00 – DITEC – TECNOTRUSS SA – 04 – 64"],
        "oficios": [{"ord": "2462", "fecha": "04 diciembre 2024 (deroga ORD 1373/2024 y 277/2024; aprueba ÑANDÚ y ÑANDÚ RD)"}]},
    7: {"nombre": "VIT RURAL ÑANDÚ RD", "materialidad": "Panel SIP", "codigosAprobacion": ["00 – DITEC – TECNOTRUSS SA – 05 – 64"],
        "oficios": [{"ord": "2462", "fecha": "04 diciembre 2024 (deroga ORD 1373/2024 y 277/2024; aprueba ÑANDÚ y ÑANDÚ RD)"}]},
    10: {"superficie": "52,57 m² base + 9,2 m² ampliación proyectada"},
    11: {"zonaTermica": "A - B - C - D - E - F, según condicionantes por zona (EETT e Informe Cumplimiento Estándar Higrotérmico)"},
    12: {"superficie": "50,63 m² base + 11,11 m² ampliación proyectada"},
    13: {"empresa": "Constructora Nova Unión SpA (propietario) · sistema Baumax", "oficios": [{"ord": "810", "fecha": "03 mayo 2023 (ORD anterior 803 del 03-05-2023)"}]},
    14: {"pisos": "3 pisos (1 solución habitacional por piso)"},
    15: {"pisos": "5 pisos (4 soluciones habitacionales por piso)",
         "superficie": "Desde 57,80 hasta 58,07 m² (depto. interior) + 1,29 m² (½ sup. balcón) + áreas comunes",
         "oficios": [{"ord": "2450", "fecha": "29 diciembre 2023"}]},
    16: {"oficios": [{"ord": "248", "fecha": "17 febrero 2025"}]},
    17: {"superficie": "50,05 m² base + 11,3 m² ampliación proyectada", "oficios": [{"ord": "545", "fecha": "28 febrero 2024"}]},
    18: {"codigosAprobacion": ["15 – DITEC – TECNOFAST – 01 – 60.04"], "propietario": "TECNO FAST S.A."},
    19: {"materialidad": "Muros SIP (Smart Panel exterior, OSB y alma de poliestireno expandido); tabiquería de acero galvanizado liviano; cerchas y frontones de madera; revestimiento exterior Smart Panel",
         "oficios": [{"ord": "507", "fecha": "16 abril 2025 (deroga ORD 462 del 10-04-2025)"}]},
    20: {"oficios": [{"ord": "2704", "fecha": "31 diciembre 2024"}, {"ord": "251", "fecha": "19 febrero 2025 (ajusta código de aprobación)"}],
         "codigosAprobacion": ["00 – DITEC – PREFABRICADAS PREMIUM SPA – 01 – 50,14"]},
    21: {"empresa": "Prefabricados PREMIUM SpA", "nombre": "VIT LIMARI ADOSADA", "programa": "DS 49", "zonaTermica": "A-B-C-D-E", "pisos": "1 piso",
         "resExEmpresa": "Res. Ex. 1657 del 04.10.2023", "oficios": [{"ord": "762", "fecha": "20 mayo 2025"}]},
    22: {"oficios": [{"ord": "1006", "fecha": "26 abril 2024 (aprobación)"}, {"ord": "749", "fecha": "19 mayo 2025 (rectifica superficie y código)"}],
         "codigosAprobacion": ["00 – DITEC – PROMET – 03 – 55,56 (nuevo); 00 – DITEC – PROMET – 01 – 58 (original)"]},
    23: {"superficie": "51,28 m² base + 9,66 m² ampliación proyectada", "oficios": [{"ord": "2575", "fecha": "17 diciembre 2024"}]},
    24: {"superficie": "52,28 m² base + 10,75 m² ampliación proyectada", "oficios": [{"ord": "424", "fecha": "31 marzo 2025"}]},
}
COTEJADAS = set(range(1, 25))  # las 24, leídas el 17-sep-2026


def main():
    carpeta = sys.argv[1]
    fichas = []
    for f in sorted(os.listdir(carpeta), key=lambda x: int(re.match(r"(\d+)", x).group(1)) if re.match(r"\d+", x) else 999):
        if f.lower().endswith(".pdf"):
            x = parsear(os.path.join(carpeta, f))
            n = int(re.match(r"(\d+)", f).group(1))
            x.update(COTEJO.get(n, {}))
            x["verificadoManual"] = n in COTEJADAS
            fichas.append(x)
    dst = os.path.join(os.path.dirname(__file__), "..", "src", "data", "vit-fichas.json")
    json.dump({"fuente": "Fichas VIT publicadas por Minvu DITEC en minvu.gob.cl/construccion-industrializada/",
               "consulta": "2026-09-17", "fichas": fichas}, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for x in fichas:
        print(f"{x['archivo'][:38]:38} | {x['empresa']} | {x['nombre']} | {x['programa']} | {x['tipologia']} | {x['zonaTermica']} | {x['superficie']} | {x['sistema']} | {x['materialidad']} | {x['pisos']} | ORD {[o['ord'] for o in x['oficios']]}")


if __name__ == "__main__":
    main()
