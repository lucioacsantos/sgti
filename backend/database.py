import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Configuração da URL de Conexão
# Para produção, recomenda-se usar variáveis de ambiente (ex: os.getenv("DATABASE_URL"))
# Formato: postgresql://usuario:senha@host:porta/nome_do_banco
SQLALCHEMY_DATABASE_URL = "postgresql://cmdb:cmdb@localhost/cmdb"

# 2. Criação do Engine
# O 'engine' é o ponto de entrada para o banco de dados.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # pool_size e max_overflow ajudam na performance de concorrência do FastAPI
    pool_size=5,
    max_overflow=10
)

# 3. Fábrica de Sessões
# 'autocommit=False' garante que as transações sejam tratadas explicitamente
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Classe Base para os Modelos
# Todos os seus modelos (Ativo, Relacionamento, etc.) herdarão desta classe
Base = declarative_base()

# 5. Função Utilitária (Dependency Injection)
# Esta função será usada no FastAPI para garantir que cada requisição tenha sua própria sessão
# e que ela seja fechada após o uso, evitando vazamentos de memória (memory leaks).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()