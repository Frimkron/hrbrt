#!/usr/bin/python2

import io
import sys
import mock
import unittest
import Tkinter
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
		s = dt.FirstSection([],None)
		d = dt.Document([s])
		self.assertEquals(s, d.sections[0])
		
	def test_sections_attribute_readonly(self):
		d = dt.Document([dt.FirstSection([],None)])
		with self.assertRaises(AttributeError):
			d.sections = ["weh"]
			
	def test_sections_attribute_immutable(self):
		s = dt.FirstSection([],None)
		d = dt.Document([s])
		d.sections[0] = "weh"
		self.assertEquals(s,d.sections[0])

	def test_is_completed_readable(self):
		d = dt.Document([])
		d.is_completed
		
	def test_is_completed_not_writable(self):
		d = dt.Document([])
		with self.assertRaises(AttributeError):
			d.is_completed = True

	def setup_parse_methods(self):
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[["foo"]])})
		dt.Section.parse.side_effect = make_parse({"s":self.make_section("foo",gotos=[])})

	mock_parse_methods = mock_statics(dt,"FirstSection.parse","Section.parse")
	
	@mock_parse_methods
	def test_parse_returns_populated_document(self):
		self.setup_parse_methods()
		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo")
		dt.FirstSection.parse.side_effect = make_parse({"f":s1})
		dt.Section.parse.side_effect = make_parse({"s":s2})
		result = dt.Document.parse(MockInput("fs\x00",0,None))
		self.assertTrue( isinstance(result,dt.Document) )
		self.assertTrue( hasattr(result,"sections") )
		self.assertEquals( [s1,s2], list(result.sections) )

	@mock_parse_methods
	def test_parse_expects_firstsection(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Document.parse(MockInput("s\x00",0,None)) )
		self.assertFalse( dt.Section.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_zero_sections(self):
		self.setup_parse_methods()
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[])})
		self.assertIsNotNone( dt.Document.parse(MockInput("f\x00",0,None)) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_sections(self):
		self.setup_parse_methods()
		dt.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[["one"]])})
		secitr = iter([
			self.make_section("one",gotos=[["two"]]),
			self.make_section("two",gotos=[["three"]]),
			self.make_section("three",gotos=[])
		])
		dt.Section.parse.side_effect = make_parse({"s":secitr.next})
		self.assertIsNotNone( dt.Document.parse(MockInput("fsss\x00",0,None)) )
		
	@mock_parse_methods
	def test_parse_expects_char_0(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Document.parse(MockInput("fq",0,None)) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("fs\x00",0,None)
		dt.Document.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("fsq",0,None)
		dt.Document.parse(i)
		self.assertEquals(0, i.pos)
	
	def make_section(self,name=None,gotos=[]):
		cbs = []
		for gs in gotos:
			cs = []
			for g in gs:
				cs.append(dt.Choice("blah","weh","yadda",g,"wibble"))
			cbs.append(dt.ChoiceBlock(cs,""))
		bs = [dt.TextBlock("foo","bar")]
		bs.extend(cbs)
		if name is None:
			return dt.FirstSection(bs,"")
		else:
			return dt.Section(name,bs,"")

	def test_validate_returns_error_for_duplicate_section_names(self):
	
		s1 = self.make_section(gotos=[["foobar"]])
		s2 = self.make_section("foobar",gotos=[["foobar"]])
		s3 = self.make_section("foobar",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertEquals("Duplicate section name 'foobar'", 
			d.validate() )
		
	def test_validate_uses_case_insensitive_section_names(self):
		
		s1 = self.make_section(gotos=[["foobar"]])
		s2 = self.make_section("foobar",gotos=[["foobar"]])
		s3 = self.make_section("FoObAr",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertEqual("Duplicate section name 'foobar'",
			d.validate() )
							
	def test_validate_doesnt_return_error_for_unique_section_names(self):
	
		s1 = self.make_section(gotos=[["foobar"]])
		s2 = self.make_section("foobar",gotos=[["wibble"]])
		s3 = self.make_section("wibble",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )
		
	def test_validate_returns_error_for_invalid_goto_reference_in_first_section(self):
		
		s1 = self.make_section(gotos=[["nowhere","somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertEquals("Go-to references unknown section 'nowhere'",
			d.validate() )
	
	def test_validate_uses_case_insensitive_gotos_in_first_section(self):
		
		s1 = self.make_section(gotos=[["sOmEwHeRe"]])
		s2 = self.make_section("SoMeWhErE",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )
		
	def test_validate_returns_error_for_invalid_goto_reference_in_section(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[["neverneverland","somewhere",None]])
		d = dt.Document([s1,s2,s3])
		self.assertEquals("Go-to references unknown section 'neverneverland'",
			d.validate() )
			
	def test_validate_uses_case_insensitive_gotos_in_section(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["AnYwHeRe"]])
		s3 = self.make_section("aNyWhErE",gotos=[["somewhere",None]])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )
				
	def test_validate_doesnt_return_error_for_valid_forward_goto_references(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )
	
	def test_validate_doesnt_return_error_for_valid_backward_goto_references(self):
				
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["anywhere"]])
		s3 = self.make_section("anywhere",gotos=[["somewhere",None]])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )

	def test_validate_doesnt_return_error_for_self_goto_references(self):
		
		s1 = self.make_section(gotos=[["somewhere"]])
		s2 = self.make_section("somewhere",gotos=[["somewhere","anywhere"]])
		s3 = self.make_section("anywhere",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )

	def test_validate_doesnt_return_error_for_indirectly_looping_goto_references(self):
	
		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo",gotos=[["end","bar"]])
		s3 = self.make_section("bar",gotos=[["foo"]])
		s4 = self.make_section("end",gotos=[])
		d = dt.Document([s1,s2,s3,s4])
		self.assertIsNone( d.validate() )
	
	def test_parse_returns_error_for_incomplete_user_path_in_first_section(self):
	
		s1 = self.make_section(gotos=[[None,"the end"]])
		s2 = self.make_section("the end",gotos=[])
		d = dt.Document([s1,s2])
		self.assertEquals('Section "first" has one or more '
			+'choices that reach end of section and so never '
			+'reach end of document', d.validate())
		
	def test_parse_returns_error_for_incomplete_user_path_in_second_section(self):
	
		s1 = self.make_section(gotos=[["second","the end"]])
		s2 = self.make_section("second",gotos=[["the end",None]])
		s3 = self.make_section("the end",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertEquals('Section "second" has one or more '
			+'choices that reach end of section and so never '
			+'reach end of document', d.validate())
		
	def test_parse_only_considers_last_choice_block_for_imcomplete_path(self):
		
		s1 = self.make_section(gotos=[["second",None],["second","the end"]])
		s2 = self.make_section("second",gotos=[[None,"the end"],["the end","the end"]])
		s3 = self.make_section("the end",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertIsNone( d.validate() )
		
	def test_parse_requires_dropout_choice_in_last_section(self):
		
		s1 = self.make_section(gotos=[["second"]])
		s2 = self.make_section("second",gotos=[["the end"]])
		s3 = self.make_section("the end",gotos=[["second","the end"]])
		d = dt.Document([s1,s2,s3])
		self.assertEquals('End section "the end" has no choices '
			+'that reach end of document', d.validate())
		
	def test_validate_requires_choices_in_sections(self):
		
		s1 = self.make_section(gotos=[])
		s2 = self.make_section("the end",gotos=[[None]])
		d = dt.Document([s1,s2])
		self.assertEquals('Section "first" has no choice blocks '
			+'and so cannot reach end of document', d.validate())
			
	def test_validate_allows_lack_of_choices_in_end_section(self):
	
		s1 = self.make_section(gotos=[["the end"]])
		s2 = self.make_section("the end",gotos=[])
		d = dt.Document([s1,s2])
		self.assertIsNone( d.validate() )

	def test_validate_defers_decision_on_looping_choices(self):
		
		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo",gotos=[["bar","end"]])
		s3 = self.make_section("bar",gotos=[["foo"]])
		s4 = self.make_section("end",gotos=[])
		d = dt.Document([s1,s2,s3,s4])
		self.assertIsNone( d.validate() )			
		
	def test_validate_returns_error_for_dead_end_self_loop(self):

		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo",gotos=[["bar","end"]])
		s3 = self.make_section("bar",gotos=[["bar"]])
		s4 = self.make_section("end",gotos=[])
		d = dt.Document([s1,s2,s3,s4])
		self.assertEquals('Dead-end loop found in section "bar"',
			d.validate() )
			
	def test_validate_returns_error_for_dead_end_indirect_loop(self):
	
		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo",gotos=[["bar","end"]])
		s3 = self.make_section("bar",gotos=[["weh"]])
		s4 = self.make_section("weh",gotos=[["bar"]])
		s5 = self.make_section("end",gotos=[])
		d = dt.Document([s1,s2,s3,s4,s5])
		self.assertEquals('Dead-end loop found in section "weh"',
			d.validate() )		
			
	def test_validate_returns_error_for_double_dead_end_loop(self):
		
		s1 = self.make_section(gotos=[["foo"]])
		s2 = self.make_section("foo",gotos=[["foo","foo"]])
		s3 = self.make_section("end",gotos=[])
		d = dt.Document([s1,s2,s3])
		self.assertEquals('Dead-end loop found in section "foo"',
			d.validate() )
		
	def test_is_completed_returns_true_for_completed_section(self):
		s1 = mock.Mock()
		s1.is_completed = False
		s2 = mock.Mock()
		s2.is_completed = True
		d = dt.Document([s1,s2])
		self.assertEquals(True, d.is_completed)
		
	def test_is_completed_returns_false_for_no_completed_sections(self):
		s1 = mock.Mock()
		s1.is_completed = False
		s2 = mock.Mock()
		s2.is_completed = False
		d = dt.Document([s1,s2])
		self.assertEquals(False, d.is_completed)
		
		
class TestFirstSection(unittest.TestCase):

	def test_construct(self):
		dt.FirstSection([],"bar")
		
	def test_items_readable(self):
		i = dt.TextBlock("a",None)
		f = dt.FirstSection([i],None)
		self.assertEquals([i], f.items)
		
	def test_items_not_writable(self):
		f = dt.FirstSection([dt.TextBlock("a",None)],None)
		with self.assertRaises(AttributeError):
			f.items = ["bar"]
			
	def test_items_immutable(self):
		i = dt.TextBlock("a",None)
		f = dt.FirstSection([i],None)
		f.items[0] = "bar"
		self.assertEquals(i,f.items[0])
			
	def test_feedback_readable(self):
		f = dt.FirstSection([],"bar")
		self.assertEquals("bar",f.feedback)
		
	def test_feedback_not_writable(self):
		f = dt.FirstSection([],"bar")
		with self.assertRaises(AttributeError):
			f.feedback = "blah"
		
	def test_is_completed_readable(self):
		f = dt.FirstSection([],None)
		f.is_completed
		
	def test_is_completed_not_writable(self):
		f = dt.FirstSection([],None)
		with self.assertRaises(AttributeError):
			f.is_completed = True
		
	def setup_parse_methods(self):
		dt.SectionContent.parse.side_effect = make_parse({"c":dt.SectionContent("a","b")})
		
	mock_parse_methods = mock_statics(dt,"SectionContent.parse")
			
	@mock_parse_methods
	def test_parse_returns_populated_firstsection(self):	
		self.setup_parse_methods()
		c = dt.SectionContent(["foo"],"bar")
		dt.SectionContent.parse.side_effect = make_parse({"c":c})
		result = dt.FirstSection.parse(MockInput("c",0,None))
		self.assertTrue( isinstance(result,dt.FirstSection) )
		self.assertTrue( hasattr(result,"items") )
		self.assertEquals( ["foo"], result.items )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals( "bar", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.SectionContent.parse.side_effect = make_parse({"c":dt.SectionContent([],None)})
		result = dt.FirstSection.parse(MockInput("c"))
		self.assertIsNone(result.feedback)
		
	@mock_parse_methods
	def test_parse_expects_sectioncontent(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.FirstSection.parse(MockInput("q",0,None)) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		input = MockInput("c",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(1, input.pos)

	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		input = MockInput("q",0,None)
		dt.FirstSection.parse(input)
		self.assertEquals(0, input.pos)
		
	def test_is_completed_returns_true_for_completed_choiceblock(self):
		cb1 = mock.Mock()
		cb1.is_completed = False
		cb2 = mock.Mock()
		cb2.is_completed = True
		f = dt.FirstSection([cb1,cb2],None)
		self.assertEquals(True, f.is_completed)
		
	def test_is_completed_returns_true_for_feedback(self):
		f = dt.FirstSection([],"foobar")
		self.assertEquals(True, f.is_completed)
		
	def test_is_completed_returns_false_for_no_feedback_or_completed_blocks(self):
		cb1 = mock.Mock()
		cb1.is_completed = False
		cb2 = mock.Mock()
		cb2.is_completed = False
		f = dt.FirstSection([cb1,cb2],None)
		self.assertEquals(False, f.is_completed)
		

class TestSection(unittest.TestCase):
	
	def test_construct(self):
		dt.Section("foo",[],None)
		
	def test_heading_readable(self):
		s = dt.Section("foo",[],None)
		self.assertEquals("foo", s.heading)
		
	def test_heading_not_writable(self):
		s = dt.Section("foo",[],None)
		with self.assertRaises(AttributeError):
			s.heading = "yadda"
			
	def test_items_readable(self):
		i = dt.TextBlock("a",None)
		s = dt.Section("foo",[i],None)
		self.assertEquals([i], s.items)
		
	def test_items_not_writable(self):
		s = dt.Section("foo",[dt.TextBlock("a",None)],None)
		with self.assertRaises(AttributeError):
			s.items = "weh"
			
	def test_items_immutable(self):
		i = dt.TextBlock("a",None)
		s = dt.Section("foo",[i],None)
		s.items[0] = "yadda"
		self.assertEquals(i,s.items[0])
		
	def test_feedback_readable(self):
		s = dt.Section("foo",[],"weh")
		self.assertEquals("weh", s.feedback)
		
	def test_feedback_not_writable(self):
		s = dt.Section("foo",[],"weh")
		with self.assertRaises(AttributeError):
			s.feedback = "blah"	
	
	def test_is_completed_readable(self):
		s = dt.Section("foo",[],None)
		s.is_completed
		
	def test_is_completed_not_writable(self):
		s = dt.Section("foo",[],None)
		with self.assertRaises(AttributeError):
			s.is_completed = True
	
	def setup_parse_methods(self):
		dt.Heading.parse.side_effect = make_parse({"h":dt.Heading("a")})
		dt.SectionContent.parse.side_effect = make_parse({"c":dt.SectionContent("b","c")})
		
	mock_parse_methods = mock_statics(dt,"Heading.parse","SectionContent.parse")	
		
	@mock_parse_methods
	def test_parse_returns_populated_section(self):
		self.setup_parse_methods()
		h = dt.Heading("wobble")
		dt.Heading.parse.side_effect = make_parse({"h":h})
		c = dt.SectionContent(["foo"],"bar")
		dt.SectionContent.parse.side_effect = make_parse({"c":c})
		result = dt.Section.parse(MockInput("hc",0,None))
		self.assertTrue( isinstance(result,dt.Section) )
		self.assertTrue( hasattr(result,"heading") )
		self.assertEquals("wobble", result.heading)
		self.assertTrue( hasattr(result,"items") )
		self.assertEquals(["foo"], result.items)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("bar", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.SectionContent.parse.side_effect = make_parse({"c":dt.SectionContent([],None)})
		result = dt.Section.parse(MockInput("hc"))
		self.assertIsNone(result.feedback)
		
	@mock_parse_methods
	def test_parse_expects_heading(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Section.parse(MockInput("c",0,None)) )
		self.assertFalse( dt.SectionContent.parse.called )
		
	@mock_parse_methods
	def test_parse_expects_sectioncontent(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Section.parse(MockInput("hq",0,None)) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("hc",0,None)
		dt.Section.parse(i)
		self.assertEquals(2, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("hq",0,None)
		dt.Section.parse(i)
		self.assertEquals(0, i.pos)
		
	def test_is_completed_returns_true_for_completed_choiceblock(self):
		cb1 = mock.Mock()
		cb1.is_completed = False
		cb2 = mock.Mock()
		cb2.is_completed = True
		s = dt.Section("dave",[cb1,cb2],None)
		self.assertEquals(True, s.is_completed)
		
	def test_is_completed_returns_true_for_feedback(self):
		cb1 = mock.Mock()
		cb1.is_completed = False
		cb2 = mock.Mock()
		cb2.is_completed = False
		s = dt.Section("dave",[cb1,cb2],"foobar")
		self.assertEquals(True, s.is_completed)
		
	def test_is_completed_returns_false_for_no_completed_choiceblocks_or_feedback(self):
		cb1 = mock.Mock()
		cb1.is_completed = False
		cb2 = mock.Mock()
		cb2.is_completed = False
		s = dt.Section("dave",[cb1,cb2],None)
		self.assertEquals(False, s.is_completed)
		
		
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
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("foobar")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.Heading.parse(MockInput("qhwnhl",0,None))
		self.assertTrue( isinstance(result,dt.Heading) )
		self.assertTrue( hasattr(result,"name") )
		self.assertEquals("foobar", result.name)
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("hwnhl",0,None)) )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_first_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
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
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.Heading.parse(MockInput("qhnhl",0,None)) )

	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_name(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwhl",0,None)) )
		self.assertEquals(1, dt.HeadingMarker.parse.call_count)
		self.assertFalse( dt.Newline.parse.called )		

	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_secton_headingmarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnl",0,None)) )
		self.assertFalse( dt.Newline.parse.called )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.Heading.parse(MockInput("qhwnhz",0,None)) )
		
	@mock_statics(dt,"QuoteMarker.parse","HeadingMarker.parse",
			"LineWhitespace.parse","Name.parse","Newline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.HeadingMarker.parse.side_effect = make_parse({"h":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
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
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qhwnhz",0,None)
		dt.Heading.parse(i)
		self.assertEquals(0, i.pos)
	

class TestQuoteMarker(unittest.TestCase):
	
	def test_construct(self):
		dt.QuoteMarker()
		
	def test_parse_returns_quotemarker(self):
		result = dt.QuoteMarker.parse(MockInput(" \t> x",0,None))
		self.assertTrue( isinstance(result,dt.QuoteMarker) )
		
	def test_parse_allows_no_whitespace(self):
		self.assertIsNotNone( dt.QuoteMarker.parse(MockInput(">x",0,None)) )
		
	def test_parse_expects_angle_bracket(self):
		self.assertIsNone( dt.QuoteMarker.parse(MockInput("x",0,None)) )
		
	def test_parse_allows_multiple_markers(self):
		self.assertIsNotNone( dt.QuoteMarker.parse(MockInput(" > > > x",0,None)) )
		
	def test_parse_allows_trailing_whitespace(self):
		i = MockInput(">\t x")
		self.assertIsNotNone( dt.QuoteMarker.parse(i) )
		self.assertEquals(3,i.pos)
		
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
		dt.SectionContent(["foo","bar"],"weh")
		
	def test_items_readable(self):
		c = dt.SectionContent(["foo","bar"],"weh")
		self.assertEquals("foo", c.items[0])
		
	def test_items_not_writable(self):
		c = dt.SectionContent(["foo","bar"],"weh")
		with self.assertRaises(AttributeError):
			c.items = ["weh"]
			
	def test_items_immutable(self):
		c = dt.SectionContent(["foo","bar"],"weh")
		c.items[0] = "weh"
		self.assertEquals("foo", c.items[0])
		  	
	def test_feedback_readable(self):
		c = dt.SectionContent(["foo","bar"],"weh")
		self.assertEquals("weh",c.feedback)
		
	def test_feedback_not_writable(self):
		c = dt.SectionContent(["foo","bar"],"weh")
		with self.assertRaises(AttributeError):
			c.feedback = "blah"

	def setup_parse_methods(self):
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":dt.ChoiceBlock([],"a")})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":dt.InstructionBlock("","b")})
		dt.TextBlock.parse.side_effect = make_parse({"t":dt.TextBlock("","c")})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("a")})
		dt.StarterLine.parse.side_effect = make_parse({"s":object()})
		  	
	mock_parse_methods = mock_statics(dt,"BlankLine.parse","ChoiceBlock.parse",
			"InstructionBlock.parse","TextBlock.parse","FeedbackLine.parse",
			"StarterLine.parse")
	
	@mock_parse_methods
	def test_parse_returns_populated_sectioncontent(self):
		self.setup_parse_methods()
		c = dt.ChoiceBlock([],"foo")
		dt.ChoiceBlock.parse.side_effect = make_parse({"c":c})
		i = dt.InstructionBlock("","bar")
		dt.InstructionBlock.parse.side_effect = make_parse({"i":i})
		t = dt.TextBlock("","weh")
		dt.TextBlock.parse.side_effect = make_parse({"t":t})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("blah"),"F":dt.FeedbackLine("yadda")})
		result = dt.SectionContent.parse(MockInput("fbFcit$"))
		self.assertTrue( isinstance(result,dt.SectionContent) )
		self.assertTrue( hasattr(result,"items") )
		self.assertEquals([c,i,t], result.items)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah yadda bar weh", result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.TextBlock.parse.side_effect = make_parse({"t":dt.TextBlock("",None)})
		dt.InstructionBlock.parse.side_effect = make_parse({"i":dt.InstructionBlock("",None)})
		result = dt.SectionContent.parse(MockInput("bcit$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_allows_no_blanklines_or_feedbacklines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("cit$")) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_blank_lines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("bbbcit$")) )
		  	
	@mock_parse_methods
	def test_parse_allows_multiple_feedback_lines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("fffcit$")) )
		  	
	@mock_parse_methods
	def test_parse_checks_starterline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.StarterLine.parse.side_effect = make_parse({"f":object()})
		dt.TextBlock.parse.side_effect = make_parse({"f":dt.TextBlock("a","")})
		result = dt.SectionContent.parse(MockInput("f$"))
		self.assertIsNotNone( result )
		self.assertEquals(0, len(result.feedback))
		self.assertEquals(1, len(result.items))
		  	
	@mock_parse_methods
	def test_parse_expects_block(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.SectionContent.parse(MockInput("bbb$")) )
		
	@mock_parse_methods
	def test_parse_allows_many_mixed_blocks(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.SectionContent.parse(MockInput("btiicttci$")) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("bcit$")
		dt.SectionContent.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("bbbbbb$")
		dt.SectionContent.parse(i)
		self.assertEquals(0, i.pos)
		
	@mock_parse_methods
	def test_parse_throws_error_for_consecutive_choice_blocks(self):
		self.setup_parse_methods()
		with self.assertRaises(dt.ValidationError):
			dt.SectionContent.parse(MockInput("cc$"))
		
	@mock_parse_methods
	def test_parse_doesnt_throw_error_for_nonconsecutive_choice_blocks(self):
		self.setup_parse_methods()
		dt.SectionContent.parse(MockInput("ctc$"))	
	
		
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
		dt.ChoiceBlock([dt.Choice(None,"a","b","c",None)],None)
		
	def test_choices_readable(self):
		cc = dt.Choice(None,"a","b","c",None)
		c = dt.ChoiceBlock([cc],None)
		self.assertEquals(cc, c.choices[0])
		
	def test_choices_not_writable(self):
		c = dt.ChoiceBlock([dt.Choice(None,"a","b","c",None)],None)
		with self.assertRaises(AttributeError):
			c.choices = ["weh"]
			
	def test_choices_immutable(self):
		cc = dt.Choice(None,"a","b","c",None)
		c = dt.ChoiceBlock([cc],None)
		c.choices[0] = "blah"
		self.assertEquals(cc,c.choices[0])
		
	def test_feedback_readable(self):
		c = dt.ChoiceBlock([],"weh")
		self.assertEquals("weh", c.feedback)
		
	def test_feedback_not_writable(self):	
		c = dt.ChoiceBlock([],"weh")
		with self.assertRaises(AttributeError):
			c.feedback = "wibble"
			
	def test_is_completed_readable(self):
		c = dt.ChoiceBlock([],None)
		c.is_completed
		
	def test_is_completed_not_writable(self):
		c = dt.ChoiceBlock([],None)
		with self.assertRaises(AttributeError):
			c.is_completed = True

	def setup_parse_methods(self):
		dt.FirstChoice.parse.side_effect = make_parse({"C":dt.FirstChoice("a","b","c","d","e")})
		dt.Choice.parse.side_effect = make_parse({"c":dt.Choice("a","b","c","d","e")})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("a")})
		dt.StarterLine.parse.side_effect = make_parse({"s":object()})
	
	mock_parse_methods = mock_statics(dt,"FirstChoice.parse","Choice.parse",
		"BlankLine.parse","FeedbackLine.parse","StarterLine.parse")
			
	@mock_parse_methods
	def test_parse_returns_populated_choiceblock(self):
		self.setup_parse_methods()
		c1 = dt.FirstChoice("a","b","c","d","wibble")
		c2 = dt.Choice("a","b","c","d","flibble")
		dt.FirstChoice.parse.side_effect = make_parse({"C":c1})
		dt.Choice.parse.side_effect = make_parse({"c":c2})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("blah"),"F":dt.FeedbackLine("yadda")})
		result = dt.ChoiceBlock.parse(MockInput("CfbFc$"))
		self.assertTrue( isinstance(result,dt.ChoiceBlock) )
		self.assertTrue( hasattr(result,"choices") )
		self.assertEquals( [c1,c2], result.choices )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals( "wibble blah yadda flibble", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.FirstChoice.parse.side_effect = make_parse({"C":dt.FirstChoice("a","b","c","d",None)})
		dt.Choice.parse.side_effect = make_parse({"c":dt.Choice("a","b","c","d",None)})
		result = dt.ChoiceBlock.parse(MockInput("Cc$"))
		self.assertIsNone( result.feedback )

	@mock_parse_methods		
	def test_parse_expects_firstchoice(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceBlock.parse(MockInput("c$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		self.assertFalse( dt.Choice.parse.called )
		self.assertFalse( dt.FeedbackLine.parse.called )

	@mock_parse_methods		  	
	def test_parse_allows_multiple_choices(self):
		self.setup_parse_methods()
		result = dt.ChoiceBlock.parse(MockInput("Cccc$"))
		self.assertIsNotNone( result )
		self.assertEquals(4, len(result.choices) )
		self.assertEquals(7, len(result.feedback) )

	@mock_parse_methods		
	def test_parse_allows_multiple_blanklines(self):
		self.setup_parse_methods()
		result = dt.ChoiceBlock.parse(MockInput("Cbbbc$"))
		self.assertIsNotNone( result )
		self.assertEquals(2, len(result.choices) )
		self.assertEquals(3, len(result.feedback) )
		  	
	@mock_parse_methods
	def test_parse_allows_multiple_feedbacklines(self):
		self.setup_parse_methods()
		result = dt.ChoiceBlock.parse(MockInput("Cfff$"))
		self.assertIsNotNone( result )
		self.assertEquals(1, len(result.choices) )
		self.assertEquals(7, len(result.feedback) )
		  	
	@mock_parse_methods
	def test_parse_checks_choice_before_feedbackline(self):
		self.setup_parse_methods()		
		dt.FeedbackLine.parse.side_effect = make_parse({"c":dt.FeedbackLine("a")})
		result = dt.ChoiceBlock.parse(MockInput("Cc$"))
		self.assertIsNotNone( result )
		self.assertEquals(2, len(result.choices) )
		self.assertEquals(3, len(result.feedback) )
		  	
	@mock_parse_methods
	def test_parse_checks_starterline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.StarterLine.parse.side_effect = make_parse({"f":object()})
		result = dt.ChoiceBlock.parse(MockInput("Cf$"))
		self.assertIsNotNone( result )
		self.assertEquals(1, len(result.choices) )
		self.assertEquals(1, len(result.feedback) )
		  	
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("Cbfcfb$")
		dt.ChoiceBlock.parse(i)
		self.assertEquals(6, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("c$")
		dt.ChoiceBlock.parse(i)
		self.assertEquals(0, i.pos)

	def test_is_completed_returns_true_for_mark(self):
		cb = dt.ChoiceBlock([
			dt.Choice(None,"a","b","c",None),
			dt.Choice("X","d","e","f",None)
		],None)
		self.assertEquals(True, cb.is_completed)
		
	def test_is_completed_returns_true_for_feedback(self):
		cb = dt.ChoiceBlock([
			dt.Choice(None,"a","b","c","great"),
			dt.Choice(None,"d","e","f",None)
		],"great")
		self.assertEquals(True, cb.is_completed)
		
	def test_is_completed_returns_false_for_no_marks_or_feedback(self):
		cb = dt.ChoiceBlock([
			dt.Choice(None,"a","b","c",None),
			dt.Choice(None,"d","e","f",None)
		],None)
		self.assertEquals(False, cb.is_completed)


class TestFirstChoice(unittest.TestCase):

	def test_construct(self):
		dt.FirstChoice("foo","bar","weh","blah","wibble")
		
	def test_mark_readable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		self.assertEquals("foo",c.mark)
		
	def test_mark_not_writable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.mark = "wibble"
			
	def test_description_readable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		self.assertEquals("bar",c.description)
		
	def test_description_not_writable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.description = "wibble"
			
	def test_response_readable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		self.assertEquals("weh",c.response)
		
	def test_response_not_writable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.response = "wibble"
		  	
	def test_goto_readable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		self.assertEquals("blah",c.goto)
		
	def test_goto_not_writable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.goto = "wibble"

	def test_feedback_readable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		self.assertEquals("wibble",c.feedback)

	def test_feedback_not_writable(self):
		c = dt.FirstChoice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.feedback = "blarg"

	def setup_parse_methods(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.FirstTextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"m":dt.ChoiceMarker("a")})
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("b","c","d","e")})
		  	
	mock_parse_methods = mock_statics(dt,"QuoteMarker.parse","FirstTextLineMarker.parse",
			"ChoiceMarker.parse","LineWhitespace.parse","ChoiceContent.parse")

	@mock_parse_methods		  	
	def test_parse_returns_populated_firstchoice(self):
		self.setup_parse_methods()
		dt.ChoiceMarker.parse.side_effect = make_parse({"m":dt.ChoiceMarker("foo")})
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("bar","weh","blah","wibble")})
		result = dt.FirstChoice.parse(MockInput("qtwmc$"))
		self.assertTrue( isinstance(result,dt.FirstChoice) )
		self.assertTrue( hasattr(result,"mark") )
		self.assertEquals( "foo", result.mark )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals( "bar", result.description )
		self.assertTrue( hasattr(result,"response") )
		self.assertEquals( "weh", result.response )
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals( "blah", result.goto )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals( "wibble", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("a","b","c",None)})
		result = dt.FirstChoice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_mark(self):
		self.setup_parse_methods()
		dt.ChoiceMarker.parse.side_effect = make_parse({"m":dt.ChoiceMarker(None)})
		result = dt.FirstChoice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.mark)
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_response(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("b",None,"d","e")})
		result = dt.FirstChoice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.response)
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_goto(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("b","c",None,"e")})
		result = dt.FirstChoice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.goto)
		
	@mock_parse_methods
	def test_parse_allows_no_quotemarker(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.FirstChoice.parse(MockInput("twmc$")) )

	@mock_parse_methods		
	def test_parse_expects_firsttextlinemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.FirstChoice.parse(MockInput("qwmc$")) )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		self.assertFalse( dt.ChoiceContent.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_linewhitespace_after_textlinemarker(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.FirstChoice.parse(MockInput("qtmc$")) )

	@mock_parse_methods		
	def test_parse_expects_choicemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.FirstChoice.parse(MockInput("qtwc$")) )
		self.assertFalse( dt.ChoiceContent.parse.called )

	@mock_parse_methods		
	def test_parse_expects_choicecontent(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.FirstChoice.parse(MockInput("qtwm$")) )

	@mock_parse_methods			
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("qtwmc$")
		dt.FirstChoice.parse(i)
		self.assertEquals(5,i.pos)
	
	@mock_parse_methods		
	def test_parse_consumes_no_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("qtwm$")
		dt.FirstChoice.parse(i)
		self.assertEquals(0,i.pos)
		
	def test_can_set_mark(self):
		c = dt.FirstChoice(None,"foo",None,None,None)
		self.assertEquals(None, c.mark)
		c.set_mark("blah")
		self.assertEquals("blah", c.mark)
		  	

