import re
import os
import json

from gimfu.t2listingh5 import t2listingh5
from gimfu.geo_common import quick_enthalpy

from t2data import t2generator
from t2data import t2data_parser, t2data
from t2incons import t2incon
from t2thermo import *
import numpy as np

KGSPERTD = 1000./24./60./60. # kg/s per ton/day
KGSPERTH = 1000./60./60. # kg/s per ton/hour

def normalname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    is_match = True
    for i in xrange(5):
        if name_wc[i] != '*':
            if name_wc[i] != name[i]:
                is_match = False
                break
    return is_match

def toughname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    from mulgrids import unfix_blockname
    c_name_wc = unfix_blockname(name_wc)
    c_name = unfix_blockname(name)

    is_match = True
    for i in xrange(5):
        if c_name_wc[i] != '*':
            if c_name_wc[i] != c_name[i]:
                is_match = False
                break
    return is_match

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

def write_geners(geners, fname, silent=True):
    if not silent:
        print('Writing %s ...' % fname)
    tmpdat = t2data()
    outfile=t2data_parser(fname,'w')
    outfile.write('GENER\n')
    for g in geners:
        tmpdat.write_generator(g,outfile)
    outfile.close()

def write_gener_file(geners, filename, silent=True):
    if not silent:
        print('Writing %s ...' % filename)
    dat = t2data()
    for g in geners:
        dat.add_generator(g)
    outfile=t2data_parser(filename,'w')
    dat.write_generators(outfile)
    outfile.close()

def write_gener_if(geners, is_true, filename):
    """ This will go through a list of t2generators, and only writes to file is
    individual generator is qualified by is_true.  is_true is a callable,
    accepting a single t2generator object, returns True or False.
    """
    dat = t2data()
    for g in geners:
        if is_true(g):
            dat.add_generator(g)
    outfile=t2data_parser(filename,'w')
    dat.write_generators(outfile)
    outfile.close()

def select_geners_byname(names, geners, warning=False):
    selected = []
    for gn in names:
        gre = re.compile(gn)
        gs = [g for g in geners if gre.match(g.name)]
        if warning and len(gs) == 0:
            raise Exception("No gener(s) match %s" % gn)
        selected += gs
    return selected

def well_blocks(geo, well_name, divisions=1, elevation=False,
    deviations=False, qtree=None, extend=False):
    blocks = geo.well_values(well_name,
                             geo.block_name_list,
                             divisions=divisions,
                             elevation=elevation,
                             deviations=deviations,
                             qtree=qtree,
                             extend=extend)
    if blocks is None:
        raise Exception('Well %s not found in geometry %s' % (well_name, geo.filename))
    return blocks[1]

def modify_wellname(mod,original):
    """ modifying well name according to rules: any '*' characters in mod
    will be keep original name, otherwise overwritten by mod. """
    newname = []
    for i in range(5):
        if mod[i] == '*':
            newname.append(original[i])
        else:
            newname.append(mod[i])
    return "".join(newname)

def imak_group_by_ratios(ratios, total, geners,
                         overflow_unit_ratio=0.1, overflow_times=None,
                         warning=False):
    """
    overflow_unit_ratio between 0.0 and 1.0
    if overflow_times is integer, repeat base geners n times with the ratio
    """
    all_geners = []
    base_geners = []
    for wn, ratio in ratios:
        wgs = select_geners_byname([wn], geners, warning=True)
        for g in wgs:
            g.gx = total * ratio / float(len(wgs))
            base_geners.append(g)
            all_geners.append(g)
    from copy import deepcopy
    if isinstance(overflow_times, int):
        for i in range(overflow_times):
            for g in base_geners:
                gg = deepcopy(g)
                gg.gx = g.gx * overflow_unit_ratio
                all_geners.append(gg)
    return all_geners

