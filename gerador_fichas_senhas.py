import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))  # funciona também com PyInstaller
FUNDO_1_A_21 = BASE / "assets" / "fundo_senhas_1_a_21.png"
FUNDO_22_A_30 = BASE / "assets" / "fundo_senhas_22_a_30.png"

DIAS = [
    ("Terça-feira", 0, ["09h00 às 10h30", "14h30 às 16h00"]),
    ("Quarta-feira", 1, ["09h00 às 10h30"]),
    ("Quinta-feira", 2, ["09h00 às 10h30", "14h30 às 16h00"]),
    ("Sexta-feira", 3, ["09h00 às 10h30"]),
]
HORARIOS = ["09h00 às 10h30", "14h30 às 16h00"]   # linhas da grade de checkboxes

COLUNAS = 3
LINHAS_POR_PAGINA = 7
FICHAS_POR_PAGINA = COLUNAS * LINHAS_POR_PAGINA  # 21
TOTAL_SENHAS = 30

# ---- Geometria (em pontos; 1 pt = 1/72 pol) ----
FUNDO_LARGURA = 556.0
FUNDO_ALTURA = 756.5

# A imagem de fundo é centralizada horizontalmente na página A4, de modo que a
# margem em branco da esquerda seja igual à da direita.
LARGURA_PAGINA = A4[0]                                   # 595,28 pt
FUNDO_X = (LARGURA_PAGINA - FUNDO_LARGURA) / 2           # ~19,64 pt

# Centro de cada coluna DENTRO da imagem (medido nos pixels do PNG, 2224 px = 556 pt).
# As três colunas têm espaçamento idêntico (187,5 pt entre elas).
CENTRO_COL_NA_IMAGEM = [90.4, 277.9, 465.4]
# Mesmo centro na página (imagem deslocada para o centro) — usado para data e total
CENTRO_COLUNA = [FUNDO_X + c for c in CENTRO_COL_NA_IMAGEM]

# Linha de base do "SENHA N" de cada uma das 7 linhas, medida do topo da página
BASE_SENHA = [58.75, 166.5, 274.25, 382.5, 490.0, 598.25, 706.25]
# Distância (para baixo) da linha de base do "SENHA N" até os textos azuis
DESCE_DATA = 22.8         # linha "25/10/26 – 09h00 às 10h30"
DESCE_TOTAL = 36.8        # linha "(30 SENHAS)" (14 pt abaixo da anterior)

# Linhas de corte: só entre as colunas (nunca nas laterais da folha)
CORTE_X = [(CENTRO_COLUNA[0] + CENTRO_COLUNA[1]) / 2,    # entre as senhas 1 e 2 (coluna 1|2)
           (CENTRO_COLUNA[1] + CENTRO_COLUNA[2]) / 2]    # entre as senhas 2 e 3 (coluna 2|3)
ALTURA_LINHA_FICHA = 107.75   # altura de cada linha de fichas (pt)
COR_CORTE = colors.HexColor("#D0D0D0")   # cinza bem claro
ESPESSURA_CORTE = 0.25                   # metade da espessura anterior

COR_AZUL = colors.HexColor("#2F5496")
TAMANHO_FONTE = 10


def registrar_fonte():
    """Usa Calibri (a fonte do Word); se não houver, Carlito; senão Helvetica."""
    candidatos = [
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Calibri.ttf",
        "/Library/Fonts/Calibri.ttf",
    ]
    for caminho in candidatos:
        if Path(caminho).exists():
            pdfmetrics.registerFont(TTFont("FonteSenha", caminho))
            return "FonteSenha"
    return "Helvetica"


def carregar_fundo(caminho):
    """Abre o PNG, achata a transparência sobre branco puro e remove os tons
    quase brancos (254) que criavam as linhas fantasma nas laterais e entre colunas."""
    img = Image.open(caminho).convert("RGBA")
    base = Image.new("RGBA", img.size, (255, 255, 255, 255))
    base.alpha_composite(img)
    rgb = base.convert("RGB")
    quase_branco = rgb.convert("L").point(lambda v: 255 if v >= 250 else 0)
    rgb.paste((255, 255, 255), mask=quase_branco)
    return ImageReader(rgb)


