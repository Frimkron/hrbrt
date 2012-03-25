#!/usr/bin/python2

import mock
import unittest
import dectree as dt

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
	
	def __init__(self,data,pos,parent):
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


def make_parse(*rets):
	def gen():
		for r in rets:
			yield r
		while True:
			yield None
	g = gen()
	def parse(input):
		v = g.next()
		if v is not None and v is not False:
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
		dt.FirstSection.parse.side_effect = make_parse(s1)
		dt.Section.parse.side_effect = make_parse(s2)
		result = dt.Document.parse(MockInput("ab\x00",0,None))
		self.assertTrue( isinstance(result,dt.Document) )
		self.assertTrue( hasattr(result,"sections") )
		self.assertEquals( [s1,s2], list(result.sections) )

	@mock_globals(dt,"FirstSection","Section")
	def test_parse_expects_firstsection(self):
		dt.FirstSection.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Document.parse(MockInput("ab\x00",0,None)) )
		self.assertFalse( dt.Section.parse.called )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_allows_zero_sections(self):
		dt.FirstSection.parse.side_effect = make_parse(object())
		dt.Section.parse.side_effect = make_parse(None)
		self.assertIsNotNone( dt.Document.parse(MockInput("a\x00",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_allows_multiple_sections(self):
		dt.FirstSection.parse.side_effect = make_parse(object())
		dt.Section.parse.side_effect = make_parse(object(),object(),object())
		self.assertIsNotNone( dt.Document.parse(MockInput("abbb\x00",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_expects_char_0(self):
		dt.FirstSection.parse.side_effect = make_parse(object())
		dt.Section.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Document.parse(MockInput("aq",0,None)) )
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_consumes_input_on_success(self):
		dt.FirstSection.parse.side_effect = make_parse(object())
		dt.Section.parse.side_effect = make_parse(object())
		i = MockInput("ab\x00",0,None)
		dt.Document.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_globals(dt,"FirstSection","Section")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.FirstSection.parse.side_effect = make_parse(object())
		dt.Section.parse.side_effect = make_parse(object())
		i = MockInput("abz",0,None)
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
		dt.SectionContent.parse.side_effect = make_parse(c)
		result = dt.FirstSection.parse(MockInput("s",0,None))
		self.assertTrue( isinstance(result,dt.FirstSection) )
		self.assertTrue( hasattr(result,"content") )
		self.assertEquals( c, result.content )
		
	@mock_globals(dt,"SectionContent")
	def test_parse_expects_sectioncontent(self):
		dt.SectionContent.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.FirstSection.parse(MockInput("s",0,None)) )
		
	@mock_globals(dt,"SectionContent")
	def test_parse_consumes_input_on_success(self):
		dt.SectionContent.parse.side_effect = make_parse(object())
		input = MockInput("s",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(1, input.pos)

	@mock_globals(dt,"SectionContent")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.SectionContent.parse.side_effect = make_parse(None)
		input = MockInput("s",0,None)
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
		dt.Heading.parse.side_effect = make_parse(h)
		c = object()
		dt.SectionContent.parse.side_effect = make_parse(c)
		result = dt.Section.parse(MockInput("hc",0,None))
		self.assertTrue( isinstance(result,dt.Section) )
		self.assertTrue( hasattr(result,"heading") )
		self.assertEquals(h, result.heading)
		self.assertTrue( hasattr(result,"content") )
		self.assertEquals(c, result.content)
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_expects_heading(self):
		dt.Heading.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Section.parse(MockInput("ab",0,None)) )
		self.assertFalse( dt.SectionContent.parse.called )
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_expects_sectioncontent(self):
		dt.Heading.parse.side_effect = make_parse(object())
		dt.SectionContent.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Section.parse(MockInput("ab",0,None)) )
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_consumes_input_on_success(self):
		dt.Heading.parse.side_effect = make_parse(object())
		dt.SectionContent.parse.side_effect = make_parse(object())
		i = MockInput("ab",0,None)
		dt.Section.parse(i)
		self.assertEquals(2, i.pos)
		
	@mock_globals(dt,"Heading","SectionContent")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.Heading.parse.side_effect = make_parse(object())
		dt.SectionContent.parse.side_effect = make_parse(None)
		i = MockInput("ab",0,None)
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
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(n)
		dt.Newline.parse.side_effect = make_parse(object())
		result = dt.Heading.parse(MockInput("qhwnhl",0,None))
		self.assertTrue( isinstance(result,dt.Heading) )
		self.assertTrue( hasattr(result,"name") )
		self.assertEquals(n, result.name)
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse(False)
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse_side_effect = make_parse(object())
		dt.Newline.parse.side_effect = make_parse(object())
		self.assertIsNotNone( dt.Heading.parse(MockInput("hwnhl",0,None)) )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_first_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhl",0,None)) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertEquals( 1, dt.HeadingMarker.parse.call_count )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_allows_no_linewhitespace(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(False)
		dt.Name.parse.side_effect = make_parse(object)
		dt.Newline.parse.side_effect = make_parse(object)
		self.assertIsNotNone( dt.Heading.parse(MockInput("qhnhl",0,None)) )

	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_name(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhl",0,None)) )
		self.assertEquals(1, dt.HeadingMarker.parse.call_count)
		self.assertFalse( dt.Newline.parse.called )		

	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_secton_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),None)
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(object())
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhl",0,None)) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(object())
		dt.Newline.parse.side_effect = make_parse(None)
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhl",0,None)) )
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(object())
		dt.Newline.parse.side_effect = make_parse(object())
		i = MockInput("qhwnhl",0,None)
		dt.Heading.parse(i)
		self.assertEquals(6, i.pos)
		
	@mock_globals(dt,"QuoteMarker","HeadingMarker","LineWhitespace","Name","Newline")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse(object())
		dt.HeadingMarker.parse.side_effect = make_parse(object(),object())
		dt.LineWhitespace.parse.side_effect = make_parse(object())
		dt.Name.parse.side_effect = make_parse(object())
		dt.Newline.parse.side_effect = make_parse(None)
		i = MockInput("qhwnhl",0,None)
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
		  	
		  	
unittest.main()

