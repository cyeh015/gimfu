""" Module for generating report tables of scenario specification.

This module replies on .json files generated along side scenario simulations.
Tables in LaTeX format is genreated for use in the figure report.
"""
import json
from copy import deepcopy

from gimfu.figure_report import escape_latex_special_chars

class CleanTable(object):
    """ Generating clean table where repeated cell is empty if content is the
        same as previous row.

    Attributes:
        headers (list): List of headers strings.
        table (list): List of table rows.
    """
    def __init__(self, headers=None, omit_repeats=[], widths=None):
        """
        Args:
            headers (list): List of headers strings.

            omit_repeats (list): List of columns (headers) that should omit
            content if cell is the same as previous row.
        """
        if widths:
            if len(widths) != len(headers):
                raise ValueError("Widths must have the same length as headers.")
        self.headers = headers
        self.widths = widths
        self.omit_repeats = [self.headers.index(h) for h in omit_repeats]
        self.table = []
        # the following are automatically generated/formatted/refreshed
        self.detected_widths = [len(h) for h in self.headers]
        self._clean_headers = self.headers
        self._clean_table = None

    def add_row(self, row):
        """ Add a row to the table.

        Args:
            row (list): List of row strings.
        """
        self.table.append(row)
        self._clean_table = None # reset clean table

    @property
    def clean_table(self):
        # update clean table
        if self._clean_table is None:
            self.detected_widths = [len(h) for h in self.headers]
            self._clean_table = []
            prev_row = None
            for row in self.table:
                row_copy = deepcopy(row)
                if prev_row:
                    for i, cell in enumerate(row_copy):
                        self.detected_widths[i] = max(self.detected_widths[i], len(cell))
                        if cell == prev_row[i] and (i in self.omit_repeats):
                            # row_copy[i] = ' ' * len(prev_row[i])
                            row_copy[i] = ''
                self._clean_table.append(row_copy)
                prev_row = row
        # fix and align column widths
        if self.widths:
            final_widths = self.widths
        else:
            final_widths = self.detected_widths
        self._clean_headers = [h.ljust(w) for h, w in zip(self.headers, final_widths)]
        # self._clean_headers = [h.strip().ljust(w) for h, w in zip(self.headers, final_widths)]
        for row in self._clean_table:
            for i, cell in enumerate(row):
                row[i] = cell.ljust(final_widths[i])
                # row[i] = cell.strip().ljust(final_widths[i])
        return self._clean_table

    @property
    def clean_headers(self):
        # ensure clean header is updated
        clean_table = self.clean_table
        return self._clean_headers

    def dumps_latex(self, print_header=True, hline=True, caption=''):
        """ return lines in LaTeX format. """
        from tabulate import tabulate
        table = tabulate(self.clean_table, headers=self.clean_headers,
                         tablefmt='latex_longtable',
                         disable_numparse=True)
        if caption:
            caption_code = "\\caption{%s}\n" % escape_latex_special_chars(caption)
            # caption_code += "\n".join([
            #     '\\ttfamily',
            #     '\\tiny',
            # ])
            # only replace the first occurrence
            table = table.replace("\\end{longtable}", caption_code + "\n\\end{longtable}", 1)

        lines = [
            '',
            # '\\begin{table}',
            '\\ttfamily',
            '\\tiny',
            # '\\centering',
            table,
            # '\\caption{%s}' % escape_latex_special_chars(caption),
            # '\\end{table}',
            '',
            ]
        return '\n'.join(lines)

    def dumps_txt(self, print_header=True, hline=True, vsep=' | '):
        """ return lines pure text or on screen. """
        table = self.clean_table
        headers = self.clean_headers
        hline_width = sum([len(h) for h in headers]) + (len(self.headers)-1) * len(vsep)
        lines = []
        if headers and print_header:
            lines.append(vsep.join(headers))
        if hline:
            lines.append('-' * hline_width)
        for row in table:
            lines.append(vsep.join(row))
        if hline:
            lines.append('-' * hline_width)
        return '\n'.join(lines)


def collate_well_stacks(spec_json):
    """ Collate well stacks from all simulations in a scenario.

    Returns:
        well_stack_specs: dict of well stack specifications. Primarily used for
            generating a table with stack_spec_table().

        well_geners: dict of well generators. eg. {
            'WK1': [('abc 1', 'WW  1'), ('abc 2', 'WW  1')],
            'WK2': [('xyz 5', 'TT  2'), ('xyz 5', 'WW  2')],
        }

    Args:
        spec_json: json-like object of scenario specification.
    """
    well_stacks = []
    well_stack_specs = {}
    well_geners = {}
    simulations = spec_json["simulations"]
    for sim in simulations:
        for spec in sim['specs']:
            if spec:
                for stack in spec['well_stacks']:
                    if stack:
                        well_stacks.append(stack)

                        # well_geners
                        stack_spec = spec['specifications'][stack]
                        for well in stack_spec['wells']:
                            if well not in well_geners:
                                well_geners[well] = []
                            for gener in stack_spec['geners'][well]:
                                if gener not in well_geners[well]:
                                    well_geners[well].append(gener)
                            # well_geners[well] += stack_spec['geners'][well]

                        # well_stack_specs
                        well_stack_specs.update(spec['specifications'])

    return well_stack_specs, well_geners


