#!/usr/bin/env python3

import begin
import begin.formatters
import begin.utils
import argparse
import sys    
import re
from . import VERSION
from . import io as hio
from . import parse as hparse
from . import run as hrun


class NoDefaultHelpFormatter(argparse.HelpFormatter):

    def _get_help_string(self, action):
        return re.sub(r'\(default:.*\)', '', action.help)


def _choice_validator(*choices):
    def validator(v):
        if v not in choices:
            raise ValueError("{} not in {}".format(v, choices))
        return v
    return validator


@begin.start(
    formatter_class=NoDefaultHelpFormatter
)
@begin.convert(
    #fromfmt=_choice_validator("hrbrt"), 
    tofmt=_choice_validator("hrbrt","json","xml","markdown"),
    run=_choice_validator("cli","gui"),
)
def main(
        input: "File to read from or '-' (standard input)",
        output: "Output the result. A filename, or '-' (standard output)" =None,
        #fromfmt: "Input format. One of  'hrbrt'" =None,
        tofmt: "Output format. One of 'hrbrt', 'json', 'xml' or 'markdown'" =None,
        run: "Run document interactively. One of 'cli' or 'gui'" =None,
    ):    
    """Processes HRBrT branching text documents"""

    # determine input format
    if input is not None and "." in input:
        ext = input[input.rindex(".")+1:]
    else:
        ext = None
        
    #if fromfmt == "json" or (fromfmt is None and ext in hio.JsonIO.EXTENSIONS):
    #    informat = hio.JsonIO
    #else:        
    #    informat = hio.HrbrtIO
    informat = hio.HrbrtIO

    # read from input stream
    if input not in (None, "-"):
        instream = open(input, "r", encoding='utf-8')
    else:
        instream = sys.stdin

    try:    
        document = informat.read(instream)
    except (hparse.InputError, hparse.ValidationError) as e:
        sys.exit(str(e))

    # validate document
    vfail = document.validate()
    if vfail:
        sys.exit(vfail)

    # if requested, run and add feedback to parse tree
    if run is not None:
        if run == "gui":
            runner = hrun.GuiRunner
        else:
            runner = hrun.CommandLineRunner
            
        try:            
            runner.run(document)
        except hrun.RunnerError as e:
            sys.exit(str(e))

    # if requested, write output to stream
    if output is not None or tofmt is not None:
    
        # determine output format
        if output is not None and "." in output:
            ext = output[output.rindex(".")+1:]
        else:
            ext = None

        if tofmt == "json" or (tofmt is None and ext in hio.JsonIO.EXTENSIONS):
            outformat = hio.JsonIO
        elif tofmt == "markdown" or (tofmt is None and ext in hio.MarkdownIO.EXTENSIONS):
            outformat = hio.MarkdownIO
        elif tofmt == "xml" or (tofmt is None and ext in hio.XmlIO.EXTENSIONS):
            outformat = hio.XmlIO
        else:        
            outformat = hio.HrbrtIO
        
        # write to output stream
        if output not in (None,"-"):
            outstream = open(output, "w", encoding='utf-8')
        elif output == "-":
            outstream = sys.stdout
        elif input in (None,"-"):
            outstream = sys.stdout
        else:
            outstream = open("%s.out.%s" % ( input[:input.rindex(".")]
                if "." in input else input, outformat.EXTENSIONS[0] ), "w", encoding='utf-8')
                            
        with outstream:
            outformat.write(document,outstream)
