import tkinter as tk
import tkinter.font as tkFont
import tkinter.ttk as ttk
import tkinter.messagebox as tkMsg
import webbrowser


# Jogar para biblioteca sapilib

class GuiCreateToolTip(object):
    '''
    create a tooltip for a given widget
    '''
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background='#F5F6CE', relief='solid', borderwidth=1,
                       font=("times", "10", "normal"))
        label.pack(ipadx=3)
    def close(self, event=None):
        if self.tw:
            self.tw.destroy()




def gui_sort_treeview(tree, col, descending):
    """sort tree contents when a column header is clicked on"""
    # grab values to sort
    data = [(tree.set(child, col), child) \
        for child in tree.get_children('')]
    # if the data to be sorted is numeric change to float
    #data =  change_numeric(data)
    # now sort the data in place
    data.sort(reverse=descending)
    for ix, item in enumerate(data):
        tree.move(item[1], '', ix)
    # switch the heading so it will sort in the opposite direction
    tree.heading(col, command=lambda col=col: gui_sort_treeview(tree, col, int(not descending)))


# ===============================================================================




class TelaQuesitacao():

    def __init__(self, master, dic_quesitos, solicitacao_exame):

        # Armazena propriedades
        self.master=master
        self.dic_quesitos = dic_quesitos
        self.solicitacao_exame = solicitacao_exame

        # Texto da solicitação de exame
        if self.solicitacao_exame.get('texto_solicitacao', None) is None:
            self.solicitacao_exame['texto_solicitacao'] = "Não foi possível recuperar o texto da solicitação de exame. Consulte documento no SisCrim para compreender o motivo."
        self.solicitacao_exame['texto_solicitacao']=str(self.solicitacao_exame['texto_solicitacao']).strip()

        # Inicializa variáveis
        self.id_quesitacao_escolhida = None
        self.linha_quesito_selecionadas = list()
        
        # Ajusta título
        self.master.title("sapi_laudo: Escolha de quesitação")

        # Frame principal
        self.mainframe = ttk.Frame(master)
        self.mainframe.pack(fill='both', expand=True)
        self.mainframe.pack_propagate(0)

        # Cria notebook
        self.notebook = ttk.Notebook(self.mainframe)

        # Aba principal
        self.frame_principal = self.constroi_frame_principal(self.notebook)
        self.notebook.add(self.frame_principal, text=" Escolha da quesitação ")

        # Aba da solicitação de exame
        self.frame_texto_solicitacao = self.constroi_frame_texto_solicitacao_exame(self.notebook)
        self.notebook.add(self.frame_texto_solicitacao, text=" Texto da Solicitação ")

        # Aba para escolha da quesitacao
        self.frame_quesitacao = self.frame_escolha_quesitacao(self.notebook, dic_quesitos)
        self.notebook.add(self.frame_quesitacao, text=" Quesitações padrão ")

        #
        self.notebook.pack(fill='both', expand=True)

        # Controle de fullscreen
        self.full_screen_state = False
        self.master.bind("<F11>", self.toggle_fullscreen)
        self.master.bind("<Escape>", self.end_fullscreen)

    def toggle_fullscreen(self, event=None):
        self.full_screen_state = not self.full_screen_state  # Just toggling the boolean
        self.master.attributes("-fullscreen", self.full_screen_state)
        return "break"

    def end_fullscreen(self, event=None):
        self.state = False
        self.master.attributes("-fullscreen", False)
        return "break"

    # Constroi frame principal
    def constroi_frame_principal(self, parent):

        # Frame geral
        frame_geral = ttk.Frame(parent)

        # Monta url para exibir árvore no siscrim
        # Todo: Colocar url verdadeira
        self.url_arvore_siscrim = "https://desenvolvimento.ditec.pf.gov.br/sistemas/criminalistica"

        # Dados do documento de solicitação de exame
        frame_aux = ttk.Frame(frame_geral)
        frame_aux.grid(row=10, column=10, padx=10, pady=10, sticky="W")


        # Cria um link para um documento no SisCrim
        url = self.url_arvore_siscrim
        label = tk.Label(frame_aux, text="Memorando 1234/18-SR/DPF/PR",  fg="blue")
        # Coloca underline
        f = tkFont.Font(label, label.cget("font"))
        f.configure(underline=True)
        label.configure(font=f)
        self.label_tooltip1 = GuiCreateToolTip(label, "Clique para abrir árvore do documento no Siscrim")
        #label.bind("<Button-1>", lambda e, url=url: webbrowser.open_new(url))
        label.bind("<Button-1>", self.invocar_url)

        label.grid(row=10, column=10)


        #ttk.Button(frame_aux, text='SisCrim', command=self.abrir_arvore_siscrim).grid(row=10, column=11, sticky="W")

        # Quesitação corrente
        ttk.Label(frame_geral, text="Quesitação escolhida:").grid(row=20, column=10, padx=10, sticky="W")




        self.text_quesitacao_atual = tk.Text(frame_geral, height=15, width=100)
        self.text_quesitacao_atual.grid(row=21, column=10, columnspan=2, padx=15)
        self.text_quesitacao_atual.config(font=("Times new roman", 12), undo=True, wrap='word')
        self.text_quesitacao_atual.configure(background='#E0E0E0')

        self.atualiza_texto_quesitacao_escolhida()

        scrollb = tk.Scrollbar(frame_geral, command=self.text_quesitacao_atual.yview)
        scrollb.grid(row=21, column=11, sticky='nsew')
        self.text_quesitacao_atual['yscrollcommand'] = scrollb.set

        # Botões de ação
        frame_aux = ttk.Frame(frame_geral)
        frame_aux.grid(row=30, column=10, padx=10, pady=10, sticky="W")

        self.botao_confirmar = ttk.Button(frame_aux, text=' Confirmar ', command=self.botao_confirmar_clique)
        self.botao_confirmar.pack(side=tk.LEFT, padx=10)

        self.botao_escolher_quesitacao = ttk.Button(frame_aux, text=' Escolha Manual ', command=self.botao_escolher_quesitacao_clique)
        self.botao_escolher_quesitacao.pack(side=tk.LEFT, padx=10)

        self.botao_escolha_automatica = ttk.Button(frame_aux, text=' Escolha Automática ', command=self.botao_escolha_automatica_clique)
        self.botao_escolha_automatica.pack(side=tk.LEFT, padx=10)
        tooltip1 = GuiCreateToolTip(self.botao_escolha_automatica, "Programa irá buscar a quesitação com maior similaridade")

        self.botao_cancelar = ttk.Button(frame_aux, text=' Cancelar ', command=self.botao_cancelar_clique)
        self.botao_cancelar.pack(side=tk.LEFT, padx=10)

        #
        return frame_geral


    def atualiza_texto_quesitacao_escolhida(self):


        # Habilita alteração
        self.text_quesitacao_atual.config(state=tk.NORMAL)

        # Texto da quesitação atualmente escolhida
        quesitacao_escolhida_texto=""
        if self.id_quesitacao_escolhida is None:
            quesitacao_escolhida_texto=("Você ainda não escolheu a quesitação.\n"
                                            "Dica: Utilize a escolha manual ou escolha automatizada\n")
        else:
            quesitacao_escolhida_texto = self.dic_quesitos[self.id_quesitacao_escolhida]['texto_quesitos']

        # Limpa conteúdo atual, se houver
        self.text_quesitacao_atual.delete(1.0, tk.END)

        print(quesitacao_escolhida_texto)

        # Guarda novo conteúdo
        self.text_quesitacao_atual.insert(tk.END, quesitacao_escolhida_texto)

        # Desabilita alteração
        self.text_quesitacao_atual.config(state=tk.DISABLED)

    def invocar_url(self, e):
        print("invocado", e)
        webbrowser.open_new(self.url_arvore_siscrim)
        webbrowser.open_new(self.url_arvore_siscrim)

    def botao_confirmar_clique(self):
        print("Clicou botao_confirmar_clique")

        if self.id_quesitacao_escolhida is None:
            tkMsg.showerror("Faltou quesitação","Primeiramente você deve escolher uma quesitação")
            return

        # Tudo certo
        self.master.destroy()

    def botao_cancelar_clique(self):
        print("Clicou botao_cancelar_clique")
        self.master.destroy()

    def botao_escolher_quesitacao_clique(self):
        print("Clicou botao_escolher_quesitacao_clique")
        self.notebook.select(self.frame_quesitacao)

    def botao_escolha_automatica_clique(self):
        print("Clicou botao_escolha_automatica_clique")
        if str(self.solicitacao_exame['texto_solicitacao']).strip=="":
            # rrrrr
            tkMsg.showinfo("Aviso", "Não é possível efetuar a escolha de quesitação automaticamente, uma vez que o texto da solicitação de exame não foi recuperado do SisCrim")
            return "break"

        #
        #
        # compara_quesitos_com_solicitacao(texto_solicitacao)
        #
        # # Selecione o melhor quesito
        # # sorted(Gmod_quesitos_respostas, key=itemgetter('age'))
        # menor_taxa_similaridade_aceita = 0.8
        # melhor_taxa_similaridade = menor_taxa_similaridade_aceita
        # k_quesito_similar = None
        # for k_qr in Gmod_quesitos_respostas:
        #     qr = Gmod_quesitos_respostas[k_qr]
        #     taxa_similaridade = qr['taxa_similaridade']
        #     texto_quesitos = qr['texto_quesitos']
        #     if taxa_similaridade > melhor_taxa_similaridade:
        #         melhor_taxa_similaridade = taxa_similaridade
        #         k_quesito_similar = k_qr

    def abrir_arvore_siscrim(self, dummy=0):

        # kkkk
        #webbrowser.open(self.url_arvore_siscrim)
        print("Url invocada:", self.url_arvore_siscrim)


    # Constroi frame para exibição do texto da solicitação de exame
    def constroi_frame_texto_solicitacao_exame(self, parent):

        # Frame geral
        frame_geral = ttk.Frame(parent)

        txt_frm = tk.Frame(frame_geral, width=300, height=300)
        txt_frm.pack(fill="both", expand=True)

        # ensure a consistent GUI size
        txt_frm.grid_propagate(False)
        # implement stretchability
        txt_frm.grid_rowconfigure(1, weight=1)
        txt_frm.grid_columnconfigure(0, weight=1)

        #
        ttk.Label(txt_frm, text="Atenção: O texto extraído abaixo pode conter incorreções, caso o documento tenha passado por algum  algum procedimento de digitalização. Na dúvida, consulte o arquivo em formato PDF no SisCrim.").grid(row=0, column=0, padx=10, pady=10)

        # create uma caixa de texto com scrollbar
        self.txt = tk.Text(txt_frm, borderwidth=3, relief="sunken")
        self.txt.config(font=("Times new roman", 12), undo=True, wrap='word')
        self.txt.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        self.txt.configure(background='#E0E0E0')

        # create a Scrollbar and associate it with txt
        scrollb = tk.Scrollbar(txt_frm, command=self.txt.yview)
        scrollb.grid(row=1, column=1, sticky='nsew')
        self.txt['yscrollcommand'] = scrollb.set

        self.txt.insert(tk.END, self.solicitacao_exame['texto_solicitacao'])
        # Read only
        self.txt.config(state=tk.DISABLED)
        return frame_geral

    # Constrói treview para quesitação
    def frame_escolha_quesitacao(self, parent, dic_quesitos):


        # Inicializa Variáveis
        self.filtro_qtd_quesitos = None
        self.filtro_itemizador = None

        frame = ttk.Frame(parent)

        # Mensagem de aviso
        #msg = ttk.Label(frame, text=s)
        #msg.grid(column=0, row=0)

        frame_aux = ttk.Frame(frame)
        frame_aux.grid(column=0, row=0, sticky="nw")
        linha = 1

        # Processa quesitos e extrai informações relevantes para montagem de filtros
        lista_qtd_quesitos=list()
        for k_q in dic_quesitos:
            quesitacao=dic_quesitos[k_q]
            # Quantidade de quesitos
            quantidade = int(quesitacao['quantidade_quesitos'])
            if quantidade not in lista_qtd_quesitos:
                lista_qtd_quesitos.append(quantidade)


        # Ordena lista de quantidade e quesitos
        lista_qtd_quesitos.sort()
        lista_qtd_quesitos.insert(0, "Qualquer")
        print(lista_qtd_quesitos)

        # Quantidade de quesitos
        coluna=10
        ttk.Label(frame_aux, text="Quantidade de Quesitos:").grid(column=coluna, row=linha)  # 1
        self.number_qtd_quesitos = tk.StringVar()  # 2
        self.combo_qtd_quesitos = ttk.Combobox(frame_aux, width=12, textvariable=self.number_qtd_quesitos, state="readonly")
        self.combo_qtd_quesitos.bind("<<ComboboxSelected>>", self.combo_qtd_quesitos_change)
        self.combo_qtd_quesitos['values'] = lista_qtd_quesitos
        self.combo_qtd_quesitos.current(0)
        self.combo_qtd_quesitos.grid(column=coluna+1, row=linha, pady=10)

        # # Itemizador
        # coluna=20
        # ttk.Label(frame_aux, text="Itemizador:").grid(column=coluna, row=linha)  # 1
        # self.string_itemizador = tk.StringVar()  # 2
        # self.combo_itemizador = ttk.Combobox(frame_aux, width=12, textvariable=self.string_itemizador, state="readonly")
        # self.combo_itemizador.bind("<<ComboboxSelected>>", self.combo_itemizador_change)
        # self.combo_itemizador['values'] = ('Qualquer', "1)", "01)", "1.", "I)")  # 4
        # self.combo_itemizador.current(0)
        # self.combo_itemizador.grid(column=coluna+1, row=linha, pady=10, padx=10)


        # Status da escolha de quesitação
        coluna = 30
        self.status_selecao = ttk.Label(frame_aux, text="")
        self.status_selecao.grid(column=coluna, row=linha)

        # Dicas
        coluna=90
        label = ttk.Label(frame_aux, text="?", font=("times", "16", "bold"))
        label.grid(column=coluna, row=linha)
        label.configure(foreground='blue')
        GuiCreateToolTip(label, ("1) Filtre por quantidade de quesitos.\n"
                                 "2) Filtre por texto quesito, com duplo clique nos que quesitos que são idênticos à solicitação.\n"
                                 "Continue até atingir a quesitação correta (ou mais próxima)."))

        #label.configure(background='black')
        # kkk

        #label = ttk.Label(frame_aux, text="Quantidade de quesitos")
        #label.grid(column=1, row=1, sticky="nw", padx=5)

        #listbox_qtd = tk.Listbox(frame_aux, selectmode=tk.SINGLE)
        #listbox_qtd.grid(column=1, row=2, sticky="nw", padx=5)
        #for item in ["Qualquer", "1", "5", "6"]:
        #    listbox_qtd.insert(tk.END, item)
        #listbox_qtd.select_set(0)

        # label = ttk.Label(frame_aux, text="Tipo de itemizador")
        # label.grid(column=2, row=1, sticky="nw")
        #
        # listbox_itemizador = tk.Listbox(frame_aux, selectmode=tk.SINGLE)
        # listbox_itemizador.grid(column=2, row=2, sticky="nw")
        # for item in ["Qualquer", "1)", "1.", "I)"]:
        #     listbox_itemizador.insert(tk.END, item)
        # listbox_itemizador.select_set(0)


        # Para que serve isto.
        # Aparentemente a que tem peso 1 tem capacidade de expandir
        # Acho que se tiver peso 0 ficará estática
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # treeview
        lista_colunas = ['quesitação', 'quesito']

        #self.trv = ttk.Treeview(frame, columns=lista_colunas, show="headings")
        self.trv = ttk.Treeview(frame, columns=('quesito',), show="headings")
        self.trv.heading(0, text='Quesito')
        #self.trv.bind('<Button-1>', self.treeview_duplo_clique)
        self.trv.bind('<Double-Button-1>', self.treeview_duplo_clique)

        self.trv.configure(
             style="App.Treeview"
            ,height=19
            #,columns=("#1", "#2")
            #,displaycolumns="#1, #2"
            ,selectmode="browse"
        )
        self.trv.grid(column=0, row=2, sticky="nsew")

        # Monta cabeçalho da tabela com opção de classificação
        #for col in lista_colunas:
        #    self.trv.heading(col, text=col.title(),
        #                     command=lambda c=col: gui_sort_treeview(self.trv, c, 0), anchor="w")


        # treeview's scrollbars
        sbar_vertical = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.trv.yview)
        sbar_vertical.grid(column=1, row=2, sticky="ns")
        sbar_horizontal = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.trv.xview)
        sbar_horizontal.grid(column=0, row=3, sticky="we")
        self.trv.configure(yscrollcommand=sbar_vertical.set,
                           xscrollcommand=sbar_horizontal.set)


        # Preenche treeview com dados
        self.popula_tree_view()

        return frame


    def treeview_clique(self, event):
        return

        print(event.y)
        print(self.trv.identify_row(event.y))
        print(event.x)
        print("duplo clique")

        curItem = self.trv.focus()
        print(self.trv.item(curItem))

        # Armazena o id da quesitacao selecionada
        linha_quesito = self.trv.item(curItem)['values'][1]
        print("linha quesito selecionada", linha_quesito)

        # Atualiza filtro por linha de quesito
        if linha_quesito in self.linha_quesito_selecionadas:
            # Se já estava na lista, remove
            self.linha_quesito_selecionadas.remove(linha_quesito)
        else:
            # Se não estava na lista, insere
            self.linha_quesito_selecionadas.append(linha_quesito)

        # Refresh no treeview
        self.popula_tree_view()


    def treeview_duplo_clique(self, event):
        print("x = ", event.x)
        print("y = ", event.y)
        print("row = ", self.trv.identify_row(event.y))
        coluna_clique = self.trv.identify_column(event.x)
        print("column = ", coluna_clique)

        # Depois trocar estes #1 e #2 por um nome
        #if coluna_clique == "#1":
            # Clicou na quesitação

        # Armazena o id da quesitacao selecionada
        curItem = self.trv.focus()
        print(self.trv.item(curItem))

        linha_quesito = self.trv.item(curItem)['values'][0]
        print("linha quesito selecionada", linha_quesito)

        # Atualiza filtro por linha de quesito
        if linha_quesito in self.linha_quesito_selecionadas:
            # Se já estava na lista, remove
            self.linha_quesito_selecionadas.remove(linha_quesito)
        else:
            # Se não estava na lista, insere
            self.linha_quesito_selecionadas.append(linha_quesito)

        # Refresh no treeview
        self.popula_tree_view()



        # curItem = self.trv.focus()
        # print(self.trv.item(curItem))
        #
        # # Armazena o id da quesitacao selecionada
        # self.id_quesitacao_escolhida = self.trv.item(curItem)['values'][0]
        # print("id_quesitacao_escolhida", self.id_quesitacao_escolhida)
        #
        # # Atualiza o texto da quesitação selecionada na tela principal
        # self.atualiza_texto_quesitacao_escolhida()
        #
        # #
        # self.notebook.select(self.frame_principal)


    def popula_tree_view(self):

        # Limpa treeview
        self.trv.delete(*self.trv.get_children())

        # Seleciona as quesitaçõe que contêm TODAS as linhas de quesitos selecionadas
        quesitacoes_selecionadas=list()
        for id_quesitacao in self.dic_quesitos:
            quesitacao=dic_quesitos[id_quesitacao]
            contem_todos = True
            for linha in self.linha_quesito_selecionadas:
                if linha not in quesitacao['texto_quesitos']:
                    # Se linha não está contida na quesitação, ignora
                    contem_todos = False
                    break

            # Se contém todos os quesitos, considera
            if contem_todos:
                quesitacoes_selecionadas.append(id_quesitacao)

        # Seleciona as linhas de quesitos distintas a serem exibidas
        linhas_exibir = list()
        quesitacoes_exibidas = dict()
        for id_quesitacao in self.dic_quesitos:
            quesitacao = dic_quesitos[id_quesitacao]

            # Despreza se não atender filtro de quantidade de quesitos
            if self.filtro_qtd_quesitos is not None and self.filtro_qtd_quesitos!= 'Qualquer':
                if int(quesitacao['quantidade_quesitos']) != int(self.filtro_qtd_quesitos):
                    continue

            # Despreza se houver quesitacoes selecionadas, e esta não for uma delas
            if len(quesitacoes_selecionadas) > 0:
                if id_quesitacao not in quesitacoes_selecionadas:
                    continue

            for linha in quesitacao['texto_quesitos'].split('\n'):
                linha = linha.strip()
                if linha == "":
                    continue

                if linha not in linhas_exibir:
                    linhas_exibir.append(linha)
                    # Inclui no dicionario de quesitacoes exibidas
                    quesitacoes_exibidas[id_quesitacao]=1

        # Ordena linhas a serem exibidas
        linhas_exibir.sort()

        # Insere linhas a serem exibidas no treeview
        col_quesito_max = 0
        for linha in linhas_exibir:

            # Escolhe tag
            tag='nao_selecionado'
            if linha in self.linha_quesito_selecionadas:
                tag='selecionado'

            # Inclui registro
            # Esta sintaxe (linha,) é estranha mas está correta
            # Substituir por (linha) irá dar erro, pois o string será desmembrado
            self.trv.insert('', 'end', values=(linha,) , tags=(tag))

            # Armazena a largura necessária para acomodar a maior linha de quesito
            col_w = tkFont.Font().measure(linha)
            if col_quesito_max<col_w:
                col_quesito_max=col_w

        # Ajusta largura das colunas
        self.trv.column('quesito', width=col_quesito_max)

        # Cor por tag
        self.trv.tag_configure('nao_selecionado', background='')
        self.trv.tag_configure('selecionado', background='#339933', foreground='white')


        # Ajusta o status da seleção
        qtd_quesitacoes = len(quesitacoes_exibidas)
        status="????"
        if qtd_quesitacoes==1:
            status="OK, quesitação única definida"
        elif qtd_quesitacoes>1:
            status="Quantidade de quesitações possíveis: " + str(qtd_quesitacoes) + ". Continue filtrando até restar apenas UMA"

        self.status_selecao['text']=status

        # Chegou na quesitação única
        self.id_quesitacao_escolhida = None
        self.atualiza_texto_quesitacao_escolhida()

        if qtd_quesitacoes == 1:

            # Armazena o id da quesitacao selecionada
            self.id_quesitacao_escolhida = list(quesitacoes_exibidas)[0]
            self.atualiza_texto_quesitacao_escolhida()
            print("id_quesitacao_escolhida", self.id_quesitacao_escolhida)

            # Retorna para a página principal
            self.notebook.select(self.frame_principal)


    def combo_qtd_quesitos_change(self, event):
        self.filtro_qtd_quesitos = self.combo_qtd_quesitos.get()
        print("mudou qtd_quesitos: ",self.filtro_qtd_quesitos)

        # Como mudou quantidade de quesitos, elimina qualquer filtro por linha de quesito
        self.linha_quesito_selecionadas = list()

        # Remonta tabela de quesitos
        self.popula_tree_view()



