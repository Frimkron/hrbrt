# TODO: Unit tests
# TODO: Blocks should not be broken by blank lines or feedback.
#	- feedback blocks should be combined in each section and put
#	in their own attribute
# TODO: Section names should be unique
# TODO: Section names should be valid - post process AST?
# TODO: Recipient may assume to read into next section 
#		when there isn't a goto in a section.
# TODO: Probably no need for line nodes in AST
# TODO: Command line recipient usage 
# TODO: Command line sender usage
# TODO: Tidy up formal definition
# TODO: Command line interactive mode
# TODO: GUI interactive mode for recipient
# TODO: GUI interactive mode for sender
# TODO: Open document output
# TODO: Markdown output :D

"""	
Document <- FirstSection Section* '\x00'
FirstSection <- SectionContent
Section <- Heading SectionContent
SectionContent <- BlankLine* ( ChoiceBlock | InstructionBlock | TextBlock |  FeedbackBlock )+
BlankLine <- QuoteMarker? LineWhitespace? Newline
ChoiceBlock <- Choice+ BlankLine*
InstructionBlock <- InstructionLine+ BlankLine*
TextBlock <- TextLine+ BlankLine*
FeedbackBlock <- ( !( InstructionLine TextLine Choice Heading ) FeedbackLine )+ BlankLine*
QuoteMarker <- '([ \t]*>)+'
LineWhitespace <- '[ \t]+'
Newline <- '(\r\n|\r|\n)'
Choice <- QuoteMarker? TextLineMarker ChoiceMarker ChoiceDescription ChoiceResponse? Newline
ChoiceMarker <- ChoiceMarkerOpen LineWhitespace? ChoiceMarkerText? ChoiceMarkerClose
ChoiceMarkerOpen <- '['
ChoiceMarkerText <- '[a-zA-Z0-9_- \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|]+'
ChoiceMarkerClose <- ']'
ChoiceDescription <- ChoiceDescPart ( Newline QuoteMarker? TextLineMarker !ChoiceMarker ChoiceDescPart )*
ChoiceDescPart <- ( '[a-zA-Z0-9_ \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|]+' | '-' !'-' )+
ChoiceResponse <- ChoiceResponseSeparator ChoiceResponseDesc? ChoiceGoto?
ChoiceResponseSeparator <- '--'
ChoiceResponseDesc <-- ChoiceResponseDescPart ( Newline QuoteMarker? TextLineMarker !ChoiceMarker ChoiceReponseDescPart )*
ChoiceResponseDescPart <- ( '[a-zABCDEFHIJKLMNOPQRSTUVWXYZZ0-9_ \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|-]' | 'G' !'O TO' )+
ChoiceGoto <- GotoMarker LineWhitespace? Name EndPunctuation?
GotoMarker <- 'GO TO'
EndPunctuation <- '[.,:;!?]+'
Heading <- QuoteMarker? HeadingMarker LineWhitespace? Name HeadingMarker Newline
HeadingMarker <- '={2,}'
Name <- '[a-zA-Z0-9_-][a-zA-Z0-9_ -]*'
InstructionLine <- QuoteMarker? InstructionLineMarker LineText Newline
InstructionLineMarker <- '%[ \t]'
LineText <- '[a-zA-Z0-9_- \t`!"$%^&*()_+=[{]};:'@#~,<.>/?\|]+'
TextLine <- QuoteMarker? TextLineMarker LineText Newline
TextLineMarker <- ':[ \t]'
FeedbackLine <- QuoteMarker? LineText Newline
"""

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


class Document(object):

	_sections = None
	sections = property(lambda s: list(s._sections))
	
	def __init__(self,sections):
		self._sections = sections
		
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
		return Document(items)