def make_IMAK_wells(incon, addp, pi, temp, newwell_labels, blocks, rates,
                    new_total_rate):
    """  returns a list of generators. if newwell_labels contains '*' the '*'s
    will be replaced by an incrementing integer.
    """

    total_rate = sum(rates)
    dat = t2data()
    for i in range(len(blocks)):
        gx = rates[i] / total_rate * new_total_rate
        ex = quick_enthalpy(temp,'liq')
        hg = incon[b][0] + addp
        fg = pi

        w_name = modify_wellname(newwell_labels,'%05d'%(i+1))
        g=t2generator(name=w_name,block=blocks[i],type='IMAK',gx=gx,ex=ex,hg=hg,fg=fg)
        dat.add_generator(g)
    return dat.generatorlist

def make_IMAK_by_blocks(total_rate, blocks_ratios, incon, addp, pi, temp,
                        geo,
                        naming='II***',
                        overflow_unit_ratio=0.1, overflow_times=None,
                        warning=False):
    """ if incon is None, use rho*g*h + addp as IMAK pressure, otherwise use
    incon of the block to add p

    Usually block_ratios is a list of tuples of (block, ratio).  But it is
    possible to have tuples of three (block, ratio, naming), where the naming
    will overwrite the routine level naming.
    """

    rho = cowat(temp, sat(temp)+1.0e5)[0]

    all_geners = []
    base_geners = []
    for br in blocks_ratios:
        if len(br) == 2:
            b, ratio = br
            final_naming = naming
        elif len(br) == 3:
            b, ratio, final_naming = br

        if isinstance(addp, dict):
            _addp = addp[b]
        else:
            _addp = addp


        if incon is None:
            col = geo.column[geo.column_name(b)]
            lay = geo.layer[geo.layer_name(b)]
            pbottom = rho * 9.81 * (col.surface - geo.block_centre(lay, col)[2])
            pbottom += _addp
        else:
            pbottom = incon[b][0] + _addp

        # print('# making GENERs:')
        g = t2generator(name=modify_wellname(final_naming,b),
                        block=b,
                        type='IMAK',
                        gx=total_rate * ratio,
                        ex=quick_enthalpy(temp,'liq'),
                        hg=pbottom,
                        fg=pi,
                        )
        base_geners.append(g)
        all_geners.append(g)

    from copy import deepcopy
    if isinstance(overflow_times, int):
        for i in range(overflow_times):
            for g in base_geners:
                gg = deepcopy(g)
                gg.gx = g.gx * overflow_unit_ratio
                all_geners.append(gg)
    return all_geners




def make_IMAK_by_wellnames(total_rate, wellnames_ratios, incon, addp, pi, temp,
                           feedzone_fname, geo,
                           naming='II***',
                           overflow_unit_ratio=0.1, overflow_times=None,
                           warning=False):
    """ if incon is None, use rho*g*h + addp as IMAK pressure,
    otherwise use incon of the block to add p.

    For each inj well to have its own WHP, addp can be specified as a dict.  The
    keys should be wellnames, same as used for ratios and feedzones.
    """

    rho = cowat(temp, sat(temp)+1.0e5)[0]


    with open(feedzone_fname, 'r') as f:
        data_feeds = json.load(f)

    all_geners = []
    base_geners = []
    for wn,ratio in wellnames_ratios:
        # print('# checking %s feedzones' % wn,)
        bs = well_blocks(geo, wn)
        feed_blocks = []
        for f in data_feeds[wn]:
            for b in bs:
                blay = geo.layer[geo.layer_name(b)]
                btop, bbot = blay.top, blay.bottom
                ftop, fbot = f['elev_top'], f['elev_bot']
                if (ftop > bbot > fbot) or (ftop > btop > fbot) or (btop >= ftop and bbot <= fbot):
                    # print(b,)
                    if b not in feed_blocks:
                        feed_blocks.append(b)
        if isinstance(addp, dict):
            _addp = addp[wn]
        else:
            _addp = addp
        for b in feed_blocks:
            if incon is None:
                col = geo.column[geo.column_name(b)]
                lay = geo.layer[geo.layer_name(b)]
                pbottom = rho * 9.81 * (col.surface - geo.block_centre(lay, col)[2])
                pbottom += _addp
            else:
                pbottom = incon[b][0] + _addp
            g = t2generator(name=modify_wellname(naming,wn),
                            block=b,
                            type='IMAK',
                            gx=total_rate * ratio / float(len(feed_blocks)),
                            ex=quick_enthalpy(temp,'liq'),
                            hg=pbottom,
                            fg=pi,
                            )
            base_geners.append(g)
            all_geners.append(g)

    from copy import deepcopy
    if isinstance(overflow_times, int):
        for i in range(overflow_times):
            for g in base_geners:
                gg = deepcopy(g)
                gg.gx = g.gx * overflow_unit_ratio
                all_geners.append(gg)
    return all_geners


