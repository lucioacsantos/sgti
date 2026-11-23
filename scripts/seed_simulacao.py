# Objetivo: Popula ambiente de SIMULAÇÃO do Mapa de TI: ativos, aplicações, infraestrutura e relacionamentos.
# Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

"""Dados de simulação para demonstrar o grafo de relacionamentos (Mapa de TI).

Idempotente (pode rodar mais de uma vez). Reutiliza o seed base:

Uso (a partir da raiz):  PYTHONPATH=backend venv/bin/python scripts/seed_simulacao.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
from database import SessionLocal, engine
from seed import seed_reference_data, seed_aplicacoes, seed_service_account

models.Base.metadata.create_all(bind=engine)


def _get_or_create(db, model, filtros: dict, defaults: dict = None):
    instancia = db.query(model).filter_by(**filtros).first()
    if instancia:
        return instancia, False
    dados = dict(defaults or {})
    dados.update(filtros)
    instancia = model(**dados)
    db.add(instancia)
    return instancia, True


class Simulacao:
    def __init__(self, db):
        self.db = db
        self.cache = {}

    # --- helpers de referência ---
    def ref(self, model, campo: str, chave: str):
        chave_cache = f"{model.__name__}:{chave}"
        if chave_cache in self.cache:
            return self.cache[chave_cache]
        instancia, _ = _get_or_create(self.db, model, {campo: chave})
        self.db.flush()
        self.cache[chave_cache] = instancia
        return instancia

    def tipo(self, nome): return self.ref(models.TipoAtivo, "nome", nome)
    def ambiente(self, nome): return self.ref(models.Ambiente, "nome", nome)
    def status(self, nome): return self.ref(models.StatusAtivo, "nome", nome)
    def criticidade(self, nivel): return return_crit(self.db, self.cache, nivel)  # noqa: F821 - definido no módulo
    def area(self, sigla): return self.ref(models.Areas, "sigla", sigla)
    def sor(self, abreviacao): return self.ref(models.SistemaOperacional, "abreviacao", abreviacao)

    def rel_tipo(self, nome, descricao=None):
        instancia, _ = _get_or_create(self.db, models.TipoRelacionamento,
                                      {"nome": nome}, {"descricao": descricao})
        self.db.flush()
        return instancia

    def rel(self, origem, destino, tipo_nome, descricao=None):
        tp = self.rel_tipo(tipo_nome)
        _, criado = _get_or_create(self.db, models.Relacionamento, {
            "origem_id": origem.id, "destino_id": destino.id, "tipo_id": tp.id,
        }, {"descricao": descricao})
        return criado

    def ativo(self, nome, tipo, ambiente, criticidade=None, statusNome="Ativo",
              fqdn=None, descricao=None, area_sigla="COINF", sor_="Ubuntu 24.04"):
        existente = self.db.query(models.Ativo).filter_by(nome=nome).first()
        if existente:
            return existente
        ativo = models.Ativo(
            nome=nome,
            descricao=descricao or f"{tipo} {ambiente} (simulação)",
            fqdn=fqdn or f"{nome}.sgti.local",
            tipo_id=self.tipo(tipo).id,
            ambiente_id=self.ambiente(ambiente).id,
            status_id=self.status(statusNome).id,
            criticidade_id=self.criticidade(criticidade).id if criticidade else None,
            areas_id=self.area(area_sigla).id,
            sor_id=self.sor(sor_).id,
        )
        self.db.add(ativo)
        self.db.flush()
        return ativo

    def aplicacao(self, sistema, descricao, objetivo, linguagens, bancos, area_tec, area_neg):
        existente = self.db.query(models.Aplicacao).filter_by(sistema=sistema).first()
        if existente:
            return existente
        app = models.Aplicacao(
            sistema=sistema, descricao=descricao, objetivo=objetivo,
            linguagens=linguagens, bancos_dados=bancos,
            area_tecnologia=area_tec, area_negocio=area_neg,
        )
        self.db.add(app)
        self.db.flush()
        return app


def return_crit(db, cache, nivel):
    chave = f"Criticidade:{nivel}"
    if chave in cache:
        return cache[chave]
    instancia, _ = _get_or_create(db, models.Criticidade, {"nivel": nivel})
    db.flush()
    cache[chave] = instancia
    return instancia


def rodar():
    db = SessionLocal()
    try:
        seed_reference_data(db)
        seed_aplicacoes(db)
        sim = Simulacao(db)

        prod = "Produção"; homol = "Homologação"; dev = "Desenvolvimento"
        crit = "Crítica"; alta = "Alta"; media = "Média"; baixa = "Baixa"

        # ------- Ativos: malha de rede -------
        fw = sim.ativo("fw-edge01", "Equipamento de Rede", prod, crit, descricao="Firewall de borda principal")
        rtr = sim.ativo("rtr-borda01", "Equipamento de Rede", prod, crit, descricao="Roteador de borda com operadora")
        sw1 = sim.ativo("sw-core01", "Equipamento de Rede", prod, crit, descricao="Switch core principal")
        sw2 = sim.ativo("sw-core02", "Equipamento de Rede", prod, alta, descricao="Switch core redundante")
        swacc = sim.ativo("sw-acc01", "Equipamento de Rede", prod, media, descricao="Switch acesso andar 1")
        swdev = sim.ativo("sw-dev01", "Equipamento de Rede", dev, baixa, descricao="Switch rede de desenvolvimento")
        proxy = sim.ativo("proxy-web01", "Servidor Virtual", prod, alta, descricao="Proxy reverso / WAF")
        dns1 = sim.ativo("dns01", "Servidor Virtual", prod, alta, descricao="DNS autoritativo primário")
        dns2 = sim.ativo("dns02", "Servidor Virtual", prod, media, descricao="DNS autoritativo secundário")
        ldap = sim.ativo("dc01", "Servidor Físico", prod, crit, descricao="Domain controller / LDAP (OpenLDAP lacstech.local)")
        ntp = sim.ativo("ntp01", "Servidor Virtual", prod, baixa, descricao="Servidor NTP interno")

        # ------- Ativos: hipervisores e bancos -------
        hyp1 = sim.ativo("hyp-nv01", "Servidor Físico", prod, crit, sor_="RHEL 9", descricao="Hypervisor 1 (Proxmox)")
        hyp2 = sim.ativo("hyp-nv02", "Servidor Físico", prod, crit, sor_="RHEL 9", descricao="Hypervisor 2 (Proxmox)")
        hyp3 = sim.ativo("hyp-nv03", "Servidor Físico", prod, alta, sor_="RHEL 9", descricao="Hypervisor 3 (Proxmox)")
        bk = sim.ativo("srv-bkp01", "Servidor Físico", prod, alta, sor_="Debian 12", descricao="Servidor de backup (Bacula)")

        dbp1 = sim.ativo("db-prod01", "Servidor Virtual", prod, crit, sor_="RHEL 9", descricao="PostgreSQL produção - master")
        dbp2 = sim.ativo("db-prod02", "Servidor Virtual", prod, crit, sor_="RHEL 9", descricao="PostgreSQL produção - réplica")
        dbh = sim.ativo("db-homol01", "Servidor Virtual", homol, media, sor_="RHEL 9", descricao="PostgreSQL homologação")
        dbd = sim.ativo("db-dev01", "Servidor Virtual", dev, baixa, descricao="PostgreSQL desenvolvimento")
        erpdb = sim.ativo("erp-db01", "Servidor Físico", prod, crit, sor_="Windows Server 2022", descricao="MS SQL Server do ERP Protheus")

        # ------- Ativos: aplicações -------
        web1 = sim.ativo("app-web01", "Servidor Virtual", prod, alta, descricao="Nginx + app portal institucional (node 1)")
        web2 = sim.ativo("app-web02", "Servidor Virtual", prod, alta, descricao="Nginx + app portal institucional (node 2)")
        api = sim.ativo("app-api01", "Servidor Virtual", prod, alta, descricao="API de serviços do portal (FastAPI)")
        appsgh = sim.ativo("app-homol01", "Servidor Virtual", homol, media, descricao="Servidor de aplicação homologação")
        sgti = sim.ativo("sgti-app01", "Servidor Virtual", prod, alta, descricao="Aplicação SGTI CMDB (front + backend)")
        erpapp = sim.ativo("erp-app01", "Servidor Virtual", prod, crit, descricao="Protheus AppServer")
        zbx = sim.ativo("zbx-server01", "Servidor Virtual", prod, alta, descricao="Servidor Zabbix principal")

        # ------- Ativos: Kubernetes e containers -------
        k8s1 = sim.ativo("k8s-master01", "Servidor Virtual", prod, alta, descricao="Control plane Kubernetes")
        k8s2 = sim.ativo("k8s-worker01", "Servidor Virtual", prod, alta, descricao="Worker Kubernetes 1")
        k8s3 = sim.ativo("k8s-worker02", "Servidor Virtual", prod, media, descricao="Worker Kubernetes 2")
        ctraf = sim.ativo("ctr-airflow01", "Container", dev, baixa, descricao="Airflow (orquestração de ingestão)")
        ctrcs = sim.ativo("ctr-cassandra01", "Container", prod, media, descricao="Cassandra (métricas de descoberta)")
        ctrni = sim.ativo("ctr-nifi01", "Container", prod, media, descricao="NiFi (ingestão vRNI → CMDB)")

        # ------- Ativos: estações (isoladas, para filtro) -------
        est1 = sim.ativo("est-op-0527", "Estação de Trabalho", prod, baixa, descricao="Estação operações (sem vínculos registrados)")
        est2 = sim.ativo("est-ti-0311", "Estação de Trabalho", dev, baixa, descricao="Estação coordenador TI")

        # ------- IPs de amostra -------
        ips = [
            (rtr, "200.199.10.1"), (fw, "10.0.0.1"), (sw1, "10.0.0.2"), (sw2, "10.0.0.3"),
            (proxy, "10.10.1.5"), (dns1, "10.10.1.11"), (dns2, "10.10.1.12"), (ldap, "10.10.1.20"),
            (hyp1, "10.10.1.31"), (hyp2, "10.10.1.32"), (hyp3, "10.10.1.33"),
            (dbp1, "10.10.2.20"), (dbp2, "10.10.2.21"), (web1, "10.10.3.30"), (web2, "10.10.3.31"),
            (api, "10.10.3.40"), (sgti, "10.10.3.50"), (erpdb, "10.10.4.10"), (erpapp, "10.10.4.11"),
            (zbx, "10.10.1.10"), (k8s1, "10.10.5.10"), (k8s2, "10.10.5.11"), (k8s3, "10.10.5.12"),
            (bk, "10.10.2.99"),
        ]
        for ativo, ip in ips:
            existe = sim.db.query(models.EnderecoIp).filter_by(ativo_id=ativo.id, ip=ip).first()
            if not existe:
                sim.db.add(models.EnderecoIp(ativo_id=ativo.id, ip=ip, interface="eth0", primario=True))

        # ------- Aplicações -------
        portal = sim.db.query(models.Aplicacao).filter_by(sistema="Portal Institucional").first()
        cmdb = sim.db.query(models.Aplicacao).filter_by(sistema="SGTI CMDB").first()
        zabbix = sim.db.query(models.Aplicacao).filter_by(sistema="Sistema de Monitoramento").first()
        portal = portal or sim.aplicacao("Portal Institucional", "Portal web institucional", "Atendimento ao cidadão", "PHP, JavaScript", "PostgreSQL", "COINF", "GOSD")
        cmdb = cmdb or sim.aplicacao("SGTI CMDB", "Gestão de configuração de TI", "Controle de ativos de TI", "Python, Vue", "PostgreSQL", "COINF", "GESIN")
        zabbix = zabbix or sim.aplicacao("Sistema de Monitoramento", "Plataforma Zabbix", "Monitoração de infraestrutura", "C, PHP", "PostgreSQL", "COINF", "GOSD")
        erp = sim.aplicacao("ERP Protheus", "Protheus TOTVS - Gestão", "Folha, financeiro e patrimônio", "AdvPL", "MSSQL", "COINF", "GOSD")
        integracao = sim.aplicacao("Plataforma Integracao", "Camada de integração e ingestão", "ETL de fontes externas (vRNI/Zabbix)", "Python", "Cassandra", "COINF", "CODEV")

        # ------- Infraestrutura: clusters, namespaces, serviços -------
        cl_prod, _ = _get_or_create(sim.db, models.Cluster, {"nome": "k8s-producao"}, {"descricao": "Cluster Kubernetes de produção", "ativo_id": k8s1.id})
        cl_homol, _ = _get_or_create(sim.db, models.Cluster, {"nome": "k8s-homologacao"}, {"descricao": "Cluster Kubernetes homologação", "ativo_id": appsgh.id})
        sim.db.flush()
        for ns, ativo_ns in [("integracao", k8s2), ("web", k8s3)]:
            _get_or_create(sim.db, models.Namespace, {"nome": ns, "cluster_id": cl_prod.id}, {"ativo_id": ativo_ns.id})
        sim.db.flush()

        for nome, tipo, ativo in [
            ("DBAccess", "Banco de dados", erpdb), ("AppServer Protheus", "Aplicação", erpapp),
            ("DBAccess Homolog", "Banco de dados", dbh), ("Zabbix Server", "Aplicação", zbx),
            ("Zabbix Proxy", "Aplicação", proxy), ("Ingestão vRNI", "Integração", ctrni),
            ("Airflow Scheduler", "Aplicação", ctraf), ("Cassandra Metrics", "Banco de dados", ctrcs),
        ]:
            _get_or_create(sim.db, models.Servico, {"nome": nome, "ativo_id": ativo.id}, {"tipo": tipo})

        for nome, desc, ativo in [
            ("Portal ao Cidadão", "Serviço público digital dos cidadãos", web1),
            ("ERP Corporativo", "Gestão empresarial integrada", erpapp),
            ("Monitoramento Continuo", "NOC - observabilidade", zbx),
            ("Gestão de Ativos", "CMDB e mapa de TI", sgti),
            ("Integração de Dados", "Ingestão e reconciliação", k8s2),
        ]:
            _get_or_create(sim.db, models.ServicoNegocio, {"nome": nome}, {"descricao": desc, "ativo_id": ativo.id})

        for app, ativo, porta in [
            (portal, web1, 8080), (portal, web2, 8080), (cmdb, sgti, 5173),
            (zabbix, zbx, 10051), (erp, erpapp, 8010), (integracao, k8s2, 8091),
        ]:
            _get_or_create(sim.db, models.InstanciaAplicacao,
                           {"aplicacao_id": app.id, "ativo_id": ativo.id, "porta": porta},
                           {"path_execucao": f"/opt/{app.sistema.lower().replace(' ', '-')}"})

        # ------- Relacionamentos (grafo) -------
        T = "Conecta-se a"; D = "Depende de"; C = "Contém"
        arestas = [
            (rtr, fw, T, "Link operadora → firewall"),
            (fw, sw1, T, "Firewall → switch core 1"),
            (fw, sw2, T, "Firewall → switch core 2"),
            (sw1, sw2, T, "Uplink de redundância"),
            (sw1, swacc, T, "Distribuição andar 1"),
            (swdev, sw2, T, "Rede de dev → core"),
            (dns1, sw1, T), (dns2, sw1, T), (ldap, sw1, T), (ntp, sw1, T),
            (hyp1, sw1, T), (hyp2, sw1, T), (hyp3, sw2, T),
            (dbp1, sw1, T), (dbp2, sw1, T), (dbh, swacc, T), (dbd, swdev, T),
            (web1, sw1, T), (web2, sw1, T), (api, sw1, T), (sgti, sw1, T),
            (erpdb, sw1, T), (erpapp, sw1, T), (zbx, sw1, T), (bk, sw2, T),
            (k8s1, sw1, T), (k8s2, sw1, T), (k8s3, sw2, T),
            (ctraf, k8s1, C, "Container Airflow na camada de ingestão"),
            (ctrcs, k8s2, C), (ctrni, k8s2, C),
            (web1, hyp1, C), (web2, hyp1, C), (api, hyp2, C), (sgti, hyp2, C),
            (dbp1, hyp1, C), (dbp2, hyp2, C), (dbh, hyp3, C), (dbd, hyp3, C),
            (erpapp, hyp2, C), (erpdb, hyp3, C, "ERP em hypervisor dedicado"),
            (zbx, hyp2, C), (k8s1, hyp1, C), (k8s2, hyp2, C), (k8s3, hyp3, C),
            (proxy, hyp1, C), (dns1, hyp1, C), (dns2, hyp2, C), (ntp, hyp3, C),
            (web1, dbp1, D, "Portal lê e grava no PostgreSQL master"),
            (web2, dbp1, D), (web2, dbp2, D, "Leituras na réplica"),
            (api, dbp1, D, "API acessa base transacional"),
            (api, dns1, D, "Integrações resolvem nomes internos"),
            (sgti, dbp1, D, "SGTI CMDB usa PostgreSQL da produção"),
            (sgti, ldap, D, "Autenticação AD/LDAP"),
            (erpapp, erpdb, D, "AppServer Protheus → DBAccess/MSSQL"),
            (erpapp, ldap, D, "Autenticação usuários ERP"),
            (dbh, appsgh, D, "App homologação usa base homologação"),
            (ctraf, ctrcs, D, "Airflow grava métricas no Cassandra"),
            (ctrni, sgti, D, "NiFi envia descobertas vRNI ao CMDB"),
            (zbx, dbp1, D, "Zabbix persiste no PostgreSQL"),
            (bk, dbp1, D, "Backup lógica do banco master"),
            (bk, erpdb, D, "Backup do MSSQL do ERP"),
            (zbx, dbp2, T, "Checa réplica"),
            (zbx, hyp1, T), (zbx, hyp2, T),
            (proxy, web1, D, "Proxy encaminha ao node 1"),
            (proxy, web2, D, "Proxy encaminha ao node 2"),
        ]
        for o, d, t, *resto in arestas:
            sim.rel(o, d, t, resto[0] if resto else None)

        sim.db.commit()
        resumo = {
            "ativos": sim.db.query(models.Ativo).count(),
            "aplicacoes": sim.db.query(models.Aplicacao).count(),
            "clusters": sim.db.query(models.Cluster).count(),
            "namespaces": sim.db.query(models.Namespace).count(),
            "servicos": sim.db.query(models.Servico).count(),
            "servicos_negocio": sim.db.query(models.ServicoNegocio).count(),
            "instancias": sim.db.query(models.InstanciaAplicacao).count(),
            "ips": sim.db.query(models.EnderecoIp).count(),
            "relacionamentos": sim.db.query(models.Relacionamento).count(),
            "tipos_relacionamento": sim.db.query(models.TipoRelacionamento).count(),
        }
        print("Simulação do Mapa de TI populada:", resumo)
    finally:
        db.close()


if __name__ == "__main__":
    rodar()
