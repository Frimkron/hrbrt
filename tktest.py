from Tkinter import *


class Runner(object):
	"""Handle running of decision tree, maintains state"""
	
	def run(self): pass


class RunnerGUIListener(object):
	
	def on_next(self): pass
	def on_prev(self): pass
	def on_change_selection(self,value): pass

class RunnerListener(object):
	
	def on_can_go_back_change(self,value): pass
	def on_can_go_forward_change(self,value): pass


class RunnerGUI(object):
	"""Dumb frontend for runner, reacts to state change events,
		sends user interaction events"""
	
	def __init__(self,master):
		
		self.fmain = Frame(master)
		self.fmain.pack(side=TOP)		
		
		self.fbottom = Frame(self.fmain)
		self.fbottom.pack(side=BOTTOM,fill=BOTH,expand=1)
		
		self.bnext = Button(self.fbottom,text="Next >>")
		self.bnext.pack(side=RIGHT,padx=12,pady=12)
		
		self.bprev = Button(self.fbottom,text="<< Prev",state=DISABLED)
		self.bprev.pack(side=LEFT,padx=12,pady=12)
		
		self.fright = Frame(self.fmain,width=200,height=200)
		self.fright.pack_propagate(0)
		self.fright.pack(side=RIGHT,fill=BOTH,expand=1,padx=12,pady=12)
		
		self.optvar = StringVar()
		rad1 = Radiobutton(self.fright,text="Alpha",value="Alpha",
			variable=self.optvar)
		rad1.pack(side=TOP,anchor=W)
		
		rad1 = Radiobutton(self.fright,text="Beta",value="Beta",
			variable=self.optvar)
		rad1.pack(side=TOP,anchor=W)
		
		rad1 = Radiobutton(self.fright,text="Gamma",value="Gamma",
			variable=self.optvar)
		rad1.pack(side=TOP,anchor=W)
		
		self.fleft = Frame(self.fmain,width=200,height=200)
		self.fleft.pack_propagate(0)
		self.fleft.pack(side=LEFT,fill=BOTH,expand=1,padx=12,pady=12)
				
		llabel = Label(self.fleft,text="I am on the left side\nand I am a label",
			justify=LEFT,state=DISABLED)
		llabel.pack(side=TOP,anchor=W)
		
tkroot = Tk()
runne = Runner(tkroot)
tkroot.mainloop()
