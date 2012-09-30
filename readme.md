Hrbrt
=====

Hrbrt (Human-Readable BRanching Text) is a file format which expresses a 
directed graph of text nodes linked by choices, similar to a flow chart. 
Potential uses include decision trees, questionnaires, and videogame dialogue 
scripts. 

Inspired by [Markdown]'s philosophy, Hrbrt is machine-parsable yet perfectly 
human-readable. The lack of markup and other syntactic clutter in Hrbrt's 
syntax makes it easily understandable to non-technical users and convenient to 
author using any basic text editor.

[markdown]: http://daringfireball.net/projects/markdown/

*hrbrt* is a command line program (or python module) for parsing files in Hrbrt
format. It can convert Hrbrt to other formats or "run" a file using command 
line or GUI-based prompts.


`hrbrt` Command
---------------

### Dependencies ###

hrbrt requires [Python 2.7], and optionally [Tkinter] to use the GUI option 
(some distributions package it separately).

[python 2.7]: http://python.org
[tkinter]: http://docs.python.org/library/tkinter.html

### Usage ###

	hrbrt [options] [infile [outfile]]
	
### Positional Arguments ###
	
`infile`

File to read. Use `-` to read from standard input. This is the default.
 
`outfile`

File to write output to. Use `-` to write to standard output. If input file 
is specified, output file defaults to `<infile>.out.<ext>` using the name of 
the input file and the appropriate file extension for the output format. If no 
input file is specified, defaults to standard output.
  
### Options ###

`-h`, `--help`

Show this usage information and exit
  
`-f`, `--fromfmt`

Input format. If not specified, the input format is inferred from the input 
file extension. Currently only `hrbrt` is supported. This is the default.
  
`-t`, `--tofmt`

Output format. One of `hrbrt`, `json`, `xml`, or `markdown`. If not specified, 
the output format is inferred from the output file extension. Default is 
`hrbrt`.

`-v`, `--validate`

Just validate input, reporting syntax errors, and exit

`-r`, `--run`