class TestChoice(unittest.TestCase):

	def test_construct(self):
		dt.Choice("foo","bar","weh","blah","wibble")
		
	def test_mark_readable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		self.assertEquals("foo",c.mark)
		
	def test_mark_not_writable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.mark = "wibble"
			
	def test_description_readable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		self.assertEquals("bar",c.description)
		
	def test_description_not_writable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.description = "wibble"
			
	def test_response_readable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		self.assertEquals("weh",c.response)
		
	def test_response_not_writable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.response = "wibble"
			
	def test_goto_readable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		self.assertEquals("blah",c.goto)
		
	def test_goto_not_writable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.goto = "wibble"
			
	def test_feedback_readable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		self.assertEquals("wibble",c.feedback)
			
	def test_feedback_not_writable(self):
		c = dt.Choice("foo","bar","weh","blah","wibble")
		with self.assertRaises(AttributeError):
			c.feedback = "meh"
			
	def setup_parse_methods(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"t":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"m":dt.ChoiceMarker("a")})
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("b","c","d","e")})
			
	mock_parse_methods = mock_statics(dt,"QuoteMarker.parse","TextLineMarker.parse",
		"ChoiceMarker.parse", "LineWhitespace.parse","ChoiceContent.parse")
			
	@mock_parse_methods
	def test_parse_returns_populated_choice(self):
		self.setup_parse_methods()
		dt.ChoiceMarker.parse.side_effect = make_parse({"m":dt.ChoiceMarker("foo")})
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("bar","weh","blah","wibble")})
		result = dt.Choice.parse(MockInput("qtwmc$"))
		self.assertTrue( isinstance(result,dt.Choice) )
		self.assertTrue( hasattr(result,"mark") )
		self.assertEquals( "foo", result.mark )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals( "bar", result.description )
		self.assertTrue( hasattr(result,"response") )
		self.assertEquals( "weh", result.response )
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals( "blah", result.goto )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals( "wibble", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("a","b","c",None)})
		result = dt.Choice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_response(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("a",None,"c","d")})
		result = dt.Choice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.response)
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_goto(self):
		self.setup_parse_methods()
		dt.ChoiceContent.parse.side_effect = make_parse({"c":dt.ChoiceContent("a","b",None,"d")})
		result = dt.Choice.parse(MockInput("qtwmc$"))
		self.assertIsNone(result.goto)
		
	@mock_parse_methods
	def test_parse_allows_no_quotemarker(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.Choice.parse(MockInput("twmc$")) )
		
	@mock_parse_methods
	def test_parse_expects_textlinemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Choice.parse(MockInput("qwmc$")) )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		self.assertFalse( dt.ChoiceContent.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_linewhitespace_after_textlinemarker(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.Choice.parse(MockInput("qtmc$")) )
		
	@mock_parse_methods
	def test_parse_expects_choicemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Choice.parse(MockInput("qtwc$")) )
		self.assertFalse( dt.ChoiceContent.parse.called )
		
	@mock_parse_methods
	def test_parse_expects_choicecontent(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.Choice.parse(MockInput("qtwm$")) )
			
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("qtwmc$")
		dt.Choice.parse(i)
		self.assertEquals(5,i.pos)
		
	@mock_parse_methods
	def test_parse_consumes_no_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("qtwm$")
		dt.Choice.parse(i)
		self.assertEquals(0,i.pos)
		
	def test_can_set_mark(self):
		c = dt.Choice(None,"foo","bar","weh",None)
		self.assertEquals(None,c.mark)
		c.set_mark("lol")
		self.assertEquals("lol",c.mark)


