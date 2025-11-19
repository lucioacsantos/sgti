# CMDB - Configuration Management Database

Sistema completo de gerenciamento de ativos de TI com Python, FastAPI, PostgreSQL e interface web moderna.

## 🚀 Características

- ✅ API RESTful completa com FastAPI
- ✅ Banco de dados PostgreSQL com SQLAlchemy assíncrono
- ✅ Interface web responsiva com Bootstrap 5
- ✅ Documentação automática com Swagger
- ✅ Suporte a relacionamentos entre ativos
- ✅ Filtros avançados e busca

## 📋 Requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL

## 🏃 Como Executar

Os workflows já estão configurados e devem iniciar automaticamente:

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5000
- **API Docs**: http://localhost:8000/docs

## 📚 Documentação

- **Python Virtual Environment**: no diretório inicial da aplicação "pyhton3 -m venv venv"
- **Ativar Python Virtual Environment**: no diretório inicial "source venv/bin/activate" 
- **Instalar dependências com pip**: a partir do diretório do backend "pip install -r requirements.txt"
- **Instalar dependências do nodejs**: no diretório do frontend "npm install && npm run build"
- **Configurar inicialização**: configurar sgti-back.service e sgti-front.service seguindo as instruções contidas neles
- **Inicializar os serviços**: sudo systemctl start sgti-back.service sgti-front.service


## 🛠️ Tecnologias

**Backend:**
- FastAPI
- SQLAlchemy (async)
- asyncpg
- Pydantic
- PostgreSQL

**Frontend:**
- Vite
- Bootstrap 5
- Vanilla JavaScript

## 📝 Licença

GNU General Public License v3.0