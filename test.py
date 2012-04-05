#!/usr/bin/python2

# see TODO

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


def get_nested(obj,propspec):
	parts = propspec.split(".")
	path,name = parts[:-1],parts[-1]
	for n in path:
		obj = getattr(obj,n)
	return obj,name


def mock_statics(where,*names):
	def dec(fn):
		def newfn(*args,**kargs):
			staticmap = {}
			try:
				# store static methods in map, replace with mocks
				for n in names:
					obj,prop = get_nested(where,n)
					staticmap[n] = getattr(obj,prop)
					setattr(obj,prop,mock.Mock())
				return fn(*args,**kargs)
			finally:
				# restore static methods
				for n in names:
					obj,prop = get_nested(where,n)
					setattr(obj,prop,staticmethod(
						staticmap.get(n,getattr(obj,prop))))
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
		
		if callable(v) and not isinstance(v,mock.Mock):
			return v()
		else:
			return v
	return parse			


def make_text_line(text):
	m = mock.Mock()
	m.text.text = text
	return m
	
	
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

	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_returns_populated_document(self):
		s1 = self.make_section()
		s2 = self.make_section("foo")
		dt.FirstSection.parse.side_effect = make_parse({"f":s1})
		dt.Section.parse.side_effect = make_parse({"s":s2})
		result = dt.Document.parse(MockInput("fs\x00",0,None))
		self.assertTrue( isinstance(result,dt.Document) )
		self.assertTrue( hasattr(result,"sections") )
		self.assertEquals( [s1,s2], list(result.sections) )

	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_expects_firstsection(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		self.assertIsNone( dt.Document.parse(MockInput("s\x00",0,None)) )
		self.assertFalse( dt.Section.parse.called )
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_allows_zero_sections(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		dt.Section.parse.side_effect = make_parse({"s":self.make_section("foo")})
		self.assertIsNotNone( dt.Document.parse(MockInput("f\x00",0,None)) )
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_allows_multiple_sections(self):
		secgen = (self.make_section(n) for n in ["one","two","three"])
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		dt.Section.parse.side_effect = make_parse({"s":secgen.next})
		self.assertIsNotNone( dt.Document.parse(MockInput("fsss\x00",0,None)) )
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_expects_char_0(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		dt.Section.parse.side_effect = make_parse({"s":self.make_section("foo")})
		self.assertIsNone( dt.Document.parse(MockInput("fq",0,None)) )
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_consumes_input_on_success(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		dt.Section.parse.side_effect = make_parse({"s":self.make_section("foo")})
		i = MockInput("fs\x00",0,None)
		dt.Document.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section()})
		dt.Section.parse.side_effect = make_parse({"s":self.make_section("foo")})
		i = MockInput("fsq",0,None)
		dt.Document.parse(i)
		self.assertEquals(0, i.pos)
	
	def make_section(self,name=None,gotos=[]):
		cbs = []
		for gs in gotos:
			cs = []
			for g in gs:
				cs.append(dt.Choice(
					dt.ChoiceMarker(
						dt.ChoiceMarkerText("blah")),
					dt.ChoiceDescription([
						dt.ChoiceDescPart("weh")]),
					dt.ChoiceResponse(
						dt.ChoiceResponseDesc([
							dt.ChoiceResponseDescPart("yadda")]),
						dt.ChoiceGoto(
							dt.Name(g)))))
			cbs.append(dt.ChoiceBlock(cs))
		bs = [dt.TextBlock("foo","bar")]
		bs.extend(cbs)
		c = dt.SectionContent(bs)
		if name is None:
			return dt.FirstSection(c)
		else:
			h = dt.Heading( dt.Name(name) )
			return dt.Section(h,c)

	@mock_statics(dt,"FirstSection.parse","Section.parse")	
	def test_parse_throws_error_for_duplicate_section_names(self):
	
		s1 = self.make_section()
		s2 = self.make_section("foobar")
		s3 = self.make_section("foobar")
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		with self.assertRaises(dt.ValidationError):		
			dt.Document.parse(MockInput("\x00"))
			
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_doesnt_throw_error_for_unique_section_names(self):
	
		s1 = self.make_section()
		s2 = self.make_section("foobar")
		s3 = self.make_section("wibble")
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		dt.Document.parse(MockInput("\x00"))
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")
	def test_parse_throws_error_for_invalid_goto_reference_in_first_section(self):
		
		s1 = self.make_section(gotos=[["nowhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		with self.assertRaises(dt.ValidationError):
			dt.Document.parse(MockInput("\x00"))

	@mock_statics(dt,"FirstSection.parse","Section.parse")	
	def test_parse_throws_error_for_invalid_goto_reference_in_section(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[])
		s3 = self.make_section("anywhere",gotos=[["neverneverland","somewhere"]])
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		with self.assertRaises(dt.ValidationError):
			dt.Document.parse(MockInput("\x00"))

	@mock_statics(dt,"FirstSection.parse","Section.parse")		
	def test_parse_doesnt_throw_error_for_valid_forward_goto_references(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		dt.Document.parse(MockInput("\x00"))
	
	@mock_statics(dt,"FirstSection.parse","Section.parse")		
	def test_parse_doesnt_throw_error_for_valid_backward_goto_references(self):
				
		s1 = self.make_section(gotos=[])
		s2 = self.make_section("somewhere",gotos=[])
		s3 = self.make_section("anywhere",gotos=[["somewhere"]])
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		dt.Document.parse(MockInput("\x00"))
		
	@mock_statics(dt,"FirstSection.parse","Section.parse")		
	def test_parse_doesnt_throws_error_for_self_goto_references(self):
		
		s1 = self.make_section(gotos=[])
		s2 = self.make_section("somewhere",gotos=[["somewhere"]])
		s3 = self.make_section("anywhere", gotos=[["anywhere"]])
		
		dt.FirstSection.parse.return_value = s1
		dt.Section.parse.side_effect = [s2,s3,None]
		
		dt.Document.parse(MockInput("\x00"))
		
		
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
			
	@mock_statics(dt,"SectionContent.parse")
	def test_parse_returns_populated_firstsection(self):	
		c = object()
		dt.SectionContent.parse.side_effect = make_parse({"c":c})
		result = dt.FirstSection.parse(MockInput("c",0,None))
		self.assertTrue( isinstance(result,dt.FirstSection) )
		self.assertTrue( hasattr(result,"content") )
		self.assertEquals( c, result.content )
		
	@mock_statics(dt,"SectionContent.parse")
	def test_parse_expects_sectioncontent(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.FirstSection.parse(MockInput("q",0,None)) )
		
	@mock_statics(dt,"SectionContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		input = MockInput("c",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(1, input.pos)

	@mock_statics(dt,"SectionContent.parse")
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
		
	@mock_statics(dt,"Heading.parse","SectionContent.parse")	
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
		
	@mock_statics(dt,"Heading.parse","SectionContent.parse")
	def test_parse_expects_heading(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		self.assertIsNone( dt.Section.parse(MockInput("c",0,None)) )
		self.assertFalse( dt.SectionContent.parse.called )
		
	@mock_statics(dt,"Heading.parse","SectionContent.parse")
	def test_parse_expects_sectioncontent(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.Section.parse(MockInput("hq",0,None)) )
		
	@mock_statics(dt,"Heading.parse","SectionContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.SectionContent.parse.side_effect = make_parse({"c":object()})
		i = MockInput("hc",0,None)
		dt.Section.parse(i)
		self.assertEquals(2, i.pos)
		
	@mock_statics(dt,"Heading.parse","SectionContent.parse")
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
			
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
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
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("hwnhl",0,None)) )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_first_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qwnhl",0,None)) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertEquals( 1, dt.HeadingMarker.parse.call_count )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("qhnhl",0,None)) )

	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_name(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwhl",0,None)) )
		self.assertEquals(1, dt.HeadingMarker.parse.call_count)
		self.assertFalse( dt.Newline.parse.called )		

	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_secton_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnl",0,None)) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhz",0,None)) )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qhwnhl",0,None)
		dt.Heading.parse(i)
		self.assertEquals(6, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
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
		  	
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")
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

	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")
	def test_parse_allows_no_blank_line(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("citf$")) )
		
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")	
	def test_parse_allows_multiple_blank_lines(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("bbbcitf$")) )
		  	
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")	
	def test_parse_expects_block(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNone( dt.SectionContent.parse(MockInput("bbb$")) )
		
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")	
	def test_parse_allows_many_mixed_blocks(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("btiicfttccfi$")) )
		
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")	
	def test_parse_consumes_input_on_success(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":object()})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":object()})
		dt.TextBlock.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackBlock.parse.side_effect = make_parse({"f":object()})
		i = MockInput("bcitf$")
		dt.SectionContent.parse(i)
		self.assertEquals(5, i.pos)
		
	@mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackBlock.parse")	
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

	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
	def test_parse_returns_blankline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.BlankLine.parse(MockInput("qwl"))
		self.assertTrue( isinstance(result,dt.BlankLine) )
		
	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.BlankLine.parse(MockInput("wl")) )
		  	
	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
	def test_parse_allows_no_linewhitespace(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.BlankLine.parse(MockInput("ql")) )
			
	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.BlankLine.parse(MockInput("qwz")) )
	
	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qwl")
		dt.BlankLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")	
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
		
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_returns_populated_choiceblock(self):
		c1 = object()
		c2 = object()
		dt.Choice.parse.side_effect = make_parse({"c":c1,"C":c2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		result = dt.ChoiceBlock.parse(MockInput("cCb$"))
		self.assertTrue( isinstance(result,dt.ChoiceBlock) )
		self.assertTrue( hasattr(result,"choices") )
		self.assertEquals( [c1,c2], result.choices )
		
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_expects_choice(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.ChoiceBlock.parse(MockInput("b$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		  	
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_allows_multiple_choices(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("cccb$")) )
		  	
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_allows_no_blanklines(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("c$")) )
		  	
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_allows_multiple_blank_lines(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.ChoiceBlock.parse(MockInput("cbbb$")) )
		  	
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
	def test_parse_consumes_input_on_success(self):
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		i = MockInput("ccb$")
		dt.ChoiceBlock.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"Choice.parse","BlankLine.parse")
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
			
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse", "LineWhitespace.parse")
	def test_parse_returns_populated_choice(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		c = object()
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":c})
		d = object()
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":d})
		r = object()
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":r})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.Choice.parse(MockInput("qtwcwdrl"))
		self.assertTrue( isinstance(result,dt.Choice) )
		self.assertTrue( hasattr(result,"marker") )
		self.assertEquals( c, result.marker )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals( d, result.description )
		self.assertTrue( hasattr(result,"response") )
		self.assertEquals( r, result.response )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("twcwdrl")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_expects_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qwcwdrl")) )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		self.assertFalse( dt.ChoiceDescription.parse.called )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_allows_no_linewhitespace_after_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("qtcwdrl")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_expects_choicemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtwwdrl")) )
		self.assertFalse( dt.ChoiceDescription.parse.called )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_allows_no_whitespace_after_choicemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("qtwcdrl")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_expects_choice_description(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtwcwrl")) )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_allows_no_choiceresponse(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Choice.parse(MockInput("qtwcwdl")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Choice.parse(MockInput("qtwcwdr$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtwcwdrl")
		dt.Choice.parse(i)
		self.assertEquals(8,i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"ChoiceMarker.parse","ChoiceDescription.parse",
			"ChoiceResponse.parse", "Newline.parse","LineWhitespace.parse")
	def test_parse_consumes_no_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})		
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtwcwdr$")
		dt.Choice.parse(i)
		self.assertEquals(0,i.pos)


class TestTextLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.TextLineMarker()
		
	def test_parse_returns_textlinemarker(self):
		result = dt.TextLineMarker.parse(MockInput(":$"))
		self.assertTrue( isinstance(result,dt.TextLineMarker) )
		
	def test_parse_expects_color(self):
		self.assertIsNone( dt.TextLineMarker.parse(MockInput("$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput(":$")
		dt.TextLineMarker.parse(i)
		self.assertEquals(1, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("$")
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
			
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
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
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
	def test_parse_expects_choicemarkeropen(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("wtc")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarkerText.parse.called )
		self.assertFalse( dt.ChoiceMarkerClose.parse.called )
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("otc")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
	def test_parse_allows_no_choicemarkertext(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("owc")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
	def test_parse_expects_choicemarkerclose(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("owt$")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerText.parse.side_effect = make_parse({"t":object()})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		i = MockInput("owtc")
		dt.ChoiceMarker.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerText.parse","ChoiceMarkerClose.parse")
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

	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_returns_populated_choicedescription(self):
		p1 = object()
		p2 = object()
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":p1,"d":p2})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceDescription.parse(MockInput("pnd$"))
		self.assertTrue( isinstance(result,dt.ChoiceDescription) )
		self.assertTrue( hasattr(result,"parts") )
		self.assertEquals([p1,p2], result.parts)
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_part(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.ChoiceDescription.parse(MockInput("z$")) )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )
		self.assertFalse( dt.ChoiceDescNewline.parse.called )
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_allows_single_part(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		self.assertIsNotNone( dt.ChoiceDescription.parse(MockInput("p$")) )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_choicedescnewline_for_second_part(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceDescription.parse(MockInput("pp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))

	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_part_for_second_part(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceDescription.parse(MockInput("pn$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_allows_multiple_parts(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceDescription.parse(MockInput("pnpnpnp$"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.parts))
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		i = MockInput("pnp$")
		dt.ChoiceDescription.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
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
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_returns_populated_choiceresponse(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		d = object()	
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":d})
		g = object()
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":g})
		result = dt.ChoiceResponse.parse(MockInput("nsndg$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponse) )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals(d, result.description)
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals(g, result.goto)
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_allows_no_first_choicedescnewline(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("sndg$")) )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_expects_choiceresponseseparator(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNone( dt.ChoiceResponse.parse(MockInput("n$")) )
		self.assertFalse( dt.ChoiceResponseDesc.parse.called )
		self.assertFalse( dt.ChoiceGoto.parse.called )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_allows_no_choicedescnewline_for_choiceresponsedesc(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsdg$")) )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_allows_choicegoto_and_no_choiceresponsedesc(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsg$")) )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_allows_choiceresponsedesc_and_no_choicegoto(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsnd$")) )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_expects_either_choiceresponsedesc_or_choicegoto(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		self.assertIsNone( dt.ChoiceResponse.parse(MockInput("ns$")) )
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		i = MockInput("nsndg$")
		dt.ChoiceResponse.parse(i)
		self.assertEquals(5, i.pos)
		
	@mock_statics(dt,"ChoiceResponseSeparator.parse","ChoiceDescNewline.parse",
			"ChoiceResponseDesc.parse","ChoiceGoto.parse")	
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})	
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":object()})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":object()})
		i = MockInput("nsn$")
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

	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_returns_populated_choiceresponsedesc(self):
		p1 = object()
		p2 = object()
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":p1,"d":p2})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pnd$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponseDesc) )
		self.assertTrue( hasattr(result,"parts") )
		self.assertEquals([p1,p2], result.parts)

	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_first_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		self.assertIsNone( dt.ChoiceResponseDesc.parse(MockInput("z$")) )
		self.assertFalse( dt.ChoiceDescNewline.parse.called )
		
	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_choicedescnewline_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_expects_part_for_second_part(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pn$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.parts))
		
	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_allows_multiple_parts(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		result = dt.ChoiceResponseDesc.parse(MockInput("pnpnpnp$"))
		self.assertIsNotNone(result)
		self.assertEquals(4, len(result.parts))

	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
		i = MockInput("pnp$")
		dt.ChoiceResponseDesc.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":object()})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":object()})
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
			
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_returns_choicegoto(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		n = object()
		dt.Name.parse.side_effect = make_parse({"n":n})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		result = dt.ChoiceGoto.parse(MockInput("lmwne$"))
		self.assertTrue( isinstance(result,dt.ChoiceGoto) )
		self.assertTrue( hasattr(result,"name") )
		self.assertEquals( n, result.name )

	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_allows_no_choicedescnewline(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("mwne$")) )

	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_expects_gotomarker(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("lwne$")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("lmne$")) )
		
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_expects_name(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("lmwe$")) )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_allows_no_endpunctuation(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("lmwn$")) )
		
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		i = MockInput("lmwne$")
		dt.ChoiceGoto.parse(i)
		self.assertEquals(5,i.pos)
		
	@mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":object()})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":object()})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		i = MockInput("lmwq$")
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
		dt.InstructionBlock("foo","bar")

	def test_text_readable(self):
		b = dt.InstructionBlock("foo","bar")
		self.assertEquals("foo",b.text)
		
	def test_text_not_writable(self):
		b = dt.InstructionBlock("foo","bar")
		with self.assertRaises(AttributeError):
			b.text = "weh"

	def test_feedback_readable(self):
		b = dt.InstructionBlock("foo","bar")
		self.assertEquals("bar",b.feedback)
		
	def test_feedback_not_writable(self):
		b = dt.InstructionBlock("foo","bar")
		with self.assertRaises(AttributeError):
			b.feedback = "weh"

	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_returns_instructionblock(self):
		l1 = dt.FirstInstructionLine(dt.LineText("foo"))
		l2 = dt.InstructionLine(dt.LineText("bar"))
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":l1})
		dt.InstructionLine.parse.side_effect = make_parse({"i":l2})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		f1 = dt.FeedbackLine(dt.LineText("blah"))
		f2 = dt.FeedbackLine(dt.LineText("yadda"))
		dt.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
		result = dt.InstructionBlock.parse(MockInput("IfbFi$"))
		self.assertTrue( isinstance(result,dt.InstructionBlock) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo bar", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah yadda", result.feedback)
				
	@mock_statics(dt,"FirstInstructionLine.parse", "InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_expects_firstinstructionline(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText(""))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText(""))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		self.assertIsNone( dt.InstructionBlock.parse(MockInput("i$")) )
		self.assertFalse( dt.InstructionLine.parse.called )
		self.assertFalse( dt.BlankLine.parse.called )
		self.assertFalse( dt.FeedbackLine.parse.called )
		
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_allows_multiple_instructionlines(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("c"))})
		result =  dt.InstructionBlock.parse(MockInput("Iii$"))
		self.assertIsNotNone( result )
		self.assertEquals(5, len(result.text) )
			
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_allows_multiple_blank_lines(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("c"))})
		result = dt.InstructionBlock.parse(MockInput("Ibbbi$"))
		self.assertIsNotNone( result )
		self.assertEquals(3,len(result.text))
		
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_allows_multiple_feedback_lines(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("c"))})
		result = dt.InstructionBlock.parse(MockInput("Ifff$"))
		self.assertIsNotNone( result )
		self.assertEquals(5,len(result.feedback))
		
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_checks_instructionline_before_feedbackline(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"i":dt.FeedbackLine(dt.LineText("c"))})
		result = dt.InstructionBlock.parse(MockInput("Ii$"))
		self.assertIsNotNone( result )
		self.assertEquals(3,len(result.text))
		
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_consumes_input_on_success(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("c"))})
		i = MockInput("Ifbfib$")
		dt.InstructionBlock.parse(i)
		self.assertEquals(6,i.pos)
		
	@mock_statics(dt,"FirstInstructionLine.parse","InstructionLine.parse", 
			"BlankLine.parse","FeedbackLine.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine(dt.LineText("a"))})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("c"))})
		i = MockInput("i$")
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
	
	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_returns_populated_instructionline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		c = dt.TextLineContent("foobar")
		dt.TextLineContent.parse.side_effect = make_parse({"c":c})
		result = dt.InstructionLine.parse(MockInput("qic$"))
		self.assertTrue( isinstance(result,dt.InstructionLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( "foobar", result.text )
		
	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_allows_no_quote_marker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNotNone( dt.InstructionLine.parse(MockInput("ic$")) )

	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_instructionlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNone( dt.InstructionLine.parse(MockInput("qc$")) )
		self.assertFalse( dt.TextLineContent.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_textlinecontent(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNone( dt.InstructionLine.parse(MockInput("qi$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		i = MockInput("qic$")
		dt.InstructionLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","InstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		i = MockInput("qi$")
		dt.InstructionLine.parse(i)
		self.assertEquals(0, i.pos)


class TestInstructionLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.InstructionLineMarker()
		
	def test_parse_returns_instructionlinemarker(self):
		result = dt.InstructionLineMarker.parse(MockInput("%$"))
		self.assertTrue( isinstance(result,dt.InstructionLineMarker) )

	def test_parse_expects_percent(self):
		self.assertIsNone( dt.InstructionLineMarker.parse(MockInput("z$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("%$")
		dt.InstructionLineMarker.parse(i)
		self.assertEquals(1,i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("$")
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
		dt.TextBlock("foo","bar")
		
	def test_text_readable(self):
		b = dt.TextBlock("foo","bar")
		self.assertEquals("foo",b.text)
		
	def test_lines_not_writable(self):
		b = dt.TextBlock("foo","bar")
		with self.assertRaises(AttributeError):
			b.text = "weh"
			
	def test_feedback_readable(self):
		b = dt.TextBlock("foo","bar")
		self.assertEquals("bar",b.feedback)
		
	def test_feedback_not_writable(self):
		b = dt.TextBlock("foo","bar")
		with self.assertRaises(AttributeError):
			b.feedback = "weh"
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_returns_populated_textblock(self):
		t1 = dt.FirstTextLine(dt.LineText("foo"))
		t2 = dt.TextLine(dt.LineText("bar"))
		dt.FirstTextLine.parse.side_effect = make_parse({"t":t1})
		dt.TextLine.parse.side_effect = make_parse({"T":t2})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		f1 = dt.FeedbackLine(dt.LineText("blah"))
		f2 = dt.FeedbackLine(dt.LineText("yadda"))
		dt.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
		result = dt.TextBlock.parse(MockInput("tfbFT$"))
		self.assertTrue( isinstance(result,dt.TextBlock) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo bar", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah yadda", result.feedback)
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse") 
	def test_parse_expects_firsttextline(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText(""))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText(""))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		self.assertIsNone( dt.TextBlock.parse(MockInput("t$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		self.assertFalse( dt.TextLine.parse.called )
		self.assertFalse( dt.FeedbackLine.parse.called )
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse") 
	def test_parse_allows_single_line(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText(""))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText(""))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		self.assertIsNotNone( dt.TextBlock.parse(MockInput("T$")) )
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_allows_multiple_textlines(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText("a"))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		result = dt.TextBlock.parse(MockInput("Ttt$"))
		self.assertIsNotNone( result )
		self.assertEquals(5, len(result.text) )
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_allows_multiple_blanklines(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText("a"))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		result = dt.TextBlock.parse(MockInput("Tbbbt$"))
		self.assertIsNotNone( result )
		self.assertEquals( 3, len(result.text) )
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_allows_multiple_feedbacklines(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText(""))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText(""))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText("a"))})
		result = dt.TextBlock.parse(MockInput("Tfff$")) 
		self.assertIsNotNone( result )
		self.assertEquals( 5, len(result.feedback) )

	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_checks_textline_before_feedbackline(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText("d"))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText("c"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"t":dt.FeedbackLine(dt.LineText("a"))})
		result = dt.TextBlock.parse(MockInput("Tt$")) 
		self.assertIsNotNone( result )
		self.assertEquals( 3, len(result.text) )
		self.assertEquals( 0, len(result.feedback) )
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_consumes_input_on_success(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText("a"))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText("b"))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine("")})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		i = MockInput("Ttf$")
		dt.TextBlock.parse(i)
		self.assertEquals(3,i.pos)
		
	@mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse")
	def test_parse_consumes_input_on_success(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine(dt.LineText(""))})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine(dt.LineText(""))})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine(dt.LineText(""))})
		i = MockInput("t$")
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
			
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_returns_populated_textline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("foo")})
		result = dt.TextLine.parse(MockInput("qmc$"))
		self.assertTrue( isinstance(result, dt.TextLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo", result.text)
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_allows_no_quote_marker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("bar")})
		self.assertIsNotNone( dt.TextLine.parse(MockInput("mc$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("weh")})
		self.assertIsNone( dt.TextLine.parse(MockInput("qc$")) )
		self.assertFalse( dt.TextLineContent.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_textlinecontent(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("weh")})
		self.assertIsNone( dt.TextLine.parse(MockInput("qm$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("blah")})
		i = MockInput("qmc$")
		dt.TextLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"c":dt.TextLineContent("wibble")})
		i = MockInput("qm$")
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
	
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
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
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_expects_feedbackline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("b$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_checks_and_rejects_instructionline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"l":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_checks_and_rejects_textline(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"l":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_checks_and_rejects_choice(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"l":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_checks_and_rejects_heading(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"l":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"l":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNone( dt.FeedbackBlock.parse(MockInput("lb$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
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
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_allows_no_blanklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.FeedbackBlock.parse(MockInput("f$")) )
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
	def test_parse_allows_multiple_blanklines(self):
		dt.InstructionLine.parse.side_effect = make_parse({"i":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.Choice.parse.side_effect = make_parse({"c":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		self.assertIsNotNone( dt.FeedbackBlock.parse(MockInput("fbbb$")) )
	
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
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
		
	@mock_statics(dt,"InstructionLine.parse","TextLine.parse","Choice.parse",
			"Heading.parse","FeedbackLine.parse","BlankLine.parse")
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
			
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_returns_populated_feedbackline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		t = object()
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":t})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.FeedbackLine.parse(MockInput("qtl$"))
		self.assertTrue( isinstance(result,dt.FeedbackLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( t, result.text )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})	
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.FeedbackLine.parse(MockInput("tl$")) )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_expects_linetext(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})	
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})		
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("ql$")) )
		self.assertFalse( dt.Newline.parse.called )

	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_checks_for_and_rejects_textlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})	
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("qtl$")) )
		self.assertFalse( dt.Newline.parse.called )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_checks_for_and_rejects_instructionlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})		
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("qtl$")) )
		self.assertFalse( dt.Newline.parse.called )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})	
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("qt$")) )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})	
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtl$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse",
			"TextLineMarker.parse","InstructionLineMarker.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineText.parse.side_effect = make_parse({"t":object()})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qt$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceDescNewline(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceDescNewline()
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_returns_choicedescnewline(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceDescNewline.parse(MockInput("lqtw$"))
		self.assertTrue( isinstance(result,dt.ChoiceDescNewline) )
	
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_expects_newline(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("qtw$")) )
		self.assertFalse( dt.QuoteMarker.parse.called )
		self.assertFalse( dt.TextLineMarker.parse.called )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("ltw$")) )
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_expects_textlinemarker(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lqw$")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lqt$")) )
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_rejects_choicemarker(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lqtwc$")) )
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_consumes_input_on_success(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("lqtw$")
		dt.ChoiceDescNewline.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_statics(dt,"Newline.parse","QuoteMarker.parse","TextLineMarker.parse",
			"LineWhitespace.parse","ChoiceMarker.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		i = MockInput("lqtwc$")
		dt.ChoiceDescNewline.parse(i)
		self.assertEquals(0, i.pos)


class TestFirstTextLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.FirstTextLineMarker()
		
	def test_parse_returns_firsttextlinemarker(self):
		result = dt.FirstTextLineMarker.parse(MockInput("::$"))
		self.assertTrue( isinstance(result,dt.FirstTextLineMarker) )
		
	def test_parse_expects_first_colon(self):
		self.assertIsNone( dt.FirstTextLineMarker.parse(MockInput("$")) )
		
	def test_parse_expects_second_colon(self):
		self.assertIsNone( dt.FirstTextLineMarker.parse(MockInput(":$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("::$")
		dt.FirstTextLineMarker.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput(":$")
		dt.FirstTextLineMarker.parse(i)
		self.assertEquals(0, i.pos)


class TestFirstTextLine(unittest.TestCase):

	def test_construct(self):
		dt.FirstTextLine("foo")
		
	def test_text_readable(self):
		l = dt.FirstTextLine("foo")
		self.assertEquals("foo",l.text)
		
	def test_text_not_writable(self):
		l = dt.FirstTextLine("foo")
		with self.assertRaises(AttributeError):
			l.text = "bar"
			
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_returns_populated_firsttextline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("foo")})
		result = dt.FirstTextLine.parse(MockInput("qmc$"))
		self.assertTrue( isinstance(result,dt.FirstTextLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( "foo", result.text )
		
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_allows_no_quote_marker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("bar")})
		self.assertIsNotNone( dt.FirstTextLine.parse(MockInput("mc$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_firsttextlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("blah")})
		self.assertIsNone( dt.FirstTextLine.parse(MockInput("qc$")) )
		self.assertFalse( dt.TextLineContent.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_firsttextlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("blah")})
		self.assertIsNone( dt.FirstTextLine.parse(MockInput("qm$")) )
	
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("blah")})
		i = MockInput("qmc$")
		dt.FirstTextLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_dpesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("yadda")})
		i = MockInput("qm$")
		dt.FirstTextLine.parse(i)
		self.assertEquals(0, i.pos)


class TestFirstInstructionLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.FirstInstructionLineMarker()
		
	def test_parse_returns_firstinstructionlinemarker(self):
		result = dt.FirstInstructionLineMarker.parse(MockInput("%%$"))
		self.assertTrue( isinstance(result,dt.FirstInstructionLineMarker) )
		
	def test_parse_expects_first_percent(self):
		self.assertIsNone( dt.FirstInstructionLineMarker.parse(MockInput("$")) )
		
	def test_parse_expects_second_percent(self):
		self.assertIsNone( dt.FirstInstructionLineMarker.parse(MockInput("%$")) )
		
	def test_parse_consumes_input_on_success(self):
		i = MockInput("%%$")
		dt.FirstInstructionLineMarker.parse(i)
		self.assertEquals(2, i.pos)
		
	def test_parse_doesnt_consume_input_on_failure(self):
		i = MockInput("%$")
		dt.FirstInstructionLineMarker.parse(i)
		self.assertEquals(0, i.pos)


class TestFirstInstructionLine(unittest.TestCase):

	def test_construct(self):
		dt.FirstInstructionLine("foo")
		
	def test_text_readable(self):
		l = dt.FirstInstructionLine("foo")
		self.assertEquals("foo", l.text)

	def test_text_not_writable(self):
		l = dt.FirstInstructionLine("foo")
		with self.assertRaises(AttributeError):
			l.text = "bar"
			
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_returns_populated_firstInstructionLine(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("foobar")})
		result = dt.FirstInstructionLine.parse(MockInput("qic$"))
		self.assertTrue( isinstance(result,dt.FirstInstructionLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foobar", result.text)
		
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNotNone( dt.FirstInstructionLine.parse(MockInput("ic$")) )
		
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_firstinstructionlinemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNone( dt.FirstInstructionLine.parse(MockInput("qc$")) )
		self.assertFalse( dt.TextLineContent.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_expects_textlinecontent(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		self.assertIsNone( dt.FirstInstructionLine.parse(MockInput("qi$")) )
			
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		i = MockInput("qic$")
		dt.FirstInstructionLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
			"TextLineContent.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
		dt.TextLineContent.parse.side_effect = make_parse({"c":dt.TextLineContent("")})
		i = MockInput("qi$")
		dt.FirstInstructionLine.parse(i)
		self.assertEquals(0, i.pos)


class TestTextLineContent(unittest.TestCase):

	def test_construct(self):
		dt.TextLineContent("foo")
		
	def test_text_is_readable(self):
		c = dt.TextLineContent("foo")
		self.assertEquals("foo",c.text)
		
	def test_text_is_not_writable(self):
		c = dt.TextLineContent("foo")
		with self.assertRaises(AttributeError):
			c.text = "weh"
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_returns_populated_textlinecontent(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		t = dt.LineText("foo")
		dt.LineText.parse.side_effect = make_parse({"t":t})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.TextLineContent.parse(MockInput("wtl$"))
		self.assertTrue( isinstance(result,dt.TextLineContent) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo",result.text)
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.TextLineContent.parse(MockInput("tl$")) )
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_expects_linetext(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.TextLineContent.parse(MockInput("wl$")) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_expects_newline(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.TextLineContent.parse(MockInput("wt$")) )
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("wtl$")
		dt.TextLineContent.parse(i)
		self.assertEquals(3,i.pos)
		
	@mock_statics(dt,"LineWhitespace.parse","LineText.parse","Newline.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("wt$")
		dt.TextLineContent.parse(i)
		self.assertEquals(0,i.pos)
		
unittest.main()

