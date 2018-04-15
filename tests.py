#!/usr/bin/env python3

import os
import os.path
import codecs
import io
import sys
from unittest import mock
import unittest
import tkinter as Tkinter
import re
import hrbrt.io as hio
import hrbrt.run as hrun
import hrbrt.parse as hps


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
        hps.Input("foobar")
        
    def test_can_iterate(self):
        i = hps.Input("abc")
        self.assertEqual("a",i.next())
        self.assertEqual("b",i.next())
        self.assertEqual("c",i.next())

    def test_can_branch(self):
        i = hps.Input("abcdef")
        i.next()
        j = i.branch()
        self.assertEqual("b", i.next())
        self.assertEqual("b", j.next())
        self.assertEqual("c", j.next())
        self.assertEqual("c", i.next())
        
    def test_can_commit(self):
        i = hps.Input("abcdef")
        j = i.branch()
        j.next()
        j.next()
        j.commit()
        self.assertEqual("c",i.next())
        
    def test_get_deepest_pos(self):
        i = hps.Input("abcdef")
        i.next()
        j = i.branch()
        j.next()
        k = j.branch()
        k.next()
        self.assertEqual(3, i.get_deepest_pos())


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
        hps.Document([object(),object()])
        
    def test_sections_readable(self):
        s = hps.FirstSection([],None)
        d = hps.Document([s])
        self.assertEqual(s, d.sections[0])
        
    def test_sections_attribute_readonly(self):
        d = hps.Document([hps.FirstSection([],None)])
        with self.assertRaises(AttributeError):
            d.sections = ["weh"]
            
    def test_sections_attribute_immutable(self):
        s = hps.FirstSection([],None)
        d = hps.Document([s])
        d.sections[0] = "weh"
        self.assertEqual(s,d.sections[0])

    def test_is_completed_readable(self):
        d = hps.Document([])
        d.is_completed
        
    def test_is_completed_not_writable(self):
        d = hps.Document([])
        with self.assertRaises(AttributeError):
            d.is_completed = True

    def setup_parse_methods(self):
        hps.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[["foo"]])})
        hps.Section.parse.side_effect = make_parse({"s":self.make_section("foo",gotos=[])})

    mock_parse_methods = mock_statics(hps,"FirstSection.parse","Section.parse")
    
    @mock_parse_methods
    def test_parse_returns_populated_document(self):
        self.setup_parse_methods()
        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo")
        hps.FirstSection.parse.side_effect = make_parse({"f":s1})
        hps.Section.parse.side_effect = make_parse({"s":s2})
        result = hps.Document.parse(MockInput("fs\x00",0,None))
        self.assertTrue( isinstance(result,hps.Document) )
        self.assertTrue( hasattr(result,"sections") )
        self.assertEqual( [s1,s2], list(result.sections) )

    @mock_parse_methods
    def test_parse_expects_firstsection(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Document.parse(MockInput("s\x00",0,None)) )
        self.assertFalse( hps.Section.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_zero_sections(self):
        self.setup_parse_methods()
        hps.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[])})
        self.assertIsNotNone( hps.Document.parse(MockInput("f\x00",0,None)) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_sections(self):
        self.setup_parse_methods()
        hps.FirstSection.parse.side_effect = make_parse({"f":self.make_section(gotos=[["one"]])})
        secitr = iter([
            self.make_section("one",gotos=[["two"]]),
            self.make_section("two",gotos=[["three"]]),
            self.make_section("three",gotos=[])
        ])
        hps.Section.parse.side_effect = make_parse({"s":next(secitr)})
        self.assertIsNotNone( hps.Document.parse(MockInput("fsss\x00",0,None)) )
        
    @mock_parse_methods
    def test_parse_expects_char_0(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Document.parse(MockInput("fq",0,None)) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("fs\x00",0,None)
        hps.Document.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("fsq",0,None)
        hps.Document.parse(i)
        self.assertEqual(0, i.pos)
    
    def make_section(self,name=None,gotos=[]):
        cbs = []
        for gs in gotos:
            cs = []
            for g in gs:
                cs.append(hps.Choice("blah","weh","yadda",g,"wibble"))
            cbs.append(hps.ChoiceBlock(cs,""))
        bs = [hps.TextBlock("foo","bar")]
        bs.extend(cbs)
        if name is None:
            return hps.FirstSection(bs,"")
        else:
            return hps.Section(name,bs,"")

    def test_validate_returns_error_for_duplicate_section_names(self):
    
        s1 = self.make_section(gotos=[["foobar"]])
        s2 = self.make_section("foobar",gotos=[["foobar"]])
        s3 = self.make_section("foobar",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertEqual("Duplicate section name 'foobar'", 
            d.validate() )
        
    def test_validate_uses_case_insensitive_section_names(self):
        
        s1 = self.make_section(gotos=[["foobar"]])
        s2 = self.make_section("foobar",gotos=[["foobar"]])
        s3 = self.make_section("FoObAr",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertEqual("Duplicate section name 'foobar'",
            d.validate() )
                            
    def test_validate_doesnt_return_error_for_unique_section_names(self):
    
        s1 = self.make_section(gotos=[["foobar"]])
        s2 = self.make_section("foobar",gotos=[["wibble"]])
        s3 = self.make_section("wibble",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )
        
    def test_validate_returns_error_for_invalid_goto_reference_in_first_section(self):
        
        s1 = self.make_section(gotos=[["nowhere","somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["anywhere"]])
        s3 = self.make_section("anywhere",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertEqual("Go-to references unknown section 'nowhere'",
            d.validate() )
    
    def test_validate_uses_case_insensitive_gotos_in_first_section(self):
        
        s1 = self.make_section(gotos=[["sOmEwHeRe"]])
        s2 = self.make_section("SoMeWhErE",gotos=[["anywhere"]])
        s3 = self.make_section("anywhere",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )
        
    def test_validate_returns_error_for_invalid_goto_reference_in_section(self):
        
        s1 = self.make_section(gotos=[["somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["anywhere"]])
        s3 = self.make_section("anywhere",gotos=[["neverneverland","somewhere",None]])
        d = hps.Document([s1,s2,s3])
        self.assertEqual("Go-to references unknown section 'neverneverland'",
            d.validate() )
            
    def test_validate_uses_case_insensitive_gotos_in_section(self):
        
        s1 = self.make_section(gotos=[["somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["AnYwHeRe"]])
        s3 = self.make_section("aNyWhErE",gotos=[["somewhere",None]])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )
                
    def test_validate_doesnt_return_error_for_valid_forward_goto_references(self):
        
        s1 = self.make_section(gotos=[["somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["anywhere"]])
        s3 = self.make_section("anywhere",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )
    
    def test_validate_doesnt_return_error_for_valid_backward_goto_references(self):
                
        s1 = self.make_section(gotos=[["somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["anywhere"]])
        s3 = self.make_section("anywhere",gotos=[["somewhere",None]])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )

    def test_validate_doesnt_return_error_for_self_goto_references(self):
        
        s1 = self.make_section(gotos=[["somewhere"]])
        s2 = self.make_section("somewhere",gotos=[["somewhere","anywhere"]])
        s3 = self.make_section("anywhere",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )

    def test_validate_doesnt_return_error_for_indirectly_looping_goto_references(self):
    
        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo",gotos=[["end","bar"]])
        s3 = self.make_section("bar",gotos=[["foo"]])
        s4 = self.make_section("end",gotos=[])
        d = hps.Document([s1,s2,s3,s4])
        self.assertIsNone( d.validate() )
    
    def test_parse_returns_error_for_incomplete_user_path_in_first_section(self):
    
        s1 = self.make_section(gotos=[[None,"the end"]])
        s2 = self.make_section("the end",gotos=[])
        d = hps.Document([s1,s2])
        self.assertEqual('Section "first" has one or more '
            +'choices that reach end of section and so never '
            +'reach end of document', d.validate())
        
    def test_parse_returns_error_for_incomplete_user_path_in_second_section(self):
    
        s1 = self.make_section(gotos=[["second","the end"]])
        s2 = self.make_section("second",gotos=[["the end",None]])
        s3 = self.make_section("the end",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertEqual('Section "second" has one or more '
            +'choices that reach end of section and so never '
            +'reach end of document', d.validate())
        
    def test_parse_only_considers_last_choice_block_for_imcomplete_path(self):
        
        s1 = self.make_section(gotos=[["second",None],["second","the end"]])
        s2 = self.make_section("second",gotos=[[None,"the end"],["the end","the end"]])
        s3 = self.make_section("the end",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertIsNone( d.validate() )
        
    def test_parse_requires_dropout_choice_in_last_section(self):
        
        s1 = self.make_section(gotos=[["second"]])
        s2 = self.make_section("second",gotos=[["the end"]])
        s3 = self.make_section("the end",gotos=[["second","the end"]])
        d = hps.Document([s1,s2,s3])
        self.assertEqual('End section "the end" has no choices '
            +'that reach end of document', d.validate())
        
    def test_validate_requires_choices_in_sections(self):
        
        s1 = self.make_section(gotos=[])
        s2 = self.make_section("the end",gotos=[[None]])
        d = hps.Document([s1,s2])
        self.assertEqual('Section "first" has no choice blocks '
            +'and so cannot reach end of document', d.validate())
            
    def test_validate_allows_lack_of_choices_in_end_section(self):
    
        s1 = self.make_section(gotos=[["the end"]])
        s2 = self.make_section("the end",gotos=[])
        d = hps.Document([s1,s2])
        self.assertIsNone( d.validate() )

    def test_validate_defers_decision_on_looping_choices(self):
        
        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo",gotos=[["bar","end"]])
        s3 = self.make_section("bar",gotos=[["foo"]])
        s4 = self.make_section("end",gotos=[])
        d = hps.Document([s1,s2,s3,s4])
        self.assertIsNone( d.validate() )            
        
    def test_validate_returns_error_for_dead_end_self_loop(self):

        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo",gotos=[["bar","end"]])
        s3 = self.make_section("bar",gotos=[["bar"]])
        s4 = self.make_section("end",gotos=[])
        d = hps.Document([s1,s2,s3,s4])
        self.assertEqual('Dead-end loop found in section "bar"',
            d.validate() )
            
    def test_validate_returns_error_for_dead_end_indirect_loop(self):
    
        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo",gotos=[["bar","end"]])
        s3 = self.make_section("bar",gotos=[["weh"]])
        s4 = self.make_section("weh",gotos=[["bar"]])
        s5 = self.make_section("end",gotos=[])
        d = hps.Document([s1,s2,s3,s4,s5])
        self.assertEqual('Dead-end loop found in section "weh"',
            d.validate() )        
            
    def test_validate_returns_error_for_double_dead_end_loop(self):
        
        s1 = self.make_section(gotos=[["foo"]])
        s2 = self.make_section("foo",gotos=[["foo","foo"]])
        s3 = self.make_section("end",gotos=[])
        d = hps.Document([s1,s2,s3])
        self.assertEqual('Dead-end loop found in section "foo"',
            d.validate() )
        
    def test_is_completed_returns_true_for_completed_section(self):
        s1 = mock.Mock()
        s1.is_completed = False
        s2 = mock.Mock()
        s2.is_completed = True
        d = hps.Document([s1,s2])
        self.assertEqual(True, d.is_completed)
        
    def test_is_completed_returns_false_for_no_completed_sections(self):
        s1 = mock.Mock()
        s1.is_completed = False
        s2 = mock.Mock()
        s2.is_completed = False
        d = hps.Document([s1,s2])
        self.assertEqual(False, d.is_completed)
        
        
class TestFirstSection(unittest.TestCase):

    def test_construct(self):
        hps.FirstSection([],"bar")
        
    def test_items_readable(self):
        i = hps.TextBlock("a",None)
        f = hps.FirstSection([i],None)
        self.assertEqual([i], f.items)
        
    def test_items_not_writable(self):
        f = hps.FirstSection([hps.TextBlock("a",None)],None)
        with self.assertRaises(AttributeError):
            f.items = ["bar"]
            
    def test_items_immutable(self):
        i = hps.TextBlock("a",None)
        f = hps.FirstSection([i],None)
        f.items[0] = "bar"
        self.assertEqual(i,f.items[0])
            
    def test_feedback_readable(self):
        f = hps.FirstSection([],"bar")
        self.assertEqual("bar",f.feedback)
        
    def test_feedback_not_writable(self):
        f = hps.FirstSection([],"bar")
        with self.assertRaises(AttributeError):
            f.feedback = "blah"
        
    def test_is_completed_readable(self):
        f = hps.FirstSection([],None)
        f.is_completed
        
    def test_is_completed_not_writable(self):
        f = hps.FirstSection([],None)
        with self.assertRaises(AttributeError):
            f.is_completed = True
        
    def setup_parse_methods(self):
        hps.SectionContent.parse.side_effect = make_parse({"c":hps.SectionContent("a","b")})
        
    mock_parse_methods = mock_statics(hps,"SectionContent.parse")
            
    @mock_parse_methods
    def test_parse_returns_populated_firstsection(self):    
        self.setup_parse_methods()
        c = hps.SectionContent(["foo"],"bar")
        hps.SectionContent.parse.side_effect = make_parse({"c":c})
        result = hps.FirstSection.parse(MockInput("c",0,None))
        self.assertTrue( isinstance(result,hps.FirstSection) )
        self.assertTrue( hasattr(result,"items") )
        self.assertEqual( ["foo"], result.items )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual( "bar", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.SectionContent.parse.side_effect = make_parse({"c":hps.SectionContent([],None)})
        result = hps.FirstSection.parse(MockInput("c"))
        self.assertIsNone(result.feedback)
        
    @mock_parse_methods
    def test_parse_expects_sectioncontent(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.FirstSection.parse(MockInput("q",0,None)) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        input = MockInput("c",0,None)
        hps.FirstSection.parse(input)
        self.assertEqual(1, input.pos)

    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        input = MockInput("q",0,None)
        hps.FirstSection.parse(input)
        self.assertEqual(0, input.pos)
        
    def test_is_completed_returns_true_for_completed_choiceblock(self):
        cb1 = mock.Mock()
        cb1.is_completed = False
        cb2 = mock.Mock()
        cb2.is_completed = True
        f = hps.FirstSection([cb1,cb2],None)
        self.assertEqual(True, f.is_completed)
        
    def test_is_completed_returns_true_for_feedback(self):
        f = hps.FirstSection([],"foobar")
        self.assertEqual(True, f.is_completed)
        
    def test_is_completed_returns_false_for_no_feedback_or_completed_blocks(self):
        cb1 = mock.Mock()
        cb1.is_completed = False
        cb2 = mock.Mock()
        cb2.is_completed = False
        f = hps.FirstSection([cb1,cb2],None)
        self.assertEqual(False, f.is_completed)
        

class TestSection(unittest.TestCase):
    
    def test_construct(self):
        hps.Section("foo",[],None)
        
    def test_heading_readable(self):
        s = hps.Section("foo",[],None)
        self.assertEqual("foo", s.heading)
        
    def test_heading_not_writable(self):
        s = hps.Section("foo",[],None)
        with self.assertRaises(AttributeError):
            s.heading = "yadda"
            
    def test_items_readable(self):
        i = hps.TextBlock("a",None)
        s = hps.Section("foo",[i],None)
        self.assertEqual([i], s.items)
        
    def test_items_not_writable(self):
        s = hps.Section("foo",[hps.TextBlock("a",None)],None)
        with self.assertRaises(AttributeError):
            s.items = "weh"
            
    def test_items_immutable(self):
        i = hps.TextBlock("a",None)
        s = hps.Section("foo",[i],None)
        s.items[0] = "yadda"
        self.assertEqual(i,s.items[0])
        
    def test_feedback_readable(self):
        s = hps.Section("foo",[],"weh")
        self.assertEqual("weh", s.feedback)
        
    def test_feedback_not_writable(self):
        s = hps.Section("foo",[],"weh")
        with self.assertRaises(AttributeError):
            s.feedback = "blah"    
    
    def test_is_completed_readable(self):
        s = hps.Section("foo",[],None)
        s.is_completed
        
    def test_is_completed_not_writable(self):
        s = hps.Section("foo",[],None)
        with self.assertRaises(AttributeError):
            s.is_completed = True
    
    def setup_parse_methods(self):
        hps.Heading.parse.side_effect = make_parse({"h":hps.Heading("a")})
        hps.SectionContent.parse.side_effect = make_parse({"c":hps.SectionContent("b","c")})
        
    mock_parse_methods = mock_statics(hps,"Heading.parse","SectionContent.parse")    
        
    @mock_parse_methods
    def test_parse_returns_populated_section(self):
        self.setup_parse_methods()
        h = hps.Heading("wobble")
        hps.Heading.parse.side_effect = make_parse({"h":h})
        c = hps.SectionContent(["foo"],"bar")
        hps.SectionContent.parse.side_effect = make_parse({"c":c})
        result = hps.Section.parse(MockInput("hc",0,None))
        self.assertTrue( isinstance(result,hps.Section) )
        self.assertTrue( hasattr(result,"heading") )
        self.assertEqual("wobble", result.heading)
        self.assertTrue( hasattr(result,"items") )
        self.assertEqual(["foo"], result.items)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("bar", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.SectionContent.parse.side_effect = make_parse({"c":hps.SectionContent([],None)})
        result = hps.Section.parse(MockInput("hc"))
        self.assertIsNone(result.feedback)
        
    @mock_parse_methods
    def test_parse_expects_heading(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Section.parse(MockInput("c",0,None)) )
        self.assertFalse( hps.SectionContent.parse.called )
        
    @mock_parse_methods
    def test_parse_expects_sectioncontent(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Section.parse(MockInput("hq",0,None)) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("hc",0,None)
        hps.Section.parse(i)
        self.assertEqual(2, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("hq",0,None)
        hps.Section.parse(i)
        self.assertEqual(0, i.pos)
        
    def test_is_completed_returns_true_for_completed_choiceblock(self):
        cb1 = mock.Mock()
        cb1.is_completed = False
        cb2 = mock.Mock()
        cb2.is_completed = True
        s = hps.Section("dave",[cb1,cb2],None)
        self.assertEqual(True, s.is_completed)
        
    def test_is_completed_returns_true_for_feedback(self):
        cb1 = mock.Mock()
        cb1.is_completed = False
        cb2 = mock.Mock()
        cb2.is_completed = False
        s = hps.Section("dave",[cb1,cb2],"foobar")
        self.assertEqual(True, s.is_completed)
        
    def test_is_completed_returns_false_for_no_completed_choiceblocks_or_feedback(self):
        cb1 = mock.Mock()
        cb1.is_completed = False
        cb2 = mock.Mock()
        cb2.is_completed = False
        s = hps.Section("dave",[cb1,cb2],None)
        self.assertEqual(False, s.is_completed)
        
        
class TestHeading(unittest.TestCase):

    def test_construct(self):
        hps.Heading("foo")
        
    def test_name_readable(self):
        h = hps.Heading("foo")
        self.assertEqual("foo", h.name)
        
    def test_name_attribute_readonly(self):
        h = hps.Heading("foo")
        with self.assertRaises(AttributeError):
            h.name = "bar"
            
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_returns_populated_heading(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("foobar")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        result = hps.Heading.parse(MockInput("qhwnhl",0,None))
        self.assertTrue( isinstance(result,hps.Heading) )
        self.assertTrue( hasattr(result,"name") )
        self.assertEqual("foobar", result.name)
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_allows_no_quotemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.Heading.parse(MockInput("hwnhl",0,None)) )
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_expects_first_headingmarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.Heading.parse(MockInput("qwnhl",0,None)) )
        self.assertFalse( hps.LineWhitespace.parse.called )
        self.assertFalse( hps.Name.parse.called )
        self.assertEqual( 1, hps.HeadingMarker.parse.call_count )
        self.assertFalse( hps.Newline.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_allows_no_linewhitespace(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.Heading.parse(MockInput("qhnhl",0,None)) )

    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_expects_name(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        self.assertIsNone( hps.Heading.parse(MockInput("qhwhl",0,None)) )
        self.assertEqual(1, hps.HeadingMarker.parse.call_count)
        self.assertFalse( hps.Newline.parse.called )        

    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_expects_secton_headingmarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        self.assertIsNone( hps.Heading.parse(MockInput("qhwnl",0,None)) )
        self.assertFalse( hps.Newline.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_expects_newline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.Heading.parse(MockInput("qhwnhz",0,None)) )
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qhwnhl",0,None)
        hps.Heading.parse(i)
        self.assertEqual(6, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","HeadingMarker.parse",
            "LineWhitespace.parse","Name.parse","Newline.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.HeadingMarker.parse.side_effect = make_parse({"h":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qhwnhz",0,None)
        hps.Heading.parse(i)
        self.assertEqual(0, i.pos)
    

class TestQuoteMarker(unittest.TestCase):
    
    def test_construct(self):
        hps.QuoteMarker()
        
    def test_parse_returns_quotemarker(self):
        result = hps.QuoteMarker.parse(MockInput(" \t> x",0,None))
        self.assertTrue( isinstance(result,hps.QuoteMarker) )
        
    def test_parse_allows_no_whitespace(self):
        self.assertIsNotNone( hps.QuoteMarker.parse(MockInput(">x",0,None)) )
        
    def test_parse_expects_angle_bracket(self):
        self.assertIsNone( hps.QuoteMarker.parse(MockInput("x",0,None)) )
        
    def test_parse_allows_multiple_markers(self):
        self.assertIsNotNone( hps.QuoteMarker.parse(MockInput(" > > > x",0,None)) )
        
    def test_parse_allows_trailing_whitespace(self):
        i = MockInput(">\t x")
        self.assertIsNotNone( hps.QuoteMarker.parse(i) )
        self.assertEqual(3,i.pos)
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("\t>x",0,None)
        hps.QuoteMarker.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("\t\t\tx",0,None)
        hps.QuoteMarker.parse(i)
        self.assertEqual(0, i.pos)


class TestHeadingMarker(unittest.TestCase):
    
    def test_construct(self):
        hps.HeadingMarker()
        
    def test_parse_returns_headingmarker(self):
        result = hps.HeadingMarker.parse(MockInput("==x",0,None))    
        self.assertTrue( isinstance(result,hps.HeadingMarker) )
        
    def test_parse_expects_first_equals(self):
        self.assertIsNone( hps.HeadingMarker.parse(MockInput("zx",0,None)) )
        
    def test_parse_expects_second_equals(self):
        self.assertIsNone( hps.HeadingMarker.parse(MockInput("=qx",0,None)) )
        
    def test_parse_allows_more_than_two_equals(self):
        i = MockInput("=====x",0,None)
        self.assertIsNotNone( hps.HeadingMarker.parse(i) )
        self.assertEqual(5, i.pos)
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("==x",0,None)
        hps.HeadingMarker.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("=x",0,None)
        hps.HeadingMarker.parse(i)
        self.assertEqual(0, i.pos)
        
        
class TestLineWhitespace(unittest.TestCase):

    def test_construct(self):
        hps.LineWhitespace()
        
    def test_parse_returns_linewhitespace(self):
        result = hps.LineWhitespace.parse(MockInput(" x",0,None))
        self.assertTrue( isinstance(result,hps.LineWhitespace) )
        
    def test_parse_expects_space_or_tab(self):
        self.assertIsNone( hps.LineWhitespace.parse(MockInput("qx",0,None)) )
        
    def test_parse_accepts_tab(self):
        self.assertIsNotNone( hps.LineWhitespace.parse(MockInput("\tx",0,None)) )
        
    def test_parse_accepts_multiple_spaces_and_tabs(self):
        i = MockInput("  \t\t \tx",0,None)
        self.assertIsNotNone( hps.LineWhitespace.parse(i) )
        self.assertEqual(6, i.pos)
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("\t\tx",0,None)
        hps.LineWhitespace.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("qx",0,None)
        hps.LineWhitespace.parse(i)
        self.assertEqual(0, i.pos)
        
        
class TestName(unittest.TestCase):

    def test_construct(self):
        hps.Name("foo")
        
    def test_text_readable(self):
        n = hps.Name("foo")
        self.assertEqual("foo",n.text)
        
    def test_text_not_writable(self):
        n = hps.Name("foo")
        with self.assertRaises(AttributeError):
            n.text = "bar"
            
    def test_parse_returns_populated_name(self):
        result = hps.Name.parse(MockInput("foo^",0,None))
        self.assertTrue( isinstance(result,hps.Name) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo", result.text)
        
    def test_parse_expects_word_char(self):
        self.assertIsNone( hps.Name.parse(MockInput(",^",0,None)) )
        
    def test_parse_allows_uppercase(self):
        self.assertIsNotNone( hps.Name.parse(MockInput("A^",0,None)) )
        
    def test_parse_allows_number(self):
        self.assertIsNotNone( hps.Name.parse(MockInput("9^",0,None)) )    
    
    def test_parse_allows_underscore(self):
        self.assertIsNotNone( hps.Name.parse(MockInput("_^",0,None)) )
        
    def test_parse_allows_hyphen(self):
        self.assertIsNotNone( hps.Name.parse(MockInput("-^",0,None)) )
        
    def test_parse_allows_multiple_characters(self):
        i = MockInput("abcXY-Z123^",0,None)
        self.assertIsNotNone( hps.Name.parse(i) )
        self.assertEqual(10, i.pos)
        
    def test_parse_allows_spaces(self):
        i = MockInput("foo bar^",0,None)
        self.assertIsNotNone( hps.Name.parse(i) )
        self.assertEqual(7, i.pos)
        
    def test_parse_doesnt_allow_leading_space(self):
        self.assertIsNone( hps.Name.parse(MockInput("   foo^",0,None)) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("HowNowBrownCow^",0,None)
        hps.Name.parse(i)
        self.assertEqual(14, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput(",^",0,None)
        hps.Name.parse(i)
        self.assertEqual(0, i.pos)
        
        
class TestNewline(unittest.TestCase):

    def test_construct(self):
        hps.Newline()
        
    def test_parse_returns_newline(self):
        result = hps.Newline.parse(MockInput("\n^",0,None))
        self.assertTrue( isinstance(result,hps.Newline) )
        
    def test_parse_expects_newline(self):
        self.assertIsNone( hps.Newline.parse(MockInput(",^",0,None)) )
        
    def test_parse_accepts_carriage_return(self):
        self.assertIsNotNone( hps.Newline.parse(MockInput("\r^",0,None)) )
        
    def test_parse_accepts_cr_nl(self):
        i = MockInput("\r\n^",0,None)
        self.assertIsNotNone( hps.Newline.parse(i) )
        self.assertEqual(2, i.pos)
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("\n^",0,None)
        hps.Newline.parse(i)
        self.assertEqual(1, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("\t^",0,None)
        hps.Newline.parse(i)
        self.assertEqual(0, i.pos)


class TestSectionContent(unittest.TestCase):

    def test_construct(self):
        hps.SectionContent(["foo","bar"],"weh")
        
    def test_items_readable(self):
        c = hps.SectionContent(["foo","bar"],"weh")
        self.assertEqual("foo", c.items[0])
        
    def test_items_not_writable(self):
        c = hps.SectionContent(["foo","bar"],"weh")
        with self.assertRaises(AttributeError):
            c.items = ["weh"]
            
    def test_items_immutable(self):
        c = hps.SectionContent(["foo","bar"],"weh")
        c.items[0] = "weh"
        self.assertEqual("foo", c.items[0])
        
    def test_feedback_readable(self):
        c = hps.SectionContent(["foo","bar"],"weh")
        self.assertEqual("weh",c.feedback)
        
    def test_feedback_not_writable(self):
        c = hps.SectionContent(["foo","bar"],"weh")
        with self.assertRaises(AttributeError):
            c.feedback = "blah"

    def setup_parse_methods(self):
        hps.BlankLine.parse.side_effect = make_parse({"b":object()})
        hps.ChoiceBlock.parse.side_effect = make_parse({"c":hps.ChoiceBlock([],"a")})
        hps.InstructionBlock.parse.side_effect = make_parse({"i":hps.InstructionBlock("","b")})
        hps.TextBlock.parse.side_effect = make_parse({"t":hps.TextBlock("","c")})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("a")})
        hps.StarterLine.parse.side_effect = make_parse({"s":object()})
        
    mock_parse_methods = mock_statics(hps,"BlankLine.parse","ChoiceBlock.parse",
            "InstructionBlock.parse","TextBlock.parse","FeedbackLine.parse",
            "StarterLine.parse")
    
    @mock_parse_methods
    def test_parse_returns_populated_sectioncontent(self):
        self.setup_parse_methods()
        c = hps.ChoiceBlock([],"foo")
        hps.ChoiceBlock.parse.side_effect = make_parse({"c":c})
        i = hps.InstructionBlock("","bar")
        hps.InstructionBlock.parse.side_effect = make_parse({"i":i})
        t = hps.TextBlock("","weh")
        hps.TextBlock.parse.side_effect = make_parse({"t":t})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("blah"),"F":hps.FeedbackLine("yadda")})
        result = hps.SectionContent.parse(MockInput("fbFcit$"))
        self.assertTrue( isinstance(result,hps.SectionContent) )
        self.assertTrue( hasattr(result,"items") )
        self.assertEqual([c,i,t], result.items)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("blah yadda bar weh", result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.TextBlock.parse.side_effect = make_parse({"t":hps.TextBlock("",None)})
        hps.InstructionBlock.parse.side_effect = make_parse({"i":hps.InstructionBlock("",None)})
        result = hps.SectionContent.parse(MockInput("bcit$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_allows_no_blanklines_or_feedbacklines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.SectionContent.parse(MockInput("cit$")) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_blank_lines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.SectionContent.parse(MockInput("bbbcit$")) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_feedback_lines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.SectionContent.parse(MockInput("fffcit$")) )
        
    @mock_parse_methods
    def test_parse_checks_starterline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.StarterLine.parse.side_effect = make_parse({"f":object()})
        hps.TextBlock.parse.side_effect = make_parse({"f":hps.TextBlock("a","")})
        result = hps.SectionContent.parse(MockInput("f$"))
        self.assertIsNotNone( result )
        self.assertEqual(0, len(result.feedback))
        self.assertEqual(1, len(result.items))
        
    @mock_parse_methods
    def test_parse_expects_block(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.SectionContent.parse(MockInput("bbb$")) )
        
    @mock_parse_methods
    def test_parse_allows_many_mixed_blocks(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.SectionContent.parse(MockInput("btiicttci$")) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("bcit$")
        hps.SectionContent.parse(i)
        self.assertEqual(4, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("bbbbbb$")
        hps.SectionContent.parse(i)
        self.assertEqual(0, i.pos)
        
    @mock_parse_methods
    def test_parse_throws_error_for_consecutive_choice_blocks(self):
        self.setup_parse_methods()
        with self.assertRaises(hps.ValidationError):
            hps.SectionContent.parse(MockInput("cc$"))
        
    @mock_parse_methods
    def test_parse_doesnt_throw_error_for_nonconsecutive_choice_blocks(self):
        self.setup_parse_methods()
        hps.SectionContent.parse(MockInput("ctc$"))    
    
        
class TestBlankLine(unittest.TestCase):

    def test_construct(self):
        hps.BlankLine()

    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_returns_blankline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        result = hps.BlankLine.parse(MockInput("qwl"))
        self.assertTrue( isinstance(result,hps.BlankLine) )
        
    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_allows_no_quotemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.BlankLine.parse(MockInput("wl")) )
        
    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_allows_no_linewhitespace(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.BlankLine.parse(MockInput("ql")) )
            
    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_expects_newline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.BlankLine.parse(MockInput("qwz")) )
    
    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qwl")
        hps.BlankLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","LineWhitespace.parse","Newline.parse")    
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qwz")
        hps.BlankLine.parse(i)
        self.assertEqual(0, i.pos)
    
    
class TestChoiceBlock(unittest.TestCase):
    
    def test_construct(self):
        hps.ChoiceBlock([hps.Choice(None,"a","b","c",None)],None)
        
    def test_choices_readable(self):
        cc = hps.Choice(None,"a","b","c",None)
        c = hps.ChoiceBlock([cc],None)
        self.assertEqual(cc, c.choices[0])
        
    def test_choices_not_writable(self):
        c = hps.ChoiceBlock([hps.Choice(None,"a","b","c",None)],None)
        with self.assertRaises(AttributeError):
            c.choices = ["weh"]
            
    def test_choices_immutable(self):
        cc = hps.Choice(None,"a","b","c",None)
        c = hps.ChoiceBlock([cc],None)
        c.choices[0] = "blah"
        self.assertEqual(cc,c.choices[0])
        
    def test_feedback_readable(self):
        c = hps.ChoiceBlock([],"weh")
        self.assertEqual("weh", c.feedback)
        
    def test_feedback_not_writable(self):    
        c = hps.ChoiceBlock([],"weh")
        with self.assertRaises(AttributeError):
            c.feedback = "wibble"
            
    def test_is_completed_readable(self):
        c = hps.ChoiceBlock([],None)
        c.is_completed
        
    def test_is_completed_not_writable(self):
        c = hps.ChoiceBlock([],None)
        with self.assertRaises(AttributeError):
            c.is_completed = True

    def setup_parse_methods(self):
        hps.FirstChoice.parse.side_effect = make_parse({"C":hps.FirstChoice("a","b","c","d","e")})
        hps.Choice.parse.side_effect = make_parse({"c":hps.Choice("a","b","c","d","e")})
        hps.BlankLine.parse.side_effect = make_parse({"b":hps.BlankLine()})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("a")})
        hps.StarterLine.parse.side_effect = make_parse({"s":object()})
    
    mock_parse_methods = mock_statics(hps,"FirstChoice.parse","Choice.parse",
        "BlankLine.parse","FeedbackLine.parse","StarterLine.parse")
            
    @mock_parse_methods
    def test_parse_returns_populated_choiceblock(self):
        self.setup_parse_methods()
        c1 = hps.FirstChoice("a","b","c","d","wibble")
        c2 = hps.Choice("a","b","c","d","flibble")
        hps.FirstChoice.parse.side_effect = make_parse({"C":c1})
        hps.Choice.parse.side_effect = make_parse({"c":c2})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("blah"),"F":hps.FeedbackLine("yadda")})
        result = hps.ChoiceBlock.parse(MockInput("CfbFc$"))
        self.assertTrue( isinstance(result,hps.ChoiceBlock) )
        self.assertTrue( hasattr(result,"choices") )
        self.assertEqual( [c1,c2], result.choices )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual( "wibble blah yadda flibble", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.FirstChoice.parse.side_effect = make_parse({"C":hps.FirstChoice("a","b","c","d",None)})
        hps.Choice.parse.side_effect = make_parse({"c":hps.Choice("a","b","c","d",None)})
        result = hps.ChoiceBlock.parse(MockInput("Cc$"))
        self.assertIsNone( result.feedback )

    @mock_parse_methods        
    def test_parse_expects_firstchoice(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceBlock.parse(MockInput("c$")) )
        self.assertFalse( hps.BlankLine.parse.called )
        self.assertFalse( hps.Choice.parse.called )
        self.assertFalse( hps.FeedbackLine.parse.called )

    @mock_parse_methods              
    def test_parse_allows_multiple_choices(self):
        self.setup_parse_methods()
        result = hps.ChoiceBlock.parse(MockInput("Cccc$"))
        self.assertIsNotNone( result )
        self.assertEqual(4, len(result.choices) )
        self.assertEqual(7, len(result.feedback) )

    @mock_parse_methods        
    def test_parse_allows_multiple_blanklines(self):
        self.setup_parse_methods()
        result = hps.ChoiceBlock.parse(MockInput("Cbbbc$"))
        self.assertIsNotNone( result )
        self.assertEqual(2, len(result.choices) )
        self.assertEqual(3, len(result.feedback) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_feedbacklines(self):
        self.setup_parse_methods()
        result = hps.ChoiceBlock.parse(MockInput("Cfff$"))
        self.assertIsNotNone( result )
        self.assertEqual(1, len(result.choices) )
        self.assertEqual(7, len(result.feedback) )
        
    @mock_parse_methods
    def test_parse_checks_choice_before_feedbackline(self):
        self.setup_parse_methods()        
        hps.FeedbackLine.parse.side_effect = make_parse({"c":hps.FeedbackLine("a")})
        result = hps.ChoiceBlock.parse(MockInput("Cc$"))
        self.assertIsNotNone( result )
        self.assertEqual(2, len(result.choices) )
        self.assertEqual(3, len(result.feedback) )
        
    @mock_parse_methods
    def test_parse_checks_starterline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.StarterLine.parse.side_effect = make_parse({"f":object()})
        result = hps.ChoiceBlock.parse(MockInput("Cf$"))
        self.assertIsNotNone( result )
        self.assertEqual(1, len(result.choices) )
        self.assertEqual(1, len(result.feedback) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("Cbfcfb$")
        hps.ChoiceBlock.parse(i)
        self.assertEqual(6, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("c$")
        hps.ChoiceBlock.parse(i)
        self.assertEqual(0, i.pos)

    def test_is_completed_returns_true_for_mark(self):
        cb = hps.ChoiceBlock([
            hps.Choice(None,"a","b","c",None),
            hps.Choice("X","d","e","f",None)
        ],None)
        self.assertEqual(True, cb.is_completed)
        
    def test_is_completed_returns_true_for_feedback(self):
        cb = hps.ChoiceBlock([
            hps.Choice(None,"a","b","c","great"),
            hps.Choice(None,"d","e","f",None)
        ],"great")
        self.assertEqual(True, cb.is_completed)
        
    def test_is_completed_returns_false_for_no_marks_or_feedback(self):
        cb = hps.ChoiceBlock([
            hps.Choice(None,"a","b","c",None),
            hps.Choice(None,"d","e","f",None)
        ],None)
        self.assertEqual(False, cb.is_completed)


class TestFirstChoice(unittest.TestCase):

    def test_construct(self):
        hps.FirstChoice("foo","bar","weh","blah","wibble")
        
    def test_mark_readable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        self.assertEqual("foo",c.mark)
        
    def test_mark_not_writable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.mark = "wibble"
            
    def test_description_readable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        self.assertEqual("bar",c.description)
        
    def test_description_not_writable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.description = "wibble"
            
    def test_response_readable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        self.assertEqual("weh",c.response)
        
    def test_response_not_writable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.response = "wibble"
        
    def test_goto_readable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        self.assertEqual("blah",c.goto)
        
    def test_goto_not_writable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.goto = "wibble"

    def test_feedback_readable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        self.assertEqual("wibble",c.feedback)

    def test_feedback_not_writable(self):
        c = hps.FirstChoice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.feedback = "blarg"

    def setup_parse_methods(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"t":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarker.parse.side_effect = make_parse({"m":hps.ChoiceMarker("a")})
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("b","c","d","e")})
        
    mock_parse_methods = mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "ChoiceMarker.parse","LineWhitespace.parse","ChoiceContent.parse")

    @mock_parse_methods
    def test_parse_returns_populated_firstchoice(self):
        self.setup_parse_methods()
        hps.ChoiceMarker.parse.side_effect = make_parse({"m":hps.ChoiceMarker("foo")})
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("bar","weh","blah","wibble")})
        result = hps.FirstChoice.parse(MockInput("qtwmc$"))
        self.assertTrue( isinstance(result,hps.FirstChoice) )
        self.assertTrue( hasattr(result,"mark") )
        self.assertEqual( "foo", result.mark )
        self.assertTrue( hasattr(result,"description") )
        self.assertEqual( "bar", result.description )
        self.assertTrue( hasattr(result,"response") )
        self.assertEqual( "weh", result.response )
        self.assertTrue( hasattr(result,"goto") )
        self.assertEqual( "blah", result.goto )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual( "wibble", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("a","b","c",None)})
        result = hps.FirstChoice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_mark(self):
        self.setup_parse_methods()
        hps.ChoiceMarker.parse.side_effect = make_parse({"m":hps.ChoiceMarker(None)})
        result = hps.FirstChoice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.mark)
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_response(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("b",None,"d","e")})
        result = hps.FirstChoice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.response)
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_goto(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("b","c",None,"e")})
        result = hps.FirstChoice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.goto)
        
    @mock_parse_methods
    def test_parse_allows_no_quotemarker(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.FirstChoice.parse(MockInput("twmc$")) )

    @mock_parse_methods        
    def test_parse_expects_firsttextlinemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.FirstChoice.parse(MockInput("qwmc$")) )
        self.assertFalse( hps.ChoiceMarker.parse.called )
        self.assertFalse( hps.ChoiceContent.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_linewhitespace_after_textlinemarker(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.FirstChoice.parse(MockInput("qtmc$")) )

    @mock_parse_methods        
    def test_parse_expects_choicemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.FirstChoice.parse(MockInput("qtwc$")) )
        self.assertFalse( hps.ChoiceContent.parse.called )

    @mock_parse_methods        
    def test_parse_expects_choicecontent(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.FirstChoice.parse(MockInput("qtwm$")) )

    @mock_parse_methods            
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("qtwmc$")
        hps.FirstChoice.parse(i)
        self.assertEqual(5,i.pos)
    
    @mock_parse_methods        
    def test_parse_consumes_no_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("qtwm$")
        hps.FirstChoice.parse(i)
        self.assertEqual(0,i.pos)
        
    def test_can_set_mark(self):
        c = hps.FirstChoice(None,"foo",None,None,None)
        self.assertEqual(None, c.mark)
        c.set_mark("blah")
        self.assertEqual("blah", c.mark)
        

class TestChoice(unittest.TestCase):

    def test_construct(self):
        hps.Choice("foo","bar","weh","blah","wibble")
        
    def test_mark_readable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        self.assertEqual("foo",c.mark)
        
    def test_mark_not_writable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.mark = "wibble"
            
    def test_description_readable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        self.assertEqual("bar",c.description)
        
    def test_description_not_writable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.description = "wibble"
            
    def test_response_readable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        self.assertEqual("weh",c.response)
        
    def test_response_not_writable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.response = "wibble"
            
    def test_goto_readable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        self.assertEqual("blah",c.goto)
        
    def test_goto_not_writable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.goto = "wibble"
            
    def test_feedback_readable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        self.assertEqual("wibble",c.feedback)
            
    def test_feedback_not_writable(self):
        c = hps.Choice("foo","bar","weh","blah","wibble")
        with self.assertRaises(AttributeError):
            c.feedback = "meh"
            
    def setup_parse_methods(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"t":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarker.parse.side_effect = make_parse({"m":hps.ChoiceMarker("a")})
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("b","c","d","e")})
            
    mock_parse_methods = mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
        "ChoiceMarker.parse", "LineWhitespace.parse","ChoiceContent.parse")
            
    @mock_parse_methods
    def test_parse_returns_populated_choice(self):
        self.setup_parse_methods()
        hps.ChoiceMarker.parse.side_effect = make_parse({"m":hps.ChoiceMarker("foo")})
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("bar","weh","blah","wibble")})
        result = hps.Choice.parse(MockInput("qtwmc$"))
        self.assertTrue( isinstance(result,hps.Choice) )
        self.assertTrue( hasattr(result,"mark") )
        self.assertEqual( "foo", result.mark )
        self.assertTrue( hasattr(result,"description") )
        self.assertEqual( "bar", result.description )
        self.assertTrue( hasattr(result,"response") )
        self.assertEqual( "weh", result.response )
        self.assertTrue( hasattr(result,"goto") )
        self.assertEqual( "blah", result.goto )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual( "wibble", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("a","b","c",None)})
        result = hps.Choice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_response(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("a",None,"c","d")})
        result = hps.Choice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.response)
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_goto(self):
        self.setup_parse_methods()
        hps.ChoiceContent.parse.side_effect = make_parse({"c":hps.ChoiceContent("a","b",None,"d")})
        result = hps.Choice.parse(MockInput("qtwmc$"))
        self.assertIsNone(result.goto)
        
    @mock_parse_methods
    def test_parse_allows_no_quotemarker(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.Choice.parse(MockInput("twmc$")) )
        
    @mock_parse_methods
    def test_parse_expects_textlinemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Choice.parse(MockInput("qwmc$")) )
        self.assertFalse( hps.ChoiceMarker.parse.called )
        self.assertFalse( hps.ChoiceContent.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_linewhitespace_after_textlinemarker(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.Choice.parse(MockInput("qtmc$")) )
        
    @mock_parse_methods
    def test_parse_expects_choicemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Choice.parse(MockInput("qtwc$")) )
        self.assertFalse( hps.ChoiceContent.parse.called )
        
    @mock_parse_methods
    def test_parse_expects_choicecontent(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.Choice.parse(MockInput("qtwm$")) )
            
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("qtwmc$")
        hps.Choice.parse(i)
        self.assertEqual(5,i.pos)
        
    @mock_parse_methods
    def test_parse_consumes_no_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("qtwm$")
        hps.Choice.parse(i)
        self.assertEqual(0,i.pos)
        
    def test_can_set_mark(self):
        c = hps.Choice(None,"foo","bar","weh",None)
        self.assertEqual(None,c.mark)
        c.set_mark("lol")
        self.assertEqual("lol",c.mark)


class TestTextLineMarker(unittest.TestCase):

    def test_construct(self):
        hps.TextLineMarker()
        
    def test_parse_returns_textlinemarker(self):
        result = hps.TextLineMarker.parse(MockInput(":$"))
        self.assertTrue( isinstance(result,hps.TextLineMarker) )
        
    def test_parse_expects_colon(self):
        self.assertIsNone( hps.TextLineMarker.parse(MockInput("$")) )

    def test_parse_rejects_second_colon(self):
        self.assertIsNone( hps.TextLineMarker.parse(MockInput("::$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput(":$")
        hps.TextLineMarker.parse(i)
        self.assertEqual(1, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("$")
        hps.TextLineMarker.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceMarker(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceMarker("foo")
        
    def test_mark_is_readable(self):
        m = hps.ChoiceMarker("foo")
        self.assertEqual("foo",m.mark)
        
    def test_mark_is_not_writable(self):
        m = hps.ChoiceMarker("foo")
        with self.assertRaises(AttributeError):
            m.mark = "bar"
            
    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_returns_populated_choicemarker(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("foo")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        result = hps.ChoiceMarker.parse(MockInput("owtc"))
        self.assertTrue( isinstance(result,hps.ChoiceMarker) )
        self.assertTrue( hasattr(result,"mark") )
        self.assertEqual( "foo", result.mark )
        
    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_expects_choicemarkeropen(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        self.assertIsNone( hps.ChoiceMarker.parse(MockInput("wtc")) )
        self.assertFalse( hps.LineWhitespace.parse.called )
        self.assertFalse( hps.ChoiceMarkerMark.parse.called )
        self.assertFalse( hps.ChoiceMarkerClose.parse.called )
        
    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_allows_no_linewhitespace(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        self.assertIsNotNone( hps.ChoiceMarker.parse(MockInput("otc")) )

    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_allows_no_choicemarkermark(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        self.assertIsNotNone( hps.ChoiceMarker.parse(MockInput("owc")) )

    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_expects_choicemarkerclose(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        self.assertIsNone( hps.ChoiceMarker.parse(MockInput("owt$")) )

    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_consumes_input_on_success(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        i = MockInput("owtc")
        hps.ChoiceMarker.parse(i)
        self.assertEqual(4, i.pos)
        
    @mock_statics(hps,"ChoiceMarkerOpen.parse","LineWhitespace.parse",
            "ChoiceMarkerMark.parse","ChoiceMarkerClose.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.ChoiceMarkerOpen.parse.side_effect = make_parse({"o":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarkerMark.parse.side_effect = make_parse({"t":hps.ChoiceMarkerMark("a")})
        hps.ChoiceMarkerClose.parse.side_effect = make_parse({"c":object()})
        i = MockInput("owtz")
        hps.ChoiceMarker.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceMarkerOpen(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceMarkerOpen()
        
    def test_parse_returns_choicemarkeropen(self):
        result = hps.ChoiceMarkerOpen.parse(MockInput("[$"))
        self.assertTrue( isinstance(result,hps.ChoiceMarkerOpen) )

    def test_parse_expects_left_square(self):
        self.assertIsNone( hps.ChoiceMarkerOpen.parse(MockInput("$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("[$")
        hps.ChoiceMarkerOpen.parse(i)
        self.assertEqual(1, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("$")
        hps.ChoiceMarkerOpen.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceMarkerMark(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceMarkerMark("foo")
        
    def test_text_is_readable(self):
        c = hps.ChoiceMarkerMark("foo")
        self.assertEqual("foo", c.text)
        
    def test_text_is_not_writable(self):
        c = hps.ChoiceMarkerMark("foo")
        with self.assertRaises(AttributeError):
            c.text = "bar"
            
    def test_parse_returns_populated_choicemarkermark(self):
        result = hps.ChoiceMarkerMark.parse(MockInput("foo]"))
        self.assertTrue( isinstance(result,hps.ChoiceMarkerMark) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo", result.text)
        
    def test_parse_expects_non_right_square(self):
        self.assertIsNone( hps.ChoiceMarkerMark.parse(MockInput("]$")) )
        
    def test_parse_allows_multiple_non_right_square(self):
        self.assertIsNotNone( hps.ChoiceMarkerMark.parse(MockInput("a1%*>;@?]$")) )
        
    def text_parse_consumes_input_on_success(self):
        i = MockInput("foobar]$")
        hps.ChoiceMarkerMark.parse(i)
        self.assertEqual(6, i.pos)
        
    def text_parse_doesnt_consume_input_on_success(self):
        i = MockInput("]$")
        hps.ChoicemarkerMark.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceMarkerClose(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceMarkerClose()
        
    def test_parse_returns_choicemarkerclose(self):
        result = hps.ChoiceMarkerClose.parse(MockInput("]"))
        self.assertTrue( isinstance(result,hps.ChoiceMarkerClose) )
    
    def test_parse_expects_right_square(self):
        self.assertIsNone( hps.ChoiceMarkerClose.parse(MockInput("$")) )
    
    def test_parse_consumes_input_on_success(self):
        i = MockInput("]$")
        hps.ChoiceMarkerClose.parse(i)
        self.assertEqual(1, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("$")
        hps.ChoiceMarkerClose.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceDescription(unittest.TestCase):
    
    def test_construct(self):
        hps.ChoiceDescription("foo bar","weh")
        
    def test_text_readable(self):
        d = hps.ChoiceDescription("foo bar","weh")
        self.assertEqual("foo bar",d.text)
    
    def test_parts_not_writable(self):
        d = hps.ChoiceDescription("foo bar","weh")
        with self.assertRaises(AttributeError):
            d.text = "weh"
            
    def test_feedback_readable(self):
        d = hps.ChoiceDescription("foo bar","weh")
        self.assertEqual("weh", d.feedback)
        
    def test_feedback_not_writable(self):
        d = hps.ChoiceDescription("foo bar","weh")
        with self.assertRaises(AttributeError):
            d.feedback = "blah"

    def setup_parse_methods(self):
        hps.ChoiceDescPart.parse.side_effect = make_parse({"p":hps.ChoiceDescPart("a")})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline("b")})

    mock_parse_methods = mock_statics(hps,"ChoiceDescPart.parse","ChoiceDescNewline.parse")

    @mock_parse_methods
    def test_parse_returns_populated_choicedescription(self):
        self.setup_parse_methods()
        hps.ChoiceDescPart.parse.side_effect = make_parse({
            "p":hps.ChoiceDescPart("blah"),
            "d":hps.ChoiceDescPart("yadda"),
            "q":hps.ChoiceDescPart("weh")})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({
            "n":hps.ChoiceDescNewline("foo"),
            "N":hps.ChoiceDescNewline("bar")})
        result = hps.ChoiceDescription.parse(MockInput("pndNq$"))
        self.assertTrue( isinstance(result,hps.ChoiceDescription) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("blah yadda weh", result.text)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("foo bar", result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline(None)})
        result = hps.ChoiceDescription.parse(MockInput("pnpnp$"))
        self.assertIsNone( result.feedback )

    @mock_parse_methods        
    def test_parse_expects_part(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceDescription.parse(MockInput("z$")) )
        self.assertEqual( 1, hps.ChoiceDescPart.parse.call_count )
        self.assertFalse( hps.ChoiceDescNewline.parse.called )

    @mock_parse_methods        
    def test_parse_allows_single_part(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescription.parse(MockInput("p$")) )
        self.assertEqual( 1, hps.ChoiceDescPart.parse.call_count )

    @mock_parse_methods        
    def test_parse_expects_choicedescnewline_for_second_part(self):
        self.setup_parse_methods()
        result = hps.ChoiceDescription.parse(MockInput("pp$"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text))

    @mock_parse_methods
    def test_parse_expects_part_for_second_part(self):
        self.setup_parse_methods()
        result = hps.ChoiceDescription.parse(MockInput("pn$"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text))

    @mock_parse_methods        
    def test_parse_allows_multiple_parts(self):
        self.setup_parse_methods()
        result = hps.ChoiceDescription.parse(MockInput("pnpnpnp$"))
        self.assertIsNotNone(result)
        self.assertEqual(7, len(result.text))

    @mock_parse_methods        
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("pnp$")
        hps.ChoiceDescription.parse(i)
        self.assertEqual(3, i.pos)

    @mock_parse_methods        
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("$")
        hps.ChoiceDescription.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceDescPart(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceDescPart("foo")
        
    def test_text_readable(self):
        p = hps.ChoiceDescPart("foo")
        self.assertEqual("foo", p.text)
        
    def test_text_not_writable(self):
        p = hps.ChoiceDescPart("foo")
        with self.assertRaises(AttributeError):
            p.text = "bar"
                
    def test_parse_returns_populated_choicedescpart(self):
        result = hps.ChoiceDescPart.parse(MockInput("foobar\x00"))
        self.assertTrue( isinstance(result,hps.ChoiceDescPart) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foobar", result.text)
    
    def test_parse_trims_whitespace(self):
        result = hps.ChoiceDescPart.parse(MockInput("    foo  \x00"))
        self.assertEqual("foo",result.text)
    
    def test_parse_allows_single_hyphen(self):
        self.assertIsNotNone( hps.ChoiceDescPart.parse(MockInput("-\x00")) )
        
    def test_parse_doesnt_allow_double_hyphen(self):
        self.assertIsNone( hps.ChoiceDescPart.parse(MockInput("--\x00")) )
        
    def test_parse_allows_multiple_chars_numbers_and_punctuation(self):
        result = hps.ChoiceDescPart.parse(MockInput("a0b!7c%\x00"))
        self.assertIsNotNone(result)
        self.assertEqual(7, len(result.text) )
        
    def test_parse_allows_spaces_and_tabs(self):
        result = hps.ChoiceDescPart.parse(MockInput(" \t \tT\x00"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("abc\x00")
        hps.ChoiceDescPart.parse(i)
        self.assertEqual(3, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("--\x00")
        hps.ChoiceDescPart.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceResponse(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceResponse("foo","bar","weh")
    
    def test_description_readable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        self.assertEqual("foo", r.description)
        
    def test_description_not_writable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        with self.assertRaises(AttributeError):
            r.description = "weh"
            
    def test_goto_readable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        self.assertEqual("bar",r.goto)
        
    def test_goto_not_writable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        with self.assertRaises(AttributeError):
            r.goto = "weh"
            
    def test_feedback_readable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        self.assertEqual("weh",r.feedback)
        
    def test_feedback_not_writable(self):
        r = hps.ChoiceResponse("foo","bar","weh")
        with self.assertRaises(AttributeError):
            r.feedback = "wibble"
        
    def setup_parse_methods(self):
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline("z")})
        hps.ChoiceResponseSeparator.parse.side_effect = make_parse({"s":object()})
        hps.ChoiceResponseDesc.parse.side_effect = make_parse({"d":hps.ChoiceResponseDesc("a","g")})
        hps.ChoiceGoto.parse.side_effect = make_parse({"g":hps.ChoiceGoto("b","c")})
        
    mock_parse_methods = mock_statics(hps,"ChoiceResponseSeparator.parse",
        "ChoiceDescNewline.parse","ChoiceResponseDesc.parse","ChoiceGoto.parse")

    @mock_parse_methods        
    def test_parse_returns_populated_choiceresponse(self):
        self.setup_parse_methods()
        hps.ChoiceResponseDesc.parse.side_effect = make_parse({"d":hps.ChoiceResponseDesc("foo","wibble")})
        hps.ChoiceGoto.parse.side_effect = make_parse({"g":hps.ChoiceGoto("bar","blarg")})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({
            "n":hps.ChoiceDescNewline("jibber"),
            "N":hps.ChoiceDescNewline("jabber")})
        result = hps.ChoiceResponse.parse(MockInput("nsNdg$"))
        self.assertTrue( isinstance(result,hps.ChoiceResponse) )
        self.assertTrue( hasattr(result,"description") )
        self.assertEqual("foo", result.description)
        self.assertTrue( hasattr(result,"goto") )
        self.assertEqual("bar", result.goto)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("jibber jabber wibble blarg", result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceResponseDesc.parse.side_effect = make_parse({"d":hps.ChoiceResponseDesc("foo",None)})
        hps.ChoiceGoto.parse.side_effect = make_parse({"g":hps.ChoiceGoto("weh",None)})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline(None)})
        result = hps.ChoiceResponse.parse(MockInput("sndg$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_responsedesc(self):
        self.setup_parse_methods()
        result = hps.ChoiceResponse.parse(MockInput("sg$"))
        self.assertIsNone(result.description)
    
    @mock_parse_methods
    def test_parse_sets_none_for_empty_responsedesc(self):
        self.setup_parse_methods()
        hps.ChoiceResponseDesc.parse.side_effect = make_parse({"d":hps.ChoiceResponseDesc("",None)})
        result = hps.ChoiceResponse.parse(MockInput("sndg$"))
        self.assertIsNone(result.description)
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_goto(self):
        self.setup_parse_methods()
        result = hps.ChoiceResponse.parse(MockInput("snd$"))
        self.assertIsNone(result.goto)

    @mock_parse_methods        
    def test_parse_allows_no_first_choicedescnewline(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceResponse.parse(MockInput("sndg$")) )

    @mock_parse_methods        
    def test_parse_expects_choiceresponseseparator(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceResponse.parse(MockInput("n$")) )
        self.assertFalse( hps.ChoiceResponseDesc.parse.called )
        self.assertFalse( hps.ChoiceGoto.parse.called )

    @mock_parse_methods        
    def test_parse_allows_no_choicedescnewline_for_choiceresponsedesc(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceResponse.parse(MockInput("nsdg$")) )
    
    @mock_parse_methods    
    def test_parse_allows_choicegoto_and_no_choiceresponsedesc(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceResponse.parse(MockInput("nsg$")) )

    @mock_parse_methods        
    def test_parse_allows_choiceresponsedesc_and_no_choicegoto(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceResponse.parse(MockInput("nsnd$")) )

    @mock_parse_methods        
    def test_parse_expects_either_choiceresponsedesc_or_choicegoto(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceResponse.parse(MockInput("ns$")) )

    @mock_parse_methods        
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("nsndg$")
        hps.ChoiceResponse.parse(i)
        self.assertEqual(5, i.pos)

    @mock_parse_methods        
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("nsn$")
        hps.ChoiceResponse.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceResponseSeparator(unittest.TestCase):

    def test_construc(self):
        hps.ChoiceResponseSeparator()
        
    def test_parse_returns_choiceresponseseparator(self):
        result = hps.ChoiceResponseSeparator.parse(MockInput("--$"))
        self.assertTrue( isinstance(result,hps.ChoiceResponseSeparator) )
        
    def test_parse_expects_first_hyphen(self):
        self.assertIsNone( hps.ChoiceResponseSeparator.parse(MockInput("$")) )

    def test_parse_expects_second_hyphen(self):
        self.assertIsNone( hps.ChoiceResponseSeparator.parse(MockInput("-$")) )

    def test_parse_consumes_input_on_success(self):
        i = MockInput("--$")
        hps.ChoiceResponseSeparator.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("-$")
        hps.ChoiceResponseSeparator.parse(i)
        self.assertEqual(0, i.pos)        


class TestChoiceResponseDesc(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceResponseDesc("foo bar","weh")

    def test_text_readable(self):
        d = hps.ChoiceResponseDesc("foo bar","weh")
        self.assertEqual("foo bar", d.text)
        
    def test_text_not_writable(self):
        d = hps.ChoiceResponseDesc("foo bar","weh")
        with self.assertRaises(AttributeError):
            d.text = "weh"

    def test_feedback_readable(self):
        d = hps.ChoiceResponseDesc("foo bar","weh")
        self.assertEqual("weh",d.feedback)
        
    def test_feedback_not_writable(self):
        d = hps.ChoiceResponseDesc("foo bar","weh")
        with self.assertRaises(AttributeError):
            d.feedback = "blarg"

    def setup_parse_methods(self):
        hps.ChoiceResponseDescPart.parse.side_effect = make_parse({"p":hps.ChoiceResponseDescPart("a")})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline("b")})

    mock_parse_methods = mock_statics(hps,"ChoiceResponseDescPart.parse","ChoiceDescNewline.parse")

    @mock_parse_methods
    def test_parse_returns_populated_choiceresponsedesc(self):
        self.setup_parse_methods()
        hps.ChoiceResponseDescPart.parse.side_effect = make_parse({
            "p":hps.ChoiceResponseDescPart("blah"),
            "d":hps.ChoiceResponseDescPart("yadda"),
            "q":hps.ChoiceResponseDescPart("wibble")})
        hps.ChoiceDescNewline.parse.side_effect = make_parse({
            "n":hps.ChoiceDescNewline("weh"),
            "N":hps.ChoiceDescNewline("blarg")})
        result = hps.ChoiceResponseDesc.parse(MockInput("pndNq$"))
        self.assertTrue( isinstance(result,hps.ChoiceResponseDesc) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("blah yadda wibble", result.text)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("weh blarg", result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"n":hps.ChoiceDescNewline(None)})
        result = hps.ChoiceResponseDesc.parse(MockInput("pnp$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_expects_first_part(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceResponseDesc.parse(MockInput("z$")) )
        self.assertFalse( hps.ChoiceDescNewline.parse.called )

    @mock_parse_methods        
    def test_parse_expects_choicedescnewline_for_second_part(self):
        self.setup_parse_methods()
        result = hps.ChoiceResponseDesc.parse(MockInput("pp$"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text))

    @mock_parse_methods        
    def test_parse_expects_part_for_second_part(self):
        self.setup_parse_methods()
        result = hps.ChoiceResponseDesc.parse(MockInput("pn$"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text))

    @mock_parse_methods        
    def test_parse_allows_multiple_parts(self):
        self.setup_parse_methods()
        result = hps.ChoiceResponseDesc.parse(MockInput("pnpnpnp$"))
        self.assertIsNotNone(result)
        self.assertEqual(7, len(result.text))

    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("pnp$")
        hps.ChoiceResponseDesc.parse(i)
        self.assertEqual(3, i.pos)

    @mock_parse_methods        
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("z$")
        hps.ChoiceResponseDesc.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceResponseDescPart(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceResponseDescPart("foo")
        
    def test_text_readable(self):
        p = hps.ChoiceResponseDescPart("foo")
        self.assertEqual("foo",p.text)
        
    def test_text_not_writable(self):
        p = hps.ChoiceResponseDescPart("foo")
        with self.assertRaises(AttributeError):
            p.text = "blah"
            
    def test_parse_returns_populated_choiceresponsedescpart(self):
        result = hps.ChoiceResponseDescPart.parse(MockInput("foo\x00"))
        self.assertTrue( isinstance(result,hps.ChoiceResponseDescPart) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo", result.text)

    def test_parse_trims_whitespace(self):
        result = hps.ChoiceResponseDescPart.parse(MockInput("    foo   \x00"))
        self.assertEqual("foo", result.text)

    def test_parse_allows_got(self):
        result = hps.ChoiceResponseDescPart.parse(MockInput("GO T\x00"))
        self.assertIsNotNone(result)
        self.assertEqual(4, len(result.text))
        
    def test_parse_doesnt_allow_goto(self):
        self.assertIsNone( hps.ChoiceResponseDescPart.parse(MockInput("GO TO\x00")) )

    def test_parse_allows_chars_nums_and_punctuation(self):
        result = hps.ChoiceResponseDescPart.parse(MockInput("a0f!7%\x00"))
        self.assertIsNotNone(result)
        self.assertEqual(6, len(result.text) )
        
    def test_parse_allows_space_and_tab(self):
        result = hps.ChoiceResponseDescPart.parse(MockInput(" \t \tT\x00"))
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.text))

    def test_parse_consumes_input_on_sucess(self):
        i = MockInput("foo\x00")
        hps.ChoiceResponseDescPart.parse(i)
        self.assertEqual(3, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("GO TO\x00")
        hps.ChoiceResponseDescPart.parse(i)
        self.assertEqual(0, i.pos)
        

class TestChoiceGoto(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceGoto("foo","wibble")
    
    def test_secname_readable(self):
        g = hps.ChoiceGoto("foo","wibble")
        self.assertEqual("foo",g.secname)
        
    def test_secname_not_writable(self):
        g = hps.ChoiceGoto("foo","wibble")
        with self.assertRaises(AttributeError):
            g.secname = "bar"
            
    def test_feedback_readable(self):    
        g = hps.ChoiceGoto("foo","wibble")
        self.assertEqual("wibble",g.feedback)
        
    def test_feedback_not_writable(self):
        g = hps.ChoiceGoto("foo","wibble")
        with self.assertRaises(AttributeError):
            g.feedback = "blarg"
            
    def setup_parse_methods(self):
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"l":hps.ChoiceDescNewline("a")})
        hps.GotoMarker.parse.side_effect = make_parse({"m":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("a")})
        hps.EndPunctuation.parse.side_effect = make_parse({"e":object()})
        
    mock_parse_methods = mock_statics(hps,"GotoMarker.parse","LineWhitespace.parse",
            "Name.parse","EndPunctuation.parse","ChoiceDescNewline.parse")
            
    @mock_parse_methods
    def test_parse_returns_choicegoto(self):
        self.setup_parse_methods()
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"l":hps.ChoiceDescNewline("jibber")})
        hps.Name.parse.side_effect = make_parse({"n":hps.Name("foobar")})
        result = hps.ChoiceGoto.parse(MockInput("lmwne$"))
        self.assertTrue( isinstance(result,hps.ChoiceGoto) )
        self.assertTrue( hasattr(result,"secname") )
        self.assertEqual( "foobar", result.secname )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual( "jibber", result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceDescNewline.parse.side_effect = make_parse({"l":hps.ChoiceDescNewline(None)})
        result = hps.ChoiceGoto.parse(MockInput("lmwne$"))
        self.assertIsNone(result.feedback)

    @mock_parse_methods
    def test_parse_allows_no_choicedescnewline(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceGoto.parse(MockInput("mwne$")) )

    @mock_parse_methods
    def test_parse_expects_gotomarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceGoto.parse(MockInput("lwne$")) )
        self.assertFalse( hps.LineWhitespace.parse.called )
        self.assertFalse( hps.Name.parse.called )
        self.assertFalse( hps.EndPunctuation.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_linewhitespace(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceGoto.parse(MockInput("lmne$")) )
        
    @mock_parse_methods
    def test_parse_expects_name(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceGoto.parse(MockInput("lmwe$")) )
        self.assertFalse( hps.EndPunctuation.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_endpunctuation(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceGoto.parse(MockInput("lmwn$")) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("lmwne$")
        hps.ChoiceGoto.parse(i)
        self.assertEqual(5,i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("lmwq$")
        hps.ChoiceGoto.parse(i)
        self.assertEqual(0,i.pos)


class TestGotoMarker(unittest.TestCase):

    def test_construct(self):
        hps.GotoMarker()
        
    def test_parse_returns_gotomarker(self):
        result = hps.GotoMarker.parse(MockInput("GO TO$"))
        self.assertTrue( isinstance(result,hps.GotoMarker) )
        
    def test_parse_expects_g(self):
        self.assertIsNone( hps.GotoMarker.parse(MockInput("O TO$")) )
        
    def test_parse_expects_first_o(self):
        self.assertIsNone( hps.GotoMarker.parse(MockInput("G TO$")) )
        
    def test_parse_expects_space(self):
        self.assertIsNone( hps.GotoMarker.parse(MockInput("GOTO$")) )
        
    def test_parse_expects_t(self):
        self.assertIsNone( hps.GotoMarker.parse(MockInput("GO O$")) )
        
    def test_parse_expects_second_o(self):
        self.assertIsNone( hps.GotoMarker.parse(MockInput("GO T$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("GO TO$")
        hps.GotoMarker.parse(i)
        self.assertEqual(5, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("GO TP$")
        hps.GotoMarker.parse(i)


class TestEndPunctuation(unittest.TestCase):

    def test_construct(self):
        hps.EndPunctuation()
        
    def test_parse_returns_endpunctuation(self):
        result = hps.EndPunctuation.parse(MockInput(".$"))
        self.assertTrue( isinstance(result,hps.EndPunctuation) )
        
    def test_parse_expects_punc_char(self):
        self.assertIsNone( hps.EndPunctuation.parse(MockInput("g$")) )
        
    def test_parse_allows_comma(self):
        self.assertIsNotNone( hps.EndPunctuation.parse(MockInput(",$")) )
        
    def test_parse_allows_colon(self):
        self.assertIsNotNone( hps.EndPunctuation.parse(MockInput(":$")) )
        
    def test_parse_allows_semicolon(self):
        self.assertIsNotNone( hps.EndPunctuation.parse(MockInput(";$")) )
        
    def test_parse_allows_exclaimation(self):
        self.assertIsNotNone( hps.EndPunctuation.parse(MockInput("!$")) )
        
    def test_parse_allows_question(self):
        self.assertIsNotNone( hps.EndPunctuation.parse(MockInput("?$")) )
        
    def test_parse_allows_multiple_punc_chars(self):
        i = MockInput(",!?$")
        self.assertIsNotNone( hps.EndPunctuation.parse(i) )
        self.assertEqual(3, i.pos)
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput(".$")
        hps.EndPunctuation.parse(i)
        self.assertEqual(1,i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("g$")
        hps.EndPunctuation.parse(i)
        self.assertEqual(0,i.pos)
        

class TestInstructionBlock(unittest.TestCase):
    
    def test_construct(self):
        hps.InstructionBlock("foo","bar")

    def test_text_readable(self):
        b = hps.InstructionBlock("foo","bar")
        self.assertEqual("foo",b.text)
        
    def test_text_not_writable(self):
        b = hps.InstructionBlock("foo","bar")
        with self.assertRaises(AttributeError):
            b.text = "weh"

    def test_feedback_readable(self):
        b = hps.InstructionBlock("foo","bar")
        self.assertEqual("bar",b.feedback)
        
    def test_feedback_not_writable(self):
        b = hps.InstructionBlock("foo","bar")
        with self.assertRaises(AttributeError):
            b.feedback = "weh"

    def setup_parse_methods(self):
        hps.FirstInstructionLine.parse.side_effect = make_parse({"I":hps.FirstInstructionLine("a")})
        hps.InstructionLine.parse.side_effect = make_parse({"i":hps.InstructionLine("b")})
        hps.BlankLine.parse.side_effect = make_parse({"b":hps.BlankLine()})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("c")})
        hps.StarterLine.parse.side_effect = make_parse({"s":object()})

    mock_parse_methods = mock_statics(hps,"FirstInstructionLine.parse",
            "InstructionLine.parse","BlankLine.parse","FeedbackLine.parse",
            "StarterLine.parse")

    @mock_parse_methods
    def test_parse_returns_instructionblock(self):
        self.setup_parse_methods()
        l1 = hps.FirstInstructionLine("foo")
        l2 = hps.InstructionLine("bar")
        hps.FirstInstructionLine.parse.side_effect = make_parse({"I":l1})
        hps.InstructionLine.parse.side_effect = make_parse({"i":l2})
        f1 = hps.FeedbackLine("blah")
        f2 = hps.FeedbackLine("yadda")
        hps.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
        result = hps.InstructionBlock.parse(MockInput("IfbFi$"))
        self.assertTrue( isinstance(result,hps.InstructionBlock) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo bar", result.text)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("blah yadda", result.feedback)
                
    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        result = hps.InstructionBlock.parse(MockInput("I$"))
        self.assertIsNone( result.feedback )
            
    @mock_parse_methods
    def test_parse_expects_firstinstructionline(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.InstructionBlock.parse(MockInput("i$")) )
        self.assertFalse( hps.InstructionLine.parse.called )
        self.assertFalse( hps.BlankLine.parse.called )
        self.assertFalse( hps.FeedbackLine.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_multiple_instructionlines(self):
        self.setup_parse_methods()
        result = hps.InstructionBlock.parse(MockInput("Iii$"))
        self.assertIsNotNone( result )
        self.assertEqual(5, len(result.text) )
        self.assertEqual(None, result.feedback)
            
    @mock_parse_methods
    def test_parse_allows_multiple_blank_lines(self):
        self.setup_parse_methods()
        result = hps.InstructionBlock.parse(MockInput("Ibbbi$"))
        self.assertIsNotNone( result )
        self.assertEqual(3,len(result.text))
        self.assertEqual(None,result.feedback)
        
    @mock_parse_methods
    def test_parse_allows_multiple_feedback_lines(self):
        self.setup_parse_methods()
        result = hps.InstructionBlock.parse(MockInput("Ifff$"))
        self.assertIsNotNone( result )
        self.assertEqual(1,len(result.text))
        self.assertEqual(5,len(result.feedback))
        
    @mock_parse_methods
    def test_parse_checks_instructionline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.FeedbackLine.parse.side_effect = make_parse({"i":hps.FeedbackLine("c")})
        result = hps.InstructionBlock.parse(MockInput("Ii$"))
        self.assertIsNotNone( result )
        self.assertEqual(3,len(result.text))
        self.assertEqual(None,result.feedback)
        
    @mock_parse_methods
    def test_parse_checks_starterline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.StarterLine.parse.side_effect = make_parse({"f":object()})
        result = hps.InstructionBlock.parse(MockInput("If$"))
        self.assertIsNotNone( result )
        self.assertEqual(1,len(result.text))
        self.assertEqual(None,result.feedback)
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("Ifbfib$")
        hps.InstructionBlock.parse(i)
        self.assertEqual(6,i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("i$")
        hps.InstructionBlock.parse(i)
        self.assertEqual(0,i.pos)


class TestInstructionLine(unittest.TestCase):
    
    def test_construct(self):
        hps.InstructionLine("foo")
        
    def test_text_readable(self):
        l = hps.InstructionLine("foo")
        self.assertEqual("foo",l.text)
        
    def test_text_not_writable(self):
        l = hps.InstructionLine("foo")
        with self.assertRaises(AttributeError):
            l.text = "bar"
    
    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_returns_populated_instructionline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        c = hps.TextLineContent("foobar")
        hps.TextLineContent.parse.side_effect = make_parse({"c":c})
        result = hps.InstructionLine.parse(MockInput("qic$"))
        self.assertTrue( isinstance(result,hps.InstructionLine) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual( "foobar", result.text )
        
    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_allows_no_quote_marker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNotNone( hps.InstructionLine.parse(MockInput("ic$")) )

    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_instructionlinemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNone( hps.InstructionLine.parse(MockInput("qc$")) )
        self.assertFalse( hps.TextLineContent.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_textlinecontent(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNone( hps.InstructionLine.parse(MockInput("qi$")) )
        
    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        i = MockInput("qic$")
        hps.InstructionLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","InstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.InstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        i = MockInput("qi$")
        hps.InstructionLine.parse(i)
        self.assertEqual(0, i.pos)


class TestInstructionLineMarker(unittest.TestCase):

    def test_construct(self):
        hps.InstructionLineMarker()
        
    def test_parse_returns_instructionlinemarker(self):
        result = hps.InstructionLineMarker.parse(MockInput("%$"))
        self.assertTrue( isinstance(result,hps.InstructionLineMarker) )

    def test_parse_expects_percent(self):
        self.assertIsNone( hps.InstructionLineMarker.parse(MockInput("z$")) )

    def test_parse_rejects_second_percent(self):
        self.assertIsNone( hps.InstructionLineMarker.parse(MockInput("%%$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("%$")
        hps.InstructionLineMarker.parse(i)
        self.assertEqual(1,i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("$")
        hps.InstructionLineMarker.parse(i)
        self.assertEqual(0,i.pos)
        
        
class TestLineText(unittest.TestCase):

    def test_construct(self):
        hps.LineText("foo")
        
    def test_text_readable(self):
        t = hps.LineText("foo")
        self.assertEqual("foo", t.text)
        
    def test_text_not_writable(self):
        t = hps.LineText("foo")
        with self.assertRaises(AttributeError):
            t.text = "bar"
            
    def test_parse_returns_populated_linetext(self):
        result = hps.LineText.parse(MockInput("foo\x00"))
        self.assertTrue( isinstance(result,hps.LineText) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo", result.text)

    def test_parse_trims_whitespace(self):
        result = hps.LineText.parse(MockInput("   foo  \x00"))
        self.assertEqual("foo", result.text)
            
    def test_parse_expects_char(self):
        self.assertIsNone( hps.LineText.parse(MockInput("\x00")) )
        
    def test_parse_allows_multiple_alpha_number_or_punc_chars(self):
        result = hps.LineText.parse(MockInput("a7!f-G.\x00")) 
        self.assertIsNotNone( result )
        self.assertEqual( 7, len(result.text) )
        
    def test_parse_allows_space_and_tab(self):
        result = hps.LineText.parse(MockInput(" \t \tT\x00"))
        self.assertIsNotNone( result )
        self.assertEqual( 1, len(result.text) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("foo\x00")
        hps.LineText.parse(i)
        self.assertEqual(3,i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("\x00")
        hps.LineText.parse(i)
        self.assertEqual(0,i.pos)


class TestTextBlock(unittest.TestCase):

    def test_construct(self):
        hps.TextBlock("foo","bar")
        
    def test_text_readable(self):
        b = hps.TextBlock("foo","bar")
        self.assertEqual("foo",b.text)
        
    def test_lines_not_writable(self):
        b = hps.TextBlock("foo","bar")
        with self.assertRaises(AttributeError):
            b.text = "weh"
            
    def test_feedback_readable(self):
        b = hps.TextBlock("foo","bar")
        self.assertEqual("bar",b.feedback)
        
    def test_feedback_not_writable(self):
        b = hps.TextBlock("foo","bar")
        with self.assertRaises(AttributeError):
            b.feedback = "weh"
    
    def setup_parse_methods(self):
        hps.FirstTextLine.parse.side_effect = make_parse({"T":hps.FirstTextLine("a")})
        hps.TextLine.parse.side_effect = make_parse({"t":hps.TextLine("b")})
        hps.BlankLine.parse.side_effect = make_parse({"b":hps.BlankLine()})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("c")})
        hps.StarterLine.parse.side_effect = make_parse({"s":object()})
        
    mock_parse_methods = mock_statics(hps,"TextLine.parse","BlankLine.parse","FeedbackLine.parse",
            "FirstTextLine.parse","StarterLine.parse")
    
    @mock_parse_methods
    def test_parse_returns_populated_textblock(self):
        self.setup_parse_methods()
        t1 = hps.FirstTextLine("foo")
        t2 = hps.TextLine("bar")
        hps.FirstTextLine.parse.side_effect = make_parse({"t":t1})
        hps.TextLine.parse.side_effect = make_parse({"T":t2})
        f1 = hps.FeedbackLine("blah")
        f2 = hps.FeedbackLine("yadda")
        hps.FeedbackLine.parse.side_effect = make_parse({"f":f1,"F":f2})
        result = hps.TextBlock.parse(MockInput("tfbFT$"))
        self.assertTrue( isinstance(result,hps.TextBlock) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo bar", result.text)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("blah yadda", result.feedback)    
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        result = hps.TextBlock.parse(MockInput("T$"))
        self.assertIsNone(result.feedback)
            
    @mock_parse_methods
    def test_parse_expects_firsttextline(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.TextBlock.parse(MockInput("t$")) )
        self.assertFalse( hps.BlankLine.parse.called )
        self.assertFalse( hps.TextLine.parse.called )
        self.assertFalse( hps.FeedbackLine.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_single_line(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.TextBlock.parse(MockInput("T$")) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_textlines(self):
        self.setup_parse_methods()
        result = hps.TextBlock.parse(MockInput("Ttt$"))
        self.assertIsNotNone( result )
        self.assertEqual(5, len(result.text) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_blanklines(self):
        self.setup_parse_methods()
        result = hps.TextBlock.parse(MockInput("Tbbbt$"))
        self.assertIsNotNone( result )
        self.assertEqual( 3, len(result.text) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_feedbacklines(self):
        self.setup_parse_methods()
        result = hps.TextBlock.parse(MockInput("Tfff$")) 
        self.assertIsNotNone( result )
        self.assertEqual( 5, len(result.feedback) )

    @mock_parse_methods
    def test_parse_checks_textline_before_feedbackline(self):
        self.setup_parse_methods()        
        hps.FeedbackLine.parse.side_effect = make_parse({"t":hps.FeedbackLine("a")})
        result = hps.TextBlock.parse(MockInput("Tt$")) 
        self.assertIsNotNone( result )
        self.assertEqual( 3, len(result.text) )
        self.assertEqual( None, result.feedback )
        
    @mock_parse_methods
    def test_parse_checks_starterline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.StarterLine.parse.side_effect = make_parse({"f":object()})
        result = hps.TextBlock.parse(MockInput("Tf$")) 
        self.assertIsNotNone( result )
        self.assertEqual( 1, len(result.text) )
        self.assertEqual( None, result.feedback )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("Ttf$")
        hps.TextBlock.parse(i)
        self.assertEqual(3,i.pos)
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("t$")
        hps.TextBlock.parse(i)
        self.assertEqual(0,i.pos)


class TestTextLine(unittest.TestCase):
    
    def test_construct(self):
        hps.TextLine("foo")
        
    def test_text_readable(self):
        l = hps.TextLine("foo")
        self.assertEqual("foo", l.text)
        
    def test_text_not_writable(self):
        l = hps.TextLine("foo")
        with self.assertRaises(AttributeError):
            l.text = "bar"
            
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_returns_populated_textline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("foo")})
        result = hps.TextLine.parse(MockInput("qmc$"))
        self.assertTrue( isinstance(result, hps.TextLine) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo", result.text)
        
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_allows_no_quote_marker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("bar")})
        self.assertIsNotNone( hps.TextLine.parse(MockInput("mc$")) )
        
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_textlinemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("weh")})
        self.assertIsNone( hps.TextLine.parse(MockInput("qc$")) )
        self.assertFalse( hps.TextLineContent.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_textlinecontent(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("weh")})
        self.assertIsNone( hps.TextLine.parse(MockInput("qm$")) )
        
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("blah")})
        i = MockInput("qmc$")
        hps.TextLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","TextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"c":hps.TextLineContent("wibble")})
        i = MockInput("qm$")
        hps.TextLine.parse(i)
        self.assertEqual(0, i.pos)


class TestFeedbackLine(unittest.TestCase):
    
    def test_construct(self):
        hps.FeedbackLine("foo")
        
    def test_text_readable(self):
        l = hps.FeedbackLine("foo")
        self.assertEqual("foo", l.text)
        
    def test_text_not_writable(self):
        l = hps.FeedbackLine("foo")
        with self.assertRaises(AttributeError):
            l.text = "bar"
            
    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_returns_populated_feedbackline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        result = hps.FeedbackLine.parse(MockInput("qtl$"))
        self.assertTrue( isinstance(result,hps.FeedbackLine) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual( "foo", result.text )
    
    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_allows_no_quotemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.FeedbackLine.parse(MockInput("tl$")) )
    
    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_expects_linetext(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.FeedbackLine.parse(MockInput("ql$")) )
        self.assertFalse( hps.Newline.parse.called )

    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_expects_newline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.FeedbackLine.parse(MockInput("qt$")) )
    
    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qtl$")
        hps.FeedbackLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","LineText.parse","Newline.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("a")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("qt$")
        hps.FeedbackLine.parse(i)
        self.assertEqual(0, i.pos)


class TestChoiceDescNewline(unittest.TestCase):

    def test_construct(self):
        hps.ChoiceDescNewline("foo")
        
    def test_feedback_readable(self):
        n = hps.ChoiceDescNewline("foo")
        self.assertEqual("foo",n.feedback)
        
    def test_feedback_not_writable(self):
        n = hps.ChoiceDescNewline("foo")
        with self.assertRaises(AttributeError):
            n.feedback = "weh"
        
    mock_parse_methods = mock_statics(hps,"Newline.parse","QuoteMarker.parse",
        "TextLineMarker.parse","LineWhitespace.parse","ChoiceMarker.parse",
        "BlankLine.parse","StarterLine.parse","TextLine.parse","FeedbackLine.parse")
        
    def setup_parse_methods(self):
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.TextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceMarker.parse.side_effect = make_parse({"c":object()})
        hps.BlankLine.parse.side_effect = make_parse({"b":object()})
        hps.StarterLine.parse.side_effect = make_parse({"s":object()})
        hps.TextLine.parse.side_effect = make_parse({"t":object()})
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("a")})

    @mock_parse_methods        
    def test_parse_returns_populated_choicedescnewline(self):
        self.setup_parse_methods()
        hps.FeedbackLine.parse.side_effect = make_parse({"f":hps.FeedbackLine("foo"),"F":hps.FeedbackLine("bar")})
        result = hps.ChoiceDescNewline.parse(MockInput("lfbFqmw$"))
        self.assertTrue( isinstance(result,hps.ChoiceDescNewline) )
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("foo bar",result.feedback)
    
    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        result = hps.ChoiceDescNewline.parse(MockInput("lbqmw$"))
        self.assertIsNone(result.feedback)
    
    @mock_parse_methods
    def test_parse_expects_newline(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceDescNewline.parse(MockInput("bfqmw$")) )
        self.assertFalse( hps.QuoteMarker.parse.called )
        self.assertFalse( hps.TextLineMarker.parse.called )
        self.assertFalse( hps.LineWhitespace.parse.called )
        self.assertFalse( hps.ChoiceMarker.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_blanklines_or_feedbacklines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescNewline.parse(MockInput("lqmw$")) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_blanklines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescNewline.parse(MockInput("lbbbqmw$")) )
        
    @mock_parse_methods
    def test_parse_allows_multiple_feedbacklines(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescNewline.parse(MockInput("lfffqmw$")) )
        
    @mock_parse_methods
    def test_parse_checks_starterline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.StarterLine.parse.side_effect = make_parse({"f":object()})
        self.assertIsNone( hps.ChoiceDescNewline.parse(MockInput("lfqmw$")) )
        
    def test_parse_checks_textline_before_feedbackline(self):
        self.setup_parse_methods()
        hps.TextLine.parse_side_effect = make_parse({"f":object()})
        self.assertIsNone( hps.ChoiceDescNewline.parse(MockInput("lfqmw$")) )
        
    @mock_parse_methods
    def test_parse_allows_no_quotemarker(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescNewline.parse(MockInput("lbfmw$")) )
        
    @mock_parse_methods
    def test_parse_expects_textlinemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceDescNewline.parse(MockInput("lbfqw$")) )
        self.assertFalse( hps.LineWhitespace.parse.called )
        self.assertFalse( hps.ChoiceMarker.parse.called )
        
    @mock_parse_methods
    def test_parse_allows_no_linewhitespace(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceDescNewline.parse(MockInput("lbfqm$")) )
        
    @mock_parse_methods
    def test_parse_rejects_choicemarker(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceDescNewline.parse(MockInput("lbfqmwc$")) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("lbfqmw$")
        hps.ChoiceDescNewline.parse(i)
        self.assertEqual(6, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("lbfqmwc$")
        hps.ChoiceDescNewline.parse(i)
        self.assertEqual(0, i.pos)


class TestFirstTextLineMarker(unittest.TestCase):

    def test_construct(self):
        hps.FirstTextLineMarker()
        
    def test_parse_returns_firsttextlinemarker(self):
        result = hps.FirstTextLineMarker.parse(MockInput("::$"))
        self.assertTrue( isinstance(result,hps.FirstTextLineMarker) )
        
    def test_parse_expects_first_colon(self):
        self.assertIsNone( hps.FirstTextLineMarker.parse(MockInput("$")) )
        
    def test_parse_expects_second_colon(self):
        self.assertIsNone( hps.FirstTextLineMarker.parse(MockInput(":$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("::$")
        hps.FirstTextLineMarker.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput(":$")
        hps.FirstTextLineMarker.parse(i)
        self.assertEqual(0, i.pos)


class TestFirstTextLine(unittest.TestCase):

    def test_construct(self):
        hps.FirstTextLine("foo")
        
    def test_text_readable(self):
        l = hps.FirstTextLine("foo")
        self.assertEqual("foo",l.text)
        
    def test_text_not_writable(self):
        l = hps.FirstTextLine("foo")
        with self.assertRaises(AttributeError):
            l.text = "bar"
            
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_returns_populated_firsttextline(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("foo")})
        result = hps.FirstTextLine.parse(MockInput("qmc$"))
        self.assertTrue( isinstance(result,hps.FirstTextLine) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual( "foo", result.text )
        
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_allows_no_quote_marker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("bar")})
        self.assertIsNotNone( hps.FirstTextLine.parse(MockInput("mc$")) )
        
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_firsttextlinemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("blah")})
        self.assertIsNone( hps.FirstTextLine.parse(MockInput("qc$")) )
        self.assertFalse( hps.TextLineContent.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_firsttextlinemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("blah")})
        self.assertIsNone( hps.FirstTextLine.parse(MockInput("qm$")) )
    
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("blah")})
        i = MockInput("qmc$")
        hps.FirstTextLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","FirstTextLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_dpesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstTextLineMarker.parse.side_effect = make_parse({"m":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("yadda")})
        i = MockInput("qm$")
        hps.FirstTextLine.parse(i)
        self.assertEqual(0, i.pos)


class TestFirstInstructionLineMarker(unittest.TestCase):

    def test_construct(self):
        hps.FirstInstructionLineMarker()
        
    def test_parse_returns_firstinstructionlinemarker(self):
        result = hps.FirstInstructionLineMarker.parse(MockInput("%%$"))
        self.assertTrue( isinstance(result,hps.FirstInstructionLineMarker) )
        
    def test_parse_expects_first_percent(self):
        self.assertIsNone( hps.FirstInstructionLineMarker.parse(MockInput("$")) )
        
    def test_parse_expects_second_percent(self):
        self.assertIsNone( hps.FirstInstructionLineMarker.parse(MockInput("%$")) )
        
    def test_parse_consumes_input_on_success(self):
        i = MockInput("%%$")
        hps.FirstInstructionLineMarker.parse(i)
        self.assertEqual(2, i.pos)
        
    def test_parse_doesnt_consume_input_on_failure(self):
        i = MockInput("%$")
        hps.FirstInstructionLineMarker.parse(i)
        self.assertEqual(0, i.pos)


class TestFirstInstructionLine(unittest.TestCase):

    def test_construct(self):
        hps.FirstInstructionLine("foo")
        
    def test_text_readable(self):
        l = hps.FirstInstructionLine("foo")
        self.assertEqual("foo", l.text)

    def test_text_not_writable(self):
        l = hps.FirstInstructionLine("foo")
        with self.assertRaises(AttributeError):
            l.text = "bar"
            
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_returns_populated_firstInstructionLine(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("foobar")})
        result = hps.FirstInstructionLine.parse(MockInput("qic$"))
        self.assertTrue( isinstance(result,hps.FirstInstructionLine) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foobar", result.text)
        
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_allows_no_quotemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNotNone( hps.FirstInstructionLine.parse(MockInput("ic$")) )
        
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_firstinstructionlinemarker(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNone( hps.FirstInstructionLine.parse(MockInput("qc$")) )
        self.assertFalse( hps.TextLineContent.parse.called )
        
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_expects_textlinecontent(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        self.assertIsNone( hps.FirstInstructionLine.parse(MockInput("qi$")) )
            
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_consumes_input_on_success(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        i = MockInput("qic$")
        hps.FirstInstructionLine.parse(i)
        self.assertEqual(3, i.pos)
        
    @mock_statics(hps,"QuoteMarker.parse","FirstInstructionLineMarker.parse",
            "TextLineContent.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.QuoteMarker.parse.side_effect = make_parse({"q":object()})
        hps.FirstInstructionLineMarker.parse.side_effect = make_parse({"i":object()})
        hps.TextLineContent.parse.side_effect = make_parse({"c":hps.TextLineContent("")})
        i = MockInput("qi$")
        hps.FirstInstructionLine.parse(i)
        self.assertEqual(0, i.pos)


class TestTextLineContent(unittest.TestCase):

    def test_construct(self):
        hps.TextLineContent("foo")
        
    def test_text_is_readable(self):
        c = hps.TextLineContent("foo")
        self.assertEqual("foo",c.text)
        
    def test_text_is_not_writable(self):
        c = hps.TextLineContent("foo")
        with self.assertRaises(AttributeError):
            c.text = "weh"
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_returns_populated_textlinecontent(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        t = hps.LineText("foo")
        hps.LineText.parse.side_effect = make_parse({"t":t})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        result = hps.TextLineContent.parse(MockInput("wtl$"))
        self.assertTrue( isinstance(result,hps.TextLineContent) )
        self.assertTrue( hasattr(result,"text") )
        self.assertEqual("foo",result.text)
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_allows_no_linewhitespace(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNotNone( hps.TextLineContent.parse(MockInput("tl$")) )
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_expects_linetext(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.TextLineContent.parse(MockInput("wl$")) )
        self.assertFalse( hps.Newline.parse.called )
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_expects_newline(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        self.assertIsNone( hps.TextLineContent.parse(MockInput("wt$")) )
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_consumes_input_on_success(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("wtl$")
        hps.TextLineContent.parse(i)
        self.assertEqual(3,i.pos)
        
    @mock_statics(hps,"LineWhitespace.parse","LineText.parse","Newline.parse")
    def test_parse_doesnt_consume_input_on_failure(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.LineText.parse.side_effect = make_parse({"t":hps.LineText("foo")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        i = MockInput("wt$")
        hps.TextLineContent.parse(i)
        self.assertEqual(0,i.pos)


class TestChoiceContent(unittest.TestCase):
        
    def test_construct(self):
        hps.ChoiceContent("foo","bar","weh","wibble")
        
    def test_description_readable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        self.assertEqual("foo",c.description)
        
    def test_description_not_writable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        with self.assertRaises(AttributeError):
            c.description = "wibble"
            
    def test_response_readable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        self.assertEqual("bar",c.response)
        
    def test_response_not_writable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        with self.assertRaises(AttributeError):
            c.response = "wibble"
            
    def test_goto_readable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        self.assertEqual("weh",c.goto)
        
    def test_goto_not_writable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        with self.assertRaises(AttributeError):
            c.goto = "wibble"
            
    def test_feedback_readable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        self.assertEqual("wibble",c.feedback)
        
    def test_feedback_not_writable(self):
        c = hps.ChoiceContent("foo","bar","weh","wibble")
        with self.assertRaises(AttributeError):
            c.feedback = "blarg"
        
    def setup_parse_methods(self):
        hps.LineWhitespace.parse.side_effect = make_parse({"w":object()})
        hps.ChoiceDescription.parse.side_effect = make_parse({"d":hps.ChoiceDescription("a","z")})
        hps.ChoiceResponse.parse.side_effect = make_parse({"r":hps.ChoiceResponse("b","y","f")})
        hps.Newline.parse.side_effect = make_parse({"l":object()})
        
    mock_parse_methods = mock_statics(hps,"LineWhitespace.parse","ChoiceDescription.parse",
        "ChoiceResponse.parse","Newline.parse")

    @mock_parse_methods        
    def test_parse_returns_populated_choicecontent(self):
        self.setup_parse_methods()
        hps.ChoiceDescription.parse.side_effect = make_parse({"d":hps.ChoiceDescription("foo","blah")})
        hps.ChoiceResponse.parse.side_effect = make_parse({"r":hps.ChoiceResponse("bar","weh","wibble")})
        result = hps.ChoiceContent.parse(MockInput("wdrwl$"))
        self.assertTrue( isinstance(result,hps.ChoiceContent) )
        self.assertTrue( hasattr(result,"description") )
        self.assertEqual("foo",result.description)
        self.assertTrue( hasattr(result,"response") )
        self.assertEqual("bar",result.response)
        self.assertTrue( hasattr(result,"goto") )
        self.assertEqual("weh",result.goto)
        self.assertTrue( hasattr(result,"feedback") )
        self.assertEqual("blah wibble",result.feedback)

    @mock_parse_methods
    def test_parse_sets_none_for_no_feedback(self):
        self.setup_parse_methods()
        hps.ChoiceDescription.parse.side_effect = make_parse({"d":hps.ChoiceDescription("foo",None)})
        hps.ChoiceResponse.parse.side_effect = make_parse({"r":hps.ChoiceResponse("weh","flibble",None)})
        result = hps.ChoiceContent.parse(MockInput("wdrwl$"))
        self.assertIsNone( result.feedback )

    @mock_parse_methods
    def test_parse_sets_none_for_no_response(self):
        self.setup_parse_methods()
        hps.ChoiceResponse.parse.side_effect = make_parse({"r":hps.ChoiceResponse(None,"b","c")})
        result = hps.ChoiceContent.parse(MockInput("wdrwl$"))
        self.assertIsNone( result.response )
        
    @mock_parse_methods
    def test_parse_sets_none_for_no_goto(self):
        self.setup_parse_methods()
        hps.ChoiceResponse.parse.side_effect = make_parse({"r":hps.ChoiceResponse("a",None,"b")})
        result = hps.ChoiceContent.parse(MockInput("wdrwl$"))
        self.assertIsNone( result.goto )

    @mock_parse_methods        
    def test_parse_allows_no_first_linewhitespace(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceContent.parse(MockInput("drwl$")) )

    @mock_parse_methods        
    def test_parse_expects_choicedescription(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceContent.parse(MockInput("wrwl$")) )
        self.assertFalse( hps.ChoiceResponse.parse.called )
        self.assertFalse( hps.Newline.parse.called )

    @mock_parse_methods        
    def test_parse_allows_no_choiceresponse(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceContent.parse(MockInput("wdwl$")) )
    
    @mock_parse_methods
    def test_parse_allows_no_second_linewhitepace(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.ChoiceContent.parse(MockInput("wdrl$")) )    
        
    @mock_parse_methods
    def test_parse_expects_newline(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.ChoiceContent.parse(MockInput("wdrw$")) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("wdrwl$")
        hps.ChoiceContent.parse(i)
        self.assertEqual(5,i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("wdrw$")
        hps.ChoiceContent.parse(i)
        self.assertEqual(0,i.pos)


class TestStarterLine(unittest.TestCase):

    def test_construct(self):
        hps.StarterLine("foo")
    
    def test_line_readable(self):
        l = hps.StarterLine("foo")
        self.assertEqual("foo",l.line)
        
    def test_line_not_writable(self):
        l = hps.StarterLine("foo")
        with self.assertRaises(AttributeError):
            l.line = "bar"
    
    def setup_parse_methods(self):
        hps.FirstTextLine.parse.side_effect = make_parse({"T":object()})
        hps.FirstInstructionLine.parse.side_effect = make_parse({"I":object()})
        hps.FirstChoice.parse.side_effect = make_parse({"C":object()})
        hps.Heading.parse.side_effect = make_parse({"h":object()})
        
    mock_parse_methods = mock_statics(hps,"FirstTextLine.parse",
        "FirstInstructionLine.parse","FirstChoice.parse","Heading.parse")

    @mock_parse_methods        
    def test_parse_returns_populated_starterline(self):
        self.setup_parse_methods()
        t = object()
        hps.FirstTextLine.parse.side_effect = make_parse({"T":t})
        result = hps.StarterLine.parse(MockInput("T$"))
        self.assertTrue( isinstance(result,hps.StarterLine) )
        self.assertTrue( hasattr(result,"line") )
        self.assertEqual(t, result.line)

    @mock_parse_methods    
    def test_parse_expects_line(self):
        self.setup_parse_methods()
        self.assertIsNone( hps.StarterLine.parse(MockInput("$")) )
        
    @mock_parse_methods
    def test_parse_allows_firstinstructionline(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.StarterLine.parse(MockInput("I$")) )
        
    @mock_parse_methods
    def test_parse_allows_firstchoice(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.StarterLine.parse(MockInput("C$")) )
        
    @mock_parse_methods
    def test_parse_allows_heading(self):
        self.setup_parse_methods()
        self.assertIsNotNone( hps.StarterLine.parse(MockInput("h$")) )
        
    @mock_parse_methods
    def test_parse_rejects_non_starter(self):
        self.setup_parse_methods()
        hps.TextLine.parse.side_effect = make_parse({"t":object()})
        self.assertIsNone( hps.StarterLine.parse(MockInput("t$")) )
        
    @mock_parse_methods
    def test_parse_consumes_input_on_success(self):
        self.setup_parse_methods()
        i = MockInput("T$")
        hps.StarterLine.parse(i)
        self.assertEqual(1, i.pos)
        
    @mock_parse_methods
    def test_parse_doesnt_consume_input_on_failure(self):
        self.setup_parse_methods()
        i = MockInput("t$")
        hps.StarterLine.parse(i)
        self.assertEqual(0, i.pos)


class TestJsonIO(unittest.TestCase):

    def test_has_extensions(self):
        hio.JsonIO.EXTENSIONS[0]

    def test_write_doesnt_throw_error(self):
        s = io.StringIO()
        hio.JsonIO.write(hps.Document([]),s)
        
    def test_write_handles_document(self):
        s = io.StringIO()
        hio.JsonIO.write(hps.Document([]),s)
        self.assertEqual('[]', s.getvalue())
        
    def test_write_handles_firstsection(self):
        s = io.StringIO()
        hio.JsonIO.write( hps.Document([hps.FirstSection([],"foo")]),s )
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [],\n'
                            '        "feedback": "foo"\n'
                            '    }\n'
                            ']', s.getvalue())
    
    def test_write_handles_section(self):
        s = io.StringIO()
        hio.JsonIO.write(hps.Document([hps.Section("bar",[],"foo")]),s ) 
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [],\n'
                            '        "feedback": "foo",\n'
                            '        "name": "bar"\n'
                            '    }\n'
                            ']', s.getvalue())

    def test_write_handles_textblock(self):
        s = io.StringIO()
        hio.JsonIO.write(hps.Document([hps.FirstSection([hps.TextBlock("blah","yadda")],"")]),s ) 
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [\n'
                            '            {\n'
                            '                "content": "blah",\n'
                            '                "type": "text"\n'
                            '            }\n'
                            '        ],\n'
                            '        "feedback": ""\n'
                            '    }\n'
                            ']', s.getvalue() )
                
    def test_write_handles_instructionblock(self):
        s = io.StringIO()
        hio.JsonIO.write(
                hps.Document([hps.FirstSection([hps.InstructionBlock("wibble","flibble")],"")]),s )
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [\n'
                            '            {\n'
                            '                "content": "wibble",\n'
                            '                "type": "instructions"\n'
                            '            }\n'
                            '        ],\n'
                            '        "feedback": ""\n'
                            '    }\n'
                            ']', s.getvalue())
    
    def test_write_handles_choiceblock(self):
        s = io.StringIO()
        hio.JsonIO.write(
                hps.Document([hps.FirstSection([hps.ChoiceBlock([],"weh")],"")]),s )
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [\n'
                            '            {\n'
                            '                "content": [],\n'
                            '                "feedback": "weh",\n'
                            '                "type": "choices"\n'
                            '            }\n'
                            '        ],\n'
                            '        "feedback": ""\n'
                            '    }\n'
                            ']', s.getvalue())
                
    def test_write_handles_choice(self):
        s = io.StringIO()
        hio.JsonIO.write(
            hps.Document([hps.FirstSection([hps.ChoiceBlock([
                hps.Choice("X","33","ok","home","great") ],"great")],"great")]), s ) 
        self.assertEqual('[\n'
                            '    {\n'
                            '        "blocks": [\n'
                            '            {\n'
                            '                "content": [\n'
                            '                    {\n'
                            '                        "description": "33",\n'
                            '                        "goto": "home",\n'
                            '                        "mark": "X",\n'
                            '                        "response": "ok"\n'
                            '                    }\n'
                            '                ],\n'
                            '                "feedback": "great",\n'
                            '                "type": "choices"\n'
                            '            }\n'
                            '        ],\n'
                            '        "feedback": "great"\n'
                            '    }\n'
                            ']', s.getvalue() )
                    
                    
class TestHrbrtIO(unittest.TestCase):

    def test_has_extensions(self):
        hio.HrbrtIO.EXTENSIONS[0]
        
    def test_write_doesnt_throw_error(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([]),s)
        
    def test_write_handles_document(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([]),s)
        self.assertEqual("", s.getvalue())
        
    def test_write_handles_firstsection(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([],"this is fab") ]), s )
        self.assertEqual("\nthis is fab\n", s.getvalue())
            
    def test_write_handles_firstsection_feedback_wrap(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
                hps.FirstSection([],"This is a test to test line wrapping "
                +"and see if long lines are wrapped at some point") ]), s)
        self.assertEqual("\nThis is a test to test line wrapping and see "
            +"if long lines are wrapped at some\npoint\n",
            s.getvalue() )
            
    def test_write_handles_section(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
                hps.Section("My Section",[],"excellent stuff") ]), s)
        self.assertEqual("== My Section ==\n\n\nexcellent stuff\n", 
            s.getvalue() )
                
    def test_write_handles_section_feedback_wrap(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.Section("dave",[],"This is a test to test line wrapping "
            +"and see if long lines are wrapped at some point") ]), s)
        self.assertEqual("== dave ==\n\n\nThis is a test to test line wrapping and see "
            +"if long lines are wrapped at some\npoint\n",
            s.getvalue())
                
    def test_write_handles_textblock(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("This is a test",None) ],None) ]), s)
        self.assertEqual(":: This is a test\n", s.getvalue())

    def test_write_handles_textblock_line_wrap(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
                hps.FirstSection([ hps.TextBlock("This is a test to test line "
                    +"wrapping and see if long lines are wrapped at some "
                    +"point", None) ],None) ]), s)
        self.assertEqual(":: This is a test to test line wrapping and see "
            +"if long lines are wrapped at\n:  some point\n",
            s.getvalue())

    def test_formt_handles_firstsection_multiple_blocks(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual(":: Testing\n\n:: More testing\n",
            s.getvalue())
        
    def test_write_handles_section_multiple_blocks(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual("== dave ==\n\n:: Testing\n\n:: More testing\n",
            s.getvalue())
                
    def test_write_handles_firstsection_block_and_feedback(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual(":: Test\n\nBlah blah\n", s.getvalue())
                
    def test_write_handles_section_block_and_feedback(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual("== dave ==\n\n:: Test\n\nBlah blah\n", s.getvalue() )

    def test_write_handles_instructionblock(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock("This is a test",None) ],None) ]), s)
        self.assertEqual("%% This is a test\n", s.getvalue() )

    def test_write_handles_instructionblock_line_wrap(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock("This is a test to test line "
                +"wrapping and see if long lines are wrapped at some "
                +"point", None) ],None) ]), s)
        self.assertEqual("%% This is a test to test line wrapping and see "
            +"if long lines are wrapped at\n%  some point\n",
            s.getvalue())

    def test_write_handles_choiceblock(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([], "This is a test") ],None)]), s)
        self.assertEqual("\nThis is a test\n", s.getvalue())

    def test_write_handles_choiceblock_feedback_wrap(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([], "This is a test to see if "
                +"long lines are wrapped at some point by the line wrapping "
                +"thingy") ],None) ]), s)
        self.assertEqual("\nThis is a test to see if long lines are wrapped "
            +"at some point by the line\nwrapping thingy\n",
            s.getvalue())

    def test_write_handles_choice(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda","wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual(":: [X] blah blah\n:      -- yadda yadda\n"
                +":      GO TO wibble\n", s.getvalue())

    def test_write_handles_choice_no_mark(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"blah blah","yadda yadda","wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual(":: [] blah blah\n:      -- yadda yadda\n"
                +":      GO TO wibble\n", s.getvalue() )

    def test_write_handles_choice_no_response(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,"wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual(":: [X] blah blah\n:      -- GO TO wibble\n",
            s.getvalue())
                
    def test_write_handles_choice_no_goto(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda",None,None)
            ],None) ],None) ]), s)
        self.assertEqual(":: [X] blah blah\n:      -- yadda yadda\n",
            s.getvalue())
                
    def test_write_handles_choice_no_response_or_goto(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,None,None)
            ],None) ],None) ]), s)
        self.assertEqual(":: [X] blah blah\n", s.getvalue())

    def test_write_handles_choice_wrapped_description(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","This is a test to test long lines of text "
                    +"are wrapped properly onto the next line, okay?",
                    "yadda yadda","wibble",None) ],None) ],None)]), s)
        self.assertEqual(":: [X] This is a test to test long lines of text are "
            +"wrapped properly onto the\n:  next line, okay?\n"
            +":      -- yadda yadda\n:      GO TO wibble\n",
            s.getvalue())

    def test_write_handles_choice_wrapped_response(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah","This is a test to test long lines of text "
                    +"are wrapped properly onto the next line, okay?",
                    "wibble",None) ],None) ],None)]), s)
        self.assertEqual(":: [X] blah\n:      -- This is a test to test long lines of "
            +"text are wrapped properly onto\n:  the next line, okay?"
            +"\n:      GO TO wibble\n", s.getvalue())

    def test_write_handles_choiceblock_multiple_choices(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
                hps.FirstSection([ hps.ChoiceBlock([
                    hps.Choice("X","foo","bar","wibble",None),
                    hps.Choice("Y","weh","meh","yadda",None)
                ],None) ],None) ]), s)
        self.assertEqual(":: [X] foo\n:      -- bar\n:      GO TO wibble\n"
            +":  [Y] weh\n:      -- meh\n:      GO TO yadda\n",
            s.getvalue())

    def test_write_handles_multiple_sections(self):
        s = io.StringIO()
        hio.HrbrtIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("foo",None) ],None),
            hps.Section("dave",[ hps.TextBlock("bar",None) ],None) ]), s)
        self.assertEqual(":: foo\n\n== dave ==\n\n:: bar\n", s.getvalue())

    @mock_statics(hps,"Document.parse")
    def test_read_invokes_parse_with_input_obj(self):
        s = io.StringIO("test")
        hio.HrbrtIO.read(s)
        self.assertTrue( hps.Document.parse.called )
        self.assertEqual( 1, len(hps.Document.parse.call_args_list) )
        self.assertEqual( 0, len(hps.Document.parse.call_args[1]) )
        self.assertEqual( 1, len(hps.Document.parse.call_args[0]) )
        self.assertTrue( isinstance(hps.Document.parse.call_args[0][0], hps.Input) )

    @mock_statics(hps,"Document.parse")
    def test_read_constructs_input_with_stream_contents(self):
        s = io.StringIO("test")
        hio.HrbrtIO.read(s)
        i = hps.Document.parse.call_args[0][0]
        self.assertEqual( "test\x00", i._data )

    @mock_statics(hps,"Document.parse")
    def test_read_returns_parse_result(self):
        m = mock.Mock()
        hps.Document.parse.return_value = m
        s = io.StringIO("test")
        self.assertEqual(m, hio.HrbrtIO.read(s) )
        
    @mock_statics(hps,"Document.parse")
    def test_read_throws_inputerror_for_parse_error(self):
        hps.Document.parse.return_value = None
        s = io.StringIO("test")
        with self.assertRaises(hps.InputError):
            hio.HrbrtIO.read(s)
    