def make_IMAK_by_well(total_rate, wellnames_ratios, incon, addp, pi, temp,
                           feed_block_ratios, geo,
                           naming='II***',
                           overflow_unit_ratio=0.1, overflow_times=None,
                           warning=False):
    """ if incon is None, use rho*g*h + addp as IMAK pressure,
    otherwise use incon of the block to add p.

    feed_block_ratios is a dict of wellname: ["block": ratio, ...]

    For each inj well to have its own WHP, addp can be specified as a dict.  The
    keys should be wellnames, same as used for ratios and feedzones.
    """
    rho = cowat(temp, sat(temp)+1.0e5)[0]

    all_geners = []
    base_geners = []
    for wn,w_ratio in wellnames_ratios:
        if isinstance(addp, dict):
            _addp = addp[wn]
        else:
            _addp = addp
        for b,b_ratio in feed_block_ratios[wn].items():
            if incon is None:
                col = geo.column[geo.column_name(b)]
                lay = geo.layer[geo.layer_name(b)]
                pbottom = rho * 9.81 * (col.surface - geo.block_centre(lay, col)[2])
                pbottom += _addp
            else:
                pbottom = incon[b][0] + _addp
            g = t2generator(name=modify_wellname(naming,wn),
                            block=b,
                            type='IMAK',
                            gx=total_rate * w_ratio * b_ratio,
                            ex=quick_enthalpy(temp,'liq'),
                            hg=pbottom,
                            fg=pi,
                            )
            base_geners.append(g)
            all_geners.append(g)

    from copy import deepcopy
    if isinstance(overflow_times, int):
        for i in range(overflow_times):
            for g in base_geners:
                gg = deepcopy(g)
                gg.gx = g.gx * overflow_unit_ratio
                all_geners.append(gg)
    return all_geners


def make_injection_IMAK_group(geo, group_naming, rate, temp, wells, whp=None,
                              incon=None, pi=None, is_condensate=False, max_whp=None,
                              feedzone_filename=None, warning=True,
                              overflow_unit_ratio=1.0, overflow_times=0):

    """ make a group of IMAK geners that cap total to the specified rate.  it
    can be specified by either a list of wells and/or blocks.  Returns a list of
    T2 generators.

    If incon is None, injection pressure = rho * g * depth + whp. If incon is a
    t2incon object, whp is 'additional pressure', added onto the block's
    pressure from t2incon, injection pressure = whp + block_pressure.

    If max_whp is specified, it will act as an additional cap for all specified
    WHPs.

    To specify wells, use a list of tuples:
        (well name, block, ratio, whp, pi)
    Here the second element is set to None, blocks of the well will be worked
    out from the feedzone information.  If block is a valid string, then
    generator will be created using well name.  If specifying by block, well
    can be left as None if the gener is to be named as the block name.  eg.
        ('WK123',    None, 0.3, 10.0*e5, 1.0e-11), # WK123 may have several blocks,
        ('IA124', 'asd21', 0.7, 11.0*e5, 1.0e-11), # gener.name = 'IA124'
        (None,    'asd21', 0.7, 11.0*e5, 1.0e-11), # gener.name = 'asd21'

    whp and pi can be specified at the well/block level.  If the value is None
    in individual well/block, then it will use the default single value.
    """
    if is_condensate:
        pi_factor = -1.0
    else:
        pi_factor = 1.0

    # print('making %s %.1f kg/s ...' % (group_naming, rate))
    gs = []
    for wname, block, ratio, _whp, _pi in wells:
        if _whp is None: _whp = whp
        if max_whp is not None:
            _whp = min(_whp, max_whp)
        if _pi is None: _pi = pi
        if wname is None: wname = block
        if block is None:
            # by wells
            gs +=make_IMAK_by_wellnames(rate, [(wname, ratio)], incon=incon,
                                        addp={wname: _whp}, pi=_pi*pi_factor,
                                        temp=temp,
                                        feedzone_fname=feedzone_filename,
                                        geo=geo, naming=group_naming,
                                        overflow_unit_ratio=0.0,
                                        overflow_times=0,
                                        warning=warning)
        else:
            # by block
            gs += make_IMAK_by_blocks(rate, [(block, ratio, wname)], incon=incon,
                                      addp=_whp, pi=_pi*pi_factor, temp=temp,
                                      geo=geo, naming=group_naming,
                                      overflow_unit_ratio=0.0,
                                      overflow_times=0,
                                      warning=warning)
    for gener in gs:
        gener.name = modify_wellname(group_naming, gener.name)

    from copy import deepcopy
    gs_overflow = []
    if overflow_times > 0:
        for g in gs:
            gg = deepcopy(g)
            gg.gx = g.gx * overflow_unit_ratio
            gs_overflow.append(gg)

    return gs + gs_overflow * overflow_times


