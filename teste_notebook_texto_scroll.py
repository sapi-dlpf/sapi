import tkinter
import tkinter.ttk


class VerticalScrolledFrame(tkinter.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling
    """

    def __init__(self, parent, *args, **kw):
        tkinter.Frame.__init__(self, parent, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = tkinter.Scrollbar(self, orient=tkinter.VERTICAL)
        vscrollbar.pack(fill=tkinter.Y, side=tkinter.RIGHT, expand=tkinter.FALSE)
        canvas = tkinter.Canvas(self, bd=0, highlightthickness=0,
                                yscrollcommand=vscrollbar.set)
        canvas.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=tkinter.TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = tkinter.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=tkinter.NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        canvas.bind('<Configure>', _configure_canvas)


class GuiEscolhaQuesito:
    def __init__(self, master):

        self.master = master
        master.title("Escolha de quesitação")

        # gives weight to the cells in the grid
        rows = 0
        while rows < 50:
            master.rowconfigure(rows, weight=1)
            master.columnconfigure(rows, weight=1)
            rows += 1

        # Defines and places the notebook widget
        nb = tkinter.ttk.Notebook(master)
        nb.grid(row=1, column=0, columnspan=50, rowspan=49, sticky='NESW')

        # Adds tab 1 of the notebook
        page1 = tkinter.ttk.Frame(nb)
        nb.add(page1, text='Escolha de quesito')

        # Monta lista de quesitos
        q = 0
        var_quesito = tkinter.IntVar()
        var_quesito = 0
        tkinter.Label(page1, text="%similar.").grid(row=0, column=1, sticky=tkinter.W)
        tkinter.Label(page1, text="Quesito").grid(row=0, column=2, sticky=tkinter.W)

        for quesito in lista_quesitos:
            # Incluir variavel na lista
            # var.append(tkinter.IntVar())
            # Monta checkbox
            # tkinter.Checkbutton(page1, text=quesito, variable=var[q]).grid(row=q, sticky=tkinter.W)
            linha = q + 1
            tkinter.Label(page1, text="0.95").grid(row=linha, column=1)
            tkinter.Radiobutton(page1, text=quesito, variable=var_quesito, value=q).grid(row=linha, column=2,
                                                                                         sticky=tkinter.W)
            #
            q = q + 1

        # Adds tab 2 of the notebook
        page2 = tkinter.ttk.Frame(nb)



        txt_frm = tkinter.Frame(page2, width=300, height=300)
        txt_frm.pack(fill="both", expand=True)
        # ensure a consistent GUI size
        txt_frm.grid_propagate(False)
        # implement stretchability
        txt_frm.grid_rowconfigure(0, weight=1)
        txt_frm.grid_columnconfigure(0, weight=1)

        # create a Text widget
        self.txt = tkinter.Text(txt_frm, borderwidth=3, relief="sunken")
        self.txt.config(font=("consolas", 12), undo=True, wrap='word')
        self.txt.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # create a Scrollbar and associate it with txt
        scrollb = tkinter.Scrollbar(txt_frm, command=self.txt.yview)
        scrollb.grid(row=0, column=1, sticky='nsew')
        self.txt['yscrollcommand'] = scrollb.set

        #
        self.txt.insert(tkinter.END, texto)


        nb.add(page2, text='Solicitação de exame')

        # Tab para teste

        page3 = VerticalScrolledFrame(nb)
        nb.add(page3, text='Teste')

        frm_int = tkinter.Frame(page3, width=300, height=300)
        frm_int.pack(fill="both", expand=True)
        # ensure a consistent GUI size
        frm_int.grid_propagate(False)
        # implement stretchability
        frm_int.grid_rowconfigure(0, weight=1)
        frm_int.grid_columnconfigure(0, weight=1)

        quesito = lista_quesitos[1]

        for q in range(100):
            # listNodes.insert(tkinter.END, quesito)
            linha = q + 1
            # tkinter.Label(page3, text="0.95").grid(row=linha, column=1)
            # tkinter.Radiobutton(page3, text=quesito, variable=var_quesito, value=q).grid(row=linha, column=2, sticky=tkinter.W)
            tkinter.Label(frm_int, text="0.95").pack()
            tkinter.Radiobutton(frm_int, text=quesito, variable=var_quesito, value=q).pack()


            # tkinter.Label(window, text="Bottom label").pack()


            #
            # self.label = tkinter.Label(master, text="This is our first GUI!")
            # self.label.pack()



            #
            # self.greet_button = tkinter.Button(master, text="Greet", command=self.greet)
            # self.greet_button.pack()
            #
            # self.close_button = tkinter.Button(master, text="Close", command=master.quit)
            # self.close_button.pack()

    def greet(self):
        print("Greetings!")


def escolhe_quesito(lista_quesitos, texto):
    root = tkinter.Tk()
    root.title('Notebook Demo')
    root.geometry('600x600')

    my_gui = GuiEscolhaQuesito(root)
    root.mainloop()


quesito1 = '''NADA IGUAL.'''

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
4. Qual a número de telefone?
5. Outros dados julgados úteis.'''

lista_quesitos = [quesito1, quesito2, quesito3, quesito4]

texto = '''
    Memorando 1234/18
    xxxx
    1. Quais as caracteristicas do aparelho?
    2. Quais as chamadas?
    3. Qual a agenda?
    4. Outros dados julgados úteis.

    Lista de Materiais
    Um celular
    '''

escolhe_quesito(lista_quesitos, texto)