# Quesitação
quesito1 = '''Blá, blá, blá (um quesito).'''

quesito2 = '''I. Quais as caracteristicas do aparelho?
 II. Quais as chamadas?
 III. Qual a agenda?
 IV. Outros dados julgados úteis.'''

quesito3 = '''1. Quais as caracteristicas do aparelho?
 2. Quais as chamadas?
 3. Qual a agenda?
 4. Outros dados julgados úteis.'''

quesito4 = '''1. Quais as caracteristicas do aparelho?
 2. Quais as chamadas?
 3. Qual a agenda?
 4. Este é um quesito bem longo, que não cabe em uma linha. Logo, terá que quebrar a linha na exibição ou então ter algum mecanismo de scroll para exibir complemente. A linha é grande mesmo, para forçar a quebra. Não pode caber em uma única linha de tela. Ok, final do quesito.
 5. Outros dados julgados úteis.'''

dic_quesitos=dict()
dic_quesitos['495845086ba01']=quesito1
dic_quesitos['9645449585a02']=quesito2
dic_quesitos['353479086ba03']=quesito3
dic_quesitos['9854985f6ba04']=quesito4



texto_solicitacao='''
Memorando 1234/2018-SR/DPF/PR

linha 00
linha 01
linha 02
linha 03
linha 04
linha 05
linha 06
linha 07
linha 08
linha 09
linha 10
linha 11
linha 12
linha 13
linha 14
linha 15
linha 16
linha 17
linha 18
linha 19
linha 20
Uma linha bem comprida aqui, para ver como está se comportando. O comportamento esperado é que permita scroll. Mas se quebrar também não tem problema. O que não pode é fazer um truncamento na linha. Vamos ver o que acontece. fim da linha.
linha 01
linha 02
linha 03
linha 04
linha 05
linha 06
linha 07
linha 08
linha 09
linha 00
linha 01
linha 02
linha 03
linha 04
linha 05
linha 06
linha 07
linha 08
linha 09
linha 01
linha 02
linha 03
linha 04
linha 05
linha 06
linha 07
linha 08
linha 09
linha 00
linha 01
linha 02
linha 03
linha 04
linha 05
linha 06
linha 07
linha 08
linha 09
linha 00
ultima linha

'''