class TestTextLineMarker(unittest.TestCase):

	def test_construct(self):
		dt.TextLineMarker()
		
	def test_parse_returns_textlinemarker(self):
		result = dt.TextLineMarker.parse(MockInput(":$"))
		self.assertTrue( isinstance(result,dt.TextLineMarker) )
		
	def test_parse_expects_colon(self):
		self.assertIsNone( dt.TextLineMarker.parse(MockInput("$")) )

	def test_parse_rejects_second_colon(self):
		self.assertIsNone( dt.TextLineMarker.parse(MockInput("::$")) )
		
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
		
	def test_mark_is_readable(self):
		m = dt.ChoiceMarker("foo")
		self.assertEquals("foo",m.mark)
		
	def test_mark_is_not_writable(self):
		m = dt.ChoiceMarker("foo")
		with self.assertRaises(AttributeError):
			m.mark = "bar"
			
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_returns_populated_choicemarker(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("foo")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		result = dt.ChoiceMarker.parse(MockInput("owtc"))
		self.assertTrue( isinstance(result,dt.ChoiceMarker) )
		self.assertTrue( hasattr(result,"mark") )
		self.assertEquals( "foo", result.mark )
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_expects_choicemarkeropen(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("wtc")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarkerMark.parse.called )
		self.assertFalse( dt.ChoiceMarkerClose.parse.called )
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_allows_no_linewhitespace(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("otc")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_allows_no_choicemarkermark(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNotNone( dt.ChoiceMarker.parse(MockInput("owc")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_expects_choicemarkerclose(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		self.assertIsNone( dt.ChoiceMarker.parse(MockInput("owt$")) )

	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_consumes_input_on_success(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
		dt.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
		i = MockInput("owtc")
		dt.ChoiceMarker.parse(i)
		self.assertEquals(4, i.pos)
		
	@mock_statics(dt,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
			"ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarkerMark.parse.side_effect = make_parse({"t":dt.ChoiceMarkerMark("a")})
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


class TestChoiceMarkerMark(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceMarkerMark("foo")
		
	def test_text_is_readable(self):
		c = dt.ChoiceMarkerMark("foo")
		self.assertEquals("foo", c.text)
		
	def test_text_is_not_writable(self):
		c = dt.ChoiceMarkerMark("foo")
		with self.assertRaises(AttributeError):
			c.text = "bar"
			
	def test_parse_returns_populated_choicemarkermark(self):
		result = dt.ChoiceMarkerMark.parse(MockInput("foo]"))
		self.assertTrue( isinstance(result,dt.ChoiceMarkerMark) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo", result.text)
		
	def test_parse_expects_non_right_square(self):
		self.assertIsNone( dt.ChoiceMarkerMark.parse(MockInput("]$")) )
		
	def test_parse_allows_multiple_non_right_square(self):
		self.assertIsNotNone( dt.ChoiceMarkerMark.parse(MockInput("a1%*>;@?]$")) )
		
	def text_parse_consumes_input_on_success(self):
		i = MockInput("foobar]$")
		dt.ChoiceMarkerMark.parse(i)
		self.assertEquals(6, i.pos)
		
	def text_parse_doesnt_consume_input_on_success(self):
		i = MockInput("]$")
		dt.ChoicemarkerMark.parse(i)
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
		dt.ChoiceDescription("foo bar","weh")
		
	def test_text_readable(self):
		d = dt.ChoiceDescription("foo bar","weh")
		self.assertEquals("foo bar",d.text)
	
	def test_parts_not_writable(self):
		d = dt.ChoiceDescription("foo bar","weh")
		with self.assertRaises(AttributeError):
			d.text = "weh"
			
	def test_feedback_readable(self):
		d = dt.ChoiceDescription("foo bar","weh")
		self.assertEquals("weh", d.feedback)
		
	def test_feedback_not_writable(self):
		d = dt.ChoiceDescription("foo bar","weh")
		with self.assertRaises(AttributeError):
			d.feedback = "blah"

	def setup_parse_methods(self):
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":dt.ChoiceDescPart("a")})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("b")})

	mock_parse_methods = mock_statics(dt,"ChoiceDescPart.parse","ChoiceDescNewline.parse")

	@mock_parse_methods
	def test_parse_returns_populated_choicedescription(self):
		self.setup_parse_methods()
		dt.ChoiceDescPart.parse.side_effect = make_parse({"p":dt.ChoiceDescPart("blah"),"d":dt.ChoiceDescPart("yadda"),"q":dt.ChoiceDescPart("weh")})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("foo"),"N":dt.ChoiceDescNewline("bar")})
		result = dt.ChoiceDescription.parse(MockInput("pndNq$"))
		self.assertTrue( isinstance(result,dt.ChoiceDescription) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("blah yadda weh", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("foo bar", result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline(None)})
		result = dt.ChoiceDescription.parse(MockInput("pnpnp$"))
		self.assertIsNone( result.feedback )

	@mock_parse_methods		
	def test_parse_expects_part(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceDescription.parse(MockInput("z$")) )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )
		self.assertFalse( dt.ChoiceDescNewline.parse.called )

	@mock_parse_methods		
	def test_parse_allows_single_part(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescription.parse(MockInput("p$")) )
		self.assertEquals( 1, dt.ChoiceDescPart.parse.call_count )

	@mock_parse_methods		
	def test_parse_expects_choicedescnewline_for_second_part(self):
		self.setup_parse_methods()
		result = dt.ChoiceDescription.parse(MockInput("pp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text))

	@mock_parse_methods
	def test_parse_expects_part_for_second_part(self):
		self.setup_parse_methods()
		result = dt.ChoiceDescription.parse(MockInput("pn$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text))

	@mock_parse_methods		
	def test_parse_allows_multiple_parts(self):
		self.setup_parse_methods()
		result = dt.ChoiceDescription.parse(MockInput("pnpnpnp$"))
		self.assertIsNotNone(result)
		self.assertEquals(7, len(result.text))

	@mock_parse_methods		
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("pnp$")
		dt.ChoiceDescription.parse(i)
		self.assertEquals(3, i.pos)

	@mock_parse_methods		
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
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
	
	def test_parse_trims_whitespace(self):
		result = dt.ChoiceDescPart.parse(MockInput("    foo  \x00"))
		self.assertEquals("foo",result.text)
	
	def test_parse_allows_single_hyphen(self):
		self.assertIsNotNone( dt.ChoiceDescPart.parse(MockInput("-\x00")) )
		
	def test_parse_doesnt_allow_double_hyphen(self):
		self.assertIsNone( dt.ChoiceDescPart.parse(MockInput("--\x00")) )
		
	def test_parse_allows_multiple_chars_numbers_and_punctuation(self):
		result = dt.ChoiceDescPart.parse(MockInput("a0b!7c%\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(7, len(result.text) )
		
	def test_parse_allows_spaces_and_tabs(self):
		result = dt.ChoiceDescPart.parse(MockInput(" \t \tT\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text) )
		
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
		dt.ChoiceResponse("foo","bar","weh")
	
	def test_description_readable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		self.assertEquals("foo", r.description)
		
	def test_description_not_writable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		with self.assertRaises(AttributeError):
			r.description = "weh"
			
	def test_goto_readable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		self.assertEquals("bar",r.goto)
		
	def test_goto_not_writable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		with self.assertRaises(AttributeError):
			r.goto = "weh"
			
	def test_feedback_readable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		self.assertEquals("weh",r.feedback)
		
	def test_feedback_not_writable(self):
		r = dt.ChoiceResponse("foo","bar","weh")
		with self.assertRaises(AttributeError):
			r.feedback = "wibble"
		
	def setup_parse_methods(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("z")})
		dt.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":dt.ChoiceResponseDesc("a","g")})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":dt.ChoiceGoto("b","c")})
		
	mock_parse_methods = mock_statics(dt,"ChoiceResponseSeparator.parse",
		"ChoiceDescNewline.parse","ChoiceResponseDesc.parse","ChoiceGoto.parse")

	@mock_parse_methods		
	def test_parse_returns_populated_choiceresponse(self):
		self.setup_parse_methods()
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":dt.ChoiceResponseDesc("foo","wibble")})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":dt.ChoiceGoto("bar","blarg")})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("jibber"),"N":dt.ChoiceDescNewline("jabber")})
		result = dt.ChoiceResponse.parse(MockInput("nsNdg$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponse) )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals("foo", result.description)
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals("bar", result.goto)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("jibber jabber wibble blarg", result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":dt.ChoiceResponseDesc("foo",None)})
		dt.ChoiceGoto.parse.side_effect = make_parse({"g":dt.ChoiceGoto("weh",None)})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline(None)})
		result = dt.ChoiceResponse.parse(MockInput("sndg$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_responsedesc(self):
		self.setup_parse_methods()
		result = dt.ChoiceResponse.parse(MockInput("sg$"))
		self.assertIsNone(result.description)
	
	@mock_parse_methods
	def test_parse_sets_none_for_empty_responsedesc(self):
		self.setup_parse_methods()
		dt.ChoiceResponseDesc.parse.side_effect = make_parse({"d":dt.ChoiceResponseDesc("",None)})
		result = dt.ChoiceResponse.parse(MockInput("sndg$"))
		self.assertIsNone(result.description)
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_goto(self):
		self.setup_parse_methods()
		result = dt.ChoiceResponse.parse(MockInput("snd$"))
		self.assertIsNone(result.goto)

	@mock_parse_methods		
	def test_parse_allows_no_first_choicedescnewline(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("sndg$")) )

	@mock_parse_methods		
	def test_parse_expects_choiceresponseseparator(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceResponse.parse(MockInput("n$")) )
		self.assertFalse( dt.ChoiceResponseDesc.parse.called )
		self.assertFalse( dt.ChoiceGoto.parse.called )

	@mock_parse_methods		
	def test_parse_allows_no_choicedescnewline_for_choiceresponsedesc(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsdg$")) )
	
	@mock_parse_methods	
	def test_parse_allows_choicegoto_and_no_choiceresponsedesc(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsg$")) )

	@mock_parse_methods		
	def test_parse_allows_choiceresponsedesc_and_no_choicegoto(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceResponse.parse(MockInput("nsnd$")) )

	@mock_parse_methods		
	def test_parse_expects_either_choiceresponsedesc_or_choicegoto(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceResponse.parse(MockInput("ns$")) )

	@mock_parse_methods		
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("nsndg$")
		dt.ChoiceResponse.parse(i)
		self.assertEquals(5, i.pos)

	@mock_parse_methods		
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
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
		dt.ChoiceResponseDesc("foo bar","weh")

	def test_text_readable(self):
		d = dt.ChoiceResponseDesc("foo bar","weh")
		self.assertEquals("foo bar", d.text)
		
	def test_text_not_writable(self):
		d = dt.ChoiceResponseDesc("foo bar","weh")
		with self.assertRaises(AttributeError):
			d.text = "weh"

	def test_feedback_readable(self):
		d = dt.ChoiceResponseDesc("foo bar","weh")
		self.assertEquals("weh",d.feedback)
		
	def test_feedback_not_writable(self):
		d = dt.ChoiceResponseDesc("foo bar","weh")
		with self.assertRaises(AttributeError):
			d.feedback = "blarg"

	def setup_parse_methods(self):
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":dt.ChoiceResponseDescPart("a")})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("b")})

	mock_parse_methods = mock_statics(dt,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")

	@mock_parse_methods
	def test_parse_returns_populated_choiceresponsedesc(self):
		self.setup_parse_methods()
		dt.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":dt.ChoiceResponseDescPart("blah"),"d":dt.ChoiceResponseDescPart("yadda"),"q":dt.ChoiceResponseDescPart("wibble")})
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline("weh"),"N":dt.ChoiceDescNewline("blarg")})
		result = dt.ChoiceResponseDesc.parse(MockInput("pndNq$"))
		self.assertTrue( isinstance(result,dt.ChoiceResponseDesc) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("blah yadda wibble", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("weh blarg", result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"n":dt.ChoiceDescNewline(None)})
		result = dt.ChoiceResponseDesc.parse(MockInput("pnp$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_expects_first_part(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceResponseDesc.parse(MockInput("z$")) )
		self.assertFalse( dt.ChoiceDescNewline.parse.called )

	@mock_parse_methods		
	def test_parse_expects_choicedescnewline_for_second_part(self):
		self.setup_parse_methods()
		result = dt.ChoiceResponseDesc.parse(MockInput("pp$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text))

	@mock_parse_methods		
	def test_parse_expects_part_for_second_part(self):
		self.setup_parse_methods()
		result = dt.ChoiceResponseDesc.parse(MockInput("pn$"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text))

	@mock_parse_methods		
	def test_parse_allows_multiple_parts(self):
		self.setup_parse_methods()
		result = dt.ChoiceResponseDesc.parse(MockInput("pnpnpnp$"))
		self.assertIsNotNone(result)
		self.assertEquals(7, len(result.text))

	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("pnp$")
		dt.ChoiceResponseDesc.parse(i)
		self.assertEquals(3, i.pos)

	@mock_parse_methods		
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
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

	def test_parse_trims_whitespace(self):
		result = dt.ChoiceResponseDescPart.parse(MockInput("    foo   \x00"))
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
		result = dt.ChoiceResponseDescPart.parse(MockInput(" \t \tT\x00"))
		self.assertIsNotNone(result)
		self.assertEquals(1, len(result.text))

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
		dt.ChoiceGoto("foo","wibble")
	
	def test_secname_readable(self):
		g = dt.ChoiceGoto("foo","wibble")
		self.assertEquals("foo",g.secname)
		
	def test_secname_not_writable(self):
		g = dt.ChoiceGoto("foo","wibble")
		with self.assertRaises(AttributeError):
			g.secname = "bar"
			
	def test_feedback_readable(self):	
		g = dt.ChoiceGoto("foo","wibble")
		self.assertEquals("wibble",g.feedback)
		
	def test_feedback_not_writable(self):
		g = dt.ChoiceGoto("foo","wibble")
		with self.assertRaises(AttributeError):
			g.feedback = "blarg"
			
	def setup_parse_methods(self):
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":dt.ChoiceDescNewline("a")})
		dt.GotoMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("a")})
		dt.EndPunctuation.parse.side_effect = make_parse({"e":object()})
		
	mock_parse_methods = mock_statics(dt,"GotoMarker.parse","LineWhitespace.parse",
			"Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
			
	@mock_parse_methods
	def test_parse_returns_choicegoto(self):
		self.setup_parse_methods()
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":dt.ChoiceDescNewline("jibber")})
		dt.Name.parse.side_effect = make_parse({"n":dt.Name("foobar")})
		result = dt.ChoiceGoto.parse(MockInput("lmwne$"))
		self.assertTrue( isinstance(result,dt.ChoiceGoto) )
		self.assertTrue( hasattr(result,"secname") )
		self.assertEquals( "foobar", result.secname )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals( "jibber", result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceDescNewline.parse.side_effect = make_parse({"l":dt.ChoiceDescNewline(None)})
		result = dt.ChoiceGoto.parse(MockInput("lmwne$"))
		self.assertIsNone(result.feedback)

	@mock_parse_methods
	def test_parse_allows_no_choicedescnewline(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("mwne$")) )

	@mock_parse_methods
	def test_parse_expects_gotomarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("lwne$")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.Name.parse.called )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_linewhitespace(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("lmne$")) )
		
	@mock_parse_methods
	def test_parse_expects_name(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceGoto.parse(MockInput("lmwe$")) )
		self.assertFalse( dt.EndPunctuation.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_endpunctuation(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceGoto.parse(MockInput("lmwn$")) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("lmwne$")
		dt.ChoiceGoto.parse(i)
		self.assertEquals(5,i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
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

	def setup_parse_methods(self):
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":dt.FirstInstructionLine("a")})
		dt.InstructionLine.parse.side_effect = make_parse({"i":dt.InstructionLine("b")})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("c")})
		dt.StarterLine.parse.side_effect = make_parse({"s":object()})

	mock_parse_methods = mock_statics(dt,"FirstInstructionLine.parse",
			"InstructionLine.parse","BlankLine.parse","FeedbackLine.parse",
			"StarterLine.parse")

	@mock_parse_methods
	def test_parse_returns_instructionblock(self):
		self.setup_parse_methods()
		l1 = dt.FirstInstructionLine("foo")
		l2 = dt.InstructionLine("bar")
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":l1})
		dt.InstructionLine.parse.side_effect = make_parse({"i":l2})
		f1 = dt.FeedbackLine("blah")
		f2 = dt.FeedbackLine("yadda")
		dt.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
		result = dt.InstructionBlock.parse(MockInput("IfbFi$"))
		self.assertTrue( isinstance(result,dt.InstructionBlock) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo bar", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah yadda", result.feedback)
				
	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		result = dt.InstructionBlock.parse(MockInput("I$"))
		self.assertIsNone( result.feedback )
			
	@mock_parse_methods
	def test_parse_expects_firstinstructionline(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.InstructionBlock.parse(MockInput("i$")) )
		self.assertFalse( dt.InstructionLine.parse.called )
		self.assertFalse( dt.BlankLine.parse.called )
		self.assertFalse( dt.FeedbackLine.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_multiple_instructionlines(self):
		self.setup_parse_methods()
		result =  dt.InstructionBlock.parse(MockInput("Iii$"))
		self.assertIsNotNone( result )
		self.assertEquals(5, len(result.text) )
		self.assertEquals(None, result.feedback)
			
	@mock_parse_methods
	def test_parse_allows_multiple_blank_lines(self):
		self.setup_parse_methods()
		result = dt.InstructionBlock.parse(MockInput("Ibbbi$"))
		self.assertIsNotNone( result )
		self.assertEquals(3,len(result.text))
		self.assertEquals(None,result.feedback)
		
	@mock_parse_methods
	def test_parse_allows_multiple_feedback_lines(self):
		self.setup_parse_methods()
		result = dt.InstructionBlock.parse(MockInput("Ifff$"))
		self.assertIsNotNone( result )
		self.assertEquals(1,len(result.text))
		self.assertEquals(5,len(result.feedback))
		
	@mock_parse_methods
	def test_parse_checks_instructionline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.FeedbackLine.parse.side_effect = make_parse({"i":dt.FeedbackLine("c")})
		result = dt.InstructionBlock.parse(MockInput("Ii$"))
		self.assertIsNotNone( result )
		self.assertEquals(3,len(result.text))
		self.assertEquals(None,result.feedback)
		
	@mock_parse_methods
	def test_parse_checks_starterline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.StarterLine.parse.side_effect = make_parse({"f":object()})
		result = dt.InstructionBlock.parse(MockInput("If$"))
		self.assertIsNotNone( result )
		self.assertEquals(1,len(result.text))
		self.assertEquals(None,result.feedback)
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("Ifbfib$")
		dt.InstructionBlock.parse(i)
		self.assertEquals(6,i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
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

	def test_parse_rejects_second_percent(self):
		self.assertIsNone( dt.InstructionLineMarker.parse(MockInput("%%$")) )
		
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
		self.assertEquals("foo", result.text)

	def test_parse_trims_whitespace(self):
		result = dt.LineText.parse(MockInput("   foo  \x00"))
		self.assertEquals("foo", result.text)
			
	def test_parse_expects_char(self):
		self.assertIsNone( dt.LineText.parse(MockInput("\x00")) )
		
	def test_parse_allows_multiple_alpha_number_or_punc_chars(self):
		result = dt.LineText.parse(MockInput("a7!f-G.\x00")) 
		self.assertIsNotNone( result )
		self.assertEquals( 7, len(result.text) )
		
	def test_parse_allows_space_and_tab(self):
		result = dt.LineText.parse(MockInput(" \t \tT\x00"))
		self.assertIsNotNone( result )
		self.assertEquals( 1, len(result.text) )
		
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
	
	def setup_parse_methods(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":dt.FirstTextLine("a")})
		dt.TextLine.parse.side_effect = make_parse({"t":dt.TextLine("b")})
		dt.BlankLine.parse.side_effect = make_parse({"b":dt.BlankLine()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("c")})
		dt.StarterLine.parse.side_effect = make_parse({"s":object()})
		
	mock_parse_methods = mock_statics(dt,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
			"FirstTextLine.parse","StarterLine.parse")
	
	@mock_parse_methods
	def test_parse_returns_populated_textblock(self):
		self.setup_parse_methods()
		t1 = dt.FirstTextLine("foo")
		t2 = dt.TextLine("bar")
		dt.FirstTextLine.parse.side_effect = make_parse({"t":t1})
		dt.TextLine.parse.side_effect = make_parse({"T":t2})
		f1 = dt.FeedbackLine("blah")
		f2 = dt.FeedbackLine("yadda")
		dt.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
		result = dt.TextBlock.parse(MockInput("tfbFT$"))
		self.assertTrue( isinstance(result,dt.TextBlock) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals("foo bar", result.text)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah yadda", result.feedback)	
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		result = dt.TextBlock.parse(MockInput("T$"))
		self.assertIsNone(result.feedback)
			
	@mock_parse_methods
	def test_parse_expects_firsttextline(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.TextBlock.parse(MockInput("t$")) )
		self.assertFalse( dt.BlankLine.parse.called )
		self.assertFalse( dt.TextLine.parse.called )
		self.assertFalse( dt.FeedbackLine.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_single_line(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.TextBlock.parse(MockInput("T$")) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_textlines(self):
		self.setup_parse_methods()
		result = dt.TextBlock.parse(MockInput("Ttt$"))
		self.assertIsNotNone( result )
		self.assertEquals(5, len(result.text) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_blanklines(self):
		self.setup_parse_methods()
		result = dt.TextBlock.parse(MockInput("Tbbbt$"))
		self.assertIsNotNone( result )
		self.assertEquals( 3, len(result.text) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_feedbacklines(self):
		self.setup_parse_methods()
		result = dt.TextBlock.parse(MockInput("Tfff$")) 
		self.assertIsNotNone( result )
		self.assertEquals( 5, len(result.feedback) )

	@mock_parse_methods
	def test_parse_checks_textline_before_feedbackline(self):
		self.setup_parse_methods()		
		dt.FeedbackLine.parse.side_effect = make_parse({"t":dt.FeedbackLine("a")})
		result = dt.TextBlock.parse(MockInput("Tt$")) 
		self.assertIsNotNone( result )
		self.assertEquals( 3, len(result.text) )
		self.assertEquals( None, result.feedback )
		
	@mock_parse_methods
	def test_parse_checks_starterline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.StarterLine.parse.side_effect = make_parse({"f":object()})
		result = dt.TextBlock.parse(MockInput("Tf$")) 
		self.assertIsNotNone( result )
		self.assertEquals( 1, len(result.text) )
		self.assertEquals( None, result.feedback )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("Ttf$")
		dt.TextBlock.parse(i)
		self.assertEquals(3,i.pos)
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
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
			
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_returns_populated_feedbackline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("foo")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		result = dt.FeedbackLine.parse(MockInput("qtl$"))
		self.assertTrue( isinstance(result,dt.FeedbackLine) )
		self.assertTrue( hasattr(result,"text") )
		self.assertEquals( "foo", result.text )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_allows_no_quotemarker(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNotNone( dt.FeedbackLine.parse(MockInput("tl$")) )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_expects_linetext(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("ql$")) )
		self.assertFalse( dt.Newline.parse.called )

	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_expects_newline(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		self.assertIsNone( dt.FeedbackLine.parse(MockInput("qt$")) )
	
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_consumes_input_on_success(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qtl$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(3, i.pos)
		
	@mock_statics(dt,"QuoteMarker.parse","LineText.parse","Newline.parse")
	def test_parse_doesnt_consume_input_on_failure(self):
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.LineText.parse.side_effect = make_parse({"t":dt.LineText("a")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		i = MockInput("qt$")
		dt.FeedbackLine.parse(i)
		self.assertEquals(0, i.pos)


class TestChoiceDescNewline(unittest.TestCase):

	def test_construct(self):
		dt.ChoiceDescNewline("foo")
		
	def test_feedback_readable(self):
		n = dt.ChoiceDescNewline("foo")
		self.assertEquals("foo",n.feedback)
		
	def test_feedback_not_writable(self):
		n = dt.ChoiceDescNewline("foo")
		with self.assertRaises(AttributeError):
			n.feedback = "weh"
		
	mock_parse_methods = mock_statics(dt,"Newline.parse","QuoteMarker.parse",
		"TextLineMarker.parse","LineWhitespace.parse","ChoiceMarker.parse",
		"BlankLine.parse","StarterLine.parse","TextLine.parse","FeedbackLine.parse")
		
	def setup_parse_methods(self):
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		dt.QuoteMarker.parse.side_effect = make_parse({"q":object()})
		dt.TextLineMarker.parse.side_effect = make_parse({"m":object()})
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
		dt.BlankLine.parse.side_effect = make_parse({"b":object()})
		dt.StarterLine.parse.side_effect = make_parse({"s":object()})
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("a")})

	@mock_parse_methods		
	def test_parse_returns_populated_choicedescnewline(self):
		self.setup_parse_methods()
		dt.FeedbackLine.parse.side_effect = make_parse({"f":dt.FeedbackLine("foo"),"F":dt.FeedbackLine("bar")})
		result = dt.ChoiceDescNewline.parse(MockInput("lfbFqmw$"))
		self.assertTrue( isinstance(result,dt.ChoiceDescNewline) )
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("foo bar",result.feedback)
	
	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		result = dt.ChoiceDescNewline.parse(MockInput("lbqmw$"))
		self.assertIsNone(result.feedback)
	
	@mock_parse_methods
	def test_parse_expects_newline(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("bfqmw$")) )
		self.assertFalse( dt.QuoteMarker.parse.called )
		self.assertFalse( dt.TextLineMarker.parse.called )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_blanklines_or_feedbacklines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lqmw$")) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_blanklines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lbbbqmw$")) )
		
	@mock_parse_methods
	def test_parse_allows_multiple_feedbacklines(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lfffqmw$")) )
		
	@mock_parse_methods
	def test_parse_checks_starterline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.StarterLine.parse.side_effect = make_parse({"f":object()})
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lfqmw$")) )
		
	def test_parse_checks_textline_before_feedbackline(self):
		self.setup_parse_methods()
		dt.TextLine.parse_side_effect = make_parse({"f":object()})
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lfqmw$")) )
		
	@mock_parse_methods
	def test_parse_allows_no_quotemarker(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lbfmw$")) )
		
	@mock_parse_methods
	def test_parse_expects_textlinemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lbfqw$")) )
		self.assertFalse( dt.LineWhitespace.parse.called )
		self.assertFalse( dt.ChoiceMarker.parse.called )
		
	@mock_parse_methods
	def test_parse_allows_no_linewhitespace(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceDescNewline.parse(MockInput("lbfqm$")) )
		
	@mock_parse_methods
	def test_parse_rejects_choicemarker(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceDescNewline.parse(MockInput("lbfqmwc$")) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("lbfqmw$")
		dt.ChoiceDescNewline.parse(i)
		self.assertEquals(6, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("lbfqmwc$")
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


class TestChoiceContent(unittest.TestCase):
		
	def test_construct(self):
		dt.ChoiceContent("foo","bar","weh","wibble")
		
	def test_description_readable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		self.assertEquals("foo",c.description)
		
	def test_description_not_writable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		with self.assertRaises(AttributeError):
			c.description = "wibble"
			
	def test_response_readable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		self.assertEquals("bar",c.response)
		
	def test_response_not_writable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		with self.assertRaises(AttributeError):
			c.response = "wibble"
			
	def test_goto_readable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		self.assertEquals("weh",c.goto)
		
	def test_goto_not_writable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		with self.assertRaises(AttributeError):
			c.goto = "wibble"
			
	def test_feedback_readable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		self.assertEquals("wibble",c.feedback)
		
	def test_feedback_not_writable(self):
		c = dt.ChoiceContent("foo","bar","weh","wibble")
		with self.assertRaises(AttributeError):
			c.feedback = "blarg"
		
	def setup_parse_methods(self):
		dt.LineWhitespace.parse.side_effect = make_parse({"w":object()})
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":dt.ChoiceDescription("a","z")})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":dt.ChoiceResponse("b","y","f")})
		dt.Newline.parse.side_effect = make_parse({"l":object()})
		
	mock_parse_methods = mock_statics(dt,"LineWhitespace.parse","ChoiceDescription.parse",
		"ChoiceResponse.parse","Newline.parse")

	@mock_parse_methods		
	def test_parse_returns_populated_choicecontent(self):
		self.setup_parse_methods()
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":dt.ChoiceDescription("foo","blah")})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":dt.ChoiceResponse("bar","weh","wibble")})
		result = dt.ChoiceContent.parse(MockInput("wdrl$"))
		self.assertTrue( isinstance(result,dt.ChoiceContent) )
		self.assertTrue( hasattr(result,"description") )
		self.assertEquals("foo",result.description)
		self.assertTrue( hasattr(result,"response") )
		self.assertEquals("bar",result.response)
		self.assertTrue( hasattr(result,"goto") )
		self.assertEquals("weh",result.goto)
		self.assertTrue( hasattr(result,"feedback") )
		self.assertEquals("blah wibble",result.feedback)

	@mock_parse_methods
	def test_parse_sets_none_for_no_feedback(self):
		self.setup_parse_methods()
		dt.ChoiceDescription.parse.side_effect = make_parse({"d":dt.ChoiceDescription("foo",None)})
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":dt.ChoiceResponse("weh","flibble",None)})
		result = dt.ChoiceContent.parse(MockInput("wdrl$"))
		self.assertIsNone( result.feedback )

	@mock_parse_methods
	def test_parse_sets_none_for_no_response(self):
		self.setup_parse_methods()
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":dt.ChoiceResponse(None,"b","c")})
		result = dt.ChoiceContent.parse(MockInput("wdrl$"))
		self.assertIsNone( result.response )
		
	@mock_parse_methods
	def test_parse_sets_none_for_no_goto(self):
		self.setup_parse_methods()
		dt.ChoiceResponse.parse.side_effect = make_parse({"r":dt.ChoiceResponse("a",None,"b")})
		result = dt.ChoiceContent.parse(MockInput("wdrl$"))
		self.assertIsNone( result.goto )

	@mock_parse_methods		
	def test_parse_allows_no_linewhitespace(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceContent.parse(MockInput("drl$")) )

	@mock_parse_methods		
	def test_parse_expects_choicedescription(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceContent.parse(MockInput("wrl$")) )
		self.assertFalse( dt.ChoiceResponse.parse.called )
		self.assertFalse( dt.Newline.parse.called )

	@mock_parse_methods		
	def test_parse_allows_no_choiceresponse(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.ChoiceContent.parse(MockInput("wdl$")) )
		
	@mock_parse_methods
	def test_parse_expects_newline(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.ChoiceContent.parse(MockInput("wdr$")) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("wdrl$")
		dt.ChoiceContent.parse(i)
		self.assertEquals(4,i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("wdr$")
		dt.ChoiceContent.parse(i)
		self.assertEquals(0,i.pos)


class TestStarterLine(unittest.TestCase):

	def test_construct(self):
		dt.StarterLine("foo")
	
	def test_line_readable(self):
		l = dt.StarterLine("foo")
		self.assertEquals("foo",l.line)
		
	def test_line_not_writable(self):
		l = dt.StarterLine("foo")
		with self.assertRaises(AttributeError):
			l.line = "bar"
	
	def setup_parse_methods(self):
		dt.FirstTextLine.parse.side_effect = make_parse({"T":object()})
		dt.FirstInstructionLine.parse.side_effect = make_parse({"I":object()})
		dt.FirstChoice.parse.side_effect = make_parse({"C":object()})
		dt.Heading.parse.side_effect = make_parse({"h":object()})
		
	mock_parse_methods = mock_statics(dt,"FirstTextLine.parse",
		"FirstInstructionLine.parse","FirstChoice.parse","Heading.parse")

	@mock_parse_methods		
	def test_parse_returns_populated_starterline(self):
		self.setup_parse_methods()
		t = object()
		dt.FirstTextLine.parse.side_effect = make_parse({"T":t})
		result = dt.StarterLine.parse(MockInput("T$"))
		self.assertTrue( isinstance(result,dt.StarterLine) )
		self.assertTrue( hasattr(result,"line") )
		self.assertEquals(t, result.line)

	@mock_parse_methods	
	def test_parse_expects_line(self):
		self.setup_parse_methods()
		self.assertIsNone( dt.StarterLine.parse(MockInput("$")) )
		
	@mock_parse_methods
	def test_parse_allows_firstinstructionline(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.StarterLine.parse(MockInput("I$")) )
		
	@mock_parse_methods
	def test_parse_allows_firstchoice(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.StarterLine.parse(MockInput("C$")) )
		
	@mock_parse_methods
	def test_parse_allows_heading(self):
		self.setup_parse_methods()
		self.assertIsNotNone( dt.StarterLine.parse(MockInput("h$")) )
		
	@mock_parse_methods
	def test_parse_rejects_non_starter(self):
		self.setup_parse_methods()
		dt.TextLine.parse.side_effect = make_parse({"t":object()})
		self.assertIsNone( dt.StarterLine.parse(MockInput("t$")) )
		
	@mock_parse_methods
	def test_parse_consumes_input_on_success(self):
		self.setup_parse_methods()
		i = MockInput("T$")
		dt.StarterLine.parse(i)
		self.assertEquals(1, i.pos)
		
	@mock_parse_methods
	def test_parse_doesnt_consume_input_on_failure(self):
		self.setup_parse_methods()
		i = MockInput("t$")
		dt.StarterLine.parse(i)
		self.assertEquals(0, i.pos)


class TestJsonIO(unittest.TestCase):

	def test_has_extensions(self):
		dt.JsonIO.EXTENSIONS[0]

	def test_write_doesnt_throw_error(self):
		s = io.BytesIO()
		dt.JsonIO.write(dt.Document([]),s)
		
	def test_write_handles_document(self):
		s = io.BytesIO()
		dt.JsonIO.write(dt.Document([]),s)
		self.assertEquals('[]', s.getvalue())
		
	def test_write_handles_firstsection(self):
		s = io.BytesIO()
		dt.JsonIO.write( dt.Document([dt.FirstSection([],"foo")]),s )
		self.assertEquals('[{"blocks": [], "feedback": "foo"}]', s.getvalue())
	
	def test_write_handles_section(self):
		s = io.BytesIO()
		dt.JsonIO.write(dt.Document([dt.Section("bar",[],"foo")]),s ) 
		self.assertEquals('[{"blocks": [], "name": "bar", "feedback": "foo"}]',
			s.getvalue())

	def test_write_handles_textblock(self):
		s = io.BytesIO()
		dt.JsonIO.write(dt.Document([dt.FirstSection([dt.TextBlock("blah","yadda")],"")]),s ) 
		self.assertEquals(
			'[{"blocks": [{"content": "blah", "type": "text"}], "feedback": ""}]',
			s.getvalue() )
				
	def test_write_handles_instructionblock(self):
		s = io.BytesIO()
		dt.JsonIO.write(
				dt.Document([dt.FirstSection([dt.InstructionBlock("wibble","flibble")],"")]),s )
		self.assertEquals(
			'[{"blocks": [{"content": "wibble", "type": "instructions"}], "feedback": ""}]',
			 s.getvalue())
	
	def test_write_handles_choiceblock(self):
		s = io.BytesIO()
		dt.JsonIO.write(
				dt.Document([dt.FirstSection([dt.ChoiceBlock([],"weh")],"")]),s )
		self.assertEquals(
			'[{"blocks": [{"content": [], "type": "choices", "feedback": "weh"}], "feedback": ""}]',
			 s.getvalue())
				
	def test_write_handles_choice(self):
		s = io.BytesIO()
		dt.JsonIO.write(
			dt.Document([dt.FirstSection([dt.ChoiceBlock([
				dt.Choice("X","33","ok","home","great") ],"great")],"great")]), s ) 
		self.assertEquals(
			'[{"blocks": [{"content": ['
			+'{"response": "ok", "goto": "home", "description": "33", "mark": "X"}'
			+'], "type": "choices", "feedback": "great"}], "feedback": "great"}]',
			s.getvalue() )
					
					
class TestDecTreeIO(unittest.TestCase):

	def test_has_extensions(self):
		dt.DecTreeIO.EXTENSIONS[0]
		
	def test_write_doesnt_throw_error(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([]),s)
		
	def test_write_handles_document(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([]),s)
		self.assertEquals("", s.getvalue())
		
	def test_write_handles_firstsection(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([],"this is fab") ]), s )
		self.assertEquals("\nthis is fab\n", s.getvalue())
			
	def test_write_handles_firstsection_feedback_wrap(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
				dt.FirstSection([],"This is a test to test line wrapping "
				+"and see if long lines are wrapped at some point") ]), s)
		self.assertEquals("\nThis is a test to test line wrapping and see "
			+"if long lines are wrapped at some\npoint\n",
			s.getvalue() )
			
	def test_write_handles_section(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
				dt.Section("My Section",[],"excellent stuff") ]), s)
		self.assertEquals("== My Section ==\n\n\nexcellent stuff\n", 
			s.getvalue() )
				
	def test_write_handles_section_feedback_wrap(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.Section("dave",[],"This is a test to test line wrapping "
			+"and see if long lines are wrapped at some point") ]), s)
		self.assertEquals("== dave ==\n\n\nThis is a test to test line wrapping and see "
			+"if long lines are wrapped at some\npoint\n",
			s.getvalue())
				
	def test_write_handles_textblock(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("This is a test",None) ],None) ]), s)
		self.assertEquals(":: This is a test\n", s.getvalue())

	def test_write_handles_textblock_line_wrap(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
				dt.FirstSection([ dt.TextBlock("This is a test to test line "
					+"wrapping and see if long lines are wrapped at some "
					+"point", None) ],None) ]), s)
		self.assertEquals(":: This is a test to test line wrapping and see "
			+"if long lines are wrapped at\n:  some point\n",
			s.getvalue())

	def test_formt_handles_firstsection_multiple_blocks(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals(":: Testing\n\n:: More testing\n",
			s.getvalue())
		
	def test_write_handles_section_multiple_blocks(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals("== dave ==\n\n:: Testing\n\n:: More testing\n",
			s.getvalue())
				
	def test_write_handles_firstsection_block_and_feedback(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals(":: Test\n\nBlah blah\n", s.getvalue())
				
	def test_write_handles_section_block_and_feedback(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals("== dave ==\n\n:: Test\n\nBlah blah\n", s.getvalue() )

	def test_write_handles_instructionblock(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock("This is a test",None) ],None) ]), s)
		self.assertEquals("%% This is a test\n", s.getvalue() )

	def test_write_handles_instructionblock_line_wrap(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock("This is a test to test line "
				+"wrapping and see if long lines are wrapped at some "
				+"point", None) ],None) ]), s)
		self.assertEquals("%% This is a test to test line wrapping and see "
			+"if long lines are wrapped at\n%  some point\n",
			s.getvalue())

	def test_write_handles_choiceblock(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([], "This is a test") ],None)]), s)
		self.assertEquals("\nThis is a test\n", s.getvalue())

	def test_write_handles_choiceblock_feedback_wrap(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([], "This is a test to see if "
				+"long lines are wrapped at some point by the line wrapping "
				+"thingy") ],None) ]), s)
		self.assertEquals("\nThis is a test to see if long lines are wrapped "
			+"at some point by the line\nwrapping thingy\n",
			s.getvalue())

	def test_write_handles_choice(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda","wibble",None)
			],None) ],None) ]), s)
		self.assertEquals(":: [X] blah blah\n:      -- yadda yadda\n"
				+":      GO TO wibble\n", s.getvalue())

	def test_write_handles_choice_no_mark(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"blah blah","yadda yadda","wibble",None)
			],None) ],None) ]), s)
		self.assertEqual(":: [] blah blah\n:      -- yadda yadda\n"
				+":      GO TO wibble\n", s.getvalue() )

	def test_write_handles_choice_no_response(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,"wibble",None)
			],None) ],None) ]), s)
		self.assertEqual(":: [X] blah blah\n:      -- GO TO wibble\n",
			s.getvalue())
				
	def test_write_handles_choice_no_goto(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda",None,None)
			],None) ],None) ]), s)
		self.assertEquals(":: [X] blah blah\n:      -- yadda yadda\n",
			s.getvalue())
				
	def test_write_handles_choice_no_response_or_goto(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,None,None)
			],None) ],None) ]), s)
		self.assertEquals(":: [X] blah blah\n", s.getvalue())

	def test_write_handles_choice_wrapped_description(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","This is a test to test long lines of text "
					+"are wrapped properly onto the next line, okay?",
					"yadda yadda","wibble",None) ],None) ],None)]), s)
		self.assertEquals(":: [X] This is a test to test long lines of text are "
			+"wrapped properly onto the\n:  next line, okay?\n"
			+":      -- yadda yadda\n:      GO TO wibble\n",
			s.getvalue())

	def test_write_handles_choice_wrapped_response(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah","This is a test to test long lines of text "
					+"are wrapped properly onto the next line, okay?",
					"wibble",None) ],None) ],None)]), s)
		self.assertEquals(":: [X] blah\n:      -- This is a test to test long lines of "
			+"text are wrapped properly onto\n:  the next line, okay?"
			+"\n:      GO TO wibble\n", s.getvalue())

	def test_write_handles_choiceblock_multiple_choices(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
				dt.FirstSection([ dt.ChoiceBlock([
					dt.Choice("X","foo","bar","wibble",None),
					dt.Choice("Y","weh","meh","yadda",None)
				],None) ],None) ]), s)
		self.assertEquals(":: [X] foo\n:      -- bar\n:      GO TO wibble\n"
			+":  [Y] weh\n:      -- meh\n:      GO TO yadda\n",
			s.getvalue())

	def test_write_handles_multiple_sections(self):
		s = io.BytesIO()
		dt.DecTreeIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("foo",None) ],None),
			dt.Section("dave",[ dt.TextBlock("bar",None) ],None) ]), s)
		self.assertEquals(":: foo\n\n== dave ==\n\n:: bar\n", s.getvalue())

	@mock_statics(dt,"Document.parse")
	def test_read_invokes_parse_with_input_obj(self):
		s = io.BytesIO("test")
		dt.DecTreeIO.read(s)
		self.assertTrue( dt.Document.parse.called )
		self.assertEquals( 1, len(dt.Document.parse.call_args_list) )
		self.assertEquals( 0, len(dt.Document.parse.call_args[1]) )
		self.assertEquals( 1, len(dt.Document.parse.call_args[0]) )
		self.assertTrue( isinstance(dt.Document.parse.call_args[0][0], dt.Input) )

	@mock_statics(dt,"Document.parse")
	def test_read_constructs_input_with_stream_contents(self):
		s = io.BytesIO("test")
		dt.DecTreeIO.read(s)
		i = dt.Document.parse.call_args[0][0]
		self.assertEquals( "test\x00", i._data )

	@mock_statics(dt,"Document.parse")
	def test_read_returns_parse_result(self):
		m = mock.Mock()
		dt.Document.parse.return_value = m
		s = io.BytesIO("test")
		self.assertEquals(m, dt.DecTreeIO.read(s) )
		
	@mock_statics(dt,"Document.parse")
	def test_read_throws_inputerror_for_parse_error(self):
		dt.Document.parse.return_value = None
		s = io.BytesIO("test")
		with self.assertRaises(dt.InputError):
			dt.DecTreeIO.read(s)
	