class FirstSection(object):

	_content = None
	content = property(lambda s: s._content)

	def __init__(self,content):
		self._content = content
		
	def __repr__(self):
		return "FirstSection(%s)" % repr(self._content)
		
	@staticmethod
	def parse(input):
		input = input.branch()		
		cont = SectionContent.parse(input)
		if cont is None: return None		
		input.commit()
		return FirstSection(cont)
		
		
class Section(object):

	_heading = None
	heading = property(lambda s: s._heading)
	_content = None
	content = property(lambda s: s._content)
	
	def __init__(self,heading,content):
		self._heading = heading
		self._content = content
		
	def __repr__(self):
		return "Section(%s,%s)" % (repr(self._heading),repr(self._content))
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		head = Heading.parse(input)
		if head is None: return None
		
		cont = SectionContent.parse(input)
		if cont is None: return None
		
		input.commit()
		return Section(head,cont)
		
		
class SectionContent(object):
	
	_items = None
	items = property(lambda s: list(s._items))
	
	def __init__(self,items):
		self._items = items
		
	def __repr__(self):
		return "SectionContent(%s)" % repr(self._items)
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		if ZeroOrMore(BlankLine).parse(input) is None: return None
		
		items = OneOrMore(Alternatives(ChoiceBlock,InstructionBlock,
				TextBlock,FeedbackBlock)).parse(input)
		if items is None: return None
				
		input.commit()
		return SectionContent(items)
		
	
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
		return Heading(name)


class QuoteMarker(object):

	@staticmethod
	def parse(input):
		input = input.branch()
		if OneOrMore(Sequence(ZeroOrMore(Char(' \t')),
				Char('>'))).parse(input) is None: return None
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
	
	def __init__(self,choices):
		self._choices = choices
		
	def __repr__(self):
		return "ChoiceBlock(%s)" % repr(self._choices)
		
	@staticmethod
	def parse(input):
		input.branch()
		
		choices = OneOrMore(Choice).parse(input)
		if choices is None: return None
		
		if ZeroOrMore(BlankLine).parse(input) is None: return None
		
		input.commit()
		return ChoiceBlock(choices)
	
	
class InstructionBlock(object):
	
	_lines = None
	lines = property(lambda s: list(s._lines))
	
	def __init__(self,lines):
		self._lines = lines
		
	def __repr__(self):	
		return "InstructionBlock(%s)" % repr(self._lines)
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		lines = OneOrMore(InstructionLine).parse(input)
		if lines is None: return None
		
		if ZeroOrMore(BlankLine).parse(input) is None: return None
		
		input.commit()
		return InstructionBlock(lines)
		
	
class TextBlock(object):
	
	_lines = None
	lines = property(lambda s: list(s._lines))
	
	def __init__(self,lines):
		self._lines = lines
		
	def __repr__(self):
		return "TextBlock(%s)" % repr(self._lines)
	
	@staticmethod
	def parse(input):
		input = input.branch()
		
		lines = OneOrMore(TextLine).parse(input)
		if lines is None: return None
		
		if ZeroOrMore(BlankLine).parse(input) is None: return None
		
		input.commit()
		return TextBlock(lines)
	
	
class FeedbackBlock(object):
	
	_lines = None
	lines = property(lambda s: list(s._lines))
	
	def __init__(self,lines):
		self._lines = lines
		
	def __repr__(self):
		return "FeedbackBlock(%s)" % repr(self._lines)
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		lines = OneOrMore(Sequence(
			Not(Alternatives(InstructionLine,TextLine,Choice,Heading)),
			FeedbackLine)).parse(input)
		if lines is None: return None
		
		if ZeroOrMore(BlankLine).parse(input) is None: return None
		
		input.commit()
		return FeedbackBlock([l[1] for l in lines])


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
	
		text = LineText.parse(input)
		if text is None: return None

		if Newline.parse(input) is None: return None
		
		input.commit()	
		return TextLine(text)


