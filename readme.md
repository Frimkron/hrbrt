Hrbrt
=====

*hrbrt* is a command line program for parsing Hrbrt (Human-Readable BRanching
Text) documents. A file in Hrbrt format expresses a directed graph of text 
nodes linked by choices. Potential uses include decision trees, questionaires, 
and videogame scripts. Inspired by [Markdown]'s philosophy, Hrbrt is 
machine-parsable while attempting to remain human-readable in its raw format.

[markdown]: **TODO**

hrbrt Command
-------------

### Dependencies

hrbrt requires [Python 2], and optionally [Tkinter] to use the gui option.

[python 2]: **TODO**
[tkinter]: **TODO**

### Usage

	hrbrt [options] [file]
	
file
  : File to read (optional). Use `-` to read from standard input. This is the default.
  
### Options

-h, --help
  : Show usage page and exit
  
-o, --output
  : File to write output to. Use `-` to write to standard output. If input file is 
  specified, output file defaults to `<infile>.out.<ext>` using the name of the
  input file and the appropriat file extension for the output format. If no input
  file is specified, defaults to standard output.

-f, --fromfmt
  : Input format. If not specified, the input format is inferred from the input file 
  extension. Currently only `hrbrt` is supported. This is the default.
  
-t, --tofmt
  : Output format. One of `hrbrt`, `json`, `xml`, or `markdown`. If not specified, the 
  output format is inferred from the output file extension. Default is `hrbrt`.

-v, --validate
  : Just validate input, reporting syntax errors, and exit

-r, --run
  : How to run the file. One of `cl` (command-line), `gui` (a basic graphical wizard),
  or `none` (don't run). Defaults to `cl` if no output file or format is specified, 
  otherwise defaults to `none`. The `gui` option requires Tk/Tkinter.


### Examples

Run the file *foobar.hb* on the command line

	$ hrbrt foobar.hb

Validate *test.hb* and report errors

	$ dectree -v test.hb
	Document is valid!
	
Convert *questionnaire.hb* to markdown format

	$ dectree -o questionnaire.md questionnaire.hb

Convert *dialogue.hb* to XML and output to standard out

	$ dectree -t xml -o - dialogue.hb
	<?xml version="1.0" ?>
	<dectree>
		<section>
			<text>Nice hat!</text>
		</section>
	</dectree>

Read Hrbrt data from standard input, run using a GUI and output to *foo.js*
in JSON format

	$ dectree -r gui -o foo.js -
	:: [] Yes
	:  [] No


Hrbrt Syntax
------------

### Example

Below is an example of Hrbrt syntax:


```hrbrt

:: Hi there. 

%% Please fill in my questionaire!

:: What would you say
:  is your favourite animal?

:: [ ] Cat		-- GO TO cats
:  [ ] Dog		-- GO TO other
:  [ ] Turkey	-- GO TO other

=== Cats ===

:: What is your favourite breed of cat?

:: [ ] Burmese
:  [ ] Siamese

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

```

Details on the various document elements are described below:


### Sections ###

The first section of the document has no heading, but each subsequent section 
is indicated by a heading with 2 or more equals signs on each side. The section
heading defines the section's name, which is case-insensitive. Section names 
may be letters, numbers or any combination and may contain spaces. For example:

```	
=== My Section =====
```

This would indicate a section called "my section". All content below this 
heading, down to the next heading, is contained within this section.


### Text and Recipient's Comments ###

Regular text is added to the document by starting each line with a colon, and 
the first line of each text block starts with a double colon.  Lines without 
the preceding colons are assumed to be part of the recipient's comments. It is 
assumed that if the recipient leaves feedback in the document, they will omit 
the colon-space from the start. Example:

```	
:: This is part of the 
:  document text which 
:  the sender wrote

But this is the 
recipient's feedback
```

### Instructions ###

Lines beginning with a percent sign are ignored by the parser and are intended 
for writing instructions to users reading the raw file text. The first line of 
an instruction block starts with a double percent sign. Example:

``` 
%% Please fill in this document 
%  and send it back as soon as 
%  possible
```

### Choices ###

Each option for the recipient starts with a pair of square brackets `[]` at the
start of the line, after the colon (or double colon for the first line). There 
may optionally be spaces between the brackets. Text following the square 
brackets is treated as the option description. This may run onto multiple 
lines, but each line must start with a colon. Options in the same block form a 
group. At each choice block, the recipient indicates their (single) selection 
from the group by adding text inside the square bracket (typically an 'X' 
or '#').


### Choice Responses ###

Each choice may optionally be followed by response text. This is separated from
the choice description by a pair of hyphens `--`. The response text gives 
feedback and further instructions to the recipient on selection of that option.
A choice response may optionally be followed by a go-to statement. This 
consists of the words `GO TO` in uppercase, followed by a section name, and 
optional trailing punctuation. The section names are case-insensitive. The 
go-to statement instructs the recipient which section to jump to next.


### Quoting ###

All lines in the document my optionally be prefixed with `>` markers, as would 
typically be added by an email client. This allows recipients to reply directly
to a document sent by email and it still be parsable.


How to Read Hrbrt
-----------------

A document in Hrbrt format can be machine parsed by the recipient's machine and
presented to them interactively, or the recipient can edit and return the raw 
text document. In either case, the recipient begins reading at the start of the
document. When they encounter a set of choices, they mark their selection and 
read the response text beside it. If the response includes a `GO TO` statement,
the user jumps to that section and continues from there, until they reach the 
end of the document.