def test_make_injection_IMAK_group():
    # test 1
    naming = 'IA7'
    naming2 = naming + (5-len(naming)) * '*'
    rate = 5. *1000.*KGSPERTD
    temp = 108.0
    whp = 10.0e5

    bs = ['mar48', 'mar49', 'nar48', 'nar49', ]
    grp_def = [
        ('mar48', 'mar48', 0.25, None, None),
        ('mar49', 'mar49', 0.25, None, None),
        ('nar48', 'nar48', 0.25, None, None),
        ('nar49', 'nar49', 0.25, None, None),
    ]

    write_geners(inj_sgw_makeup(naming, rate, temp, bs, whp),
                 'inj_test1_A.geners')
    write_geners(make_injection_IMAK_group(geo, naming2, rate, temp, grp_def,
                                           whp=whp, incon=None, pi=INJECTIVITY,
                                           is_condensate=False,
                                           feedzone_filename=feed_zone_file,
                                           warning=True),
                 'inj_test1_B.geners')

    # test 2
    naming = 'IDK'
    naming2 = naming + (5-len(naming)) * '*'
    temp = 40.0
    whp = 12.0*1.0e5

    grp_def = [
        ('WK407',    None, 1.00, None, None),
    ]

    write_geners(inj_cnd_407('ID', rate, temp)[0],
                 'inj_test2_A.geners')
    write_geners(make_injection_IMAK_group(geo, naming2, rate, temp, grp_def,
                                           whp=whp, incon=None, pi=INJECTIVITY,
                                           is_condensate=True,
                                           feedzone_filename=feed_zone_file,
                                           warning=True) * 6,
                 'inj_test2_B.geners')

    # test 3
    naming = 'IC'
    naming2 = naming + (5-len(naming)) * '*'
    temp = 40.0
    whp = 12.0*1.0e5
    grp_def = [
        #  wname,   block, ratio,        whp,   pi
        ('WK301',    None,  0.05, 27.0*1.0e5, None),
        ('WK304',    None,  0.02, 20.0*1.0e5, None),
        ('WK308',    None,  0.25, 15.0*1.0e5, None),
        ('WK309',    None,  0.15, 16.0*1.0e5, None),
        ('WK310',    None,  0.03, 20.0*1.0e5, None),
        ('WK317',    None,  0.15, 38.0*1.0e5, None),
        ('WK318',    None,  0.15, 20.0*1.0e5, None),
        ('WK321',    None,  0.20, 36.0*1.0e5, None),
        ]

    write_geners(inj_cnd_otupu(naming, rate, temp, max_whp=None)[0],
                 'inj_test3_A.geners')
    write_geners(make_injection_IMAK_group(geo, naming2, rate, temp, grp_def,
                                           whp=whp, incon=None, pi=INJECTIVITY,
                                           is_condensate=True,
                                           feedzone_filename=feed_zone_file,
                                           warning=True,
                                           overflow_unit_ratio=0.5,
                                           overflow_times=1),
                 'inj_test3_B.geners')

    # test 4
    naming = 'IK'
    naming2 = naming + (5-len(naming)) * '*'
    temp = 108.0
    whp = 12.0*1.0e5
    grp_def = [
        #  wname,   block, ratio,        whp,   pi
        ('WK401',    None,  0.10, 13.2*1.0e5, None),
        ('WK403',    None,  0.25, 19.5*1.0e5, None),
        ('WK404',    None,  0.15, 45.4*1.0e5, None),
        ('WK408',    None,  0.15, 53.0*1.0e5, None),
        ('WK409',    None,  0.10, 34.2*1.0e5, None),
        ('WK410',    None,  0.25, 29.5*1.0e5, None),
    ]

    write_geners(inj_sgw_karapiti(naming, rate, temp, max_whp=None)[0],
                 'inj_test4_A.geners')
    write_geners(make_injection_IMAK_group(geo, naming2, rate, temp, grp_def,
                                           whp=whp, incon=None, pi=INJECTIVITY,
                                           is_condensate=False,
                                           feedzone_filename=feed_zone_file,
                                           warning=True,
                                           overflow_unit_ratio=0.5,
                                           overflow_times=0),
                 'inj_test4_B.geners')

    # test 5 (mixed)
    naming = 'IK'
    naming2 = naming + (5-len(naming)) * '*'
    temp = 108.0
    whp = 12.0*1.0e5
    grp_def = [
        ('WK407',    None, 0.20, 12.e5, None),
        ('mar48', 'mar48', 0.20, 10.e5, None),
        ('mar49', 'mar49', 0.20, 10.e5, None),
        ('nar48', 'nar48', 0.20, 10.e5, None),
        ('nar49', 'nar49', 0.20, 10.e5, None),
    ]

    write_geners(make_injection_IMAK_group(geo, naming2, rate, temp, grp_def,
                                           whp=whp, incon=None, pi=INJECTIVITY,
                                           is_condensate=False,
                                           feedzone_filename=feed_zone_file,
                                           warning=True,
                                           overflow_unit_ratio=0.5,
                                           overflow_times=0),
                 'inj_test5.geners')


