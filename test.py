#!/usr/bin/python2

import sys
import mock
import unittest
import dectree as dt

# monkey patching
if sys.version_info < (2,7):

	def assertIsNone(self,val):
		self.assertTrue( val is None )
	unittest.TestCase.assertIsNone = assertIsNone
	
	def assertIsNotNone(self,val):
		self.assertTrue( val is not None )
	unittest.TestCase.assertIsNotNone = assertIsNotNone
	
	class RaiseChecker(object):
		def __init__(self,testcase,expected):
			self.testcase = testcase
			self.expected = expected
		def __enter__(self):
			pass
		def __exit__(self,exctype,excval,exctb):
			self.testcase.assertEquals(self.expected,exctype)
			return True
	def assertRaises(self,*args):
		if len(args)==1:
			return RaiseChecker(self,args[0])
		else:
			self._assertRaises(*args)
	unittest.TestCase._assertRaises = unittest.TestCase.assertRaises
	unittest.TestCase.assertRaises = assertRaises


def mock_globals(where,*names):
	def dec(fn):
		def newfn(*args,**kargs):
			globmap = {}
			try:
				# store globals in map, replace with mocks
				for g in names:
					globmap[g] = getattr(where,g)
					setattr(where,g,mock.Mock())
				return fn(*args,**kargs)
			finally:
				# restore globals
				for g in names:
					setattr(where,g,globmap.get(g,getattr(where,g)))
		return newfn
	return dec


class TestInput(unittest.TestCase):
	
	def test_can_construct(self):
		dt.Input("foobar")
		
	def test_can_iterate(self):
		i = dt.Input("abc")
		self.assertEquals("a",i.next())
		self.assertEquals("b",i.next())
		self.assertEquals("c",i.next())

	def test_can_branch(self):
		i = dt.Input("abcdef")
		i.next()
		j = i.branch()
		self.assertEquals("b", i.next())
		self.assertEquals("b", j.next())
		self.assertEquals("c", j.next())
		self.assertEquals("c", i.next())
		
	def test_can_commit(self):
		i = dt.Input("abcdef")
		j = i.branch()
		j.next()
		j.next()
		j.commit()
		self.assertEquals("c",i.next())
		
	def test_get_deepest_pos(self):
		i = dt.Input("abcdef")
		i.next()
		j = i.branch()
		j.next()
		k = j.branch()
		k.next()
		self.assertEquals(3, i.get_deepest_pos())


class MockInput(object):

	pos = 0
	parent = None
	data = None
	
	def __init__(self,data,pos=0,parent=None):
		self.data = data
		self.pos = pos
		self.parent = parent
	
	def next(self):
		s = self.data[self.pos]
		self.pos += 1
		return s
	
	def branch(self):
		return MockInput(self.data,self.pos,self)
		
	def commit(self):
		if self.parent:
			self.parent.pos = self.pos


def make_parse(vals):
	def parse(input):
		n = input.data[input.pos]
		v = vals.get(n,None)
		if v is not None:
			input.next()
		return v
	return parse

	
