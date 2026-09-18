"""Demanda pública de construcción industrializada — cosecha desde la API de Mercado Público.

API: https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json (ticket personal en
.env.local, MERCADO_PUBLICO_TICKET; límite 10.000 solicitudes/día). Hay endpoint por fecha (todas las
licitaciones con actividad ese día, sólo código+nombre+estado) y por código (detalle completo).

CRITERIO DE INCLUSIÓN (se escribe antes de la primera fila, protocolo R3):
  1. Pre-filtro por nombre: alguna de las palabras clave de PALABRAS en `Nombre`.
  2. Detalle: se conserva si (a) alguna palabra clave aparece en Nombre, Descripcion o en el nombre /
     descripción de algún ítem, o (b) algún ítem tiene categoría UNSPSC 302016xx (Estructuras
     prefabricadas).
  3. Lo cosechado es CANDIDATO. La inclusión final en el sitio la decide una revisión manual fila a
     fila (campo `revision`), porque «modular» y «prefabricado» también nombran mobiliario, contenedores,
     baños químicos, etc. Nada sale al sitio con `revision` vacío.

PRIVACIDAD: no se guardan los campos de persona del comprador (NombreUsuario, RutUsuario, CargoUsuario,
CodigoUsuario). Del adjudicatario se guarda nombre y RUT sólo si el RUT es de empresa (>= 50.000.000);
si es persona natural se guarda «persona natural» sin nombre ni RUT.

Uso:  python scripts/mercado-publico.py 2025-01-01 2026-09-16
Salida: data-raw/mp-candidatos.json (acumulativo, reanudable) y resumen por stderr.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PALABRAS = re.compile(r"industrializ|modular|prefabric|panelizad|contenedor.*habitab|vivienda.*tipo|"
                      r"\bVIT\b|steel\s*frame|\bCLT\b|\bSIP\b|off.?site", re.I)
CAT_PREFAB = "302016"
RAIZ = os.path.join(os.path.dirname(__file__), "..")
SALIDA = os.path.join(RAIZ, "data-raw", "mp-candidatos.json")
BASE = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"


def ticket():
    with open(os.path.join(RAIZ, ".env.local"), encoding="utf-8") as f:
        for l in f:
            if l.startswith("MERCADO_PUBLICO_TICKET="):
                return l.split("=", 1)[1].strip()
    sys.exit("falta MERCADO_PUBLICO_TICKET en .env.local")


TK = None


def get(params, intentos=4):
    q = dict(params, ticket=TK)
    url = BASE + "?" + urllib.parse.urlencode(q)
    for i in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            time.sleep(3 * (i + 1))
            err = e
    print(f"  fallo {params}: {err}", file=sys.stderr)
    return None


def rut_empresa(rut):
    try:
        return int(re.sub(r"[^0-9]", "", rut.split("-")[0])) >= 50_000_000
    except ValueError:
        return False


def reducir(L):
    """Deja sólo lo que el sitio necesita; sin campos de persona del comprador."""
    c = L.get("Comprador") or {}
    items = []
    for it in (L.get("Items") or {}).get("Listado") or []:
        adj = it.get("Adjudicacion") or {}
        rut = adj.get("RutProveedor") or ""
        emp = rut_empresa(rut)
        items.append({
            "producto": it.get("NombreProducto"), "categoria": it.get("Categoria"),
            "codCategoria": it.get("CodigoCategoria"), "descripcion": (it.get("Descripcion") or "")[:400],
            "cantidad": it.get("Cantidad"), "unidad": it.get("UnidadMedida"),
            "adjudicatario": (adj.get("NombreProveedor") if emp else ("persona natural" if rut else None)),
            "rutAdjudicatario": rut if emp else None,
            "cantidadAdj": adj.get("Cantidad"), "montoUnitario": adj.get("MontoUnitario"),
        })
    f = L.get("Fechas") or {}
    a = L.get("Adjudicacion") or {}
    return {
        "codigo": L.get("CodigoExterno"), "nombre": L.get("Nombre"),
        "descripcion": (L.get("Descripcion") or "")[:600],
        "estado": L.get("Estado"), "codEstado": L.get("CodigoEstado"), "tipo": L.get("Tipo"),
        "organismo": c.get("NombreOrganismo"), "unidad": c.get("NombreUnidad"),
        "comuna": c.get("ComunaUnidad"), "region": (c.get("RegionUnidad") or "").strip(),
        "moneda": L.get("Moneda"), "montoEstimado": L.get("MontoEstimado"),
        "fuenteFinanciamiento": L.get("FuenteFinanciamiento"), "codigoBIP": L.get("CodigoBIP"),
        "obras": L.get("Obras"),
        "fechaPublicacion": f.get("FechaPublicacion"), "fechaCierre": f.get("FechaCierre"),
        "fechaAdjudicacion": f.get("FechaAdjudicacion"),
        "adjudicacion": {"numero": a.get("Numero"), "oferentes": a.get("NumeroOferentes"),
                         "urlActa": a.get("UrlActa")} if a else None,
        "items": items,
        "motivo": None, "revision": None,
    }


def motivo(L):
    txt = " ".join([L.get("Nombre") or "", L.get("Descripcion") or ""])
    m = PALABRAS.search(txt)
    if m:
        return "texto:" + m.group(0)
    for it in (L.get("Items") or {}).get("Listado") or []:
        if str(it.get("CodigoCategoria") or "").startswith(CAT_PREFAB):
            return "unspsc:" + str(it.get("CodigoCategoria"))
        m = PALABRAS.search((it.get("NombreProducto") or "") + " " + (it.get("Descripcion") or ""))
        if m:
            return "item:" + m.group(0)
    return None


def main():
    global TK
    TK = ticket()
    d0 = dt.date.fromisoformat(sys.argv[1]); d1 = dt.date.fromisoformat(sys.argv[2])
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    acc = {"criterio": __doc__.split("CRITERIO DE INCLUSIÓN")[1].split("PRIVACIDAD")[0].strip(),
           "diasBarridos": [], "candidatos": {}}
    if os.path.exists(SALIDA):
        acc = json.load(open(SALIDA, encoding="utf-8"))
    hechos = set(acc["diasBarridos"])
    d = d0
    n_llamadas = 0
    while d <= d1:
        k = d.isoformat()
        if k in hechos:
            d += dt.timedelta(days=1); continue
        lst = get({"fecha": d.strftime("%d%m%Y")}); n_llamadas += 1
        if lst is None:
            d += dt.timedelta(days=1); continue
        L = lst.get("Listado") or []
        pre = [x for x in L if PALABRAS.search(x.get("Nombre") or "")]
        nuevos = 0
        for x in pre:
            cod = x["CodigoExterno"]
            det = get({"codigo": cod}); n_llamadas += 1
            if not det or not det.get("Listado"):
                continue
            full = det["Listado"][0]
            m = motivo(full)
            if not m:
                continue
            r = reducir(full); r["motivo"] = m
            prev = acc["candidatos"].get(cod)
            if prev:
                r["revision"] = prev.get("revision")
            else:
                nuevos += 1
            acc["candidatos"][cod] = r
            time.sleep(0.3)
        acc["diasBarridos"].append(k)
        print(f"{k}: {len(L)} lic · {len(pre)} pre · {nuevos} nuevos · llamadas {n_llamadas}", file=sys.stderr, flush=True)
        if len(acc["diasBarridos"]) % 10 == 0:
            json.dump(acc, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        d += dt.timedelta(days=1)
        time.sleep(0.5)
    json.dump(acc, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"total candidatos: {len(acc['candidatos'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
