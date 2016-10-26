#!/usr/bin/python3

import argparse
import collections
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


MergeRow = collections.namedtuple('MergeRow', 'class_name class_type data')


class MergeCsvReader:
    def __init__(self, fobj):
        self._csv = iter(csv.reader(fobj))
        self._class_names = next(self._csv)
        self._class_types = next(self._csv)

    def __iter__(self):
        return self

    def __next__(self):
        data_row = next(self._csv)
        return [
            MergeRow(class_name=class_name, class_type=class_type, data=data)
            for class_name, class_type, data
            in zip(self._class_names, self._class_types, data_row)
        ]


def _replace_tspan(template, class_name, data):
    for e in template.findall(".//svg:tspan[@class='%s']" % class_name,
                              namespaces=NSMAP):
        # Replace text with data as-is
        e.text = data


def _create_qr_xml(data):
    qr = pyqrcode.create(data, mode='binary', error='L')
    f = io.BytesIO()
    qr.svg(f, omithw=True)
    f.seek(0)
    xml = etree.parse(f)
    return xml.getroot()


def _replace_qr(template, class_name, data):
    qr_xml_template = _create_qr_xml(data)
    for e in template.findall(".//svg:rect[@class='%s']" % class_name,
                              namespaces=NSMAP):
        qr_xml = copy.deepcopy(qr_xml_template)
        # If the rect has a transform, that needs to be applied
        # in a wrapping <g>.
        if e.get('transform'):
            replacement = etree.Element('g')
            replacement.set('transform', e.get('transform'))
            replacement.append(qr_xml)
        else:
            replacement = qr_xml
        # Replace rect with XML (expected to be an <svg> element)
        e.getparent().replace(e, replacement)
        for attr in ['class', 'x', 'y', 'width', 'height']:
                    qr_xml.set(attr, e.get(attr))


def replace(root, replacements):
    '''Apply replacements to an SVG ElementTree

    Look for class="template" attributes. next(replacements) should provide
    MergeRow instances.

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
        for class_name, class_type, data in data_row:
            {
                'tspan': _replace_tspan,
                'qr': _replace_qr,
            }[class_type](template, class_name, data)

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
        overwrite):
    with open(csv_data_path, 'r', newline='') as csv_fobj:
        generate_pdf(
            data_iterator=MergeCsvReader(csv_fobj),
            svg_template_path=svg_template_path,
            pdf_output_path=pdf_output_path,
            overwrite=overwrite,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--force', '-f', help='overwrite PDF file', action='store_true')
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
    )


if __name__ == '__main__':
    main()
