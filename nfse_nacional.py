"""
Integração com o Sistema Nacional NFS-e (Sefin Nacional / ADN) -- emissão de
NFS-e via DPS (Declaração de Prestação de Serviço), assinada digitalmente
com certificado e-CNPJ (A1/A3) e enviada por mTLS.

Fonte da verdade usada aqui: os XSDs OFICIAIS baixados de
https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual
(NFSe-ESQUEMAS_XSD-v1.01) em 26/07/2026 -- a estrutura do XML (nomes de
tag, ordem, tamanhos, enumerações) foi conferida direto neles, não é chute.

O que NÃO dá pra confirmar sem um certificado digital válido em mãos
(testado e confirmado nesta sessão -- até a página de documentação Swagger
do ambiente de homologação recusa conexão sem certificado, é mTLS em toda
a superfície):
  - o formato exato do corpo do POST /nfse (assumido aqui como XML puro,
    baseado na descrição oficial "recepção de um arquivo XML que representa
    a DPS" -- diferente da API de Eventos, que é explicitamente JSON);
  - o algoritmo de assinatura exato aceito (usado aqui RSA-SHA256, padrão
    mais moderno; alguns sistemas legados ainda pedem SHA-1);
  - qualquer erro de validação de negócio que só a Sefin Nacional acusa.
Validar os três pontos acima assim que houver certificado válido pra fazer
o primeiro envio real (começar pelo ambiente de homologação).
"""
import os
import stat
import tempfile
import unicodedata
from datetime import datetime

import requests
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from signxml import XMLSigner, methods

NS = 'http://www.sped.fazenda.gov.br/nfse'
NSMAP = {None: NS}

BASE_URLS = {
    'homologacao': 'https://adn.producaorestrita.nfse.gov.br/contribuintes',
    'producao':    'https://adn.nfse.gov.br/contribuintes',
}