class TestDocument(unittest.TestCase):

	def test_construct(self):
		dt.Document([object(),object()])
		
	def test_sections_readable(self):
		d = dt.Document(["foo"])
		self.assertEquals("foo", d.sections[0])
		
	def test_sections_attribute_readonly(self):
		d = dt.Document(["foo","bar"])
		with self.assertRaises(AttributeError):
			d.sections = ["weh"]
			
	def test_sections_attribute_immutable(self):
		d = dt.Document(["foo","bar"])
		d.sections[0] = "weh"
		self.assertEquals("foo",d.sections[0])

	@mock_globals(dt,"FirstSection","Section")
	def test_parse_returns_populated_document(self):
		s1 = object()
		s2 = object()
		dt.FirstSection.parse.side_effect = make_parse({"f":s1})
		dt.Section.parse.side_effect = make_parse({"s":s2})
		result = dt.Document.parse(MockInput("fs\x00",0,None))
		self.assertTrue( isinstance(result,dt.Document) )
		self.assertTrue( hasattr(result,"sections") )
		self.assertEquals( [s1,s2], list(result.sections) )

	@mock_globals(dt,"FirstSection","Section")
	def test_parse_expects_firstsection(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		self.assertIsNone( dt.Document.parse(MockInput("s\x00",0,None)) )
		self.assertFalse( dt.Section.parse.called )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_allows_zero_sections(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		dt.Section.parse.side_effect = make_parse({"s":object()})
		self.assertIsNotNone( dt.Document.parse(MockInput("f\x00",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_allows_multiple_sections(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		dt.Section.parse.side_effect = make_parse({"s":object()})
		self.assertIsNotNone( dt.Document.parse(MockInput("fsss\x00",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_expects_char_0(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		dt.Section.parse.side_effect = make_parse({"s":object()})
		self.assertIsNone( dt.Document.parse(MockInput("fq",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_consumes_input_on_success(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		dt.Section.parse.side_effect = make_parse({"s":object()})
		i = MockInput("fs\x00",0,None)
		dt.Document.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":object()})
		dt.Section.parse.side_effect = make_parse({"s":object()})
		i = MockInput("fsq",0,None)
		dt.Document.parse(i)
		self.assertEquals(0, i.pos)
	
		
class TestFirstSection(unittest.TestCase):

	def test_construct(self):
		dt.FirstSection(object())
		
	def test_content_readable(self):
		f = dt.FirstSection("foo")
		self.assertEquals("foo", f.content)
		
	def test_content_attribute_readonly(self):
		f = dt.FirstSection("foo")
		with self.assertRaises(AttributeError):
			f.content = "bar"
			
	@mock_globals(dt,"SectionContent")
	def test_parse_returns_populated_firstsection(self):	
		c = object()
		dt.SectionContent.parse.side_effect = make_parse({"c":c})
		result = dt.FirstSection.parse(MockInput("c",0,None))
		self.assertTrue( isinstance(result,dt.FirstSection) )
		self.assertTrue( hasattr(result,"content") )
		self.assertEquals( c, result.content )
		
	@mock_globals(dt,"SectionContent")
	def test_parse_expects_sectioncontent(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.FirstSection.parse(MockInput("q",0,None)) )
		
	@mock_globals(dt,"SectionContent")
	def test_parse_consumes_input_on_success(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		input = MockInput("c",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(1, input.pos)

	@mock_globals(dt,"SectionContent")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		input = MockInput("q",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(0, input.pos)
		

class TestSection(unittest.TestCase):
	
	def test_construct(self):
		dt.Section(object(),object())
		
	def test_heading_readable(self):
		s = dt.Section("foo","bar")
		self.assertEquals("foo", s.heading)
		
	def test_heading_attribute_readonly(self):
		s = dt.Section("foo","bar")
		with self.assertRaises(AttributeError):
			s.heading = "weh"
			
	def test_content_readable(self):
		s = dt.Section("foo","bar")
		self.assertEquals("bar", s.content)
		
	def test_content_attribute_readonly(self):
		s = dt.Section("foo","bar")
		with self.assertRaises(AttributeError):
			s.content = "weh"
		
	@mock_globals(dt,"Heading","SectionContent")	
	def test_parse_returns_populated_section(self):
		h = object()
		dt.Heading.parse.side_effect = make_parse({"h":h})
		c = object()
		dt.SectionContent.parse.side_effect = make_parse({"c":c})
		result = dt.Section.parse(MockInput("hc",0,None))
		self.assertTrue( isinstance(result,dt.Section) )
		self.assertTrue( hasattr(result,"heading") )
		self.assertEquals(h, result.heading)
		self.assertTrue( hasattr(result,"content") )
		self.assertEquals(c, result.content)
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_expects_heading(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		self.assertIsNone( dt.Section.parse(MockInput("c",0,None)) )
		self.assertFalse( dt.SectionContent.parse.called )
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_expects_sectioncontent(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.Section.parse(MockInput("hq",0,None)) )
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_consumes_input_on_success(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		i = MockInput("hc",0,None)
		dt.Section.parse(i)
		self.assertEquals(2, i.pos)
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		i = MockInput("hq",0,None)
		dt.Section.parse(i)
		self.assertEquals(0, i.pos)
		
		
class TestHeading(unittest.TestCase):

	def test_construct(self):
		dt.Heading("foo")
		
	def test_name_readable(self):
		h = dt.Heading("foo")
		self.assertEquals("foo", h.name)
		
	def test_name_attribute_readonly(self):
		h = dt.Heading("foo")
		with self.assertRaises(AttributeError):
			h.name = "bar"
			
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_returns_populated_heading(self):
		n = object()
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":n})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.Heading.parse(MockInput("qhwnhl",0,None))
		self.assertTrue( isinstance(result,dt.Heading) )
		self.assertTrue( hasattr(result,"name") )
		self.assertEquals(n, result.name)
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("hwnhl",0,None)) )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_first_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qwnhl",0,None)) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertEquals( 1, dt.HeadingMarker.parse.call_count )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_allows_no_linewhitespace(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("qhnhl",0,None)) )

	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_name(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwhl",0,None)) )
		self.assertEquals(1, dt.HeadingMarker.parse.call_count)
		self.assertFalse( dt.Newline.parse.called )		

	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_secton_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnl",0,None)) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhz",0,None)) )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qhwnhl",0,None)
		dt.Heading.parse(i)
		self.assertEquals(6, i.pos)
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qhwnhz",0,None)
		dt.Heading.parse(i)
		self.assertEquals(0, i.pos)
	

class TestQuoteMarker(unittest.TestCase):
	
	def test_construct(self):
		dt.QuoteMarker()
		
	def test_parse_returns_quotemarker(self):
		result = dt.QuoteMarker.parse(MockInput(" \t>x",0,None))
		self.assertTrue( isinstance(result,dt.QuoteMarker) )
		
	def test_parse_allows_no_whitespace(self):
		self.assertIsNotNone( dt.QuoteMarker.parse(MockInput(">x",0,None)) )
		
	def test_parse_expects_angle_bracket(self):
		self.assertIsNone( dt.QuoteMarker.parse(MockInput("x",0,None)) )
		
	def test_parse_allows_multiple_markers(self):
		self.assertIsNotNone( dt.QuoteMarker.parse(MockInput(" > > >x",0,None)) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("\t>x",0,None)
		dt.QuoteMarker.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("\t\t\tx",0,None)
		dt.QuoteMarker.parse(i)
		self.assertEquals(0, i.pos)


class TestHeadingMarker(unittest.TestCase):
	
	def test_construct(self):
		dt.HeadingMarker()
		
	def test_parse_returns_headingmarker(self):
		result = dt.HeadingMarker.parse(MockInput("==x",0,None))	
		self.assertTrue( isinstance(result,dt.HeadingMarker) )
		
	def test_parse_expects_first_equals(self):
		self.assertIsNone( dt.HeadingMarker.parse(MockInput("zx",0,None)) )
		
	def test_parse_expects_second_equals(self):
		self.assertIsNone( dt.HeadingMarker.parse(MockInput("=qx",0,None)) )
		
	def test_parse_allows_more_than_two_equals(self):
		i = MockInput("=====x",0,None)
		self.assertIsNotNone( dt.HeadingMarker.parse(i) )
		self.assertEquals(5, i.pos)
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("==x",0,None)
		dt.HeadingMarker.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("=x",0,None)
		dt.HeadingMarker.parse(i)
		self.assertEquals(0, i.pos)
		
		
class TestLineWhitespace(unittest.TestCase):

	def test_construct(self):
		dt.LineWhitespace()
		
	def test_parse_returns_linewhitespace(self):
		result = dt.LineWhitespace.parse(MockInput(" x",0,None))
		self.assertTrue( isinstance(result,dt.LineWhitespace) )
		
	def test_parse_expects_space_or_tab(self):
		self.assertIsNone( dt.LineWhitespace.parse(MockInput("qx",0,None)) )
		
	def test_parse_accepts_tab(self):
		self.assertIsNotNone( dt.LineWhitespace.parse(MockInput("\tx",0,None)) )
		
	def test_parse_accepts_multiple_spaces_and_tabs(self):
		i = MockInput("  \t\t \tx",0,None)
		self.assertIsNotNone( dt.LineWhitespace.parse(i) )
		self.assertEquals(6, i.pos)
		  	
	def test_parse_consumes_input_on_success(self):
		i = MockInput("\t\tx",0,None)
		dt.LineWhitespace.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("qx",0,None)
		dt.LineWhitespace.parse(i)
		self.assertEquals(0, i.pos)
		
		
class TestName(unittest.TestCase):

	def test_construct(self):
		dt.Name("foo")
		
	def test_text_readable(self):
		n = dt.Name("foo")
		self.assertEquals("foo",n.text)
		
	def test_text_not_writable(self):
		n = dt.Name("foo")
		with self.assertRaises(AttributeError):
			n.text = "bar"
			
	def test_parse_returns_populated_name(self):
		result = dt.Name.parse(MockInput("foo^",0,None))
		self.assertTrue( isinstance(result,dt.Name) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo", result.text)
		
	def test_parse_expects_word_char(self):
		self.assertIsNone( dt.Name.parse(MockInput(",^",0,None)) )
		
	def test_parse_allows_uppercase(self):
		self.assertIsNotNone( dt.Name.parse(MockInput("A^",0,None)) )
		
	def test_parse_allows_number(self):
		self.assertIsNotNone( dt.Name.parse(MockInput("9^",0,None)) )	
	
	def test_parse_allows_underscore(self):
		self.assertIsNotNone( dt.Name.parse(MockInput("_^",0,None)) )
		
	def test_parse_allows_hyphen(self):
		self.assertIsNotNone( dt.Name.parse(MockInput("-^",0,None)) )
		  	
	def test_parse_allows_multiple_characters(self):
		i = MockInput("abcXY-Z123^",0,None)
		self.assertIsNotNone( dt.Name.parse(i) )
		self.assertEquals(10, i.pos)
		  	
	def test_parse_allows_spaces(self):
		i = MockInput("foo bar^",0,None)
		self.assertIsNotNone( dt.Name.parse(i) )
		self.assertEquals(7, i.pos)
		  	
	def test_parse_doesnt_allow_leading_space(self):
		self.assertIsNone( dt.Name.parse(MockInput("   foo^",0,None)) )
		  	
	def test_parse_consumes_input_on_success(self):
		i = MockInput("HowNowBrownCow^",0,None)
		dt.Name.parse(i)
		self.assertEquals(14, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput(",^",0,None)
		dt.Name.parse(i)
		self.assertEquals(0, i.pos)
		  	
		  	
class TestNewline(unittest.TestCase):

	def test_construct(self):
		dt.Newline()
		
	def test_parse_returns_newline(self):
		result = dt.Newline.parse(MockInput("\n^",0,None))
		self.assertTrue( isinstance(result,dt.Newline) )
		  	
	def test_parse_expects_newline(self):
		self.assertIsNone( dt.Newline.parse(MockInput(",^",0,None)) )
		
	def test_parse_accepts_carriage_return(self):
		self.assertIsNotNone( dt.Newline.parse(MockInput("\r^",0,None)) )
		
	def test_parse_accepts_cr_nl(self):
		i = MockInput("\r\n^",0,None)
		self.assertIsNotNone( dt.Newline.parse(i) )
		self.assertEquals(2, i.pos)
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("\n^",0,None)
		dt.Newline.parse(i)
		self.assertEquals(1, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("\t^",0,None)
		dt.Newline.parse(i)
		self.assertEquals(0, i.pos)


class TestSectionContent(unittest.TestCase):

	def test_construct(self):
		dt.SectionContent(["foo","bar"])
		
	def test_items_readable(self):
		c = dt.SectionContent(["foo","bar"])
		self.assertEquals("foo", c.items[0])
		
	def test_items_not_writable(self):
		c = dt.SectionContent(["foo","bar"])
		with self.assertRaises(AttributeError):
			c.items = ["weh"]
			
	def test_items_immutable(self):
		c = dt.SectionContent(["foo","bar"])
		c.items[0] = "weh"
		self.assertEquals("foo", c.items[0])
		  	
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")
	def test_parse_returns_populated_sectioncontent(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		c = object()
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":c})
		i = object()
		dt.InstructionBlock.parse.side_effect = make_parse({"i":i})
		t = object()
		dt.TextBlock.parse.side_effect = make_parse({"t":t})
		f = object()
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":f})
		result = dt.SectionContent.parse(MockInput("bcitf$"))
		self.assertTrue( isinstance(result,dt.SectionContent) )
		self.assertTrue( hasattr(result,"items") )
		self.assertEquals([c,i,t,f], result.items)

	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_allows_no_blank_line(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("citf$")) )
		
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_allows_multiple_blank_lines(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("bbbcitf$")) )
		  	
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_expects_block(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNone( dt.SectionContent.parse(MockInput("bbb$")) )
		
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_allows_many_mixed_blocks(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("btiicfttccfi$")) )
		
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_consumes_input_on_success(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		i = MockInput("bcitf$")
		dt.SectionContent.parse(i)
		self.assertEquals(5, i.pos)
		
	@mock_globals(dt,"BlankLine","ChoiceBlock","InstructionBlock","TextBlock","FeedbackBlock")	
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		i = MockInput("bbbbbb$")
		dt.SectionContent.parse(i)
		self.assertEquals(0, i.pos)
		
		
class TestBlankLine(unittest.TestCase):

	def test_construct(self):
		dt.BlankLine()

	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_returns_blankline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.BlankLine.parse(MockInput("qwl"))
		self.assertTrue( isinstance(result,dt.BlankLine) )
		
	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.BlankLine.parse(MockInput("wl")) )
		  	
	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_allows_no_linewhitespace(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.BlankLine.parse(MockInput("ql")) )
			
	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.BlankLine.parse(MockInput("qwz")) )
	
	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qwl")
		dt.BlankLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"QuoteMarker","LineWhitespace","Newline")	
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qwz")
		dt.BlankLine.parse(i)
		self.assertEquals(0, i.pos)
	
	
class TestChoiceBlock(unittest.TestCase):
	
	def test_construct(self):
		dt.ChoiceBlock(["foo","bar"])
		
	def test_choices_readable(self):
		c = dt.ChoiceBlock(["foo","bar"])
		self.assertEquals("foo", c.choices[0])
		
	def test_choices_not_writable(self):
		c = dt.ChoiceBlock(["foo","bar"])
		with self.assertRaises(AttributeError):
			c.choices = ["weh"]
			
	def test_choices_immutable(self):
		c = dt.ChoiceBlock(["foo","bar"])
		c.choices[0] = "blah"
		self.assertEquals("foo",c.choices[0])
		
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_returns_populated_choiceblock(self):
		c1 = object()
		c2 = object()
		dt.Choice.parse.side_effect = make_parse({"c":c1,"C":c2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.ChoiceBlock.parse(MockInput("cCb$"))
		self.assertTrue( isinstance(result,dt.ChoiceBlock) )
		self.assertTrue( hasattr(result,"choices") )
		self.assertEquals( [c1,c2], result.choices )
		
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_expects_choice(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.ChoiceBlock.parse(MockInput("b$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		  	
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_allows_multiple_choices(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("cccb$")) )
		  	
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_allows_no_blanklines(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("c$")) )
		  	
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_allows_multiple_blank_lines(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("cbbb$")) )
		  	
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_consumes_input_on_success(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("ccb$")
		dt.ChoiceBlock.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"Choice","BlankLine")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("bbb$")
		dt.ChoiceBlock.parse(i)
		self.assertEquals(0, i.pos)
		  	
		  	
class TestChoice(unittest.TestCase):

	def test_construct(self):
		dt.Choice("alpha","beta","gamma")
		
	def test_marker_readable(self):
		c = dt.Choice("alpha","beta","gamma")
		self.assertEquals("alpha",c.marker)
		
	def test_marker_not_writable(self):
		c = dt.Choice("alpha","beta","gamma")
		with self.assertRaises(AttributeError):
			c.marker = "blah"
			
	def test_description_readable(self):
		c = dt.Choice("alpha","beta","gamma")
		self.assertEquals("beta",c.description)
		
	def test_description_no_writable(self):
		c = dt.Choice("alpha","beta","gamma")
		with self.assertRaises(AttributeError):
			c.description = "blah"
			
	def test_response_readable(self):
		c = dt.Choice("alpha","beta","gamma")
		self.assertEquals("gamma",c.response)
		
	def test_response_not_writable(self):
		c = dt.Choice("alpha","beta","gamma")
		with self.assertRaises(AttributeError):
			c.response = "blah"
			
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_returns_populated_choice(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		c = object()
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":c})
		d = object()
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":d})
		r = object()
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":r})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.Choice.parse(MockInput("qtcdrl"))
		self.assertTrue( isinstance(result,dt.Choice) )
		self.assertTrue( hasattr(result,"marker") )
		self.assertEquals( c, result.marker )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals( d, result.description )
		self.assertTrue( hasattr(result,"response") )
		self.assertEquals( r, result.response )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("tcdrl")) )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_expects_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qcdrl")) )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		self.assertFalse( dt.ChoiceDescription.parse.called )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_expects_choicemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtdrl")) )
		self.assertFalse( dt.ChoiceDescription.parse.called )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_expects_choice_description(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtcrl")) )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_allows_no_choiceresponse(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("qtcdl")) )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtcdr$")) )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtcdrl")
		dt.Choice.parse(i)
		self.assertEquals(6,i.pos)
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","ChoiceMarker",
		"ChoiceDescription","ChoiceResponse", "Newline")
	def test_parse_consumes_no_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtcdr$")
		dt.Choice.parse(i)
		self.assertEquals(0,i.pos)


class TestTextLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.TextLineMarker()
		
	def test_parse_returns_textlinemarker(self):
		result = dt.TextLineMarker.parse(MockInput(": $"))
		self.assertTrue( isinstance(result,dt.TextLineMarker) )
		
	def test_parse_expects_color(self):
		self.assertIsNone( dt.TextLineMarker.parse(MockInput(" $")) )
		
	def test_parse_expects_space(self):
		self.assertIsNone( dt.TextLineMarker.parse(MockInput(":$")) )
		
	def test_parse_accepts_tab(self):
		self.assertIsNotNone( dt.TextLineMarker.parse(MockInput(":\t$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput(": $")
		dt.TextLineMarker.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput(":$")
		dt.TextLineMarker.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceMarker(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceMarker("foo")
		
	def test_text_is_readable(self):
		m = dt.ChoiceMarker("foo")
		self.assertEquals("foo",m.text)
		
	def test_text_is_not_writable(self):
		m = dt.ChoiceMarker("foo")
		with self.assertRaises(AttributeError):
			m.text = "bar"
			
	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_returns_populated_choicemarker(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		t = object()
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":t})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceMarker.parse(MockInput("owtc"))
		self.assertTrue( isinstance(result,dt.ChoiceMarker) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( t, result.text )
		
	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_expects_choicemarkeropen(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("wtc")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarkerText.parse.called )
		self.assertFalse( dt.ChoiceMarkerClose.parse.called )
		
	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_allows_no_linewhitespace(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("otc")) )

	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_allows_no_choicemarkertext(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("owc")) )

	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_expects_choicemarkerclose(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("owt$")) )

	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		i = MockInput("owtc")
		dt.ChoiceMarker.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_globals(dt,"ChoiceMarkerOpen","LineWhitespace","ChoiceMarkerText","ChoiceMarkerClose")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		i = MockInput("owtz")
		dt.ChoiceMarker.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceMarkerOpen(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceMarkerOpen()
		
	def test_parse_returns_choicemarkeropen(self):
		result = dt.ChoiceMarkerOpen.parse(MockInput("[$"))
		self.assertTrue( isinstance(result,dt.ChoiceMarkerOpen) )

	def test_parse_expects_left_square(self):
		self.assertIsNone( dt.ChoiceMarkerOpen.parse(MockInput("$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("[$")
		dt.ChoiceMarkerOpen.parse(i)
		self.assertEquals(1, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("$")
		dt.ChoiceMarkerOpen.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceMarkerText(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceMarkerText("foo")
		
	def test_text_is_readable(self):
		c = dt.ChoiceMarkerText("foo")
		self.assertEquals("foo", c.text)
		
	def test_text_is_not_writable(self):
		c = dt.ChoiceMarkerText("foo")
		with self.assertRaises(AttributeError):
			c.text = "bar"
			
	def test_parse_returns_populated_choicemarkertext(self):
		result = dt.ChoiceMarkerText.parse(MockInput("foo]"))
		self.assertTrue( isinstance(result,dt.ChoiceMarkerText) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo", result.text)
		
	def test_parse_expects_non_right_square(self):
		self.assertIsNone( dt.ChoiceMarkerText.parse(MockInput("]$")) )
		
	def test_parse_allows_multiple_non_right_square(self):
		self.assertIsNotNone( dt.ChoiceMarkerText.parse(MockInput("a1%*>;@?]$")) )
		
	def text_parse_consumes_input_on_success(self):
		i = MockInput("foobar]$")
		dt.ChoiceMarkerText.parse(i)
		self.assertEquals(6, i.pos)
		
	def text_parse_doesnt_consume_input_on_success(self):
		i = MockInput("]$")
		dt.ChoicemarkerText.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceMarkerClose(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceMarkerClose()
		
	def test_parse_returns_choicemarkerclose(self):
		result = dt.ChoiceMarkerClose.parse(MockInput("]"))
		self.assertTrue( isinstance(result,dt.ChoiceMarkerClose) )
	
	def test_parse_expects_right_square(self):
		self.assertIsNone( dt.ChoiceMarkerClose.parse(MockInput("$")) )
	
	def test_parse_consumes_input_on_success(self):
		i = MockInput("]$")
		dt.ChoiceMarkerClose.parse(i)
		self.assertEquals(1, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("$")
		dt.ChoiceMarkerClose.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceDescription(unittest.TestCase):
	
	def test_construct(self):
		dt.ChoiceDescription(["foo","bar"])
		
	def test_parts_readable(self):
		d = dt.ChoiceDescription(["foo","bar"])
		self.assertEquals("foo",d.parts[0])
	
	def test_parts_not_writable(self):
		d = dt.ChoiceDescription(["foo","bar"])
		with self.assertRaises(AttributeError):
			d.parts = ["weh"]

	def test_parts_immutable(self):
		d = dt.ChoiceDescription(["foo","bar"])
		d.parts[0] = "weh"
		self.assertEquals("foo",d.parts[0])

	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_returns_populated_choicedescription(self):
		p1 = object()
		p2 = object()
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":p1,"d":p2})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("plqtd$"))
		self.assertTrue( isinstance(result,dt.ChoiceDescription) )
		self.assertTrue( hasattr(result,"parts") )
		self.assertEquals([p1,p2], result.parts)
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_expects_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceDescription.parse(MockInput("z$")) )
		self.assertFalse( dt.Newline.parse.called )
		self.assertFalse( dt.QuoteMarker.parse.called )
		self.assertFalse( dt.TextLineMarker.parse.called )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_allows_single_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceDescription.parse(MockInput("p$")) )
		self.assertFalse( dt.QuoteMarker.parse.called )
		self.assertFalse( dt.TextLineMarker.parse.called )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_allows_no_quote_marker_for_second_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("pltp$"))
		self.assertEquals(2, len(result.parts))

	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_expects_textlinemarker_for_second_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("plqp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))

	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_expects_no_choicemarker_for_second_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("plqtcp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))

	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_expects_part_for_second_part(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("plqt$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_allows_multiple_parts(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescription.parse(MockInput("plqtplqtplqtp$"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.parts))
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_consumes_input_on_success(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("plqtp$")
		dt.ChoiceDescription.parse(i)
		self.assertEquals(5, i.pos)
		
	@mock_globals(dt,"ChoiceDescPart","Newline","QuoteMarker",
		"TextLineMarker","ChoiceMarker")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("$")
		dt.ChoiceDescription.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceDescPart(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceDescPart("foo")
		
	def test_text_readable(self):
		p = dt.ChoiceDescPart("foo")
		self.assertEquals("foo", p.text)
		
	def test_text_not_writable(self):
		p = dt.ChoiceDescPart("foo")
		with self.assertRaises(AttributeError):
			p.text = "bar"
				
	def test_parse_returns_populated_choicedescpart(self):
		result = dt.ChoiceDescPart.parse(MockInput("foobar\x00"))
		self.assertTrue( isinstance(result,dt.ChoiceDescPart) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foobar", result.text)
	
	def test_parse_allows_single_hyphen(self):
		self.assertIsNotNone( dt.ChoiceDescPart.parse(MockInput("-\x00")) )
		
	def test_parse_doesnt_allow_double_hyphen(self):
		self.assertIsNone( dt.ChoiceDescPart.parse(MockInput("--\x00")) )
		
	def test_parse_allows_multiple_chars_numbers_and_punctuation(self):
		result = dt.ChoiceDescPart.parse(MockInput("a0b!7c%\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(7, len(result.text) )
		
	def test_parse_allows_spaces_and_tabs(self):
		result = dt.ChoiceDescPart.parse(MockInput(" \t \t\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.text) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("abc\x00")
		dt.ChoiceDescPart.parse(i)
		self.assertEquals(3, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("--\x00")
		dt.ChoiceDescPart.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceResponse(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceResponse("foo","bar")
	
	def test_description_readable(self):
		r = dt.ChoiceResponse("foo","bar")
		self.assertEquals("foo", r.description)
		
	def test_description_not_writable(self):
		r = dt.ChoiceResponse("foo","bar")
		with self.assertRaises(AttributeError):
			r.description = "weh"
			
	def test_goto_readable(self):
		r = dt.ChoiceResponse("foo","bar")
		self.assertEquals("bar",r.goto)
		
	def test_goto_not_writable(self):
		r = dt.ChoiceResponse("foo","bar")
		with self.assertRaises(AttributeError):
			r.goto = "weh"
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_returns_populated_choiceresponse(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		d = object()	
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":d})
		g = object()
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":g})
		result = dt.ChoiceResponse.parse(MockInput("sdg$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponse) )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals(d, result.description)
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals(g, result.goto)
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_expects_choiceresponseseparator(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNone( dt.ChoiceResponse.parse(MockInput("$")) )
		self.assertFalse( dt.ChoiceResponseDesc.parse.called )
		self.assertFalse( dt.ChoiceGoto.parse.called )
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_allows_no_choiceresponsedesc(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("sg$")) )
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_allows_no_choicegoto(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("sd$")) )
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		i = MockInput("sdg$")
		dt.ChoiceResponse.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"ChoiceResponseSeparator","ChoiceResponseDesc","ChoiceGoto")	
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		i = MockInput("z$")
		dt.ChoiceResponse.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceResponseSeparator(unittest.TestCase):

	def test_construc(self):
		dt.ChoiceResponseSeparator()
		
	def test_parse_returns_choiceresponseseparator(self):
		result = dt.ChoiceResponseSeparator.parse(MockInput("--$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponseSeparator) )
		
	def test_parse_expects_first_hyphen(self):
		self.assertIsNone( dt.ChoiceResponseSeparator.parse(MockInput("$")) )

	def test_parse_expects_second_hyphen(self):
		self.assertIsNone( dt.ChoiceResponseSeparator.parse(MockInput("-$")) )

	def test_parse_consumes_input_on_success(self):
		i = MockInput("--$")
		dt.ChoiceResponseSeparator.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("-$")
		dt.ChoiceResponseSeparator.parse(i)
		self.assertEquals(0, i.pos)		


class TestChoiceResponseDesc(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceResponseDesc(["foo","bar"])

	def test_parts_readable(self):
		d = dt.ChoiceResponseDesc(["foo","bar"])
		self.assertEquals("foo", d.parts[0])
		
	def test_parts_not_writable(self):
		d = dt.ChoiceResponseDesc(["foo","bar"])
		with self.assertRaises(AttributeError):
			d.parts = ["weh"]
			
	def test_parts_immutable(self):
		d = dt.ChoiceResponseDesc(["foo","bar"])
		d.parts[0] = "weh"
		self.assertEquals("foo", d.parts[0])

	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_returns_populated_choiceresponsedesc(self):
		p1 = object()
		p2 = object()
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":p1,"d":p2})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("plqtd$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponseDesc) )
		self.assertTrue( hasattr(result,"parts") )
		self.assertEquals([p1,p2], result.parts)

	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_expects_first_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceResponseDesc.parse(MockInput("z$")) )
		self.assertFalse( dt.Newline.parse.called )
		self.assertFalse( dt.QuoteMarker.parse.called )
		self.assertFalse( dt.TextLineMarker.parse.called )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_expects_newline_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pqtp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_allows_no_quote_marker_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pltp$"))
		self.assertIsNotNone(result)
		self.assertEquals(2, len(result.parts))
		
	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_expects_textlinemarker_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("plqp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))

	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_expects_no_choicemarker_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("plqctp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))

	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_expects_part_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("plqt$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_allows_multiple_parts(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("plqtplqtplqtp$"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.parts))

	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("plqtp$")
		dt.ChoiceResponseDesc.parse(i)
		self.assertEquals(5, i.pos)
		
	@mock_globals(dt,"ChoiceResponseDescPart","Newline","QuoteMarker",
			"TextLineMarker","ChoiceMarker")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("z$")
		dt.ChoiceResponseDesc.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceResponseDescPart(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceResponseDescPart("foo")
		
	def test_text_readable(self):
		p = dt.ChoiceResponseDescPart("foo")
		self.assertEquals("foo",p.text)
		
	def test_text_not_writable(self):
		p = dt.ChoiceResponseDescPart("foo")
		with self.assertRaises(AttributeError):
			p.text = "blah"
			
	def test_parse_returns_populated_choiceresponsedescpart(self):
		result = dt.ChoiceResponseDescPart.parse(MockInput("foo\x00"))
		self.assertTrue( isinstance(result,dt.ChoiceResponseDescPart) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo", result.text)

	def test_parse_allows_got(self):
		result = dt.ChoiceResponseDescPart.parse(MockInput("GO T\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.text))
		
	def test_parse_doesnt_allow_goto(self):
		self.assertIsNone( dt.ChoiceResponseDescPart.parse(MockInput("GO TO\x00")) )

	def test_parse_allows_chars_nums_and_punctuation(self):
		result = dt.ChoiceResponseDescPart.parse(MockInput("a0f!7%\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(6, len(result.text) )
		
	def test_parse_allows_space_and_tab(self):
		result = dt.ChoiceResponseDescPart.parse(MockInput(" \t \t\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.text))

	def test_parse_consumes_input_on_sucess(self):
		i = MockInput("foo\x00")
		dt.ChoiceResponseDescPart.parse(i)
		self.assertEquals(3, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("GO TO\x00")
		dt.ChoiceResponseDescPart.parse(i)
		self.assertEquals(0, i.pos)
		

class TestChoiceGoto(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceGoto("foo")
	
	def test_name_readable(self):
		g = dt.ChoiceGoto("foo")
		self.assertEquals("foo",g.name)
		
	def test_name_not_writable(self):
		g = dt.ChoiceGoto("foo")
		with self.assertRaises(AttributeError):
			g.name = "bar"
			
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_returns_choicegoto(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		n = object()
		dt.Name.parse.side_effect = make_parse({"n":n})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		result = dt.ChoiceGoto.parse(MockInput("mwne$"))
		self.assertTrue( isinstance(result,dt.ChoiceGoto) )
		self.assertTrue( hasattr(result,"name") )
		self.assertEquals( n, result.name )

	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_expects_gotomarker(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("wne$")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_allows_no_linewhitespace(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("mne$")) )
		
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_expects_name(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("mwe$")) )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_allows_no_endpunctuation(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("mwn$")) )
		
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_consumes_input_on_success(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		i = MockInput("mwne$")
		dt.ChoiceGoto.parse(i)
		self.assertEquals(4,i.pos)
		
	@mock_globals(dt,"GotoMarker","LineWhitespace","Name","EndPunctuation")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		i = MockInput("mwq$")
		dt.ChoiceGoto.parse(i)
		self.assertEquals(0,i.pos)


class TestGotoMarker(unittest.TestCase):

	def test_construct(self):
		dt.GotoMarker()
		
	def test_parse_returns_gotomarker(self):
		result = dt.GotoMarker.parse(MockInput("GO TO$"))
		self.assertTrue( isinstance(result,dt.GotoMarker) )
		
	def test_parse_expects_g(self):
		self.assertIsNone( dt.GotoMarker.parse(MockInput("O TO$")) )
		
	def test_parse_expects_first_o(self):
		self.assertIsNone( dt.GotoMarker.parse(MockInput("G TO$")) )
		
	def test_parse_expects_space(self):
		self.assertIsNone( dt.GotoMarker.parse(MockInput("GOTO$")) )
		
	def test_parse_expects_t(self):
		self.assertIsNone( dt.GotoMarker.parse(MockInput("GO O$")) )
		
	def test_parse_expects_second_o(self):
		self.assertIsNone( dt.GotoMarker.parse(MockInput("GO T$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("GO TO$")
		dt.GotoMarker.parse(i)
		self.assertEquals(5, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("GO TP$")
		dt.GotoMarker.parse(i)


class TestEndPunctuation(unittest.TestCase):

	def test_construct(self):
		dt.EndPunctuation()
		
	def test_parse_returns_endpunctuation(self):
		result = dt.EndPunctuation.parse(MockInput(".$"))
		self.assertTrue( isinstance(result,dt.EndPunctuation) )
		
	def test_parse_expects_punc_char(self):
		self.assertIsNone( dt.EndPunctuation.parse(MockInput("g$")) )
		
	def test_parse_allows_comma(self):
		self.assertIsNotNone( dt.EndPunctuation.parse(MockInput(",$")) )
		
	def test_parse_allows_colon(self):
		self.assertIsNotNone( dt.EndPunctuation.parse(MockInput(":$")) )
		
	def test_parse_allows_semicolon(self):
		self.assertIsNotNone( dt.EndPunctuation.parse(MockInput(";$")) )
		
	def test_parse_allows_exclaimation(self):
		self.assertIsNotNone( dt.EndPunctuation.parse(MockInput("!$")) )
		
	def test_parse_allows_question(self):
		self.assertIsNotNone( dt.EndPunctuation.parse(MockInput("?$")) )
		
	def test_parse_allows_multiple_punc_chars(self):
		i = MockInput(",!?$")
		self.assertIsNotNone( dt.EndPunctuation.parse(i) )
		self.assertEquals(3, i.pos)
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput(".$")
		dt.EndPunctuation.parse(i)
		self.assertEquals(1,i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("g$")
		dt.EndPunctuation.parse(i)
		self.assertEquals(0,i.pos)
		

class TestInstructionBlock(unittest.TestCase):
	
	def test_construct(self):
		dt.InstructionBlock(["foo","bar"])

	def test_lines_readable(self):
		b = dt.InstructionBlock(["foo","bar"])
		self.assertEquals("foo",b.lines[0])
		
	def test_lines_not_writable(self):
		b = dt.InstructionBlock(["foo","bar"])
		with self.assertRaises(AttributeError):
			b.lines = ["weh"]

	def test_lines_immutable(self):
		b = dt.InstructionBlock(["foo","bar"])
		b.lines[0] = "weh"
		self.assertEquals("foo", b.lines[0])

	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_returns_instructionblock(self):
		l1 = object()
		l2 = object()
		dt.InstructionLine.parse.side_effect = make_parse({"l":l1,"m":l2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.InstructionBlock.parse(MockInput("lmb$"))
		self.assertTrue( isinstance(result,dt.InstructionBlock) )
		self.assertTrue( hasattr(result,"lines") )
		self.assertEquals([l1,l2], result.lines)
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_expects_instructionline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.InstructionBlock.parse(MockInput("b$")) )
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_allows_multiple_instructionlines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result =  dt.InstructionBlock.parse(MockInput("lllb$"))
		self.assertIsNotNone( result )
		self.assertEquals(3, len(result.lines) )
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_allows_no_blanklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.InstructionBlock.parse(MockInput("l$")) )
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_allows_multiple_blank_lines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("lbbb$")
		self.assertIsNotNone( dt.InstructionBlock.parse(i) )
		self.assertEquals(4,i.pos)
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_consumes_input_on_success(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("lb$")
		dt.InstructionBlock.parse(i)
		self.assertEquals(2,i.pos)
		
	@mock_globals(dt,"InstructionLine", "BlankLine")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("z$")
		dt.InstructionBlock.parse(i)
		self.assertEquals(0,i.pos)


class TestInstructionLine(unittest.TestCase):
	
	def test_construct(self):
		dt.InstructionLine("foo")
		
	def test_text_readable(self):
		l = dt.InstructionLine("foo")
		self.assertEquals("foo",l.text)
		
	def test_text_not_writable(self):
		l = dt.InstructionLine("foo")
		with self.assertRaises(AttributeError):
			l.text = "bar"
	
	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_returns_populated_instructionline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		t = object()
		dt.LineText.parse.side_effect = make_parse({"t":t})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.InstructionLine.parse(MockInput("qitl$"))
		self.assertTrue( isinstance(result,dt.InstructionLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( t, result.text )
		
	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_allows_no_quote_marker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.InstructionLine.parse(MockInput("itl$")) )

	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_expects_instructionlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.InstructionLine.parse(MockInput("qtl$")) )
		self.assertFalse( dt.LineText.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_expects_linetext(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.InstructionLine.parse(MockInput("qil$")) )
		self.assertFalse( dt.Newline.parse.called )	

	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.InstructionLine.parse(MockInput("qit$")) )

	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qitl$")
		dt.InstructionLine.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_globals(dt,"QuoteMarker","InstructionLineMarker","LineText","Newline")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qit$")
		dt.InstructionLine.parse(i)
		self.assertEquals(0, i.pos)


class TestInstructionLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.InstructionLineMarker()
		
	def test_parse_returns_instructionlinemarker(self):
		result = dt.InstructionLineMarker.parse(MockInput("% $"))
		self.assertTrue( isinstance(result,dt.InstructionLineMarker) )

	def test_parse_expects_percent(self):
		self.assertIsNone( dt.InstructionLineMarker.parse(MockInput("z$")) )
		
	def test_parse_expects_space(self):
		self.assertIsNone( dt.InstructionLineMarker.parse(MockInput("%$")) )
		
	def test_parse_accepts_tab(self):
		self.assertIsNotNone( dt.InstructionLineMarker.parse(MockInput("%\t$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("% $")
		dt.InstructionLineMarker.parse(i)
		self.assertEquals(2,i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("%$")
		dt.InstructionLineMarker.parse(i)
		self.assertEquals(0,i.pos)
		
		
class TestLineText(unittest.TestCase):

	def test_construct(self):
		dt.LineText("foo")
		
	def test_text_readable(self):
		t = dt.LineText("foo")
		self.assertEquals("foo", t.text)
		
	def test_text_not_writable(self):
		t = dt.LineText("foo")
		with self.assertRaises(AttributeError):
			t.text = "bar"
			
	def test_parse_returns_populated_linetext(self):
		result = dt.LineText.parse(MockInput("foo\x00"))
		self.assertTrue( isinstance(result,dt.LineText) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo"+" ", result.text)
		
	def test_parse_expects_char(self):
		self.assertIsNone( dt.LineText.parse(MockInput("\x00")) )
		
	def test_parse_allows_multiple_alpha_number_or_punc_chars(self):
		result = dt.LineText.parse(MockInput("a7!f-G.\x00")) 
		self.assertIsNotNone( result )
		self.assertEquals( 7+1, len(result.text) )
		
	def test_parse_allows_space_and_tab(self):
		result = dt.LineText.parse(MockInput(" \t \t\x00"))
		self.assertIsNotNone( result )
		self.assertEquals( 4+1, len(result.text) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("foo\x00")
		dt.LineText.parse(i)
		self.assertEquals(3,i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("\x00")
		dt.LineText.parse(i)
		self.assertEquals(0,i.pos)


class TestTextBlock(unittest.TestCase):

	def test_construct(self):
		dt.TextBlock(["foo","bar"])
		
	def test_lines_readable(self):
		b = dt.TextBlock(["foo","bar"])
		self.assertEquals("foo",b.lines[0])
		
	def test_lines_not_writable(self):
		b = dt.TextBlock(["foo","bar"])
		with self.assertRaises(AttributeError):
			b.lines = ["weh"]
			
	def test_lines_immutable(self):
		b = dt.TextBlock(["foo","bar"])
		b.lines[0] = "weh"
		self.assertEquals("foo",b.lines[0])
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_returns_populated_textblock(self):
		l1 = object()
		l2 = object()
		dt.TextLine.parse.side_effect = make_parse({"l":l1,"m":l2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.TextBlock.parse(MockInput("lmb$"))
		self.assertTrue( isinstance(result,dt.TextBlock) )
		self.assertTrue( hasattr(result,"lines") )
		self.assertEquals([l1,l2], result.lines)
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_expects_textline(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.TextBlock.parse(MockInput("b$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_allows_no_blanklines(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.TextBlock.parse(MockInput("l$")) )
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_allows_multiple_textlines(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.TextBlock.parse(MockInput("lllb$"))
		self.assertIsNotNone( result )
		self.assertEquals(3, len(result.lines) )
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_allows_multiple_blanklines(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.TextBlock.parse(MockInput("lbbb$")) )
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_consumes_input_on_success(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("lb$")
		dt.TextBlock.parse(i)
		self.assertEquals(2,i.pos)
		
	@mock_globals(dt,"TextLine","BlankLine")
	def test_parse_consumes_input_on_success(self):
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("z$")
		dt.TextBlock.parse(i)
		self.assertEquals(0,i.pos)


class TestTextLine(unittest.TestCase):
	
	def test_construct(self):
		dt.TextLine("foo")
		
	def test_text_readable(self):
		l = dt.TextLine("foo")
		self.assertEquals("foo", l.text)
		
	def test_text_not_writable(self):
		l = dt.TextLine("foo")
		with self.assertRaises(AttributeError):
			l.text = "bar"
			
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_returns_textline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		t = object()
		dt.LineText.parse.side_effect = make_parse({"t":t})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.TextLine.parse(MockInput("qmtl$"))
		self.assertTrue( isinstance(result, dt.TextLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals(t, result.text)
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_allows_no_quote_marker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.TextLine.parse(MockInput("mtl$")) )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_expects_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.TextLine.parse(MockInput("qtl$")) )
		self.assertFalse( dt.LineText.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_expects_linetext(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.TextLine.parse(MockInput("qml$")) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.TextLine.parse(MockInput("qmt$")) )
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qmtl$")
		dt.TextLine.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_globals(dt,"QuoteMarker","TextLineMarker","LineText","Newline")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qmt$")
		dt.TextLine.parse(i)
		self.assertEquals(0, i.pos)


class TestFeedbackBlock(unittest.TestCase):

	def test_construct(self):
		dt.FeedbackBlock(["foo","bar"])
			
	def test_lines_readable(self):
		b = dt.FeedbackBlock(["foo","bar"])
		self.assertEquals("foo",b.lines[0])
			
	def test_lines_not_writable(self):
		b = dt.FeedbackBlock(["foo","bar"])
		with self.assertRaises(AttributeError):
			b.lines = ["weh"]
				
	def test_lines_immutable(self):
		b = dt.FeedbackBlock(["foo","bar"])
		b.lines[0] = "weh"
		self.assertEquals("foo",b.lines[0])
	
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_returns_populated_feedbackblock(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		l1 = object()
		l2 = object()
		dt.FeedbackLine.parse.side_effect = make_parse({"f":l1,"g":l2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.FeedbackBlock.parse(MockInput("fgb$"))
		self.assertTrue( isinstance(result,dt.FeedbackBlock) )
		self.assertTrue( hasattr(result,"lines") )
		self.assertEquals([l1,l2], result.lines)
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_expects_feedbackline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("b$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_checks_and_rejects_instructionline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_checks_and_rejects_textline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_checks_and_rejects_choice(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"l":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_checks_and_rejects_heading(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"l":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_allows_multiple_feedbacklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.FeedbackBlock.parse(MockInput("fffb$"))
		self.assertIsNotNone( result )
		self.assertEquals(3, len(result.lines) )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_allows_no_blanklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.FeedbackBlock.parse(MockInput("f$")) )
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_allows_multiple_blanklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.FeedbackBlock.parse(MockInput("fbbb$")) )
	
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_consumes_input_on_success(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("fb$")
		dt.FeedbackBlock.parse(i)
		self.assertEquals(2, i.pos)
		
	@mock_globals(dt,"InstructionLine","TextLine","Choice","Heading",
				"FeedbackLine","BlankLine")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("z$")
		dt.FeedbackBlock.parse(i)
		self.assertEquals(0, i.pos)


class TestFeedbackLine(unittest.TestCase):
	
	def test_construct(self):
		dt.FeedbackLine("foo")
		
	def test_text_readable(self):
		l = dt.FeedbackLine("foo")
		self.assertEquals("foo", l.text)
		
	def test_text_not_writable(self):
		l = dt.FeedbackLine("foo")
		with self.assertRaises(AttributeError):
			l.text = "bar"
			
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_returns_populated_feedbackline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		t = object()
		dt.LineText.parse.side_effect = make_parse({"t":t})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.FeedbackLine.parse(MockInput("qtl$"))
		self.assertTrue( isinstance(result,dt.FeedbackLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( t, result.text )
	
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.FeedbackLine.parse(MockInput("tl$")) )
	
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_expects_linetext(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("ql$")) )
		self.assertFalse( dt.Newline.parse.called )
	
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("qt$")) )
	
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtl$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"QuoteMarker","LineText","Newline")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qt$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(0, i.pos)
	
		
unittest.main()

