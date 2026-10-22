"""Urna escolar local. Biblioteca padrão; nenhuma comunicação com a internet."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path

ESCOLA = 'PEI Joaquim Paes de Barros Neto'

class ErroUrna(Exception):
    pass


def normalizar(valor):
    valor = re.sub(r'[ .\-/\s]', '', valor).upper()
    if not re.fullmatch(r'[A-Z0-9]{3,24}', valor):
        raise ErroUrna('Informe de 3 a 24 letras ou números. Inclua o dígito do RA sempre da mesma forma.')
    return valor

class Urna:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.sessao = None
        self.erros = 0
        self.bloqueio = 0
        with self.conectar() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS participantes (ra TEXT PRIMARY KEY) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS chapas (numero INTEGER PRIMARY KEY CHECK(numero BETWEEN 1 AND 4), nome TEXT NOT NULL, imagem BLOB, votos INTEGER NOT NULL DEFAULT 0 CHECK(votos>=0));
            INSERT OR IGNORE INTO config VALUES ('estado','preparacao');
            ''')
            for n in range(1,5):
                c.execute('INSERT OR IGNORE INTO chapas(numero,nome) VALUES (?,?)',(n,f'Chapa {n}'))

    def conectar(self):
        c = sqlite3.connect(self.caminho, timeout=10)
        c.execute('PRAGMA synchronous=FULL')
        return c

    def valor(self, chave):
        with self.conectar() as c:
            r=c.execute('SELECT valor FROM config WHERE chave=?',(chave,)).fetchone()
            return r[0] if r else None

    def criar_senha(self, senha):
        if len(senha)<10:
            raise ErroUrna('Crie uma senha de pelo menos 10 caracteres.')
        sal=secrets.token_hex(16)
        digest=hashlib.pbkdf2_hmac('sha256',senha.encode(),bytes.fromhex(sal),600000).hex()
        with self.conectar() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM config WHERE chave='senha'").fetchone():
                raise ErroUrna('A senha já foi criada.')
            c.executemany('INSERT INTO config VALUES (?,?)',[('sal',sal),('senha',digest)])

    def autenticar(self, senha):
        if time.monotonic()<self.bloqueio:
            raise ErroUrna('Aguarde 30 segundos antes de tentar a senha novamente.')
        sal=self.valor('sal')
        if not sal:
            raise ErroUrna('Configure a senha primeiro.')
        digest=hashlib.pbkdf2_hmac('sha256',senha.encode(),bytes.fromhex(sal),600000).hex()
        if not hmac.compare_digest(digest,self.valor('senha')):
            self.erros+=1
            if self.erros>=5:
                self.bloqueio=time.monotonic()+30
                self.erros=0
            raise ErroUrna('Senha incorreta.')
        self.erros=0

    def chapas(self):
        with self.conectar() as c:
            return c.execute('SELECT numero,nome,imagem FROM chapas ORDER BY numero').fetchall()

    def configurar(self, senha, nomes, imagens):
        self.autenticar(senha)
        if len(nomes)!=4 or any(not n.strip() or len(n.strip())>60 for n in nomes):
            raise ErroUrna('Informe quatro nomes, com até 60 caracteres cada.')
        with self.conectar() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT valor FROM config WHERE chave='estado'").fetchone()[0]!='preparacao':
                raise ErroUrna('As chapas só podem ser alteradas antes da abertura.')
            for n,(nome,img) in enumerate(zip(nomes,imagens),1):
                c.execute('UPDATE chapas SET nome=?,imagem=? WHERE numero=?',(nome.strip(),img,n))

    def mudar_estado(self, senha, destino):
        self.autenticar(senha)
        esperado={'aberta':'preparacao','encerrada':'aberta'}.get(destino)
        if esperado is None:
            raise ErroUrna('Transição inválida.')
        with self.conectar() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute("UPDATE config SET valor=? WHERE chave='estado' AND valor=?",(destino,esperado))
            if r.rowcount!=1:
                raise ErroUrna('Não é possível realizar esta ação no estado atual.')
        self.cancelar()

    def conferir(self, ra):
        ra=normalizar(ra)
        with self.conectar() as c:
            if c.execute("SELECT valor FROM config WHERE chave='estado'").fetchone()[0]!='aberta':
                raise ErroUrna('A votação não está aberta.')
            if c.execute('SELECT 1 FROM participantes WHERE ra=?',(ra,)).fetchone():
                raise ErroUrna('Este RA já participou da votação. Procure a comissão.')
        return ra

    def liberar(self, ra):
        self.cancelar()
        ra=self.conferir(ra)
        token=secrets.token_urlsafe(32)
        self.sessao=(token,ra,time.monotonic()+180)
        return token

    def cancelar(self):
        self.sessao=None

    def votar(self, token, chapa):
        sessao=self.sessao
        self.cancelar()
        if not sessao or not hmac.compare_digest(token,sessao[0]) or time.monotonic()>sessao[2]:
            raise ErroUrna('Sessão expirada. Digite seu RA novamente.')
        if type(chapa) is not int or chapa not in (1,2,3,4):
            raise ErroUrna('Escolha uma das quatro chapas.')
        try:
            with self.conectar() as c:
                c.execute('BEGIN IMMEDIATE')
                if c.execute("SELECT valor FROM config WHERE chave='estado'").fetchone()[0]!='aberta':
                    raise ErroUrna('A eleição foi encerrada.')
                c.execute('INSERT INTO participantes(ra) VALUES (?)',(sessao[1],))
                c.execute('UPDATE chapas SET votos=votos+1 WHERE numero=?',(chapa,))
        except sqlite3.IntegrityError as e:
            if getattr(e, 'sqlite_errorname', '') in ('SQLITE_CONSTRAINT_PRIMARYKEY', 'SQLITE_CONSTRAINT_UNIQUE') and 'participantes.ra' in str(e):
                raise ErroUrna('Este RA já participou da votação.') from None
            raise

    def total(self):
        with self.conectar() as c:
            return c.execute('SELECT COUNT(*) FROM participantes').fetchone()[0]

    def resultado(self, senha):
        self.autenticar(senha)
        with self.conectar() as c:
            if c.execute("SELECT valor FROM config WHERE chave='estado'").fetchone()[0]!='encerrada':
                raise ErroUrna('O resultado só estará disponível após o encerramento.')
            return c.execute('SELECT numero,nome,votos FROM chapas ORDER BY numero').fetchall()

    def backup(self, senha, destino):
        self.autenticar(senha)
        if Path(destino).resolve()==self.caminho.resolve():
            raise ErroUrna('Escolha outro arquivo para a cópia de segurança.')
        origem=self.conectar()
        alvo=sqlite3.connect(destino)
        try:
            origem.backup(alvo)
        finally:
            origem.close()
            alvo.close()
