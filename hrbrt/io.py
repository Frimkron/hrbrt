import sys
import re
import textwrap
import json
import xml.dom
import xml.dom.minidom
from . import parse


class JsonIO(object):

    EXTENSIONS = ["json","js"]

    @staticmethod
    def write(document,stream):
        JsonIO.INST._write(document,stream)
        
    def _write(self,document,stream):
        obj = self._visit_Document(document)
        stream.write(json.dumps(obj, indent=4))
        
    def _visit(self,item):
        fname = "_visit_%s" % type(item).__name__
        return getattr(self,fname,lambda x: None)(item)
        
    def _visit_Document(self,doc):
        seclist = []
        for s in doc.sections:
            seclist.append(self._visit(s))
        return seclist
        
    def _visit_FirstSection(self,sec):
        blocklist = []
        for b in sec.items:
            blocklist.append(self._visit(b))
        return { "blocks": blocklist, "feedback": sec.feedback }
        
    def _visit_Section(self,sec):
        blocklist = []
        for b in sec.items:
            blocklist.append(self._visit(b))
        return { "name": sec.heading, "blocks": blocklist, 
                "feedback": sec.feedback }
                
    def _visit_TextBlock(self,tblock):
        return { "type": "text", "content": tblock.text }
        
    def _visit_InstructionBlock(self,iblock):
        return { "type": "instructions", "content": iblock.text }
        
    def _visit_ChoiceBlock(self,cblock):
        choicelist = []
        for c in cblock.choices:
            choicelist.append(self._visit_Choice(c))
        return { "type": "choices", "content": choicelist,
                "feedback": cblock.feedback }
        
    def _visit_Choice(self,choice):
        return { "mark": choice.mark, "description": choice.description,
                "response": choice.response, "goto": choice.goto }
        
JsonIO.INST = JsonIO()


class HtmlIO(object):
    
    EXTENSIONS = ["htm","html","xhtml"]
    
    @staticmethod
    def write(document,stream):
        # TODO
        pass


class HrbrtIO(object):
    
    EXTENSIONS = ["hb"]
    LINE_WIDTH = 79
    
    @staticmethod
    def read(stream):
        return HrbrtIO.INST._read(stream)
    
    @staticmethod
    def write(document,stream):
        HrbrtIO.INST._write(document,stream)
        
    def _read(self,stream):
        instring = stream.read()
        input = parse.Input(instring)
            
        document = parse.Document.parse(input)
            
        if document is None:
            p = input.get_deepest_pos()
            raise parse.InputError("Parse error near '%s'" % (instring[p:p+100]+"..."))
        
        return document
                            
    def _write(self,doc,stream):
        stream.write( "\n".join(map(self._visit,doc.sections)) )
        
    def _visit(self,item):
        fname = "_visit_%s" % type(item).__name__
        return getattr(self,fname,lambda x: None)(item)
        
    def _visit_FirstSection(self,sec):
        s = ""
        s += "\n".join(map(self._visit,sec.items))
        if sec.feedback is not None:
            s += "\n"
            flines = textwrap.wrap(sec.feedback,HrbrtIO.LINE_WIDTH)
            for line in flines:
                s += "%s\n" % line
        return s
        
    def _visit_Section(self,sec):
        s = "== %s ==\n\n" % sec.heading
        s += "\n".join(map(self._visit,sec.items))
        if sec.feedback is not None:
            s += "\n"
            flines = textwrap.wrap(sec.feedback,HrbrtIO.LINE_WIDTH)
            for line in flines:
                s += "%s\n" % line
        return s
        
    def _visit_TextBlock(self,text):
        lines = textwrap.wrap(text.text,width=HrbrtIO.LINE_WIDTH-3)
        s = ":: %s\n" % lines[0]
        for line in lines[1:]:
            s += ":  %s\n" % line
        return s
        
    def _visit_InstructionBlock(self,instr):
        lines = textwrap.wrap(instr.text,width=HrbrtIO.LINE_WIDTH-3)
        s = "%%%% %s\n" % lines[0]
        for line in lines[1:]:
            s += "%%  %s\n" % line
        return s
        
    def _visit_ChoiceBlock(self,cblock):
        s = ""
        if len(cblock.choices) > 0:
            choicestrs = []
            choicestrs.append(":: %s" % self._visit_Choice(cblock.choices[0]))
            for choice in cblock.choices[1:]:
                choicestrs.append(":  %s" % self._visit_Choice(choice))
            s += "".join(choicestrs)
        if cblock.feedback is not None and len(cblock.feedback)>0:
            s += "\n"
            flines = textwrap.wrap(cblock.feedback,HrbrtIO.LINE_WIDTH)
            for line in flines:
                s += "%s\n" % line
        return s
        
    def _visit_Choice(self,choice):
        s = ""
        dlines = textwrap.wrap(choice.description,HrbrtIO.LINE_WIDTH, 
                        initial_indent="[%s] " % (choice.mark if choice.mark is not None else ""),
                        subsequent_indent=":  ")
        s += "\n".join(dlines)+"\n"
        if choice.response is not None or choice.goto is not None:            
            l = ":      -- "            
            if choice.response is not None:
                rlines = textwrap.wrap(choice.response,HrbrtIO.LINE_WIDTH, 
                            initial_indent=l, subsequent_indent=":  ")
                s += "\n".join(rlines)+"\n"
                if choice.goto is not None:
                    s += ":      "
            else:
                s += l
            if choice.goto is not None:
                s += "GO TO %s\n" % choice.goto
        return s

        
