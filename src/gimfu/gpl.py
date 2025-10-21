""" provides interface to easily change the content of a existing GNUPlot
 .gpl file.  Not full gpl feature supported, most of the properties is
 processed like normal string.  See __main__ for example on how to use """

from pathlib import Path

def unquote(text):
    t = text.strip()
    if len(t) < 2: raise Exception("Error at unquoting text: %s" % text)
    if t[0] not in '"'+"'": raise Exception("Error at unquoting text: %s" % text)
    if t[0] != t[-1]: raise Exception("Error at unquoting text: %s" % text)
    return t[1:-1]
def quote(text):
    q = "'"
    if q in text: q = '"'
    return q+text+q

def cleanup_multi_lines(multi_line_string):
    """ clean up the line continuation of \ in gpl files, the input
    should be the original stream of lines, with line break kept, so
    line continuation can be detected """
    lines = multi_line_string.splitlines()
    cleaned = ''
    for line in lines [:-1]:
        cleaned += line[:-1]
    return cleaned + lines[-1]

def string_eat_group(astring):
    """ will extract the string inside the grouping marks, returning
    two strings, first being the content inside the marks, second being
    the left over string.  NOTE the first char of the original string
    must be the opening of grouping character. """
    groupchar = {'"':'"',"'":"'",'{':'}','[':']','<':'>','(':')','`':'`','$':'$'}
    c = astring[0]
    iend = astring[1:].find(groupchar[c])
    if iend == -1: raise Exception('matching grouping char of %s is not found in: %s' % (c,astring))
    return (astring[1:iend+1],astring[iend+2:])

def string_eat_until(astring,until=' '):
    """ extract part of the string up to specified word or any of the
    words if a list is given, and return the leftover string as well. """
    astring = astring.lstrip()
    if type(until) == type([]):
        iend = [astring.find(u) for u in until if astring.find(u) != -1]
        if len(iend) == 0: return(astring,'')
        return (astring[:min(iend)],astring[min(iend):])
    else:
        iend = astring.find(until)
        if iend == -1: return(astring,'')
        return (astring[:iend],astring[iend:])