solicitacao_exame = {
    'materiais': [],
    'solicitacao': {   'ano_protocolo': '2017',
                       'ano_registro': '2017',
                       'ano_registro_relevante': '2017',
                       'assunto': 'ENC. 02 APARELHOS DE CELULARES PARA '
                                  'PERÍCIA.',
                       'auto_apreensao': 'apreensao -',
                       'codigo_area_exame': '2496',
                       'codigo_complexidade': '11940414',
                       'codigo_documento_externo': '32455761',
                       'codigo_finalidade_documento': '1',
                       'codigo_grupo_responsavel': '1590236',
                       'codigo_procedimento': '32455760',
                       'codigo_situacao_documento': '9651963',
                       'codigo_sujeito_posse': '1590545',
                       'codigo_titulo_exame': '9173257',
                       'codigo_unidade_posse': '3547',
                       'codigo_unidade_registro': '3547',
                       'dados_exame': {   'alvo': 'em poder de RENATO BATISTA '
                                                  'DE ALMEIDA (ITEM 09) e '
                                                  'ROSANGELA DIAS DINIZ (item '
                                                  '10)',
                                          'codigo_solicitacao_exame_siscrim': '32455761',
                                          'codigo_sujeito_exame': '4409939',
                                          'codigo_sujeito_posse': '4409939',
                                          'codigo_unidade_exame': '3547',
                                          'codigo_unidade_posse': '3547',
                                          'equipe': '-',
                                          'identificacao_solicitacao_exame_siscrim': 'Memorando '
                                                                                     '371/2017-SR/PF/PR',
                                          'iped_tipo': 'iped-ocr',
                                          'lista_itens': '10:163/2017, '
                                                         '9:163/2017',
                                          'local_armazenamento': 'gtpi-sto-02',
                                          'matricula_sujeito_posse': '17654',
                                          'metodo_entrega': 'entrega_DVD',
                                          'nome_guerra_sujeito_posse': 'Dante',
                                          'nome_sujeito_posse': 'Dante Luiz '
                                                                'Pippi Filho',
                                          'numero_auto': '-',
                                          'operacao_sintetico': '-',
                                          'precedencia': '5',
                                          'processamento_opcoes': None,
                                          'tipo_auto': 'apreensao'},
                       'data_despachado_funcionario': '2017-06-30',
                       'data_limite': None,
                       'data_protocolo': '2017-01-24',
                       'data_registro_mais_antigo': '2017-01-24',
                       'data_registro_relevante': '2017-01-24',
                       'data_ultima_operacao': '2017-06-30',
                       'equipe_busca': '-',
                       'identificacao': 'Memorando 371/2017-SR/PF/PR',
                       'local_busca': 'em poder de RENATO BATISTA DE ALMEIDA '
                                      '(ITEM 09) e ROSANGELA DIAS DINIZ (item '
                                      '10)',
                       'memorando_simplificado': 'Memorando 371-17',
                       'motivo_urgencia': None,
                       'nome_area_exame': 'Informática',
                       'nome_curto_sujeito_posse': 'Arquivo/SETEC/PR',
                       'nome_finalidade': 'Solicitação de exame',
                       'nome_signatario': 'ALESSANDRO RICARDO SILVA',
                       'nome_titulo_area': 'Laudo de Exame de Equipamento '
                                           'Computacional Portátil',
                       'numero_copia': '0',
                       'numero_protocolo': '209',
                       'numero_registro': '209',
                       'numero_registro_relevante': '209',
                       'operacao': '-',
                       'pasta_memorando': 'Memorando_371-2017-SR-PF-PR',
                       'procedimento_aquisicao': None,
                       'procedimento_numero': '062/2017',
                       'procedimento_sigla_orgao': 'SR/PF/PR',
                       'protocolo': '209/2017',
                       'quantidade_itens_indefinidos': 0,
                       'quantidade_itens_para_exame': 0,
                       'quantidade_itens_total': 0,
                       'recebido': 't',
                       'situacao_justificativa': None,
                       'solicitacao': 'Memorando 371/2017-SR/PF/PR Protocolo '
                                      'Setec: 209/2017',
                       'tipo_sujeito_posse': '2',
                       'urgencia': '1'},
    'texto_solicitacao': 'p 0209/17-SETEC/P                 ID17-0134\n'
                         '\n'
                         '\n'
                         '"laterial\n'
                         '                                                                                         '
                         'SR/PF/PR\n'
                         '163/17   telefone celular.2\n'
                         '                                                                                         '
                         'Fl:\n'
                         '                                                                                         '
                         'Rub:\n'
                         '\n'
                         '\n'
                         'Memorando   371/17-SR/PF/PR\n'
                         '\n'
                         '                                   SLKVIÇO PUBLICO '
                         'FEDERAL\n'
                         '                                   MJ - POLÍCIA '
                         'FEDERAL\n'
                         '                          SUPERINTENDÊNCIA REGIONAL '
                         'NO PARANÁ\n'
                         '\n'
                         '\n'
                         'Memorando n° 0371/2017 - IPL 0062/2017-4 SR/PF/PR\n'
                         '\n'
                         '                                                                      '
                         'Em 23 de janeiro de 2017.\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         'Ao(ÀjSenhor(a)Chefe do SETEC/SR/PF/PR.\n'
                         '\n'
                         '\n'
                         '\n'
                         'Assunto: Solicitação de exame pericial em telefone '
                         'celular.\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                  De ordem de GASTÃO SCHEFER NETO, '
                         'Delegado de Polícia Federal, a\n'
                         'fim de instruir os autos do Inquérito Policial n° '
                         '0062/2017-4-SR/PF/PR, encaminho a\n'
                         'Vossa Senhoria O(S) telefone^) celulares) e '
                         'cartãQões) SIM relacionadO(s) no Auto de\n'
                         'Apresentação e Apreensão (itens 09 e 10), cópia '
                         'anexa, arrecadado(s) em poder de\n'
                         'RENATO BATISTA DE ALMEIDA (ITEM 09) e ROSÂNGELA DIAS '
                         'DINIZ (item 10),\n'
                         'solicitando a elaboração de Laudo de Exame em '
                         'Telefone Celular, devendo os;as)\n'
                         'senhores;as)peritos;as)designados;as)responderem aos '
                         'seguintes quesitos:\n'
                         '\n'
                         '\n'
                         '                   1.   Qual a natureza e '
                         'características dO(S)materia(ais)SubmetidO(S)a '
                         'exame?\n'
                         '                   2.   Quais os números telefônicos '
                         'de habilitação associados?\n'
                         '                   3.   Quais os registros '
                         'correspondentes às chamadas               '
                         'telefônicas\n'
                         'recebidas, efetuadas e não atendidas?\n'
                         '             4. Quais os registros constantes '
                         'da(S)agenda(S)telefônica(S)?\n'
                         '             5. Extrair os dados e metadados '
                         'relativos às comunicações eletrônicas\n'
                         '(por exemplo WhatsApp) eventualmente armazenadas nos '
                         'dispositivos informáticos,\n'
                         'devendo a apresentação destes dados ser em formato '
                         'de texto legível e navegável.\n'
                         '                   6.   Outros dados julgados '
                         'úteis.\n'
                         '\n'
                         '\n'
                         '\n'
                         '                    Atenciosamente,\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                                  ALESSANDRO RICARDO '
                         'SILVA\n'
                         '                                      Escrivão de '
                         'Polícia Federal\n'
                         '                                    2a Classe - '
                         'Matrícula n° 18.039\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         ' IPL N° 0062/2017\n'
                         '\x0c'
                         '                                                                                            '
                         'SR/PF/PR\n'
                         '                                                                                            '
                         'Fl:\n'
                         '                                                                                            '
                         'Rub:\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                            SERVIÇO PÚBLICO FEDERAL\n'
                         '                               MJ - POLÍCIA FEDERAL\n'
                         '                      SUPERINTENDÊNCIA REGIONAL NO '
                         'PARANÁ\n'
                         '\n'
                         '                 AUTO CIRCUNSTANCIADO DE BUSCA E '
                         'APREENSÃO\n'
                         '\n'
                         'Ao(S) 19    dia(s)   do   mês    de janeiro de '
                         '2017,      nesta   cidade   de   Curitiba/PR,      '
                         'em\n'
                         'cumprimento ao Mandado de Busca e Apreensão, exarado '
                         'pelo MM Juiz da 23a Vara\n'
                         'Federal  de    CuritibaVPR  (cópia  anexa),     '
                         'nos    autos  do   processo    n°\n'
                         '5000197-71.2017.4.04.7000 esta equipe policial '
                         'chefiada peto Delegado^ de Policia\n'
                         'Federal GASTÂO SCHEFER NETO e composta pelo EPF '
                         'ALESSANDRO,                                 APFs\n'
                         ' AfApRüftPi                      Ar\\/\\ Lf\\        '
                         'e    C{ C£da                  compareceu no\n'
                         'endereço      declinado     no    documento     '
                         'supramencionado,        sendo    recebidos        '
                         'por\n'
                         'ff fc~/WT0           9) A-n £"Th pç          foi Me, '
                         'DA      portador      da      Cédula          de\n'
                         'Identidade/CPF n°         R6     JJ^âS3 64C\n'
                         'proprietário/morador do imóvel. Na oportunidade, o '
                         'chefe da equipe procedeu à leitura\n'
                         'do Mandado, tendo o mesmo franqueado o acesso aos '
                         'policiais, que deram integral\n'
                         'cumprimento à determinação             judicial, '
                         'logrando êxito em arrecadar e apreender o\n'
                         'seguinte:\n'
                         '\n'
                         '\n'
                         '\n'
                         '                                 DESCRJÇAQ DO '
                         'MATERIAL APREEENDIDO\n'
                         '\x0c'
                         '                                                                               '
                         'SR/PF/PR\n'
                         '                                                                              '
                         '1 Fl:\n'
                         '                                                                               '
                         'Rub:\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                            SERVIÇO PUBLICO FEDERAL\n'
                         '                             MJ - POLÍCIA FEDERAL\n'
                         '                    SUPERINTENDÊNCIA REGIONAL NO '
                         'PARANÁ\n'
                         '\n'
                         '                   Qjxk JJLecsn noJKx <Wà\n'
                         '                                                     '
                         '*ndQ ArrvT. C#~v0 OT, -ns\n'
                         '\n'
                         '\n'
                         '\n'
                         '                   °i fA/K4, 3smior+ irem\n'
                         '\n'
                         '\n'
                         '\n'
                         '  '
                         'ÀA                                                                                      '
                         ',\n'
                         '   A\n'
                         '                                                 V\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                                                                                          '
                         '■\n'
                         'Nada mais havendo^"«çr consignado, é encerrado o '
                         'presente que, depois de lido e achado\n'
                         'conforme, vai devidamente assir\n'
                         '\n'
                         '\n'
                         '\n'
                         'CHEFE DA EQUIPE:\n'
                         '\n'
                         '\n'
                         '\n'
                         'PROPRIETÁRIO/MORADOR ÒO IM0VEL:\n'
                         '\n'
                         '\n'
                         '\n'
                         '\n'
                         '                                        , fl.G Í3 '
                         '03c? 6 6=2\n'
                         '      4/.\n'
                         '\n'
                         ' IPLN" 2324/2015\n'
                         '\x0c'}



dic_quesitos = {
    '019b1f875aabcfecc2c7ee0d8fab8e37': {   'nome_bloco_quesitos': 'sapiquesitos-019b1f875aabcfecc2c7ee0d8fab8e37',
                                            'nome_bloco_respostas': 'sapirespostas-019b1f875aabcfecc2c7ee0d8fab8e37',
                                            'quantidade_quesitos': 5,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefonia '
                                                               'celular '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Qual(is) '
                                                               'o(s) número(s) '
                                                               'habilitado(s) '
                                                               'no(s) '
                                                               'aparelho(s) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)?...\n'
                                                               '5. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual(is) '
                                                              'o(s) número(s) '
                                                              'habilitado(s) '
                                                              'no(s) '
                                                              'aparelho(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)?\n'
                                                              '5. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '096b49d9f94713ca339813edf274f88d': {   'nome_bloco_quesitos': 'sapiquesitos-096b49d9f94713ca339813edf274f88d',
                                            'nome_bloco_respostas': 'sapirespostas-096b49d9f94713ca339813edf274f88d',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Qual número '
                                                               'habilitado '
                                                               'no(s) '
                                                               'aparelho(s) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)?...\n'
                                                               '5. Quais as '
                                                               'mensagens '
                                                               'enviadas e '
                                                               'recebidas '
                                                               'constantes da '
                                                               'memória do '
                                                               'aparelho?\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual número '
                                                              'habilitado '
                                                              'no(s) '
                                                              'aparelho(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)?\n'
                                                              '5. Quais as '
                                                              'mensagens '
                                                              'enviadas e '
                                                              'recebidas '
                                                              'constantes da '
                                                              'memória do '
                                                              'aparelho?\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '3acfbbc556616de8db75334f3f4a7294': {   'nome_bloco_quesitos': 'sapiquesitos-3acfbbc556616de8db75334f3f4a7294',
                                            'nome_bloco_respostas': 'sapirespostas-3acfbbc556616de8db75334f3f4a7294',
                                            'quantidade_quesitos': 8,
                                            'resumo_quesitos': '1. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '2. Há '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não atendidas? '
                                                               'Caso positivo, '
                                                               'relacionar....\n'
                                                               '3. Há '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '4. Existem '
                                                               'registros '
                                                               'referentes a '
                                                               'mensagens SMS? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '5. Há '
                                                               'informações '
                                                               'apagadas que '
                                                               'puderam ser '
                                                               'recuperadas?\n'
                                                               '6. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp), '
                                                               'fotos e vídeos '
                                                               'eventualmente '
                                                               'ar...\n'
                                                               '7. É possível, '
                                                               'a partir dos '
                                                               'dados '
                                                               'constantes no '
                                                               'objeto de '
                                                               'exame, '
                                                               'identificar o '
                                                               'usuário do '
                                                               'aparelho '
                                                               'celular?...\n'
                                                               '8. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '2. Há registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas? Caso '
                                                              'positivo, '
                                                              'relacionar.\n'
                                                              '3. Há registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '4. Existem '
                                                              'registros '
                                                              'referentes a '
                                                              'mensagens SMS? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '5. Há '
                                                              'informações '
                                                              'apagadas que '
                                                              'puderam ser '
                                                              'recuperadas?\n'
                                                              '6. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp), '
                                                              'fotos e vídeos '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '7. É possível, '
                                                              'a partir dos '
                                                              'dados '
                                                              'constantes no '
                                                              'objeto de '
                                                              'exame, '
                                                              'identificar o '
                                                              'usuário do '
                                                              'aparelho '
                                                              'celular?\n'
                                                              '8. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '472b7d4f17009522492af0ca5ffb5654': {   'nome_bloco_quesitos': 'sapiquesitos-472b7d4f17009522492af0ca5ffb5654',
                                            'nome_bloco_respostas': 'sapirespostas-472b7d4f17009522492af0ca5ffb5654',
                                            'quantidade_quesitos': 10,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza dos '
                                                               'equipamentos '
                                                               'apresentados a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'dos aparelhos '
                                                               'questionados?\n'
                                                               '3. É possível '
                                                               'determinar a '
                                                               'quem '
                                                               'pertencem?\n'
                                                               '4. Quais os '
                                                               'números '
                                                               'discados '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               '5. Quais as '
                                                               'chamadas '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               '6. Qual a '
                                                               'relação de '
                                                               'nomes e '
                                                               'telefones '
                                                               'constantes na '
                                                               'agenda '
                                                               'eletrônica dos '
                                                               'aparelhos?\n'
                                                               '7. Quais as '
                                                               'mensagens de '
                                                               'texto enviadas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               '8. Quais as '
                                                               'mensagens de '
                                                               'texto '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               '9. Existem '
                                                               'chamadas ou '
                                                               'mensagens de '
                                                               'texto trocadas '
                                                               'entre os '
                                                               'numerais '
                                                               'constantes em '
                                                               'cada um dos '
                                                               'aparelhos? '
                                                               '(cruzamento de '
                                                               'dado...\n'
                                                               '10. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza dos '
                                                              'equipamentos '
                                                              'apresentados a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação dos '
                                                              'aparelhos '
                                                              'questionados?\n'
                                                              '3. É possível '
                                                              'determinar a '
                                                              'quem '
                                                              'pertencem?\n'
                                                              '4. Quais os '
                                                              'números '
                                                              'discados '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              '5. Quais as '
                                                              'chamadas '
                                                              'recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              '6. Qual a '
                                                              'relação de '
                                                              'nomes e '
                                                              'telefones '
                                                              'constantes na '
                                                              'agenda '
                                                              'eletrônica dos '
                                                              'aparelhos?\n'
                                                              '7. Quais as '
                                                              'mensagens de '
                                                              'texto enviadas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              '8. Quais as '
                                                              'mensagens de '
                                                              'texto recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              '9. Existem '
                                                              'chamadas ou '
                                                              'mensagens de '
                                                              'texto trocadas '
                                                              'entre os '
                                                              'numerais '
                                                              'constantes em '
                                                              'cada um dos '
                                                              'aparelhos? '
                                                              '(cruzamento de '
                                                              'dados)\n'
                                                              '10. Outros '
                                                              'dados julgados '
                                                              'úteis.\n'},
    '596022c1e5270ef6c1aee1ab8a79722e': {   'nome_bloco_quesitos': 'sapiquesitos-596022c1e5270ef6c1aee1ab8a79722e',
                                            'nome_bloco_respostas': 'sapirespostas-596022c1e5270ef6c1aee1ab8a79722e',
                                            'quantidade_quesitos': 9,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'material(ais) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '3. Há '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não atendidas? '
                                                               'Caso positivo, '
                                                               'relacionar....\n'
                                                               '4. Há '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '5. Existem '
                                                               'registros '
                                                               'referentes a '
                                                               'mensagens SMS? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '6. Há '
                                                               'informações '
                                                               'apagadas que '
                                                               'puderam ser '
                                                               'recuperadas?\n'
                                                               '7. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp), '
                                                               'fotos e vídeos '
                                                               'eventualmente '
                                                               'ar...\n'
                                                               '8. É possível, '
                                                               'a partir dos '
                                                               'dados '
                                                               'constantes no '
                                                               'objeto de '
                                                               'exame, '
                                                               'identificar o '
                                                               'usuário do '
                                                               'aparelho '
                                                               'celular?...\n'
                                                               '9. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'material(ais) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '3. Há registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas? Caso '
                                                              'positivo, '
                                                              'relacionar.\n'
                                                              '4. Há registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '5. Existem '
                                                              'registros '
                                                              'referentes a '
                                                              'mensagens SMS? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '6. Há '
                                                              'informações '
                                                              'apagadas que '
                                                              'puderam ser '
                                                              'recuperadas?\n'
                                                              '7. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp), '
                                                              'fotos e vídeos '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '8. É possível, '
                                                              'a partir dos '
                                                              'dados '
                                                              'constantes no '
                                                              'objeto de '
                                                              'exame, '
                                                              'identificar o '
                                                              'usuário do '
                                                              'aparelho '
                                                              'celular?\n'
                                                              '9. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '6575765328fc4b3528aa073c7d6e5d21': {   'nome_bloco_quesitos': 'sapiquesitos-6575765328fc4b3528aa073c7d6e5d21',
                                            'nome_bloco_respostas': 'sapirespostas-6575765328fc4b3528aa073c7d6e5d21',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefonia '
                                                               'celular e '
                                                               'chip(s) '
                                                               'submetido(s) a '
                                                               'exame?...\n'
                                                               '2. Qual(is) '
                                                               'o(s) número(s) '
                                                               'habilitado(s) '
                                                               'no(s) '
                                                               'aparelho(s) e '
                                                               'chip(s) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s) e '
                                                               'chip(s)?...\n'
                                                               '5. Quais as '
                                                               'mensagens '
                                                               'escritas e de '
                                                               'voz mantidas '
                                                               'por intermédio '
                                                               'dos '
                                                               'aplicativos '
                                                               'eventualmente '
                                                               'instalados no '
                                                               'aparelho '
                                                               '(messeng...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular e '
                                                              'chip(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual(is) '
                                                              'o(s) número(s) '
                                                              'habilitado(s) '
                                                              'no(s) '
                                                              'aparelho(s) e '
                                                              'chip(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s) e '
                                                              'chip(s)?\n'
                                                              '5. Quais as '
                                                              'mensagens '
                                                              'escritas e de '
                                                              'voz mantidas '
                                                              'por intermédio '
                                                              'dos aplicativos '
                                                              'eventualmente '
                                                              'instalados no '
                                                              'aparelho '
                                                              '(messenger, '
                                                              'whatsapp, '
                                                              'telegram, bbm, '
                                                              'etc)?\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '71b7094bc7bfe94c45103946ed48b812': {   'nome_bloco_quesitos': 'sapiquesitos-71b7094bc7bfe94c45103946ed48b812',
                                            'nome_bloco_respostas': 'sapirespostas-71b7094bc7bfe94c45103946ed48b812',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'material(ais) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '3. Quais os '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não '
                                                               'atendidas?\n'
                                                               '4. Quais os '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)?\n'
                                                               '5. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp) '
                                                               'eventualmente '
                                                               'armazenadas '
                                                               'nos di...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'material(ais) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '3. Quais os '
                                                              'registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas?\n'
                                                              '4. Quais os '
                                                              'registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)?\n'
                                                              '5. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp) '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável;\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '7daaf7de628a39dd23ffb5cd62f914b0': {   'nome_bloco_quesitos': 'sapiquesitos-7daaf7de628a39dd23ffb5cd62f914b0',
                                            'nome_bloco_respostas': 'sapirespostas-7daaf7de628a39dd23ffb5cd62f914b0',
                                            'quantidade_quesitos': 10,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do material '
                                                               'submetido a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '3. Há '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não atendidas? '
                                                               'Caso positivo, '
                                                               'relacionar....\n'
                                                               '4. Há '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '5. Existem '
                                                               'registros '
                                                               'referentes a '
                                                               'mensagens SMS? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '6. Há '
                                                               'informações '
                                                               'apagadas que '
                                                               'puderam ser '
                                                               'recuperadas?\n'
                                                               '7. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp), '
                                                               'fotos e vídeos '
                                                               'eventualmente '
                                                               'ar...\n'
                                                               '8. É possível, '
                                                               'a partir dos '
                                                               'dados '
                                                               'constantes no '
                                                               'objeto de '
                                                               'exame, '
                                                               'identificar o '
                                                               'usuário do '
                                                               'aparelho '
                                                               'celular?...\n'
                                                               '9. Existe '
                                                               'algum tipo de '
                                                               'tabela de '
                                                               'empréstimos '
                                                               'nos mesmos, '
                                                               'conversas que '
                                                               'possam '
                                                               'identificar '
                                                               'relação de '
                                                               'trabalho, de '
                                                               'hierarquia...\n'
                                                               '10. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do material '
                                                              'submetido a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '3. Há registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas? Caso '
                                                              'positivo, '
                                                              'relacionar.\n'
                                                              '4. Há registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '5. Existem '
                                                              'registros '
                                                              'referentes a '
                                                              'mensagens SMS? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '6. Há '
                                                              'informações '
                                                              'apagadas que '
                                                              'puderam ser '
                                                              'recuperadas?\n'
                                                              '7. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp), '
                                                              'fotos e vídeos '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '8. É possível, '
                                                              'a partir dos '
                                                              'dados '
                                                              'constantes no '
                                                              'objeto de '
                                                              'exame, '
                                                              'identificar o '
                                                              'usuário do '
                                                              'aparelho '
                                                              'celular?\n'
                                                              '9. Existe algum '
                                                              'tipo de tabela '
                                                              'de empréstimos '
                                                              'nos mesmos, '
                                                              'conversas que '
                                                              'possam '
                                                              'identificar '
                                                              'relação de '
                                                              'trabalho, de '
                                                              'hierarquia ou '
                                                              'determinando '
                                                              'remessas de '
                                                              'valores ou '
                                                              'qualquer outro '
                                                              'fato ligado a '
                                                              'uma organização '
                                                              'que faria '
                                                              'empréstimos com '
                                                              'juros '
                                                              'abusivos?\n'
                                                              '10. Outros '
                                                              'dados julgados '
                                                              'úteis.\n'},
    '7ea6b6c017f4811055e9954d28a04ff3': {   'nome_bloco_quesitos': 'sapiquesitos-7ea6b6c017f4811055e9954d28a04ff3',
                                            'nome_bloco_respostas': 'sapirespostas-7ea6b6c017f4811055e9954d28a04ff3',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular e '
                                                               'chip(s) '
                                                               'submetido(s) a '
                                                               'exame?...\n'
                                                               '2. Qual(is) '
                                                               'o(s) número(s) '
                                                               'habilitado(s) '
                                                               'no(s) '
                                                               'aparelho(s) e '
                                                               'chip(s) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s) e '
                                                               'chip(s)?...\n'
                                                               '5. Quais as '
                                                               'mensagens '
                                                               'escritas e de '
                                                               'voz mantidas '
                                                               'por intermédio '
                                                               'dos '
                                                               'aplicativos '
                                                               'eventualmente '
                                                               'instalados no '
                                                               'aparelho '
                                                               '(messeng...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular e '
                                                              'chip(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual(is) '
                                                              'o(s) número(s) '
                                                              'habilitado(s) '
                                                              'no(s) '
                                                              'aparelho(s) e '
                                                              'chip(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s) e '
                                                              'chip(s)?\n'
                                                              '5. Quais as '
                                                              'mensagens '
                                                              'escritas e de '
                                                              'voz mantidas '
                                                              'por intermédio '
                                                              'dos aplicativos '
                                                              'eventualmente '
                                                              'instalados no '
                                                              'aparelho '
                                                              '(messenger, '
                                                              'whatsapp, '
                                                              'telegram, bbm, '
                                                              'etc)?\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '829d6492cbc35f546bc12a238a44ef44': {   'nome_bloco_quesitos': 'sapiquesitos-829d6492cbc35f546bc12a238a44ef44',
                                            'nome_bloco_respostas': 'sapirespostas-829d6492cbc35f546bc12a238a44ef44',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Qual o '
                                                               'número '
                                                               'habilitado no '
                                                               'aparelho '
                                                               'submetido a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e hora '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is)...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)?...\n'
                                                               '5. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp) '
                                                               'eventualmente '
                                                               'armazenadas '
                                                               'nos di...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual o '
                                                              'número '
                                                              'habilitado no '
                                                              'aparelho '
                                                              'submetido a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e hora '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)?\n'
                                                              '5. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp) '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '869daea13a6656b31877ae5ccda33fbe': {   'nome_bloco_quesitos': 'sapiquesitos-869daea13a6656b31877ae5ccda33fbe',
                                            'nome_bloco_respostas': 'sapirespostas-869daea13a6656b31877ae5ccda33fbe',
                                            'quantidade_quesitos': 5,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Qual o '
                                                               'número '
                                                               'habilitado no '
                                                               'aparelho '
                                                               'submetido a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)?...\n'
                                                               '5. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual o '
                                                              'número '
                                                              'habilitado no '
                                                              'aparelho '
                                                              'submetido a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)?\n'
                                                              '5. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    '8cdb23722e79aee20bbf807ec15cc873': {   'nome_bloco_quesitos': 'sapiquesitos-8cdb23722e79aee20bbf807ec15cc873',
                                            'nome_bloco_respostas': 'sapirespostas-8cdb23722e79aee20bbf807ec15cc873',
                                            'quantidade_quesitos': 10,
                                            'resumo_quesitos': 'I. Qual a '
                                                               'natureza dos '
                                                               'equipamentos '
                                                               'apresentados '
                                                               'para exame?\n'
                                                               'II. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'dos aparelhos '
                                                               'questionados?\n'
                                                               'III. É '
                                                               'possível '
                                                               'determinar a '
                                                               'quem '
                                                               'pertencem?\n'
                                                               'IV. Quais os '
                                                               'números '
                                                               'discados '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'V. Quais as '
                                                               'chamadas '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'VI. Qual a '
                                                               'relação de '
                                                               'nomes e '
                                                               'telefones '
                                                               'constantes na '
                                                               'agenda '
                                                               'eletrônica dos '
                                                               'aparelhos?\n'
                                                               'VII. Quais as '
                                                               'mensagens de '
                                                               'texto enviadas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'VIII. Quais as '
                                                               'mensagens de '
                                                               'texto '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'IX. Existem '
                                                               'chamadas ou '
                                                               'mensagens de '
                                                               'texto trocadas '
                                                               'entre os '
                                                               'numerais '
                                                               'constantes em '
                                                               'cada um dos '
                                                               'aparelhos? '
                                                               '(cruzamento de '
                                                               'dad...\n'
                                                               'X. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': 'I. Qual a '
                                                              'natureza dos '
                                                              'equipamentos '
                                                              'apresentados '
                                                              'para exame?\n'
                                                              'II. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação dos '
                                                              'aparelhos '
                                                              'questionados?\n'
                                                              'III. É possível '
                                                              'determinar a '
                                                              'quem '
                                                              'pertencem?\n'
                                                              'IV. Quais os '
                                                              'números '
                                                              'discados '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'V. Quais as '
                                                              'chamadas '
                                                              'recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'VI. Qual a '
                                                              'relação de '
                                                              'nomes e '
                                                              'telefones '
                                                              'constantes na '
                                                              'agenda '
                                                              'eletrônica dos '
                                                              'aparelhos?\n'
                                                              'VII. Quais as '
                                                              'mensagens de '
                                                              'texto enviadas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'VIII. Quais as '
                                                              'mensagens de '
                                                              'texto recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'IX. Existem '
                                                              'chamadas ou '
                                                              'mensagens de '
                                                              'texto trocadas '
                                                              'entre os '
                                                              'numerais '
                                                              'constantes em '
                                                              'cada um dos '
                                                              'aparelhos? '
                                                              '(cruzamento de '
                                                              'dados)\n'
                                                              'X. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    'a65b5838823d7cb80b5faff0a89260ac': {   'nome_bloco_quesitos': 'sapiquesitos-a65b5838823d7cb80b5faff0a89260ac',
                                            'nome_bloco_respostas': 'sapirespostas-a65b5838823d7cb80b5faff0a89260ac',
                                            'quantidade_quesitos': 11,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'material(ais) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '3. Há '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não atendidas? '
                                                               'Caso positivo, '
                                                               'relacionar....\n'
                                                               '4. Há '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '5. Existem '
                                                               'registros '
                                                               'referentes a '
                                                               'mensagens SMS? '
                                                               'Caso positivo, '
                                                               'relacionar.\n'
                                                               '6. Há '
                                                               'informações '
                                                               'apagadas que '
                                                               'puderam ser '
                                                               'recuperadas?\n'
                                                               '7. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp), '
                                                               'fotos e vídeos '
                                                               'eventualmente '
                                                               'ar...\n'
                                                               '8. É possível, '
                                                               'a partir dos '
                                                               'dados '
                                                               'constantes no '
                                                               'objeto de '
                                                               'exame, '
                                                               'identificar o '
                                                               'usuário do '
                                                               'aparelho '
                                                               'celular?...\n'
                                                               '9. É possível '
                                                               'realizar '
                                                               'despejo (dump) '
                                                               'físico da '
                                                               'memória '
                                                               'interna dos '
                                                               'dispositivos?\n'
                                                               '10. Em caso '
                                                               'positivo, é '
                                                               'possível a '
                                                               'recuperação de '
                                                               'mensagens '
                                                               'associadas ao '
                                                               'aplicativo '
                                                               'BlackBerry '
                                                               'Messenger?...\n'
                                                               '11. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'material(ais) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '3. Há registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas? Caso '
                                                              'positivo, '
                                                              'relacionar.\n'
                                                              '4. Há registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '5. Existem '
                                                              'registros '
                                                              'referentes a '
                                                              'mensagens SMS? '
                                                              'Caso positivo, '
                                                              'relacionar.\n'
                                                              '6. Há '
                                                              'informações '
                                                              'apagadas que '
                                                              'puderam ser '
                                                              'recuperadas?\n'
                                                              '7. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp), '
                                                              'fotos e vídeos '
                                                              'eventualmente '
                                                              'armazenados nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '8. É possível, '
                                                              'a partir dos '
                                                              'dados '
                                                              'constantes no '
                                                              'objeto de '
                                                              'exame, '
                                                              'identificar o '
                                                              'usuário do '
                                                              'aparelho '
                                                              'celular?\n'
                                                              '9. É possível '
                                                              'realizar '
                                                              'despejo (dump) '
                                                              'físico da '
                                                              'memória interna '
                                                              'dos '
                                                              'dispositivos?\n'
                                                              '10. Em caso '
                                                              'positivo, é '
                                                              'possível a '
                                                              'recuperação de '
                                                              'mensagens '
                                                              'associadas ao '
                                                              'aplicativo '
                                                              'BlackBerry '
                                                              'Messenger?\n'
                                                              '11. Outros '
                                                              'dados julgados '
                                                              'úteis.\n'},
    'b1be27224243b5c5e4f3eb506b69e847': {   'nome_bloco_quesitos': 'sapiquesitos-b1be27224243b5c5e4f3eb506b69e847',
                                            'nome_bloco_respostas': 'sapirespostas-b1be27224243b5c5e4f3eb506b69e847',
                                            'quantidade_quesitos': 7,
                                            'resumo_quesitos': 'I. Qual a '
                                                               'natureza do '
                                                               'equipamento '
                                                               'apresentado '
                                                               'para exame?\n'
                                                               'II. Qual o '
                                                               'número '
                                                               'telefônico de '
                                                               'habilitação do '
                                                               'aparelho '
                                                               'questionado?\n'
                                                               'III. É '
                                                               'possível '
                                                               'determinar a '
                                                               'quem '
                                                               'pertence?\n'
                                                               'IV. Quais os '
                                                               'números '
                                                               'discados '
                                                               'constantes na '
                                                               'memória do '
                                                               'aparelho?\n'
                                                               'V. Quais as '
                                                               'chamadas '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória do '
                                                               'aparelho?\n'
                                                               'VI. Qual a '
                                                               'relação de '
                                                               'nomes e '
                                                               'telefones '
                                                               'constantes na '
                                                               'agenda '
                                                               'eletrônica?\n'
                                                               'VII. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': 'I. Qual a '
                                                              'natureza do '
                                                              'equipamento '
                                                              'apresentado '
                                                              'para exame?\n'
                                                              'II. Qual o '
                                                              'número '
                                                              'telefônico de '
                                                              'habilitação do '
                                                              'aparelho '
                                                              'questionado?\n'
                                                              'III. É possível '
                                                              'determinar a '
                                                              'quem pertence?\n'
                                                              'IV. Quais os '
                                                              'números '
                                                              'discados '
                                                              'constantes na '
                                                              'memória do '
                                                              'aparelho?\n'
                                                              'V. Quais as '
                                                              'chamadas '
                                                              'recebidas '
                                                              'constantes na '
                                                              'memória do '
                                                              'aparelho?\n'
                                                              'VI. Qual a '
                                                              'relação de '
                                                              'nomes e '
                                                              'telefones '
                                                              'constantes na '
                                                              'agenda '
                                                              'eletrônica?\n'
                                                              'VII. Outros '
                                                              'dados julgados '
                                                              'úteis.\n'},
    'b2f5d080cc305be0e7f8eed7c9c352fd': {   'nome_bloco_quesitos': 'sapiquesitos-b2f5d080cc305be0e7f8eed7c9c352fd',
                                            'nome_bloco_respostas': 'sapirespostas-b2f5d080cc305be0e7f8eed7c9c352fd',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'material(ais) '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'associados?\n'
                                                               '3. Quais os '
                                                               'registros '
                                                               'correspondentes '
                                                               'às chamadas '
                                                               'telefônicas '
                                                               'recebidas, '
                                                               'efetuadas e '
                                                               'não '
                                                               'atendidas?\n'
                                                               '4. Quais os '
                                                               'registros '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s)?\n'
                                                               '5. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp), '
                                                               'fotos e vídeos '
                                                               'eventualmente '
                                                               'ar...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'material(ais) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação '
                                                              'associados?\n'
                                                              '3. Quais os '
                                                              'registros '
                                                              'correspondentes '
                                                              'às chamadas '
                                                              'telefônicas '
                                                              'recebidas, '
                                                              'efetuadas e não '
                                                              'atendidas?\n'
                                                              '4. Quais os '
                                                              'registros '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s)?\n'
                                                              '5. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp), '
                                                              'fotos e vídeos '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    'b63512002e10d4eb48faa0f109e02f16': {   'nome_bloco_quesitos': 'sapiquesitos-b63512002e10d4eb48faa0f109e02f16',
                                            'nome_bloco_respostas': 'sapirespostas-b63512002e10d4eb48faa0f109e02f16',
                                            'quantidade_quesitos': 6,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'característica '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular '
                                                               'submetido(s) a '
                                                               'exame?\n'
                                                               '2. Qual o '
                                                               'número '
                                                               'habilitado no '
                                                               'aparelho '
                                                               'submetido a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'contantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)?...\n'
                                                               '5. Extrair os '
                                                               'dados e '
                                                               'metadados '
                                                               'relativos às '
                                                               'comunicações '
                                                               'eletrônicas '
                                                               '(por exemplo '
                                                               'WhatsApp) '
                                                               'eventualmente '
                                                               'armazenadas '
                                                               'nos di...\n'
                                                               '6. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'característica '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual o '
                                                              'número '
                                                              'habilitado no '
                                                              'aparelho '
                                                              'submetido a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'contantes da(s) '
                                                              'agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)?\n'
                                                              '5. Extrair os '
                                                              'dados e '
                                                              'metadados '
                                                              'relativos às '
                                                              'comunicações '
                                                              'eletrônicas '
                                                              '(por exemplo '
                                                              'WhatsApp) '
                                                              'eventualmente '
                                                              'armazenadas nos '
                                                              'dispositivos '
                                                              'informáticos, '
                                                              'devendo a '
                                                              'apresentação '
                                                              'destes dados '
                                                              'ser em formato '
                                                              'de texto '
                                                              'legível e '
                                                              'navegável.\n'
                                                              '6. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    'ca6ca7626cb15461dabd0cbc038b561b': {   'nome_bloco_quesitos': 'sapiquesitos-ca6ca7626cb15461dabd0cbc038b561b',
                                            'nome_bloco_respostas': 'sapirespostas-ca6ca7626cb15461dabd0cbc038b561b',
                                            'quantidade_quesitos': 12,
                                            'resumo_quesitos': 'I. Qual a '
                                                               'natureza dos '
                                                               'equipamentos '
                                                               'apresentados '
                                                               'para exame?\n'
                                                               'II. Quais os '
                                                               'números '
                                                               'telefônicos de '
                                                               'habilitação '
                                                               'dos aparelhos '
                                                               'questionados?\n'
                                                               'III. É '
                                                               'possível '
                                                               'determinar a '
                                                               'quem '
                                                               'pertencem?\n'
                                                               'IV. Quais os '
                                                               'números '
                                                               'discados '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'V. Quais as '
                                                               'chamadas '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'VI. Qual a '
                                                               'relação de '
                                                               'nomes e '
                                                               'telefones '
                                                               'constantes na '
                                                               'agenda '
                                                               'eletrônica dos '
                                                               'aparelhos?\n'
                                                               'VII. Quais as '
                                                               'mensagens de '
                                                               'texto enviadas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'VIII. Quais as '
                                                               'mensagens de '
                                                               'texto '
                                                               'recebidas '
                                                               'constantes na '
                                                               'memória dos '
                                                               'aparelhos?\n'
                                                               'IX. Existem '
                                                               'chamadas ou '
                                                               'mensagens de '
                                                               'texto, '
                                                               'inclusive '
                                                               'apagadas, '
                                                               'trocadas entre '
                                                               'os numerais '
                                                               'constantes em '
                                                               'cada um dos '
                                                               'aparelho...\n'
                                                               'X. Exitem '
                                                               'conversas, '
                                                               'imagens, '
                                                               'vídeos e '
                                                               'aúdios '
                                                               'apagados do '
                                                               'aplicativo '
                                                               '“whatsapp”?\n'
                                                               'XI. Existem '
                                                               'fotografias e '
                                                               'vídeos em '
                                                               'mídias que '
                                                               'foram apagadas '
                                                               'da memória do '
                                                               'aparelho?\n'
                                                               'XII. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': 'I. Qual a '
                                                              'natureza dos '
                                                              'equipamentos '
                                                              'apresentados '
                                                              'para exame?\n'
                                                              'II. Quais os '
                                                              'números '
                                                              'telefônicos de '
                                                              'habilitação dos '
                                                              'aparelhos '
                                                              'questionados?\n'
                                                              'III. É possível '
                                                              'determinar a '
                                                              'quem '
                                                              'pertencem?\n'
                                                              'IV. Quais os '
                                                              'números '
                                                              'discados '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'V. Quais as '
                                                              'chamadas '
                                                              'recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'VI. Qual a '
                                                              'relação de '
                                                              'nomes e '
                                                              'telefones '
                                                              'constantes na '
                                                              'agenda '
                                                              'eletrônica dos '
                                                              'aparelhos?\n'
                                                              'VII. Quais as '
                                                              'mensagens de '
                                                              'texto enviadas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'VIII. Quais as '
                                                              'mensagens de '
                                                              'texto recebidas '
                                                              'constantes na '
                                                              'memória dos '
                                                              'aparelhos?\n'
                                                              'IX. Existem '
                                                              'chamadas ou '
                                                              'mensagens de '
                                                              'texto, '
                                                              'inclusive '
                                                              'apagadas, '
                                                              'trocadas entre '
                                                              'os numerais '
                                                              'constantes em '
                                                              'cada um dos '
                                                              'aparelhos? '
                                                              '(cruzamento de '
                                                              'dados)\n'
                                                              'X. Exitem '
                                                              'conversas, '
                                                              'imagens, vídeos '
                                                              'e aúdios '
                                                              'apagados do '
                                                              'aplicativo '
                                                              '“whatsapp”?\n'
                                                              'XI. Existem '
                                                              'fotografias e '
                                                              'vídeos em '
                                                              'mídias que '
                                                              'foram apagadas '
                                                              'da memória do '
                                                              'aparelho?\n'
                                                              'XII. Outros '
                                                              'dados julgados '
                                                              'úteis.\n'},
    'cac_7': {   'nome_bloco_quesitos': 'sapiquesitos-cac_7',
                 'nome_bloco_respostas': 'sapirespostas-cac_7',
                 'quantidade_quesitos': 7,
                 'resumo_quesitos': '“1) Características do aparelho e '
                                    'registro de data e hora em que se '
                                    'encontra no momento do exame;\n'
                                    '2) Registros de agenda;\n'
                                    '3) Registros de ligações (recebidas e '
                                    'efetuadas);\n'
                                    '4) Mensagens e arquivos de texto;\n'
                                    '5) Arquivos (textos, áudios, vídeos) de '
                                    'aplicativos de internet, principalmente '
                                    'de conversação (whatsapp, telegram, '
                                    'etc);...\n'
                                    '6) Arquivos de mídia (áudios e vídeos);\n'
                                    '7) Outros arquivos encontrados, inclusive '
                                    'os deletados, se possível.”',
                 'texto_quesitos': '“1) Características do aparelho e registro '
                                   'de data e hora em que se encontra no '
                                   'momento do exame;\n'
                                   '2) Registros de agenda;\n'
                                   '3) Registros de ligações (recebidas e '
                                   'efetuadas);\n'
                                   '4) Mensagens e arquivos de texto;\n'
                                   '5) Arquivos (textos, áudios, vídeos) de '
                                   'aplicativos de internet, principalmente de '
                                   'conversação (whatsapp, telegram, etc);\n'
                                   '6) Arquivos de mídia (áudios e vídeos);\n'
                                   '7) Outros arquivos encontrados, inclusive '
                                   'os deletados, se possível.”\n'},
    'ef78c3e78f7ac6b02d66677a053dba12': {   'nome_bloco_quesitos': 'sapiquesitos-ef78c3e78f7ac6b02d66677a053dba12',
                                            'nome_bloco_respostas': 'sapirespostas-ef78c3e78f7ac6b02d66677a053dba12',
                                            'quantidade_quesitos': 7,
                                            'resumo_quesitos': '1) '
                                                               'Características '
                                                               'do aparelho e '
                                                               'registro de '
                                                               'data e hora em '
                                                               'que se '
                                                               'encontra no '
                                                               'momento do '
                                                               'exame;\n'
                                                               '2) Registros '
                                                               'de agenda;\n'
                                                               '3) Registros '
                                                               'de ligações '
                                                               '(recebidas e '
                                                               'efetuadas);\n'
                                                               '4) Arquivos '
                                                               '(textos, '
                                                               'áudios, fotos '
                                                               'e vídeos) '
                                                               'recebidos e '
                                                               'enviados por '
                                                               'meio de SMS, '
                                                               'MMS, correio '
                                                               'eletrônico '
                                                               '(e-mail), '
                                                               'etc....\n'
                                                               '5) Arquivos '
                                                               '(textos, '
                                                               'áudios, fotos '
                                                               'e vídeos) '
                                                               'recebidos e '
                                                               'enviados por '
                                                               'meio de '
                                                               'aplicativos de '
                                                               'internet, '
                                                               'principalmente '
                                                               'de conv...\n'
                                                               '6) Arquivos de '
                                                               'mídia (áudios, '
                                                               'fotos e '
                                                               'vídeos) '
                                                               'gravados na '
                                                               'memória do '
                                                               'aparelho;\n'
                                                               '7) Recuperação '
                                                               'de arquivos '
                                                               'deletados.',
                                            'texto_quesitos': '1) '
                                                              'Características '
                                                              'do aparelho e '
                                                              'registro de '
                                                              'data e hora em '
                                                              'que se encontra '
                                                              'no momento do '
                                                              'exame;\n'
                                                              '2) Registros de '
                                                              'agenda;\n'
                                                              '3) Registros de '
                                                              'ligações '
                                                              '(recebidas e '
                                                              'efetuadas);\n'
                                                              '4) Arquivos '
                                                              '(textos, '
                                                              'áudios, fotos e '
                                                              'vídeos) '
                                                              'recebidos e '
                                                              'enviados por '
                                                              'meio de SMS, '
                                                              'MMS, correio '
                                                              'eletrônico '
                                                              '(e-mail), etc.\n'
                                                              '5) Arquivos '
                                                              '(textos, '
                                                              'áudios, fotos e '
                                                              'vídeos) '
                                                              'recebidos e '
                                                              'enviados por '
                                                              'meio de '
                                                              'aplicativos de '
                                                              'internet, '
                                                              'principalmente '
                                                              'de conversação '
                                                              '(whatsapp, '
                                                              'telegram, '
                                                              'etc);\n'
                                                              '6) Arquivos de '
                                                              'mídia (áudios, '
                                                              'fotos e vídeos) '
                                                              'gravados na '
                                                              'memória do '
                                                              'aparelho;\n'
                                                              '7) Recuperação '
                                                              'de arquivos '
                                                              'deletados.\n'},
    'efdfd9ee6c4d36934468d62acda39a4e': {   'nome_bloco_quesitos': 'sapiquesitos-efdfd9ee6c4d36934468d62acda39a4e',
                                            'nome_bloco_respostas': 'sapirespostas-efdfd9ee6c4d36934468d62acda39a4e',
                                            'quantidade_quesitos': 5,
                                            'resumo_quesitos': '1. Qual a '
                                                               'natureza e '
                                                               'características '
                                                               'do(s) '
                                                               'aparelho(s) de '
                                                               'telefone '
                                                               'celular/chips(s) '
                                                               'submetido(s) a '
                                                               'exame?...\n'
                                                               '2. Qual o '
                                                               'número '
                                                               'habilitado no '
                                                               'aparelho/chip '
                                                               'submetido a '
                                                               'exame?\n'
                                                               '3. Quais os '
                                                               'números de '
                                                               'telefone, '
                                                               'datas e horas '
                                                               'constantes dos '
                                                               'registros das '
                                                               'últimas '
                                                               'ligações '
                                                               'efetuadas e '
                                                               'recebidas por '
                                                               'tal(is...\n'
                                                               '4. Quais os '
                                                               'nomes e '
                                                               'números de '
                                                               'telefone '
                                                               'constantes '
                                                               'da(s) '
                                                               'agenda(s) '
                                                               'telefônica(s) '
                                                               'de tal(is) '
                                                               'aparelho(s)/chip(s)?...\n'
                                                               '5. Outros '
                                                               'dados julgados '
                                                               'úteis.',
                                            'texto_quesitos': '1. Qual a '
                                                              'natureza e '
                                                              'características '
                                                              'do(s) '
                                                              'aparelho(s) de '
                                                              'telefone '
                                                              'celular/chips(s) '
                                                              'submetido(s) a '
                                                              'exame?\n'
                                                              '2. Qual o '
                                                              'número '
                                                              'habilitado no '
                                                              'aparelho/chip '
                                                              'submetido a '
                                                              'exame?\n'
                                                              '3. Quais os '
                                                              'números de '
                                                              'telefone, datas '
                                                              'e horas '
                                                              'constantes dos '
                                                              'registros das '
                                                              'últimas '
                                                              'ligações '
                                                              'efetuadas e '
                                                              'recebidas por '
                                                              'tal(is) '
                                                              'aparelho(s) de '
                                                              'telefonia '
                                                              'celular/chip(s)?\n'
                                                              '4. Quais os '
                                                              'nomes e números '
                                                              'de telefone '
                                                              'constantes '
                                                              'da(s) agenda(s) '
                                                              'telefônica(s) '
                                                              'de tal(is) '
                                                              'aparelho(s)/chip(s)?\n'
                                                              '5. Outros dados '
                                                              'julgados '
                                                              'úteis.\n'},
    'geralduplicacaoextracao': {   'nome_bloco_quesitos': 'sapiquesitos-geralduplicacaoextracao',
                                   'nome_bloco_respostas': 'sapirespostas-geralduplicacaoextracao',
                                   'quantidade_quesitos': 2,
                                   'resumo_quesitos': '[...] solicito a Vossa '
                                                      'Senhoria seja procedido '
                                                      'o espelhamento das '
                                                      'mídias\n'
                                                      '[...] Para facilitar a '
                                                      'posterior análise, os '
                                                      'discos rígidos/mídias '
                                                      'originais, referentes a '
                                                      'cada alvo deverão ser '
                                                      'agrupados em...',
                                   'texto_quesitos': '[...] solicito a Vossa '
                                                     'Senhoria seja procedido '
                                                     'o espelhamento das '
                                                     'mídias\n'
                                                     '[...] Para facilitar a '
                                                     'posterior análise, os '
                                                     'discos rígidos/mídias '
                                                     'originais, referentes a '
                                                     'cada alvo deverão ser '
                                                     'agrupados em um único HD '
                                                     'de destino (em sendo '
                                                     'possível), separados em '
                                                     'pastas nomeadas em '
                                                     'acordo com o ITEM/ITEM '
                                                     'ARRECADAÇÃO, constante '
                                                     'do auto de apreensão '
                                                     'supracitado.\n'},
    'lda_8': {   'nome_bloco_quesitos': 'sapiquesitos-lda_8',
                 'nome_bloco_respostas': 'sapirespostas-lda_8',
                 'quantidade_quesitos': 8,
                 'resumo_quesitos': '“1. Qual a natureza do equipamento '
                                    'apresentado para exame?\n'
                                    '2. Qual(is) o(s) números(s) telefônico(s) '
                                    'habilitado(s) no aparelho questionado?\n'
                                    '3. É possível determinar a quem '
                                    'pertence?\n'
                                    '4. Qual a relação de nomes e telefones '
                                    'constantes na agenda eletrônica '
                                    '(contatos) do aparelho, bem como no(s) '
                                    'respectivo(s) c...\n'
                                    '5. Quais as chamadas recebidas e '
                                    'efetuadas constantes na memória do '
                                    'aparelho?\n'
                                    '6. Existem mensagens SMS armazenadas no '
                                    'aparelho? Em caso positivo, '
                                    'transcrevê-las, inclusive com a indicação '
                                    'de seus destina...\n'
                                    '7. Existem aplicativos de mensagens '
                                    'instantâneas instalados no aparelho? Em '
                                    'caso positivo, transcrever as mensagens '
                                    'armazenad...\n'
                                    '8. Outros dados julgados úteis.”',
                 'texto_quesitos': '“1. Qual a natureza do equipamento '
                                   'apresentado para exame?\n'
                                   '2. Qual(is) o(s) números(s) telefônico(s) '
                                   'habilitado(s) no aparelho questionado?\n'
                                   '3. É possível determinar a quem pertence?\n'
                                   '4. Qual a relação de nomes e telefones '
                                   'constantes na agenda eletrônica (contatos) '
                                   'do aparelho, bem como no(s) respectivo(s) '
                                   'cartão(ões) SIM(chip)?\n'
                                   '5. Quais as chamadas recebidas e efetuadas '
                                   'constantes na memória do aparelho?\n'
                                   '6. Existem mensagens SMS armazenadas no '
                                   'aparelho? Em caso positivo, '
                                   'transcrevê-las, inclusive com a indicação '
                                   'de seus destinatários, data e hora.\n'
                                   '7. Existem aplicativos de mensagens '
                                   'instantâneas instalados no aparelho? Em '
                                   'caso positivo, transcrever as mensagens '
                                   'armazenadas em tais aplicativos, inclusive '
                                   'com a indicação de seus destinatários, '
                                   'data e hora.\n'
                                   '8. Outros dados julgados úteis.”\n'},
    'pgz_6': {   'nome_bloco_quesitos': 'sapiquesitos-pgz_6',
                 'nome_bloco_respostas': 'sapirespostas-pgz_6',
                 'quantidade_quesitos': 6,
                 'resumo_quesitos': '“01 – Qual o modelo, descrição, '
                                    'características e estado de conservação '
                                    'do aparelho/chip encaminhados a '
                                    'exame?...\n'
                                    '02 – O aparelhos celular utiliza-se de '
                                    'chip GSM? Se positivo, qual o número do '
                                    'chip encontrado no interior de cada um '
                                    'destes ...\n'
                                    '03 – Quais são os registros que se '
                                    'encontram gravados na memória do aparelho '
                                    'e/ou dos chips: ligações recebidas, '
                                    'efetuadas, n...\n'
                                    '04 – Quais os últimos números chamados e '
                                    'recebidos pelos aparelhos?\n'
                                    '05 – Quais são os registros de ligações e '
                                    'mensagens existentes no celular/chip '
                                    'apreendido referentes à data de '
                                    'XX/XX/XXXX?...\n'
                                    '06 – Outros dados julgados úteis?”',
                 'texto_quesitos': '“01 – Qual o modelo, descrição, '
                                   'características e estado de conservação do '
                                   'aparelho/chip encaminhados a exame?\n'
                                   '02 – O aparelhos celular utiliza-se de '
                                   'chip GSM? Se positivo, qual o número do '
                                   'chip encontrado no interior de cada um '
                                   'destes aparelhos, com o respectivo número '
                                   'de telefonia celular a eles atribuídos?\n'
                                   '03 – Quais são os registros que se '
                                   'encontram gravados na memória do aparelho '
                                   'e/ou dos chips: ligações recebidas, '
                                   'efetuadas, não atendidas, agenda, '
                                   'contatos, nomes e telefones, mensagens '
                                   'recebidas, enviadas, rascunho, etc., todas '
                                   'se possível, com data e horário? Obs. '
                                   'Consignar textualmente (por escrito) no '
                                   'laudo, independentemente do envio de mídia '
                                   'anexa ou inclusa no mesmo.\n'
                                   '04 – Quais os últimos números chamados e '
                                   'recebidos pelos aparelhos?\n'
                                   '05 – Quais são os registros de ligações e '
                                   'mensagens existentes no celular/chip '
                                   'apreendido referentes à data de '
                                   'XX/XX/XXXX?\n'
                                   '06 – Outros dados julgados úteis?”\n'},
    'respostagenerica': {   'nome_bloco_quesitos': 'sapiquesitos-respostagenerica',
                            'nome_bloco_respostas': 'sapirespostas-respostagenerica',
                            'quantidade_quesitos': 1,
                            'resumo_quesitos': '[...] solicito a realização de '
                                               'exame pericial (AJUSTAR OU '
                                               'REMOVER) [...]',
                            'texto_quesitos': '[...] solicito a realização de '
                                              'exame pericial (AJUSTAR OU '
                                              'REMOVER) [...]\n'},
    'srpr_pij_10': {   'nome_bloco_quesitos': 'sapiquesitos-srpr_pij_10',
                       'nome_bloco_respostas': 'sapirespostas-srpr_pij_10',
                       'quantidade_quesitos': 10,
                       'resumo_quesitos': '“1. Qual a natureza e '
                                          'características do(s) aparelho(s) '
                                          'de telefone celular?\n'
                                          '2. Qual o número habilitado no '
                                          'aparelho submetido a exame?\n'
                                          '3. Quais os números de telefone, '
                                          'datas e horas constantes dos '
                                          'registros das últimas ligações '
                                          'efetuadas e recebidas por '
                                          'tal(is...\n'
                                          '4. Quais os nomes e números de '
                                          'telefone constantes da(s) agenda(s) '
                                          'telefônica(s) de tal(is) '
                                          'aparelho(s)?...\n'
                                          '5. Extrair os dados e metadados '
                                          'relativos às comunicações '
                                          'eletrônicas (por exemplo WhatsApp) '
                                          'eventualmente armazenadas nos '
                                          'di...\n'
                                          '6. Existe no material encaminhado '
                                          'mensagens, fotografias ou imagens '
                                          'de pornografia infantil ou cenas de '
                                          'sexo explícitos envol...\n'
                                          '7. Existem vestígios de uso dos '
                                          'perfils/nicknames '
                                          'http://www.facebook.com/XXXX, do '
                                          'e-mail xxxxxxxx@yyyy.com e dos '
                                          'nomes JJJJJ...\n'
                                          '8. Há mensagens eletrônicas '
                                          '(emails, conversas em programas de '
                                          'mensagens instantâneas, como '
                                          'twitter, msn, icq, whatsapp, '
                                          'Utor...\n'
                                          '9. Há registro de acesso a sites '
                                          'que tenham referência à pornografia '
                                          'infantil ou de que o investigado '
                                          'participe de grupo ou c...\n'
                                          '10. Outros dados julgados úteis.”',
                       'texto_quesitos': '“1. Qual a natureza e '
                                         'características do(s) aparelho(s) de '
                                         'telefone celular?\n'
                                         '2. Qual o número habilitado no '
                                         'aparelho submetido a exame?\n'
                                         '3. Quais os números de telefone, '
                                         'datas e horas constantes dos '
                                         'registros das últimas ligações '
                                         'efetuadas e recebidas por tal(is) '
                                         'aparelho(s) de telefonia celular?\n'
                                         '4. Quais os nomes e números de '
                                         'telefone constantes da(s) agenda(s) '
                                         'telefônica(s) de tal(is) '
                                         'aparelho(s)?\n'
                                         '5. Extrair os dados e metadados '
                                         'relativos às comunicações '
                                         'eletrônicas (por exemplo WhatsApp) '
                                         'eventualmente armazenadas nos '
                                         'dispositivos informáticos, devendo a '
                                         'apresentação destes dados ser em '
                                         'formato de texto legível e '
                                         'navegável;\n'
                                         '6. Existe no material encaminhado '
                                         'mensagens, fotografias ou imagens de '
                                         'pornografia infantil ou cenas de '
                                         'sexo explícitos envolvendo crianças '
                                         'ou adolescentes? \n'
                                         '7. Existem vestígios de uso dos '
                                         'perfils/nicknames '
                                         'http://www.facebook.com/XXXX, do '
                                         'e-mail xxxxxxxx@yyyy.com e dos nomes '
                                         'JJJJJ KKKK LLLL no material '
                                         'periciado?;\n'
                                         '8. Há mensagens eletrônicas (emails, '
                                         'conversas em programas de mensagens '
                                         'instantâneas, como twitter, msn, '
                                         'icq, whatsapp, Utorrent, outros) '
                                         'relacionadas a pornografia infantil '
                                         'ou sexo com crianças?\n'
                                         '9. Há registro de acesso a sites que '
                                         'tenham referência à pornografia '
                                         'infantil ou de que o investigado '
                                         'participe de grupo ou comunidade '
                                         'direcionada para a pedofilia? Caso '
                                         'positivo relacionar o que for '
                                         'encontrado;\n'
                                         '10. Outros dados julgados úteis.”\n'}}




# table5


def selecionar_quesitacao():
    root = tk.Tk()
    root.title("App")
    root.geometry("1000x700")
    #root.option_add("*Font", default_font)

    default_font = tkFont.nametofont("TkDefaultFont")
    default_font.configure(family = "Helvetica", size = 10)

    root.geometry("{0}x{1}+0+0".format(
        root.winfo_screenwidth() - 30,
        root.winfo_screenheight() - 300))
    #root.attributes('-fullscreen', True)
    tela_quesitacao = TelaQuesitacao(master=root,
                                     dic_quesitos=dic_quesitos,
                                     solicitacao_exame=solicitacao_exame)
    #root.resizable(False, False)
    root.mainloop()

    return tela_quesitacao.id_quesitacao_escolhida

id_quesitacao = selecionar_quesitacao()
print(id_quesitacao)


#OK.
#Pegar o duploclique do taste_table2
#Pegar ordenação do teste_table2
#Colocar no outro tab o texto da solicitação
