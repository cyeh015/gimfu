import os
import shutil
import subprocess
from gimfu import gpl
from copy import deepcopy

import pint
Unit = pint.UnitRegistry()
Unit.Q = Unit.Quantity

tpl_1 = '\n'.join([
    '\n',
    '\\begin{sidewaysfigure}',
    '  \\centering',
    '      \\includegraphics[bb=50 50 554 770, height=\\textheight, angle=-90]{%s}',
    '  \\caption{%s}',
    '\\end{sidewaysfigure}',
    '\\clearpage',
    '%% to avoid "too many floats" error',
    '\n',
    ])

tpl_2 = '\n'.join([
    '\\begin{figure}',
    '    \\centering',
    '    \\includegraphics[bb=50 50 554 770, width=0.7\\textwidth, angle=-90]{%s}',
    '    \\includegraphics[bb=50 50 554 770, width=0.7\\textwidth, angle=-90]{%s}',
    '    \\caption{%s}',
    '\\end{figure}',
    ])

# 1,3,2,4, tl,bl,tr,br
tpl_4 = '\n'.join([
    '\\begin{sidewaysfigure}',
    '    \\begin{minipage}[c]{0.5\\textheight}',
    '        \\includegraphics[bb=50 50 554 770, height=0.42\\textheight, angle=-90]{%s}',
    '        \\includegraphics[bb=50 50 554 770, height=0.42\\textheight, angle=-90]{%s}',
    '    \\end{minipage}',
    '    \\begin{minipage}[c]{0.5\\textheight}',
    '        \\includegraphics[bb=50 50 554 770, height=0.42\\textheight, angle=-90]{%s}',
    '        \\includegraphics[bb=50 50 554 770, height=0.42\\textheight, angle=-90]{%s}',
    '    \\end{minipage}',
    '    \\caption{%s}',
    '\\end{sidewaysfigure}',
    '\\clearpage',
    '%% to avoid "too many floats" error',
    '\n',
    ])


def escape_latex_special_chars(input_string):
    """ escape latex special chars """
    import re
    # Define a dictionary of LaTeX special characters and their escaped forms
    latex_special_chars = {
        '\\': r'\textbackslash{}',  # Backslash
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}'
    }

    # Use regex to replace each special character with its escaped version
    escaped_string = re.sub(
        '|'.join(re.escape(key) for key in latex_special_chars.keys()),
        lambda match: latex_special_chars[match.group()],
        input_string
    )

    return escaped_string


def same_path(a, b):
    """ get path of file b assumed to be at the same path as file a,
    supports wildcast '*' in filename b
    """
    import os.path
    import glob
    p,f = os.path.split(a)
    # search by name, hopefully only ONE found
    fns = glob.glob(os.path.join(p, b))
    if len(fns) != 1:
        raise Exception("Cannot locate (or too many) heatflow .csv with '%s'" % heatflow_fname)
    return fns[0]

def get_csv_data(fname, columns=[0,1], factor=None):
    """ get data from csv file, can specify columns, also suuports
    factor for things like simple unit conversion.  factor should have
    the same length as the columns.
    """
    if factor is None:
        factor = [1.0] * len(columns)
    with open(fname, 'r') as f:
        data = []
        for line in f:
            if line:
                try:
                    sps = line.split(',')
                    d = [float(sps[i]) * m for i,m in zip(columns, factor)]
                    data.append(d)
                except ValueError:
                    # skip lines that can't be converted
                    continue
    return data

BPLOT_LS_ORDER = ['1','3','4','8','12','13','14','16','27','36','22','23','24','25','26','27','28','29',]

