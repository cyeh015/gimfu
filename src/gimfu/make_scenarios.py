import logging

from gimfu.config import *

from t2data import *
from t2incons import *

import os
from os import getcwd, sep, mkdir
from sys import argv
import json

SEC_IN_A_YEAR = 60.*60.*24.*365.25

def initLogger():
    """ initialise python built-in logging module for global use """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # to console
    con_formatter = logging.Formatter("-%(levelname)-10s %(message)s")
    con = logging.StreamHandler()
    con.setLevel(logging.INFO)
    con.setFormatter(con_formatter)
    logger.addHandler(con)
    # to log file
    logf_formatter = logging.Formatter("-%(levelname)-10s %(message)s\n"\
        "            %(filename)s:%(lineno)d")
    logf = logging.FileHandler('make_scenarios_2.log')
    logf.setLevel(logging.INFO)
    logf.setFormatter(logf_formatter)
    logger.addHandler(logf)
    logging.debug("logging initialised")
initLogger()

def make_save2incon(dirname=''):
    code = '\n'.join([
        "''' use: save2incon a.save b.incon [-reset_kcyc] '''",
        "from sys import argv",
        "from t2incons import t2incon",
        "if len(argv) < 2:",
        "    print('use: save2incon a.save b.incon [-reset_kcyc]')",
        "    exit(1)",
        "readFrom = argv[1]",
        "saveTo = argv[2]",
        "if len(argv) > 3:",
        "    opt = argv[3]",
        "else:",
        "    opt = ''",
        "inc = t2incon(readFrom)",
        "if opt == '-reset_kcyc':",
        "    inc.timing['kcyc'] = 1",
        "    inc.timing['iter'] = 1",
        "inc.write(saveTo)",
        "",
        ])
    with open(dirname+'save2incon.py','w') as f:
        f.write(code)

def make_sequential_batch_cmd(bases, dirname='', simulator='autough2_6f'):
    logging.info('Using simulator %s' % simulator)
    logging.info('Generating batch file: run_all_models.bat')
    logging.info('Generating batch file: make_long_listing.bat')
    fbat = open(dirname+'run_all_models.bat','w')
    fcombine = open(dirname+'make_long_listing.bat','w')
    fbat.write('date /t > time.log\n')
    fbat.write('time /t >> time.log\n')
    for i, b in enumerate(bases):
        f = open(dirname+b+'.in','w')
        f.write('\n'.join([
            b,
            b,
            b,
            '']))
        f.close()
        if i != 0:
            #fbat.write('cp '+ bases[i-1]+ '.save '+ bases[i]+ '.incon\n')
            fbat.write('python save2incon.py '+bases[i-1]+'.save '+bases[i]+'.incon -reset_kcyc\n')
        fbat.write('date /t >  '+ b +'.time\n')
        fbat.write('time /t >>  '+ b +'.time\n')
        fbat.write(('%s < ' % simulator)+ b + '.in\n')
        fbat.write('time /t >> '+ b +'.time\n')
        fbat.write('time /t >> time.log\n')
        if i == 0:
            fcombine.write('type '+ b + '.listing >  long.listing\n')
        else:
            fcombine.write('type '+ b + '.listing >> long.listing\n')

    # combine at the end of run anyway
    for i, b in enumerate(bases):
        if i == 0:
            fbat.write('type '+ b + '.listing >  long.listing\n')
        else:
            fbat.write('type '+ b + '.listing >> long.listing\n')

    fbat.close()
    fcombine.close()

