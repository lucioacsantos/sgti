import pandas as pd
import requests
from datetime import datetime

EXCEL_FILE = "Mapping_de_Sistemas_CCEE.xlsx"
SHEET_NAME = "Sistemas CCEE"
API_URL = "http://localhost:8000/"
ENDPOINT = "aplicacoes/"
METHOD = "POST"
ERROS = []

df = pd.read_excel(
    EXCEL_FILE,
    sheet_name=SHEET_NAME,
    engine="openpyxl"
)

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

df = df.where(pd.notnull(df), '---')

try:
    for _, row in df.iterrows():
        created_at = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        data = {
            "sistema": row["sistema"],
            "descricao": row["descricao"],
            "objetivo": row["objetivo"],
            "linguagens": row["linguagens"],
            "bancos_dados": row["bancos_dados"],
            "area_tecnologia": row["area_tecnologia"],
            "area_negocio": row["area_negocio"],
            "created_at": created_at
        }
        response = requests.post(f"{API_URL}{ENDPOINT}", json=data)
        if response.status_code == 201:
            print(f"Sistema '{row['sistema']}' importado com sucesso!")
        else:
            ERROS.append((row['sistema'], response.text))
    if ERROS:
        for sistema, erro in ERROS:
            print(f" - {sistema}: {erro}")
        print(f"Importação finalizada com {len(ERROS)} erros:")
    else:
        print("Importação realizada com sucesso!")
except Exception as e:
    print(f"Ocorreu um erro durante a importação: {str(e)}")