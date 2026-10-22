import sqlite3
import tempfile
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from motor import Urna, ErroUrna

SENHA='Teste-seguro-2026'
class Testes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'urna.sqlite3'
        self.u=Urna(self.path)
        self.u.criar_senha(SENHA)
        self.u.mudar_estado(SENHA,'aberta')
    def tearDown(self): self.tmp.cleanup()
    def test_duplicado_reinicio_normalizacao(self):
        t=self.u.liberar('123.456-7'); self.u.votar(t,2)
        nova=Urna(self.path)
        with self.assertRaises(ErroUrna):nova.liberar('1234567')
        self.assertEqual(nova.total(),1)
    def test_abandono_nao_consume(self):
        self.u.liberar('123456'); self.u.cancelar()
        t=self.u.liberar('123456'); self.u.votar(t,1)
        self.assertEqual(self.u.total(),1)
    def test_token_unico(self):
        t=self.u.liberar('123456'); self.u.votar(t,4)
        with self.assertRaises(ErroUrna):self.u.votar(t,4)
        self.assertEqual(self.u.total(),1)
    def test_falha_atomica(self):
        with self.u.conectar() as c:
            c.execute("CREATE TRIGGER falhar BEFORE UPDATE OF votos ON chapas BEGIN SELECT RAISE(ABORT,'falha simulada'); END;")
        t=self.u.liberar('123456')
        with self.assertRaises(sqlite3.DatabaseError):self.u.votar(t,1)
        self.assertEqual(self.u.total(),0)
        with self.u.conectar() as c:
            self.assertEqual(c.execute('SELECT SUM(votos) FROM chapas').fetchone()[0],0)
            c.execute('DROP TRIGGER falhar')
        self.u.votar(self.u.liberar('123456'),1)
        self.assertEqual(self.u.total(),1)
    def test_concorrencia(self):
        a,b=Urna(self.path),Urna(self.path)
        ta=a.liberar('123456');tb=b.liberar('123456')
        def votar(u,t):
            try:u.votar(t,2);return True
            except ErroUrna:return False
        with ThreadPoolExecutor(2) as pool:
            fa=pool.submit(votar,a,ta);fb=pool.submit(votar,b,tb)
            self.assertEqual(sum([fa.result(),fb.result()]),1)
        self.assertEqual(self.u.total(),1)
    def test_sem_branco(self):
        t=self.u.liberar('123456')
        with self.assertRaises(ErroUrna):self.u.votar(t,0)
        self.assertEqual(self.u.total(),0)
    def test_sem_parcial_e_sem_reabertura(self):
        with self.assertRaises(ErroUrna):self.u.resultado(SENHA)
        self.u.mudar_estado(SENHA,'encerrada')
        with self.assertRaises(ErroUrna):self.u.mudar_estado(SENHA,'aberta')
        with self.assertRaises(ErroUrna):self.u.liberar('123456')
    def test_configuracao_bloqueada(self):
        with self.assertRaises(ErroUrna):self.u.configurar(SENHA,['A','B','C','D'],[None]*4)
    def test_senha_incorreta(self):
        with self.assertRaises(ErroUrna):self.u.autenticar('errada')
        self.assertIsNone(self.u.sessao)
    def test_expiracao(self):
        t=self.u.liberar('123456')
        self.u.sessao=(t,'123456',time.monotonic()-1)
        with self.assertRaises(ErroUrna):self.u.votar(t,1)
        self.assertEqual(self.u.total(),0)
    def test_backup(self):
        self.u.votar(self.u.liberar('123456'),3)
        copia=Path(self.tmp.name)/'backup.sqlite3';self.u.backup(SENHA,copia)
        nova=Urna(copia)
        self.assertEqual(nova.total(),1)
        with self.assertRaises(ErroUrna):nova.liberar('123456')
    def test_apuracao(self):
        for ra,chapa in [('1234',1),('5678',2),('9012',2)]:self.u.votar(self.u.liberar(ra),chapa)
        self.u.mudar_estado(SENHA,'encerrada')
        self.assertEqual([r[2] for r in self.u.resultado(SENHA)],[1,2,0,0])
    def test_teste_e_oficial_isolados(self):
        outra=Urna(Path(self.tmp.name)/'outra.sqlite3')
        self.u.votar(self.u.liberar('123456'),1)
        self.assertEqual(outra.total(),0)

if __name__=='__main__':unittest.main(verbosity=2)
