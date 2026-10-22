import base64
import csv
import math
import os
from pathlib import Path
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from motor import Urna, ErroUrna, ESCOLA

BASE=Path(__file__).resolve().parent
DEMO='--teste' in sys.argv
PASTA=BASE / ('dados_teste' if DEMO else 'dados_oficiais')
PASTA.mkdir(exist_ok=True)
# Uma instância por base. O bloqueio é liberado pelo sistema ao fechar ou travar.
LOCK=open(PASTA/'execucao.lock','a+b')
LOCK.seek(0)
LOCK.write(b'0')
LOCK.flush()
LOCK.seek(0)
try:
    if os.name=='nt':
        import msvcrt
        msvcrt.locking(LOCK.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(LOCK,fcntl.LOCK_EX|fcntl.LOCK_NB)
except OSError:
    r=tk.Tk(); r.withdraw()
    messagebox.showerror('Urna já aberta','Feche a outra janela da urna antes de continuar.')
    sys.exit(1)

class App:
    def __init__(self, root):
        self.r=root
        self.u=Urna(PASTA/'urna.sqlite3')
        self.token=None
        self.admin_senha=None
        self.timer=None
        self.refs=[]
        root.title('Urna do Grêmio — '+('TESTE' if DEMO else 'OFICIAL'))
        root.geometry('1100x760')
        root.minsize(900,650)
        root.attributes('-fullscreen', True)
        root.configure(bg='#eef3f8')
        s=ttk.Style(); s.theme_use('clam')
        s.configure('TFrame',background='#eef3f8')
        s.configure('TLabel',background='#eef3f8',foreground='#183048',font=('Segoe UI',13))
        s.configure('Title.TLabel',font=('Segoe UI',24,'bold'))
        s.configure('TButton',font=('Segoe UI',13),padding=12)
        s.configure('Admin.TButton',font=('Segoe UI',13),padding=6)
        s.configure('TEntry',font=('Segoe UI',16),padding=8)
        root.protocol('WM_DELETE_WINDOW',self.sair)
        self.p=ttk.Frame(root,padding=26); self.p.pack(fill='both',expand=True)
        if not self.u.valor('senha'):
            self.inicializar()
        self.inicio()

    def inicializar(self):
        while True:
            senha=simpledialog.askstring('Configuração inicial','Crie a senha da comissão (mínimo 10 caracteres).\nGuarde-a: não há recuperação automática.',show='*',parent=self.r)
            if senha is None: self.r.destroy(); sys.exit(0)
            confirma=simpledialog.askstring('Confirmar senha','Digite novamente:',show='*',parent=self.r)
            if senha!=confirma:
                messagebox.showerror('Senha','As senhas não coincidem.'); continue
            try: self.u.criar_senha(senha); break
            except ErroUrna as e: messagebox.showerror('Senha',str(e))

    def limpar(self, titulo, subtitulo=''):
        if self.timer:
            self.r.after_cancel(self.timer); self.timer=None
        for w in self.p.winfo_children(): w.destroy()
        self.refs=[]
        ttk.Label(self.p,text='SIMULAÇÃO — VOTOS DE TESTE' if DEMO else 'ELEIÇÃO DO GRÊMIO ESTUDANTIL',foreground='#a34408' if DEMO else '#236b76').pack(pady=(0,8))
        ttk.Label(self.p,text=ESCOLA,font=('Segoe UI',16,'bold')).pack()
        ttk.Label(self.p,text=titulo,style='Title.TLabel').pack(pady=(20,8))
        if subtitulo: ttk.Label(self.p,text=subtitulo,wraplength=850,justify='center').pack(pady=(0,14))

    def erro(self,e): messagebox.showerror('Urna do Grêmio',str(e),parent=self.r)

    def senha(self):
        senha=simpledialog.askstring('Comissão eleitoral','Senha da comissão:',show='*',parent=self.r)
        if senha is None: return None
        try: self.u.autenticar(senha); return senha
        except ErroUrna as e: self.erro(e); return None

    def inicio(self):
        self.admin_senha=None
        self.u.cancelar(); self.token=None
        estado=self.u.valor('estado')
        self.limpar('Sua participação faz a diferença','Digite seu RA para acessar as quatro chapas.')
        ttk.Label(self.p,text={'preparacao':'Eleição em preparação','aberta':'Votação aberta','encerrada':'Votação encerrada'}[estado]).pack(pady=12)
        if estado=='aberta':
            ttk.Label(self.p,text='RA completo ou identificador provisório').pack(pady=8)
            self.ra=ttk.Entry(self.p,width=35,font=('Segoe UI',20)); self.ra.pack(pady=8); self.ra.focus_set()
            self.ra.bind('<Return>',lambda e:self.identificar())
            ttk.Button(self.p,text='Continuar',command=self.identificar).pack(pady=12)
        ttk.Button(self.p,text='Área da comissão',command=self.admin_entrar).pack(side='bottom',pady=12)

    def identificar(self):
        try: self.token=self.u.liberar(self.ra.get())
        except ErroUrna as e: self.erro(e); return
        self.ra.delete(0,'end')
        self.escolher()
        self.timer=self.r.after(180000,self.expirar)

    def expirar(self):
        self.inicio()
        messagebox.showinfo('Tempo encerrado','Digite seu RA novamente para começar.',parent=self.r)

    def escolher(self):
        self.limpar('Escolha sua chapa','Clique na chapa desejada. Você poderá conferir e corrigir antes de confirmar.')
        grade=ttk.Frame(self.p); grade.pack(fill='both',expand=True,pady=12)
        for n,nome,img in self.u.chapas():
            f=ttk.Frame(grade,padding=8); f.grid(row=(n-1)//2,column=(n-1)%2,sticky='nsew')
            imagem=None
            if img:
                try:
                    original=tk.PhotoImage(data=base64.b64encode(img))
                    imagem=original.subsample(max(1,math.ceil(original.width()/170)),max(1,math.ceil(original.height()/100)))
                    self.refs.append(imagem)
                except tk.TclError: pass
            b=ttk.Button(f,text=f'{n:02d}  •  {nome}',command=lambda x=n,y=nome:self.confirmar(x,y),compound='top')
            if imagem: b.configure(image=imagem)
            b.pack(fill='both',expand=True)
        for n in (0,1): grade.columnconfigure(n,weight=1); grade.rowconfigure(n,weight=1)
        ttk.Button(self.p,text='Cancelar e voltar ao início',command=self.inicio).pack(pady=8)

    def confirmar(self,n,nome):
        if not messagebox.askyesno('Confirme sua escolha',f'Chapa {n:02d}\n{nome}\n\nConfirmar este voto?\nEscolha Não para corrigir.',parent=self.r): return
        try: self.u.votar(self.token,n)
        except (ErroUrna,sqlite3.Error) as e:
            self.inicio(); self.erro(e); return
        self.token=None
        self.limpar('Voto registrado com sucesso!','Obrigado por participar. Aguarde o retorno à tela inicial.')
        self.timer=self.r.after(3500,self.inicio)

    def admin_entrar(self):
        senha=self.senha()
        if senha is not None:
            self.admin_senha=senha
            self.admin()

    def admin(self):
        self.u.cancelar(); self.token=None
        estado=self.u.valor('estado')
        self.limpar('Comissão eleitoral',f'Situação: {estado}   •   Participações registradas: {self.u.total()}')
        for texto,acao in [('Editar chapas',self.editar),('Abrir votação',lambda:self.estado('aberta')),('Encerrar votação',lambda:self.estado('encerrada')),('Resultado e relatório',self.resultado),('Salvar cópia de segurança',self.backup),('Voltar à identificação',self.inicio),('Fechar programa',self.sair)]:
            ttk.Button(self.p,text=texto,command=acao,style='Admin.TButton').pack(fill='x',padx=170,pady=3)
        self.timer=self.r.after(120000,self.inicio)

    def editar(self):
        if self.u.valor('estado')!='preparacao': self.erro('As chapas ficam bloqueadas após a abertura.'); return
        self.limpar('Configurar as quatro chapas','Imagens opcionais em PNG, até 2 MB e 2000 × 2000 pixels. Sem voto em branco.')
        nomes=[]; imagens=[]
        for n,nome,img in self.u.chapas():
            f=ttk.Frame(self.p); f.pack(fill='x',pady=7)
            ttk.Label(f,text=f'{n:02d}').pack(side='left',padx=10)
            entrada=ttk.Entry(f,width=40); entrada.insert(0,nome); entrada.pack(side='left',fill='x',expand=True)
            nomes.append(entrada); imagens.append(img)
            def carregar(i=n-1):
                caminho=filedialog.askopenfilename(filetypes=[('PNG','*.png')])
                if not caminho: return
                try:
                    data=Path(caminho).read_bytes()
                    if len(data)>2_000_000: raise ErroUrna('A imagem deve ter até 2 MB.')
                    foto=tk.PhotoImage(data=base64.b64encode(data))
                    if max(foto.width(),foto.height())>2000: raise ErroUrna('Use imagem de até 2000 × 2000 pixels.')
                    imagens[i]=data
                    messagebox.showinfo('Imagem','Imagem selecionada. Clique em Salvar para concluir.')
                except (OSError,tk.TclError,ErroUrna) as e: self.erro(e)
            ttk.Button(f,text='Imagem PNG',command=carregar).pack(side='left',padx=8)
        def salvar():
            senha=self.admin_senha
            if senha is None:return
            try: self.u.configurar(senha,[e.get() for e in nomes],imagens); self.admin()
            except ErroUrna as e:self.erro(e)
        ttk.Button(self.p,text='Salvar chapas',command=salvar).pack(pady=15)
        ttk.Button(self.p,text='Voltar sem salvar',command=self.inicio).pack()
        self.timer=self.r.after(180000,self.inicio)

    def estado(self,destino):
        aviso='Abrir a votação? Os nomes e imagens ficarão bloqueados.' if destino=='aberta' else 'Encerrar definitivamente? Não será possível reabrir esta eleição.'
        if not messagebox.askyesno('Confirmar ação',aviso): return
        senha=self.admin_senha
        if senha is None:return
        try: self.u.mudar_estado(senha,destino); self.admin()
        except ErroUrna as e:self.erro(e)

    def resultado(self):
        senha=self.admin_senha
        if senha is None:return
        try: linhas=self.u.resultado(senha)
        except ErroUrna as e:self.erro(e);return
        self.limpar('Resultado da eleição',f'Total: {sum(x[2] for x in linhas)} votos • Sem voto em branco')
        for n,nome,total in linhas:
            ttk.Label(self.p,text=f'{n:02d} — {nome}: {total} voto(s)',font=('Segoe UI',19)).pack(pady=12)
        def exportar():
            destino=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='Resultado_Gremio.csv',filetypes=[('CSV','*.csv')])
            if destino:
                try:
                    with open(destino,'w',encoding='utf-8-sig',newline='') as f:
                        w=csv.writer(f,delimiter=';'); w.writerow([ESCOLA]); w.writerow(['TESTE' if DEMO else 'OFICIAL']);w.writerow(['Número','Chapa','Votos'])
                        for n,nome,v in linhas:
                            # Evita fórmulas ao abrir nomes personalizados em planilhas.
                            w.writerow([n,"'"+nome if nome[:1] in '=+-@\t\r' else nome,v])
                        w.writerow(['','TOTAL',sum(x[2] for x in linhas)])
                    messagebox.showinfo('Relatório','Relatório salvo.')
                except OSError as e:self.erro(e)
        ttk.Button(self.p,text='Exportar relatório CSV',command=exportar).pack(pady=15)
        ttk.Button(self.p,text='Voltar',command=self.inicio).pack()
        self.timer=self.r.after(120000,self.inicio)

    def backup(self):
        senha=self.admin_senha
        if senha is None:return
        destino=filedialog.asksaveasfilename(defaultextension='.sqlite3',initialfile='Backup_Urna.sqlite3',filetypes=[('Banco da urna','*.sqlite3')])
        if destino:
            try: self.u.backup(senha,destino); messagebox.showinfo('Cópia de segurança','Cópia salva. Guarde em local de acesso restrito.')
            except (ErroUrna,OSError,sqlite3.Error) as e:self.erro(e)

    def sair(self):
        if self.senha() is not None:
            self.u.cancelar(); self.r.destroy()

if __name__=='__main__':
    root=tk.Tk()
    App(root)
    root.mainloop()
