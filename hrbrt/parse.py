
ALL_CHARACTERS = (
    "abcdefghijklmnopqrstuvwxyz"
    +"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    +"0123456789"
    +"""`!"$%^&*()_-+=[{]}#~;:'@,<.>/?\\| \t"""
)


class Input(object):
    """Immutable wrapper for the input string. Holds a 
    position in the input. Holds a reference to the Input 
    it was branched from and the last Input branched from 
    it."""
    
    _pos = 0
    _data = None
    _child = None
    _parent = None
    
    def __init__(self,data):
        self._pos = 0
        self._data = data+chr(0)
        self._child = None
        self._parent = None
        
    def next(self):
        """Return the next symbol from the input string and 
        advance the position"""
        s = self._data[self._pos]
        self._pos += 1
        return s
        
    def branch(self):
        """Return a new Input at the same position as this one, 
        which holds a reference to this input"""
        b = Input(self._data)
        b._pos = self._pos
        b._parent = self
        self._child = b
        return b
        
    def commit(self):
        """Advance the position of the parent Input to 
        the same position as this one. In other words 
        allow the advancement made to the branched input to 
        take effect on the parent."""
        if self._parent is not None:
            self._parent._pos = self._pos
            
    def get_deepest_pos(self):
        """Returns the position of the last Input which descends 
        from this one"""
        if self._child is not None:
            return self._child.get_deepest_pos()
        else:
            return self._pos


class ValidationError(Exception):
    pass
    

class Document(object):

    _sections = None
    sections = property(lambda s: list(s._sections))
    _is_completed = False
    is_completed = property(lambda s: s._is_completed)
    
    def __init__(self,sections):
        self._sections = sections
        self._is_completed = False
        for s in sections:
            if getattr(s,"is_completed",False):
                self._is_completed = True
                break
        
    def __repr__(self):
        return "Document(%s)" % repr(self._sections)
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        items = []
        sec = FirstSection.parse(input)
        if sec is None: return None
        items.append(sec)
        
        sec = ZeroOrMore(Section).parse(input)
        if sec is None: return None
        items.extend(sec)
        
        if Char(chr(0)).parse(input) is None: return None
        
        input.commit()
        doc = Document(items)
                
        return doc
        
    def _walk_section(self,sec,endsec,path,lastlead,sections):
        """Walks the goto graph from this section. Raises 
        ValidationError for invalid path. Returns True if 
        path to end found."""
        
        sname = sec.heading.lower() if hasattr(sec,"heading") else "first"
        cbs = filter(lambda x: isinstance(x,ChoiceBlock), sec.items)
        found_valid = False
        
        # end section is itself a valid path
        # (at this point we assume it falls through)
        if sec is endsec:
            found_valid = True

        # only the end section may be choiceless
        if len(cbs)==0 and sec is not endsec:
            raise ValidationError(('Section "%s" has no choice blocks and so '
                    +'cannot reach end of document') % sname)

        # iterate over choice blocks
        for b in cbs:
        
            last_block = b is cbs[-1]
            gcs = filter(lambda c: c.goto is not None, b.choices)
            
            # iterate over choices with gotos
            for c in gcs:
            
                last_goto = last_block and c is gcs[-1]
                target = sections[c.goto.lower()]
                newpath = path+[sec]
                newlastlead = ( len(newpath)-1 
                        if found_valid or not last_goto else lastlead )
                
                # Is target a loop?
                if target in newpath:
                    # must be potential exit following the section
                    if newlastlead==-1 or newlastlead < newpath.index(target):
                        raise ValidationError('Dead-end loop found in section "%s"' % sname)    
                else:
                    # Recurse to target section
                    if self._walk_section(target,endsec,newpath,
                            newlastlead,sections):
                        found_valid = True
                        
            # if block doesnt fall through, stop
            if not any([c.goto is None for c in b.choices]):
                # End section *must* fall all the way through
                if sec is endsec:
                    raise ValidationError(('End section "%s" has no '
                        +'choices that reach end of document') % sname)
                break
        else:
            # Fell through last block
            # Only the end section may fall through
            if sec is not endsec:
                raise ValidationError(('Section "%s" has one or more '
                    +'choices that reach end of section and so never '
                    +'reach end of document') % sname)
                    
        return found_valid
        
    def _validate(self):
    
        # Collect sections into map, checking for duplicates        
        sectionmap = {}
        for s in self.sections[1:]:
            n = s.heading.lower()
            if n in sectionmap:
                raise ValidationError("Duplicate section name '%s'" % n)
            sectionmap[n] = s

        # Iterate over goto references, checking sections exist            
        for s in self.sections:
            for b in s.items:
                if isinstance(b,ChoiceBlock):
                    for c in b.choices:
                        if c.goto is not None:
                            n = c.goto.lower()
                            if n not in sectionmap:
                                raise ValidationError("Go-to references unknown section '%s'" % n)
                                                                
        # walk all goto paths
        self._walk_section(self.sections[0],self.sections[-1], 
            [],-1,sectionmap)
        
    def validate(self):
        try:
            self._validate()
        except ValidationError as e:
            return str(e)
        return None
        