class TextLineMarker(object):

	@staticmethod
	def parse(input):
		input = input.branch()
		if Char(":").parse(input) is None: return None
		if Char(" \t").parse(input) is None: return None
		input.commit()
		return TextLineMarker()


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
		return LineText("".join(i)+" ")


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
		
		text = LineText.parse(input)
		if text is None: return None
		
		if Newline.parse(input) is None: return None
		
		input.commit()
		return InstructionLine(text)


class InstructionLineMarker(object):

	@staticmethod
	def parse(input):
		input = input.branch()		
		if Char('%').parse(input) is None: return None
		if Char(' \t').parse(input) is None: return None		
		input.commit()
		return InstructionLineMarker()


class Choice(object):

	_marker = None
	marker = property(lambda s: s._marker)
	_description = None
	description = property(lambda s: s._description)
	_response = None
	response = property(lambda s: s._response)

	def __init__(self,marker,description,response):
		self._marker = marker
		self._description = description
		self._response = response
		
	def __repr__(self):
		return "Choice(%s,%s,%s)" % (repr(self._marker),
			repr(self._description),repr(self._response))
			
	@staticmethod
	def parse(input):
		input = input.branch()
		
		Optional(QuoteMarker).parse(input)

		if TextLineMarker.parse(input) is None: return None
		
		marker = ChoiceMarker.parse(input)
		if marker is None: return None
		
		desc = ChoiceDescription.parse(input)
		if desc is None: return None
		
		resp = Optional(ChoiceResponse).parse(input)
		if resp is None: return None
		
		if Newline.parse(input) is None: return None
		
		input.commit()
		return Choice(marker,desc,resp if resp is not False else Empty())
		

class Empty(object):
	"""A null object used to mark data which isn't present"""
	
	def __repr__(self):	
		return "Empty()"
	
		
class ChoiceMarker(object):
	
	_text = None
	text = property(lambda s: s._text)
	
	def __init__(self,text):
		self._text = text
		
	def __repr__(self):
		return "ChoiceMarker(%s)" % repr(self._text)
		
	@staticmethod
	def parse(input):
		input = input.branch()
				
		if ChoiceMarkerOpen.parse(input) is None: return None
		
		Optional(LineWhitespace).parse(input)
		
		text = Optional(ChoiceMarkerText).parse(input)
		if text is None: return None
		
		if ChoiceMarkerClose.parse(input) is None: return None
		
		input.commit()
		return ChoiceMarker(text if text is not False else Empty())
		

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
	
	
class ChoiceMarkerText(object):

	_text = None
	text = property(lambda s: s._text)

	def __init__(self,text):
		self._text = text
		
	def __repr__(self):
		return "ChoiceMarkerText(%s)" % self._text
		
	@staticmethod
	def parse(input):
		input = input.branch()

		i = OneOrMore(Char(ALL_CHARACTERS.replace("]",""))).parse(input)
		if i is None: return None			
		
		input.commit()
		return ChoiceMarkerText("".join(i).strip())
		
	
class ChoiceDescription(object):
	
	_parts = None
	parts = property(lambda s: list(s._parts))
	
	def __init__(self,parts):
		self._parts = parts
		
	def __repr__(self):	
		return "ChoiceDescription(%s)" % repr(self._parts)
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		parts = []
		p = ChoiceDescPart.parse(input)
		if p is None: return None
		parts.append(p)
		
		ps = ZeroOrMore(Sequence(Newline,Optional(QuoteMarker),
				TextLineMarker,Not(ChoiceMarker),ChoiceDescPart)).parse(input)
		if ps is None: return None
		parts.extend([p[4::5][0] for p in ps])
		
		input.commit()
		return ChoiceDescription(parts)
		
	
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
				[t[0] if isinstance(t,list) else t for t in text]))
		
	