def make_sequential_batch_cmd_sh(bases, dirname='', simulator='autough2_6f'):
    """
    Generate bash scripts for running all models and combining listings on Linux/macOS.
    """
    logging.info('Using simulator %s' % simulator)
    logging.info('Generating bash file: run_all_models.sh')
    logging.info('Generating bash file: make_long_listing.sh')
    fbat = open(os.path.join(dirname, 'run_all_models.sh'), 'w')
    fcombine = open(os.path.join(dirname, 'make_long_listing.sh'), 'w')
    fbat.write('#!/bin/bash\n')
    fbat.write('date > time.log\n')
    fbat.write('date +"%T" >> time.log\n')
    for i, b in enumerate(bases):
        with open(os.path.join(dirname, b + '.in'), 'w') as f:
            f.write('\n'.join([
                b,
                b,
                b,
                ''
            ]))
        if i != 0:
            fbat.write(f'python save2incon.py {bases[i-1]}.save {b}.incon -reset_kcyc\n')
        fbat.write(f'date > {b}.time\n')
        fbat.write(f'date +"%T" >> {b}.time\n')
        fbat.write(f'{simulator} < {b}.in\n')
        fbat.write(f'date +"%T" >> {b}.time\n')
        fbat.write(f'date +"%T" >> time.log\n')
        if i == 0:
            fcombine.write(f'cat {b}.listing > long.listing\n')
        else:
            fcombine.write(f'cat {b}.listing >> long.listing\n')

    # combine at the end of run anyway
    for i, b in enumerate(bases):
        if i == 0:
            fbat.write(f'cat {b}.listing > long.listing\n')
        else:
            fbat.write(f'cat {b}.listing >> long.listing\n')

    fbat.close()
    fcombine.close()
    # Make scripts executable
    os.chmod(os.path.join(dirname, 'run_all_models.sh'), 0o755)
    os.chmod(os.path.join(dirname, 'make_long_listing.sh'), 0o755)

def is_leap_year(y):
    if   int(y)%400 == 0: return True
    elif int(y)%100 == 0: return False
    elif int(y)%4   == 0: return True
    else:                 return False

def days_in_month(month, leap_year=False):
    if leap_year:
        d_month = [  31 , 29 , 31 , 30 , 31 , 30 , 31 , 31 , 30 , 31 , 30 , 31  ]
    else:
        d_month = [  31 , 28 , 31 , 30 , 31 , 30 , 31 , 31 , 30 , 31 , 30 , 31  ]
    return d_month[month - 1]

def date2str(d,m,y):
    ds, ms, ys = str(d), str(m), str(y)
    while len(ds) < 2: ds = '0'+ds
    while len(ms) < 2: ms = '0'+ms
    while len(ys) < 4: ys = '0'+ys
    return ds+'/'+ms+'/'+ys

def date2num_(enddate):

    d,m,y = enddate.split('/')
    months    = [ '01','02','03','04','05','06','07','08','09','10','11','12' ]
    d_month   = [  31 , 28 , 31 , 30 , 31 , 30 , 31 , 31 , 30 , 31 , 30 , 31  ]
    d_month_l = [  31 , 29 , 31 , 30 , 31 , 30 , 31 , 31 , 30 , 31 , 30 , 31  ]
    acum_ds   = [sum(d_month[:i]) for i in range(12)]
    acum_ds_l = [sum(d_month[:i]) for i in range(12)]
    ad_m   = dict(zip(months, acum_ds)) # accumulated days before this month
    ad_m_l = dict(zip(months, acum_ds_l)) # accumulated days before this month
    ds_m   = dict(zip(months, d_month)) # maximum days in this month
    ds_m_l = dict(zip(months, d_month_l)) # maximum days in this month
    # check and process d and m, this depends on data
    if m not in months:
        print(' Error, unable to convert ', enddate, ' to numeric format. check month.')
        sys.exit()
    if is_leap_year:
        if int(d) not in range(1,ds_m_l[m]+1):
            print(' Error, unable to convert ', enddate, ' to numeric format. check day.')
            sys.exit()
        num = float(y) + ((float(d) + float(ad_m_l[m]))/float(sum(d_month_l)))
    else:
        if int(d) not in range(1,ds_m[m]+1):
            print(' Error, unable to convert ', enddate, ' to numeric format. check day.')
            sys.exit()
        num = float(y) + ((float(d) + float(ad_m[m]))/float(sum(d_month)))
    return num

def date2num(date):
    try:
        date_value = float(date)
    except ValueError:
        date_value = date2num_(date)
    return date_value

def read_gener_file(fname):
    f = t2data_parser(fname,'r')
    line = f.readline()
    if line[:5] != 'GENER':
        # get rid of first line 'GENER' and check
        print('!!!!!!!!!! ERROR !!!!!!!!!!')
        print('Error reading GENER file: ', fname)
    gs = t2data()
    gs.read_generators(f)
    f.close()
    return gs.generatorlist

def lines_to_geners(lines,tmpfname):
    """ passing a list of strings and transform into a list of geners.
        the genres will alo be written into a file """
    # write
    lines_to_write = ['GENER'] + lines + ['']
    #lines.insert(0,'GENER')
    #lines.append('')
    ftmp = open(tmpfname,'w')
    ftmp.writelines('\n'.join(lines_to_write))
    ftmp.close()
    # read back
    return read_gener_file(tmpfname)

