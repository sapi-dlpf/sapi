from tkinter import *

Gusuario = ""
Gsenha = ""


def validar_credencial(dummy=0):
   global Gusuario
   global Gsenha

   Gusuario = e1.get()
   Gsenha = e2.get()

   print("First Name: %s\nLast Name: %s" % (e1.get(), e2.get()))

   if (Gsenha=="ok"):
      master.quit()

   # Continua
   e1.delete(0,END)
   e2.delete(0,END)
   e1.focus()

def montar_formulario(master):
   Label(master, text="Usuário").grid(row=0)
   Label(master, text="Senha").grid(row=1)

   e1 = Entry(master)
   e2 = Entry(master)
   e1.focus()

   e1.grid(row=0, column=1)
   e2.grid(row=1, column=1)

   Button(master, text='OK', command=validar_credencial).grid(row=3, column=0, sticky=W, pady=4)
   Button(master, text='CANCELAR', command=master.quit).grid(row=3, column=1, sticky=W, pady=4)
   master.bind('<Return>', validar_credencial)


master = Tk()
montar_formulario(master)
master.mainloop()