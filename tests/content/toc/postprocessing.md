Title: TOC with postprocessing
Date: 2020-02-03 23:06:08-08:00
Entry-ID: 1886
UUID: cc74548e-f159-55f2-a052-00fd680e74c9

## Preamble[^pre]

[^pre]: This footnote shouldn't appear in the ToC but should be accounted for.

This TOC needs postprocessing[^post].

[^post]: This footnote should also be accounted for.

.....

## Smartypants stuff

### A "smartquotes" heading

This heading has "smartquotes."

### Em-dashes -- not just for fun --- perhaps

This heading has an en-dash -- and maybe an em-dash --- yes

### Fractions like 1/2 and 1/4 are silly

They sure are.

## Image stuff

### <img src="../images/rawr.jpg"> Inline rawr?

Nope

### ![](../images/rawr.jpg) Markdown rawr?

Nope

### Markdown [rawr link](../images/rawr.jpg)

Nope

### HTML <a href="../images/rawr.jpg">rawr link</a>

Nope

## Formatting

### *Emphasis* and **strong**

Should be allowed.

### <em>em</em> <b>b</b> <sup>sup</sup> <sub>sub</sub> <strong>strong</strong> <i>i</i>

Should be allowed.

### Superscripts^&infin;

I'll allow it.

### Footnotes[^notes]

[^notes]: This makes no sense in the ToC, but does in the text

Makes no sense in the ToC, but the Markdown renderer knows to filter it out.

### Code, e.g. `code`

This is also supported and sensible.

### Math? $$d\frac{e^x}{dx} = e^x$$

I mean, this isn't actually HTML so that's up to MathJax...

### Also ~~misteaks~~ mistakes can be made

Sure.

### Is this ==notable?==

Sure, why not.
