# Urna Eletrônica CIEBP

Aplicativo local para a eleição do grêmio estudantil da **PEI Joaquim Paes de Barros Neto**. Desenvolvido em Python, com interface Tkinter/ttk e banco SQLite.

## Funcionalidades

- Quatro chapas, com nomes e imagens PNG configuráveis antes da abertura.
- Identificação por RA, sem cadastro prévio obrigatório.
- Bloqueio de identificador que já confirmou um voto.
- Sem voto em branco.
- Tela cheia e retorno automático à identificação após votar.
- Senha para entrar na comissão ou fechar a janela.
- Apuração após encerramento, exportação CSV e cópia de segurança.
- Bases independentes para teste e eleição oficial.

## Executar

Requer Python 3 com Tkinter, SQLite e demais bibliotecas padrão. Não requer pacotes pip. O alvo de uso é Windows 10/11.

1. Baixe e extraia os arquivos em uma pasta local.
2. Abra `LEIA_PRIMEIRO.html`.
3. Execute `INICIAR_TESTE.bat` e crie sua senha de teste.
4. Faça uma simulação antes de usar `INICIAR_OFICIAL.bat`.

Alternativamente:

```bash
python urna.py --teste
python urna.py
```

O primeiro comando usa dados de teste. O segundo usa a base oficial. A aplicação funciona offline depois da instalação do Python.

## Organização

| Arquivo | Função |
| --- | --- |
| `urna.py` | Interface gráfica e fluxo de interação |
| `motor.py` | Regras da eleição, senha e persistência |
| `testar_motor.py` | Testes automatizados em bases temporárias |
| `LEIA_PRIMEIRO.html` | Guia completo de operação |

## Testes

```bash
python testar_motor.py
```

A suíte inclui 13 testes de voto repetido, persistência, concorrência, falha de gravação, expiração, apuração e backup. A interface deve ser conferida no computador da escola.

## Segurança e limites

O controle é de um voto por identificador informado. Não existe consulta ao cadastro da Secretaria ou verificação automática de identidade: a comissão precisa conferir a elegibilidade e o RA presencialmente. Identificadores provisórios precisam de controle próprio para evitar que uma pessoa vote com identificadores diferentes.

A participação fica separada dos totais por chapa. O banco grava o RA e incrementa a contagem em uma transação única. A senha usa PBKDF2-SHA256 com sal. O SQLite não é criptografado: proteja o computador e os arquivos. Comparar cópias sucessivas das contagens pode revelar escolhas. Tela cheia não bloqueia atalhos do Windows. Este é um projeto escolar, sem certificação como sistema eleitoral.

**Nunca publique bancos de votação, RAs, senhas, relatórios identificáveis ou backups.** O `.gitignore` ajuda a evitar inclusões acidentais, mas não remove arquivos já rastreados pelo Git e não protege uploads manuais pelo navegador.

## Atualizações

Feche o aplicativo e faça uma cópia de segurança antes de substituir arquivos. Preserve as pastas `dados_oficiais` e `dados_teste`. Nunca apague a base oficial para reiniciar testes.

