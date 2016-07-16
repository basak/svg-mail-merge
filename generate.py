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
    '''
    for template in root.findall(".//*[@class='template']"):
        for k, v in next(replacements).items():
            for e in template.findall(".//svg:tspan[@class='%s']" % k,
                                      namespaces=NSMAP):
                e.text = v


def generate_page_svg_trees(csv_data_path, svg_template_path):
    with open(svg_template_path) as svg_fobj:
        master_tree = etree.parse(svg_fobj)

    with open(csv_data_path, 'r') as csv_fobj:
        reader = csv.DictReader(csv_fobj)
        read_iter = iter(reader)
        try:
            while True:
                page_tree = copy.deepcopy(master_tree)
                replace(page_tree.getroot(), read_iter)
                yield page_tree
        except StopIteration:
            # The final (possibly partial) page
            # Minor bug: a blank page is considered a final partial page
            yield page_tree


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


def main(csv_data_path, svg_template_path, pdf_output_path):
    with tempfile.TemporaryDirectory() as tempdir:
        pdfs = []
        for tree in generate_page_svg_trees(csv_data_path, svg_template_path):
            pdfs.append(svg_tree_to_pdf(tree, tempdir))
        concatenate_pdfs(pdfs, pdf_output_path)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