class TestCommandLineRunner(unittest.TestCase):

    def setUp(self):
        self.r = hrun.CommandLineRunner()
        self.i = io.StringIO()
        self.o = io.StringIO()

    def do_run(self,doc,input):
        i = io.StringIO(input)
        o = io.StringIO()
        hrun.CommandLineRunner()._run(doc, i, o)
        return o.getvalue()

    def test_can_run(self):
        self.do_run( hps.Document([]), "" )
    
    def test_prints_textblock(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([
                hps.TextBlock("This is a test",None)
            ],None) ]), "" )
        self.assertEqual("This is a test\n\n[enter]\n\n", result)

    def test_invokes_readline_after_printing_textblock(self):
        log = []
        def record(text): log.append(text)
        i = mock.Mock()
        i.readline.side_effect = lambda: record("readline")
        o = mock.Mock()
        o.write.side_effect = lambda s: record("write %s" % s)
        d = hps.Document([ hps.FirstSection([ hps.TextBlock("Foobar",None) ],None) ])
        hrun.CommandLineRunner()._run(d,i,o)
        self.assertEqual(["write Foobar\n\n","write [enter]","readline","write \n\n"],log)

    def test_doesnt_print_instructionblock(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([
                hps.InstructionBlock("This is a test",None)
            ],None) ]), "" )
        self.assertEqual("",result)
        
    def test_prints_choiceblock(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha",None,None,None),
                hps.Choice(None,"beta",None,None,None)
            ],None) ],None) ]), "1\n" )
        self.assertEqual("1) alpha\n2) beta\n\n> \n\n", result)

    def test_validates_choice_selection_too_low(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha",None,None,None),
                hps.Choice(None,"beta",None,None,None)
            ],None) ],None) ]), "0\n1\n" )
        self.assertEqual("1) alpha\n2) beta\n\n> \n\n"
            +"Invalid choice\n\n> \n\n", result)

    def test_validates_choice_selection_too_high(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha",None,None,None),
                hps.Choice(None,"beta",None,None,None)
            ],None) ],None) ]), "3\n1\n" )
        self.assertEqual("1) alpha\n2) beta\n\n> \n\n"
            +"Invalid choice\n\n> \n\n", result)

    def test_validates_choice_selection_non_numeric(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha",None,None,None),
                hps.Choice(None,"beta",None,None,None)
            ],None) ],None) ]), "foo\n1\n" )
        self.assertEqual("1) alpha\n2) beta\n\n> \n\n"
            +"Enter a number\n\n> \n\n", result)

    def test_prints_choice_response(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha","Where on earth",None,None),
                hps.Choice(None,"beta","is Carmen Sandiego",None,None)
            ],None) ],None) ]), "2\n" )
        self.assertEqual("1) alpha\n2) beta\n\n> \n\n"
            +"is Carmen Sandiego\n\n[enter]\n\n", result)

    def test_invokes_readline_after_printing_choice_response(self):
        log = []
        def readline():
            log.append("readline")
            return "1\n"
        def write(val):
            log.append("write %s" % val)
        i = mock.Mock()
        i.readline.side_effect = readline
        o = mock.Mock()
        o.write.side_effect = write
        d = hps.Document([ hps.FirstSection([ hps.ChoiceBlock([
            hps.Choice(None,"foo","bar",None,None) ],None) ],None) ])
        hrun.CommandLineRunner()._run(d,i,o)
        self.assertEqual(["write 1) foo\n","write \n","write > ","readline",
            "write \n\n","write bar\n\n","write [enter]","readline","write \n\n"],log)

    def test_follows_goto_forwards(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"foo",None,"flibble",None)
            ],None), ],None),
            hps.Section("flibble",[],None) ]), "1\n" )
    
    def test_prints_section_title(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"foo",None,"kittens",None)
            ],None) ],None),
            hps.Section("KiTTenS",[],None) ]),"1\n" )
        self.assertEqual("1) foo\n\n> \n\nKiTTenS\n-------\n\n", result)
        
    def test_follows_gotos_backwards(self):
        result = self.do_run( hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"alpha",None,"blarg",None),
            ],None) ],None),
            hps.Section("foobar",[ hps.ChoiceBlock([
                hps.Choice(None,"apple",None,"blarg",None),
            ],None) ],None),
            hps.Section("blarg",[ hps.ChoiceBlock([
                hps.Choice(None,"aberdeen",None,"foobar",None),
                hps.Choice(None,"birmingham",None,None,None),
            ],None) ],None) ]), "1\n1\n1\n2\n" )
        self.assertEqual("1) alpha\n\n> "
            +"\n\nblarg\n-----\n\n1) aberdeen\n2) birmingham\n\n> "
            +"\n\nfoobar\n------\n\n1) apple\n\n> "
            +"\n\nblarg\n-----\n\n1) aberdeen\n2) birmingham\n\n> \n\n", result)
            
    def test_records_selected_choice_in_document(self):
        d = hps.Document([ hps.FirstSection([ hps.ChoiceBlock([
            hps.Choice(None,"foo",None,None,None),
            hps.Choice(None,"bar",None,None,None) ],None) ],None) ])
        self.assertEqual(None,d.sections[0].items[0].choices[0].mark)
        self.assertEqual(None,d.sections[0].items[0].choices[1].mark)
        self.do_run(d,"2\n")
        self.assertEqual(None,d.sections[0].items[0].choices[0].mark)
        self.assertEqual("X",d.sections[0].items[0].choices[1].mark)
        
    def test_overwrites_existing_selected_choice_in_document(self):
        d = hps.Document([ hps.FirstSection([ hps.ChoiceBlock([
            hps.Choice("X","foo",None,None,None),
            hps.Choice(None,"bar",None,None,None) ],None) ],None) ])
        self.assertEqual("X",d.sections[0].items[0].choices[0].mark)
        self.assertEqual(None,d.sections[0].items[0].choices[1].mark)
        self.do_run(d,"2\n")
        self.assertEqual(None,d.sections[0].items[0].choices[0].mark)
        self.assertEqual("X",d.sections[0].items[0].choices[1].mark)
        
        