def mod_gpl(g, settings, skip_irrecoverable=False):
    """ this function parses the 'settings' dict used in entry, and apply
    actions to the gnuplot gpl object.

    Some action like 'reverse' (usually for injection) should only be done once.
    This can be done by setting the skip_irrecoverable = True. It's better to
    skip those actions when repeated modifying .gpl files.
    """
    from copy import deepcopy
    if 'replace_series' in settings:
        ls = BPLOT_LS_ORDER
        def replace_s(s, t, i):
            if 'data' in t:
                s.data = t['data']
                del t['data']
            if 'title' in t:
                s.title = t['title']
                del t['title']
            if 'with' in t:
                s.withstyle = t['with']
                del t['with']
            if 'ls' in t:
                s.set_ls(t['ls'])
                del t['ls']
            for k in t.keys():
                raise Exception("'Error in replace_series[%i]: key %s not recognised" % (i,k))
        for i,(s,t) in enumerate(zip(g.series, settings['replace_series'][:len(g.series)])):
            replace_s(s, t, i)
        for j,t in enumerate(settings['replace_series'][len(g.series):]):
            g.series.append(deepcopy(g.series[-1]))
            s = g.series[-1]
            s.set_with('linespoints')
            s.set_ls(ls[j+i])
            replace_s(s, t, j)

    if 'xlabel' in settings:
        if settings['xlabel'] is None:
            g.xlabel = ''
        else:
            g.xlabel = settings['xlabel']

    if 'ylabel' in settings:
        if settings['ylabel'] is None:
            g.ylabel = ''
        else:
            g.ylabel = settings['ylabel']

    if 'xrange' in settings:
        g.set('xrange', settings['xrange'])
        if settings['xrange'] is None:
            g.unset('xrange')

    if 'yrange' in settings:
        g.set('yrange', settings['yrange'])
        if settings['yrange'] is None:
            g.unset('yrange')

    if 'title' in settings:
        # replace if sepcified, other left alone
        g.set('title', settings['title'])

    if 'reverse' in settings and settings['reverse'] is True:
        if not skip_irrecoverable:
            def reverse_y(series):
                new_data = []
                for d in series.data:
                    new_data.append([d[0], -d[1]])
                series.data = new_data
                return series
            for s in g.series:
                s = reverse_y(s)

    if 'series_titles' in settings:
        for s,t in zip(g.series, settings['series_titles']):
            s.title = t

    if 'series_with' in settings:
        for s,t in zip(g.series, settings['series_with']):
            s.set_with(t)

    if 'series_ls' in settings:
        # NOTE bplot.exe generate ls sequence as:
        #      1 3 4 8 12 13 14 16 27 36 22 23 24 25 26 27 28 29
        for s,t in zip(g.series, settings['series_ls']):
            s.set_style(t)

    if 'apply_series_function' in settings:
        if not skip_irrecoverable:
            def apply_math(series, fn):
                new_data = []
                for d in series.data:
                    new_data.append(list(fn(d)))
                series.data = new_data
                return series
            for s in g.series:
                s = apply_math(s, settings['apply_series_function'])

    if 'apply_gpl_function' in settings:
        if not skip_irrecoverable:
            settings['apply_gpl_function'](g)

    if 'xrangemin' in settings:
        g.auto_xrange_min(settings['xrangemin'])

    if 'yrangemin' in settings:
        g.auto_yrange_min(settings['yrangemin'])

    if 'terminal' in settings:
        g.set('terminal', settings['terminal'])

    if 'add_cmd' in settings:
        for cmd in settings['add_cmd']:
            g._cmdlines.append(cmd + '\n')

    if 'xtics' in settings:
        g.xtics = settings['xtics']

    if 'ytics' in settings:
        g.ytics = settings['ytics']

    if 'mxtics' in settings:
        g.set('mxtics', settings['mxtics'])

    if 'mytics' in settings:
        g.set('mytics', settings['mytics'])

    if 'grid' in settings:
        g.set('grid', settings['grid'])

    return g

