import collections
import sys
from . import parse


class RunnerError(Exception):
    pass
    

class CommandLineRunner(object):

    FIRST = object()

    @staticmethod
    def run(document):
        CommandLineRunner.INST._run(document, sys.stdin, sys.stdout)
        
    def _run(self,document,ins,outs):        
        
        if len(document.sections)==0: return
        
        # make map of sections
        sections = {}
        for i,s in enumerate(document.sections):
            name = s.heading.lower() if hasattr(s,"heading") else CommandLineRunner.FIRST            
            sections[name] = s

        sname = CommandLineRunner.FIRST

        # walk section graph        
        while sname is not None:
            section = sections[sname]
            sname = self._run_section(section,ins,outs)

    def _run_section(self,section,ins,outs):
        if hasattr(section,"heading"):
            outs.write(section.heading+"\n"
                +"-"*len(section.heading)+"\n\n")
        for block in section.items:
            goto = self._run_block(block,ins,outs)
            if goto is not None: return goto
        return None

    def _run_block(self,block,ins,outs):
        hname = "_run_%s" % type(block).__name__
        return getattr(self,hname,self._run_default)(block,ins,outs)

    def _run_default(self,block,ins,outs):
        return None

    def _wait_for_enter(self,ins,outs):
        outs.write("[enter]")
        outs.flush()
        ins.readline()
        outs.write("\n\n")
        
    def _run_TextBlock(self,block,ins,outs):
        outs.write(block.text+"\n\n")
        self._wait_for_enter(ins,outs)
        return None
        
    def _run_ChoiceBlock(self,block,ins,outs):
        
        for i,c in enumerate(block.choices):
                outs.write("%d) %s\n" % (i+1,c.description))
        outs.write("\n")
        
        while True:
            outs.write("> ")
            outs.flush()
            selstring = ins.readline()
            outs.write("\n\n")
            try:
                selnum = int(selstring)
            except ValueError:
                outs.write("Enter a number\n\n")
                continue
                
            if selnum < 1 or selnum > len(block.choices):
                outs.write("Invalid choice\n\n")
                continue
                
            break
                
        chosen = block.choices[selnum-1]
        
        for c in block.choices:
            c.set_mark("X" if c is chosen else None)
            
        if chosen.response is not None:
            outs.write("%s\n\n" % chosen.response)
            self._wait_for_enter(ins,outs)
    
        if chosen.goto is not None:
            return chosen.goto.lower()
                
        return None

        
CommandLineRunner.INST = CommandLineRunner()


