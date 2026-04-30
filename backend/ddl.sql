CREATE TABLE public.ambiente (
	id serial4 NOT NULL,
	nome varchar(50) NOT NULL,
	CONSTRAINT ambiente_nome_key UNIQUE (nome),
	CONSTRAINT ambiente_pkey PRIMARY KEY (id)
);


CREATE TABLE public.api_token (
	id serial4 NOT NULL,
	nome varchar(255) NULL,
	"token" text NOT NULL,
	ativo bool DEFAULT true NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT api_token_pkey PRIMARY KEY (id),
	CONSTRAINT api_token_token_key UNIQUE (token)
);



CREATE TABLE public.audit_log (
	id serial4 NOT NULL,
	entidade varchar(100) NOT NULL,
	entidade_id int4 NULL,
	acao varchar(50) NULL,
	antes jsonb NULL,
	depois jsonb NULL,
	usuario varchar(255) NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT audit_log_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_audit_entidade ON public.audit_log USING btree (entidade);


CREATE TABLE public.criticidade (
	id serial4 NOT NULL,
	nivel varchar(50) NOT NULL,
	CONSTRAINT criticidade_nivel_key UNIQUE (nivel),
	CONSTRAINT criticidade_pkey PRIMARY KEY (id)
);


CREATE TABLE public.service_accounts (
	id serial4 NOT NULL,
	"name" varchar(100) NOT NULL,
	"token" varchar(255) NOT NULL,
	created_at timestamp NULL,
	expires_at timestamp NOT NULL,
	is_active bool NULL,
	CONSTRAINT service_accounts_name_key UNIQUE (name),
	CONSTRAINT service_accounts_pkey PRIMARY KEY (id)
);
CREATE INDEX ix_service_accounts_id ON public.service_accounts USING btree (id);
CREATE UNIQUE INDEX ix_service_accounts_token ON public.service_accounts USING btree (token);


CREATE TABLE public.sor (
	id serial4 NOT NULL,
	abreviacao varchar(50) NOT NULL,
	descricao varchar(255) NOT NULL,
	lifecycle varchar(150) NULL,
	CONSTRAINT sor_pk PRIMARY KEY (id),
	CONSTRAINT sor_unique UNIQUE (abreviacao),
	CONSTRAINT sor_unique_1 UNIQUE (descricao)
);


CREATE TABLE public.status_ativo (
	id serial4 NOT NULL,
	nome varchar(50) NOT NULL,
	CONSTRAINT status_ativo_nome_key UNIQUE (nome),
	CONSTRAINT status_ativo_pkey PRIMARY KEY (id)
);


CREATE TABLE public.tipo_ativo (
	id serial4 NOT NULL,
	nome varchar(100) NOT NULL,
	descricao text NULL,
	CONSTRAINT tipo_ativo_nome_key UNIQUE (nome),
	CONSTRAINT tipo_ativo_pkey PRIMARY KEY (id)
);


CREATE TABLE public.tipo_relacionamento (
	id serial4 NOT NULL,
	nome varchar(100) NOT NULL,
	descricao text NULL,
	CONSTRAINT tipo_relacionamento_nome_key UNIQUE (nome),
	CONSTRAINT tipo_relacionamento_pkey PRIMARY KEY (id)
);


CREATE TABLE public.areas (
	id serial4 NOT NULL,
	nome varchar(100) NOT NULL,
	sigla text NULL,
	CONSTRAINT areas_nome_key UNIQUE (nome),
	CONSTRAINT areas_sigla_key UNIQUE (sigla),
	CONSTRAINT areas_pkey PRIMARY KEY (id)
);


CREATE TABLE public.ativo (
	id serial4 NOT NULL,
	nome varchar(255) NOT NULL,
	descricao text NULL,
	tipo_id int4 NOT NULL,
	ambiente_id int4 NULL,
	status_id int4 NULL,
	criticidade_id int4 NULL,
    sor_id int4 NULL,
	areas_id int4 NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT ativo_pkey PRIMARY KEY (id),
	CONSTRAINT ativo_ambiente_id_fkey FOREIGN KEY (ambiente_id) REFERENCES public.ambiente(id),
	CONSTRAINT ativo_criticidade_id_fkey FOREIGN KEY (criticidade_id) REFERENCES public.criticidade(id),
	CONSTRAINT ativo_sor_fk FOREIGN KEY (sor_id) REFERENCES public.sor(id),
	CONSTRAINT ativo_status_id_fkey FOREIGN KEY (status_id) REFERENCES public.status_ativo(id),
	CONSTRAINT ativo_tipo_id_fkey FOREIGN KEY (tipo_id) REFERENCES public.tipo_ativo(id),
	CONSTRAINT ativo_areas_id_fkey FOREIGN KEY (areas_id) REFERENCES public.areas(id)
);
CREATE INDEX idx_ativo_nome ON public.ativo USING btree (nome);
CREATE INDEX idx_ativo_tipo ON public.ativo USING btree (tipo_id);


CREATE TABLE public."cluster" (
	id serial4 NOT NULL,
	nome varchar(255) NOT NULL,
	descricao text NULL,
	ativo_id int4 NULL,
	CONSTRAINT cluster_ativo_id_key UNIQUE (ativo_id),
	CONSTRAINT cluster_nome_key UNIQUE (nome),
	CONSTRAINT cluster_pkey PRIMARY KEY (id),
	CONSTRAINT cluster_ativo_id_fkey FOREIGN KEY (ativo_id) REFERENCES public.ativo(id) ON DELETE SET NULL
);


CREATE TABLE public."namespace" (
	id serial4 NOT NULL,
	nome varchar(255) NOT NULL,
	cluster_id int4 NULL,
	ativo_id int4 NULL,
	CONSTRAINT namespace_ativo_id_key UNIQUE (ativo_id),
	CONSTRAINT namespace_pkey PRIMARY KEY (id),
	CONSTRAINT namespace_ativo_id_fkey FOREIGN KEY (ativo_id) REFERENCES public.ativo(id) ON DELETE SET NULL,
	CONSTRAINT namespace_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES public."cluster"(id) ON DELETE CASCADE
);


CREATE TABLE public.relacionamento (
	id serial4 NOT NULL,
	origem_id int4 NOT NULL,
	destino_id int4 NOT NULL,
	tipo_id int4 NOT NULL,
	descricao text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT relacionamento_pkey PRIMARY KEY (id),
	CONSTRAINT relacionamento_destino_id_fkey FOREIGN KEY (destino_id) REFERENCES public.ativo(id) ON DELETE CASCADE,
	CONSTRAINT relacionamento_origem_id_fkey FOREIGN KEY (origem_id) REFERENCES public.ativo(id) ON DELETE CASCADE,
	CONSTRAINT relacionamento_tipo_id_fkey FOREIGN KEY (tipo_id) REFERENCES public.tipo_relacionamento(id)
);
CREATE INDEX idx_rel_destino ON public.relacionamento USING btree (destino_id);
CREATE INDEX idx_rel_origem ON public.relacionamento USING btree (origem_id);
CREATE INDEX idx_rel_tipo ON public.relacionamento USING btree (tipo_id);


CREATE TABLE public.servico (
	id serial4 NOT NULL,
	nome varchar(255) NOT NULL,
	tipo varchar(50) NULL,
	host_id int4 NULL,
	ativo_id int4 NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT servico_ativo_id_key UNIQUE (ativo_id),
	CONSTRAINT servico_pkey PRIMARY KEY (id),
	CONSTRAINT servico_ativo_id_fkey FOREIGN KEY (ativo_id) REFERENCES public.ativo(id) ON DELETE SET NULL
);


CREATE TABLE public.servico_negocio (
	id serial4 NOT NULL,
	nome varchar(255) NOT NULL,
	descricao text NULL,
	ativo_id int4 NULL,
	CONSTRAINT servico_negocio_ativo_id_key UNIQUE (ativo_id),
	CONSTRAINT servico_negocio_pkey PRIMARY KEY (id),
	CONSTRAINT servico_negocio_ativo_id_fkey FOREIGN KEY (ativo_id) REFERENCES public.ativo(id) ON DELETE SET NULL
);


CREATE TABLE public.aplicacao (
	id serial4 NOT NULL,
	sistema varchar(255) NOT NULL,
	descricao varchar(255) NULL,
	objetivo text NULL,
	linguagens varchar(255) NULL,
	bancos_dados varchar(255) NULL,
	area_tecnologia varchar(255) NULL,
	area_negocio varchar(255) NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT aplicacao_pkey PRIMARY KEY (id),
	CONSTRAINT aplicacao_sistema_key UNIQUE (sistema)
);


CREATE TABLE public.instancia_aplicacao (
	id serial4 NOT NULL,
	aplicacao_id int4 NOT NULL,
	ativo_id int4 NULL,
	porta int4 NULL,
	path_execucao varchar(255) NULL,
	comando_execucao text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT instancia_aplicacao_ativo_id_key UNIQUE (ativo_id),
	CONSTRAINT instancia_aplicacao_pkey PRIMARY KEY (id),
	CONSTRAINT instancia_aplicacao_aplicacao_id_fkey FOREIGN KEY (aplicacao_id) REFERENCES public.aplicacao(id) ON DELETE CASCADE,
	CONSTRAINT instancia_aplicacao_ativo_id_fkey FOREIGN KEY (ativo_id) REFERENCES public.ativo(id) ON DELETE SET NULL
);


CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL, -- login AD
    nome VARCHAR(255),
    email VARCHAR(255),
    totp_secret VARCHAR(64),
    totp_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE usuario_backup_code (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    codigo_hash VARCHAR(255) NOT NULL,
    usado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


// Token de exemplo para testes, expira em 24/05/2026
INSERT INTO public.service_accounts
	(id, "name", "token", created_at, expires_at, is_active)
	VALUES(1, 'string', 'T4THTi61laNULjELRKRUkWGepvWpzjazVxdQCLBfv5XEPOf4CNk0coy_Znr84lx6', 
		'2026-04-24 19:04:19.952', '2026-05-24 19:04:19.914', true);