def block_depth(geo, block_name):
    """ get depth of a model block (from surface)

    If block_name is a list of names, then a list of depths will be returened.
    """
    if not isinstance(block_name, list):
        bs = [block_name]
    else:
        bs = block_name
    depths = []
    for b in bs:
        c = geo.column_name(b)
        lay = geo.layer[geo.layer_name(b)]
        try:
            depths.append(geo.column[c].surface - geo.block_centre(lay, geo.column[c])[2])
        except KeyError:
            # happends when column does not exist (special atm)
            depths.append(geo.layerlist[0].bottom - lay.centre)
    if not isinstance(block_name, list):
        return depths[0]
    else:
        return depth


def liq_inj_pressure(t, depth, pump):
    """ Returns pressure at depth by adding over-/pump- pressure to rho*g*h.

    temp in degc, depth in m, pump pressure in pa """
    import t2thermo
    # liq water density does not vary too much with pressure
    # hence assume saturation pressure + 10 bar
    ADD_SAT_P = 10.0e5
    g = 9.81
    d, u = t2thermo.cowat(t, p=t2thermo.sat(t)+ADD_SAT_P)
    return d * g * depth + pump

class DeliverabilityCurvesSteam(object):
    """ a simplified, depth-independent curve used for steam wells
    """
    def __init__(self, pcutoff=2.5e5, phuge=300.e5):
        # all in (Pa)
        self.phuge = phuge
        self.pcutoff = pcutoff

    def get_pcutoff_table(self):
        w_enth = [0.0000000e+00, 2.0000000e+06, 2.1000000e+06, 2.8000000e+06]
        w_pres = [   self.phuge,    self.phuge,  self.pcutoff,  self.pcutoff]
        return w_enth, w_pres

    def __repr__(self):
        return 'steam-cutoff-%.2f-bar' % (self.pcutoff/1.e5)