class ChoiceResponse(object):
	
	_text = None
	text = property(lambda s: s._text)
	_goto = None
	goto = property(lambda s: s._goto)
	
	def __init__(self,text,goto):
		self._text = text
		self._goto = goto
	
	def __repr__(self):
		return "ChoiceResponse(%s,%s)" % (repr(self._text),repr(self._goto))
	
	@staticmethod
	def parse(input):
		input = input.branch()
		
		if ChoiceResponseSeparator.parse(input) is None: return None
		
		text = Optional(ChoiceResponseDesc).parse(input)
		if text is None: return None
						
		goto = Optional(ChoiceGoto).parse(input)
		if goto is None: return None
						
		input.commit()
		return ChoiceResponse(text if text is not False else Empty(),
			goto if goto is not False else Empty())
			

class ChoiceResponseSeparator(object):

	@staticmethod
	def parse(input):
		input = input.branch()
		if Char('-').parse(input) is None: return None
		if Char('-').parse(input) is None: return None
		input.commit()
		return ChoiceResponseSeparator()
				

class ChoiceResponseDesc(object):

	_parts = None
	parts = property(lambda s: list(s._parts))
	
	def __init__(self,parts):
		self._parts = parts
				
	def __repr__(self):
		return "ChoiceResponseDesc(%s)" % repr(self._parts)
				
	@staticmethod
	def parse(input):
		input = input.branch()
		
		parts = []
		p = ChoiceResponseDescPart.parse(input)
		if p is None: return None
		parts.append(p)
		
		ps = ZeroOrMore(Sequence(Newline,Optional(QuoteMarker),
				TextLineMarker,Not(ChoiceMarker),ChoiceResponseDescPart)).parse(input)
		if ps is None: return None
		parts.extend([p[4::5][0] for p in ps])
		
		input.commit()
		return ChoiceResponseDesc(parts)
				
		
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
				[t[0] if isinstance(t,list) else t for t in text]))
		
		
class ChoiceGoto(object):
		
	_name = None
	name = property(lambda s: s._name)
		
	def __init__(self,name):
		self._name = name
		
	def __repr__(self):
		return "ChoiceGoto(%s)" % repr(self._name)
		
	@staticmethod
	def parse(input):
		input = input.branch()
		
		if GotoMarker.parse(input) is None: return None
		
		Optional(LineWhitespace).parse(input)
		
		name = Name.parse(input)
		if name is None: return None
		
		Optional(EndPunctuation).parse(input)
		
		input.commit()
		return ChoiceGoto(name)
		
		
class GotoMarker(object):
	
	@staticmethod
	def parse(input):
		input = input.branch()
		if Sequence(Char('G'),Char('O'),Char(' '),
				Char('T'),Char('O')).parse(input) is None: return None
		input.commit()
		return GotoMarker()
	
	
class EndPunctuation(object):
	
	_CHARACTERS = ".,!?;"
	
	@staticmethod
	def parse(input):
		input = input.branch()
		if OneOrMore(Char(EndPunctuation._CHARACTERS)).parse(input) is None: return None
		input.commit()
		return EndPunctuation
		
		
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
		return FeedbackLine(text)
		

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


