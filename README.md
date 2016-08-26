SVG Template Mail Merge to PDF
==============================

Features
--------

* CSV data input.
* Parses SVG properly: no nasty hacked search and replacing.
* Supports multiple data rows per page (just set up your SVG
  page appropriately).
* Multiple page PDF output.
* QR code support.

Limitations
-----------

* Text fields, and up to one QR code only per record.
* An individual text field must be on a single line (we modify just the
  `tspan` tag).
* Cannot combine with other uses of the `class` attribute due to dumb
  XPath query (pull requests welcome).

Instructions
------------

1. Create text fields using Inkscape. Populate them with a single line
of text.
2. For QR codes, create a rectangle instead.
2. Go to "Edit->XML Editor" in Inkscape.
3. Select a field. For text fields, open it up to find the `tspan` tag.
For rectangles, just the rectangle itself is fine.
4. Name this object by adding an attribute of key `class`. The value of
the attribute can be a field name of your choice.
5. Group the fields and any other design elements together.
6. Select the group.
7. In the XML Editor, add an attribute of key `class` with a value of
`template`.
8. Use "Edit->Clone->Create Tiled Clones" or similar to create multiple
instances if required.
9. Save this file as your master template.
10. Before passing this through the mail merge program, you must use
"Edit->Clone->Unlink clone" on any clones that are used for templates.
This is so that each template can be changed independently in the merge.
Save this as a different temporary file to feed to the merge. This way
you can continue to use your master template's linked clones to make
later changes if necessary.
11. Prepare a CSV file. There must be a heading row with fields that
match your field names (the `class` attributes you added earlier).
12. Run `python3 generate.py input.svg input.csv output.pdf`

Installing
----------

This program requires Inkscape, Ghostscript, Python 3 and the Python
lxml module. On Ubuntu, you can install these with `sudo apt install
inkscape ghostscript python3 python3-lxml`.