def lose_precision(num, frmt):
    """ Returns the float number that loses its precision after the
    formating.  This is done by putting numbers into string, using specified
    frmt and then back to float. """
    s = frmt % num
    return float(s)

def enable_t2data_time_higher_prec():
    """
    Temporarily modify PyTOUGH's t2data writing format specification, to allow
    tstart and tstop to be written with slightly higher precision: from '10.3e'
    to '10.4e'.  This can be dangerous, as negative time will be broken by
    '10.4e'.  Generally it is better to use save/incon file mechanism to control
    the much higher precision restart time, instead of playing with the spec.
    This however will not work if you want ot control higer precision of
    stopping time.
    """
    t2data_format_specification['param2'][1][0] = '10.4e' # tstart
    t2data_format_specification['param2'][1][1] = '10.4e' # tstop

# a list of file names that contains the building blocks (geners)
#
# For lines started with an '*', a config section will be read instead.
# eg.
#*TMAK_test
# will use section [*TMAK_test] as the source of GENERators
#
# Lines starting with '>', will read a number between '>' and '*'
# and repeat the *section the sepcified number of times
# eg.
#> 5 *ToRepeat
# will use *ToRepeat 5 times
#
# for lines startes with ':', are treated as direct lines from TOUGH2
# input file.
# eg.
#:hbn47hbn47                 -12     DMAK -1.000e-11 0.000e+00 2.000e+01 2.500e+05
#: 0.0000000e+00 8.4000000e+05 8.5000000e+05 9.0000000e+05
#: 1.0000000e+06 1.1000000e+06 1.2000000e+06 1.3000000e+06
#: 1.5000000e+06 1.9000000e+06 2.7000000e+06 2.8000000e+06
#: 3.0000000e+07 3.0000000e+07 1.8132376e+07 1.7823866e+07
#: 1.5017281e+07 9.7064135e+06 5.0435647e+06 4.1507355e+06
#: 3.8343393e+06 3.3400564e+06 3.3400564e+06 3.3400564e+06
# will cause the lines to be read as raw tough2 file (minus the first ':'
#
# For lines start with an '|', CFG file of making IMAK geners will be read after the
# second '|', and scaled (evenly) to the specified total injection.
# eg.
#|500.00|make_injection.cfg
# will run the make_IMAK_wells.py script and use make_injection.cfg to generate a
# list of GENERs to insert.
#
def collect_geners_from_cfg(cfg, cfg_entry_name):
    """ returns a list of generators and its spec, as a tuple of ([], {}).

    The spec is a optional record/info of the contents of the geners produced
    from this suroutine.
    """
    all_geners = []
    spec = {
        'external_geners_files': [], # external gener file names
        'well_stacks': [],
        'specifications': {},
    }
    if isinstance(cfg_entry_name, list):
        # a list (hopefully strings) is lines to be processed
        parts = cfg_entry_name
    else:
        # a single string is a config entry name
        parts = cfg.get_list(cfg_entry_name)
    i = 0
    t2verbatim = False
    while i < len(parts):
        line = parts[i]
        if line.strip()[0] == ':':
            if not t2verbatim:
                t2verbatim = True
                t2vname = 't2verbatim_'+str(i+1)+'.tmp'
                v_lines = []
            v_lines.append(line[line.find(':')+1:])
        elif t2verbatim:
            # write and read t2 verbatim
            print('  inserting verbatim: (', t2vname, ')')
            gs = lines_to_geners(v_lines,t2vname)
            all_geners = all_geners + gs
            # finishes verbatim
            t2verbatim = False
        if not t2verbatim:
            if line.strip()[0] == '*':
                # write and read a section as t2 gener
                s_lines = cfg.get_list(line.strip())
                print('  inserting section: ', line.strip())
                gs = lines_to_geners(s_lines,line[1:].strip()+'.tmp')
                all_geners = all_geners + gs
            elif line.strip()[0] == '>':
                # line must starts as >N* where N is number of repeating sections
                if line.find('*') == -1:
                    print('!!!!!!!!!! ERROR !!!!!!!!!!')
                    print('Error reading CFG line: ', line)
                    from sys import exit
                    exit()
                s_lines = cfg.get_list(line[line.find('*'):].strip())
                repeat = int(line[1:line.find('*')])
                print('  inserting section: ', line[line.find('*'):].strip(), ' by ', repeat, ' times ')
                gs = lines_to_geners(s_lines,line[line.find('*')+1:].strip()+'.tmp')
                for r in range(repeat):
                    all_geners = all_geners + gs
            elif line.strip()[0] == '|':
                inj_entry = line.strip()[1:].split('|')
                if len(inj_entry) != 2:
                    print('!!!!!!!!!! ERROR !!!!!!!!!!')
                    print('Error reading CFG line: ', line)
                    from sys import exit
                    exit()
                total_inj = float(inj_entry[0])
                inj_cfg = config(inj_entry[1])
                print('  inserting section: ', total_inj, ' kg/s of ', inj_entry[1].strip())
                from make_IMAK_wells import make_IMAK_wells_proc_cfg, make_IMAK_wells
                injpar = make_IMAK_wells_proc_cfg(inj_cfg)
                gs = make_IMAK_wells(injpar[0],injpar[1],injpar[2],injpar[3],injpar[4],injpar[5],injpar[6],total_inj)
                all_geners = all_geners + gs
            else:
                # read geners froma a specified file
                fname_geners = line.strip()
                print('  inserting GENER file: ' + fname_geners)
                gs = read_gener_file(fname_geners)
                all_geners = all_geners + gs
                spec['external_geners_files'].append(fname_geners)
                # optional spec
                fname_spec = fname_geners + '.spec.json'
                if os.path.isfile(fname_spec):
                    with open(fname_spec, 'r') as fspec:
                        print('    found associated geners spec: ' + fname_spec)
                        gs_spec = json.load(fspec)

                        well_stack_name = gs_spec['name']
                        spec['well_stacks'].append(well_stack_name)
                        spec['specifications'][well_stack_name] = gs_spec
                else:
                    spec['well_stacks'].append(None)
        i = i + 1
    if t2verbatim:
        # have to finish verbatim if it happends to be the last line
        print('  inserting verbatim: (', t2vname, ')')
        gs = lines_to_geners(v_lines,t2vname)
        all_geners = all_geners + gs
        # finishes verbatim
    return all_geners, spec