class FigureReport(object):
    def __init__(self, geometry, listings,
                 fig_path='./_plots/',
                 data_path='./field_data/',
                 title='',
                 starting_time=0.0,
                 report_name='report',
                 additional_t2listings=[],
                 ):
        self.geometry = geometry
        self.listings = listings
        self.title = title
        self.starting_time = starting_time

        self.bplot_lists = {}
        self.latex_lines = []
        self.gpl_mods = [] # !!! this is the real list of all figures, stored in each .gpl files

        # skip bplot, directly extract results and insert during self.mod_gpls
        self.additional_t2listings=additional_t2listings

        #  TODO-redo these:
        self._captions = {} # caption to be shown exported excel

        self.fig_path = fig_path # where bplot outputs .gpl .eps etc.
        self.data_path = data_path # fielddata dir for bplot
        self.report_name = report_name

        if not os.path.exists(self.fig_path):
            os.mkdir(self.fig_path)
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

    def _new_entry(self, p):
        """ return the gpl file name """
        def entry_string(p):
            lines = ['#####%2i' % len(p['geners'])]
            lines += p['geners']
            if 'datafiles' in p:
                lines += p['datafiles']
            lines += ['\n'] * 3
            s = '\n'.join(lines)
            return s
        if p['type'] not in self.bplot_lists:
            self.bplot_lists[p['type']] = []
        self.bplot_lists[p['type']].append(entry_string(p))
        fname = p['type']+ ('%i' % len(self.bplot_lists[p['type']]))
        self.gpl_mods.append((fname+'.gpl',p))
        return fname

    def add_titlepage(self, title, report_number, date, template):
        self.latex_lines.append(template % (title, report_number, date))
        self.latex_lines.append('\n\n')

    def add_chapter(self, name, set_counter=None):
        if isinstance(set_counter, int):
            self.latex_lines.append('\\setcounter{chapter}{%i}' % (set_counter-1))
        self.latex_lines.append('\\chapter{%s}' % name)
        self.latex_lines.append('\n')

    def add_lines(self, lines):
        self.latex_lines += lines

    def add_tex_file(self, filename):
        with open(filename, 'r') as f:
            self.latex_lines += f.readlines()

    def add_table(self, contents, header=None):
        from tabulate import tabulate
        self.latex_lines += [
            r'',
            r'\begin{center}',
            str(tabulate(contents, header, tablefmt='latex')),
            r'\end{center}',
            r'',
            ]

    def add_page_1(self, p1):
        # need empty plot ".eps" to avoid latex waiting
        fname = '.eps'
        if p1 is not None:
            fname = self._new_entry(p1) + '.eps'
            self.latex_lines.append(tpl_1 % (fname, p1['caption']))
            self._captions[fname.replace('.eps', '.gpl')] = p1['caption']

    def add_page_2(self, p1, p2, caption):
        # need empty plot ".eps" to avoid latex waiting
        fn1, fn2 = '.eps', '.eps'
        if p1 is not None:
            fn1 = self._new_entry(p1) + '.eps'
        if p2 is not None:
            fn2 = self._new_entry(p2) + '.eps'
        self.latex_lines.append(tpl_2 % (fn1, fn2, caption))
        self._captions[fn1.replace('.eps', '.gpl')] = caption + ' (a)'
        self._captions[fn2.replace('.eps', '.gpl')] = caption + ' (b)'

    def add_page_4(self, p1, p2, p3, p4, caption):
        # need empty plot ".eps" to avoid latex waiting
        fn = ['.eps'] * 4
        for i,p in enumerate([p1, p2, p3, p4]):
            if p is not None:
                fn[i] = self._new_entry(p) + '.eps'
        self.latex_lines.append(tpl_4 % (fn[0], fn[2], fn[1], fn[3], caption))
        self._captions[fn[0].replace('.eps', '.gpl')] = caption + ' (a)'
        self._captions[fn[1].replace('.eps', '.gpl')] = caption + ' (b)'
        self._captions[fn[2].replace('.eps', '.gpl')] = caption + ' (c)'
        self._captions[fn[3].replace('.eps', '.gpl')] = caption + ' (d)'

    def _write_bplot_cfg(self):
        """ generate file option.cfg to be used by bplot.exe """
        lines = [
            '[GeometryFile] ! Geometry (MULGRAPH) file name',
            os.path.normpath(self.geometry),
            '![Tough2File] ! TOUGH2 data file name',
            '! not used here',
            '!-----',
            '[ListingFiles,%i] ! listing file names' % len(self.listings),
            '\n'.join([os.path.normpath(p) for p in self.listings]),
            '!-----',
            '[WellListFiles,%i] ! list of columns and real well data file names' % len(self.well_lists),
            '\n'.join([os.path.normpath(p) for p in self.well_lists]),
            '!-----',
            '[ReadDataDirectory] ! real data directory',
            os.path.normpath(self.data_path)+os.sep,
            '[PlotOutputDirectory] ! plots output directory',
            os.path.normpath(self.fig_path)+os.sep,
            '[FontSize] ! font size: 18 for Evi',
            '18',
            '[PlotMainTitle] ! title',
            self.title,
            '[NumOfSeriesPerPlot] ! maximum of series per plot - 1 ',
            '50',
            '[HistoryStartingTime] ! starting time for history matching',
            '%f' % self.starting_time,
            '\n\n\n',
            '! file generated by make_report.py',
            '\n\n\n',
        ]
        with open('option.cfg', 'w') as f:
            f.write('\n'.join(lines))

    def make_bplot(self, clean_files=True):
        # this has to wait until here, cannot do it in __init__
        flist = {
            'HistMtd': 'tpl_mass_rate.list',
            'HistEth': 'tpl_enthalpy.list',
            'HistStd': 'tpl_steam_rate.list',
            'HistPab': 'tpl_pressu.list',
            'HistPdr': 'tpl_pressu_drawdown.list',
            'HistTmp': 'tpl_temp.list',
        }
        self.well_lists = []
        for t,lines in self.bplot_lists.items():
            with open(flist[t], 'r') as ftpl:
                flistname = flist[t].replace('tpl_', '_')
                self.well_lists.append(flistname)
                with open(flistname, 'w') as flst:
                    flst.write(''.join(ftpl.readlines()))
                    flst.write('\n'.join(lines))
                    flst.write('[END]\n\n')
        self._write_bplot_cfg()
        if clean_files:
            all_files = os.listdir(self.fig_path)
            del_files = [os.path.join(self.fig_path, f) for f in all_files if f.lower()[-4:] in ['.eps', '.gpl', '.png']]
            for f in del_files:
                os.remove(f)
        with open('bplot.in', 'w') as f:
            f.write('option.cfg\n')
        subprocess.call('bplot < bplot.in', shell=True)

    def mod_gpls(self, settings_for_all={}, additional_gpl_cmds=[],
                 filetype='eps', skip_irrecoverable=False):
        """ additional settings that applies on ALL Report can be supplied here """


        orig = os.getcwd()
        os.chdir(self.fig_path)
        for fn,m in self.gpl_mods:
            # print fn, ':', m
            g = gpl.gplfile(fn)

            # additional t2listings, extract directly, add to series
            if m['type'] == 'HistPab':
                block = m['geners'][0]
                for lst in self.additional_t2listings:
                    try:
                        x, y = lst.history(('e', block, 'fluid_pressure'))

                        xx = (Unit.Q(x, "sec") + Unit.Q(self.starting_time, "year")).to('year')
                        yy = Unit.Q(y, "Pa").to("bar")

                        new_series = deepcopy(g.series[-1])
                        new_series .data = []
                        for xxx,yyy in zip(xx.magnitude, yy.magnitude):
                            new_series.data.append([xxx, yyy])
                        new_series.title = lst.filename
                        new_series.withstyle = 'linespoints ls 3'
                        g.series.append(new_series)

                        # breakpoint()

                    except KeyError:
                        print(f"@@@@@@@@@@@ Failed to get {lst._h5} {('e', block, 'pressure')}")
                        continue

            if m['type'] == 'HistTmp':
                block = m['geners'][0]
                for lst in self.additional_t2listings:
                    try:
                        x, y = lst.history(('e', block, 'fluid_temperature'))
                        xx = (Unit.Q(x, "sec") + Unit.Q(self.starting_time, "year")).to('year')
                        yy = Unit.Q(y, "degC").to("degC")

                        new_series = deepcopy(g.series[-1])
                        new_series .data = []
                        for xxx,yyy in zip(xx.magnitude, yy.magnitude):
                            new_series.data.append([xxx, yyy])
                        new_series.title = lst.filename
                        new_series.withstyle = 'linespoints ls 3'
                        g.series.append(new_series)

                        # breakpoint()

                    except KeyError:
                        print(f"@@@@@@@@@@@ Failed to get {lst._h5} {('e', block, 'pressure')}")
                        continue


            g.set_filetype(filetype)
            g.set_custom_linestyles(linewidth=2, pointsize=1.2)
            # additional_gpl_cmds
            g._cmdlines.append(" \n")
            for cmd in additional_gpl_cmds:
                if not cmd.endswith('\n'):
                    cmd += '\n'
                g._cmdlines.append(cmd)
            g._cmdlines.append(" \n")
            # settings for all
            # m.update(settings_for_all) # maybe this will render other ones useless?
            g = mod_gpl(g, settings_for_all, skip_irrecoverable=skip_irrecoverable)
            # settings this plot, comes last, to overwrite
            g = mod_gpl(g, m, skip_irrecoverable=skip_irrecoverable)
            g.remove_abs_path()
            g.write()
            subprocess.call(['gnuplot', fn])
        os.chdir(orig)

    def export_xls(self, output_dir='_export'):
        """ export all bplot data to an Excel spreadsheets

        NOTE xlwt does not supports newer format .xlsx which allows more than 256 columns
             xlsxwriter is very similar to xlwt
             TODO upgrade to something more modern, which may have rather different interface

            import xlwt
            wb = xlwt.Workbook()
            ws = wb.add_sheet('%i' % i)
            wb.save(os.path.join(output_dir, '%s.xls' % self.report_name))
        """
        import xlsxwriter
        wb = xlsxwriter.Workbook(os.path.join(output_dir, '%s.xlsx' % self.report_name))
        orig = os.getcwd()
        os.chdir(self.fig_path)
        try:
            for i,(fn,m) in enumerate(self.gpl_mods):
                g = gpl.gplfile(fn)
                ws = wb.add_worksheet('%i' % i)
                ws.write(0, 0, self._captions[fn] + ':' + g.title)
                for ii,s in enumerate(g.series):
                    ofsx = 1 + ii * 2 # X
                    ofsy = ofsx + 1   # Y
                    ws.write(ofsx, 0, s.title); ws.write(ofsy, 0, s.title)
                    ws.write(ofsx, 1, g.xlabel); ws.write(ofsy, 1, g.ylabel)
                    for jj,v in enumerate(s.data):
                        ws.write(ofsx, 2+jj, v[0])
                        ws.write(ofsy, 2+jj, v[1])
        except Exception as e:
            print('Error while exporting...')
            print('    ', fn)
            print('    ', self._captions[fn] + ':' + g.title)
            print('    ', s.title)
            raise e
        os.chdir(orig)
        if not os.path.isdir(output_dir):
            if os.path.exists(output_dir):
                raise Exception("FigureReport.export_xls() output_dir '%s' is possibly a file." % output_dir)
            else:
                os.mkdir(output_dir)
        wb.close()

    def make_report(self, output_dir='_report', clean_files=False):
        # compose latex file and compile, within self.fig_path
        with open('report_template.tex', 'r') as ftpl:
            with open(self.fig_path + self.report_name + '.tex', 'w') as ftex:
                ftex.write(''.join(ftpl.readlines()))
                ftex.write('\n'.join(self.latex_lines))
                ftex.write('\n\n\\end{document}\n\n\n')

        orig = os.getcwd()
        os.chdir(self.fig_path)
        subprocess.call(['latex', f"{self.report_name}.tex"])
        subprocess.call(['dvips', '-P', 'pdf', f"{self.report_name}.dvi"])
        subprocess.call([
            'gs', '-sPAPERSIZE=a4', '-dSAFER', '-dBATCH', '-dNOPAUSE',
            '-sDEVICE=pdfwrite',
            f'-sOutputFile={self.report_name}.pdf',
            '-c', 'save', 'pop',
            '-f', f'{self.report_name}.ps',
            ])

        # subprocess.call('"C:\\Program Files\\MiKTeX 2.9\\miktex\\bin\\x64\\dvips.exe" -P pdf "%s.dvi"' % self.report_name)
        # subprocess.call('"C:\\Program Files\\gs\\gs9.21\\bin\\gswin64c.exe" -sPAPERSIZE=a4 -dSAFER -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -sOutputFile="%s.pdf" -c save pop -f "%s.ps"' % (self.report_name, self.report_name), shell=True)
        if clean_files:
            for ext in ['.aux', '.dvi', '.log', '.maf', '.mtc', '.mtc0', '.out', '.ps', '.tex']:
                os.remove(self.report_name + ext)
        os.chdir(orig)
        if not os.path.isdir(output_dir):
            if os.path.exists(output_dir):
                msg1 = 'Failed to copy report %s into specified output_dir.' % os.path.join(self.fig_path, self.report_name+'.pdf')
                msg2 = "FigureReport.make_report() output_dir '%s' is possibly a file." % output_dir
                raise Exception(msg1 + '\n' + msg2)
            else:
                os.mkdir(output_dir)
        shutil.copy2(os.path.join(self.fig_path, self.report_name+'.pdf'), output_dir)

