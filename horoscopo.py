import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://hojenobicho.com/horoscopo"

SIGNOS = {
    "aries": {
        "nome": "Áries",
        "periodo": "21/03 a 20/04"
    },
    "touro": {
        "nome": "Touro",
        "periodo": "21/04 a 20/05"
    },
    "gemeos": {
        "nome": "Gêmeos",
        "periodo": "21/05 a 20/06"
    },
    "cancer": {
        "nome": "Câncer",
        "periodo": "21/06 a 21/07"
    },
    "leao": {
        "nome": "Leão",
        "periodo": "22/07 a 22/08"
    },
    "virgem": {
        "nome": "Virgem",
        "periodo": "23/08 a 22/09"
    },
    "libra": {
        "nome": "Libra",
        "periodo": "23/09 a 22/10"
    },
    "escorpiao": {
        "nome": "Escorpião",
        "periodo": "23/10 a 21/11"
    },
    "sagitario": {
        "nome": "Sagitário",
        "periodo": "22/11 a 21/12"
    },
    "capricornio": {
        "nome": "Capricórnio",
        "periodo": "22/12 a 20/01"
    },
    "aquario": {
        "nome": "Aquário",
        "periodo": "21/01 a 19/02"
    },
    "peixes": {
        "nome": "Peixes",
        "periodo": "20/02 a 20/03"
    }
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def limpar_texto(texto):
    if not texto:
        return ""

    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def texto_apos_titulo(soup, titulo):
    elemento = soup.find(
        lambda tag:
            tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
            and titulo.lower() in tag.get_text(" ", strip=True).lower()
    )

    if not elemento:
        return ""

    proximo = elemento.find_next()

    while proximo:
        if proximo.name == "p":
            texto = limpar_texto(proximo.get_text(" ", strip=True))
            if texto:
                return texto

        if proximo.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            break

        proximo = proximo.find_next()

    return ""


def extrair_valor_por_label(soup, label):
    texto_pagina = soup.get_text("\n", strip=True)

    padrao = rf"{re.escape(label)}\s*:?\s*(.+)"
    match = re.search(padrao, texto_pagina, re.IGNORECASE)

    if not match:
        return ""

    valor = limpar_texto(match.group(1))

    return valor


def extrair_dezenas(soup):
    titulo = soup.find(
        lambda tag:
            tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
            and "dezenas pra hoje" in tag.get_text(" ", strip=True).lower()
    )

    dezenas = []

    if titulo:
        bloco = titulo.parent

        if bloco:
            numeros = bloco.find_all(
                lambda tag:
                    tag.name in ["span", "div", "li"]
                    and re.fullmatch(r"\d{2}", tag.get_text(strip=True) or "")
            )

            for numero in numeros:
                dezena = numero.get_text(strip=True)

                if dezena not in dezenas:
                    dezenas.append(dezena)

    if not dezenas:
        texto = soup.get_text(" ", strip=True)
        trecho = re.search(
            r"Dezenas pra Hoje(.{0,300})",
            texto,
            re.IGNORECASE
        )

        if trecho:
            dezenas = re.findall(
                r"\b\d{2}\b",
                trecho.group(1)
            )

    return dezenas[:5]


def extrair_cor(soup):
    titulo = soup.find(
        lambda tag:
            tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
            and "cor do dia" in tag.get_text(" ", strip=True).lower()
    )

    if not titulo:
        return ""

    elemento = titulo.find_next()

    while elemento:
        texto = limpar_texto(elemento.get_text(" ", strip=True))

        if texto and texto.lower() != "cor do dia":
            return texto

        elemento = elemento.find_next()

    return ""


def extrair_info_signo(soup, label):
    texto = soup.get_text("\n", strip=True)

    padrao = rf"{re.escape(label)}\s*:\s*(.+)"
    match = re.search(padrao, texto, re.IGNORECASE)

    if not match:
        return ""

    return limpar_texto(match.group(1))


def coletar_signo(slug, info):
    url = f"{BASE_URL}/{slug}/"

    print(f"Coletando {info['nome']}...")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    previsao = texto_apos_titulo(
        soup,
        "Previsão"
    )

    dezenas = extrair_dezenas(soup)

    cor = extrair_cor(soup)

    elemento = extrair_info_signo(
        soup,
        "Elemento"
    )

    amuletos = extrair_info_signo(
        soup,
        "Amuletos"
    )

    pedraria = extrair_info_signo(
        soup,
        "Pedraria"
    )

    essencias = extrair_info_signo(
        soup,
        "Essências"
    )

    imagem = (
        f"https://hojenobicho.com/"
        f"assets/img/horoscopo/signo/{slug}_300.png"
    )

    return {
        "nome": info["nome"],
        "slug": slug,
        "periodo": info["periodo"],
        "previsao": previsao,
        "dezenas": dezenas,
        "cor": cor,
        "elemento": elemento,
        "amuletos": amuletos,
        "pedraria": pedraria,
        "essencias": essencias,
        "imagem": imagem,
        "fonte": url
    }


def main():
    resultado = {
        "atualizado_em": datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        ),
        "signos": {}
    }

    for slug, info in SIGNOS.items():

        try:
            dados = coletar_signo(
                slug,
                info
            )

            resultado["signos"][slug] = dados

            print(
                f"OK: {info['nome']} "
                f"- {len(dados['dezenas'])} dezenas"
            )

        except Exception as erro:

            print(
                f"ERRO em {info['nome']}: {erro}"
            )

            resultado["signos"][slug] = {
                "nome": info["nome"],
                "slug": slug,
                "periodo": info["periodo"],
                "erro": str(erro)
            }

    os.makedirs(
        "resultado",
        exist_ok=True
    )

    caminho = (
        "resultado/"
        "horoscopo.json"
    )

    with open(
        caminho,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            resultado,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("Arquivo gerado:")
    print(caminho)


if __name__ == "__main__":
    main()
