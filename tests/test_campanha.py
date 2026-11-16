"""Campanha progressiva: clientes do cadastro e leads, um lote por dia, linha certa e opção de saída."""

from __future__ import annotations

import base64
import gzip
import json
from datetime import date, timedelta
from urllib.parse import unquote

import pytest

from livraria_agentes.campanha import (Campanha, classificar, contactos, importar_leads, lingua_do_numero,
                                       telefone_internacional)
from livraria_agentes.loja import Loja
from livraria_agentes.motor import Motor
from test_agentes import AGORA, ClaudeFalso, _msg, _texto

LEADS = [
    {"id": "seed3-0", "pa": "Moçambique", "org": "Igreja Evangélica Assembleia de Deus da Matola", "t1": "84 111 2222",
     "obs": "WhatsApp publicado", "pr": "ALTA"},
    {"id": "seed3-1", "pa": "Moçambique", "org": "Papelaria Central", "tipo": "Papelaria",
     "wa": "+258 82 333 4444"},
    {"id": "seed3-2", "pa": "Moçambique", "org": "Sr. António", "lk": "https://wa.me/258875556666"},
    {"id": "seed3-3", "pa": "Moçambique", "org": "Arquidiocese", "t1": "+258 21 326 240"},  # fixo, sem prova
    {"id": "seed5-0", "pa": "Essuatíni", "org": "Mpolonjeni Alliance Church", "t1": "+268 7613 0566",
     "obs": "Contacto geral · WhatsApp publicado", "pr": "ALTA"},
    {"id": "seed-0", "pa": "Brasil", "org": "Assembleia de Deus - Caxias", "t1": "(54) 3028-7252",
     "lk": "https://wa.me/5554997084703"},
    {"id": "seed4-0", "pa": "África do Sul", "org": "Bible College of Southern Africa", "wa": "+27 82 000 1111"},
    {"id": "seed2-0", "pa": "RD Congo", "t1": "+243 81 234 5678", "tipo": "Contato WhatsApp CPAD",
     "obs": "Origem: Lista de Clientes Oficial Global · Rótulo salvo no WhatsApp (não é nome de pessoa): Frère Jean"},
]


@pytest.fixture
def loja(tmp_path):
    loja = Loja(tmp_path / "loja.json", relogio=lambda: AGORA)
    loja.dados["cadastro_clientes"] = [
        {"id_erp": "1", "nome": "Igreja Metodista da Matola", "tipo": "Igreja", "whatsapp": ["258847279956"]},
        {"id_erp": "2", "nome": "Ana Macuácua", "tipo": "Cliente VIP", "whatsapp": ["258840000001"]},
        {"id_erp": "3", "nome": "Livraria Fé", "tipo": "Revendedor", "whatsapp": ["258847000002"]},
    ]
    return loja


def test_classifica_e_encontra_o_numero():
    assert classificar("Mpolonjeni Alliance Church") == "Igreja"
    assert classificar("Papelaria Central", "Papelaria") == "Livraria"
    assert classificar("Bible College of Southern Africa") == "Empresa / instituição"
    assert classificar("Sr. António") == "Cliente VIP"
    assert telefone_internacional("(54) 99708-4703", "Brasil") == "5554997084703"
    assert telefone_internacional("https://wa.me/5554997084703", "Brasil") == "5554997084703"
    assert telefone_internacional("+258 21 326 240", "Moçambique") is None  # fixo
    assert telefone_internacional("84 111 2222", "Moçambique") == "258841112222"
    assert [lingua_do_numero(n) for n in ("258841112222", "26876130566", "243812345678")] == ["pt", "en", "fr"]


def test_cada_contacto_vai_para_a_linha_certa(loja):
    por_id = {c["id"]: c for c in contactos(loja, LEADS)}
    assert por_id["cliente-1"]["linha"] == "+258 86 504 8400"  # igreja do cadastro -> Damião
    assert por_id["cliente-3"]["linha"] == "+258 84 508 2787"  # revendedor -> Sérgio
    assert por_id["cliente-2"]["linha"] == "+258 84 468 9369"  # VIP -> retalho
    assert por_id["seed3-0"]["linha"] == "+258 86 504 8400"  # lead de igreja em Moçambique
    assert por_id["seed3-1"]["linha"] == "+258 84 508 2787"  # papelaria -> livrarias e revendedores
    assert por_id["seed3-2"]["linha"] == "+258 84 468 9369"  # lead sem tipo -> VIP / retalho
    assert "seed3-3" not in por_id
    internacional = {i: por_id[i] for i in ("seed5-0", "seed-0", "seed4-0", "seed2-0")}
    assert {c["linha"] for c in internacional.values()} == {"+258 87 712 7070"}
    assert [internacional[i]["tipo"] for i in ("seed5-0", "seed4-0", "seed2-0")] == [
        "Igreja", "Empresa / instituição", "Cliente VIP"]
    assert [c["id"] for c in contactos(loja, LEADS)][:3] == ["cliente-1", "cliente-2", "cliente-3"]


def test_mensagem_na_lingua_do_pais_com_opcao_de_saida(loja):
    por_id = {c["id"]: c for c in contactos(loja, LEADS)}
    from livraria_agentes.campanha import link, mensagem

    assert mensagem(por_id["seed3-0"]).startswith("Paz do Senhor!") and "responda SAIR" in mensagem(por_id["seed3-0"])
    assert "reply STOP" in mensagem(por_id["seed5-0"]) and mensagem(por_id["seed5-0"]).startswith("Blessings")
    assert "répondez STOP" in mensagem(por_id["seed2-0"])
    assert mensagem(por_id["cliente-2"]).startswith("Olá, Ana!")
    assert unquote(link(por_id["seed-0"])).startswith("https://wa.me/5554997084703?text=Paz do Senhor")