class GenerSection(object):
    """ A gener section is a list of generator objects that generally represents
    a part of a field, which can change over time.  It is specified as a list of
    enddates with a list of respective geners.  Geners is a list of t2data
    generator objects. """
    def __init__(self):
        super(GenerSection, self).__init__()
        self.enddates = []
        self.geners = []
        self.specs = []

    def add(self, enddate=None, gener_list=[], spec=None):
        """ If enddate is None, means no enddate, applies forever.  If
        gener_list is empty list [], means no geners until the enddate.  It does
        NOT make sense to have both empty date and empty list. """
        if enddate is None and gener_list == []:
            logging.error("GenerSection.add(): It does not make sense to have a section without both enddate and gener_list.")
            return
        self.enddates.append(enddate)
        self.geners.append(gener_list)
        self.specs.append(spec)

    def periodRange(self, i):
        """ returns the starting and end time of period of index i """
        e = self.enddates[i] # could raise IndexError
        if i - 1 < 0:
            s = None
        else:
            s = self.enddates[i-1]
        return (s,e)

    def inRange(self,t,range_or_i):
        """ return True if t is within range of the specified range (or period
        index)"""
        if isinstance(range_or_i,tuple):
            r = range_or_i
        else:
            r = self.periodRange(range_or_i)

        s_ok = False
        if r[0] is None:
            s_ok = True
        else:
            if r[0] < t:
                s_ok = True

        e_ok = False
        if r[1] is None:
            e_ok = True
        else:
            if r[1] >= t:
                e_ok = True

        return all([s_ok,e_ok])

    def indexAt(self, date):
        """ This gives the index of the time period that covers the date. """
        for i in range(len(self.enddates)):
            if self.inRange(date,i):
                return i
        return None

    def genersAt(self, date):
        """ This gives the geners of the time period that covers the date. """
        i = self.indexAt(date)
        if i is None:
            return []
        else:
            return self.geners[i]

    def specsAt(self, date):
        i = self.indexAt(date)
        if i is None:
            return {}
        else:
            return self.specs[i]

    def nextDateAt(self, date):
        """ Returns the next time-tag, if the date value is queal to the in-
        range period's tim-tag, the next tim-tag will be used.  If no next time-
        tag, return None. """
        i = self.indexAt(date)
        if i is None:
            return None
        ed = self.enddates[i]
        if ed == date:
            if i+1 < len(self.enddates):
                ed = self.enddates[i+1]
            else:
                ed = None
        return ed

    def read(self, cfg, s_name, offset_date=0.0):
        """ Reads from a cfg entry, which contains information about time
        varying specification of a part of field.  """
        if isinstance(s_name, str):
            sec_lines = cfg.get_list(s_name)
        elif isinstance(s_name,list):
            sec_lines = s_name
        else:
            logging.error("Unable to read %s" % s_name)

        lines = []
        for line in sec_lines:
            if line.startswith('@'):
                time = date2num(line[1:]) - offset_date # in simulation time
                gs, spec = collect_geners_from_cfg(cfg,lines)
                self.add(time, gs, spec)
                lines = [] # reset for next time period
            else:
                lines.append(line)
        if lines:
            # some left-over lines without a end time-tag
            gs, spec = collect_geners_from_cfg(cfg,lines)
            # print(spec)
            self.add(None, gs, spec)

        # print('~~~~~~~~~~', self.specs)

