from t2listing import *
from t2data import *

from gimfu.t2listingh5 import t2listingh5

from gimfu.multiple_listings_plotting import get_block_history
from gimfu.multiple_listings_plotting import get_gener_history
from gimfu.scenario_extraction import external_name

import re
import os
import glob
import json
from copy import deepcopy
from pprint import pprint as pp
import pickle
import numpy as np

import xlwt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def normalname_match(name_wc, name):
    """ return true if the name_wc (wild cast * supported) match name """
    is_match = True
    for i in range(5):
        if name_wc[i] != '*':
            if name_wc[i] != name[i]:
                is_match = False
                break
    return is_match

def get_gener_curve(bname,gname,dat):
    for g in dat.generatorlist:
        if g.name == gname and g.block == bname:
            if abs(g.ltab) > 1:
                enth = g.time
                pcut = g.rate
                return enth,pcut

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

def to_thr(xs):
    return [x * 3.6 for x in xs]

def to_thr_rev(xs):
    return [-x * 3.6 for x in xs]

def to_MJday_rev(xs):
    # production heatflow -J/s to MJ/day
    return [-x * 60.*60.*24./1.0e6 for x in xs]

def to_tdaybar(xs):
    # deliverability terms (mobility-density-PI)
    # kg/s/Pa to t/day/bar
    return [x * 60.*60.*24.*1.e5/1.e3 for x in xs]


def gener_pdf(pdf_pages, gener_hist, block_hist, datgen_hist, notes=''):
    """ plot history of gener on deliverability into a pdf file

    If notes is a string then it will be printed on all pages, if notes is a
    dict with (block, gener) as key, then each page can have its own notes.

    - each figure/page is a single generator
    - each page contains sub figures:
        + Pcutoff curve, wellbore pressu vs. enthalpy
        + notes
        + reservoir pressure history and Pcutoff
        + enthalpy history
        + massflow history
        + steamflow history
    """
    raise NotImplementedError

def plot_prd_geners(pdf_fname, bns_gns, gener_hist, block_hist, datgen_hist, curves, notes=""):
    FIGURE_DIR = 'non_standatd_figures'
    if not os.path.exists(FIGURE_DIR):
        os.makedirs(FIGURE_DIR)
    pdf_pages = PdfPages(pdf_fname)
    for bn,gn in bns_gns:
        curve_x, curve_y = curves[(bn,gn)]

        ts = gener_hist[(bn, gn, 'Enthalpy')][0]
        gx = gener_hist[(bn, gn, 'Enthalpy')][1]
        gy = block_hist[(bn, 'Pressure')][1]
        mass = gener_hist[(bn, gn, 'Generation rate')][1]
        steam = gener_hist[(bn, gn, 'Steam sepa.')][1]
        cap = datgen_hist[(bn, gn, 'Mass Cap')]
        reqps = gener_hist[(bn, gn, 'Wellbore pressure')][1]


        curve_x, curve_y = to_kjkg(curve_x), to_bar(curve_y)
        gx, gy = to_kjkg(gx), to_bar(gy)
        reqps = to_bar(reqps)
        ts = to_year(ts,1953.0)
        mass, steam = to_thr_rev(mass), to_thr(steam)
        cap = to_thr(cap)

        fig = plt.figure(figsize=(16.0,10.0))

        fig.add_subplot(321)
        plt.plot(gx,gy,'.-')
        plt.plot(curve_x, curve_y,'.-')
        plt.plot(gx[0],gy[0],'ro')
        plt.xlabel('Enthalpy (kJ/kg)')
        plt.ylabel('Pressure (bara)')
        plt.ylim(0.0,220.0)
        plt.xlim(750.0,3000.0)
        plt.grid(True)
        plt.legend(labels=['Actual','Delv. curve'],loc='upper right')
        plt.title('Pcutoff Curve (%s,%s)' % (bn,gn))

        fig.add_subplot(322)
        plt.axis([0, 10, 0, 10])
        plt.text(5, 5, notes, ha='center', va='center', wrap=True)

        fig.add_subplot(323)
        plt.plot(ts, gy,'.-')
        plt.plot(ts, reqps,'.-')
        plt.plot(ts[0],gy[0],'ro')
        plt.xlabel('Year')
        plt.ylabel('Pressure (bar)')
        plt.legend(labels=['Actual','Pcutoff'],loc='upper right')
        plt.grid(True)

        fig.add_subplot(324)
        plt.plot(ts, gx,'.-')
        plt.plot(ts[0],gx[0],'ro')
        plt.xlabel('Year')
        plt.ylabel('Enthalpy (kJ/kg)')
        plt.grid(True)

        fig.add_subplot(325)
        plt.plot(ts,mass,'.-')
        plt.plot(ts,cap, '.--')
        plt.plot(ts[0],mass[0],'ro')
        plt.xlabel('Year')
        plt.ylabel('Mass Flow Rate (t/hr)')
        plt.grid(True)

        fig.add_subplot(326)
        plt.plot(ts,steam,'.-')
        plt.plot(ts[0],steam[0],'ro')
        plt.xlabel('Year')
        plt.ylabel('Steam Flow Rate (t/hr)')
        plt.grid(True)

        # plt.savefig(FIGURE_DIR+'/'+gn+'.png')
        #orientation='portrait', papertype='a4'
        pdf_pages.savefig(fig)
        plt.close(fig)
    pdf_pages.close()