class DeliverabilityCurves(object):
    """ Pcutoff vs. Enthalpy curve set for GENER types such as DELG and DMAK.

    The set includes a Pcutoff vs Enthalpies for a set of Depths.

    hard_cutoff_enth - (J/kg) is the *hard* cut-off enthalpy, the table was
    overwrittend below this point to use the p_huge value.  If None, table's
    enthalpies will not be altered.

    p_huge - (Pa) is the huge value used for hard cutoff
    """
    def __init__(self, filename=None):
        self.depths = None # a list of depths (m)
        self.enths = None  # a list of enthalpies (J/kg)
        self.table = None  # a numpy () array of Pcutoffs (Pa) (n_depths, n_enths)
        self.hard_cutoff_enth = None # (J/kg)
        self.p_huge = 500.0e5 # (Pa)
        self.curve_source = 'cfg'
        if filename is not None:
            self.load_from_cfg(filename)

    def load_from_cfg(self, filename):
        from gimfu import config
        if isinstance(filename, config.config):
            cfg = filename
        else:
            self.curve_source = filename
            cfg = config.config(filename)
        # unfortunately old curve.cfg format uses kJ/kg and bar here
        # load the tables and depths values
        self.depths = [float(a) for a in cfg.get_list('LookupDepths')]
        self.enths = [float(a)*1000.0 for a in cfg.get_list('PcutoffEnthalpyTable')[0].split()]
        table_raw = cfg.get_list('PcutoffEnthalpyTable')
        self.table = np.array([[float(a)*1.0e5 for a in table_raw[i].split()] for i in range(1,len(table_raw))])
        # array of shape (len(depths), len(enths))

        if cfg.check_optional('CutoffEnthalpy'):
            self.hard_cutoff_enth = float(cfg.get_value('CutoffEnthalpy').strip()) * 1000.0
        if cfg.check_optional('HugePressure'):
            self.p_huge = float(cfg.get_value('HugePressure').strip()) * 1.0e5

    def get_pcutoff_table(self, depth):
        """ get a "Pcutoff vs. Enthalpy" curve for a given depth

        returns (enthalpy list, pressure list), can be used in DELG/DMAK etc.
        """
        SMALL_ENTH = 10.0 * 1000.0 # small increment of enthalpy for creating the cutoff region
        if (depth < self.depths[0]) or (depth > self.depths[-1]):
            raise Exception('!!! Depth of %f out of DeliverabilityCurves range: (%f,%f)' % (depth, self.depths[0], self.depths[-1]))

        pressures = [np.interp(depth, self.depths, self.table[:,e]) for e in range(len(self.enths))]

        # start table to cover zero
        w_enth, w_pres = [0.0], [self.p_huge]
        if self.hard_cutoff_enth is not None:
            # pad if hard cutoff
            p_enth_add10 = np.interp(self.hard_cutoff_enth + SMALL_ENTH , self.enths, pressures)
            w_enth += [self.hard_cutoff_enth, self.hard_cutoff_enth+SMALL_ENTH]
            w_pres += [self.p_huge, p_enth_add10]
        else:
            # otherwise cutoff at SMALL_ENTH
            w_enth += [self.enths[0] + SMALL_ENTH]
            w_pres += [self.p_huge]

        # form the table to be inserted into generator
        ii = [i for i in range(len(self.enths)) if self.enths[i] > w_enth[-1]]
        w_enth += [self.enths[i] for i in ii]
        w_pres += [pressures[i] for i in ii]

        # add one last entry if the table may not cover all enthalpy situations
        if w_enth[-1] < 2800.0e3:
            w_enth.append(2800.0e3)
            w_pres.append(w_pres[-1])

        return w_enth, w_pres

    def __repr__(self):
        return self.curve_source


