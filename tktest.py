from Tkinter import *

class Runner(object):
	
	def __init__(self,master):
		
		self.fmain = Frame(master)
		self.fmain.pack()		
		
		self.fbottom = Frame(self.fmain)
		self.fbottom.pack(side=BOTTOM)
		
		self.bprev = Button(self.fbottom,text="<< Prev")
		self.bprev.pack(side=LEFT)
		
		self.bnext = Button(self.fbottom,text="Next >>")
		self.bnext.pack(side=RIGHT)
		
		self.fleft = Frame(self.fmain)
		self.fleft.pack(side=LEFT,fill=BOTH,expand=1)
				
		llabel = Label(self.fleft,text="I am on the left side",
			width=30,height=20)
		llabel.pack(fill=BOTH,expand=1)
				
		self.fright = Frame(self.fmain)
		self.fright.pack(side=RIGHT,fill=BOTH,expand=1)
		
		self.optvar = StringVar()
		rad1 = Radiobutton(self.fright,text="Alpha",value="Alpha",
			variable=self.optvar,width=30)
		rad1.grid()
		
		self.optvar = StringVar()
		rad1 = Radiobutton(self.fright,text="Beta",value="Beta",
			variable=self.optvar,width=30)
		rad1.grid()
		
		self.optvar = StringVar()
		rad1 = Radiobutton(self.fright,text="Gamma",value="Gamma",
			variable=self.optvar,width=30)
		rad1.grid()


tkroot = Tk()
runne = Runner(tkroot)
tkroot.mainloop()