def export_prd_geners(xls_fname, bns_gns, gener_hist, block_hist, datgen_hist, curves):
    if not bns_gns:
        print('export_prd_geners(): No matched geners found, do nothing.')
        return
    wb = xlwt.Workbook()
    ws = wb.add_sheet('production blocks')
    # plot one by one
    for ii,(bn,gn) in enumerate(bns_gns):
        # time, massflow, enthalpy, pressure, steamflow
        ts = gener_hist[(bn, gn, 'Enthalpy')][0]
        fs = gener_hist[(bn, gn, 'Generation rate')][1]
        es = gener_hist[(bn, gn, 'Enthalpy')][1]
        ps = block_hist[(bn, 'Pressure')][1]
        ss = gener_hist[(bn, gn, 'Steam sepa.')][1]
        pws = gener_hist[(bn, gn, 'Wellbore pressure')][1]
        dvs = gener_hist[(bn, gn, 'Deliverability')][1]
        cs = datgen_hist[(bn, gn, 'Mass Cap')]


        # calc heatflow kg/s * J/kg = J/s -> * 60*60*24/1e6 = MJ/day
        hs = [f*e for f,e in zip(fs,es)]
        hs = to_MJday_rev(hs)
        ts = to_year(ts,1953.0)
        fs = to_tday_rev(fs)
        cs = to_tday(cs)
        es = to_kjkg(es)
        ps = to_bar(ps)
        ss = to_tday(ss)
        pws = to_bar(pws)
        dvs = to_tdaybar(dvs)

        ofsx = ii * 8 # X, ii * number of variables
        ofsy = 0   # Y
        # TIMES
        # print(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Times (year)')
        for jj,v in enumerate(ts):
            ws.write(ofsx, 3+jj, v)
        # MASS
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Massflow (t/day)')
        for jj,v in enumerate(fs):
            ws.write(ofsx, 3+jj, v)
        # ENTH
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Enthalpy (kJ/kg)')
        for jj,v in enumerate(es):
            ws.write(ofsx, 3+jj, v)
        # HEAT
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Heatflow (MJ/day)')
        for jj,v in enumerate(hs):
            ws.write(ofsx, 3+jj, v)
        # PRESSURE
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Pressure (bar)')
        for jj,v in enumerate(ps):
            ws.write(ofsx, 3+jj, v)
        # WELLBORE PRESSURE
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Wellbore Pressure (bar)')
        for jj,v in enumerate(pws):
            ws.write(ofsx, 3+jj, v)
        # DELIVERABILITY
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Deliverability (t/day/bar)')
        for jj,v in enumerate(dvs):
            ws.write(ofsx, 3+jj, v)
        # MASS CAP
        ofsx += 1 # X
        ws.write(ofsx, ofsy, bn)
        ws.write(ofsx, ofsy+1, gn)
        ws.write(ofsx, ofsy+2, 'Massflow Cap (t/day)')
        for jj,v in enumerate(cs):
            ws.write(ofsx, 3+jj, v)
    # save exported xls
    wb.save(xls_fname)