def test_um_lote_por_dia_sem_repetir_ate_completar(loja, tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config" / "campanha.json").write_text(json.dumps({"por_linha_por_dia": 1}))
    import livraria_agentes.campanha as campanha_mod

    monkeypatch.setattr(campanha_mod, "_achar", lambda r: tmp_path / r)
    campanha = Campanha(loja, tmp_path / "campanha")
    campanha.arq_leads.write_text(json.dumps(LEADS))
    vistos = []
    for d in range(8):
        lote = campanha.lote(date(2026, 11, 16) + timedelta(days=d))
        assert campanha.lote(date(2026, 11, 16) + timedelta(days=d)) == lote  # o mesmo dia não avança duas vezes
        vistos += [c["id"] for fila in lote["linhas"].values() for c in fila]
    assert len(vistos) == len(set(vistos)) == 10  # todos, sem repetir
    assert all(p["faltam"] == 0 for p in campanha.progresso()["linhas"].values())


def test_quem_responde_sair_sai_da_lista(loja, tmp_path):
    motor = Motor(loja, tmp_path / "c", cliente=ClaudeFalso([]))
    r = motor.responder("258841112222", "SAIR")
    assert r.textos[0].startswith("Está bem, não voltaremos")
    assert "258841112222" not in [c["numero"] for c in contactos(loja, LEADS)]
    assert motor.responder("26876130566", "Stop").textos[0].startswith("Done")


def test_mensagem_da_campanha_enviada_pela_app_nao_cala_o_robo(loja, tmp_path):
    falso = ClaudeFalso([_msg(_texto("Paz do Senhor! Envio já o catálogo."))])
    motor = Motor(loja, tmp_path / "c", cliente=falso)
    assert motor.humano_respondeu_pela_app(
        "258841112222", "Paz do Senhor! Escrevemos da CPAD... Para não receber mais mensagens, responda SAIR.") == "campanha"
    r = motor.responder("258841112222", "Sim, mandem o catálogo")
    assert r.textos == ["Paz do Senhor! Envio já o catálogo."]
    assert "mensagem de apresentação" in falso.chamadas[0][-1]["content"]


def test_pagina_do_dia_com_links(loja, tmp_path):
    campanha = Campanha(loja, tmp_path / "campanha")
    campanha.arq_leads.write_text(json.dumps(LEADS))
    pagina = campanha.pagina(campanha.lote(), "+258 86 504 8400")
    assert "Linha +258 86 504 8400" in pagina and "wa.me/258847279956?text=" in pagina
    assert "+258 84 468 9369" not in pagina


def test_importa_leads_da_pagina_do_erp(tmp_path):
    bloco = lambda dados: base64.b64encode(gzip.compress(json.dumps(dados).encode())).decode()
    pagina = tmp_path / "erp.html"
    pagina.write_text(f'<script id="seed" type="text/plain">{bloco({"L": [LEADS[5]], "EV": []})}</script>'
                      f'<script id="seed2" type="text/plain">{bloco([LEADS[7]])}</script>'
                      f'<script id="seed8" type="text/plain">{bloco([["P1"]])}</script>', encoding="utf-8")
    r = importar_leads(pagina, tmp_path / "leads.json")
    assert r["lidos"] == 2 and r["guardados"] == 2
    guardados = json.loads((tmp_path / "leads.json").read_text())
    assert [g["nome"] for g in guardados] == ["Assembleia de Deus - Caxias", "Frère Jean"]


def test_limpeza_antes_de_guardar():
    from livraria_agentes.campanha import limpar_leads

    partilhado = [{"id": f"x{i}", "pa": "Brasil", "org": f"AD cargo {i}", "lk": "https://wa.me/555132761430"}
                  for i in range(5)]  # central partilhada por 5 registos
    brutos = LEADS + partilhado + [
        {"id": "f1", "pa": "Brasil", "org": "Pastor presidente", "tipo": "Função-alvo de prospecção",
         "lk": "https://wa.me/5511999990000"},
        {"id": "d1", "pa": "Moçambique", "org": "Igreja duplicada", "wa": "+258 82 333 4444"},  # repetido
        {"id": "s1", "pa": "Moçambique", "wa": "+258 84 999 8888"},  # sem nome
    ]
    limpos, saiu = limpar_leads(brutos)
    assert saiu == {"funcao_alvo": 1, "sem_whatsapp_comprovado": 1, "sem_nome": 1, "numero_partilhado": 5,
                    "repetidos": 1}
    numeros = [l["numero"] for l in limpos]
    assert len(numeros) == len(set(numeros)) == 7
    assert "25821326240" not in numeros and "555132761430" not in numeros


def test_rotulos_que_nao_sao_nomes_ficam_de_fora():
    from livraria_agentes.campanha import parece_nome

    bons = ["Pastor Adler Silva - USA", "Irmã - Delaila Cheberte - Zâmbia/ Maputo", "Sandra", "Eva🥰",
            "Irmão Moisés Balamala 87 MOÇAMBIQUE", "CADORE S LDA", "Exata Contabilidade", "Luizardo"]
    maus = ["SBT", "BFC", "Brasil", "95 Faof", "1 Africa Do Sul AP", "daladenizdeniz", "fredericongunza@gmael.co",
            "eliasmanuelchefelix", "", "🙏"]
    assert all(parece_nome(r) for r in bons), [r for r in bons if not parece_nome(r)]
    assert not any(parece_nome(r) for r in maus), [r for r in maus if parece_nome(r)]
