% A Decision Tree Document Format
% Mark Frimston
% 2012-03-17

Motivation
----------

Sometimes, a simple message is not a sufficiently productive way of
communicating with someone. After a small number of back and forth emails, 
someone will decide to pick up the phone or meet in person to have a 
face-to-face conversation. This way, the feedback loop is shorter and each 
question can be devised based on the previous answer received in order to 
exchange the necessary information between participants.

Face to face conversations are not always possible, however. And waiting for 
someone to become available for such a discussion can mean that the original 
reason for the discussions gets forgotten about. Sometimes one can end up 
trying to ask relevant questions in a message such as an email, by anticipating
the answers the recipient might give and formulating a kind of if-else tree 
structure in the message. For example:

> Hey Alice
> 
> Did you get the file server up and running yet? If so, do you know what port 
> it's listening on? Or if not, do you know roughly when it'll be ready? And 
> could you set it up to listen on port 4444?
> 
> Thanks,
> Bob

Here Bob provides two different further questions based on the anticipated 
answers to his original question. A single level of if-else branch is about as 
far as one can go before grammar starts to get in the way and the message 
becomes confusing:

> Hey Alice
>
> Are you in charge of setting up the new file server? If so, did you get it up 
> and running yet? If you did, is there a password set up for it already? If 
> there is, could you leave it with Chris on Tuesday, please. If there isn't 
> a password, please could you leave it like that for the time being and I will 
> set one. If the server isn't ready yet, please could you hand that job over to 
> Dianne, assuming she isn't busy. If she is busy, please could give it to Ed
> instead. When you've handed that over, could you let me know: are we still 
> waiting on that hard disk from the supplier? If we are, please could you give 
> them a call and ask them what's taking so long. If we're not, let me know what 
> the problem is. If you're not in charge of the file server, and it's Frank 
> instead, tell him to pop in for a chat with me when he's around tomorrow. Or if 
> it's George, and he's still on holiday, please could you take over. If he's not 
> on holiday, have him contact me. Otherwise if it's neither of them, let me know 
> who is in charge of the damn file server.
>
> Thanks,
> Bob

The decision tree that this message describes looks like this:

    In charge of file server?
      |-- YES 
      |    '-- Is it up and running yet?
      |         |-- YES
      |         |    '-- Is there a password?
      |         |         |-- YES 
      |         |         |    '-- Leave with Chris on Tues
      |         |         '-- NO
      |         |              '-- Leave as is, I will set
      |         '-- NO
      |              |-- Is Dianne busy?
      |              |    |-- YES
      |              |    |    '-- Hand file server to Ed
      |              |    '-- NO
      |              |         '-- Hand file server to Dianne
      |              '-- Waiting on hard disk?
      |                   |-- YES
      |                   |    '-- Ask what's taking so long
      |                   '-- NO
      |                        '-- Let me know what problem is
      '-- NO
           '-- Is Frank in charge?
                |-- YES
                |    '-- Tell him to pop in tomorrow
                '-- NO
                     '-- Is George in charge?
                          |-- YES
                          |    '-- Is he on holiday?
                          |         |-- YES
                          |         |    '-- You take over
                          |         '-- NO
                          |              '-- Have him contact me
                          '-- NO
                               '-- Tell me who's in charge

Which gets a little difficult to express in a plain text email, for example. I 
propose a decision tree format to make this kind of multiple-choice message 
easier for the writer to express and easier for the recipient to understand.

Potential Uses
--------------

* Email discussions
* Branching questionnaires
* Knowledge bases
* Troubleshooters
* Walkthroughs
* Videogame dialogue trees

Goals
-----

My aim for this format is as follows:

* Should be able to create in simple ascii text
* Should be adequately readable in its raw text format (see 
  [the Markdown philosophy][1])
* Should be parsable by machine in order to transform into a nicer-presented 
  format, for example introducing radio buttons and folding
* Should be clear to the recipient how to respond
* Recipient's response should also be machine-parsable so, for example,  the 
  thread of conversation can be presented
* Sender should be able to express a tree of multiple-choice questions
* Recipient should be able to follow the trail of relevent questions based on
  their answers.
* Sender should be able to insert sequences of text and questions for each 
  decision branch in the tree
* Nice to have: format also parseable as Markdown
* Recipient should be able to read all of the conversation branches
* Recipient should be able to go back and change their mind about their 
  responses.
* Recipient should be able add comments to clarify their choices and provide 
  additional information
  
[1]: http://daringfireball.net/projects/markdown/

Format
------