def paginas_da_semana(data_terca, selecionados=None):
    """Para cada dia/horário: página 1 = senhas 1-21, página 2 = senhas 22-30.

    `selecionados` é um conjunto de pares (deslocamento_do_dia, horario).
    Se for None, gera todos os horários; senão, só os que estiverem no conjunto.
    """
    if data_terca.weekday() != 1:
        raise ValueError("A data inicial precisa ser uma terça-feira.")
    paginas = []
    for _nome, deslocamento, horarios in DIAS:
        data_atendimento = data_terca + timedelta(days=deslocamento)
        for horario in horarios:
            if selecionados is not None and (deslocamento, horario) not in selecionados:
                continue
            for fundo, quantidade in ((FUNDO_1_A_21, FICHAS_POR_PAGINA),
                                      (FUNDO_22_A_30, TOTAL_SENHAS - FICHAS_POR_PAGINA)):
                paginas.append({"fundo": fundo, "quantidade": quantidade,
                                "data": data_atendimento, "horario": horario})
    return paginas


def gerar_pdf(data_terca, caminho_pdf, selecionados=None):
    for arq in (FUNDO_1_A_21, FUNDO_22_A_30):
        if not arq.exists():
            raise FileNotFoundError(f"Imagem de fundo não encontrada:\n{arq}")

    paginas = paginas_da_semana(data_terca, selecionados)
    if not paginas:
        raise ValueError("Nenhum dia/horário selecionado.")
    fonte = registrar_fonte()
    _largura, altura = A4
    fundos = {p: carregar_fundo(p) for p in (FUNDO_1_A_21, FUNDO_22_A_30)}

    pdf = canvas.Canvas(str(caminho_pdf), pagesize=A4)
    pdf.setTitle(f"Fichas de senhas - semana de {data_terca:%d/%m/%Y}")
    pdf.setAuthor("Gerador de Fichas de Senhas")

    for pagina in paginas:
        # Imagem de fundo: centralizada horizontalmente, colada no topo da página
        pdf.drawImage(fundos[pagina["fundo"]], FUNDO_X, altura - FUNDO_ALTURA,
                      width=FUNDO_LARGURA, height=FUNDO_ALTURA)

        # Linhas de corte verticais entre as colunas (1|2 e 2|3), sem linhas nas laterais
        linhas_usadas = -(-pagina["quantidade"] // COLUNAS)   # arredonda para cima
        base_ultima = BASE_SENHA[linhas_usadas - 1] - BASE_SENHA[0] + ALTURA_LINHA_FICHA
        pdf.setStrokeColor(COR_CORTE)
        pdf.setLineWidth(ESPESSURA_CORTE)
        pdf.setDash(3, 3)   # 3 pt de traço, 3 pt de espaço
        for x in CORTE_X:
            pdf.line(x, altura, x, altura - base_ultima)

        pdf.setFillColor(COR_AZUL)
        pdf.setFont(fonte, TAMANHO_FONTE)
        texto_data = f"{pagina['data']:%d/%m/%y} – {pagina['horario']}"
        for i in range(pagina["quantidade"]):
            linha, coluna = divmod(i, COLUNAS)
            base = BASE_SENHA[linha]
            centro = CENTRO_COLUNA[coluna]
            pdf.drawCentredString(centro, altura - (base + DESCE_DATA), texto_data)
            pdf.drawCentredString(centro, altura - (base + DESCE_TOTAL), "(30 SENHAS)")
        pdf.showPage()
    pdf.save()
    return len(paginas) // 2 * TOTAL_SENHAS, len(paginas)


# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]

COR_TOPO = "#1f3a5f"
COR_FUNDO = "#f4f6f9"
COR_DESTAQUE = "#0078d7"
COR_OK = "#1a7f37"
COR_ERRO = "#b00020"
FONTE = ("Segoe UI", 10)
FONTE_NEGRITO = ("Segoe UI", 10, "bold")


def parse_data(texto):
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def proxima_terca(base=None):
    """Hoje, se for terça-feira; senão, a próxima terça."""
    base = base or date.today()
    return base + timedelta(days=(1 - base.weekday()) % 7)


class SeletorData(tk.Toplevel):
    """Janela 'Escolher data': navegação por mês, dias clicáveis, Limpar e Hoje.
    Qualquer dia pode ser clicado; a validação de 'precisa ser terça' fica
    no botão Gerar PDF. As terças-feiras aparecem em negrito."""

    def __init__(self, master, ancora, inicial, ao_escolher):
        super().__init__(master)
        self.title("Escolher data")
        self.resizable(False, False)
        self.configure(bg="white")
        self.transient(master)
        self.ao_escolher = ao_escolher
        self.inicial = inicial
        self.hoje = date.today()
        self.ano, self.mes = inicial.year, inicial.month

        topo = tk.Frame(self, bg="white")
        topo.pack(fill="x", padx=12, pady=(12, 6))
        tk.Button(topo, text="◄", width=3, relief="solid", bd=1, bg="white",
                  command=lambda: self.mudar_mes(-1)).pack(side="left")
        tk.Button(topo, text="►", width=3, relief="solid", bd=1, bg="white",
                  command=lambda: self.mudar_mes(1)).pack(side="right")
        self.titulo = tk.Label(topo, bg="white", font=("Segoe UI", 12, "bold"))
        self.titulo.pack(expand=True)

        self.corpo = tk.Frame(self, bg="white")
        self.corpo.pack(padx=12, pady=4)

        rodape = tk.Frame(self, bg="white")
        rodape.pack(fill="x", padx=12, pady=(8, 12))
        tk.Button(rodape, text="Limpar", width=10, relief="solid", bd=1, bg="white",
                  command=lambda: self.escolher(None)).pack(side="left")
        tk.Button(rodape, text="Hoje", width=10, relief="solid", bd=1, bg="white",
                  command=lambda: self.escolher(self.hoje)).pack(side="right")

        self.desenhar()

        # abre logo abaixo do campo de data
        self.update_idletasks()
        largura, altura = self.winfo_reqwidth(), self.winfo_reqheight()
        x = ancora.winfo_rootx()
        y = ancora.winfo_rooty() + ancora.winfo_height() + 4
        tela_l, tela_a = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x, tela_l - largura - 10))
        if y + altura > tela_a - 40:
            y = max(0, ancora.winfo_rooty() - altura - 4)
        self.geometry(f"+{x}+{y}")
        self.bind("<Escape>", lambda _e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def mudar_mes(self, delta):
        total = self.mes - 1 + delta
        self.ano += total // 12
        self.mes = total % 12 + 1
        self.desenhar()

    def escolher(self, dia):
        self.ao_escolher(dia)
        self.destroy()

    def desenhar(self):
        for w in self.corpo.winfo_children():
            w.destroy()
        self.titulo.config(text=f"{MESES[self.mes - 1]} de {self.ano}")

        for col, letra in enumerate("DSTQQSS"):
            tk.Label(self.corpo, text=letra, width=4, bg="white",
                     font=FONTE_NEGRITO).grid(row=0, column=col, pady=(0, 4))

        semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(self.ano, self.mes)
        for lin, semana in enumerate(semanas, start=1):
            for col, dia in enumerate(semana):
                selecionado = dia == self.inicial
                do_mes = dia.month == self.mes
                if selecionado:
                    estilo = dict(bg=COR_DESTAQUE, fg="white", activebackground="#005A9E",
                                  activeforeground="white")
                else:
                    estilo = dict(bg="white", fg="black" if do_mes else "#A0A0A0",
                                  activebackground="#CCE4F7")
                if dia == self.hoje and not selecionado:
                    estilo.update(highlightthickness=1, highlightbackground="#555555")
                else:
                    estilo.update(highlightthickness=0)
                # terças-feiras em negrito, para facilitar a escolha
                negrito = selecionado or dia.weekday() == 1
                tk.Button(self.corpo, text=str(dia.day), width=4, relief="flat", bd=0,
                          font=("Segoe UI", 10, "bold" if negrito else "normal"),
                          cursor="hand2", command=lambda d=dia: self.escolher(d), **estilo
                          ).grid(row=lin, column=col, padx=1, pady=1)


class Aplicativo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de Fichas de Senhas")
        self.configure(bg=COR_FUNDO)
        self.resizable(False, False)

        estilo = ttk.Style(self)
        estilo.theme_use("vista" if "vista" in estilo.theme_names() else "clam")
        estilo.configure("Gerar.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 8))
        estilo.configure("TButton", font=FONTE, padding=(10, 5))

        self.var_data = tk.StringVar(value=proxima_terca().strftime("%d/%m/%Y"))
        self.var_resumo = tk.StringVar()
        self.var_aviso = tk.StringVar()
        self.var_status = tk.StringVar()
        self.selecao = {}      # (deslocamento_do_dia, horario) -> BooleanVar
        self.cab_dias = []     # (StringVar do cabeçalho, nome do dia)

        self._montar()
        self.var_data.trace_add("write", lambda *_: self._atualizar_data())
        self._atualizar_data()
        self._atualizar_resumo()
        self._centralizar(720)

    # -- construção da tela --------------------------------------------------
    def _montar(self):
        topo = tk.Frame(self, bg=COR_TOPO)
        topo.pack(fill="x")
        tk.Label(topo, text="Gerador de Fichas de Senhas", bg=COR_TOPO, fg="white",
                 font=("Segoe UI", 22, "bold")).pack(pady=(22, 0))
        tk.Label(topo, text="Atendimentos de confissão", bg=COR_TOPO, fg="#c9d6e8",
                 font=("Segoe UI", 12)).pack(pady=(0, 20))

        corpo = tk.Frame(self, bg=COR_FUNDO)
        corpo.pack(fill="both", expand=True, padx=36, pady=(22, 0))
        corpo.columnconfigure(0, weight=1)

        # 1. Data inicial
        self._rotulo(corpo, "1.  Terça-feira que inicia a semana", 0)
        linha = tk.Frame(corpo, bg=COR_FUNDO)
        linha.grid(row=1, column=0, sticky="w")
        self.entrada = ttk.Entry(linha, textvariable=self.var_data, width=16,
                                 font=("Segoe UI", 11))
        self.entrada.pack(side="left", ipady=3)
        ttk.Button(linha, text="📅", width=4, command=self.abrir_calendario).pack(
            side="left", padx=(6, 0))
        self._dica(corpo, "Digite no formato DD/MM/AAAA ou escolha no calendário "
                          "(as terças aparecem em negrito).", 2)
        self.lbl_aviso = tk.Label(corpo, textvariable=self.var_aviso, bg=COR_FUNDO,
                                  font=FONTE_NEGRITO, anchor="w")
        self.lbl_aviso.grid(row=3, column=0, sticky="w", pady=(4, 0))

        # 2. Confissões (dias x horários)
        self._rotulo(corpo, "2.  Confissões que terão senhas", 4)
        cartao = tk.Frame(corpo, bg="white", highlightthickness=1,
                          highlightbackground="#d9dee5", padx=18, pady=14)
        cartao.grid(row=5, column=0, sticky="ew")

        for col, (nome, _desl, _horarios) in enumerate(DIAS, start=1):
            var = tk.StringVar(value=nome)
            self.cab_dias.append((var, nome))
            tk.Label(cartao, textvariable=var, bg="white", font=FONTE_NEGRITO,
                     justify="center").grid(row=0, column=col, padx=14, pady=(0, 8))
        for col in range(1, len(DIAS) + 1):
            cartao.columnconfigure(col, weight=1)

        for lin, horario in enumerate(HORARIOS, start=1):
            tk.Label(cartao, text=horario, bg="white", font=FONTE).grid(
                row=lin, column=0, sticky="w", padx=(0, 10), pady=4)
            for col, (_nome, deslocamento, horarios) in enumerate(DIAS, start=1):
                if horario in horarios:      # só cria checkbox onde há confissão
                    var = tk.BooleanVar(value=True)
                    self.selecao[(deslocamento, horario)] = var
                    tk.Checkbutton(cartao, variable=var, bg="white", activebackground="white",
                                   cursor="hand2", command=self._atualizar_resumo
                                   ).grid(row=lin, column=col, pady=4)
                else:
                    tk.Label(cartao, text="—", bg="white", fg="#b0b0b0").grid(
                        row=lin, column=col, pady=4)

        self._dica(corpo, "Desmarque o dia/horário em que a confissão foi cancelada.", 6)
        tk.Label(corpo, textvariable=self.var_resumo, bg=COR_FUNDO, fg="#1b1b1b",
                 font=FONTE_NEGRITO, anchor="w").grid(row=7, column=0, sticky="w", pady=(10, 0))

        # Rodapé
        rodape = tk.Frame(self, bg=COR_FUNDO)
        rodape.pack(fill="x", padx=36, pady=(14, 22))
        tk.Label(rodape, textvariable=self.var_status, bg=COR_FUNDO, fg=COR_ERRO,
                 font=FONTE, wraplength=640, justify="left").pack(anchor="w", pady=(0, 8))
        botoes = tk.Frame(rodape, bg=COR_FUNDO)
        botoes.pack(fill="x")
        self.btn_gerar = ttk.Button(botoes, text="Gerar PDF", style="Gerar.TButton",
                                    command=self.gerar)
        self.btn_gerar.pack(side="left")
        ttk.Button(botoes, text="Sair", command=self.destroy).pack(side="right")

    def _rotulo(self, pai, texto, linha):
        tk.Label(pai, text=texto, bg=COR_FUNDO, fg="#1b1b1b",
                 font=("Segoe UI", 11, "bold")).grid(
            row=linha, column=0, sticky="w", pady=(16 if linha else 0, 4))

    def _dica(self, pai, texto, linha):
        tk.Label(pai, text=texto, bg=COR_FUNDO, fg="#666666",
                 font=("Segoe UI", 9)).grid(row=linha, column=0, sticky="w", pady=(3, 0))

    def _centralizar(self, largura):
        self.update_idletasks()
        largura = max(largura, self.winfo_reqwidth())
        altura = self.winfo_reqheight()
        x = (self.winfo_screenwidth() - largura) // 2
        y = max(0, (self.winfo_screenheight() - altura) // 3)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    # -- atualizações dinâmicas ---------------------------------------------
    def _atualizar_data(self):
        texto = self.var_data.get().strip()
        try:
            data = parse_data(texto)
        except ValueError:
            data = None

        if not texto:
            self.var_aviso.set("")
        elif data is None:
            self.var_aviso.set("Digite a data completa: DD/MM/AAAA.")
            self.lbl_aviso.config(fg="#666666")
        elif data.weekday() != 1:
            self.var_aviso.set(f"⚠ {data:%d/%m/%Y} é {DIAS_SEMANA[data.weekday()]}. "
                               "Escolha uma terça-feira.")
            self.lbl_aviso.config(fg=COR_ERRO)
        else:
            sexta = data + timedelta(days=3)
            self.var_aviso.set(f"✔ Terça-feira. Semana de {data:%d/%m} a {sexta:%d/%m}.")
            self.lbl_aviso.config(fg=COR_OK)

        valida = data is not None and data.weekday() == 1
        for (var, nome), (_n, deslocamento, _h) in zip(self.cab_dias, DIAS):
            if valida:
                var.set(f"{nome}\n{data + timedelta(days=deslocamento):%d/%m}")
            else:
                var.set(nome)

    def _atualizar_resumo(self):
        n = sum(1 for var in self.selecao.values() if var.get())
        if n == 0:
            self.var_resumo.set("Nenhum atendimento selecionado.")
        else:
            palavra = "atendimento selecionado" if n == 1 else "atendimentos selecionados"
            self.var_resumo.set(f"{n} {palavra}  →  {n * TOTAL_SENHAS} fichas em {n * 2} páginas "
                                "(senhas 1–21 e 22–30 em cada um)")

    # -- ações ---------------------------------------------------------------
    def abrir_calendario(self):
        try:
            inicial = parse_data(self.var_data.get())
        except ValueError:
            inicial = proxima_terca()
        SeletorData(self, self.entrada, inicial, self.definir_data)

    def definir_data(self, dia):
        self.var_data.set(dia.strftime("%d/%m/%Y") if dia else "")

    def gerar(self):
        self.var_status.set("")
        try:
            data_inicial = parse_data(self.var_data.get())
        except ValueError:
            messagebox.showerror("Data inválida",
                                 "Digite uma data válida no formato DD/MM/AAAA.", parent=self)
            self.entrada.focus_set()
            return
        if data_inicial.weekday() != 1:
            messagebox.showerror("Data inválida",
                                 "A data inicial precisa ser uma terça-feira.", parent=self)
            self.entrada.focus_set()
            return

        selecionados = {chave for chave, var in self.selecao.items() if var.get()}
        if not selecionados:
            messagebox.showerror("Nada selecionado",
                                 "Marque pelo menos um dia/horário de confissão.", parent=self)
            return

        nome = f"fichas_senhas_{data_inicial:%d-%m-%Y}.pdf"
        caminho = filedialog.asksaveasfilename(
            parent=self, title="Salvar PDF das fichas", defaultextension=".pdf",
            initialfile=nome, filetypes=[("Arquivo PDF", "*.pdf")])
        if not caminho:
            return

        self.btn_gerar.state(["disabled"])
        self.var_status.set("Gerando PDF, aguarde...")
        self.update_idletasks()
        try:
            qtd, paginas = gerar_pdf(data_inicial, caminho, selecionados)
        except Exception as erro:
            self.var_status.set("")
            messagebox.showerror("Erro", f"Não foi possível gerar o PDF.\n\n{erro}", parent=self)
            return
        finally:
            self.btn_gerar.state(["!disabled"])

        self.var_status.set("")
        messagebox.showinfo("PDF gerado",
                            f"Arquivo criado!\nFichas: {qtd}\nPáginas: {paginas}\n\n{caminho}",
                            parent=self)


if __name__ == "__main__":
    Aplicativo().mainloop()