class TestWrapText(unittest.TestCase):

	def test_creates_line(self):
		self.assertEquals(["foo"],dt.wrap_text("foo",999))
		
	def test_spaces_words(self):
		self.assertEquals(["foo bar"],dt.wrap_text("foo bar",999))
		
	def test_condenses_space(self):
		self.assertEquals(["foo bar"],dt.wrap_text("foo    bar",999))
		
	def test_wraps_at_line_length(self):
		self.assertEquals(["cat sat","mat"],dt.wrap_text("cat sat mat",10))
		
	def test_allows_exact_line_length(self):
		self.assertEquals(["cat sat on","mat"],dt.wrap_text("cat sat on mat",10))
		
	def test_breaks_words_longer_than_line(self):
		self.assertEquals(["catsatonma","t"],dt.wrap_text("catsatonmat",10))
		
	def test_puts_broken_word_on_end_of_line(self):
		self.assertEquals(["the catsat","onmat"],dt.wrap_text("the catsatonmat",10))
		
	def test_breaks_long_words_multiple_times(self):
		self.assertEquals(["catsatonma","tandthenwe","nttoshops"],
			dt.wrap_text("catsatonmatandthenwenttoshops",10))
			
	def test_uses_start_parameter(self):
		self.assertEquals(["the","cat sat on","the mat"],
			dt.wrap_text("the cat sat on the mat",10,5))
			
	def test_uses_start_param_for_long_word_break(self):
		self.assertEquals(["theca","tsatonthem","atthenwent","toshops"],
			dt.wrap_text("thecatsatonthematthenwenttoshops",10,5))
			
	def test_returns_no_lines_for_no_text(self):
		self.assertEquals([],dt.wrap_text("",10))