def export_prd_geners_flat(xls_fname, bns_gns, gener_hist, block_hist, datgen_hist):
    if not bns_gns:
        print('export_prd_geners_flat(): No matched geners found, do nothing.')
        return
    # flat xls
    wb = xlwt.Workbook()
    ws = wb.add_sheet('production blocks')

    ofsx = 0
    ofsy = 0   # Y
    ws.write(ofsx, ofsy, 'Times (year)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Block'); ofsy += 1
    ws.write(ofsx, ofsy, 'Gener'); ofsy += 1
    ws.write(ofsx, ofsy, 'Massflow (t/day)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Enthalpy (kJ/kg)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Heatflow (MJ/day)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Pressure (bar)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Wellbore Pressure (bar)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Deliverability (t/day/bar)'); ofsy += 1
    ws.write(ofsx, ofsy, 'Massflow Cap (t/day)'); ofsy += 1

    # plot one by one
    for ii,(bn,gn) in enumerate(bns_gns):
        # time, massflow, enthalpy, pressure, steamflow
        ts = gener_hist[(bn, gn, 'Enthalpy')][0]
        fs = gener_hist[(bn, gn, 'Generation rate')][1]
        es = gener_hist[(bn, gn, 'Enthalpy')][1]
        ps = block_hist[(bn, 'Pressure')][1]
        ss = gener_hist[(bn, gn, 'Steam sepa.')][1]
        pws = gener_hist[(bn, gn, 'Wellbore pressure')][1]
        dvs = gener_hist[(bn, gn, 'Deliverability')][1]
        cs = datgen_hist[(bn, gn, 'Mass Cap')]

        # calc heatflow kg/s * J/kg = J/s -> * 60*60*24/1e6 = MJ/day
        hs = [f*e for f,e in zip(fs,es)]
        hs = to_MJday_rev(hs)
        ts = to_year(ts,1953.0)
        fs = to_tday_rev(fs)
        cs = to_tday(cs)
        es = to_kjkg(es)
        ps = to_bar(ps)
        ss = to_tday(ss)
        pws = to_bar(pws)
        dvs = to_tdaybar(dvs)
        for time, mass, enth, heat, pres, pwb, delv, cap in zip(ts, fs, es, hs, ps, pws, dvs, cs):
            ofsx += 1
            ofsy = 0   # Y
            ws.write(ofsx, ofsy, time); ofsy += 1
            ws.write(ofsx, ofsy, bn); ofsy += 1
            ws.write(ofsx, ofsy, gn); ofsy += 1
            ws.write(ofsx, ofsy, mass); ofsy += 1
            ws.write(ofsx, ofsy, enth); ofsy += 1
            ws.write(ofsx, ofsy, heat); ofsy += 1
            ws.write(ofsx, ofsy, pres); ofsy += 1
            ws.write(ofsx, ofsy, pwb); ofsy += 1
            ws.write(ofsx, ofsy, delv); ofsy += 1
            ws.write(ofsx, ofsy, cap); ofsy += 1
    # save exported xls
    wb.save(xls_fname)