class series(object):
    def __init__(self,cmdline):
        # these two will always be identical
        self.datafile, self.function = '', ''
        self._actual_cmd = ''
        # only has value if specified or read in-place from .gpl
        self.data = []
        self.axes = None
        self.title = None
        self.withstyle = None
        line = cmdline.strip()
        (command,line) = string_eat_until(line,[' axes',' title',' notitle',' with'])
        self.datafile, self.function = command, command
        # parse the rest
        while line.strip() != '':
            line = line.strip()
            if line.find(' ') == -1:
                # single word left
                kwrd = line
                value = ''
            else:
                (kwrd,line) = string_eat_until(line.strip(),' ')
                (value,line) = string_eat_until(line.strip(),[' axes',' title',' notitle',' with'])
                # print '@@@@@'+ kwrd+'@'+value+'@'
            if kwrd == 'axes':       self.axes = value
            elif kwrd == 'title':    self.title = unquote(value)
            elif kwrd == 'notitle':  self.title = ''
            elif kwrd == 'with':    self.withstyle = value
        # fix bplot.exe bug by overwrite this early on
        self._fix_bplot_no_ls_issue()

    def __setattr__(self,name,value):
        """ update self._actual_cmd according to datafile OR function """
        if name == 'datafile':
            if value is None:
                self._actual_cmd = self.function or ''
            else:
                if value == '': value = "'-'"
                # add qutation for user if forget
                if value[0] not in '"'+"'": value = "'" + value + "'"
                self._actual_cmd = value
        if name == 'function':
            if value is None:
                self._actual_cmd = self.datafile or ''
            else:
                self._actual_cmd = value
        # proceed as normal, for all
        self.__dict__[name] = value

    def get_with(self):
        if self.withstyle is None:
            return None
        else:
            # always the first option, not optional in gnuplot I think
            return self.withstyle.split()[0]
    def set_with(self, style):
        """
        style is a string, must be one of (see gnuplot manual):
            lines dots steps errorbars xerrorbar xyerrorlines
            points impulses fsteps errorlines xerrorlines yerrorbars
            linespoints labels histeps financebars xyerrorbars yerrorlines
            surface vectors parallelaxes
        or
            boxes boxplot ellipses image
            boxerrorbars candlesticks filledcurves rgbimage
            boxxyerrorbars circles histograms rgbalpha pm3d
        or
            table
        """
        if style is None:
            self.withstyle = style
            return
        if self.withstyle is None:
            self.withstyle = style
        sps = self.withstyle.split()
        self.withstyle = ' '.join([style] + sps[1:])

    def get_ls(self):
        """ get 'ls' value from the 'with' command """
        sps = self.withstyle.split()
        i = None
        for k in ['ls', 'linestyle']:
            try:
                i = sps.index(k)
            except ValueError:
                continue
        if i is None:
            return None
        else:
            return sps[i+1]
    def set_ls(self, ls):
        """ set 'ls' value from the 'with' command """
        if self.withstyle is None:
            self.set_style('linespoints')
        sps = self.withstyle.split()
        i = None
        for k in ['ls', 'linestyle']:
            try:
                i = sps.index(k)
            except ValueError:
                continue
        if i is None:
            if ls is None:
                return
            else:
                # no ls specified yet, insert at the start
                self.withstyle = ' '.join(sps[:1] + ['ls', str(ls)] + sps[2:])
        else:
            if ls is None:
                self.withstyle = ' '.join(sps[:i] + sps[i+2:])
            else:
                self.withstyle = ' '.join(sps[:i+1] + [str(ls)] + sps[i+2:])

    def _fix_bplot_no_ls_issue(self):
        """ fix AY bplot.exe's bug of missing linestyle/ls in the with command.
        gnuplot's 'with' command:
            with <style> { {linestyle | ls <line_style>}
                           | {{linetype | lt <line_type>}
                              {linewidth | lw <line_width>}
                              {linecolor | lc <colorspec>}
                              {pointtype | pt <point_type>}
                              {pointsize | ps <point_size>}
                              {fill | fs <fillstyle>}
                              {nohidden3d} {nocontours} {nosurface}
                              {palette}}
                         }

        """
        if self.withstyle is not None:
            sps = self.withstyle.split()
            # the second item in the command SHOULD NOT be a number
            # fix this bplot.exe bug by inserting 'ls'
            if len(sps) > 1 and sps[1].isdigit():
                sps.insert(1, 'ls')
            self.withstyle = ' '.join(sps)

    def write(self):
        command = ''
        command += self._actual_cmd
        if self.axes is not None:
            command += ' axes '+ self.axes
        if self.title is not None:
            command += ' title '+ quote(self.title)
        if self.withstyle is not None:
            # seems gnuplot after 5.0 no longer accepts 'linespoints 1', but need 'linespoints ls 1'
            if self.withstyle.strip().startswith('linespoints'):
                if 'ls' not in self.withstyle:
                    self.withstyle = self.withstyle.replace('linespoints lt', 'linespoints ls')
            command += ' with '+ self.withstyle
        return command
    command_string = property(write)

    def __repr__(self):
        return '<gpl.series object>: %s' % self.command_string

    def read_series_data(self,openedfile):
        if self.datafile[0] in '"'+"'":
            fn,tmp = string_eat_group(self.datafile.strip())
            if fn == '-':
                # read until 'e'
                while True:
                    line = openedfile.readline()
                    if line.strip() == 'e': break
                    self.data.append([float(x) for x in line.split()])

    def write_series_data(self,openedfile):
        if self.datafile[:3] in ["'-'", '"-"']:
            # from os import linesep
            linesep = '\n'
            for xs in self.data:
                openedfile.write(' '.join([('%20.13e' % x) for x in xs]) + linesep)
            # for a,b in self.data:
            #     openedfile.write('%20.13e %20.13e%s' % (a,b,linesep))
            openedfile.write('e'+linesep)

    def reverse_yvalue(self):
        for d in self.data:
            d[1] = -d[1]


