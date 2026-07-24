import sys
sys.path.insert(0, '/opt/neurabusiness')
from app import app, db
from models import Empresa, Cliente

CLIENTES = [
  {"nome":"ARLINDO LUIZ DA SILVA JUNIOR","tipo":"PF","cpf_cnpj":"106.741.004-09","endereco":"Rua Emidio Vidal de Negreiros, 711, Planalto 2","cidade":"Mataraca","estado":"PB","cep":"58292000","telefone":"(83) 9 8816-1245","email":""},
  {"nome":"ARQUIDIOCESE DA PARAIBA","tipo":"PJ","cpf_cnpj":"09.140.351/0044-02","endereco":"Praca Dom Adauto, S/N, Centro","cidade":"Joao Pessoa","estado":"PB","cep":"58010670","telefone":"(83) 3133-1000","email":"curia@arquidiocesepb.org.br"},
  {"nome":"ASSOCIACAO DE SUPORTE E BENEFICIOS VEICULAR","tipo":"PJ","cpf_cnpj":"39.487.811/0001-02","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"CAMARA MUNICIPAL DE MAMANGUAPE","tipo":"PJ","cpf_cnpj":"12.720.256/0001-52","endereco":"Rua Coronel Evaristo de Queiros, S/N, Centro","cidade":"Mamanguape","estado":"PB","cep":"58280000","telefone":"(83) 3291-3000","email":""},
  {"nome":"CAMARA MUNICIPAL DE MATARACA","tipo":"PJ","cpf_cnpj":"01.799.815/0001-45","endereco":"Rua Vereador Zeca Bezerra, 1, Planalto II","cidade":"Mataraca","estado":"PB","cep":"58292000","telefone":"(83) 99305-4008","email":""},
  {"nome":"CAMPO ALEGRE AGRICULTURA E COMERCIO LTDA","tipo":"PJ","cpf_cnpj":"04.691.042/0001-77","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"CARDUS ENERGIA LTDA.","tipo":"PJ","cpf_cnpj":"01.843.012/0002-21","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"CONSELHO DA ESCOLA ESTADUAL JOSE AUGUSTO TRINDADE","tipo":"PJ","cpf_cnpj":"01.886.520/0001-06","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"D PADUA - DESTILACAO PRODUCAO AGROINDUSTRIA E COMERCIO SA","tipo":"PJ","cpf_cnpj":"06.312.488/0001-79","endereco":"","cidade":"Rio Tinto","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"FUNDO MUNICIPAL DE SAUDE DE MAMANGUAPE","tipo":"PJ","cpf_cnpj":"08.674.396/0001-64","endereco":"Rua Coronel Evaristo de Queiros, S/N, Centro","cidade":"Mamanguape","estado":"PB","cep":"58280000","telefone":"(83) 3291-3000","email":""},
  {"nome":"FUNDO MUNICIPAL DE SAUDE DE MATARACA","tipo":"PJ","cpf_cnpj":"13.070.749/0001-57","endereco":"Rua Daniel Toscano, 28, Centro","cidade":"Mataraca","estado":"PB","cep":"58292000","telefone":"(83) 9.9302-6220","email":"prefeitura@mataraca.pb.gov.br"},
  {"nome":"INTERCOM IT TECNOLOGIA E SERVICOS LTDA","tipo":"PJ","cpf_cnpj":"35.728.415/0001-60","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"LUANA DREYER","tipo":"PF","cpf_cnpj":"024.006.210-80","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"M.D COMERCIO DE COMBUSTIVEL PLANALTO LTDA","tipo":"PJ","cpf_cnpj":"28.868.323/0001-10","endereco":"","cidade":"Mataraca","estado":"PB","cep":"58292000","telefone":"","email":""},
  {"nome":"MAMANGUAPE - FUNDO MUNICIPAL DE ASSISTENCIA SOCIAL","tipo":"PJ","cpf_cnpj":"14.498.387/0001-62","endereco":"Rua Coronel Evaristo de Queiros, S/N, Centro","cidade":"Mamanguape","estado":"PB","cep":"58280000","telefone":"(83) 3291-3000","email":""},
  {"nome":"MATIAS E RODRIGUES LTDA","tipo":"PJ","cpf_cnpj":"18.654.692/0001-57","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"MIGUEL DA SILVA BASTOS","tipo":"PJ","cpf_cnpj":"04.599.680/0001-62","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
  {"nome":"MUNICIPIO DE ARARA","tipo":"PJ","cpf_cnpj":"08.778.755/0001-23","endereco":"Praca Padre Cicero, S/N, Centro","cidade":"Arara","estado":"PB","cep":"58287000","telefone":"(83) 3286-1144","email":""},
  {"nome":"MUNICIPIO DE CALDAS BRANDAO","tipo":"PJ","cpf_cnpj":"08.809.071/0001-41","endereco":"Rua Sebastiao Marinheiro, S/N, Centro","cidade":"Caldas Brandao","estado":"PB","cep":"58348000","telefone":"(83) 3289-1104","email":""},
  {"nome":"MUNICIPIO DE MAMANGUAPE","tipo":"PJ","cpf_cnpj":"08.898.124/0001-48","endereco":"Praca Cel. Evaristo de Queiros, S/N, Centro","cidade":"Mamanguape","estado":"PB","cep":"58280000","telefone":"(83) 3291-3000","email":""},
  {"nome":"MUNICIPIO DE MATARACA","tipo":"PJ","cpf_cnpj":"08.898.256/0001-70","endereco":"Rua Daniel Toscano, 28, Centro","cidade":"Mataraca","estado":"PB","cep":"58292000","telefone":"(83) 9.9302-6220","email":"prefeitura@mataraca.pb.gov.br"},
  {"nome":"MUNICIPIO DE PEDRO REGIS","tipo":"PJ","cpf_cnpj":"01.612.967/0001-97","endereco":"Rua Jose Rodrigues de Lima, S/N, Centro","cidade":"Pedro Regis","estado":"PB","cep":"58293000","telefone":"(83) 3294-1104","email":""},
  {"nome":"MUNICIPIO DE PILOES","tipo":"PJ","cpf_cnpj":"08.786.626/0001-87","endereco":"Rua Joao Pessoa, S/N, Centro","cidade":"Piloes","estado":"PB","cep":"58337000","telefone":"(83) 3293-1100","email":""},
  {"nome":"MUNICIPIO DE RIO TINTO","tipo":"PJ","cpf_cnpj":"08.899.940/0001-76","endereco":"Praca Marques do Herval, S/N, Centro","cidade":"Rio Tinto","estado":"PB","cep":"58297000","telefone":"(83) 3292-1104","email":""},
  {"nome":"MUNICIPIO DE SAPE","tipo":"PJ","cpf_cnpj":"08.917.080/0001-56","endereco":"Praca Getulio Vargas, S/N, Centro","cidade":"Sape","estado":"PB","cep":"58300000","telefone":"(83) 3263-3000","email":""},
  {"nome":"MUNICIPIO DE SERTAOZINHO","tipo":"PJ","cpf_cnpj":"01.612.771/0001-00","endereco":"Rua Francisco das Chagas, S/N, Centro","cidade":"Sertaozinho","estado":"PB","cep":"58337000","telefone":"(83) 3293-1122","email":""},
  {"nome":"PRO-FE EMPREENDIMENTOS E AGROPASTORIL SA","tipo":"PJ","cpf_cnpj":"04.706.576/0001-20","endereco":"","cidade":"","estado":"PB","cep":"","telefone":"","email":""},
]

with app.app_context():
    emp = Empresa.query.filter_by(cnpj='45.127.220/0001-19').first()
    if not emp:
        print('[ERRO] Empresa nao encontrada!')
        exit(1)
    count = 0
    for c in CLIENTES:
        existe = Cliente.query.filter_by(empresa_id=emp.id, cpf_cnpj=c['cpf_cnpj']).first()
        if not existe:
            db.session.add(Cliente(empresa_id=emp.id, nome=c['nome'], tipo=c['tipo'],
                cpf_cnpj=c['cpf_cnpj'], endereco=c['endereco'], cidade=c['cidade'],
                estado=c['estado'], cep=c['cep'], telefone=c['telefone'], email=c['email']))
            count += 1
    db.session.commit()
    print(f'[OK] {count} clientes importados!')
