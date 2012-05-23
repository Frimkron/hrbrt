from Tkinter import *


class Runner(object):
	"""Handle running of decision tree, maintains state"""

	def run(self):
		tkroot = Tk()
		self.gui = RunnerGUI(tkroot)
		self.gui.listener = self
		self.items = [
			RunnerListener.Text("This is a test"),
			RunnerListener.Choice(["alpha","beta","gamma"]),
			RunnerListener.Text("Wow what an adventure"),
		]
		self.current = 0
		self.current_updated()
		tkroot.mainloop()

	def current_updated(self):
		self.gui.on_back_allowed_change(self.current > 0)
		self.gui.on_forward_allowed_change(self.current < len(self.items)-1)
		self.gui.on_prev_item_change(self.items[self.current-1] if self.current > 0 else None)
		self.gui.on_curr_item_change(self.items[self.current])
		
	def on_next(self):
		if self.current < len(self.items):
			self.current += 1
			self.current_updated()
		
	def on_prev(self):
		if self.current > 0:
			self.current -= 1
			self.current_updated()
		
	def on_change_selection(self,value):
		pass

class RunnerGUIListener(object):
	
	def on_next(self): pass
	def on_prev(self): pass
	def on_change_selection(self,value): pass

class RunnerListener(object):
	
	class Text(object):
		def __init__(self,text):
			self.text = text
	
	class Choice(object):
		def __init__(self,options):
			self.options = options
	
	def on_back_allowed_change(self,isallowed): pass
	def on_forward_allowed_change(self,isallowed): pass
	def on_prev_item_change(self,iteminfo): pass
	def on_curr_item_change(self,iteminfo): pass
	def on_section_change(self,name): pass

class TextFrameContent(object):
	
	def __init__(self,frame,info,enabled):
		self.label = Label(frame,text=info.text,justify=LEFT,
			state=NORMAL if enabled else DISABLED)
		self.label.pack(side=TOP,anchor=W)
		
	def destroy(self):
		self.label.destroy()
		
class ChoiceFrameContent(object):
	
	def __init__(self,frame,info,enabled,onchange):
		self.var = StringVar()
		self.radios = []
		for o in info.options:
			r = Radiobutton(frame,text=o,variable=self.var,justify=LEFT,
				state=NORMAL if enabled else DISABLED,
				command=self._make_callback(o,onchange))
			r.pack(side=TOP,anchor=W)
			self.radios.append(r)
		
	def _make_callback(self,option,callback):
		return lambda: callback(option)
		
	def destroy(self):
		for r in self.radios:
			r.destroy()

class RunnerGUI(object):
	"""Dumb frontend for runner, reacts to state change events,
		sends user interaction events"""

	listener = None
	fleft = None
	fright = None
	bnext = None
	bprev = None
	leftcontent = None
	rightcontent = None
	
	def __init__(self,master):
		
		fmain = Frame(master)
		fmain.pack(side=TOP)		
		
		fbottom = Frame(fmain)
		fbottom.pack(side=BOTTOM,fill=BOTH,expand=1)
		
		self.bnext = Button(fbottom,text="Next >>",command=self.fire_on_next)
		self.bnext.pack(side=RIGHT,padx=12,pady=12)
		
		self.bprev = Button(fbottom,text="<< Prev",command=self.fire_on_prev)
		self.bprev.pack(side=LEFT,padx=12,pady=12)
		
		self.fright = Frame(fmain,width=200,height=200)
		self.fright.pack_propagate(0)
		self.fright.pack(side=RIGHT,fill=BOTH,expand=1,padx=12,pady=12)
		
		self.fleft = Frame(fmain,width=200,height=200)
		self.fleft.pack_propagate(0)
		self.fleft.pack(side=LEFT,fill=BOTH,expand=1,padx=12,pady=12)

	def fire_on_next(self):
		if self.listener: self.listener.on_next()

	def fire_on_prev(self):
		if self.listener: self.listener.on_prev()

	def fire_on_change_selection(self,val):
		if self.listener: self.listener.on_change_selection(val)

	def on_back_allowed_change(self,isallowed):
		self.bprev.config(state=NORMAL if isallowed else DISABLED)
		
	def on_forward_allowed_change(self,isallowed):
		self.bnext.config(state=NORMAL if isallowed else DISABLED)
	
	def on_prev_item_change(self,iteminfo):
		if self.leftcontent:
			self.leftcontent.destroy()
			self.leftcontent = None
			
		if isinstance(iteminfo,RunnerListener.Text):
			self.leftcontent = TextFrameContent(self.fleft,iteminfo,False)
		elif isinstance(iteminfo,RunnerListener.Choice):
			self.leftcontent = ChoiceFrameContent(self.fleft,iteminfo,False,lambda v: None)
	
	def on_curr_item_change(self,iteminfo):
		if self.rightcontent:
			self.rightcontent.destroy()
			self.rightcontent = None
			
		if isinstance(iteminfo,RunnerListener.Text):
			self.rightcontent = TextFrameContent(self.fright,iteminfo,True)
		elif isinstance(iteminfo,RunnerListener.Choice):
			self.rightcontent = ChoiceFrameContent(self.fright,iteminfo,True,
				self.fire_on_change_selection)
				
	def on_section_change(self,name):
		pass
			
print "before run"		
Runner().run()
print "after run"