import unittest
class GenerSectionTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def _make_gener_sect(self,list_of_tuples):
        """ [ (1990.0, [x,y,z]), (1995.0, []) ] will make GenerSection obj of
        gs.enddates = [1990.0, 1995.0], gs.geners = [[x,y,z],[]]"""
        gs = GenerSection()
        gs.enddates, gs.geners = zip(*list_of_tuples)
        return gs

    def test_read(self):
        lines = [
        ':aaa11a   1                   0     IMAK        1.0',
        ':aaa22a   2                   0     IMAK        2.0',
        ':aaa33a   3                   0     IMAK        3.0',
        '@ 1000.0',
        ':bbb44b   4                   0     IMAK        4.0',
        ':bbb55b   5                   0     IMAK        5.0',
        ':bbb66b   6                   0     IMAK        6.0',
        '@ 2000.0',
        ]
        gs = GenerSection()
        gs.read(None,lines)
        print("%i time periods:" % len(gs.enddates))
        for d,gg in zip(gs.enddates, gs.geners):
            print("    %s @ (%s)" % (str(d),'), ('.join([str(g) for g in gg])))

        lines = [
        ':aaa11a   1                   0     IMAK        1.0',
        ':aaa22a   2                   0     IMAK        2.0',
        ':aaa33a   3                   0     IMAK        3.0',
        ]
        gs = GenerSection()
        gs.read(None,lines)
        print("%i time periods:" % len(gs.enddates))
        for d,gg in zip(gs.enddates, gs.geners):
            print("    %s @ (%s)" % (str(d),'), ('.join([str(g) for g in gg])))

        lines = [
        '@ 1000.0',
        ':bbb44b   4                   0     IMAK        4.0',
        ':bbb55b   5                   0     IMAK        5.0',
        ':bbb66b   6                   0     IMAK        6.0',
        ]
        gs = GenerSection()
        gs.read(None,lines)
        print("%i time periods:" % len(gs.enddates))
        for d,gg in zip(gs.enddates, gs.geners):
            print("    %s @ (%s)" % (str(d),'), ('.join([str(g) for g in gg])))

    def test_geners_at(self):
        gs = self._make_gener_sect([
            (1000.0, [1,2,3]),
            (2000.0, [4,5,6]),
            ])
        self.assertEqual(gs.genersAt( 989.0), [1,2,3])
        self.assertEqual(gs.genersAt(1000.0), [1,2,3])
        self.assertEqual(gs.genersAt(1500.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.1), [])

        gs = self._make_gener_sect([
            (None, [1,2,3]),
            ])
        self.assertEqual(gs.genersAt( 989.0), [1,2,3])
        self.assertEqual(gs.genersAt(1000.0), [1,2,3])
        self.assertEqual(gs.genersAt(1500.0), [1,2,3])
        self.assertEqual(gs.genersAt(2000.0), [1,2,3])
        self.assertEqual(gs.genersAt(2000.1), [1,2,3])

        gs = self._make_gener_sect([
            (1000.0, []),
            (None, [4,5,6]),
            ])
        self.assertEqual(gs.genersAt( 989.0), [])
        self.assertEqual(gs.genersAt(1000.0), [])
        self.assertEqual(gs.genersAt(1500.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.1), [4,5,6])

        gs = self._make_gener_sect([
            (1000.0, [1,2,3]),
            ])
        self.assertEqual(gs.genersAt( 989.0), [1,2,3])
        self.assertEqual(gs.genersAt(1000.0), [1,2,3])
        self.assertEqual(gs.genersAt(1500.0), [])
        self.assertEqual(gs.genersAt(2000.0), [])
        self.assertEqual(gs.genersAt(2000.1), [])

        gs = self._make_gener_sect([
            (1000.0, []),
            (2000.0, [4,5,6]),
            ])
        self.assertEqual(gs.genersAt( 989.0), [])
        self.assertEqual(gs.genersAt(1000.0), [])
        self.assertEqual(gs.genersAt(1500.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.0), [4,5,6])
        self.assertEqual(gs.genersAt(2000.1), [])

    def test_next_date_at(self):
        gs = self._make_gener_sect([
            (1000.0, [1,2,3]),
            (2000.0, [4,5,6]),
            ])
        self.assertEqual(gs.nextDateAt( 989.0), 1000.0)
        self.assertEqual(gs.nextDateAt(1000.0), 2000.0)
        self.assertEqual(gs.nextDateAt(1500.0), 2000.0)
        self.assertEqual(gs.nextDateAt(2000.0), None)
        self.assertEqual(gs.nextDateAt(2000.1), None)

        gs = self._make_gener_sect([
            (None, [1,2,3]),
            ])
        self.assertEqual(gs.nextDateAt( 989.0), None)
        self.assertEqual(gs.nextDateAt(1000.0), None)
        self.assertEqual(gs.nextDateAt(1500.0), None)
        self.assertEqual(gs.nextDateAt(2000.0), None)
        self.assertEqual(gs.nextDateAt(2000.1), None)

        gs = self._make_gener_sect([
            (1000.0, []),
            (None, [4,5,6]),
            ])
        self.assertEqual(gs.nextDateAt( 989.0), 1000.0)
        self.assertEqual(gs.nextDateAt(1000.0), None)
        self.assertEqual(gs.nextDateAt(1500.0), None)
        self.assertEqual(gs.nextDateAt(2000.0), None)
        self.assertEqual(gs.nextDateAt(2000.1), None)

        gs = self._make_gener_sect([
            (1000.0, [1,2,3]),
            ])
        self.assertEqual(gs.nextDateAt( 989.0), 1000.0)
        self.assertEqual(gs.nextDateAt(1000.0), None)
        self.assertEqual(gs.nextDateAt(1500.0), None)
        self.assertEqual(gs.nextDateAt(2000.0), None)
        self.assertEqual(gs.nextDateAt(2000.1), None)

        gs = self._make_gener_sect([
            (1000.0, []),
            (2000.0, [4,5,6]),
            ])
        self.assertEqual(gs.nextDateAt( 989.0), 1000.0)
        self.assertEqual(gs.nextDateAt(1000.0), 2000.0)
        self.assertEqual(gs.nextDateAt(1500.0), 2000.0)
        self.assertEqual(gs.nextDateAt(2000.0), None)
        self.assertEqual(gs.nextDateAt(2000.1), None)


    def tearDown(self):
        pass