class TestCommandLineRunner(unittest.TestCase):

	def setUp(self):
		self.r = dt.CommandLineRunner()
		self.i = io.BytesIO()
		self.o = io.BytesIO()

	def do_run(self,doc,input):
		i = io.BytesIO(input)
		o = io.BytesIO()
		dt.CommandLineRunner()._run(doc,i,o)
		return o.getvalue()

	def test_can_run(self):
		self.do_run( dt.Document([]), "" )
	
	def test_prints_textblock(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([
				dt.TextBlock("This is a test",None)
			],None) ]), "" )
		self.assertEquals("This is a test\n\n[enter]\n\n", result)

	def test_invokes_readline_after_printing_textblock(self):
		log = []
		def record(text): log.append(text)
		i = mock.Mock()
		i.readline.side_effect = lambda: record("readline")
		o = mock.Mock()
		o.write.side_effect = lambda s: record("write %s" % s)
		d = dt.Document([ dt.FirstSection([ dt.TextBlock("Foobar",None) ],None) ])
		dt.CommandLineRunner()._run(d,i,o)
		self.assertEquals(["write Foobar\n\n","write [enter]","readline","write \n\n"],log)

	def test_doesnt_print_instructionblock(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([
				dt.InstructionBlock("This is a test",None)
			],None) ]), "" )
		self.assertEquals("",result)
		
	def test_prints_choiceblock(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha",None,None,None),
				dt.Choice(None,"beta",None,None,None)
			],None) ],None) ]), "1\n" )
		self.assertEquals("1) alpha\n2) beta\n\n> \n\n", result)

	def test_validates_choice_selection_too_low(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha",None,None,None),
				dt.Choice(None,"beta",None,None,None)
			],None) ],None) ]), "0\n1\n" )
		self.assertEquals("1) alpha\n2) beta\n\n> \n\n"
			+"Invalid choice\n\n> \n\n", result)

	def test_validates_choice_selection_too_high(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha",None,None,None),
				dt.Choice(None,"beta",None,None,None)
			],None) ],None) ]), "3\n1\n" )
		self.assertEquals("1) alpha\n2) beta\n\n> \n\n"
			+"Invalid choice\n\n> \n\n", result)

	def test_validates_choice_selection_non_numeric(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha",None,None,None),
				dt.Choice(None,"beta",None,None,None)
			],None) ],None) ]), "foo\n1\n" )
		self.assertEquals("1) alpha\n2) beta\n\n> \n\n"
			+"Enter a number\n\n> \n\n", result)

	def test_prints_choice_response(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha","Where on earth",None,None),
				dt.Choice(None,"beta","is Carmen Sandiego",None,None)
			],None) ],None) ]), "2\n" )
		self.assertEquals("1) alpha\n2) beta\n\n> \n\n"
			+"is Carmen Sandiego\n\n", result)

	def test_follows_goto_forwards(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"foo",None,"flibble",None)
			],None), ],None),
			dt.Section("flibble",[],None) ]), "1\n" )
	
	def test_prints_section_title(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"foo",None,"kittens",None)
			],None) ],None),
			dt.Section("KiTTenS",[],None) ]),"1\n" )
		self.assertEquals("1) foo\n\n> \n\nKiTTenS\n-------\n\n", result)
		
	def test_follows_gotos_backwards(self):
		result = self.do_run( dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"alpha",None,"blarg",None),
			],None) ],None),
			dt.Section("foobar",[ dt.ChoiceBlock([
				dt.Choice(None,"apple",None,"blarg",None),
			],None) ],None),
			dt.Section("blarg",[ dt.ChoiceBlock([
				dt.Choice(None,"aberdeen",None,"foobar",None),
				dt.Choice(None,"birmingham",None,None,None),
			],None) ],None) ]), "1\n1\n1\n2\n" )
		self.assertEquals("1) alpha\n\n> "
			+"\n\nblarg\n-----\n\n1) aberdeen\n2) birmingham\n\n> "
			+"\n\nfoobar\n------\n\n1) apple\n\n> "
			+"\n\nblarg\n-----\n\n1) aberdeen\n2) birmingham\n\n> \n\n", result)
			
	def test_records_selected_choice_in_document(self):
		d = dt.Document([ dt.FirstSection([ dt.ChoiceBlock([
			dt.Choice(None,"foo",None,None,None),
			dt.Choice(None,"bar",None,None,None) ],None) ],None) ])
		self.assertEquals(None,d.sections[0].items[0].choices[0].mark)
		self.assertEquals(None,d.sections[0].items[0].choices[1].mark)
		self.do_run(d,"2\n")
		self.assertEquals(None,d.sections[0].items[0].choices[0].mark)
		self.assertEquals("X",d.sections[0].items[0].choices[1].mark)
		
	def test_overwrites_existing_selected_choice_in_document(self):
		d = dt.Document([ dt.FirstSection([ dt.ChoiceBlock([
			dt.Choice("X","foo",None,None,None),
			dt.Choice(None,"bar",None,None,None) ],None) ],None) ])
		self.assertEquals("X",d.sections[0].items[0].choices[0].mark)
		self.assertEquals(None,d.sections[0].items[0].choices[1].mark)
		self.do_run(d,"2\n")
		self.assertEquals(None,d.sections[0].items[0].choices[0].mark)
		self.assertEquals("X",d.sections[0].items[0].choices[1].mark)
		
		
