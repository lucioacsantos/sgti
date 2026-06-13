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
- Ollama, caso utilize o endpoint de integração com modelo de linguagem

## 🏃 Como Executar

Os workflows já estão configurados e devem iniciar automaticamente:

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5000
- **API Docs**: http://localhost:8000/docs

## 🔐 Autenticação da API

Alguns endpoints exigem autenticação por service account. Envie o token no header:

```bash
X-Service-Token: SEU_TOKEN
```

## 🤖 Integração com Ollama

A API possui um endpoint para enviar perguntas a um modelo local do Ollama.

- **Endpoint**: `POST /ollama/`
- **Autenticação**: exige header `X-Service-Token`
- **URL padrão do Ollama**: `http://localhost:11434/api/generate`
- **Modelo padrão**: `llama3`

Variáveis de ambiente opcionais:

```bash
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3
```

Exemplo de requisição:

```bash
curl -X POST http://localhost:8000/ollama/ \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: SEU_TOKEN" \
  -d '{"question": "Explique o que é uma CMDB", "model": "llama3"}'
```

Exemplo de resposta:

```json
{
  "response": "Uma CMDB é uma base de dados usada para gerenciar informações sobre ativos e serviços de TI..."
}
```

## 🧩 Integração Ollama + Zabbix

A API também permite enviar a resposta gerada pelo Ollama para as observações de um alarme aberto no Zabbix.

- **Endpoint**: `POST /zabbix/alarmes/observacao-ollama/`
- **Autenticação**: exige header `X-Service-Token`
- **Validação no Zabbix**: consulta `problem.get` para confirmar que o `event_id` está aberto
- **Prompt do modelo**: inclui dados do alarme aberto, como nome do problema, severidade e object ID
- **Gravação da observação**: usa `event.acknowledge` com ação de adicionar mensagem

Variáveis de ambiente:

```bash
ZABBIX_API_URL=http://zabbix.example.com/zabbix/api_jsonrpc.php
ZABBIX_API_TOKEN=SEU_TOKEN_DA_API
```

Também é possível autenticar com usuário e senha:

```bash
ZABBIX_API_URL=http://zabbix.example.com/zabbix/api_jsonrpc.php
ZABBIX_USER=Admin
ZABBIX_PASSWORD=zabbix
```

Caso sua instalação use token via header Bearer:

```bash
ZABBIX_USE_BEARER_TOKEN=true
```

Exemplo de requisição:

```bash
curl -X POST http://localhost:8000/zabbix/alarmes/observacao-ollama/ \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: SEU_TOKEN" \
  -d '{
    "event_id": "123456",
    "question": "Analise este alarme e sugira os próximos passos operacionais.",
    "model": "llama3"
  }'
```

Exemplo de resposta:

```json
{
  "event_id": "123456",
  "problem_name": "CPU utilization is too high",
  "ollama_response": "Verifique os processos com maior consumo de CPU e valide se houve aumento recente de carga...",
  "zabbix_result": {
    "eventids": [
      "123456"
    ]
  }
}
```

## 📚 Documentação

- **Python Virtual Environment**: no diretório inicial da aplicação "python3 -m venv venv"
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