def make_ver1(cfg):
    """ this is the original make_scenario, based on a list of specified time
    cuts, and each time cut is specified.  This is the older way of making
    scenarios, suitable for those have sorted out the scenarios nicely already.
    It may be harder to use than ver2 if start from scratch. """
    sname = cfg.get_value('ScenarioName').strip()
    #nsdat = t2data(cfg.get_value('NaturalStateDataFile').strip())
    prname = cfg.get_value('ProductionDataFile').strip()
    prdat = t2data(prname)
    prsav = t2incon(prname[:-3]+'save')
    dates = cfg.get_list('ScheduleDates')
    offset_date = cfg.get_value('HistoryStartingTime').strip()

    # processing info from CFG
    date_values = []
    try: offset_data_value = float(offset_date)
    except: offset_data_value = date2num(offset_date)
    for d in dates:
        try: date_values.append(float(d) - offset_data_value)
        except: date_values.append(date2num(d) - offset_data_value)

    namebase = os.path.basename(prname).split('_')[0].replace('pr','fut') + '_' + sname + '_'
    dirname = sname + '\\'
    sfilenames = []
    for i in range(1,len(dates)+1):
        sfilenames.append(namebase + '%02d'%i)
    make_sequential_batch_cmd(sfilenames,dirname)
    make_sequential_batch_cmd_sh(sfilenames,dirname)
    sfilenames = [dirname+s+'.dat' for s in sfilenames]
    prsav.write(dirname+sfilenames[0]+'.incon', reset=True)

    print('--------------------------------------------')
    print('Common building blocks:')
    geners_common, spec_common = collect_geners_from_cfg(cfg, 'Gener_Common')

    for i in range(len(dates)):
        print('--------------------------------------------')
        print('File ', i+1, ' enddate: ', dates[i], '(', date_values[i], ')')
        prdat.parameter['tstart'] = prdat.parameter['tstop']
        prdat.parameter['tstop'] = date_values[i] *60.0*60.0*24.0*365.25

        geners_this, spec_this = collect_geners_from_cfg(cfg, 'Gener_'+str(i+1))
        prdat.clear_generators()
        for g in geners_common: prdat.add_generator(g)
        for g in geners_this: prdat.add_generator(g)

        print('Writing scenario file: ', sfilenames[i], '...')
        prdat.write(sfilenames[i])

    print('--------------------------------------------')
    print('Done - Finished writing all scenario files.')