class TestMarkdownIO(unittest.TestCase):
	
	def test_has_extensions(self):
		dt.MarkdownIO.EXTENSIONS[0]
		
	def test_write_doesnt_throw_error(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([]),s)
		
	def test_write_handles_document(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([]),s)
		self.assertEquals("", s.getvalue())
		
	def test_write_handles_firstsection(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([],"this is fab") ]), s )
		self.assertEquals("\n> this is fab\n", s.getvalue())
			
	def test_write_handles_firstsection_feedback_wrap(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
				dt.FirstSection([],"This is a test to test line wrapping "
				+"and see if long lines are wrapped at some point") ]), s)
		self.assertEquals("\n> This is a test to test line wrapping and see "
			+"if long lines are wrapped at\n> some point\n",
			s.getvalue() )
			
	def test_write_handles_section(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
				dt.Section("My Section",[],"excellent stuff") ]), s)
		self.assertEquals("My Section\n----------\n\n\n> excellent stuff\n", 
			s.getvalue() )
				
	def test_write_handles_section_feedback_wrap(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.Section("dave",[],"This is a test to test line wrapping "
			+"and see if long lines are wrapped at some point") ]), s)
		self.assertEquals("dave\n----\n\n\n> This is a test to test line wrapping and see "
			+"if long lines are wrapped at\n> some point\n",
			s.getvalue())
				
	def test_write_handles_textblock(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("This is a test",None) ],None) ]), s)
		self.assertEquals("This is a test\n", s.getvalue())

	def test_write_handles_textblock_line_wrap(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
				dt.FirstSection([ dt.TextBlock("This is a test to test line "
					+"wrapping and see if long lines are wrapped at some "
					+"point", None) ],None) ]), s)
		self.assertEquals("This is a test to test line wrapping and see "
			+"if long lines are wrapped at some\npoint\n",
			s.getvalue())

	def test_formt_handles_firstsection_multiple_blocks(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals("Testing\n\nMore testing\n",
			s.getvalue())
		
	def test_write_handles_section_multiple_blocks(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals("dave\n----\n\nTesting\n\nMore testing\n",
			s.getvalue())
				
	def test_write_handles_firstsection_block_and_feedback(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals("Test\n\n> Blah blah\n", s.getvalue())
				
	def test_write_handles_section_block_and_feedback(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals("dave\n----\n\nTest\n\n> Blah blah\n", s.getvalue() )

	def test_write_handles_instructionblock(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock("This is a test",None) ],None) ]), s)
		self.assertEquals("<!-- This is a test -->\n", s.getvalue() )

	def test_write_doesnt_print_double_dash_in_comments(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock("This is a -- test",None) ],None) ]), s)
		self.assertEquals("<!-- This is a test -->\n", s.getvalue() )

	def test_write_handles_instructionblock_line_wrap(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock("This is a test to test line "
				+"wrapping and see if long lines are wrapped at some "
				+"point", None) ],None) ]), s)
		self.assertEquals("<!-- This is a test to test line wrapping and see "
			+"if long lines are wrapped at\nsome point -->\n",
			s.getvalue())

	def test_write_handles_choiceblock(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([], "This is a test") ],None)]), s)
		self.assertEquals("\n> This is a test\n", s.getvalue())

	def test_write_handles_choiceblock_feedback_wrap(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([], "This is a test to see if "
				+"long lines are wrapped at some point by the line wrapping "
				+"thingy") ],None) ]), s)
		self.assertEquals("\n> This is a test to see if long lines are wrapped "
			+"at some point by the line\n> wrapping thingy\n",
			s.getvalue())

	def test_write_handles_choice(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda","wibble",None)
			],None) ],None) ]), s)
		self.assertEquals("- **[X] [blah blah](#wibble)** _yadda yadda_\n", s.getvalue())

	def test_write_formats_goto_link(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda","99 Bottles of Beer",None)
			],None) ],None) ]), s)
		self.assertEquals("- **[X] [blah blah](#bottles-of-beer)** _yadda yadda_\n", s.getvalue())

	def test_write_handles_choice_no_mark(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"blah blah","yadda yadda","wibble",None)
			],None) ],None) ]), s)
		self.assertEqual("- **[] [blah blah](#wibble)** _yadda yadda_\n", s.getvalue() )

	def test_write_handles_choice_no_response(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,"wibble",None)
			],None) ],None) ]), s)
		self.assertEqual("- **[X] [blah blah](#wibble)**\n", s.getvalue())
				
	def test_write_handles_choice_no_goto(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda",None,None)
			],None) ],None) ]), s)
		self.assertEquals("- **[X] blah blah** _yadda yadda_\n",
			s.getvalue())
				
	def test_write_handles_choice_no_response_or_goto(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,None,None)
			],None) ],None) ]), s)
		self.assertEquals("- **[X] blah blah**\n", s.getvalue())

	def test_write_handles_choice_wrapped_description(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","This is a test to test long lines of text "
					+"are wrapped properly onto the next line, okay?",
					"yadda yadda","wibble",None) ],None) ],None)]), s)
		self.assertEquals("- **[X] [This is a test to test long lines of text are "
			+"wrapped properly onto\n  the next line, okay?](#wibble)** "
			+"_yadda yadda_\n",s.getvalue())

	def test_write_handles_choice_wrapped_response(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah","This is a test to test long lines of text "
					+"are wrapped properly onto the next line, okay?",
					"wibble",None) ],None) ],None)]), s)
		self.assertEquals("- **[X] [blah](#wibble)** _This is a test to test long lines of "
			+"text are\n  wrapped properly onto the next line, okay?_\n",
			s.getvalue())

	def test_write_handles_choiceblock_multiple_choices(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
				dt.FirstSection([ dt.ChoiceBlock([
					dt.Choice("X","foo","bar","wibble",None),
					dt.Choice("Y","weh","meh","yadda",None),
				],None) ],None) ]), s)
		self.assertEquals("- **[X] [foo](#wibble)** _bar_\n"
			+"- **[Y] [weh](#yadda)** _meh_\n",
			s.getvalue())

	def test_write_handles_multiple_sections(self):
		s = io.BytesIO()
		dt.MarkdownIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("foo",None) ],None),
			dt.Section("dave",[ dt.TextBlock("bar",None) ],None) ]), s)
		self.assertEquals("foo\n\ndave\n----\n\nbar\n", s.getvalue())

