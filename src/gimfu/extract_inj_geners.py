from t2listing import *
from t2data import *

from gimfu.t2listingh5 import t2listingh5

from gimfu.multiple_listings_plotting import get_block_history
from gimfu.multiple_listings_plotting import get_gener_history
from gimfu.scenario_extraction import external_name

import os
import glob
import re
import json
from copy import deepcopy

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import xlwt


def normalname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    is_match = True
    for i in xrange(5):
        if name_wc[i] != '*':
            if name_wc[i] != name[i]:
                is_match = False
                break
    return is_match


def to_kjkg(xs):
    return [x/1000. for x in xs]

def to_bar(xs):
    return [x/1.e5 for x in xs]

def to_year(xs,start_year=0.0):
    sec_in_year = 60. * 60. * 24. * 365.25
    return [x / sec_in_year + start_year for x in xs]

def to_tday(xs):
    return [x * 86.4 for x in xs]

def to_tday_rev(xs):
    return [-x * 86.4 for x in xs]

def plot_inj_geners(sdir, scenario_name, block_name, gener_name):
    FIGURE_DIR = 'non_standatd_figures'
    if not os.path.exists(FIGURE_DIR):
        os.makedirs(FIGURE_DIR)

    sname = scenario_name
    out_fname = 'inj_%s' % sname.replace('/', '_').replace('\\', '_')
    lst_fnames = sorted(glob.glob('%s/wai*.h5' % sdir))
    dat_fnames = [fn.replace('.h5', '.dat') for fn in lst_fnames]

    lsts, dats = [], []
    print('found listing files:')
    for flst,fdat in zip(lst_fnames, dat_fnames):
        print('    loading %s, %s ...' % (flst, fdat))
        lsts.append(t2listingh5(flst))
        dats.append(t2data(fdat))

    bname, gname = block_name, gener_name
    rebn, regn = re.compile(bname), re.compile(gname)
    columns =  ['Generation rate']
    units =    ['t/day']
    converts = [to_tday]
    tbl,bgcs = get_gener_history(bname, gname, lsts, cols=columns)

    # collect gener info from t2data, and fake it into time series as from lst
    # collect place holder first: all matching gners from all dats
    imak_pcutoff = {}
    for dat in dats:
        for g in dat.generatorlist:
            if re.match(rebn, g.block) and re.match(regn, g.name) and g.type == 'IMAK':
                gid = (g.block, g.name)
                if gid not in imak_pcutoff:
                        imak_pcutoff[gid] = []
    for dat, lst in zip(dats, lsts):
        pcutoff = {}
        for i,g in enumerate(dat.generatorlist):
            if re.match(rebn, g.block) and re.match(regn, g.name) and g.type == 'IMAK':
                pcutoff[(g.block, g.name)] = g.hg
        for gid in imak_pcutoff:
            # use value if gener in this dat, otherwise use 0.0
            if gid in pcutoff:
                imak_pcutoff[gid] += [pcutoff[gid]] * lst.num_fulltimes
            else:
                imak_pcutoff[gid] += [0.0] * lst.num_fulltimes


    wb = xlwt.Workbook()
    ws = wb.add_sheet('injection well blocks')
    for ii,(b,g,c) in enumerate(bgcs):
        # TIMES
        ofsx = ii * 2 # X
        ofsy = 0      # Y
        ws.write(ofsx, ofsy, b)
        ws.write(ofsx, ofsy+1, g)
        ws.write(ofsx, ofsy+2, 'Times (year)')
        values = to_year(tbl[(b,g,c)][0], start_year=1953.0)
        for jj,v in enumerate(values):
            ws.write(ofsx, 3+jj, v)
        for cn,u,fc in zip(columns, units, converts):
            # MASS etc
            ofsx += 1 # X
            ws.write(ofsx, ofsy, b)
            ws.write(ofsx, ofsy+1, g)
            ws.write(ofsx, ofsy+2, '%s (%s)' % (cn,u))
            values = fc(tbl[(b,g,c)][1])
            for jj,v in enumerate(values):
                ws.write(ofsx, 3+jj, v)
    wb.save(out_fname + '.xls')

    # get pressure for the blocks
    blocklist = list(set([b for b,g,c in bgcs]))
    columns = ['Pressure']
    ptbl,bcs = get_block_history(blocklist, lsts, cols=columns)

    pdf_pages = PdfPages('figs_%s.pdf' % out_fname)

    bgs = []
    for b,g,c in bgcs:
        if (b,g) not in bgs:
            bgs.append((b,g))

    for b,g in bgs:
        fig = plt.figure(figsize=(16.0,10.0))

        fig.add_subplot(221)
        xs = to_year(tbl[(b,g,'Generation rate')][0], start_year=1953.0)
        ys = to_tday(tbl[(b,g,'Generation rate')][1])
        plt.plot(xs, ys)
        plt.xlabel('Year')
        plt.ylabel('Mass Flow Rate (t/day)')
        plt.title('Generator (%s,%s)' % (b,g))
        plt.grid(True)

        fig.add_subplot(222)
        xs = to_year(ptbl[b, 'Pressure'][0], start_year=1953.0)
        ys = to_bar(ptbl[b, 'Pressure'][1])
        plt.plot(xs, ys)
        cutoff = to_bar(imak_pcutoff[(b,g)])
        plt.plot(xs, cutoff)
        plt.xlabel('Year')
        plt.ylabel('Pressure (bar)')
        plt.title('Block %s' % b)
        plt.grid(True)

        fig.add_subplot(223)
        plt.axis([0, 10, 0, 10])
        ss = '\n'.join([s for s in lst_fnames])
        plt.text(5, 5, ss, ha='center', va='center', wrap=True)
        plt.grid(False)

        pdf_pages.savefig(fig)
        plt.close(fig)

    pdf_pages.close()

def main():
    with open('settings.json', 'r') as f:
        cfg = json.load(f)

    bname, gname = cfg['injection']['block'], cfg['injection']['gener']
    for sdir in cfg['dir_to_extract']:
        # use basename (the last part of the the normalized path) as sname
        sname = os.path.basename(os.path.normpath(sdir))
        sname = external_name(cfg, sname)
        print("Extracting scenario '%s' from directory: %s" % (sname, sdir))

        plot_inj_geners(sdir, sname, bname, gname)

    return 0

if __name__ == '__main__':
    exit(main())