def make_ver2(cfg):
    """ This reads, process, and makes scenario using VERSION 2 INTERFACE, with
    time-varied ScenarioSections specified.  The config file must have
    [ScenarioSections] and [ScenarioEndingTime] specified.  Each section should
    have time-tags spliting section into parts,each applied to a time period.
    """
    scenario_spec = {}
    ##### collect misc. info
    sname = cfg.get_value('ScenarioName').strip()
    prname = cfg.get_value('ProductionDataFile').strip()
    prdat = t2data(prname)
    prsav = t2incon(prname[:-3]+'save')

    offset_date = date2num(cfg.get_value('HistoryStartingTime').strip())
    final_date = date2num(cfg.get_value('ScenarioEndingTime').strip())

    print_all_init_tables = False
    if cfg.check_optional('PrintAllInitialTables'):
        if cfg.get_value('PrintAllInitialTables').strip().lower() == 'true':
            print_all_init_tables = True

    print_conne_table = False
    if cfg.check_optional('PrintConnectionTables'):
        if cfg.get_value('PrintConnectionTables').strip().lower() == 'true':
            print_conne_table = True

    if cfg.check_optional('Simulator'):
        simulator = cfg.get_value('Simulator').strip()

    scenario_spec.update({
        'name': sname,
        'pr_model': prname,
        'date_offset': offset_date,
        'date_end': final_date,
        'simulator': simulator,
        'simulations': [],
        'well_stack_specification': {},
    })

    ##### compose sections for the scenario
    sections = []
    section_names = cfg.get_list('ScenarioSections')
    for s_name in section_names:
        sect = GenerSection()
        sect.read(cfg,s_name)
        sections.append(sect)

    ##### check all possible time period
    start_t = prdat.parameter['tstop'] / SEC_IN_A_YEAR + offset_date
    final_t = final_date
    logging.debug("before iterating s = %.2f f = %.2f" % (start_t,final_t))
    times = []
    while start_t < final_t:
        end_t = min([s.nextDateAt(start_t) for s in sections if s.nextDateAt(start_t) is not None] + [final_t])
        times.append((start_t,end_t))
        start_t = end_t

    ##### geneerating simulation file names
    namebase = os.path.basename(prname).split('_')[0].replace('pr','fut') + '_' + sname + '_'
    dirname = sname + sep
    try:
        mkdir(dirname)
    except OSError:
        pass
    sfilenames = [namebase + '%02d'%i for i in range(1,len(times)+1)]

    # the value will lose some precision as it's being written into file (via t2data)
    from functools import partial
    t2_prec = partial(lose_precision,frmt='%10.4e')
    # make t2data write input file with slightly higher prec tstart and tstop
    enable_t2data_time_higher_prec()

    ##### actually make these generators and input files
    actual_sfilenames, skipped = [], []
    cnt = 0
    import copy
    orig_output_times = copy.deepcopy(prdat.output_times)
    orig_timestep = prdat.parameter['timestep'][0]
    for (i,fname), (start_t,end_t) in zip(enumerate(sfilenames),times):
        logging.info("+++ %i from %.3f to %.3f" % (i+1,start_t,end_t))
        prdat.parameter['tstart'] = (start_t - offset_date) * SEC_IN_A_YEAR
        prdat.parameter['tstop'] = (end_t - offset_date) * SEC_IN_A_YEAR

        if print_conne_table:
            prdat.parameter['print_level'] = 3
        else:
            prdat.parameter['print_level'] = 1

        # avoid the negative time stepping in case stopping time is shorter than
        # the first initial time step
        prdat.parameter['timestep'][0] = orig_timestep
        true_tstart = t2_prec(prdat.parameter['tstart'])
        true_tstop = t2_prec(prdat.parameter['tstop'])
        t_diff = true_tstop - true_tstart
        if t_diff < prdat.parameter['timestep'][0]:
            prdat.parameter['timestep'][0] = t_diff

        # skip if the actual time diff is too small
        if t2_prec(t_diff) == 0.0:
            logging.warning("Sim %i skiped because time diff too small." % i)
            skipped.append("%.4f -- %.4f (%10.4e -- %10.4e)" % (start_t,end_t,true_tstart,true_tstop))
            continue

        # TODO: find a better rule to avoid negative time steping
        # don't need yearly output times if sim is very short.
        # if t_diff < 0.1 * SEC_IN_A_YEAR:
        #     prdat.output_times = {}
        # else:
        #     prdat.output_times = copy.deepcopy(orig_output_times)

        # avoid printing initial tables after second run
        cnt += 1
        if cnt > 1:
            if print_all_init_tables:
                prdat.parameter['option'][24] = 2
            else:
                prdat.parameter['option'][24] = 0

        # ensure simulation finishes - not restricting MCYC, need new autough2
        prdat.parameter['max_timesteps'] = -1

        gener_this = []
        specs_this = []
        for s in sections:
            # the period is actually FROM start_t + a_very_small_number TO end_t
            gener_this += s.genersAt(end_t)
            specs_this.append(s.specsAt(end_t))
            # print(specs_this)
        for g in gener_this:
            logging.debug("  ('%s','%s')" % (g.block,g.name))

        prdat.clear_generators()
        for g in gener_this:
            prdat.add_generator(g)

        logging.debug("Simulation file %s written." % fname)
        prdat.write(dirname+fname+'.dat')
        if i == 0:
            prsav.write(dirname+fname+'.incon')
        actual_sfilenames.append(fname)

        scenario_spec['simulations'].append({
            'filename': fname,
            'aut2_tstart_sec': true_tstart,
            'aut2_tstop_sec': true_tstop,
            'tstart_yr': start_t,
            'tstop_yr': end_t,
            'specs': specs_this,
        })

    ##### make helper batch file
    make_sequential_batch_cmd(actual_sfilenames, dirname, simulator=simulator)
    make_sequential_batch_cmd_sh(sfilenames,dirname, simulator=simulator)
    make_save2incon(dirname)

    ##### warn about any skips
    if len(skipped) > 0:
        logging.warning("%i simulations are skipped" % len(skipped))
        for skp in skipped:
            logging.warning(skp)

    logging.info('Generating scenario spec file: scenario_spec.json')
    with open(dirname + 'scenario_spec.json', 'w') as fspec:
        json.dump(scenario_spec, fspec, indent=4, sort_keys=True)

def main():
    # read CFG file, if not specified, default name is assumed
    cwd = getcwd() + sep
    cfg = config()
    if len(argv) > 1:
        cfg.read_from_file(cwd+argv[1])
    else:
        cfg.read_from_file(cwd+'make_scenarios.cfg')

    if cfg.check_optional('ScheduleDates'):
        logging.info("[ScheduleDates] found in config -> use version 1 make")
        logging.warning("Please note version 1 format make is legacy, which is harder to use, please use version 2 spec format for new projects. AY May 2014.")
        make_ver1(cfg)
    elif cfg.check_optional('ScenarioEndingTime') and cfg.check_optional('ScenarioSections'):
        logging.info("[ScenarioEndingTime] and [ScenarioSections] found in config -> use version 2 make")
        make_ver2(cfg)
    else:
        logging.error("Please make sure you are configuring the scenario either using version 1 or 2, but not both!")
    return 0

if __name__ == '__main__':
    main()