class HtmlOutput(object):
	
	def output(self,tree):
		# TODO doctype
		return "<html><body>%s</body></html>" % (
			"".join(map(self._visit,tree.sections)) )
		
	def _visit(self,node,**kargs):
		return getattr(self,"_do_%s" % type(node).__name__,
				self._do_default)(node,**kargs)
		
	def _do_FirstSection(self,node):
		return self._visit(node.content,secname="!first")
		
	def _do_Section(self,node):
		name = node.heading.name.text.lower()
		return self._visit(node.heading)+self._visit(node.content,secname=name)

	def _do_Heading(self,node):
		return "<h2>%s</h2>" % self._escape(node.name.text)
		
	def _do_SectionContent(self,node,secname):
		s = ""
		for i,item in enumerate(node.items):
			s += self._visit(item,blockid=secname+"_"+str(i))
		return s
	
	def _do_TextBlock(self,node,blockid):
		return "<p>%s</p>" % (
			"".join(map(self._visit,node.lines)) )	
	
	def _do_TextLine(self,node):
		return self._escape(node.text.text)
	
	def _do_InstructionBlock(self,node,blockid):
		# TODO: comments may not contain '--'
		return "<!-- %s -->" % (
			"".join(map(self._visit,node.lines)) )
		
	def _do_InstructionLine(self,node):
		return self._escape(node.text.text)
		
	def _do_FeedbackBlock(self,node,blockid):
		return '<p class="feedback">%s</p>' % (
			"".join(map(self._visit,node.lines)) )
		
	def _do_FeedbackLine(self,node):
		return self._escape(node.text.text)

	def _do_ChoiceBlock(self,node,blockid):
		s = ""
		for i,c in enumerate(node.choices):
			s += self._visit(c,setname=blockid,choiceid=blockid+"_"+str(i))
		return "<form>%s</form>" % s
		
	def _do_Choice(self,node,setname,choiceid):
		return ( ('<div><input id="%(choiceid)s" type="radio" name="%(setname)s" />'
				+'<label for="%(choiceid)s">%(description)s</label></div>')
				% { "choiceid":self._escape(choiceid), "setname":self._escape(setname),
					"description":self._escape(self._visit(node.description)) } )
		
	def _do_ChoiceDescription(self,node):
		return "".join(map(self._visit,node.parts))
		
	def _do_ChoiceDescPart(self,node):
		return node.text
		
	def _do_default(self,node,**kargs):
		return ""
		
	def _escape(self,text):
		return ( text.replace("&","&amp;")
				.replace("<","&lt;")
				.replace(">","&gt;")
				.replace('"',"&quot;") )
  	
	
s = """\
: Hi Alice,

%	Please put X in each box as appropriate and leave additional 
%	comments on separate lines (without a : at the start).  You 
%	can follow "GO TO <section>" instructions by searching for 
%	"== <section>" using ctl+f, for example.
    
: Who's in charge of setting up the file server?
    
: [X] Me		-- GO TO me.
: [] Frank	-- Tell him to pop in to have a chat with me when he's 
:  				in tomorrow. GO TO end.
: [] George	-- GO TO george 
: [] Other	-- Let me know whos's in charge of the damn file server. 
:  				GO TO end.

Here is some feedback
Put here as a test

== Me ==
    	
: Did you get it up and running yet?
    	
: [] Yes it's up and running	-- GO TO server running.
: [] No it's not ready yet	-- GO TO server not running.
    

== George ==

: Is he on holiday?
  	
: [] Yes	-- Please could you take over from him. GO TO end.
: [] No		-- Have him to contact me. GO TO end.
    

== Server Running ==
    
: Ok that's great! Thanks for getting that set up.
    	
: Is there a password?
   	
: [] Yes a password has been set	-- Leave it with Chris 
:										on Tuesday GO TO end.
: [] No, no password is set			-- Leave it like that and 
:										I will set one. GO TO end.
    
== Server Not Running ==
    	
: Is Dianne busy?
	
: [] Yes she's occupied	-- Hand over the file server job to Ed GO TO end.
: [] No she's not busy	-- Hand over the file server job to Dianne GO TO end.
    
: Are we still waiting on that hard disk from the supplier?
    	
: [] Yes, still waiting	-- Call them and ask what's taking so long. GO TO end.
: [] Not waiting		-- Let me know what the problem is. GO TO end.
    
    
== End ==
    
: Thanks,
: Bob.
"""

#import pdb
#pdb.set_trace()

#i = Input(s)
#d = Document.parse(i)
#if d is not None:
	#print d
#	print HtmlOutput().output(d)
#else:
#	p = i.get_deepest_pos()
#	print "Parse error near %s" % repr(s[p:p+100]+"...")

if __name__ == "__main__":
	import argparse
	
	ap = argparse.ArgumentParser(description="Parse decision tree documents")
	ap.parse_args()
