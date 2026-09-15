"""Seed inicial para banco PostgreSQL recém-instalado do SGTI CMDB.

Popula dados auxiliares, service account, ativos de exemplo e usuários.
Uso:  cd backend && ../venv/bin/python seed.py
"""
import datetime
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)


def seed_reference_data(db):
    criticidades = ["Baixa", "Média", "Alta", "Crítica"]
    tipos = ["Servidor Físico", "Servidor Virtual", "Container", "Equipamento de Rede", "Estação de Trabalho"]
    ambientes = ["Produção", "Homologação", "Desenvolvimento", "Teste"]
    statuses = ["Ativo", "Inativo", "Em Manutenção", "Desativado"]
    relacoes = [
        ("Depende de", "Dependência de aplicação/serviço"),
        ("Contém", "Contém fisicamente ou logicamente"),
        ("Conecta-se a", "Conexão de rede"),
    ]
    sors = [
        ("Ubuntu 22.04", "Ubuntu Server 22.04 LTS", "LTS"),
        ("Ubuntu 24.04", "Ubuntu Server 24.04 LTS", "LTS"),
        ("RHEL 9", "Red Hat Enterprise Linux 9", "Suporte completo"),
        ("Windows Server 2022", "Microsoft Windows Server 2022", "Suporte completo"),
        ("Debian 12", "Debian GNU/Linux 12 Bookworm", "LTS"),
    ]
    areas = [
        ("Gerência de Segurança da Informação", "GESIN"),
        ("Gerência de Operações e Suporte", "GOSD"),
        ("Coordenação de Infraestrutura", "COINF"),
        ("Coordenação de Desenvolvimento", "CODEV"),
    ]

    for nivel in criticidades:
        if not db.query(models.Criticidade).filter_by(nivel=nivel).first():
            db.add(models.Criticidade(nivel=nivel))
    for nome in tipos:
        if not db.query(models.TipoAtivo).filter_by(nome=nome).first():
            db.add(models.TipoAtivo(nome=nome))
    for nome in ambientes:
        if not db.query(models.Ambiente).filter_by(nome=nome).first():
            db.add(models.Ambiente(nome=nome))
    for nome in statuses:
        if not db.query(models.StatusAtivo).filter_by(nome=nome).first():
            db.add(models.StatusAtivo(nome=nome))
    for abrev, desc, life in sors:
        if not db.query(models.SistemaOperacional).filter_by(abreviacao=abrev).first():
            db.add(models.SistemaOperacional(abreviacao=abrev, descricao=desc, lifecycle=life))
    for nome, sigla in areas:
        if not db.query(models.Areas).filter_by(nome=nome).first():
            db.add(models.Areas(nome=nome, sigla=sigla))
    for nome, desc in relacoes:
        if not db.query(models.TipoRelacionamento).filter_by(nome=nome).first():
            db.add(models.TipoRelacionamento(nome=nome, descricao=desc))
    db.commit()


def seed_aplicacoes(db):
    apps = [
        ("Portal Institucional", "Portal web institucional", "Atendimento ao cidadão", "PHP, JavaScript", "PostgreSQL", "COINF", "GOSD"),
        ("SGTI CMDB", "Gestão de configuração de TI", "Controle de ativos de TI", "Python, React", "PostgreSQL", "COINF", "GESIN"),
        ("Sistema de Monitoramento", "Plataforma Zabbix de monitoramento", "Monitoração de infraestrutura", "C, PHP", "PostgreSQL", "COINF", "GOSD"),
    ]
    for sistema, desc, obj, lang, bd, area_tec, area_neg in apps:
        if not db.query(models.Aplicacao).filter_by(sistema=sistema).first():
            db.add(
                models.Aplicacao(
                    sistema=sistema,
                    descricao=desc,
                    objetivo=obj,
                    linguagens=lang,
                    bancos_dados=bd,
                    area_tecnologia=area_tec,
                    area_negocio=area_neg,
                )
            )
    db.commit()


def seed_service_account(db) -> str:
    """Cria service account para integrações (Zabbix/automações). Retorna o token em claro."""
    existente = db.query(models.ServiceAccount).filter_by(name="integracao-zabbix").first()
    if existente:
        return None
    token = secrets.token_urlsafe(48)
    conta = models.ServiceAccount(
        name="integracao-zabbix",
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365),
        is_active=True,
    )
    conta.set_token(token)
    db.add(conta)
    db.commit()
    return token