How to run the file. One of `cl` (command-line), `gui` (a basic graphical 
wizard), or `no` (don't run). Defaults to `cl` if no output file or format is 
specified, otherwise defaults to `no`. The `gui` option requires Tk/Tkinter.


### Examples ###

Run the file *foobar.hb* on the command line

	$ hrbrt foobar.hb

Validate *test.hb* and report errors

	$ hrbrt -v test.hb
	Document is valid!
	
Convert *questionnaire.hb* to markdown format

	$ hrbrt questionnaire.hb questionnaire.md

Convert *dialogue.hb* to XML and output to standard out

	$ hrbrt -t xml dialogue.hb
	<?xml version="1.0" ?>
	<document>
		<section>
			<text>Nice hat!</text>
		</section>
	</document>

Read Hrbrt data from standard input, run using a GUI and output to *foo.js*
in JSON format

	$ hrbrt -r gui - foo.js
	:: [] Yes
	:  [] No


As a Python Module
------------------

To use `hrbrt` as a Python module, first rename the file so that it has a ".py"
extension, then import. The `HrbrtIO` class can be used to parse a Hrbrt 
document from a stream into a parse tree represented by a `Document` object.

See the usage example below:

	>>> import hrbrt, io
	>>> 
	>>> # A minimal Hrbrt document
	... data = ":: Test\n"
	>>> 
	>>> # Create a simple string stream.
	... # Could read from a file stream instead
	... stream = io.BytesIO(data)
	>>> 
	>>> # Parse the data stream
	... document = hrbrt.HrbrtIO.read(stream)
	>>> 
	>>> # Read data from the resulting parse tree
	... print document.sections[0].items[0].text
	Test
	>>> 


Hrbrt Syntax
------------

### How to Read Hrbrt ###

A document in Hrbrt format can be parsed by the recipient's machine and 
presented to them interactively, or the recipient can edit and return the raw 
text document. 

In either case, the recipient begins reading at the start of the document. When
they encounter a set of choices, they mark their selection and read the 
response text beside it. If the response includes a `GO TO` statement, the user
jumps to that section and continues from there, otherwise the user continues 
reading as normal. The user continues to follow the flow of the document until 
they reach the end.

A user reading the raw Hrbrt text may mark their selection at each set of 
options by inserting character data in the corresponding box (typically an 'X'
or '#'). They may also add feedback to the document by adding new lines of
text or writing in the existing blank lines.


### Example ###

Below is an example of Hrbrt syntax:

	:: Hi there. 
	
	%% Please fill in my questionnaire!
	
	:: What would you say
	:  is your favourite animal?
	
	:: [ ] Cat		-- GO TO cats
	:  [ ] Dog		-- GO TO other
	:  [ ] Turkey	-- GO TO other
	
	=== Cats ===
	
	:: What is your favourite breed of cat?
	
	:: [ ] Burmese
	:  [ ] Siamese
	:  [ ] Persian
	:  [ ] Other
	
	:: What do you like most about cats?
	
	:: [ ] Their ears	-- GO TO end
	:  [ ] Their noses	-- GO TO end
	:  [ ] Their paws	-- GO TO end
	:  [ ] Their fur	-- GO TO end
	
	=== Other ===
	
	:: Are you sure you don't like 
	:  CATS more?
	
	:: [ ] Yes	-- GO TO end
	:  [ ] No	-- Your finger slipped. I see.
					GO TO cats
	
	=== End ===
	
	:: Thanks for your input!


### Sections ###

Sections serve to split up the document and provide reference points to which
the user can be directed as they traverse the document. (See explanation of 
"go-to" statements in the chapter "Choice Responses").

Each section contains one or more *blocks* of content. These may be any 
combination of *text*, *instruction* or *choice* blocks (see subsequent 
chapters for details).

The first section of the document is where the user begins reading, and has no 
heading. Each subsequent section is indicated by a heading with 2 or more 
equals signs on each side. The section heading defines the section's name, 
which is case-insensitive. Section names must only contain letters, numbers,
underscores, hyphens or spaces. All content below this heading, down to the
next heading, is contained within the section.

Example:
	
	=== My Section ===


### Text and Recipient's Feedback ###

Blocks of regular text can be added to the document by starting the first line
of the block with a double colon, and each subsequent line with a single colon.
A Hrbrt viewing tool will typically present separate text blocks to the user 
one at a time.

Lines without the preceding colons are assumed to be part of the recipient's 
feedback. It is assumed that if the recipient leaves feedback in the document, 
they will omit the colon from the start. 

Example:

	:: This is part of the 
	:  document text that
	:  the sender wrote
	
	But this is the 
	recipient's feedback
	
When the document is parsed, recipient feedback is included in the output. 
Feedback within a choice block (see "Choices" chapter) is grouped together and 
attached to the block, and other feedback is grouped together and attached to 
the section.


### Instructions ###

Instruction blocks are *not* presented to the user when parsed by a program 
such as a visual Hrbrt reader. They are intended for providing instructions to 
users reading the raw file text only. The first line of an instruction block 
starts with a double percent sign, and each subsequent line with a single 
percent sign.

Example:

	%% Please fill in this document 
	%  and send it back as soon as 
	%  possible


### Choices ###

Blocks of choices are used to present the user with options from which they can
make a single selection. Users Reading the raw Hrbrt text indicate their 
selection by writing something inside the box beside it. This is typically an 
`X` or `#` character, but may contain any single-line content other than `]`.

Each choice of the block goes on its own line. The first choice starts with a 
double colon, and each subsequent choice starts with a single colon. Each 
option then consists of a pair of square brackets `[]` followed by the option 
description. The description may run onto multiple lines, each starting with a 
colon.

Example:

	:: [] Animal
	:  [] Some kind
	:      of Mineral
	:  [] Vegetable

A choice block may not immediately follow another choice block. They must be
separated, using a text block for example.


### Choice Responses ###

Each choice may optionally be followed by response text. This is 
separated from the choice description by a pair of hyphens `--`. The response 
text gives feedback and further instructions to the recipient on selection of 
that option.

A choice response may optionally be followed by a go-to statement. This 
consists of the words `GO TO` in uppercase, followed by a section name, and 
optional trailing punctuation. The section names are case-insensitive. 
The go-to statement instructs the recipient or viewing tool as to which section
to jump to next.

The response and go-to statement may flow onto multiple lines, each starting 
with a colon.

Example:

	:: [] Animal	-- Good choice! GO TO my section
	:  [] Mineral	-- Ok. GO TO some section.
	:  [] Vegetable	-- Not bad, but I 
	:                  think you could
	:                  have chosen better.
	:                  GO TO end


### Quoting ###

All lines in the document my optionally be prefixed with `>` markers, as would 
typically be added by an email client. The `>` markers themselves are ignored, 
but the following line content is still parsed. This allows recipients to reply
directly to a document sent by email and it still be parsable.


### Section Flow Rules ###

A valid Hrbrt document *must* allow the user to reach the end of the document's
final section. Dead ends and infinite loops are not allowed.

Before reaching the end of a section (other than the final section) the user 
*must* be explicitly directed to a different section by a 
go-to statement. In other words, a document is not valid
if the user can "fall through" to the end of a section. 

For example, the following is *not* allowed:

	:: [] Option A -- GO TO my section
	:  [] Option B
	
	== My Section ==
	...

A choice block may not immediately follow another choice block (for 
readability reasons). They must be separated by another block, such as a text 
block.


Hrbrt Formal Definition
-----------------------

	<Document> ::= <FirstSection> <Section>*
	
	<FirstSection> ::= <SectionContent>
	
	<Section> ::= <Heading> <SectionContent>
	
	<SectionContent> ::= ( <BlankLine> | !<StarterLine> <FeedbackLine> )*
	                        ( <ChoiceBlock> | <InstructionBlock> | <TextBlock> )+
	
	<BlankLine> ::= <QuoteMarker>? <LineWhitespace>? <Newline>
	
	<ChoiceBlock> ::= <FirstChoice>
	                   ( <BlankLine> | <Choice> | !<StarterLine> <FeedbackLine> )*
	
	<InstructionBlock> ::= <FirstInstructionLine>
	                        ( <BlankLine> | <InstructionLine> 
	                          | !<StarterLine> <FeedbackLine> )*   
	
	<TextBlock> ::= <FirstTextLine> 
	                 ( <BlankLine> | <TextLine> | !<StarterLine> <FeedbackLine> )*
	
	<StarterLine> ::= <FirstTextLine> | <FirstInstructionLine> 
	                    | <Heading> | <FirstChoice>
	
	<QuoteMarker> ::= ( ( ' ' | '\t' )* '>' )+ ( ' ' | '\t' )*
	
	<LineWhitespace> ::= ( ' ' | '\t' )+
	
	<Newline> ::= '\r' '\n'? | '\n'
	
	<Choice> ::= <QuoteMarker>? <TextLineMarker> 
	               <LineWhitespace>? <ChoiceMarker> <ChoiceContent>
	
	<FirstChoice> ::= <QuoteMarker>? <FirstTextLineMarker>
	                    <LineWhitespace>? <ChoiceMarker> <ChoiceContent>
	
	<ChoiceContent> ::= <LineWhitespace>? <ChoiceDescription> <ChoiceResponse>?
	                      <LineWhitespace>? <Newline>
	
	<ChoiceMarker> ::= '[' <LineWhitespace>? <ChoiceMarkerMark>? ']'
	
	<ChoiceMarkerMark> ::= ( '\x20-\x5C' | '\x5E-\x7E' | '\t' )+
	
	<ChoiceDescription> ::= <ChoiceDescPart> 
	                         ( ChoiceDescNewline> <ChoiceDescPart> )*
	
	<ChoiceDescNewline> ::= <Newline>
	                     ( <BlankLine> | !( <StarterLine> | <TextLine> ) <FeedbackLine> )*
	                     <QuoteMarker>? <TextLineMarker> <LineWhitespace>? !<ChoiceMarker>
	
	<ChoiceDescPart> ::= ( '\x20-\x2C' | '\x2E-\x7E' | '\t' | '-' !'-' )+
	
	<ChoiceResponse> ::= <ChoiceDescNewline>? '-' '-'
	                      ( <ChoiceDescNewline>? <ChoiceResponseDesc> <ChoiceGoto>? 
	                        | <ChoiceGoto> )
	
	<ChoiceResponseDesc> ::= <ChoiceResponseDescPart>
	                          ( <ChoiceDescNewLine> <ChoiceResponseDescPart> )*
	
	<ChoiceResponseDescPart> ::= ( '\x20-\x46' | '\x48-\x7E' 
	                               | 'G' !( 'O' ' ' 'T' 'O') )
	
	<ChoiceGoto> ::= <ChoiceDescNewLin>? 'G' 'O' ' ' 'T' 'O' 
	                   <LineWhitespace>? <Name> <EndPunctuation>?
	
	<EndPunctuation> ::= ( '.' | ',' | ':' | ';' | '!' | '?' )+
	
	<Heading> ::= <QuoteMarker>? <HeadingMarker> <LineWhitespace>?
	                <Name> <HeadingMarker> <Newline>
	
	<HeadingMarker> ::= '=' '='+
	
	<Name> ::= ( 'a-z' | 'A-Z' | '0-9' | '_' | '-' )
				( 'a-z' | 'A-Z' | '0-9' | '_' | '-' | ' ' )*
	
	<InstructionLine> ::= <QuoteMarker>? <InstructionLineMarker> <TextLineContent>
	
	<InstructionLineMarker ::= '%' !'%'
	
	<FirstInstructionLine> ::= <QuoteMarker>? 
	                             <FirstInstructionLineMarker> <TextLineContent>
	
	<FirstInstructionLineMarker> ::= '%' '%'
	
	<LineText> ::= ( '\x20-\x7E' | '\t' )+
	
	<TextLine> ::= <QuoteMarker>? <TextLineMarker> <TextLineContent>
	
	<TextLineMarker> ::= ':' !':'
	
	<FirstTextLine> ::= <QuoteMarker>? <FirstTextLineMarker> <TextLineContent>
	
	<FirstTextLineMarker> ::= ':' ':'
	
	<TextLineContent> ::= <LineWhitespace>? <LineText> <Newline>
	
	<FeedbackLine> ::= <QuoteMarker>? <LineText> <Newline>
	

Credits and Licence
-------------------

* Author: Mark Frimston
* Email: <mfrimston@gmail.com>
* Homepage: <http://markfrimston.co.uk>
* Project page: <https://github.com/Frimkron/hrbrt>

The `hrbrt` tool is released under the [MIT licence]. For the full text of 
this licence, see the source file.

[MIT licence]: http://en.wikipedia.org/wiki/Mit_license