Here is an example document:

    : Hi Alice,

    %  Please put X in each box as appropriate and leave additional 
    %  comments on separate lines (without a : at the start).  You 
    %  can follow "GO TO <section>" instructions by searching for 
    %  "== <section>"using ctl+f, for example.
    
    : Who's in charge of setting up the file server?
    
    : [] Me		-- GO TO me.
    : [] Frank	-- Tell him to pop in to have a chat with me when he's 
    :  				in tomorrow. GO TO end.
    : [] George	-- GO TO george 
    : [] Other	-- Let me know whos's in charge of the damn file server. 
    :  				GO TO end.

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

Details on the various document elements are described below:

### Sections ###

The first section of the document has no heading, but each subsequent section 
is indicated by a heading with 2 or more equals signs on each side. The section
heading defines the section's name, which is case-insensitive. Section names 
may be letters, numbers or any combination and may contain spaces. For example:

    === My Section =====

This would indicate a section called "my section".

### Text and Recipient's Comments ###

Regular text is added to the document by starting each line with a colon and 
space. Lines without the preceding colon-space are assumed to be part of the 
recipient's comments. It is assumed that if the recipient leaves feedback in 
the document, they will omit the colon-space from the start. Example:

    : This is part of the 
    : document text
    
    But this is the 
    recipient's feedback

### Instructions ###

Lines beginning with a percent sign and space are ignored by document parsers 
and are intended for writing instructions to users reading the raw file text.
Example:

    % Please fill in this document and send it back

### Choices ###

Each option for the recipient starts with a pair of square brackets `[]` at the
start of the line, after the colon space. There may optionally be spaces 
between the brackets. Text following the square brackets is treated as the 
option description. This may run onto multiple lines, but each line must start 
with a colon-space and a blank line will end the choice. Unbroken sequences of 
choices are treated as the same group. Text lines, instruction lines and new 
sections will end the current choice group. At each choice group, the recipient
indicates their (single) selection from the group by adding text inside the 
square bracket (typically an 'X' or '#').

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


Use
---

A document in this format can be interpreted by the recipient's machine and 
presented to them interactively, or the recipient can edit and return the raw 
text document. In either case, the recipient begins reading at the start of the
document. When they encounter a set of choices, they mark their selection and 
read the response text beside it. If the response includes a `GO TO` statement,
the user jumps to that section and continues from there, until they reach the 
end of a section or the end of the document.


Formal Definition
-----------------

    <document> ::= <first-section> <section> *
    <first-section> ::= <section-content>
    <section> ::= <heading> <section-content>
    <heading> ::= <quote-marker> ? <heading-marker> <line-whitespace> ? <name> 
    				<line-whitespace> ? <heading-marker> <linebreak>
    <name> ::= <word> ( <line-whitespace> <word> ) *
    <section-content> ::= <blank-line> * <block> +
    <block> ::= <text-block> | <instruction-block> | <choice-block> | <feedback-block>
    <text-block> ::= <text-line> + <blank-line> *
    <text-line> ::= <quote-marker> ? <text-line-marker> <line-text> <linebreak>
    <line-text> ::= <line-whitespace> ? <line-non-white> <line-part> * 
    <line-non-white> ::= <word> | <punctuation>
    <line-part> ::= <word> | <punctuation> | <line-whitespace>
    <instruction-block> ::= <instruction-line> + <blank-line> *
    <instruction-line> ::= <quote-marker> ? <instruction-line-marker> 
    						<line-text> <linebreak>
    <choice-block> ::= <choice> + <blank-line> *
    <choice> ::= <quote-marker>? <choice-marker> <multiline-text> 
    				<choice-response> ? <linebreak>
    <multiline-text> ::= <line-text> ( <multiline-break> <line-text> ) *
    <multiline-break> ::= <linebreak> <quote-marker> ? <text-line-marker>
    <choice-marker> ::= <choice-marker-open> <line-text> ? <choice-marker-close>
    <choice-response> ::= <choice-response-separator> <multiline-text> ? 
    						<choice-goto> ? 
    <choice-goto> ::= <goto-marker> <line-whitespace> ? <name> <punctuation> ?
    <feedback-block> ::= <feedback-line> + <blank-line> *
    <feedback-line> ::= <line-text> <linebreak>
    <blank-line> ::= <quote-marker> ? <line-whitespace> ? <linebreak>
    
    quote-marker				/> /
    linebreak					/\n/
    heading-marker				/={2,}/
    text-line-marker			/: /
    instruction-line-marker 	/% /
    word						/[a-zA-Z0-9_-]+/
    punctuation					/[`¬!"£$%^&*()_-+=#~}\]{['@;:\/?.>,<\\|]/
    choice-marker-open			/: \[/
    choice-marker-close			/\]/
    choice-response-separator	/--/
    goto-marker					/GO TO/
    line-whitespace				/[ \t]+/

