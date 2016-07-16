#!/usr/bin/python3

import copy
import csv
import subprocess
import sys
import tempfile

from lxml import etree


NSMAP = {
    'svg': "http://www.w3.org/2000/svg",
}


def replace(root, replacements):
    '''Apply replacements to an SVG ElementTree

    Look for class="template" attributes. next(replacements) should provide a
    dictionary of "class=<key>" replacements for tspan objects inside the
    template.

    Returns a tuple of (count, go_again). count is how many templates we
    filled. go_again is whether replace needs to be called again, which is True
    unless we hit StopIteration while reading from replacements.
    '''
    count = 0
    for template in root.findall(".//*[@class='template']"):
        try:
            data_row = next(replacements)
        except StopIteration:
            return count, False
        count += 1
        for k, v in data_row.items():
            for e in template.findall(".//svg:tspan[@class='%s']" % k,
                                      namespaces=NSMAP):
                e.text = v
    return count, True


def generate_page_svg_trees(data_iterator, svg_template_path):
    with open(svg_template_path) as svg_fobj:
        master_tree = etree.parse(svg_fobj)

        while True:
            page_tree = copy.deepcopy(master_tree)
            count, go_again = replace(page_tree.getroot(), data_iterator)
            if count:
                yield page_tree
            if not go_again:
                break


def svg_tree_to_pdf(tree, tempdir):
    pdf = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)

    with tempfile.NamedTemporaryFile(dir=tempdir, suffix='.svg') as svg:
        tree.write(svg)
        svg.flush()
        subprocess.check_call(['inkscape', '-A', pdf.name, svg.name])

    return pdf.name


def concatenate_pdfs(input_pdf_paths, output_pdf_path):
    args = [
        'gs',
        '-dBATCH',
        '-dNOPAUSE',
        '-q',
        '-sDEVICE=pdfwrite',
        '-sOutputFile=%s' % output_pdf_path
    ]
    args.extend(input_pdf_paths)
    subprocess.check_call(args)


def generate_pdf(data_iterator, svg_template_path, pdf_output_path):
    with tempfile.TemporaryDirectory() as tempdir:
        pdfs = []
        for tree in generate_page_svg_trees(data_iterator, svg_template_path):
            pdfs.append(svg_tree_to_pdf(tree, tempdir))
        concatenate_pdfs(pdfs, pdf_output_path)


def main(csv_data_path, svg_template_path, pdf_output_path):
    with open(csv_data_path, 'r') as csv_fobj:
        reader = csv.DictReader(csv_fobj)
        generate_pdf(iter(reader), svg_template_path, pdf_output_path)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
