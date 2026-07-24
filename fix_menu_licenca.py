# -*- coding: utf-8 -*-
"""
fix_menu_licenca.py

Adiciona o item de menu "Licenças NeuraDesk" no dropdown do usuário,
visível só para quem é super_admin.

Idempotente. Faz backup do base.html antes de alterar.
"""
import shutil
import datetime

BASE_HTML_PATH = "/opt/neurabusiness/templates/base.html"


def main():
    with open(BASE_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'listar_licencas_neuradesk' in content:
        print('Patch já aplicado. Nada a fazer.')
        return

    OLD = '''          <li><a class="dropdown-item" href="{{ url_for('listar_usuarios') }}"><i class="fas fa-users-cog me-2 text-info"></i>Usuários</a></li>
          <li><hr class="dropdown-divider" style="border-color:var(--nb-border)"></li>
          {% endif %}'''

    NEW = '''          <li><a class="dropdown-item" href="{{ url_for('listar_usuarios') }}"><i class="fas fa-users-cog me-2 text-info"></i>Usuários</a></li>
          {% endif %}
          {% if current_user and current_user.is_super_admin %}
          <li><a class="dropdown-item" href="{{ url_for('listar_licencas_neuradesk') }}"><i class="fas fa-key me-2" style="color:#f97316"></i>Licenças NeuraDesk</a></li>
          {% endif %}
          {% if session.is_admin %}
          <li><hr class="dropdown-divider" style="border-color:var(--nb-border)"></li>
          {% endif %}'''

    if content.count(OLD) != 1:
        raise SystemExit('ERRO: âncora do menu não encontrada ou duplicada.')

    backup_path = BASE_HTML_PATH + f'.bak_{datetime.datetime.now():%Y%m%d_%H%M%S}'
    shutil.copy2(BASE_HTML_PATH, backup_path)
    print(f'Backup criado em: {backup_path}')

    content = content.replace(OLD, NEW, 1)

    with open(BASE_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print('base.html atualizado com sucesso.')


if __name__ == '__main__':
    main()