class TestMarkdownIO(unittest.TestCase):
    
    def test_has_extensions(self):
        hio.MarkdownIO.EXTENSIONS[0]
        
    def test_write_doesnt_throw_error(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([]),s)
        
    def test_write_handles_document(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([]),s)
        self.assertEqual("", s.getvalue())
        
    def test_write_handles_firstsection(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([],"this is fab") ]), s )
        self.assertEqual("\n> this is fab\n", s.getvalue())
            
    def test_write_handles_firstsection_feedback_wrap(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
                hps.FirstSection([],"This is a test to test line wrapping "
                +"and see if long lines are wrapped at some point") ]), s)
        self.assertEqual("\n> This is a test to test line wrapping and see "
            +"if long lines are wrapped at\n> some point\n",
            s.getvalue() )
            
    def test_write_handles_section(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
                hps.Section("My Section",[],"excellent stuff") ]), s)
        self.assertEqual("My Section\n----------\n\n\n> excellent stuff\n", 
            s.getvalue() )
                
    def test_write_handles_section_feedback_wrap(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.Section("dave",[],"This is a test to test line wrapping "
            +"and see if long lines are wrapped at some point") ]), s)
        self.assertEqual("dave\n----\n\n\n> This is a test to test line wrapping and see "
            +"if long lines are wrapped at\n> some point\n",
            s.getvalue())
                
    def test_write_handles_textblock(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("This is a test",None) ],None) ]), s)
        self.assertEqual("This is a test\n", s.getvalue())

    def test_write_handles_textblock_line_wrap(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
                hps.FirstSection([ hps.TextBlock("This is a test to test line "
                    +"wrapping and see if long lines are wrapped at some "
                    +"point", None) ],None) ]), s)
        self.assertEqual("This is a test to test line wrapping and see "
            +"if long lines are wrapped at some\npoint\n",
            s.getvalue())

    def test_formt_handles_firstsection_multiple_blocks(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual("Testing\n\nMore testing\n",
            s.getvalue())
        
    def test_write_handles_section_multiple_blocks(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual("dave\n----\n\nTesting\n\nMore testing\n",
            s.getvalue())
                
    def test_write_handles_firstsection_block_and_feedback(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual("Test\n\n> Blah blah\n", s.getvalue())
                
    def test_write_handles_section_block_and_feedback(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual("dave\n----\n\nTest\n\n> Blah blah\n", s.getvalue() )

    def test_write_handles_instructionblock(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock("This is a test",None) ],None) ]), s)
        self.assertEqual("<!-- This is a test -->\n", s.getvalue() )

    def test_write_doesnt_print_double_dash_in_comments(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock("This is a -- test",None) ],None) ]), s)
        self.assertEqual("<!-- This is a  test -->\n", s.getvalue() )

    def test_write_handles_instructionblock_line_wrap(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock("This is a test to test line "
                +"wrapping and see if long lines are wrapped at some "
                +"point", None) ],None) ]), s)
        self.assertEqual("<!-- This is a test to test line wrapping and see "
            +"if long lines are wrapped at\nsome point -->\n",
            s.getvalue())

    def test_write_handles_choiceblock(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([], "This is a test") ],None)]), s)
        self.assertEqual("\n> This is a test\n", s.getvalue())

    def test_write_handles_choiceblock_feedback_wrap(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([], "This is a test to see if "
                +"long lines are wrapped at some point by the line wrapping "
                +"thingy") ],None) ]), s)
        self.assertEqual("\n> This is a test to see if long lines are wrapped "
            +"at some point by the line\n> wrapping thingy\n",
            s.getvalue())

    def test_write_handles_choice(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda","wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[X] [blah blah](#wibble)** _yadda yadda_\n", s.getvalue())

    def test_write_formats_goto_link(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda","99 Bottles of Beer",None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[X] [blah blah](#bottles-of-beer)** _yadda yadda_\n", s.getvalue())

    def test_write_handles_choice_no_mark(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"blah blah","yadda yadda","wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[] [blah blah](#wibble)** _yadda yadda_\n", s.getvalue() )

    def test_write_handles_choice_no_response(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,"wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[X] [blah blah](#wibble)**\n", s.getvalue())
                
    def test_write_handles_choice_no_goto(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda",None,None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[X] blah blah** _yadda yadda_\n",
            s.getvalue())
                
    def test_write_handles_choice_no_response_or_goto(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,None,None)
            ],None) ],None) ]), s)
        self.assertEqual("- **[X] blah blah**\n", s.getvalue())

    def test_write_handles_choice_wrapped_description(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","This is a test to test long lines of text "
                    +"are wrapped properly onto the next line, okay?",
                    "yadda yadda","wibble",None) ],None) ],None)]), s)
        self.assertEqual("- **[X] [This is a test to test long lines of text are "
            +"wrapped properly onto\n  the next line, okay?](#wibble)** "
            +"_yadda yadda_\n",s.getvalue())

    def test_write_handles_choice_wrapped_response(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah","This is a test to test long lines of text "
                    +"are wrapped properly onto the next line, okay?",
                    "wibble",None) ],None) ],None)]), s)
        self.assertEqual("- **[X] [blah](#wibble)** _This is a test to test long lines of "
            +"text are\n  wrapped properly onto the next line, okay?_\n",
            s.getvalue())

    def test_write_handles_choiceblock_multiple_choices(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
                hps.FirstSection([ hps.ChoiceBlock([
                    hps.Choice("X","foo","bar","wibble",None),
                    hps.Choice("Y","weh","meh","yadda",None),
                ],None) ],None) ]), s)
        self.assertEqual("- **[X] [foo](#wibble)** _bar_\n"
            +"- **[Y] [weh](#yadda)** _meh_\n",
            s.getvalue())

    def test_write_handles_multiple_sections(self):
        s = io.StringIO()
        hio.MarkdownIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("foo",None) ],None),
            hps.Section("dave",[ hps.TextBlock("bar",None) ],None) ]), s)
        self.assertEqual("foo\n\ndave\n----\n\nbar\n", s.getvalue())


