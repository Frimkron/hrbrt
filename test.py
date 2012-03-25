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

	@mock_globals(dt,"FirstSection","ZeroOrMore","Char")
	def test_parse_parses_firstsection_with_branched_input(self):
		dt.FirstSection.parse.return_value = None
		i = mock.Mock()
		b = mock.Mock()
		i.branch.return_value = b
		dt.Document.parse(i)
		dt.FirstSection.parse.assert_called_once_with(b)

	@mock_globals(dt,"FirstSection","ZeroOrMore","Char")		
	def test_parse_expects_firstsection(self):
		dt.FirstSection.parse.return_value = None
		i = mock.Mock()
		self.assertIsNone( dt.Document.parse(i) )
		
	@mock_globals(dt,"FirstSection","ZeroOrMore","Char")
	def test_parse_parses_zero_or_more_sections_with_branched_input(self):
		dt.FirstSection.parse.return_value = object()
		z = mock.Mock()
		z.parse.return_value = []
		dt.ZeroOrMore.return_value = z
		i = mock.Mock()
		b = mock.Mock()
		i.branch.return_value = b
		dt.Document.parse(i)
		dt.ZeroOrMore.assert_called_once_with(dt.Section)
		z.parse.assert_called_once_with(b)
		
	@mock_globals(dt,"FirstSection","ZeroOrMore","Char")
	def test_parse_parses_char0_with_branched_input(self):
		dt.FirstSection.parse.return_value = object()
		z = mock.Mock()
		z.parse.return_value = []
		dt.ZeroOrMore.return_value = z
		i = mock.Mock()
		b = mock.Mock()
		i.branch.return_value = b
		dt.Document.parse(i)
		c = mock.Mock()
		dt.Char.return_value = c
		dt.Char.assert_called_once_with('\x00')
		c.parse.assert_called_once_with(b)
		
		
"""	
Testing strategy: don't bother testing utility classes individually.
Do need to test that failed branches don't consume input.
But input object is mocked.
Input branching is already covered by tests. Just need to know that 
sub-expressions make use of it.
Ok - will test each sub-expression individually to avoid multi-level
mock input branches
"""

unittest.main()