def main_(sdir, sname, block_name, gener_name):
    MAKE_PLOTS = True
    MAKE_XLS = True
    MAKE_XLS_FLAT = True

    flsts = sorted(glob.glob('%s/wai*.h5' % sdir))
    fdats = [fn.replace('.h5', '.dat') for fn in flsts]
    out_fname = 'prd_%s' % sname
    cache_fname = '_extract_prd_geners_%s.pkl' % sname
    use_cache = False
    if os.path.exists(cache_fname):
        ans = input('Cache file %s exists. Use it? (y/n) ' % cache_fname)
        if ans.lower() == 'y':
            use_cache = True

    if use_cache:
        print(f'Loading from cache {cache_fname} ...')
        with open(cache_fname, 'rb') as f:
            bns_gns, gener_hist, block_hist, datgen_hist, curves, lst_fulltimes = pickle.load(f)
    else:
        print(f'Loading {len(flsts)} model results...')
        lsts = [t2listingh5(fn) for fn in flsts]
        print(f"Loading {len(fdats)} dat files...")
        dats = [t2data(fn) for fn in fdats]

        # fulltimes for each lst
        lst_fulltimes = [lst.fulltimes for lst in lsts]

        # find all matching generators
        # collect Pcutoff curves
        rebn, regn = re.compile(block_name), re.compile(gener_name)
        bns_gns = []
        curves = {}
        for dat in dats:
            print('  in dat file %s' % dat.filename)
            for g in dat.generatorlist:
                if re.match(rebn, g.block) and re.match(regn, g.name):
                    if (g.block,g.name) not in bns_gns:
                        bns_gns.append((g.block,g.name))
                        if abs(g.ltab) > 1:
                            # g.time is enthalpy, g.rate is Pcutoff
                            curves[(g.block,g.name)] = (g.time, g.rate)

        variables = ['Generation rate', 'Enthalpy', 'Steam sepa.', 'Wellbore pressure', 'Deliverability']
        gener_hist, gener_bgcns = get_gener_history([b for b,g in bns_gns],
                                                    [g for b,g in bns_gns],
                                                    lsts, cols=variables,
                                                    silent=False)

        blocks = list(set([b for b,g,cn in gener_bgcns]))
        block_hist, block_bcns = get_block_history(blocks, lsts, ['Pressure'])

        # compute the *fake* history of g.hg
        def get_gen_data(gen=None, dname=None):
            d = {
                'Mass Cap': 'hg',
            }
            if dname is None:
                return d.keys()
            else:
                return getattr(gen, d[dname])
        g_dnames = get_gen_data()
        datgen_hist = {}
        for dat,ts in zip(dats,lst_fulltimes):
            vs = {}
            for bn,gn in bns_gns:
                for cn in g_dnames:
                    value = 0.0
                    if (bn,gn) in dat.generator:
                        gen = dat.generator[(bn,gn)]
                        if gen.type in ['DMAT']:
                            value = get_gen_data(gen, cn)
                    if (bn,gn,cn) not in datgen_hist:
                        datgen_hist[(bn,gn,cn)] = np.array([], dtype=np.float64)
                    datgen_hist[(bn,gn,cn)] = np.concatenate((datgen_hist[(bn,gn,cn)],
                                                              np.ones_like(ts) * value))

        with open(cache_fname, 'wb') as f:
            print(f"Writing/overwriting cache file {cache_fname} ...")
            pickle.dump([bns_gns, gener_hist, block_hist, datgen_hist, curves, lst_fulltimes], f)


    if MAKE_PLOTS:
        print(f"Plotting ...")
        plot_prd_geners('figs_%s.pdf' % out_fname,
            bns_gns, gener_hist, block_hist, datgen_hist, curves,
            notes="\n".join(flsts))

    if MAKE_XLS:
        print(f"Exporting ...")
        export_prd_geners('%s.xls' % out_fname,
            bns_gns, gener_hist, block_hist, datgen_hist, curves)

    if MAKE_XLS_FLAT:
        print(f"Exporting (flat) ...")
        export_prd_geners_flat('%s_flat.xls' % out_fname,
            bns_gns, gener_hist, block_hist, datgen_hist)

def main():
    with open('settings.json', 'r') as f:
        cfg = json.load(f)

    bname, gname = cfg['production']['block'], cfg['production']['gener']
    for sdir in cfg['dir_to_extract']:
        # use basename (the last part of the the normalized path) as sname
        sname = os.path.basename(os.path.normpath(sdir))
        sname = external_name(cfg, sname)
        print("Extracting scenario '%s' from directory: %s" % (sname, sdir))

        main_(sdir, sname, bname, gname)

    print("Done.")
    return 0

if __name__ == '__main__':
    exit(main())