def get_delg_pis(geners, pr_filename, sav_filename, init_massflow=None,
                 tmpdir='tmp_get_pi_delg', aut2='AUTOUGH2_7_0-10',
                 not_flowing_pi=None, pr_listing=None):
    """ Using AUTOUGH2's .autogeners to get PIs for DELG/DMAK/DMAT generators.

    TOUGH2 input file name expected here instead of t2data object because we
    want to open a new instance of t2data for temporary use, just to avoid
    potential confusion with whatever that is passed in.

    Output geners will have .gx overwritten by PI calculated by AUT2 in all
    cases.  But other values such as .type .ex .hg .fg will be kept as the
    original geners.

    This subroutine also supports metadata, if the original t2generator has
    additional property of .meta then it will be inherited by the returned
    generators.  It doesn't matter what object it is.

    If not_flowing_pi is set, it will be used to replace the 0.0 PI caused by
    generators that are not flowing (possibly due to pressure too low).

    NOTE if the well is not able to flow, PI will be 0.0 (from AUT2)
    """
    # only works with these, others may have incompatable gener properties
    for g in geners:
        if g.type not in ['DELG', 'DMAK', 'DMAT']:
            raise Exception("get_delg_pis() does not support gener '%s' with type: '%s'" % (str(g), g.type))

    if init_massflow is None:
        # use rates with original .hg
        init_rates = [-abs(g.hg) for g in geners]
    elif isinstance(init_massflow, list):
        if len(init_massflow) != len(geners):
            raise Exception("get_delg_pis() init_massflow does not have correct length!")
        init_rates = [-abs(f) for f in init_massflow]
    elif isinstance(init_massflow, float):
        init_rates = [-abs(init_massflow)] * len(geners)

    orig_meta = {(g.block, g.name): g.meta for g in geners if hasattr(g, 'meta')}
    orig_types = [g.type for g in geners]
    orig_hgs = [g.hg for g in geners]
    orig_fgs = [g.fg for g in geners]
    tmp = t2data(pr_filename)
    tmp.clear_generators()
    tmp.parameter['max_timesteps'] = 1
    tmp.parameter['max_timestep'] = 1.0 # sec
    tmp.parameter['print_level'] = 1 # supress CCCCC table dump
    for g, ir in zip(geners, init_rates):
        g.type = 'DELG'
        g.hg = ir
        tmp.add_generator(g)
    sav = t2incon(sav_filename)

    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)
    original_dir = os.getcwd()
    os.chdir(tmpdir)

    # ---
    tmp.write('tmp.dat')
    sav.write('tmp.incon', reset=True)
    tmp.run(save_filename='tmp.save',
            incon_filename='tmp.incon',
            simulator=aut2,
            silent=True)
    auto_gs = read_gener_file('tmp.autogeners')
    lst = t2listingh5('tmp.h5')
    lst.last()
    if pr_listing:
        pr_listing.last()
    for g,t,hg,fg in zip(auto_gs, orig_types, orig_hgs, orig_fgs):
        if g.gx == 0.0:
            # find out how much too low pressure is
            enth = lst.generation[(g.block, g.name)]['Enthalpy']

            if pr_listing:
                for block, name in pr_listing.generation.row_name:
                    if g.block == block:
                        enth = pr_listing.generation[(g.block, name)]['Enthalpy']

            pres = lst.element[g.block]['Pressure']
            p_cutoff = np.interp(enth, g.time, g.rate)

            if not_flowing_pi is not None:
                print('*** %s:%s possibly pressure too low to flow, reset PI to %10.4e' % (
                    g.block, g.name, not_flowing_pi))
                g.gx = not_flowing_pi
            else:
                print('*** %s:%s possibly pressure too low to flow, PI is ZERO' % (
                    g.block, g.name))

            print('                ' \
                  '%10.5f < %10.5f bar at %10.5f kJ/kg' % (
                  pres / 1.e5, p_cutoff / 1.e5, enth / 1.e3))
        g.type = t
        g.hg = hg
        g.fg = fg
        if (g.block, g.name) in orig_meta:
            g.meta = orig_meta[(g.block, g.name)]

    os.chdir(original_dir)
    return auto_gs


