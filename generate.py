#!/usr/bin/python3

import argparse
import copy
import csv
import io
import os
import subprocess
import sys
import tempfile

from lxml import etree
import pyqrcode


NSMAP = {
    'svg': "http://www.w3.org/2000/svg",
}


class QrCreator:
    def __init__(self, source, key):
        self.source = iter(source)
        self.key = key

    def __iter__(self):
        return self

    def __next__(self):
        n = dict(next(self.source))
        qr = pyqrcode.create(n[self.key], mode='binary', error='L')
        f = io.BytesIO()
        qr.svg(f, omithw=True)
        f.seek(0)
        xml = etree.parse(f)
        n[self.key] = xml.getroot()
        return n


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
                # Replace text with data as-is
                e.text = v
            for e in template.findall(".//svg:rect[@class='%s']" % k,
                                      namespaces=NSMAP):
                # If the rect has a transform, that needs to be applied
                # in a wrapping <g>.
                if e.get('transform'):
                    replacement = etree.Element('g')
                    replacement.set('transform', e.get('transform'))
                    replacement.append(v)
                else:
                    replacement = v
                # Replace rect with XML (expected to be an <svg> element)
                e.getparent().replace(e, replacement)
                for attr in ['class', 'x', 'y', 'width', 'height']:
                    v.set(attr, e.get(attr))

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


def generate_pdf(data_iterator, svg_template_path, pdf_output_path, overwrite):
    with tempfile.TemporaryDirectory() as tempdir:
        pdfs = []
        for tree in generate_page_svg_trees(data_iterator, svg_template_path):
            pdfs.append(svg_tree_to_pdf(tree, tempdir))
        if not overwrite:
            open(pdf_output_path, 'x').close()
        concatenate_pdfs(pdfs, pdf_output_path)


def process_csv(csv_data_path, svg_template_path, pdf_output_path,
        overwrite, qr=None):
    with open(csv_data_path, 'r') as csv_fobj:
        csv_reader = csv.DictReader(csv_fobj)

        if qr:
            reader = QrCreator(csv_reader, qr)
        else:
            reader = csv_reader

        generate_pdf(
            data_iterator=iter(reader),
            svg_template_path=svg_template_path,
            pdf_output_path=pdf_output_path,
            overwrite=overwrite,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--force', '-f', help='overwrite PDF file', action='store_true')
    parser.add_argument('--qr')
    parser.add_argument('input_svg_file')
    parser.add_argument('input_csv_file')
    parser.add_argument('output_pdf_file')
    args = parser.parse_args()
    if not args.force and os.path.exists(args.output_pdf_file):
        if os.isatty(sys.stdin.fileno()):
            answer = input(
                "File %s already exists. Overwrite? [y/N] " %
                args.output_pdf_file,
            )
            if answer.lower() in ['y', 'yes']:
                args.force = True
            else:
                print("Aborted")
                sys.exit(1)
        else:
            print(
                "Error: file %s already exists. Use --force to overwrite.\n"
                "Aborted" % args.output_pdf_file,
                file=sys.stderr,
            )
            sys.exit(1)
    process_csv(
        csv_data_path=args.input_csv_file,
        svg_template_path=args.input_svg_file,
        pdf_output_path=args.output_pdf_file,
        overwrite=args.force,
        qr=args.qr,
    )


if __name__ == '__main__':
    main()