class GuiRunnerGui(object):
    """Dumb frontend for runner, reacts to state change events,
        sends user interaction events"""
        
    class TextFrameContent(object):
    
        def __init__(self,frame,info,enabled):
            self.label = tk.Label(frame,text=info.text,justify=tk.LEFT,
                state=tk.NORMAL if enabled else tk.DISABLED,wraplength=200)
            self.label.pack(side=tk.TOP,anchor=tk.W)
            
        def destroy(self):
            self.label.destroy()
            
    class ChoiceFrameContent(object):
        
        def __init__(self,frame,info,enabled,onchange):
            self.var = tk.IntVar(value=info.selected if info.selected is not None else -1)
            self.radios = []
            for i,o in enumerate(info.options):
                r = tk.Radiobutton(frame,text=o,variable=self.var,justify=tk.LEFT,
                    state=tk.NORMAL if enabled else tk.DISABLED,value=i,
                    command=self._make_callback(i,onchange),wraplength=175)
                r.pack(side=tk.TOP,anchor=tk.W)
                self.radios.append(r)
            
        def _make_callback(self,optindex,callback):
            return lambda: callback(optindex)
            
        def destroy(self):
            for r in self.radios:
                r.destroy()

    listener = None
    fleft = None
    fright = None
    bnext = None
    bprev = None
    leftcontent = None
    rightcontent = None
    
    def __init__(self,master):
        
        fmain = tk.Frame(master)
        fmain.pack(side=tk.TOP)        
        
        fbottom = tk.Frame(fmain)
        fbottom.pack(side=tk.BOTTOM,fill=tk.BOTH,expand=1)
        
        self.bnext = tk.Button(fbottom,text="Next >>",command=self.fire_on_next)
        self.bnext.pack(side=tk.RIGHT,padx=12,pady=12)
        
        self.bprev = tk.Button(fbottom,text="<< Prev",command=self.fire_on_prev)
        self.bprev.pack(side=tk.LEFT,padx=12,pady=12)
        
        self.fright = tk.Frame(fmain,width=200,height=200)
        self.fright.pack_propagate(0)
        self.fright.pack(side=tk.RIGHT,fill=tk.BOTH,expand=1,padx=12,pady=12)
        
        self.fleft = tk.Frame(fmain,width=200,height=200)
        self.fleft.pack_propagate(0)
        self.fleft.pack(side=tk.LEFT,fill=tk.BOTH,expand=1,padx=12,pady=12)

    def fire_on_next(self):
        if self.listener: self.listener.on_next()

    def fire_on_prev(self):
        if self.listener: self.listener.on_prev()

    def fire_on_change_selection(self,val):
        if self.listener: self.listener.on_change_selection(val)

    def on_back_allowed_change(self,isallowed):
        self.bprev.config(state=tk.NORMAL if isallowed else tk.DISABLED)
        
    def on_forward_allowed_change(self,isallowed):
        self.bnext.config(state=tk.NORMAL if isallowed else tk.DISABLED)
    
    def on_prev_item_change(self,iteminfo):
        if self.leftcontent:
            self.leftcontent.destroy()
            self.leftcontent = None
            
        if isinstance(iteminfo,GuiRunnerText):
            self.leftcontent = GuiRunnerGui.TextFrameContent(self.fleft,iteminfo,False)
        elif isinstance(iteminfo,GuiRunnerChoice):
            self.leftcontent = GuiRunnerGui.ChoiceFrameContent(self.fleft,iteminfo,False,
                lambda v: None)
    
    def on_curr_item_change(self,iteminfo):
        if self.rightcontent:
            self.rightcontent.destroy()
            self.rightcontent = None
            
        if isinstance(iteminfo,GuiRunnerText):
            self.rightcontent = GuiRunnerGui.TextFrameContent(self.fright,iteminfo,True)
        elif isinstance(iteminfo,GuiRunnerChoice):
            self.rightcontent = GuiRunnerGui.ChoiceFrameContent(self.fright,iteminfo,True,
                self.fire_on_change_selection)
                
    def on_section_change(self,name):
        pass
        
        
class GuiRunnerText(object):
    def __init__(self,text):
        self.text = text
    
        
class GuiRunnerChoice(object):
    def __init__(self,options,selected):
        self.options = options
        self.selected = selected
        
        
