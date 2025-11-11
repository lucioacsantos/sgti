# CMDB - Configuration Management Database

## Visão Geral
Sistema completo de gerenciamento de ativos de TI (CMDB) com backend FastAPI, PostgreSQL e frontend Vite+Bootstrap. Permite cadastro, consulta, atualização e remoção de ativos, além de gerenciar relacionamentos entre eles.

## Estrutura do Projeto

### Backend (Python + FastAPI)
- **backend/database.py** - Configuração do banco de dados com SQLAlchemy assíncrono e asyncpg
- **backend/models.py** - Modelos SQLAlchemy para ativos e relacionamentos
- **backend/schemas.py** - Schemas Pydantic para validação de dados
- **backend/routers/assets.py** - Endpoints RESTful para CRUD de ativos
- **backend/routers/relationships.py** - Endpoints para gerenciar relacionamentos
- **backend/main.py** - Aplicação FastAPI principal com documentação Swagger

### Frontend (Vite + Bootstrap)
- **frontend/index.html** - Interface HTML com Bootstrap 5
- **frontend/src/main.js** - Lógica JavaScript para integração com API
- **frontend/vite.config.js** - Configuração do Vite (porta 5000, host 0.0.0.0)

## Funcionalidades

### Ativos de TI
- ✅ Criar novos ativos (máquinas virtuais, containers, switches, aplicativos, bancos de dados)
- ✅ Listar todos os ativos com filtros por tipo e proprietário
- ✅ Visualizar detalhes de um ativo específico
- ✅ Atualizar informações de ativos
- ✅ Deletar ativos
- ✅ Cada ativo contém: ID, nome, tipo, descrição, proprietário

### Relacionamentos
- ✅ Criar relacionamentos entre ativos (hospeda, depende, conecta, gerencia, monitora, backup)
- ✅ Visualizar todos os relacionamentos
- ✅ Deletar relacionamentos
- ✅ Navegação bidirecional entre ativos relacionados

## Tecnologias Utilizadas

### Backend
- **FastAPI** - Framework web moderno e rápido
- **SQLAlchemy 2.0** - ORM assíncrono
- **asyncpg** - Driver PostgreSQL assíncrono para máxima performance
- **Pydantic** - Validação de dados e serialização
- **Uvicorn** - Servidor ASGI
- **PostgreSQL** - Banco de dados relacional

### Frontend
- **Vite** - Build tool moderna e rápida
- **Bootstrap 5** - Framework CSS responsivo
- **Vanilla JavaScript** - Sem frameworks adicionais
- **Fetch API** - Comunicação com backend

## Endpoints da API

### Ativos
- `POST /assets/` - Criar novo ativo
- `GET /assets/` - Listar ativos (com filtros opcionais: type, owner)
- `GET /assets/{id}` - Obter ativo específico com relacionamentos
- `PUT /assets/{id}` - Atualizar ativo
- `DELETE /assets/{id}` - Deletar ativo

### Relacionamentos
- `POST /relationships/` - Criar relacionamento
- `GET /relationships/` - Listar todos os relacionamentos
- `DELETE /relationships/{source_id}/{target_id}` - Deletar relacionamento

### Documentação
- `GET /` - Informações da API
- `GET /docs` - Swagger UI (documentação interativa)
- `GET /redoc` - ReDoc (documentação alternativa)

## Como Usar

### Interface Web
1. Acesse o frontend através do webview
2. Aba **Ativos de TI**: gerencie seus ativos
   - Clique em "Novo Ativo" para adicionar
   - Use filtros para buscar ativos específicos
   - Edite ou delete ativos existentes
3. Aba **Relacionamentos**: gerencie dependências entre ativos
   - Crie relacionamentos entre dois ativos
   - Visualize e delete relacionamentos existentes

### API REST
- Documentação interativa disponível em: http://localhost:8000/docs
- Use qualquer cliente HTTP (Postman, curl, etc.) para interagir com a API

## Arquitetura em Camadas

### Camada de Modelos (models.py)
- Define estrutura de dados no banco
- Relacionamentos many-to-many entre ativos
- Índices para otimização de consultas

### Camada de Schemas (schemas.py)
- Validação de entrada/saída com Pydantic
- Separação entre criação, atualização e resposta
- Tipos fortemente tipados

### Camada de Rotas (routers/)
- Endpoints RESTful organizados por recurso
- Validação automática de parâmetros
- Tratamento de erros HTTP

### Camada de Banco (database.py)
- Conexão assíncrona com PostgreSQL
- Pool de conexões gerenciado
- Transações automáticas

## Tipos de Ativos Suportados
- Máquina Virtual
- Container
- Switch
- Aplicativo
- Banco de Dados
- Servidor
- Firewall

## Tipos de Relacionamentos
- **hospeda** - Um ativo hospeda outro (ex: servidor hospeda aplicativo)
- **depende** - Um ativo depende de outro
- **conecta** - Um ativo conecta a outro (ex: switch conecta a servidor)
- **gerencia** - Um ativo gerencia outro
- **monitora** - Um ativo monitora outro
- **backup** - Um ativo é backup de outro

## Estado Atual
✅ Backend completo e funcional
✅ Frontend completo e funcional
✅ Banco de dados PostgreSQL configurado
✅ Documentação Swagger automática
✅ Workflows configurados e rodando
✅ Integração frontend-backend funcionando

## Melhorias Futuras
- Busca avançada com múltiplos filtros combinados
- Visualização gráfica de dependências (grafo de relacionamentos)
- Histórico de alterações e auditoria
- Dashboard com métricas e estatísticas
- Exportação/importação de dados em CSV/JSON
- Autenticação e controle de acesso
- Validação de ciclos em relacionamentos
- Tags e categorias personalizadas para ativos