class TestXmlIO(unittest.TestCase):

    def strip_text_nodes(self,xml):
        tags = "feedback|name|text|instructions|mark|desc|response|goto"
        return re.sub("<(%s)>\s*" % tags,"<\\1>",
            re.sub("\s*</(%s)>" % tags,"</\\1>",xml))

    def test_has_extensions(self):
        hio.XmlIO.EXTENSIONS[0]
        
    def test_write_doesnt_throw_error(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([]),s)
        
    def test_write_handles_document(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([]),s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document/>\n', self.strip_text_nodes(s.getvalue()))
        
    def test_write_handles_firstsection(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([],'this "is" <fab>') ]), s )
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <feedback>this &quot;is&quot; &lt;fab&gt;</feedback>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()))
                    
    def test_write_handles_section(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
                hps.Section('My <"> Section',[],'excellent "stuff" >_<') ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <name>My &lt;&quot;&gt; Section</name>\n'
            '        <feedback>excellent &quot;stuff&quot; &gt;_&lt;</feedback>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
                
    def test_write_handles_textblock(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock('This is "a" <<test>>',None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <text>This is &quot;a&quot; &lt;&lt;test&gt;&gt;</text>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_formt_handles_firstsection_multiple_blocks(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <text>Testing</text>\n'
            '        <text>More testing</text>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
        
    def test_write_handles_section_multiple_blocks(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Testing",None),
                hps.TextBlock("More testing",None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <name>dave</name>\n'
            '        <text>Testing</text>\n'
            '        <text>More testing</text>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
                
    def test_write_handles_firstsection_block_and_feedback(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <text>Test</text>\n'
            '        <feedback>Blah blah</feedback>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
                
    def test_write_handles_section_block_and_feedback(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.Section("dave",[ hps.TextBlock("Test",None) ], "Blah blah") ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <name>dave</name>\n'
            '        <text>Test</text>\n'
            '        <feedback>Blah blah</feedback>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_instructionblock(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.InstructionBlock('This is >a< "test"',None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <instructions>This is &gt;a&lt; &quot;test&quot;</instructions>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_choiceblock(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([], '<This> is "a" test') ],None)]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <feedback>&lt;This&gt; is &quot;a&quot; test</feedback>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_choice(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice('>"X"<','"blah" <blah>',
                    '>>yadda " yadda<<','"wi>bb<le"',None)
            ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <mark>&gt;&quot;X&quot;&lt;</mark>\n'
            '                <desc>&quot;blah&quot; &lt;blah&gt;</desc>\n'
            '                <response>&gt;&gt;yadda &quot; yadda&lt;&lt;</response>\n'
            '                <goto>&quot;wi&gt;bb&lt;le&quot;</goto>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_choice_no_mark(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"blah blah",
                    "yadda yadda","wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <desc>blah blah</desc>\n'
            '                <response>yadda yadda</response>\n'
            '                <goto>wibble</goto>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_choice_no_response(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,"wibble",None)
            ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <mark>X</mark>\n'
            '                <desc>blah blah</desc>\n'
            '                <goto>wibble</goto>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
                
    def test_write_handles_choice_no_goto(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah","yadda yadda",None,None)
            ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <mark>X</mark>\n'
            '                <desc>blah blah</desc>\n'
            '                <response>yadda yadda</response>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )
                
    def test_write_handles_choice_no_response_or_goto(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice("X","blah blah",None,None,None)
            ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <mark>X</mark>\n'
            '                <desc>blah blah</desc>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_choiceblock_multiple_choices(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
                hps.FirstSection([ hps.ChoiceBlock([
                    hps.Choice("X","foo","bar","wibble",None),
                    hps.Choice("Y","weh","meh","yadda",None),
                ],None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <choice>\n'
            '            <option>\n'
            '                <mark>X</mark>\n'
            '                <desc>foo</desc>\n'
            '                <response>bar</response>\n'
            '                <goto>wibble</goto>\n'
            '            </option>\n'
            '            <option>\n'
            '                <mark>Y</mark>\n'
            '                <desc>weh</desc>\n'
            '                <response>meh</response>\n'
            '                <goto>yadda</goto>\n'
            '            </option>\n'
            '        </choice>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )

    def test_write_handles_multiple_sections(self):
        s = io.StringIO()
        hio.XmlIO.write(hps.Document([
            hps.FirstSection([ hps.TextBlock("foo",None) ],None),
            hps.Section("dave",[ hps.TextBlock("bar",None) ],None) ]), s)
        self.assertEqual(
            '<?xml version="1.0" ?>\n'
            '<document>\n'
            '    <section>\n'
            '        <text>foo</text>\n'
            '    </section>\n'
            '    <section>\n'
            '        <name>dave</name>\n'
            '        <text>bar</text>\n'
            '    </section>\n'
            '</document>\n', 
            self.strip_text_nodes(s.getvalue()) )


class TestGuiRunner(unittest.TestCase):

    def setUp(self):
        self.tk = mock.Mock()
        self.gui = mock.Mock()
        self.runner = None
        
    def do_run(self,doc,mockloop=None,catch=True):
        self.runner = hrun.GuiRunner()
        if mockloop:
            self.tk.mainloop.side_effect = mockloop
        try:
            self.runner._run(doc,self.tk,self.gui)
        except hrun.RunnerError:
            if not catch: raise
        
    def test_can_run(self):
        self.do_run(hps.Document([]))

    def test_registers_as_gui_listener(self):
        self.do_run(hps.Document([]))
        self.assertEqual(self.runner,self.gui.listener)
    
    def test_starts_tk_event_loop(self):
        self.do_run(hps.Document([]))
        self.assertEqual(1, self.tk.mainloop.call_count)
            
    def test_performs_initial_gui_update(self):
        self.do_run(hps.Document([]))
        self.assertEqual(1, self.gui.on_prev_item_change.call_count)
        self.assertEqual(1, self.gui.on_curr_item_change.call_count)
        self.assertEqual(1, self.gui.on_back_allowed_change.call_count)
        self.assertEqual(1, self.gui.on_forward_allowed_change.call_count)
        self.assertEqual(1, self.gui.on_section_change.call_count)
        
    def test_shows_current_textblock(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("This is a test",None) ],None)]))
        self.assertEqual(0, len(self.gui.on_curr_item_change.call_args[1]))
        self.assertEqual(1, len(self.gui.on_curr_item_change.call_args[0]))
        item = self.gui.on_curr_item_change.call_args[0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual( "This is a test", item.text )
        
    def test_shows_current_choiceblock(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"Animal",None,None,None),
                hps.Choice(None,"Mineral",None,None,None),
                hps.Choice(None,"Vegetable",None,None,None),
            ],None) ],None)]))
        self.assertEqual(0, len(self.gui.on_curr_item_change.call_args[1]))
        self.assertEqual(1, len(self.gui.on_curr_item_change.call_args[0]))
        item = self.gui.on_curr_item_change.call_args[0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual( ["Animal","Mineral","Vegetable"], item.options )
        self.assertIsNone( item.selected )
        
    def test_indicates_selected_option_for_choiceblock(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"Animal",None,None,None),
                hps.Choice(None,"Mineral",None,None,None),
                hps.Choice("X", "Vegetable",None,None,None),
            ],None) ],None)]))
        self.assertEqual(2, self.gui.on_curr_item_change.call_args[0][0].selected)
        
    def test_doesnt_show_instructionblock(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.InstructionBlock("Ignore me",None) ],None)]))
        self.assertEqual(0, len(self.gui.on_curr_item_change.call_args[1]))
        self.assertEqual(1, len(self.gui.on_curr_item_change.call_args[0]))
        item = self.gui.on_curr_item_change.call_args[0][0]
        self.assertIsNone( item )
        
    def test_shows_no_previous_block_for_first_block(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None) ],None)]))
        self.assertEqual(0, len(self.gui.on_prev_item_change.call_args[1]))
        self.assertEqual(1, len(self.gui.on_prev_item_change.call_args[0]))
        item = self.gui.on_prev_item_change.call_args[0][0]
        self.assertIsNone( item )
        
    def test_disallows_back_for_first_block(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None) ],None)]))
        self.assertEqual(0,len(self.gui.on_back_allowed_change.call_args[1]))
        self.assertEqual(1,len(self.gui.on_back_allowed_change.call_args[0]))
        self.assertEqual( False, self.gui.on_back_allowed_change.call_args[0][0] )    

    def test_allows_forward_initially(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None) ],None)]))
        self.assertEqual(0,len(self.gui.on_forward_allowed_change.call_args[1]))
        self.assertEqual(1,len(self.gui.on_forward_allowed_change.call_args[0]))
        self.assertEqual( True, self.gui.on_forward_allowed_change.call_args[0][0] )
        
    def test_sets_initial_section_name_blank(self):
        self.do_run(hps.Document([hps.FirstSection([],None)]))
        self.gui.on_section_change.assert_called_once_with( None )
        
    def test_updates_curr_item_to_textblock_on_next(self):
        def loop():
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("this is the first item",None),
            hps.TextBlock("this is the second item",None) 
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText))
        self.assertEqual("this is the second item", item.text)
        
    def test_updates_curr_item_to_choiceblock_on_next(self):
        def loop():
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("this is the first item",None),
            hps.ChoiceBlock([
                hps.Choice(None,"Opt A",None,None,None),
                hps.Choice(None,"Opt B",None,None,None) ],None) 
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["Opt A","Opt B"], item.options)

    def test_updates_prev_item_to_textblock_on_next(self):
        def loop(): 
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("this is the first item",None),
            hps.TextBlock("this is the second item",None)
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("this is the first item", item.text)
    
    def test_updates_prev_item_to_choiceblock_on_next(self):
        def loop(): 
            self.runner.on_change_selection(0)
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"Opt A",None,None,None),
                hps.Choice(None,"Opt B",None,None,None) ],None),
            hps.TextBlock("This is a test",None)
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["Opt A","Opt B"],item.options)

    def test_allows_back_on_next(self):
        def loop(): 
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foobar",None),
            hps.TextBlock("blah blah",None),
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_back_allowed_change.call_count)
        self.assertEqual(True,self.gui.on_back_allowed_change.call_args_list[1][0][0])

    def test_updates_current_item_to_textblock_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("this is the first item",None),
            hps.TextBlock("this is the second item",None) 
        ],None)]),mockloop=loop)
        self.assertEqual(3, self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText))
        self.assertEqual("this is the first item", item.text)
        
    def test_updates_current_item_to_choiceblock_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"Opt A",None,None,None),
                hps.Choice(None,"Opt B",None,None,None) ],None),
            hps.TextBlock("this is the second item",None) 
        ],None)]),mockloop=loop)
        self.assertEqual(3, self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice))
        self.assertEqual(["Opt A","Opt B"], item.options)
        
    def test_updates_prev_item_to_blank_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo bar",None),
            hps.TextBlock("this is the second item",None) 
        ],None)]),mockloop=loop)
        self.assertEqual(3, self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[2][0][0]
        self.assertIsNone(item)
    
    def test_updates_prev_item_to_textblock_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo bar",None),
            hps.TextBlock("this is the second item",None),
            hps.TextBlock("blah blah",None),
        ],None)]),mockloop=loop)
        self.assertEqual(4, self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("foo bar",item.text)

    def test_updates_prev_item_to_choiceblock_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cake",None,None,None),
                hps.Choice(None,"death",None,None,None) ],None),
            hps.TextBlock("this is the second item",None),
            hps.TextBlock("blah blah",None),
        ],None)]),mockloop=loop)
        self.assertEqual(4, self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cake","death"],item.options)
        
    def test_allows_back_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None),
            hps.TextBlock("weh",None),
        ],None)]),mockloop=loop)
        self.assertEqual(4,self.gui.on_back_allowed_change.call_count)
        self.assertTrue( self.gui.on_back_allowed_change.call_args_list[3][0][0] )
        
    def test_disallows_back_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None),
        ],None)]),mockloop=loop)
        self.assertEqual(3,self.gui.on_back_allowed_change.call_count)
        self.assertFalse( self.gui.on_back_allowed_change.call_args_list[2][0][0] )
        
    def test_allows_forward_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None),
        ],None)]),mockloop=loop)
        self.assertEqual(3,self.gui.on_forward_allowed_change.call_count)
        self.assertTrue( self.gui.on_forward_allowed_change.call_args_list[2][0][0] )
    
    def test_doesnt_allow_forward_before_choice_made(self):
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats",None,None,None),
                hps.Choice(None,"dogs",None,None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]))
        self.gui.on_forward_allowed_change.assert_called_once_with(False)
        
    def test_allows_forward_after_choice_made(self):
        def loop():
            self.runner.on_change_selection(1)
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats",None,None,None),
                hps.Choice(None,"dogs",None,None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_forward_allowed_change.call_count)
        self.assertTrue( self.gui.on_forward_allowed_change.call_args_list[1][0][0] )        

    def test_only_allows_forward_first_time_choice_made(self):
        def loop():    
            self.runner.on_change_selection(0)
            self.runner.on_change_selection(1)
            self.runner.on_change_selection(0)
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats",None,None,None),
                hps.Choice(None,"dogs",None,None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(2, self.gui.on_forward_allowed_change.call_count)

    def test_remembers_choice_selection(self):
        def loop():
            self.runner.on_change_selection(1)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats",None,None,None),
                hps.Choice(None,"dogs",None,None,None)],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(3,self.gui.on_curr_item_change.call_count)
        self.assertEqual(3,self.gui.on_prev_item_change.call_count)
        self.assertIsNone( self.gui.on_curr_item_change.call_args_list[0][0][0].selected )
        self.assertEqual(1, self.gui.on_prev_item_change.call_args_list[1][0][0].selected)
        self.assertEqual(1, self.gui.on_curr_item_change.call_args_list[2][0][0].selected)

    def test_displays_choice_response_as_current_item_on_next(self):
        def loop():
            self.runner.on_change_selection(1)
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(2,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("booo",item.text)

    def test_displays_choice_response_as_current_item_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(4,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("yay",item.text)

    def test_displays_choice_response_as_previous_item_on_next(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(3,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("yay",item.text)

    def test_displays_choice_response_as_previous_item_on_prev(self):
        def loop():
            self.runner.on_change_selection(1)
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None),
        ],None)]),mockloop=loop)
        self.assertEqual(5,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[4][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("booo",item.text)

    def test_displays_choice_as_current_item_on_prev_from_response(self):
        def loop():
            self.runner.on_change_selection(1)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(3,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cats","dogs"],item.options)

    def test_displays_choice_as_previous_item_on_prev_to_response(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"cats","yay",None,None),
                hps.Choice(None,"dogs","booo",None,None) ],None),
            hps.TextBlock("foo",None),
        ],None)]),mockloop=loop)
        self.assertEqual(4,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cats","dogs"],item.options)

    def test_allows_forward_for_goto(self):
        def loop():
            self.runner.on_change_selection(0)
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats",None,"Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None)
        ]), mockloop=loop)
        self.assertEqual(2,self.gui.on_forward_allowed_change.call_count)
        self.assertEqual( True, self.gui.on_forward_allowed_change.call_args_list[1][0][0] )
        
    def test_allows_forward_for_goto_with_response(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats","yay","Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None)
        ]), mockloop=loop)
        self.assertEqual(3,self.gui.on_forward_allowed_change.call_count)
        self.assertEqual( True, self.gui.on_forward_allowed_change.call_args_list[2][0][0] )
        
    def test_allows_back_for_goto(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats",None,"Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None)
        ]), mockloop=loop)
        self.assertEqual(2,self.gui.on_back_allowed_change.call_count)
        self.assertEqual( True, self.gui.on_back_allowed_change.call_args_list[1][0][0] )
        
    def test_allows_back_for_goto_with_response(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats","yay","Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None)
        ]), mockloop=loop)
        self.assertEqual(3,self.gui.on_back_allowed_change.call_count)
        self.assertEqual( True, self.gui.on_back_allowed_change.call_args_list[2][0][0] )

    def test_follows_goto_on_next(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats",None,"Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None) 
        ]), mockloop=loop)
        self.assertEqual(2,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("this is a test", item.text)
        self.assertEqual(2,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[1][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cats"], item.options)
        
    def test_follows_goto_with_response_on_next(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats","yay","Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None) 
        ]), mockloop=loop)
        self.assertEqual(3,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("this is a test", item.text)
        self.assertEqual(3,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("yay", item.text)
        
    def test_follows_goto_back_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats",None,"Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None) 
        ]), mockloop=loop)
        self.assertEqual(3,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[2][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cats"], item.options)
        self.assertEqual(3,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[2][0][0]
        self.assertIsNone(item)
        
    def test_follows_goto_back_to_response_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.ChoiceBlock([
                    hps.Choice(None,"cats","yay","Foobar",None) ],None) ],None),
            hps.Section("fooBar",[
                hps.TextBlock("this is a test",None) ],None) 
        ]), mockloop=loop)
        self.assertEqual(4,self.gui.on_curr_item_change.call_count)
        item = self.gui.on_curr_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerText) )
        self.assertEqual("yay", item.text)
        self.assertEqual(4,self.gui.on_prev_item_change.call_count)
        item = self.gui.on_prev_item_change.call_args_list[3][0][0]
        self.assertTrue( isinstance(item,hrun.GuiRunnerChoice) )
        self.assertEqual(["cats"],item.options)

    def test_updates_section_title_on_next(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"foo",None,"dave",None)
            ],None) ],None),
            hps.Section("DavE",[ hps.TextBlock("bar",None) ],None),
        ]),mockloop=loop)
        self.assertEqual(2,self.gui.on_section_change.call_count)
        self.assertEqual("DavE",self.gui.on_section_change.call_args_list[1][0][0])

    def test_doesnt_update_title_for_same_section_on_next(self):
        def loop():
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([
                hps.TextBlock("foo",None),
                hps.TextBlock("bar",None) ],None),
        ]),mockloop=loop)
        self.assertEqual(1,self.gui.on_section_change.call_count)
        
    def test_updates_section_title_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"cats",None,"Alpha",None)
            ],None) ],None),
            hps.Section("alpha",[ hps.ChoiceBlock([
                hps.Choice(None,"dogs",None,"Omega",None)
            ],None) ],None),
            hps.Section("omega",[ hps.TextBlock("weh",None) ],None),
        ]),mockloop=loop)
        self.assertEqual(4,self.gui.on_section_change.call_count)
        self.assertEqual("alpha",self.gui.on_section_change.call_args_list[3][0][0])

    def test_upates_section_title_to_none_on_prev(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([ hps.ChoiceBlock([
                hps.Choice(None,"ducks",None,"Fred",None)
            ],None) ],None),
            hps.Section("freD", [ hps.TextBlock("foo",None) ],None)
        ]),mockloop=loop)
        self.assertEqual(3,self.gui.on_section_change.call_count)
        self.assertIsNone(self.gui.on_section_change.call_args_list[2][0][0])
        
    def test_doesnt_update_title_for_same_section_on_prev(self):
        def loop():
            self.runner.on_next()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([ 
                hps.TextBlock("foo",None),
                hps.TextBlock("bar",None) ],None),
        ]),mockloop=loop)
        self.assertEqual(1,self.gui.on_section_change.call_count)    

    def test_closes_gui_if_end_reached(self):
        def loop():
            self.runner.on_next()
        self.do_run(hps.Document([
            hps.FirstSection([ hps.TextBlock("foo",None) ],None),
        ]),mockloop=loop,catch=False)
        self.tk.quit.assert_called_once_with()
        
    def test_writes_selections_to_doc_if_end_reached(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_change_selection(1)
            self.runner.on_next()
        d = hps.Document([ hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"left",None,None,None),
                hps.Choice(None,"right",None,None,None) ],None),
            hps.ChoiceBlock([
                hps.Choice(None,"up",None,None,None),
                hps.Choice(None,"down",None,None,None) ],None),
        ],None) ])
        self.do_run(d,mockloop=loop,catch=False)
        self.assertEqual("X",d.sections[0].items[0].choices[0].mark)
        self.assertIsNone(d.sections[0].items[0].choices[1].mark)
        self.assertIsNone(d.sections[0].items[1].choices[0].mark)
        self.assertEqual("X",d.sections[0].items[1].choices[1].mark)

    def test_throws_error_if_gui_closed_early(self):
        def loop():
            self.runner.on_change_selection(1)
            self.runner.on_next()
            self.runner.on_change_selection(0)            
        d = hps.Document([ hps.FirstSection([
            hps.ChoiceBlock([
                hps.Choice(None,"left",None,None,None),
                hps.Choice(None,"right",None,None,None) ],None),
            hps.ChoiceBlock([
                hps.Choice(None,"up",None,None,None),
                hps.Choice(None,"down",None,None,None) ],None),
        ],None) ])
        with self.assertRaises(hrun.RunnerError):
            self.do_run(d,mockloop=loop,catch=False)
            
    def test_allows_forward_at_end(self):
        def loop():
            self.runner.on_next()
        self.do_run(hps.Document([ hps.FirstSection([
            hps.TextBlock("foo",None),
            hps.TextBlock("bar",None)
        ],None) ]),mockloop=loop)
        self.assertEqual(2,self.gui.on_forward_allowed_change.call_count)
        self.assertEqual(True,self.gui.on_forward_allowed_change.call_args_list[1][0][0])
        
    def test_goes_back_over_all_loop_iterations(self):
        def loop():
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_change_selection(0)
            self.runner.on_next()
            self.runner.on_change_selection(1)
            self.runner.on_next()
            self.runner.on_prev()
            self.runner.on_prev()
            self.runner.on_prev()
        self.do_run(hps.Document([
            hps.FirstSection([hps.ChoiceBlock([
                hps.Choice(None,"foo",None,"sec",None) ],None)],None),
            hps.Section("sec",[hps.ChoiceBlock([
                hps.Choice(None,"bar",None,"sec",None),
                hps.Choice(None,"weh","ahuh",None,None) ],None)],None)
        ]),mockloop=loop)
        self.assertEqual(7,self.gui.on_curr_item_change.call_count)
        self.assertEqual(["bar","weh"],
            self.gui.on_curr_item_change.call_args_list[4][0][0].options)
        self.assertEqual(["bar","weh"],
            self.gui.on_curr_item_change.call_args_list[5][0][0].options)
        self.assertEqual(["foo"],
            self.gui.on_curr_item_change.call_args_list[6][0][0].options)



