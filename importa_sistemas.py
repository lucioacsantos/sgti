import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch


EXCEL_FILE = "Cópia de Mapping_de_Sistemas CCEE.xlsx"
SHEET_NAME = "Sistemas CCEE"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "seu_banco",
    "user": "seu_usuario",
    "password": "sua_senha"
}

df = pd.read_excel(
    EXCEL_FILE,
    sheet_name=SHEET_NAME,
    engine="openpyxl"
)

df = df.rename(columns={
    "Sistemas": "sistema",
    "Descritivo da Sigla": "descricao",
    "Objetivo": "objetivo",
    "Linguagem": "linguagens",
    "Banco de Dados": "bancos_dados",
    "Área de Tecnologia": "area_tecnologia",
    "Área de Negócios": "area_negocio"
})

df = df[
    [
        "sistema",
        "descricao",
        "objetivo",
        "linguagens",
        "bancos_dados",
        "area_tecnologia",
        "area_negocio"
    ]
]

df = df.dropna(subset=["sistema"])

df = df.where(pd.notnull(df), None)

sql = """
INSERT INTO public.aplicacao (
    sistema,
    descricao,
    objetivo,
    linguagens,
    bancos_dados,
    area_tecnologia,
    area_negocio
)
VALUES (
    %(sistema)s,
    %(descricao)s,
    %(objetivo)s,
    %(linguagens)s,
    %(bancos_dados)s,
    %(area_tecnologia)s,
    %(area_negocio)s
)
ON CONFLICT (sistema) DO NOTHING;
"""

conn = psycopg2.connect(**DB_CONFIG)

try:
    with conn:
        with conn.cursor() as cur:
            execute_batch(cur, sql, df.to_dict(orient="records"))
    print("✅ Importação realizada com sucesso!")
finally:
    conn.close()