def stack_schedule_table(spec_json):
    """ Generate a table for well stacks used in a scenario.

    Args:
        spec_json: json-like object of scenario specification.
    """
    scenario = spec_json
    simulations = spec_json["simulations"]
    table = CleanTable(headers=['Scenario', 'Dates', 'Well Stack'],
                       omit_repeats=['Scenario', 'Dates'],
                       # widths=[10, 20, 50],
                       )
    str_sname = "%5s" % scenario['name']
    for sim in simulations:
        str_dates = "%6.1f - %6.1f" % (sim['tstart_yr'], sim['tstop_yr'])
        well_stacks = []
        for spec in sim['specs']:
            if spec:
                for stack in spec['well_stacks']:
                    if stack:
                        well_stacks.append(stack)
        for stack in well_stacks:
            table.add_row([str_sname, str_dates, stack])
    return table


def stack_spec_table(stack_spec_json, abbrev={}):
    """ Generate a table for a well stack specification.

    Args:
        stack_spec_json: json-like object of well stack specification.
        abbrev: dict of abbreviations to replace long names.
    """
    table = CleanTable(headers=[
                           'Well',
                           'Geners',
                           'Blocks',
                           'Clean t/hr',
                           'Cap t/hr',
                           'Ecut kJ/kg',
                           'Psep bar',
                           'Cap by',
                           'Deliv.~Curve',
                           ],
                       # omit_repeats=[],
                       # widths=[50, 10, 50],
                       )
    def fmt(fmt, a):
        if a is not None:
            if a in abbrev:
                return fmt % abbrev[a]
            return fmt % a
        else:
            return ''
    for well in stack_spec_json['wells']:
        all_bnames = sorted(set([g[0] for g in stack_spec_json['geners'][well]]))
        blocks_str = ','.join(all_bnames)
        all_gnames = sorted(set([g[1] for g in stack_spec_json['geners'][well]]))
        geners_str = ','.join(all_gnames)
        table.add_row([
            fmt('%s'   , well),
            fmt('%s', geners_str),
            fmt('%s', blocks_str),
            fmt('%5.1f', stack_spec_json['clean_rate_t/hr'][well]),
            fmt('%5.1f', stack_spec_json['cap_t/hr'][well]),
            fmt('%6.0f', stack_spec_json['e_cutoff_kJ/kg'][well]),
            fmt('%5.2f', stack_spec_json['p_sep_bara'][well]),
            fmt('%s'   , stack_spec_json['cap_spec_source'][well]),
            fmt('%s'   , stack_spec_json['deliv_curve'][well]),
            ])
    return table

def well_geners_table(well_geners, custom_sort_key=None):
    """ Generate a table for well generators.

    Args:
        well_geners: dict of well generators.
    """
    table = CleanTable(headers=['Well', 'Generator', ], omit_repeats=['Well'], )
    for well in sorted(well_geners.keys(), key=custom_sort_key):
        for gener in well_geners[well]:
            table.add_row([well, '(%5s:%5s)' % tuple(gener), ])
    return table

def well_blocks_geners_table(well_geners, custom_sort_key=None):
    """ Generate a table for well blocks.

    Args:
        well_geners: dict of well generators.
    """
    table = CleanTable(headers=['Well', 'Model Blocks', 'Geners'], )
    for well in sorted(well_geners.keys(), key=custom_sort_key):
        all_bnames = sorted(set([g[0] for g in well_geners[well]]))
        all_gnames = sorted(set([g[1] for g in well_geners[well]]))
        table.add_row([well, ', '.join(all_bnames), ', '.join(all_gnames), ])
    return table

def well_blocks_table(well_geners, custom_sort_key=None):
    """ Generate a table for well blocks.

    Args:
        well_geners: dict of well generators.
    """
    table = CleanTable(headers=['Well', 'Model Blocks'], )
    for well in sorted(well_geners.keys(), key=custom_sort_key):
        all_bnames = sorted(set([g[0] for g in well_geners[well]]))
        table.add_row([well, ', '.join(all_bnames), ])
    return table


if __name__ == "__main__":
    with open('scenario_spec.json', 'r') as f:
        spec_json = json.load(f)

    # abbreviate long names
    abbrev = {
        'steam-cutoff-2.00-bar': 'Steam (2.0 bar WHP)',
        './make_pcutoff_curves_TH12_50WHP/make_Pcutoff_curve.out': 'TH12  (5.0 bar WHP)',
    }

    # Custom sort key function
    def custom_sort_key(s):
        # Return a tuple where the first element determines if 'WK' is present or not
        # and the second element is the string itself for normal sorting.
        return (0 if s.startswith("WK") else 1, s)

    tables = []
    # tables.append(stack_schedule_table(spec_json))

    well_stack_specs, well_geners = collate_well_stacks(spec_json)
    tables.append(stack_spec_table(well_stack_specs['THIPOI_PH2x_137sep'],
                                   abbrev=abbrev))
    # tables.append(well_geners_table(well_geners, custom_sort_key=custom_sort_key))
    tables.append(well_blocks_geners_table(well_geners, custom_sort_key=custom_sort_key))
    # tables.append(well_blocks_table(well_geners, custom_sort_key=custom_sort_key))

    for table in tables:
        print('\n\n')
        print(table.dumps_txt())
        # print(table.dumps_latex())


