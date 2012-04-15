# TODO: Recipient may assume to read into next section 
#		when there isn't a goto in a section. Force author to 
#		have all paths lead to final section. Or else introduce
#		some kind of END HERE syntax for explicitly telling the 
#		user to stop reading (though an explicit end section is 
#		just as easy to author)
# TODO: Allow gotos at the end of sections.
# TODO: Fix up whitespace in combined snippets, particularly feedback
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
SectionContent <- ( BlankLine | !StarterLine FeedbackLine )* ( ChoiceBlock | InstructionBlock | TextBlock )+
BlankLine <- QuoteMarker? LineWhitespace? Newline
ChoiceBlock <- FirstChoice ( BlankLine | Choice | !StarterLine FeedbackLine )*
InstructionBlock <- FirstInstructionLine ( BlankLine | InstructionLine | !StarterLine FeedbackLine )*
TextBlock <- FirstTextLine ( BlankLine | TextLine | !StarterLine FeedbackLine )*
StarterLine <- FirstTextLine | FirstInstructionLine | Heading | FirstChoice
QuoteMarker <- '([ \t]*>)+[ \t]*'
LineWhitespace <- '[ \t]+'
Newline <- '(\r\n|\r|\n)'
Choice <- QuoteMarker? TextLineMarker LineWhitespace? ChoiceMarker ChoiceContent
FirstChoice <- QuoteMarker? FirstTextLineMarker LineWhitespace? ChoiceMarker ChoiceContent
ChoiceContent <- LineWhitespace? ChoiceDescription ChoiceResponse? Newline
ChoiceMarker <- ChoiceMarkerOpen LineWhitespace? ChoiceMarkerMark? ChoiceMarkerClose
ChoiceMarkerOpen <- '['
ChoiceMarkerMark <- '[a-zA-Z0-9_- \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|]+'
ChoiceMarkerClose <- ']'
ChoiceDescription <- ChoiceDescPart ( ChoiceDescNewline ChoiceDescPart )*
ChoiceDescNewline <- Newline ( BlankLine | !( StarterLine | TextLine ) FeedbackLine )* QuoteMarker? TextLineMarker LineWhitespace? !ChoiceMarker
ChoiceDescPart <- ( '[a-zA-Z0-9_ \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|]+' | '-' !'-' )+
ChoiceResponse <- ChoiceDescNewline? ChoiceResponseSeparator ( ChoiceDescNewline? ChoiceResponseDesc ChoiceGoto? | ChoiceGoto )
ChoiceResponseSeparator <- '--'
ChoiceResponseDesc <-- ChoiceResponseDescPart ( ChoiceDescNewline ChoiceReponseDescPart )*
ChoiceResponseDescPart <- ( '[a-zABCDEFHIJKLMNOPQRSTUVWXYZ0-9_ \t`!"$%^&*()_+=[{};:'@#~,<.>/?\|-]' | 'G' !'O TO' )+
ChoiceGoto <- ChoiceDescNewline? GotoMarker LineWhitespace? Name EndPunctuation?
GotoMarker <- 'GO TO'
EndPunctuation <- '[.,:;!?]+'
Heading <- QuoteMarker? HeadingMarker LineWhitespace? Name HeadingMarker Newline
HeadingMarker <- '={2,}'
Name <- '[a-zA-Z0-9_-][a-zA-Z0-9_ -]*'
InstructionLine <- QuoteMarker? InstructionLineMarker TextLineContent
InstructionLineMarker <- '%' !'%'
FirstInstructionLine <- QuoteMarker? FirstInstructionLineMarker TextLineContent
FirstInstructionLineMarker <- '%%'
LineText <- '[a-zA-Z0-9_- \t`!"$%^&*()_+=[{]};:'@#~,<.>/?\|]+'
TextLine <- QuoteMarker? TextLineMarker TextLineContent
TextLineMarker <- ':' !':'
FirstTextLine <- QuoteMarker? FirstTextLineMarker TextLineContent
FirstTextLineMarker <- '::'
TextLineContent <- LineWhitespace? LineText Newline
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


class ValidationError(Exception):
	pass


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
		doc = Document(items)
		
		Document._validate(doc)
		
		return doc
		
	@staticmethod
	def _walk_section(sec,endsec,walked,lastchance,sections):
		"""Walks the goto graph from this section. Returns True if section 
		paths valid or False if unknown. Raises ValidationError for invalid path."""
		
		sname = sec.heading.name if hasattr(sec,"heading") else "first"
		
		# TODO: this is wrong - looping back to a section on its 
		#       last chance isn't necessarily an error.
		# check if already walked
		if sec in walked:
			if sec in lastchance:
				# if it was this section's last chance to find a valid
				# path, the section is invalid
				raise ValidationError(('End of document cannot be reached '
					+'from section "%s"') % sname)
			else:
				# otherwise we're still waiting to find out if this 
				# section is valid
				return False
		
		# iterate over choice blocks
		found_valid = False
		found_any = False
		has_leads = False
		for b in sec.content.items:
			if isinstance(b,ChoiceBlock):
				fallthrough = False
				# iterate over choices
				for c in b.choices:
					found_any = True
					if c.goto is None: 
						# No goto means block falls through
						fallthrough = True
					else:
						# Recurse to target section
						newwalked = set(walked)
						newwalked.add(sec)
						newlchance = set(lastchance)
						# TODO: need to add self to newlchance
						# if last chance
						if( Document._walk_section(
								sections[c.goto],endsec,newwalked,
								newlchance,sections) ):
							found_valid = True
						else:
							has_leads = True
				# if block doesnt fall through, stop
				if not fallthrough:
					# End section *must* fall through
					if sec is endsec:
						raise ValidationError(('End section "%s" has no '
							+'choices that reach end of document') % sname)
					break
		else:
			# Fell through last block
			# Only the end section may fall through
			if sec is not endsec:
				if not found_any:
					raise ValidationError(('Section "%s" has no choices '
						+'and so never reaches end of document') % sname)
				else:
					raise ValidationError(('Section "%s" has one or more '
						+'choices that reach end of section and so never '
						+'reach end of document') % sname)
			else:
				# end section fell through, so mission accomplished
				return True
		
		# TODO: this is wrong
		# if section has no decidedly valid paths, return invalid
		if not found_valid:
			raise ValidationError(('Section "%s" has no choices that reach end of '
				+'document') % sname)
		
		return True	
		
		
	@staticmethod
	def _validate(doc):
	
		# Collect sections into map, checking for duplicates		
		sectionmap = {}
		for s in doc.sections[1:]:
			n = s.heading.name
			if n in sectionmap:
				raise ValidationError("Duplicate section name '%s'" % n)
			sectionmap[n] = s

		# Iterate over goto references, checking sections exist			
		for s in doc.sections:
			for b in s.content.items:
				if isinstance(b,ChoiceBlock):
					for c in b.choices:
						if c.goto is not None:
							n = c.goto
							if n not in sectionmap:
								raise ValidationError("Goto references unknown section '%s'" % n)
								
		# walk all goto paths
		Document._walk_section(doc.sections[0],doc.sections[-1], set([]),sectionmap)
		

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
			flines.append(i.feedback)
		if len(items)==0: return None
				
		last = None
		for i in items:
			if isinstance(i,ChoiceBlock) and isinstance(last,ChoiceBlock):
				raise ValidationError("Consecutive choice blocks are not allowed")
			last = i
				
		input.commit()
		return SectionContent(items," ".join(flines))
		
	
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
	
	def __init__(self,choices,feedback):
		self._choices = choices
		self._feedback = feedback
		
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
		return ChoiceBlock(choices," ".join(flines))
	
	
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
				tlines.append(l.text)
			elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
				flines.append(l[1].text)
				
		input.commit()
		return InstructionBlock(" ".join(tlines)," ".join(flines))
		
	
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
				tlines.append(l.text)
			elif isinstance(l,list) and isinstance(l[1],FeedbackLine):
				flines.append(l[1].text)
					
		input.commit()
		return TextBlock(" ".join(tlines)," ".join(flines))
	
	
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
		parts.append(p.text)
		
		ps = ZeroOrMore(Sequence(
			ChoiceDescNewline,ChoiceDescPart)).parse(input)
		if ps is None: return None
		parts.extend([p[1].text for p in ps])
		flines.extend([p[0].feedback for p in ps])
		
		input.commit()
		return ChoiceDescription(" ".join(parts)," ".join(flines))


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
		return ChoiceDescNewline(" ".join(flines))		
	
	
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
			desc.text if desc is not False else None,
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
		flines.extend([p[0].feedback for p in ps])
		
		input.commit()
		return ChoiceResponseDesc(" ".join(parts)," ".join(flines))
				
		
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

# <Choice> ::= <QuoteMarker>? <FirstTextLineMarker> <LineWhitespace>?
#				<ChoiceMarker> <LineWhitespace>? 

s = """\
::	blah
:	yadda
floogle
::	[]	opt a
alpha
:			--
beta
:				test test
gamma
:			GO TO foo
delta
:	[]	opt b
epsilon
:			--
t'other one
:				123 123
omega
:			GO TO foo
blah
== foo ==

::	yadda
:	blarg
"""

if __name__ == "__main__":

	#import pdb
	#pdb.set_trace()
	
	i = Input(s)
	try:
		d = Document.parse(i)
		if d is not None:
			print d
			#print HtmlOutput().output(d)
		else:
			p = i.get_deepest_pos()
			print "Parse error near %s" % repr(s[p:p+100]+"...")
			
	except ValidationError as e:
		print "Validation error: %s" % str(e)
	
#	import argparse
#	
#	ap = argparse.ArgumentParser(description="Parse decision tree documents")
#	ap.parse_args()
