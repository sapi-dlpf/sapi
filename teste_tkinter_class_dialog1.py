#from tkinter import Tk, BOTH
#from tkinter import messagebox as tkinter.mbox
# from tkinter import ttk
import tkinter
from tkinter import ttk
#from tkinter import *


class DialogoCredencial(tkinter.Frame):

    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):

        '''
        self.master.title("Message boxes")
        self.pack()

        error = ttk.Button(self, text="Error", command=self.onError)
        error.grid(padx=5, pady=5)
        warning = ttk.Button(self, text="Warning", command=self.onWarn)
        warning.grid(row=1, column=0)
        question = ttk.Button(self, text="Question", command=self.onQuest)
        question.grid(row=0, column=1)
        inform = ttk.Button(self, text="Information", command=self.onInfo)
        inform.grid(row=1, column=1)
        '''

        self.master.title("Credencial (Setec3 = SisCrim) ")
        self.pack()


        ttk.Label(self, text="Usuário").grid(row=0)
        ttk.Label(self, text="Senha").grid(row=1)

        self.entrada_usuario = ttk.Entry(self)
        self.entrada_senha = ttk.Entry(self, show="*")
        self.entrada_usuario.focus()

        self.entrada_usuario.grid(row=0, column=1)
        self.entrada_senha.grid(row=1, column=1)

        ttk.Button(self, text='OK', command=self.validar_credencial).grid(row=3, column=0, pady=4)
        ttk.Button(self, text='CANCELAR', command=self.quit).grid(row=3, column=1, pady=4)

        self.master.bind('<Return>', self.validar_credencial)

    def validar_credencial(self, dummy=0):
        self.usuario = self.entrada_usuario.get()
        self.senha = self.entrada_senha.get()
        print("usuario = ", self.usuario)
        print("senha = ", self.senha)

        if (self.senha == "ok"):
            self.quit()

        # Continua
        self.entrada_usuario.delete(0, tkinter.END)
        self.entrada_senha.delete(0, tkinter.END)
        self.entrada_usuario.focus()

        # comando
        self.botao_ok=True

    def onError(self):
        tkinter.mbox.showerror("Error", "Could not open file")

    def onWarn(self):
        tkinter.mbox.showwarning("Warning", "Deprecated function call")

    def onQuest(self):
        tkinter.mbox.askquestion("Question", "Are you sure to quit?")

    def onInfo(self):
        tkinter.mbox.showinfo("Information", "Download completed")


def autenticar_usuario():

    # Dados do usuário autenticado
    usuario=dict()

    # Abre janela gráfica para pegar credencial
    root = tkinter.Tk()
    dialogo = DialogoCredencial()
    root.geometry("400x150+300+300")
    root.mainloop()

    # Credencial fornecida
    if (dialogo.get('usuario', None) is None):
        # Usuário não foi fornecido
        return

    # Verifica se credencial é válida
    print(dialogo.usuario)
    print(dialogo.senha)
    print(dialogo.botao_ok)

def main():
    autenticar_usuario()

if __name__ == '__main__':
    main()   