def get_pi_delg(geners, pr_filename, sav_filename, max_steam=20.0):
    """ Using AUTOUGH2's .autogeners to get PIs for DELG/DMAK generators.

    TOUGH2 input file name expected here instead of t2data object because we
    want to open a new instance of t2data for temporary use, just to avoid
    potential confusing with whatever that is passed in.
    """

    orig_types = [g.type for g in geners]
    orig_fgs = [g.fg for g in geners]
    tmp = t2data(pr_filename)
    tmp.clear_generators()
    tmp.parameter['max_timesteps'] = 1
    for g in geners:
        # g.type = 'DELG'
        tmp.add_generator(g)
    sav = t2incon(sav_filename)

    TMPDIR = 'tmp_get_pi_delg'
    if not os.path.isdir(TMPDIR):
        os.mkdir(TMPDIR)
    # for f in copy_files:
    #     shutil.copy2(f, TMPDIR)
    original_dir = os.getcwd()
    os.chdir(TMPDIR)

    # ---
    tmp.write('tmp.dat')
    sav.write('tmp.incon', reset=True)
    tmp.run(save_filename='tmp.save',
            incon_filename='tmp.incon',
            simulator=AUT2,
            silent=True)
    auto_gs = read_gener_file('tmp.autogeners')
    lst = None
    if max_steam is None:
        lst = t2listing('tmp.listing')
    for g,t,fg in zip(auto_gs, orig_types, orig_fgs):
        if g.gx == 0.0:
            print('*** %s:%s possibly pressure too low to flow, reset PI' % (g.block, g.name))
            g.gx = 1.0e-11
        if lst is not None:
            max_steam = lst.generation[(g.block, g.name)]['Steam sepa.']
        else:
            pass
        g.type = t
        g.hg = max_steam
        g.fg = fg

    os.chdir(original_dir)
    return auto_gs


def get_max_steam_delg(geners, pr_filename, sav_filename, max_steam=20.0,
                       large_pi=1.0e-10):
    """ use steam separation from listing gener tables to cap DMAK/DELGs

    Combined with a reasonably large PI, this can 'throttle' an actually more
    productive DMAK at a lower initial rate.

    If large_pi is set to None, then the original PI will be preserved.  Be
    careful this will mean the well's initial flowrate to be determined by both
    PI as well as steam cap!

    TOUGH2 input file name expected here instead of t2data object because we
    want to open a new instance of t2data for temporary use, just to avoid
    potential confusing with whatever that is passed in.
    """
    orig_types = [g.type for g in geners]
    orig_fgs = [g.fg for g in geners]
    tmp = t2data(pr_filename)
    tmp.clear_generators()
    tmp.parameter['max_timesteps'] = 1
    for g in geners:
        # g.type = 'DELG'
        tmp.add_generator(g)
    sav = t2incon(sav_filename)

    TMPDIR = 'tmp_get_max_steam_delg'
    if not os.path.isdir(TMPDIR):
        os.mkdir(TMPDIR)
    # for f in copy_files:
    #     shutil.copy2(f, TMPDIR)
    original_dir = os.getcwd()
    os.chdir(TMPDIR)

    # ---
    tmp.write('tmp.dat')
    sav.write('tmp.incon', reset=True)
    tmp.run(save_filename='tmp.save',
            incon_filename='tmp.incon',
            simulator=AUT2,
            silent=True)
    auto_gs = read_gener_file('tmp.autogeners')
    lst = t2listing('tmp.listing')
    for g,t,fg in zip(auto_gs, orig_types, orig_fgs):
        g.gx = large_pi
        steam = lst.generation[(g.block, g.name)]['Steam sepa.']
        if steam == 0.0:
            print('*** %s:%s possibly pressure too low to flow, use default steam max' % (g.block, g.name))
            steam = max_steam
        g.type = t
        g.hg = steam
        g.fg = fg

    os.chdir(original_dir)
    return auto_gs








