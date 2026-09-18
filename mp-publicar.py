"""Publica en src/data/mp-licitaciones.json sólo las licitaciones con revisión «incluir».

Entradas: data-raw/mp-candidatos.json (cosecha, scripts/mercado-publico.py) y data-raw/mp-revision.json
(revisión fila a fila: revision incluir|excluir|dudoso, tipo, motivo). Las dudosas y excluidas no salen.

Supresiones (derecho de oposición/supresión de una persona natural, Ley 19.628 / 21.719):
data-raw/mp-supresiones.json = {"<razón social tal como la publica Mercado Público>": {"sustituto": "empresa individual",
"fecha": "aaaa-mm-dd", "motivo": "…"}}. Se aplica SIEMPRE al publicar, de modo que una nueva cosecha no reintroduce
el nombre suprimido. El archivo se crea vacío ({}) si no existe.
Uso: python scripts/mp-publicar.py
"""
import json
import os

RAIZ = os.path.join(os.path.dirname(__file__), "..")
cand = json.load(open(os.path.join(RAIZ, "data-raw", "mp-candidatos.json"), encoding="utf-8"))
rev = json.load(open(os.path.join(RAIZ, "data-raw", "mp-revision.json"), encoding="utf-8"))
ruta_sup = os.path.join(RAIZ, "data-raw", "mp-supresiones.json")
if not os.path.exists(ruta_sup):
    json.dump({}, open(ruta_sup, "w", encoding="utf-8"))
sup = json.load(open(ruta_sup, encoding="utf-8"))

salida = []
for cod, c in cand["candidatos"].items():
    r = rev.get(cod)
    if not r or r["revision"] != "incluir":
        continue
    adj = sorted({sup[a]["sustituto"] if a in sup else a for a in (it["adjudicatario"] for it in c["items"]) if a})
    salida.append({
        "codigo": cod, "nombre": c["nombre"], "organismo": c["organismo"], "region": c["region"],
        "comuna": c["comuna"], "estado": c["estado"], "tipo": r["tipo"], "montoEstimado": c["montoEstimado"],
        "moneda": c["moneda"], "fechaPublicacion": c["fechaPublicacion"], "fechaAdjudicacion": c["fechaAdjudicacion"],
        "adjudicatarios": adj, "motivo": r["motivo"],
    })
salida.sort(key=lambda x: x["fechaPublicacion"] or "", reverse=True)
dias = sorted(cand["diasBarridos"])
doc = {
    "fuente": "Mercado Público (ChileCompra), API pública de licitaciones",
    "consulta": "2026-09-17",
    "periodo": [dias[0], dias[-1]],
    "candidatas": len(cand["candidatos"]),
    "revision": {k: sum(1 for r in rev.values() if r["revision"] == k) for k in ("incluir", "excluir", "dudoso")},
    "criterio": cand["criterio"],
    "licitaciones": salida,
}
json.dump(doc, open(os.path.join(RAIZ, "src", "data", "mp-licitaciones.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(salida), "publicadas de", len(cand["candidatos"]), "| revisión:", doc["revision"], "| supresiones aplicadas:", len(sup))