class TestXmlIO(unittest.TestCase):

	def test_has_extensions(self):
		dt.XmlIO.EXTENSIONS[0]
		
	def test_write_doesnt_throw_error(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([]),s)
		
	def test_write_handles_document(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([]),s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree/>\n', s.getvalue())
		
	def test_write_handles_firstsection(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([],'this "is" <fab>') ]), s )
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <feedback>this &quot;is&quot; &lt;fab&gt;</feedback>\n'
			+'    </section>\n'
			+'</dectree>\n', 
			s.getvalue())
					
	def test_write_handles_section(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
				dt.Section('My <"> Section',[],'excellent "stuff" >_<') ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <name>My &lt;&quot;&gt; Section</name>\n'
			+'        <feedback>excellent &quot;stuff&quot; &gt;_&lt;</feedback>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue() )
				
	def test_write_handles_textblock(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock('This is "a" <<test>>',None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <text>This is &quot;a&quot; &lt;&lt;test&gt;&gt;</text>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())

	def test_formt_handles_firstsection_multiple_blocks(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <text>Testing</text>\n'
			+'        <text>More testing</text>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())
		
	def test_write_handles_section_multiple_blocks(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Testing",None),
				dt.TextBlock("More testing",None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <name>dave</name>\n'
			+'        <text>Testing</text>\n'
			+'        <text>More testing</text>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())
				
	def test_write_handles_firstsection_block_and_feedback(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <text>Test</text>\n'
			+'        <feedback>Blah blah</feedback>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())
				
	def test_write_handles_section_block_and_feedback(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.Section("dave",[ dt.TextBlock("Test",None) ], "Blah blah") ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <name>dave</name>\n'
			+'        <text>Test</text>\n'
			+'        <feedback>Blah blah</feedback>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue() )

	def test_write_handles_instructionblock(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.InstructionBlock('This is >a< "test"',None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <instructions>This is &gt;a&lt; &quot;test&quot;</instructions>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue() )

	def test_write_handles_choiceblock(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([], '<This> is "a" test') ],None)]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <feedback>&lt;This&gt; is &quot;a&quot; test</feedback>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())

	def test_write_handles_choice(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice('>"X"<','"blah" <blah>',
					'>>yadda " yadda<<','"wi>bb<le"',None)
			],None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <mark>&gt;&quot;X&quot;&lt;</mark>\n'
			+'                <desc>&quot;blah&quot; &lt;blah&gt;</desc>\n'
			+'                <response>&gt;&gt;yadda &quot; yadda&lt;&lt;</response>\n'
			+'                <goto>&quot;wi&gt;bb&lt;le&quot;</goto>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())

	def test_write_handles_choice_no_mark(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice(None,"blah blah",
					"yadda yadda","wibble",None)
			],None) ],None) ]), s)
		self.assertEqual(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <desc>blah blah</desc>\n'
			+'                <response>yadda yadda</response>\n'
			+'                <goto>wibble</goto>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue() )

	def test_write_handles_choice_no_response(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,"wibble",None)
			],None) ],None) ]), s)
		self.assertEqual(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <mark>X</mark>\n'
			+'                <desc>blah blah</desc>\n'
			+'                <goto>wibble</goto>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())
				
	def test_write_handles_choice_no_goto(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah","yadda yadda",None,None)
			],None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <mark>X</mark>\n'
			+'                <desc>blah blah</desc>\n'
			+'                <response>yadda yadda</response>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())
				
	def test_write_handles_choice_no_response_or_goto(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.ChoiceBlock([
				dt.Choice("X","blah blah",None,None,None)
			],None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <mark>X</mark>\n'
			+'                <desc>blah blah</desc>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())

	def test_write_handles_choiceblock_multiple_choices(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
				dt.FirstSection([ dt.ChoiceBlock([
					dt.Choice("X","foo","bar","wibble",None),
					dt.Choice("Y","weh","meh","yadda",None),
				],None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <choice>\n'
			+'            <option>\n'
			+'                <mark>X</mark>\n'
			+'                <desc>foo</desc>\n'
			+'                <response>bar</response>\n'
			+'                <goto>wibble</goto>\n'
			+'            </option>\n'
			+'            <option>\n'
			+'                <mark>Y</mark>\n'
			+'                <desc>weh</desc>\n'
			+'                <response>meh</response>\n'
			+'                <goto>yadda</goto>\n'
			+'            </option>\n'
			+'        </choice>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())

	def test_write_handles_multiple_sections(self):
		s = io.BytesIO()
		dt.XmlIO.write(dt.Document([
			dt.FirstSection([ dt.TextBlock("foo",None) ],None),
			dt.Section("dave",[ dt.TextBlock("bar",None) ],None) ]), s)
		self.assertEquals(
			'<?xml version="1.0" ?>\n'
			+'<dectree>\n'
			+'    <section>\n'
			+'        <text>foo</text>\n'
			+'    </section>\n'
			+'    <section>\n'
			+'        <name>dave</name>\n'
			+'        <text>bar</text>\n'
			+'    </section>\n'
			+'</dectree>\n', s.getvalue())


class TestGuiRunner(unittest.TestCase):

	def setUp(self):
		self.tk = mock.Mock()
		self.gui = mock.Mock()
		
	def do_run(self,doc,mockloop=None):
		runner = dt.GuiRunner()
		if mockloop:
			self.tk.mainloop.side_effect = lambda: mockloop(runner)
		runner._run(doc,self.tk,self.gui)
		
	def test_can_run(self):
		self.do_run(dt.Document([]))
	
	def test_starts_tk_event_loop(self):
		self.do_run(dt.Document([]))
		self.assertEquals(1, self.tk.mainloop.call_count)
			
	def test_performs_initial_gui_update(self):
		self.do_run(dt.Document([]))
		self.assertEquals(1, self.gui.on_prev_item_change.call_count)
		self.assertEquals(1, self.gui.on_curr_item_change.call_count)
		self.assertEquals(1, self.gui.on_back_allowed_change.call_count)
		self.assertEquals(1, self.gui.on_forward_allowed_change.call_count)
		self.assertEquals(1, self.gui.on_section_change.call_count)
		
	def test_shows_current_textblock(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("This is a test",None) ],None)]))
		self.assertEquals(0, len(self.gui.on_curr_item_change.call_args[1]))
		self.assertEquals(1, len(self.gui.on_curr_item_change.call_args[0]))
		item = self.gui.on_curr_item_change.call_args[0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerText) )
		self.assertEquals( "This is a test", item.text )
		
	def test_shows_current_choiceblock(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"Animal",None,None,None),
				dt.Choice(None,"Mineral",None,None,None),
				dt.Choice(None,"Vegetable",None,None,None),
			],None) ],None)]))
		self.assertEquals(0, len(self.gui.on_curr_item_change.call_args[1]))
		self.assertEquals(1, len(self.gui.on_curr_item_change.call_args[0]))
		item = self.gui.on_curr_item_change.call_args[0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerChoice) )
		self.assertEquals( ["Animal","Mineral","Vegetable"], item.options )
		self.assertIsNone( item.selected )
		
	def test_indicates_selected_option_for_choiceblock(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"Animal",None,None,None),
				dt.Choice(None,"Mineral",None,None,None),
				dt.Choice("X", "Vegetable",None,None,None),
			],None) ],None)]))
		self.assertEquals(2, self.gui.on_curr_item_change.call_args[0][0].selected)
		
	def test_doesnt_show_instructionblock(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.InstructionBlock("Ignore me",None) ],None)]))
		self.assertEquals(0, len(self.gui.on_curr_item_change.call_args[1]))
		self.assertEquals(1, len(self.gui.on_curr_item_change.call_args[0]))
		item = self.gui.on_curr_item_change.call_args[0][0]
		self.assertIsNone( item )
		
	def test_shows_no_previous_block_for_first_block(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None) ],None)]))
		self.assertEquals(0, len(self.gui.on_prev_item_change.call_args[1]))
		self.assertEquals(1, len(self.gui.on_prev_item_change.call_args[0]))
		item = self.gui.on_prev_item_change.call_args[0][0]
		self.assertIsNone( item )
		
	def test_disallows_back_for_first_block(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None) ],None)]))
		self.assertEquals(0,len(self.gui.on_back_allowed_change.call_args[1]))
		self.assertEquals(1,len(self.gui.on_back_allowed_change.call_args[0]))
		self.assertEquals( False, self.gui.on_back_allowed_change.call_args[0][0] )	

	def test_allows_forward_initially(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None),
			dt.TextBlock("bar",None) ],None)]))
		self.assertEquals(0,len(self.gui.on_forward_allowed_change.call_args[1]))
		self.assertEquals(1,len(self.gui.on_forward_allowed_change.call_args[0]))
		self.assertEquals( True, self.gui.on_forward_allowed_change.call_args[0][0] )
		
	def test_sets_initial_section_name_blank(self):
		self.do_run(dt.Document([dt.FirstSection([],None)]))
		self.gui.on_section_change.assert_called_once_with( None )
		
	def test_updates_curr_item_to_textblock_on_next(self):
		def loop(runner):
			runner.on_next()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("this is the first item",None),
			dt.TextBlock("this is the second item",None) 
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_curr_item_change.call_count)
		item = self.gui.on_curr_item_change.call_args_list[1][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerText))
		self.assertEquals("this is the second item", item.text)
		
	def test_updates_curr_item_to_choiceblock_on_next(self):
		def loop(runner):
			runner.on_next()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("this is the first item",None),
			dt.ChoiceBlock([
				dt.Choice(None,"Opt A",None,None,None),
				dt.Choice(None,"Opt B",None,None,None) ],None) 
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_curr_item_change.call_count)
		item = self.gui.on_curr_item_change.call_args_list[1][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerChoice) )
		self.assertEquals(["Opt A","Opt B"], item.options)

	def test_updates_prev_item_to_textblock_on_next(self):
		def loop(runner): runner.on_next()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("this is the first item",None),
			dt.TextBlock("this is the second item",None)
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_prev_item_change.call_count)
		item = self.gui.on_prev_item_change.call_args_list[1][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerText) )
		self.assertEquals("this is the first item", item.text)
	
	def test_updates_prev_item_to_choiceblock_on_next(self):
		def loop(runner): runner.on_next()
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"Opt A",None,None,None),
				dt.Choice(None,"Opt B",None,None,None) ],None),
			dt.TextBlock("This is a test",None)
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_prev_item_change.call_count)
		item = self.gui.on_prev_item_change.call_args_list[1][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerChoice) )
		self.assertEquals(["Opt A","Opt B"],item.options)

	def test_allows_back_on_next(self):
		def loop(runner): runner.on_next()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foobar",None),
			dt.TextBlock("blah blah",None),
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_back_allowed_change.call_count)
		self.assertEquals(True,self.gui.on_back_allowed_change.call_args_list[1][0][0])

	def test_updates_current_item_to_textblock_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("this is the first item",None),
			dt.TextBlock("this is the second item",None) 
		],None)]),mockloop=loop)
		self.assertEquals(3, self.gui.on_curr_item_change.call_count)
		item = self.gui.on_curr_item_change.call_args_list[2][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerText))
		self.assertEquals("this is the first item", item.text)
		
	def test_updates_current_item_to_choiceblock_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"Opt A",None,None,None),
				dt.Choice(None,"Opt B",None,None,None) ],None),
			dt.TextBlock("this is the second item",None) 
		],None)]),mockloop=loop)
		self.assertEquals(3, self.gui.on_curr_item_change.call_count)
		item = self.gui.on_curr_item_change.call_args_list[2][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerChoice))
		self.assertEquals(["Opt A","Opt B"], item.options)
		
	def test_updates_prev_item_to_blank_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo bar",None),
			dt.TextBlock("this is the second item",None) 
		],None)]),mockloop=loop)
		self.assertEquals(3, self.gui.on_prev_item_change.call_count)
		item = self.gui.on_prev_item_change.call_args_list[2][0][0]
		self.assertIsNone(item)
	
	def test_updates_prev_item_to_textblock_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo bar",None),
			dt.TextBlock("this is the second item",None),
			dt.TextBlock("blah blah",None),
		],None)]),mockloop=loop)
		self.assertEquals(4, self.gui.on_prev_item_change.call_count)
		item = self.gui.on_prev_item_change.call_args_list[3][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerText) )
		self.assertEquals("foo bar",item.text)

	def test_updates_prev_item_to_choiceblock_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"cake",None,None,None),
				dt.Choice(None,"death",None,None,None) ],None),
			dt.TextBlock("this is the second item",None),
			dt.TextBlock("blah blah",None),
		],None)]),mockloop=loop)
		self.assertEquals(4, self.gui.on_prev_item_change.call_count)
		item = self.gui.on_prev_item_change.call_args_list[3][0][0]
		self.assertTrue( isinstance(item,dt.GuiRunnerChoice) )
		self.assertEquals(["cake","death"],item.options)
		
	def test_allows_back_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None),
			dt.TextBlock("bar",None),
			dt.TextBlock("weh",None),
		],None)]),mockloop=loop)
		self.assertEquals(4,self.gui.on_back_allowed_change.call_count)
		self.assertTrue( self.gui.on_back_allowed_change.call_args_list[3][0][0] )
		
	def test_disallows_back_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None),
			dt.TextBlock("bar",None),
		],None)]),mockloop=loop)
		self.assertEquals(3,self.gui.on_back_allowed_change.call_count)
		self.assertFalse( self.gui.on_back_allowed_change.call_args_list[2][0][0] )
		
	def test_allows_forward_on_prev(self):
		def loop(runner):
			runner.on_next()
			runner.on_prev()
		self.do_run(dt.Document([dt.FirstSection([
			dt.TextBlock("foo",None),
			dt.TextBlock("bar",None),
		],None)]),mockloop=loop)
		self.assertEquals(3,self.gui.on_forward_allowed_change.call_count)
		self.assertTrue( self.gui.on_forward_allowed_change.call_args_list[2][0][0] )
	
	def test_doesnt_allow_forward_before_choice_made(self):
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"cats",None,None,None),
				dt.Choice(None,"dogs",None,None,None) ],None),
			dt.TextBlock("foo",None),
		],None)]))
		self.gui.on_forward_allowed_change.assert_called_once_with(False)
		
	def test_allows_forward_after_choice_made(self):
		def loop(runner):
			runner.on_change_selection(1)
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"cats",None,None,None),
				dt.Choice(None,"dogs",None,None,None) ],None),
			dt.TextBlock("foo",None),
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_forward_allowed_change.call_count)
		self.assertTrue( self.gui.on_forward_allowed_change.call_args_list[1][0][0] )		

	def test_only_allows_forward_first_time_choice_made(self):
		def loop(runner):	
			runner.on_change_selection(0)
			runner.on_change_selection(1)
			runner.on_change_selection(0)
		self.do_run(dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"cats",None,None,None),
				dt.Choice(None,"dogs",None,None,None) ],None),
			dt.TextBlock("foo",None),
		],None)]),mockloop=loop)
		self.assertEquals(2, self.gui.on_forward_allowed_change.call_count)

	def test_sets_choice_mark_on_selection(self):
		def loop(runner):
			runner.on_change_selection(1)
		d = dt.Document([dt.FirstSection([
			dt.ChoiceBlock([
				dt.Choice(None,"cats",None,None,None),
				dt.Choice(None,"dogs",None,None,None) ],None),
			dt.TextBlock("foo",None) ],None)])
		self.assertIsNone(d.sections[0].items[0].choices[0].mark)
		self.assertIsNone(d.sections[0].items[0].choices[1].mark)
		self.do_run(d,mockloop=loop)
		self.assertIsNone(d.sections[0].items[0].choices[0].mark)
		self.assertEquals("X",d.sections[0].items[0].choices[1].mark)
		
	# TODO: ending on last "next"
	
unittest.main()


