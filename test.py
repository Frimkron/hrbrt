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

# ChoiceDescription
# ChoiceDescPart
# ChoiceResponse
# ChoiceResponseSeparator
# ChoiceResponseDesc
# ChoiceResponseDescPart
# ChoiceGoto
# GotoMarker
# EndPunctuation
# InstructionBlock
# InstructionLine
# InstructionLineMarker
# LineText
# TextBlock
# TextLine
# FeedbackBlock
# FeedbackLine		
		
unittest.main()