class FirstSection(object):

    _items = None
    items = property(lambda s: list(s._items))
    _feedback = None
    feedback = property(lambda s: s._feedback)
    _is_completed = False
    is_completed = property(lambda s: s._is_completed)

    def __init__(self,items,feedback):
        self._items = items
        self._feedback = feedback
        self._is_completed = False
        for i in items:
            if getattr(i,"is_completed",False):
                self._is_completed = True
                break
        if self.feedback is not None:
            self._is_completed = True
        
    def __repr__(self):
        return "FirstSection(%s,%s)" % (
            repr(self._items),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()        
        cont = SectionContent.parse(input)
        if cont is None: return None        
        input.commit()
        return FirstSection(cont.items,cont.feedback)
        
        
class Section(object):

    _heading = None
    heading = property(lambda s: s._heading)
    _items = None
    items = property(lambda s: list(s._items))
    _feedback = None
    feedback = property(lambda s: s._feedback)
    _is_completed = False
    is_completed = property(lambda s: s._is_completed)
    
    def __init__(self,heading,items,feedback):
        self._heading = heading
        self._items = items
        self._feedback = feedback
        self._is_completed = False
        for i in items:
            if getattr(i,"is_completed",False):
                self._is_completed = True
                break
        if feedback is not None:
            self._is_completed = True
        
    def __repr__(self):
        return "Section(%s,%s,%s)" % (
            repr(self._heading),repr(self._items),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        head = Heading.parse(input)
        if head is None: return None
        
        cont = SectionContent.parse(input)
        if cont is None: return None
        
        input.commit()
        return Section(head.name,cont.items,cont.feedback)
        
        
class SectionContent(object):
    
    _items = None
    items = property(lambda s: list(s._items))
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,items,feedback):
        self._items = items
        self._feedback = feedback
        
    def __repr__(self):
        return "SectionContent(%s,%s)" % (
            repr(self._items),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        items = []
        flines = []
        
        while True:
            l = Alternatives(BlankLine,
                    Sequence(Not(StarterLine),FeedbackLine)).parse(input)
            if l is None:
                break
            elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
                flines.append(l[1].text)
                
        while True:
            i = Alternatives(ChoiceBlock,InstructionBlock,
                TextBlock).parse(input)
            if i is None: break
            items.append(i)
            if not isinstance(i,ChoiceBlock) and i.feedback is not None:
                flines.append(i.feedback)
        if len(items)==0: return None
                
        last = None
        for i in items:
            if isinstance(i,ChoiceBlock) and isinstance(last,ChoiceBlock):
                raise ValidationError("Consecutive choice blocks are not allowed. "
                    +"Separate with text block or instruction block")
            last = i
                
        input.commit()
        return SectionContent(items,
            " ".join(flines) if len(flines)>0 else None )
        
    
class Heading(object):

    _name = None
    name = property(lambda s: s._name)
    
    def __init__(self,name):
        self._name = name
        
    def __repr__(self):
        return "Heading(%s)" % repr(self._name)
        
    @staticmethod
    def parse(input):
        input = input.branch()
    
        Optional(QuoteMarker).parse(input)
    
        if HeadingMarker.parse(input) is None: return None
        
        Optional(LineWhitespace).parse(input)
        
        name = Name.parse(input)
        if name is None: return None

        if HeadingMarker.parse(input) is None: return None
        
        if Newline.parse(input) is None: return None

        input.commit()            
        return Heading(name.text)


class QuoteMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if OneOrMore(Sequence(ZeroOrMore(Char(' \t')),
                Char('>'))).parse(input) is None: return None
        ZeroOrMore(Char(' \t')).parse(input)
        input.commit()
        return QuoteMarker()


class HeadingMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Char("=").parse(input) is None: return None
        if OneOrMore(Char("=")).parse(input) is None: return None
        input.commit()
        return HeadingMarker()


class Name(object):

    _CHARACTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    
    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "Name(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()
    
        i = []
        r = Char(Name._CHARACTERS).parse(input)
        if r is None: return None
        i.append(r)
        
        r = ZeroOrMore(Char(Name._CHARACTERS+" ")).parse(input)
        if r is None: return None
        i.extend(r)
    
        input.commit()
        return Name("".join(i).strip())
        

class Newline(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Alternatives(Sequence(Char("\r"),Char("\n")),
                Char("\n"),Char("\r")).parse(input) is None: return None
        input.commit()
        return Newline()


class ChoiceBlock(object):
    
    _choices = None
    choices = property(lambda s: list(s._choices))
    _feedback = None
    feedback = property(lambda s: s._feedback)
    _is_completed = False
    is_completed = property(lambda s: s._is_completed)
    
    def __init__(self,choices,feedback):
        self._choices = choices
        self._feedback = feedback
        self._is_completed = False
        for c in choices:
            if c.mark is not None:
                self._is_completed = True
                break
        if feedback is not None:
            self._is_completed = True
        
    def __repr__(self):
        return "ChoiceBlock(%s,%s)" % (
            repr(self._choices),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input.branch()
        
        choices = []
        flines = []
        
        l = FirstChoice.parse(input)
        if l is None: return None
        choices.append(l)
        if l.feedback is not None:
            flines.append(l.feedback)

        while True:
            l = Alternatives(BlankLine,Choice,
                Sequence(Not(StarterLine),FeedbackLine)).parse(input)
            if l is None:
                break
            elif isinstance(l,Choice):
                choices.append(l)
                if l.feedback is not None:
                    flines.append(l.feedback)
            elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
                flines.append(l[1].text)        
        
        input.commit()
        return ChoiceBlock(choices,
            " ".join(flines) if len(flines)>0 else None)
    
    
class InstructionBlock(object):
    
    _text = None
    text = property(lambda s: s._text)
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,text,feedback):
        self._text = text
        self._feedback = feedback
        
    def __repr__(self):    
        return "InstructionBlock(%s,%s)" % (
            repr(self._text),repr(self._feedback))
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        tlines = []
        flines = []
        
        l = FirstInstructionLine.parse(input)
        if l is None: return None
        tlines.append(l.text)
        
        while True:
            l = Alternatives(BlankLine,InstructionLine,
                Sequence(Not(StarterLine),FeedbackLine)).parse(input)
            if l is None: 
                break
            elif isinstance(l,InstructionLine):
                tlines.append(l.text.strip())
            elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
                flines.append(l[1].text.strip())
                
        input.commit()
        return InstructionBlock(" ".join(tlines),
            " ".join(flines) if len(flines)>0 else None)
        
    
class TextBlock(object):
    
    _text = None
    text = property(lambda s: s._text)
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,text,feedback):
        self._text = text
        self._feedback = feedback
        
    def __repr__(self):
        return "TextBlock(%s,%s)" % (
            repr(self._text),repr(self._feedback) )
    
    @staticmethod
    def parse(input):
        input = input.branch()
        
        tlines = []
        flines = []
        
        l = FirstTextLine.parse(input)
        if l is None: return None
        tlines.append(l.text)
        
        while True:
            l = Alternatives(BlankLine,TextLine,
                    Sequence(Not(StarterLine),FeedbackLine)).parse(input)
            if l is None: 
                break
            elif isinstance(l,TextLine):
                tlines.append(l.text.strip())
            elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
                flines.append(l[1].text.strip())
                    
        input.commit()
        return TextBlock( " ".join(tlines),
            " ".join(flines) if len(flines)>0 else None )
    
    
class TextLine(object):

    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "TextLine(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()
    
        Optional(QuoteMarker).parse(input)
    
        if TextLineMarker.parse(input) is None: return None

        content = TextLineContent.parse(input)
        if content is None: return None    
        
        input.commit()    
        return TextLine(content.text)


class FirstTextLine(object):

    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "FirstTextLine(%s)" % repr(self._text)

    @staticmethod
    def parse(input):
        input = input.branch()
    
        Optional(QuoteMarker).parse(input)
    
        if FirstTextLineMarker.parse(input) is None: return None

        content = TextLineContent.parse(input)
        if content is None: return None    
        
        input.commit()    
        return FirstTextLine(content.text)


class TextLineContent(object):

    _text = None
    text = property(lambda s: s._text)

    def __init__(self,text):
        self._text = text
        
    def __repr__(self):    
        return "TextLineContent(%s)" % repr(self._text)

    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(LineWhitespace).parse(input)
        
        text = LineText.parse(input)
        if text is None: return None
        
        if Newline.parse(input) is None: return None
        
        input.commit()
        return TextLineContent(text.text)


class TextLineMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Char(":").parse(input) is None: return None
        if Not(Char(":")).parse(input) is None: return None
        input.commit()
        return TextLineMarker()


class FirstTextLineMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Char(":").parse(input) is None: return None
        if Char(":").parse(input) is None: return None
        input.commit()
        return FirstTextLineMarker()


class LineText(object):

    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "LineText(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        i = OneOrMore(Char(ALL_CHARACTERS)).parse(input)
        if i is None: return None
        
        input.commit()
        return LineText("".join(i).strip())


class BlankLine(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(QuoteMarker).parse(input)
        
        Optional(LineWhitespace).parse(input)

        if Newline.parse(input) is None: return None

        input.commit()        
        return BlankLine()
        
    def __repr__(self):
        return "BlankLine()"


class LineWhitespace(object):

    @staticmethod
    def parse(input):
        input = input.branch()        
        if OneOrMore(Char(" \t")).parse(input) is None: return None        
        input.commit()
        return LineWhitespace()


class InstructionLine(object):
    
    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text

    def __repr__(self):
        return "InstructionLine(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()    
        
        Optional(QuoteMarker).parse(input)
        
        if InstructionLineMarker.parse(input) is None: return None

        text = TextLineContent.parse(input)
        if text is None: return None        
        
        input.commit()
        return InstructionLine(text.text)


class InstructionLineMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()        
        if Char('%').parse(input) is None: return None
        if Not(Char('%')).parse(input) is None: return None
        input.commit()
        return InstructionLineMarker()


class FirstInstructionLine(object):
    
    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text

    def __repr__(self):
        return "FirstInstructionLine(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()    
        
        Optional(QuoteMarker).parse(input)
        
        if FirstInstructionLineMarker.parse(input) is None: return None

        text = TextLineContent.parse(input)
        if text is None: return None        
        
        input.commit()
        return FirstInstructionLine(text.text)


class FirstInstructionLineMarker(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Char('%').parse(input) is None: return None
        if Char('%').parse(input) is None: return None
        input.commit()
        return FirstInstructionLineMarker()


class Choice(object):

    _mark = None
    mark = property(lambda s: s._mark)
    _description = None
    description = property(lambda s: s._description)
    _response = None
    response = property(lambda s: s._response)
    _goto = None
    goto = property(lambda s: s._goto)
    _feedback = None
    feedback = property(lambda s: s._feedback)

    def __init__(self,mark,description,response,goto,feedback):
        self._mark = mark
        self._description = description
        self._response = response
        self._goto = goto
        self._feedback = feedback
        
    def __repr__(self):
        return "Choice(%s,%s,%s,%s,%s)" % ( repr(self._mark),
            repr(self._description),repr(self._response),
            repr(self._goto), repr(self._feedback) )

    def set_mark(self,mark):
        self._mark = mark
            
    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(QuoteMarker).parse(input)

        if TextLineMarker.parse(input) is None: return None

        Optional(LineWhitespace).parse(input)
        
        marker = ChoiceMarker.parse(input)
        if marker is None: return None

        content = ChoiceContent.parse(input)
        if content is None: return None
        
        input.commit()
        return Choice(marker.mark,content.description,
            content.response,content.goto,content.feedback)
        
        
class FirstChoice(object):

    _mark = None
    mark = property(lambda s: s._mark)
    _description = None
    description = property(lambda s: s._description)
    _response = None
    response = property(lambda s: s._response)
    _goto = None
    goto = property(lambda s: s._goto)
    _feedback = None
    feedback = property(lambda s: s._feedback)

    def __init__(self,mark,description,response,goto,feedback):
        self._mark = mark
        self._description = description
        self._response = response
        self._goto = goto
        self._feedback = feedback
        
    def __repr__(self):
        return "FirstChoice(%s,%s,%s,%s,%s)" % ( repr(self._mark),
            repr(self._description),repr(self._response),
            repr(self._goto),repr(self._feedback) )

    def set_mark(self,mark):
        self._mark = mark
            
    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(QuoteMarker).parse(input)

        if FirstTextLineMarker.parse(input) is None: return None

        Optional(LineWhitespace).parse(input)
        
        marker = ChoiceMarker.parse(input)
        if marker is None: return None

        content = ChoiceContent.parse(input)
        if content is None: return None
        
        input.commit()
        return FirstChoice(marker.mark,content.description,
            content.response,content.goto,content.feedback)
        

class ChoiceMarker(object):
    
    _mark = None
    mark = property(lambda s: s._mark)
    
    def __init__(self,mark):
        self._mark = mark
        
    def __repr__(self):
        return "ChoiceMarker(%s)" % repr(self._mark)
        
    @staticmethod
    def parse(input):
        input = input.branch()
                
        if ChoiceMarkerOpen.parse(input) is None: return None
        
        Optional(LineWhitespace).parse(input)
        
        mark = Optional(ChoiceMarkerMark).parse(input)
        if mark is None: return None
        
        if ChoiceMarkerClose.parse(input) is None: return None
        
        input.commit()
        return ChoiceMarker(mark.text if mark is not False else None)
        

class ChoiceMarkerOpen(object):
    
    @staticmethod
    def parse(input):
        input = input.branch()
        if Char('[').parse(input) is None: return None
        input.commit()
        return ChoiceMarkerOpen()
    
    
class ChoiceMarkerClose(object):
    
    @staticmethod
    def parse(input):
        input = input.branch()
        if Char(']').parse(input) is None: return None
        input.commit()
        return ChoiceMarkerClose()
    
    
class ChoiceMarkerMark(object):

    _text = None
    text = property(lambda s: s._text)

    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "ChoiceMarkerMark(%s)" % self._text
        
    @staticmethod
    def parse(input):
        input = input.branch()

        i = OneOrMore(Char(ALL_CHARACTERS.replace("]",""))).parse(input)
        if i is None: return None            
        
        input.commit()
        return ChoiceMarkerMark("".join(i).strip())


class ChoiceContent(object):

    _description = None
    description = property(lambda s: s._description)
    _response = None
    response = property(lambda s: s._response)
    _goto = None
    goto = property(lambda s: s._goto)
    _feedback = None
    feedback = property(lambda s: s._feedback)

    def __init__(self,description,response,goto,feedback):
        self._description = description
        self._response = response
        self._goto = goto
        self._feedback = feedback
        
    def __repr__(self):
        return "ChoiceContent(%s,%s,%s,%s)" % (
            repr(self._description),repr(self._response),
            repr(self._goto),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(LineWhitespace).parse(input)
        
        desc = ChoiceDescription.parse(input)
        if desc is None: return None
        
        resp = Optional(ChoiceResponse).parse(input)

        Optional(LineWhitespace).parse(input)
        
        if Newline.parse(input) is None: return None
        
        input.commit()

        fb = [desc.feedback]
        if resp is not False: fb.append(resp.feedback)
        fb = filter(lambda x: x is not None,fb)
                
        return ChoiceContent(desc.text,
            resp.description if resp is not False else None,
            resp.goto if resp is not False else None,
            " ".join(fb) if len(fb)>0 else None)            
    
    
class ChoiceDescription(object):
    
    _text = None
    text = property(lambda s: s._text)
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,text,feedback):
        self._text = text
        self._feedback = feedback
        
    def __repr__(self):    
        return "ChoiceDescription(%s,%s)" % (
            repr(self._text),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        parts = []
        flines = []
        
        p = ChoiceDescPart.parse(input)
        if p is None: return None
        parts.append(p.text.strip())
        
        ps = ZeroOrMore(Sequence(
            ChoiceDescNewline,ChoiceDescPart)).parse(input)
        if ps is None: return None
        parts.extend([p[1].text for p in ps])
        flines.extend(filter(lambda x: x is not None,
            [p[0].feedback for p in ps]))
        
        input.commit()
        return ChoiceDescription(" ".join(parts),
            " ".join(flines) if len(flines)>0 else None)


class ChoiceDescNewline(object):

    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,feedback):
        self._feedback = feedback

    def __repr__(self):
        return "ChoiceDescNewline(%s)" % repr(self._feedback)

    @staticmethod
    def parse(input):
        input = input.branch()
        
        flines = []
    
        if Newline.parse(input) is None: return None

        while True:
            l = Alternatives(
                    BlankLine,
                    Sequence(
                        Not(Alternatives(StarterLine,TextLine)),
                        FeedbackLine)).parse(input)
            if l is None:
                break
            elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
                flines.append(l[1].text)
    
        Optional(QuoteMarker).parse(input)
        
        if TextLineMarker.parse(input) is None: return None
        
        Optional(LineWhitespace).parse(input)
        
        if Not(ChoiceMarker).parse(input) is None: return None
        
        input.commit()
        return ChoiceDescNewline(
            " ".join(flines) if len(flines)>0 else None )        
    
    
class ChoiceDescPart(object):

    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):    
        return "ChoiceDescPart(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input = input.branch()
        text = OneOrMore(Alternatives(
                Char(ALL_CHARACTERS.replace("-","")),
                Sequence(Char('-'),Not(Char('-'))))).parse(input)
        if text is None: return None
        input.commit()
        return ChoiceDescPart("".join(
                [t[0] if isinstance(t,list) else t for t in text]).strip())
        
    
class ChoiceResponse(object):
    
    _description = None
    description = property(lambda s: s._description)
    _goto = None
    goto = property(lambda s: s._goto)
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,description,goto,feedback):
        self._description = description
        self._goto = goto
        self._feedback = feedback
    
    def __repr__(self):
        return "ChoiceResponse(%s,%s,%s)" % (
            repr(self._description),repr(self._goto),repr(self._feedback) )
    
    @staticmethod
    def parse(input):
        input = input.branch()

        n1 = Optional(ChoiceDescNewline).parse(input)
        
        if ChoiceResponseSeparator.parse(input) is None: return None

        result = Sequence(
            Optional(ChoiceDescNewline),
            ChoiceResponseDesc,
            Optional(ChoiceGoto)).parse(input)
        if result is not None:
            n2 = result[0]
            desc = result[1]
            goto = result[2]
        else:
            result = ChoiceGoto.parse(input)
            if result is None: return None
            n2 = False
            desc = False
            goto = result

        flines = []
        if n1 is not False: flines.append(n1.feedback)
        if n2 is not False: flines.append(n2.feedback)
        if desc is not False: flines.append(desc.feedback)
        if goto is not False: flines.append(goto.feedback)
        flines = filter(lambda x: x is not None,flines)
        
        input.commit()
        return ChoiceResponse(
            desc.text if desc is not False and len(desc.text)>0 else None,
            goto.secname if goto is not False else None,
            " ".join(flines) if len(flines)>0 else None )
            

class ChoiceResponseSeparator(object):

    @staticmethod
    def parse(input):
        input = input.branch()
        if Char('-').parse(input) is None: return None
        if Char('-').parse(input) is None: return None
        input.commit()
        return ChoiceResponseSeparator()
                

class ChoiceResponseDesc(object):

    _text = None
    text = property(lambda s: s._text)
    _feedback = None
    feedback = property(lambda s: s._feedback)
    
    def __init__(self,text,feedback):
        self._text = text
        self._feedback = feedback
                
    def __repr__(self):
        return "ChoiceResponseDesc(%s,%s)" % (
            repr(self._text),repr(self._feedback) )
                
    @staticmethod
    def parse(input):    
        input = input.branch()
        
        parts = []
        flines = []
        
        p = ChoiceResponseDescPart.parse(input)
        if p is None: return None
        parts.append(p.text)
        
        ps = ZeroOrMore(Sequence(
            ChoiceDescNewline,ChoiceResponseDescPart)).parse(input)
        if ps is None: return None
        parts.extend([p[1].text for p in ps])
        flines.extend(filter(lambda s: s is not None, 
            [p[0].feedback for p in ps]))
        
        input.commit()
        return ChoiceResponseDesc(" ".join(parts),
            " ".join(flines) if len(flines)>0 else None)
                
        
class ChoiceResponseDescPart(object):

    _text = None
    text = property(lambda s: s._text)
    
    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "ChoiceResponseDescPart(%s)" % repr(self._text)
        
    @staticmethod
    def parse(input):
        input.branch()
        text = OneOrMore(Alternatives(
                Char(ALL_CHARACTERS.replace("G","")),
                Sequence(
                    Char('G'),
                    Not(Sequence(Char('O'),Char(' '),Char('T'),Char('O')))
                )
            )).parse(input)
        if text is None: return None
        input.commit()
        return ChoiceResponseDescPart("".join(
                [t[0] if isinstance(t,list) else t for t in text]).strip())
        
        
class ChoiceGoto(object):
        
    _secname = None
    secname = property(lambda s: s._secname)
    _feedback = None
    feedback = property(lambda s: s._feedback)
        
    def __init__(self,secname,feedback):
        self._secname = secname
        self._feedback = feedback
        
    def __repr__(self):
        return "ChoiceGoto(%s,%s)" % (
            repr(self._secname),repr(self._feedback) )
        
    @staticmethod
    def parse(input):
        input = input.branch()

        nl = Optional(ChoiceDescNewline).parse(input)
        
        if GotoMarker.parse(input) is None: return None
        
        Optional(LineWhitespace).parse(input)
        
        secname = Name.parse(input)
        if secname is None: return None
        
        Optional(EndPunctuation).parse(input)
        
        input.commit()
        return ChoiceGoto( secname.text,
            nl.feedback if nl is not False else None )
        
        
class GotoMarker(object):
    
    @staticmethod
    def parse(input):
        input = input.branch()
        if Sequence(Char('G'),Char('O'),Char(' '),
                Char('T'),Char('O')).parse(input) is None: return None
        input.commit()
        return GotoMarker()
    
    
class EndPunctuation(object):
    
    _CHARACTERS = ".,!?;:"
    
    @staticmethod
    def parse(input):
        input = input.branch()
        if OneOrMore(Char(EndPunctuation._CHARACTERS)).parse(input) is None: return None
        input.commit()
        return EndPunctuation()
        
        
class FeedbackLine(object):

    _text = None
    text = property(lambda s: s._text)

    def __init__(self,text):
        self._text = text
        
    def __repr__(self):
        return "FeedbackLine(%s)" % self._text
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        Optional(QuoteMarker).parse(input)

        text = LineText.parse(input)
        if text is None: return None
        
        if Newline.parse(input) is None: return None
        
        input.commit()
        return FeedbackLine(text.text)


class StarterLine(object):

    _line = None
    line = property(lambda s: s._line)

    def __init__(self,line):
        self._line = line
        
    def __repr__(self):
        return "StarterLine(%s)" % repr(self._line)
        
    @staticmethod
    def parse(input):
        input = input.branch()
        
        line = Alternatives(FirstTextLine,FirstInstructionLine,
            Heading,FirstChoice).parse(input)
        if line is None: return None
        
        input.commit()
        return StarterLine(line)
        

class Alternatives(object):
    """( A | B ) implementation"""
    
    _alts = None
    
    def __init__(self,*alts):
        self._alts = alts
        
    def parse(self,input):
        input = input.branch()
        for a in self._alts:
            r = a.parse(input)
            if r is not None: 
                input.commit()
                return r
        return None
    
    
class OneOrMore(object):
    """A+ implementation"""
    
    _item = None
    
    def __init__(self,item):
        self._item = item
    
    def parse(self,input):
        input = input.branch()
        i = []
        r = self._item.parse(input)
        if r is None: return None
        i.append(r)
        while True:
            r = self._item.parse(input)
            if r is None: break
            i.append(r)
        input.commit()
        return i
        
        
class ZeroOrMore(object):
    """B* implementation"""

    _item = None
    
    def __init__(self,item):
        self._item = item
        
    def parse(self,input):
        input = input.branch()
        i = []
        while True:
            r = self._item.parse(input)
            if r is None: break
            i.append(r)
        input.commit()
        return i
        
        
class Optional(object):
    """A? implementation"""
    
    _item = None
    
    def __init__(self,item):
        self._item = item
        
    def parse(self,input):
        input = input.branch()
        r = self._item.parse(input)
        if r is None: return False
        input.commit()
        return r
        
        
class NOf(object):
    """A{n} implementation"""
    
    _times = 0
    _item = None
    
    def __init__(self,times,item):
        self._times = times
        self._item = item
        
    def parse(self,input):
        input = input.branch()
        i = []
        for j in range(self._times):
            r = self._item.parse(input)
            if r is None: return None
            i.append(r)
        input.commit()
        return i
        

class Sequence(object):
    """A B implementation"""
    
    _items = None
    
    def __init__(self,*items):
        self._items = items
        
    def parse(self,input):
        input = input.branch()
        i = []
        for j in self._items:
            r = j.parse(input)
            if r is None: return None
            i.append(r)
        input.commit()
        return i
        

class Not(object):
    """!A implementation"""
    
    _item = None
    
    def __init__(self,item):
        self._item = item
        
    def parse(self,input):
        input = input.branch()
        if self._item.parse(input) is not None: 
            return None
        return False
            
        
class Char(object):
    """Parses a single symbol of those specified in 
    the given string"""

    _chars = None
    
    def __init__(self,chars):
        self._chars = chars
        
    def parse(self,input):
        input = input.branch()
        c = input.next()
        if not c in self._chars: return None
        input.commit()
        return c


class InputError(Exception):
    pass