def seed_ativos(db):
    if db.query(models.Ativo).count() > 0:
        return
    tipo_srv = db.query(models.TipoAtivo).filter_by(nome="Servidor Virtual").first()
    tipo_fis = db.query(models.TipoAtivo).filter_by(nome="Servidor Físico").first()
    prod = db.query(models.Ambiente).filter_by(nome="Produção").first()
    homol = db.query(models.Ambiente).filter_by(nome="Homologação").first()
    status_ativo = db.query(models.StatusAtivo).filter_by(nome="Ativo").first()
    crit_alta = db.query(models.Criticidade).filter_by(nivel="Alta").first()
    crit_crit = db.query(models.Criticidade).filter_by(nivel="Crítica").first()
    ubuntu = db.query(models.SistemaOperacional).filter_by(abreviacao="Ubuntu 22.04").first()
    rhel = db.query(models.SistemaOperacional).filter_by(abreviacao="RHEL 9").first()
    area_coinf = db.query(models.Areas).filter_by(sigla="COINF").first()
    area_gosd = db.query(models.Areas).filter_by(sigla="GOSD").first()

    ativos = [
        models.Ativo(nome="zbx-server01", descricao="Servidor principal do Zabbix", tipo_id=tipo_srv.id, ambiente_id=prod.id, status_id=status_ativo.id, criticidade_id=crit_crit.id, sor_id=ubuntu.id, areas_id=area_gosd.id),
        models.Ativo(nome="db-prod01", descricao="Banco de dados PostgreSQL de produção", tipo_id=tipo_fis.id, ambiente_id=prod.id, status_id=status_ativo.id, criticidade_id=crit_crit.id, sor_id=rhel.id, areas_id=area_coinf.id),
        models.Ativo(nome="app-web01", descricao="Servidor de aplicação web", tipo_id=tipo_srv.id, ambiente_id=prod.id, status_id=status_ativo.id, criticidade_id=crit_alta.id, sor_id=ubuntu.id, areas_id=area_coinf.id),
        models.Ativo(nome="app-homol01", descricao="Servidor de aplicação homologação", tipo_id=tipo_srv.id, ambiente_id=homol.id, status_id=status_ativo.id, criticidade_id=crit_alta.id, sor_id=ubuntu.id, areas_id=area_coinf.id),
    ]
    db.add_all(ativos)
    db.commit()

    db.add_all(
        [
            models.EnderecoIp(ativo_id=ativos[0].id, ip="10.10.1.10", interface="eth0", primario=True),
            models.EnderecoIp(ativo_id=ativos[1].id, ip="10.10.2.20", interface="eth0", primario=True),
            models.EnderecoIp(ativo_id=ativos[2].id, ip="10.10.3.30", interface="eth0", primario=True),
            models.EnderecoIp(ativo_id=ativos[3].id, ip="10.20.3.30", interface="eth0", primario=True),
        ]
    )
    tipo_dep = db.query(models.TipoRelacionamento).filter_by(nome="Depende de").first()
    tipo_contem = db.query(models.TipoRelacionamento).filter_by(nome="Contém").first()
    db.add_all(
        [
            models.Relacionamento(origem_id=ativos[2].id, destino_id=ativos[1].id, tipo_id=tipo_dep.id, descricao="app-web01 usa o banco db-prod01"),
            models.Relacionamento(origem_id=ativos[0].id, destino_id=ativos[3].id, tipo_id=tipo_contem.id, descricao="Zabbix monitora app-homol01"),
        ]
    )
    portal = db.query(models.Aplicacao).filter_by(sistema="Portal Institucional").first()
    cmdb = db.query(models.Aplicacao).filter_by(sistema="SGTI CMDB").first()
    db.add_all(
        [
            models.InstanciaAplicacao(aplicacao_id=portal.id, ativo_id=ativos[2].id, porta=8080, path_execucao="/var/www/portal"),
            models.InstanciaAplicacao(aplicacao_id=cmdb.id, ativo_id=ativos[1].id, porta=5432, path_execucao="/opt/sgti/backend"),
        ]
    )
    db.commit()


def main():
    db = SessionLocal()
    try:
        seed_reference_data(db)
        seed_aplicacoes(db)
        seed_ativos(db)
        token = seed_service_account(db)
        counts = {
            "criticidades": db.query(models.Criticidade).count(),
            "tipos_ativo": db.query(models.TipoAtivo).count(),
            "ambientes": db.query(models.Ambiente).count(),
            "status": db.query(models.StatusAtivo).count(),
            "sor": db.query(models.SistemaOperacional).count(),
            "areas": db.query(models.Areas).count(),
            "tipos_relacionamento": db.query(models.TipoRelacionamento).count(),
            "aplicacoes": db.query(models.Aplicacao).count(),
            "ativos": db.query(models.Ativo).count(),
            "ips": db.query(models.EnderecoIp).count(),
            "relacionamentos": db.query(models.Relacionamento).count(),
            "service_accounts": db.query(models.ServiceAccount).count(),
        }
        print("Seed concluído:", counts)
        if token:
            print("\n=== SERVICE ACCOUNT 'integracao-zabbix' ===")
            print(f"Token (guarde com segurança): {token}")
            print("Header para a API: X-Service-Token: <token>")
    finally:
        db.close()


if __name__ == "__main__":
    main()