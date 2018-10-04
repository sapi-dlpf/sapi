import calendar
import tkinter as tk
from tkinter import ttk

calendar_object = calendar.Calendar()
ROOT = tk.Tk()


def date_changed(event):
    global my_year, my_month, my_day
    selected_year = int(my_year.get())
    selected_month = int(my_month.get())
    # use .itermonthdays get set new valid day selection
    my_day['values'] = \
        [x for x in calendar_object.itermonthdays(
            selected_year, selected_month) if x]
    last_day = sum(1 for x in my_day['values']) - 1
    # if day is invalid set to last valid day
    if my_day.get() not in my_day['values']:
        my_day.current(last_day)


my_year = ttk.Combobox(values=(2019, 2020),
                      state='readonly',
                      width=7)
my_year.grid(column=0, row=0)
my_year.bind('<<ComboboxSelected>>', date_changed)
my_year.current(0)

my_month = ttk.Combobox(values=[*range(1,13)],
                       state='readonly',
                       width=5)
my_month.grid(column=1, row=0)
my_month.bind('<<ComboboxSelected>>', date_changed)
my_month.current(0)


my_day = ttk.Combobox(values=[*range(1,32)],
                     state='readonly',
                     width=5)
my_day.grid(column=2, row=0)
my_day.current(0)
ROOT.mainloop()