# ─── Lookup de município (IBGE) -- API pública, sem certificado, testável agora ──
def buscar_codigo_municipio_ibge(cidade, uf, timeout=10):
    """Consulta a API pública de Localidades do IBGE (não exige certificado
    nem chave) pra achar o código de 7 dígitos do município a partir do
    nome + UF. Usado pra preencher o município do tomador (cliente) quando
    ele ainda não tem isso cadastrado. Retorna None se não encontrar."""
    if not cidade or not uf:
        return None
    try:
        r = requests.get(
            f'https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf.strip().upper()}/municipios',
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        alvo = _normalizar(cidade)
        for m in r.json():
            if _normalizar(m.get('nome', '')) == alvo:
                return str(m['id'])
    except requests.RequestException:
        return None
    return None


def _normalizar(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode('ascii')
    return s.strip().upper()


def _digitos(s):
    return ''.join(c for c in (s or '') if c.isdigit())


def _sub(pai, tag, texto):
    el = etree.SubElement(pai, f'{{{NS}}}{tag}')
    el.text = str(texto)
    return el


# ─── Montagem do XML da DPS ─────────────────────────────────────────────────
def montar_dps_xml(empresa, cliente, itens, proposta_numero, proposta_titulo, observacao, ambiente=None):
    """Monta o XML (ainda não assinado) da DPS a partir dos dados já
    cadastrados no NeuraBusiness. Retorna (xml_bytes, dps_id, erro) -- erro
    é uma string amigável quando falta alguma config obrigatória.

    `itens`: lista de ItemProposta (ou objetos com .quantidade/.preco_unitario).
    """
    ambiente = ambiente or empresa.nfse_ambiente or 'homologacao'

    if not empresa.nfse_codigo_municipio:
        return None, None, 'Município (código IBGE) da empresa não configurado em /admin/integracoes.'
    if not empresa.nfse_codigo_tributacao_nacional:
        return None, None, 'Código de tributação nacional do serviço não configurado em /admin/integracoes.'

    cnpj = _digitos(empresa.cnpj)
    if len(cnpj) != 14:
        return None, None, f'CNPJ da empresa inválido ou incompleto: {empresa.cnpj!r}'

    if not itens:
        return None, None, 'A proposta não tem itens -- não há o que emitir.'

    numero_dps = (empresa.nfse_ultimo_numero_dps or 0) + 1
    serie_dps = (empresa.nfse_serie_dps or '1').strip() or '1'
    dps_id = f"DPS{empresa.nfse_codigo_municipio}2{cnpj}{serie_dps.zfill(5)}{str(numero_dps).zfill(15)}"

    dh_emi = datetime.now().astimezone().isoformat(timespec='seconds')

    dps = etree.Element(f'{{{NS}}}DPS', nsmap=NSMAP, versao='1.01')
    infDPS = etree.SubElement(dps, f'{{{NS}}}infDPS', Id=dps_id)

    _sub(infDPS, 'tpAmb', '2' if ambiente == 'homologacao' else '1')
    _sub(infDPS, 'dhEmi', dh_emi)
    _sub(infDPS, 'verAplic', 'NeuraBusiness1.0')
    _sub(infDPS, 'serie', serie_dps)
    _sub(infDPS, 'nDPS', str(numero_dps))
    _sub(infDPS, 'dCompet', datetime.now().strftime('%Y-%m-%d'))
    _sub(infDPS, 'tpEmit', '1')  # 1 = Prestador
    _sub(infDPS, 'cLocEmi', empresa.nfse_codigo_municipio)

    # prest (prestador -- a própria Creative)
    prest = etree.SubElement(infDPS, f'{{{NS}}}prest')
    _sub(prest, 'CNPJ', cnpj)
    if empresa.nfse_inscricao_municipal:
        _sub(prest, 'IM', empresa.nfse_inscricao_municipal)
    _sub(prest, 'xNome', (empresa.razao_social or empresa.fantasia)[:300])
    if empresa.telefone:
        _sub(prest, 'fone', _digitos(empresa.telefone))
    if empresa.email:
        _sub(prest, 'email', empresa.email)
    regTrib = etree.SubElement(prest, f'{{{NS}}}regTrib')
    op_simp_nac = {'mei': '2', 'simples_nacional': '3', 'normal': '1'}.get(empresa.nfse_regime_tributario, '2')
    _sub(regTrib, 'opSimpNac', op_simp_nac)
    _sub(regTrib, 'regEspTrib', '0')  # 0 = Nenhum

    # toma (tomador -- o cliente da proposta)
    if cliente:
        toma = etree.SubElement(infDPS, f'{{{NS}}}toma')
        doc_cliente = _digitos(cliente.cpf_cnpj)
        if len(doc_cliente) == 14:
            _sub(toma, 'CNPJ', doc_cliente)
        elif len(doc_cliente) == 11:
            _sub(toma, 'CPF', doc_cliente)
        else:
            _sub(toma, 'cNaoNIF', '1')  # 1 = Dispensado do NIF
        _sub(toma, 'xNome', cliente.nome[:300])
        cmun_cliente = cliente.codigo_municipio_ibge or buscar_codigo_municipio_ibge(cliente.cidade, cliente.estado)
        if cmun_cliente and cliente.cep:
            end = etree.SubElement(toma, f'{{{NS}}}end')
            endNac = etree.SubElement(end, f'{{{NS}}}endNac')
            _sub(endNac, 'cMun', cmun_cliente)
            _sub(endNac, 'CEP', _digitos(cliente.cep))
            _sub(end, 'xLgr', (cliente.endereco or 'Não informado')[:255])
            _sub(end, 'nro', 'S/N')
            _sub(end, 'xBairro', 'Não informado')
        if cliente.email:
            _sub(toma, 'email', cliente.email)

    # serv (serviço prestado)
    serv = etree.SubElement(infDPS, f'{{{NS}}}serv')
    locPrest = etree.SubElement(serv, f'{{{NS}}}locPrest')
    _sub(locPrest, 'cLocPrestacao', empresa.nfse_codigo_municipio)
    cServ = etree.SubElement(serv, f'{{{NS}}}cServ')
    _sub(cServ, 'cTribNac', empresa.nfse_codigo_tributacao_nacional)
    descricao = (observacao or '').strip()
    itens_desc = '; '.join(f'{i.descricao} (qtd {i.quantidade})' for i in itens)[:1500]
    xdesc = f'{proposta_titulo or proposta_numero} -- {itens_desc}'
    if descricao:
        xdesc = f'{xdesc}. Obs: {descricao}'
    _sub(cServ, 'xDescServ', xdesc[:2000])
    if empresa.nfse_cnbs:
        _sub(cServ, 'cNBS', empresa.nfse_cnbs)

    # valores
    valor_total = round(sum((i.quantidade or 0) * (i.preco_unitario or 0) for i in itens), 2)
    valores = etree.SubElement(infDPS, f'{{{NS}}}valores')
    vServPrest = etree.SubElement(valores, f'{{{NS}}}vServPrest')
    _sub(vServPrest, 'vServ', f'{valor_total:.2f}')
    trib = etree.SubElement(valores, f'{{{NS}}}trib')
    tribMun = etree.SubElement(trib, f'{{{NS}}}tribMun')
    _sub(tribMun, 'tribISSQN', '1')   # 1 = Operação tributável
    _sub(tribMun, 'tpRetISSQN', '1')  # 1 = Não retido
    if empresa.nfse_aliquota_iss:
        _sub(tribMun, 'pAliq', f'{empresa.nfse_aliquota_iss:.2f}')
    totTrib = etree.SubElement(trib, f'{{{NS}}}totTrib')
    _sub(totTrib, 'indTotTrib', '0')  # 0 = sem detalhamento de tributos aproximados

    xml_bytes = etree.tostring(dps, xml_declaration=True, encoding='UTF-8', standalone=False)
    return xml_bytes, dps_id, None


# ─── Assinatura digital (XMLDSig) ───────────────────────────────────────────
def assinar_dps_xml(xml_bytes, pfx_bytes, senha, dps_id):
    """Assina a DPS com o certificado do prestador (arquivo .pfx). O
    <Signature> fica como irmão de <infDPS> dentro de <DPS>, referenciando
    o Id do infDPS -- é assim que o schema oficial (TCDPS) exige."""
    chave_privada, certificado, _outros = pkcs12.load_key_and_certificates(
        pfx_bytes, (senha or '').encode('utf-8')
    )
    chave_pem = chave_privada.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    cert_pem = certificado.public_bytes(Encoding.PEM)

    root = etree.fromstring(xml_bytes)
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/2001/10/xml-exc-c14n#',
    )
    assinado = signer.sign(root, key=chave_pem, cert=cert_pem, reference_uri=f'#{dps_id}')
    return etree.tostring(assinado, xml_declaration=True, encoding='UTF-8', standalone=False)


# ─── Envio (mTLS) ────────────────────────────────────────────────────────────
def _certificado_para_arquivos_pem(pfx_bytes, senha):
    """mTLS via `requests` exige caminho de arquivo (não dá pra passar bytes
    em memória) -- grava cert+chave em arquivos temporários só-leitura-dono
    numa pasta privada, pra usar na chamada e apagar logo em seguida."""
    chave_privada, certificado, _outros = pkcs12.load_key_and_certificates(
        pfx_bytes, (senha or '').encode('utf-8')
    )
    pasta = tempfile.mkdtemp(prefix='nfse_cert_')
    os.chmod(pasta, stat.S_IRWXU)
    cert_path = os.path.join(pasta, 'cert.pem')
    key_path = os.path.join(pasta, 'key.pem')
    with open(cert_path, 'wb') as f:
        f.write(certificado.public_bytes(Encoding.PEM))
    with open(key_path, 'wb') as f:
        f.write(chave_privada.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(cert_path, stat.S_IRUSR | stat.S_IWUSR)
    os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    return cert_path, key_path, pasta


def _limpar_arquivos_temp(*paths_e_pasta):
    import shutil
    for p in paths_e_pasta:
        if p and os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)


def emitir_nfse(xml_assinado_bytes, pfx_bytes, senha, ambiente='homologacao', timeout=30):
    """POST /nfse -- envia a DPS assinada. Retorna (nfse_xml_bytes, erro).
    `erro` é um dict {'status_code'/'message', 'body'} quando dá problema."""
    cert_path = key_path = pasta = None
    try:
        cert_path, key_path, pasta = _certificado_para_arquivos_pem(pfx_bytes, senha)
        url = f"{BASE_URLS[ambiente]}/nfse"
        r = requests.post(
            url,
            data=xml_assinado_bytes,
            headers={'Content-Type': 'application/xml'},
            cert=(cert_path, key_path),
            timeout=timeout,
        )
        if r.status_code not in (200, 201):
            return None, {'status_code': r.status_code, 'body': r.text[:2000]}
        return r.content, None
    except requests.RequestException as e:
        return None, {'message': str(e)}
    finally:
        _limpar_arquivos_temp(pasta)


def consultar_nfse(chave_acesso, pfx_bytes, senha, ambiente='homologacao', timeout=20):
    """GET /nfse/{chaveAcesso} -- consulta uma NFS-e já emitida."""
    cert_path = key_path = pasta = None
    try:
        cert_path, key_path, pasta = _certificado_para_arquivos_pem(pfx_bytes, senha)
        url = f"{BASE_URLS[ambiente]}/nfse/{chave_acesso}"
        r = requests.get(url, cert=(cert_path, key_path), timeout=timeout)
        if r.status_code != 200:
            return None, {'status_code': r.status_code, 'body': r.text[:2000]}
        return r.content, None
    except requests.RequestException as e:
        return None, {'message': str(e)}
    finally:
        _limpar_arquivos_temp(pasta)