HrbrtIO.INST = HrbrtIO()


class MarkdownIO(object):
    
    EXTENSIONS = ["md","markdown"]
    LINE_WIDTH = 79
    
    @staticmethod
    def write(document,stream):
        MarkdownIO.INST._write(document,stream)
        
    def _write(self,document,stream):
        stream.write("\n".join(map(self._visit_section,document.sections)))
        
    def _visit_section(self,section):
        s = ""
        
        if hasattr(section,"heading"):
            s += section.heading + "\n" + "-"*len(section.heading)+"\n\n"
            
        s += "\n".join(map(self._visit,section.items))
        
        if section.feedback is not None:
            s += "\n" + "".join(map(lambda s: "> %s\n" % s,
                textwrap.wrap(section.feedback,MarkdownIO.LINE_WIDTH-2)))
            
        return s
            
    def _visit(self,item):
        hname = "_visit_%s" % type(item).__name__.lower()
        return getattr(self,hname,self._visit_default)(item)
        
    def _visit_default(self,item):
        return ""
        
    def _visit_textblock(self,block):
        return "".join(map(lambda s: "%s\n" % s,
            textwrap.wrap(block.text,MarkdownIO.LINE_WIDTH)))
        
    def _visit_instructionblock(self,block):
        return ("\n".join(textwrap.wrap(block.text.replace("--",""),
            MarkdownIO.LINE_WIDTH,initial_indent='<!-- ')) + " -->\n")
        
    def _visit_choiceblock(self,block):
        s = ""
        s += "".join(map(self._visit_choice,block.choices))
        
        if block.feedback is not None:
            s += "\n" + "".join(map(lambda s: "> %s\n" % s,
                textwrap.wrap(block.feedback,MarkdownIO.LINE_WIDTH-2)))
        return s
        
    def _headingize(self,text):
        return re.sub("\s","-",
            re.sub("^\d+\s*","",text.lower()))
        
    def _visit_choice(self,choice):
        m = "[%s]" % (choice.mark if choice.mark else "")
        d = choice.description
        if choice.goto:
            d = "[%s](#%s)" % (d,self._headingize(choice.goto))
        r = ""
        if choice.response:
            r = " _%s_" % choice.response
        return "- " + "  ".join(map(lambda s: "%s\n" % s, textwrap.wrap(
            "**%s %s**%s" % (m,d,r),MarkdownIO.LINE_WIDTH-2)))
    
    
MarkdownIO.INST = MarkdownIO()


class XmlIO(object):

    EXTENSIONS = ["xml"]

    @staticmethod
    def write(document,stream):
        XmlIO.INST._write(document,stream)
        
    def _write(self,document,stream):
        doc = xml.dom.minidom.getDOMImplementation().createDocument(None,None,None)
        self._append_to(self._visit_document(document,doc),doc)
        doc.writexml(stream,addindent=" "*4,newl="\n")
        
    def _textel(self,name,text,doc):
        el = doc.createElement(name)
        el.appendChild(doc.createTextNode(text))
        return el
    
    def _append_to(self,child,parent):
        if child and parent:
            parent.appendChild(child)
    
    def _visit(self,item,doc):
        hname = "_visit_%s" % type(item).__name__.lower()
        return getattr(self,hname,self._visit_default)(item,doc)
        
    def _visit_default(self,item,doc):
        return None
    
    def _visit_document(self,document,doc):
        elDoc = doc.createElement("document")
        for section in document.sections:
            self._append_to(self._visit_section(section,doc),elDoc)
        return elDoc
        
    def _visit_section(self,section,doc):
        elSec = doc.createElement("section")
        if hasattr(section,"heading"):
            self._append_to(self._textel("name",section.heading,doc),elSec)
        for block in section.items:
            self._append_to(self._visit(block,doc),elSec)
        if section.feedback:
            self._append_to(self._textel("feedback",section.feedback,doc),elSec)
        return elSec
        
    def _visit_textblock(self,text,doc):
        return self._textel("text",text.text,doc)
        
    def _visit_instructionblock(self,inst,doc):
        return self._textel("instructions",inst.text,doc)
        
    def _visit_choiceblock(self,choice,doc):
        elChoice = doc.createElement("choice")
        for c in choice.choices:
            self._append_to(self._visit_choice(c,doc),elChoice)
        if choice.feedback:
            self._append_to(self._textel("feedback",choice.feedback,doc),elChoice)
        return elChoice
        
    def _visit_choice(self,choice,doc):
        elOpt = doc.createElement("option")
        if choice.mark:
            self._append_to(self._textel("mark",choice.mark,doc),elOpt)
        if choice.description:
            self._append_to(self._textel("desc",choice.description,doc),elOpt)
        if choice.response:
            self._append_to(self._textel("response",choice.response,doc),elOpt)
        if choice.goto:
            self._append_to(self._textel("goto",choice.goto.lower(),doc),elOpt)
        return elOpt

        
XmlIO.INST = XmlIO()
