#!/usr/bin/python2


# TODO: Consecutive choice block check belongs in validate method
# TODO: JSON input
# TODO: XML input
# TODO: HTML output
# TODO: S-Exp output
# TODO: S-Exp input
# TODO: Allow gotos at the end of sections.
# TODO: Allow header line in syntax
# TODO: Open document output


import begin
import begin.utils
import sys    
from . import io as hio
from . import parse as hparse
from . import run as hrun


def _choice_validator(*choices):
    def validator(v):
        if v not in choices:
            raise ValueError("{} not in {}".format(v, choices))
        return v
    return validator
    

@begin.start
@begin.convert(
    fromfmt=_choice_validator("hrbrt"), 
    tofmt=_choice_validator("hrbrt","json","xml","markdown"),
    run=_choice_validator("cli","gui","no"),
)
def main(
        input,  # file to read from
        output="-",  # file to write to
        fromfmt=None,  # input format
        tofmt=None,    # output format
        validate=False,  # just validate input
        run="cli",  # how to run file
    ):
    """Processes HRBrT branching text documents"""

    # determine input format
    if input is not None and "." in input:
        ext = input[input.rindex(".")+1:]
    else:
        ext = None
        
    if fromfmt == "json" or (fromfmt is None and ext in hio.JsonIO.EXTENSIONS):
        informat = hio.JsonIO
    else:        
        informat = hio.HrbrtIO

    # read from input stream
    if input not in (None, "-"):
        instream = open(input,"r")
    else:
        instream = sys.stdin

    try:    
        document = informat.read(instream)
    except hparse.InputError as e:
        sys.exit(str(e))

    # validate document
    vfail = document.validate()
    if vfail:
        sys.exit(vfail)

    # if just validating, stop here
    if validate:
        print("Document is valid!")
        sys.exit(0)
    
    # default to command line run if no run or output specified
    if run is None and output is None and tofmt is None:
        run = "cli"
    
    # if necessary, run and add feedback to parse tree
    if run not in (None,"no"):
        if run == "gui":
            runner = hrun.GuiRunner
        else:
            runner = hrun.CommandLineRunner
            
        try:            
            runner.run(document)
        except hrun.RunnerError as e:
            sys.exit(str(e))
    
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
        outstream = open(output,"w")
    elif output == "-":
        outstream = sys.stdout
    elif input in (None,"-"):
        outstream = sys.stdout
    else:
        outstream = open("%s.out.%s" % ( input[:input.rindex(".")]
            if "." in input else input, outformat.EXTENSIONS[0] ),"w")
                        
    with outstream:
        outformat.write(document,outstream)