class GuiRunner(object):

    class Step(object):
        
        sectionname = None
        next = None

        def __init__(self,sectionname,next):
            self.sectionname = sectionname
            self.next = next
        
        @staticmethod
        def from_block(sectionname,secmapper,next,block): 
            if isinstance(block,parse.TextBlock):
                return GuiRunner.TextStep.from_block(sectionname,next,block)
            elif isinstance(block,parse.ChoiceBlock):
                return GuiRunner.ChoiceStep.from_block(sectionname,secmapper,next,block)
            else:
                return None
        
        def can_go_forward(self):
            return True
            
        def forward(self):
            return self.next
            

    class TextStep(Step):
    
        text = None
        
        @staticmethod
        def from_block(sectionname,next,textblock):
            return GuiRunner.TextStep(sectionname,next,textblock.text)
        
        def __init__(self,sectionname,next,text):
            GuiRunner.Step.__init__(self,sectionname,next)
            self.text = text
            
        def to_item(self):
            return GuiRunnerText(self.text)
            
    class ChoiceStep(Step):
    
        Option = collections.namedtuple("Option","desc step")
    
        options = None
        selected = None
        _docupdater = None
    
        @staticmethod
        def from_block(sectionname,secmapper,next,choiceblock):
            selected = None
            options = []
            for i,choice in enumerate(choiceblock.choices):
                if choice.mark and not selected:
                    selected = i
                secmapper(GuiRunner.ChoiceStep._make_map_callback(
                    sectionname,next,choice,options))
            return GuiRunner.ChoiceStep(sectionname,next,options,selected,
                GuiRunner.ChoiceStep._make_updater_callback(choiceblock))

        @staticmethod
        def _make_updater_callback(choiceblock):
            def updater(val):
                for i,choice in enumerate(choiceblock.choices):
                    choice.set_mark( "X" if i==val else None )
            return updater

        @staticmethod
        def _make_map_callback(sectionname,next,choice,options):
            def callback(sectionmap):
                step = next
                if choice.goto:
                    step = sectionmap[choice.goto.lower()]
                if choice.response:
                    step = GuiRunner.TextStep(sectionname,step,choice.response)
                options.append(GuiRunner.ChoiceStep.Option(choice.description,step))
            return callback
                        
        def __init__(self,sectionname,next,options,selected,docupdater):
            GuiRunner.Step.__init__(self,sectionname,next)
            self._docupdater = docupdater
            self.options = options
            self.set_selected(selected)
            
        def to_item(self):
            return GuiRunnerChoice([o.desc for o in self.options],self.selected)

        def can_go_forward(self):
            return self.selected is not None
            
        def forward(self):
            return self.options[self.selected].step
            
        def set_selected(self,val):
            self.selected = val
            self._docupdater(val)
        
    _gui = None
    _tkroot = None
    _current_secname = None
    _completed = False
    _path = None

    @staticmethod
    def run(document):
        GuiRunner.INST._run(document)
        
    def _run(self,document,tkroot=None,gui=None):
        global tk
        try: 
            import tkinter as tk
        except ImportError:
            try:
                import Tkinter as tk
            except ImportError:
                raise RunnerError("Failed to load tkinter module required to display gui. "
                                   +"You may need to install Tk and/or Tkinter")
    
        if not tkroot: tkroot = tk.Tk()
        self._tkroot = tkroot
        if not gui: gui = GuiRunnerGui(self._tkroot)
        self._gui = gui
        
        self._gui.listener = self
        
        self._path = []
        secmap = {}
        secmap_cbs = []
        for sec in document.sections:
            name = getattr(sec,"heading",None)
            step = None
            for b in reversed(sec.items):
                s = GuiRunner.Step.from_block(name,
                    lambda cb: secmap_cbs.append(cb),step,b)
                if s: step = s
            secmap[name.lower() if name else None] = step
        for cb in secmap_cbs:
            cb(secmap)

        self._current_secname = object()            
        self._path_push( secmap[None] if len(secmap)>0 else None )
            
        self._tkroot.mainloop()
        
        if not self._completed:
            raise RunnerError("User aborted")
        
    def _path_push(self,step):
        self._path.append(step)
        self._path_updated()
        
    def _path_pop(self):
        self._path.pop()
        self._path_updated()
        
    def _path_updated(self):
        new_secname = self._path[-1].sectionname if self._path[-1] else None
        if new_secname != self._current_secname:
            self._current_secname = new_secname
            self._gui.on_section_change(self._current_secname)
        curr_item = ( self._path[-1].to_item() if self._path[-1] is not None else None )
        prev_item = ( self._path[-2].to_item() if len(self._path)>1 else None )
        self._gui.on_curr_item_change(curr_item)
        self._gui.on_prev_item_change(prev_item)
        self._gui.on_forward_allowed_change(self._path[-1].can_go_forward()
            if self._path[-1] is not None else False )
        self._gui.on_back_allowed_change( len(self._path)>1 )
        
    def on_next(self):
        next = self._path[-1].forward()
        if not next:
            self._completed = True
            self._tkroot.quit()
        else:
            self._path_push(next)
        
    def on_prev(self):
        self._path_pop()
        
    def on_change_selection(self,val):    
        old_fa = self._path[-1].can_go_forward()
        self._path[-1].set_selected(val)
        new_fa = self._path[-1].can_go_forward()
        if old_fa != new_fa:
            self._gui.on_forward_allowed_change(new_fa)

        
GuiRunner.INST = GuiRunner()
