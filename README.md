# Radar Construcción Industrializada — scripts de datos

Scripts con los que [Radar Construcción Industrializada](https://radar-construccion-industrializados.netlify.app)
(Tercera Letra) genera sus series a partir de registros oficiales. Cada script declara en su cabecera la fuente, la leyenda y los supuestos. Las salidas
son JSON que el sitio lee tal cual.

| Script | Fuente | Salida |
|---|---|---|
| `ine-fue.py` | INE, permisos de edificación (FUE), bases anuales 2019–2024 | serie nacional y regional del prefabricado (categorías G/H/I), dos cotas, permisos, concentración, control de leyenda |
| `deficit-censo.py` | Minvu CECT, déficit habitacional Censo 2024 (metodología completa) | país, 16 regiones, 346 comunas |
| `fichas-vit.py` | Minvu DITEC, fichas de viviendas industrializadas tipo (PDF) | tabla del oficio de aprobación de cada ficha, con cotejo manual |
| `mercado-publico.py` | Mercado Público, API pública de licitaciones (ticket personal, gratuito) | cosecha diaria de candidatas por palabra clave y categoría UNSPSC |
| `mp-publicar.py` | revisión fila a fila de las candidatas | sólo lo revisado como «incluir»; aplica supresiones de personas naturales |

## Uso

Python 3.12, `openpyxl`, `pymupdf`, `requests`. Las bases del INE se descargan de la pestaña «Bases de datos» de
[ine.gob.cl](https://www.ine.gob.cl/estadisticas-por-tema/industria-energia-y-construccion/permisos-de-edificacion)
a `ine-bases/base-<año>.zip`. El ticket de Mercado Público se pide en
[api.mercadopublico.cl](https://api.mercadopublico.cl) y se guarda en un archivo de entorno local como
`MERCADO_PUBLICO_TICKET=…`, que nunca se versiona.

## Privacidad

`mercado-publico.py` no guarda los campos de la persona que publica una licitación. De los adjudicatarios se
conserva la razón social sólo cuando el RUT es de persona jurídica (≥ 50.000.000); las personas naturales
quedan como «persona natural», sin nombre ni RUT. `mp-publicar.py` aplica `data-raw/mp-supresiones.json` en
cada publicación, de modo que una supresión pedida por su titular no se reintroduce con la siguiente cosecha.

## Método y correcciones

La metodología completa, los niveles de afirmación (N1, N2, derivado) y el historial de correcciones están en
la página «Metodología y fuentes» del radar. Correcciones y fuentes: contacto@terceraletra.cl.

© Tercera Letra SpA. Código bajo licencia MIT; los datos pertenecen a sus fuentes oficiales.
