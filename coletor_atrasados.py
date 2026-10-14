#!/usr/bin/env python3
"""Extrator dos rankings publicamente apresentados pelo bichoatrasado.com.

Instalar: pip install -r requirements.txt
Coleta: python coletor_atrasados.py
Uma banca: python coletor_atrasados.py --bancas rio pernambuco
Teste local: python coletor_atrasados.py --arquivo caminho.html --banca rio
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE = 'https://bichoatrasado.com'
BANCAS = {
    'rio': 'PT Rio', 'federal': 'Federal', 'look-goias': 'Look',
    'nacional': 'Nacional', 'loteria-dos-sonhos': 'Loteria dos Sonhos',
    'paraiba': 'Lotep', 'bahia': 'Bahia', 'sao-paulo': 'PT SP',
    'lbr-brasilia': 'LBR', 'minas-gerais': 'Minas',
    'pernambuco': 'Pernambuco', 'rio-grande-do-sul': 'RS', 'sergipe': 'Abaese'
}
COLUNAS = ['banca','pagina','url_fonte','modalidade','posicao','bicho','grupo','dezenas',
           'atraso_sorteios','dias_sem_sair','recorde','media','ultima_data_hora',
           'ultima_milhar','ultima_extracao','ultimo_premio','nivel',
           'atualizacao_fonte','data_coleta']

def texto(tag):
    return tag.get_text(' ', strip=True) if tag else ''

def numero(texto_br):
    m = re.search(r'\d[\d.,]*', texto_br)
    return m.group(0) if m else ''

def html_para_registros(html, slug):
    """Usa estrutura semântica do HTML, em vez de hashes aleatórios de classes Next.js."""
    if slug not in BANCAS:
        raise ValueError(f'Banca desconhecida: {slug}')
    soup = BeautifulSoup(html, 'html.parser')
    artigo = soup.select_one('main article') or soup
    status = artigo.select_one('[class*="StatusLine"]')
    atualizacao = texto(status)
    # Caso o nome da classe mude, a data do JSON-LD pode servir como referência.
    if not atualizacao:
        for script in artigo.select('script[type="application/ld+json"]'):
            try:
                graph = json.loads(script.string or script.get_text()).get('@graph', [])
                pagina = next((x for x in graph if x.get('@type') == 'WebPage'), None)
                if pagina:
                    atualizacao = pagina.get('dateModified', '')
                    break
            except (ValueError, AttributeError):
                pass
    saida = []
    for painel in artigo.select('[role="tabpanel"]'):
        tabid = painel.get('id','').lower()
        if 'painel-cabeca' in tabid:
            modo = 'cabeca'
        elif 'painel-cinco' in tabid:
            modo = 'primeiro_ao_quinto'
        else:
            caption = texto(painel.select_one('caption')).lower()
            modo = 'cabeca' if 'cabeça' in caption or 'cabeca' in caption else 'primeiro_ao_quinto' if '5º' in caption else None
        if not modo:
            continue
        for row in painel.select('tbody tr'):
            cells = row.find_all(['td','th'], recursive=False)
            if len(cells) < 8:
                continue
            nome = texto(cells[1].select_one('[class*="__nome"]'))
            grupo_m = re.search(r'Grupo\s+(\d{1,2})\s*·\s*([\d-]+)', texto(cells[1]), re.I)
            if not nome or not grupo_m:
                raise ValueError(f'Linha incompleta na banca {slug}: {texto(row)[:160]}')
            ultima = cells[6]
            data_hora = texto(ultima.select_one('[class*="__quando"]'))
            data_hora = re.sub(r'^Última:\s*', '', data_hora, flags=re.I)
            detalhe = texto(ultima.select_one('[class*="__sub"]'))
            detalhes = [x.strip() for x in detalhe.split('·')]
            nivel = texto(cells[7].select_one('[data-heat]'))
            saida.append({
                'banca': BANCAS[slug], 'pagina': slug,
                'url_fonte': urljoin(BASE+'/',slug), 'modalidade': modo,
                'posicao': int(numero(texto(cells[0]))), 'bicho': nome,
                'grupo': grupo_m.group(1).zfill(2), 'dezenas': grupo_m.group(2),
                'atraso_sorteios': int(numero(texto(cells[2]))),
                'dias_sem_sair': int(numero(texto(cells[3]))),
                'recorde': int(numero(texto(cells[4]))),
                'media': numero(texto(cells[5])),
                'ultima_data_hora': data_hora,
                'ultima_milhar': detalhes[0] if detalhes else '',
                'ultima_extracao': detalhes[1] if len(detalhes)>1 else '',
                'ultimo_premio': detalhes[2] if len(detalhes)>2 else '',
                'nivel': nivel, 'atualizacao_fonte': atualizacao,
                'data_coleta': datetime.now().astimezone().isoformat(timespec='seconds')
            })
    validar_registros(saida,slug)
    return saida

def validar_registros(registros,slug):
    for modo in ('cabeca','primeiro_ao_quinto'):
        linhas = [r for r in registros if r['modalidade']==modo]
        grupos = {r['grupo'] for r in linhas}
        if len(linhas)!=25 or len(grupos)!=25 or {r['posicao'] for r in linhas}!=set(range(1,26)):
            raise ValueError(f'{slug}: tabela {modo} incompleta ou duplicada: {len(linhas)} linhas, {len(grupos)} grupos')
        if grupos != {f'{x:02d}' for x in range(1,26)}:
            raise ValueError(f'{slug}: grupos ausentes em {modo}')

def criar_sessao():
    s=requests.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; ColetorEstatistico/1.1; +https://bichoatrasado.com/)', 'Accept-Language':'pt-BR,pt;q=0.9'})
    retry=Retry(total=2, backoff_factor=1.0, status_forcelist=[429,500,502,503,504], respect_retry_after_header=True)
    s.mount('https://',HTTPAdapter(max_retries=retry))
    return s

def salvar(saida, erros, pasta):
    pasta.mkdir(parents=True,exist_ok=True)
    with (pasta/'atrasados.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=COLUNAS,delimiter=';')
        writer.writeheader()
        writer.writerows(saida)
    (pasta/'atrasados.json').write_text(json.dumps({'total':len(saida),'dados':saida,'falhas':erros},ensure_ascii=False,indent=2),encoding='utf-8')
    (pasta/'relatorio.json').write_text(json.dumps({'registros':len(saida),'bancas_ok':len({r['pagina'] for r in saida}),'falhas':erros},ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bancas',nargs='+',choices=list(BANCAS),help='Filtrar bancas; padrão: todas as 13')
    parser.add_argument('--arquivo',type=Path,help='Usar HTML previamente salvo em vez de baixar')
    parser.add_argument('--banca',choices=list(BANCAS),help='Banca a que pertence --arquivo')
    parser.add_argument('--saida',type=Path,default=Path('resultado'),help='Pasta de saída')
    parser.add_argument('--espera',type=float,default=2.0,help='Pausa entre páginas, em segundos')
    args=parser.parse_args()
    if args.arquivo and not args.banca:
        parser.error('--arquivo exige --banca')
    if args.espera<0:
        parser.error('--espera não pode ser negativa')
    saida=[]; falhas=[]
    if args.arquivo:
        try:
            html=args.arquivo.read_text(encoding='utf-8-sig')
            saida=html_para_registros(html,args.banca)
            print(f'OK local {BANCAS[args.banca]}: {len(saida)} registros')
        except (OSError,UnicodeError,ValueError) as e:
            falhas.append({'banca':args.banca,'erro':str(e)})
    else:
        session=criar_sessao()
        slugs=args.bancas or list(BANCAS)
        for n,slug in enumerate(slugs):
            if n: time.sleep(args.espera)
            try:
                r=session.get(urljoin(BASE+'/',slug),timeout=(10,30))
                r.raise_for_status()
                items=html_para_registros(r.text,slug)
                saida.extend(items)
                print(f'OK {BANCAS[slug]:22}: {len(items)} registros')
            except (requests.RequestException,ValueError) as e:
                falhas.append({'banca':slug,'erro':str(e)})
                print(f'FALHA {BANCAS[slug]}: {e}',file=sys.stderr)
    salvar(saida,falhas,args.saida)
    print(f'Concluído: {len(saida)} registros, {len(falhas)} falhas. Arquivos em {args.saida.resolve()}')
    return 0 if not falhas else 1

if __name__=='__main__':
    sys.exit(main())