class gplfile(object):
    option_is_text = {
    'terminal'   : False ,
    'title'      : True  ,
    'output'     : True  ,
    'key'        : False ,
    'xlabel'     : True  ,
    'ylabel'     : True  ,
    'logscale'   : False ,
    'xrange'     : False ,
    'yrange'     : False ,
    'xtics'      : False ,
    'ytics'      : False ,
    'mxtics'     : False ,
    'mytics'     : False ,
    'grid'       : False
     }
    def __init__(self,filename):
        self.series=[]
        self.read(filename)
        self.filename = filename

    def read(self,filename):
        self._cmdlines = []
        f = open(filename,'r')
        cmdline = ''
        line = ' '
        while line:
            line = f.readline()
            # record empty line, to avoid next detection fail
            if line.strip() == '':
                self._cmdlines.append(line)
                continue
            # combine multi-lines into one cmdline if ends with \
            cmdline = line
            while line.rstrip('\r\n')[-1] == '\\':
                line = f.readline()
                cmdline += line
            # processing a cmdline
            words = cleanup_multi_lines(cmdline).split()
            if words[0] == 'set':
                if words[1] in gplfile.option_is_text.keys():
                    istart = cmdline.find(words[1]) + len(words[1]) + 1
                    self.__dict__[words[1]] = cmdline[istart:].rstrip().strip('"'+"'")
            elif words[0] == 'unset':
                if words[1] in gplfile.option_is_text.keys():
                    if words[1] in self.__dict__: self.__dict__[words[0]] = None
            elif words[0] == 'plot':
                cmdline = cleanup_multi_lines(cmdline.lstrip())
                self.series = [series(a) for a in cmdline[4:].split(',')]
                # special to plot command, needs to consume the expected data
                for s in self.series:
                    s.read_series_data(f)
                # ignore all entries after plot (they won't affect plot anyway
                break
            # always record cmdline
            self._cmdlines.append(cmdline)
        f.close()

    def write(self,filename = None):
        if filename is None:
            filename = self.filename
        linesep = '\n'
        f = open(filename,'w')
        # print those other options, before plot command
        for orig_line in self._cmdlines:
            words = cleanup_multi_lines(orig_line).split()
            to_write = orig_line
            if len(words) > 0:
                if words[0] in ['set','unset']:
                    if words[1] in gplfile.option_is_text.keys():
                        if words[1] in self.__dict__:
                            if self.__dict__[words[1]] is None:
                                to_write = 'unset '+words[1]+linesep
                            else:
                                to_write = 'set '+words[1]+' '+self._auto_quote_value(words[1])+linesep
            f.write(to_write)
        ### print plot command
        if len(self.series) < 1: raise Exception('<gpl.gplfile object> write() failed, there must be at least one series to plot')
        ### plot command
        f.write('plot \\'+linesep)
        for s in self.series[:-1]:
            f.write(s.command_string+',\\'+linesep)
        f.write(self.series[-1].command_string+linesep)
        ### write data section
        for s in self.series:
            s.write_series_data(f)
        ### end comment
        f.write(linesep)
        from datetime import datetime
        f.write('# file writted by gpl.py '+datetime.now().__str__()+linesep)
        f.write(linesep)
        f.close()

    def set(self,option,value):
        if option in gplfile.option_is_text.keys():
            if option not in self.__dict__:
                self._cmdlines.append("set %s %s" % (option,value))
            self.__dict__[option] = value
    def unset(self,option):
        if option in gplfile.option_is_text.keys():
            self.__dict__[option] = None

    def _auto_quote_value(self,option):
        if option not in self.__dict__.keys(): return None
        value = str(self.__dict__[option])
        if value is None: return ''
        if value == '': return ''
        if gplfile.option_is_text[option]:
            if '"' in value: q = "'"
            else: q = '"'
            if option == 'output': q = "'"
            value = q+value+q
        return value

    def __repr__(self):
        allopts = []
        for opt in sorted(gplfile.option_is_text.keys()):
            if opt not in self.__dict__.keys(): continue
            val = self._auto_quote_value(opt)
            allopts.append('set %s %s' % (opt,val))
        return '\n'.join([
            '<gpl.gplfile object> with overwriting options:'
            ] + allopts)

    def remove_abs_path(self):
        self.output = str(Path('.') / Path(self.output).name)
        # i = self.output.rfind('\\')
        # self.output = '.'+self.output[i:]

    def reverse_yvalue(self):
        for s in self.series:
            s.reverse_yvalue()

    def auto_xrange_min(self, r):
        r_half = r / 2.0
        sss = []
        for s in self.series:
            xs,ys = zip(*(s.data))
            sss = sss + list(xs)
        smin, smax = min(sss), max(sss)
        if (smax - smin) < r:
            smean = (smin + smax) / 2.0
            self.set('xrange', '[*<%f:%f<*]' % (smean - r_half, smean + r_half))

    def auto_yrange_min(self, r):
        r_half = r / 2.0
        sss = []
        for s in self.series:
            xs,ys = zip(*(s.data))
            sss = sss + list(ys)
        smin, smax = min(sss), max(sss)
        if (smax - smin) < r:
            smean = (smin + smax) / 2.0
            self.set('yrange', '[*<%f:%f<*]' % (smean - r_half, smean + r_half))

    def set_filetype(self, filetype):
        """ convnience function of changing between .eps and .png
        """
        terms = {
            'png': 'pngcairo enhanced font "Arial,18" size 1000,750',
            'eps': 'postscript landscape enhanced colour "Arial" 18',
        }
        self.terminal = terms[filetype]
        for ext in terms.keys():
            self.output = self.output.replace('.'+ext, '.'+filetype)

    def set_series_with(self, indices, linespoints):
        """ overwrite series to show either as points only, line only or both

        indices: is a list of indices, if an indix is out of current plot's
                 range, it will be ignored
        linespoints: should be 'lines', 'points' or most commonly 'linespoints'
        """
        if linespoints not in['lines', 'points', 'linespoints']:
            raise Exception
        for i,s in enumerate(self.series):
            if i in indices:
                if self.withstyle.strip().startswith('linespoints'):
                    if 'ls' not in self.withstyle:
                        self.withstyle = self.withstyle.replace('linespoints', 'linespoints ls')


    def set_custom_linestyles(self, linewidth=2, pointsize=1.2):
        # be careful to add \n to end each line
        additional_gpl_cmds = [
            " \n",
            "set style line  1 lc rgb '#FF0000' lt 1 lw %f pt  1 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line  3 lc rgb '#0000FF' lt 1 lw %f pt  6 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line  4 lc rgb '#008000' lt 1 lw %f pt  8 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line  8 lc rgb '#FF8C00' lt 1 lw %f pt 10 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 12 lc rgb '#00BFFF' lt 1 lw %f pt  2 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 13 lc rgb '#696969' lt 1 lw %f pt 12 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 14 lc rgb '#FF00FF' lt 1 lw %f pt 14 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 16 lc rgb '#0000FF' lt 1 lw %f pt  1 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 27 lc rgb '#008000' lt 1 lw %f pt  6 ps %f # pi -1 \n" % (linewidth, pointsize),
            "set style line 36 lc rgb '#FF8C00' lt 1 lw %f pt  8 ps %f # pi -1 \n" % (linewidth, pointsize),
            " \n",
        ]
        for cmd in additional_gpl_cmds:
            self._cmdlines.append(cmd)
        # NOTE:
        # a series with bplot.exe generated 'with linespoints 1' will be
        # automatically updated to 'with linespoints ls 1', so GNUPlot 5.0+ can
        # deal with it correctly


if __name__ == "__main__":
    g = gplfile('test.gpl')
    s = g.series[0]


    # g.title = g.title + 'XXX'
    # g.series[1].title = g.series[1].title + 'XXX'

    # print g.output
    # g.set('yrange','[0:100]')
    # g.unset('xrange')
    # g.remove_abs_path()
    # print g.output

    # g.write('test1.gpl')




