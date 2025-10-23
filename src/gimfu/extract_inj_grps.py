""" plot massflow and enthalpy of generators by groups.

Massflow will be stacked within a group.  An average enthalpy will be included
for each group.

Expects 'settings.json' file whereever this script is launched.  It should look
something like this:

{
    "external_scenario_names": {
        "s3A"   : "s3A"   ,
        "s3B"   : "s3B"   ,
        "s4A"   : "s4A"   ,
        "s4A1"  : "s4A1"  ,
        "s4A2"  : "s4A2"  ,
        "s4C"   : "s4C"
    },
    "use_spec_json": true,
    "dir_to_extract" : [
        "../s3A-V78",
        "../s3A2-V78",
        "../s3Ab-V78",
        "../s3Ac-V78"
    ],
    "production": {
        "block": ".....",
        "gener": "(MT|MW|ET|EW)..."
    },
    "injection": {
        "block": ".....",
        "gener": "(I[ABCD]|HI)..."
    }
}

"""


from t2data import *

from gimfu.t2listingh5 import t2listingh5

from gimfu.scenario_extraction import external_name
from gimfu.scenario_extraction import average_enthalpy
from gimfu.scenario_extraction import matching_geners_from_lsts
from gimfu.scenario_extraction import to_year, to_kjkg
from gimfu.scenario_extraction import to_thr_rev, to_ktd_rev, to_thr, to_ktd
from gimfu.scenario_extraction import assign_kgs, assign_jkg, assign_sec
from gimfu.multiple_listings_plotting import get_gener_history
from gimfu.scenario_spec_report import collate_well_stacks

import json
import csv
import glob
import re
import os
import os.path
import pickle
from pprint import pprint as pp
from functools import partial

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from cycler import cycler

import numpy as np

# plt.style.use("seaborn-v0_8-dark")
mpl.rcParams['axes.formatter.useoffset'] = False
colors = np.vstack([
    plt.cm.Set1.colors,
    plt.cm.Set2.colors,
    plt.cm.Set3.colors,
    # plt.cm.Pastel1.colors,
    # plt.cm.Pastel2.colors,
    plt.cm.tab20b.colors,
    plt.cm.tab20.colors,
    # plt.cm.tab20c.colors
])
mpl.rcParams["axes.prop_cycle"] = cycler(color=colors)


def grouping_from_spec(spec_json):
    """ returns a grouping dict based on the spec.

        Basically reverse of the well_geners from collate_well_stacks().
        grouping is a dict {(block, gener): 'GRP NAME', ...}
    """
    stacks, wells = collate_well_stacks(spec_json)
    grouping = {}
    for well, bgs in wells.items():
        for block,gener in bgs:
            if (block,gener) in grouping:
                if well != grouping[(block,gener)]:
                    err = 'Spec %s a gener (%s,%s) is associated ' \
                          'with diff wells: %s != %s' % (fspec,
                          block, gener, grouping[(block,gener)], well)
                    raise Exception(err)
            grouping[(block,gener)] = well
    return grouping

def grouping_by_gener_name(bgs, alias={}):
    new_grps = {}
    for bg in bgs:
        new_grps[bg] = alias.get(bg[1], bg[1])
    return new_grps

def default_grouping(bgs, custom_grouping=None):
    """ given a list of (block, gener), automatically returns grouping, which is
        a dict {(block, gener): 'GRP NAME', ...}

    custom_grouping can be specified, eg.
        {
            "dry1": ["WK234", "WK238", "WK240", ...],
            "dry2": ["WK236", "WK216", "WK118", ...],
            ...
        }
    """
    specified = {}
    if custom_grouping:
        for gg, bb in custom_grouping.items():
            for b in bb:
                if b in specified:
                    err = 'Custom grouping has (%s) in two groups: %s and %s' % (
                        b, specified[b], gg)
                    raise Exception(err)
                specified[b] = gg

    delimiter = '-'
    group_by_first_n_chars = 2
    grouping = {}
    for bg in bgs:
        use_key = bg
        if isinstance(bg, tuple):
            use_key = bg[1]
        if bg in specified:
            grp = specified[bg]
        elif '-' in use_key:
            grp = use_key.split('-')[0]
        else:
            grp = use_key[:group_by_first_n_chars]
        grouping[bg] = grp
    return grouping

def plot_mass_enth_groups(pdf_pages, times,
                          grouped_mass, grouped_enth, grouped_tags,
                          title_prefix='',
                          to_mass_unit=assign_kgs,
                          to_enth_unit=assign_jkg,
                          to_time_unit=assign_sec):

    MAX_N_LEGENDS = 50
    MIN_RANGE_ENTH = 40.0
    # _nu is in new unit
    times_nu, time_lbl = to_time_unit(times)

    return_mass, return_enth = {}, {} # in original unit
    for grp in grouped_mass.keys():
        if len(grouped_mass[grp]) == 0:
            continue
        total_mass, avg_enth = average_enthalpy(grouped_mass[grp], grouped_enth[grp])
        return_mass[grp] = total_mass
        return_enth[grp] = avg_enth

        all_mass_nu = [to_mass_unit(m)[0] for m in grouped_mass[grp][::-1]]
        all_enth_nu = [to_enth_unit(e)[0] for e in grouped_enth[grp][::-1]]
        avg_enth, enth_lbl = to_enth_unit(avg_enth)
        total_mass, mass_lbl = to_mass_unit(total_mass)

        fig, (ax1, ax2) = plt.subplots(2,1, sharex=True)
        # ax3.get_shared_x_axes().join(ax2, ax3)
        fig.set_figwidth(8.5)
        fig.set_figheight(13)

        ax1.set_title('%s Group %s' % (title_prefix, grp))
        # ax1.axis([0, 10, 0, 10])
        # ax1.text(5, 5, '\n'.join(grouped_tags[grp]), ha='center', va='center', wrap=True)
        # ax1.tick_params(left=False, right=False, bottom=False,
        #                 labelleft=False, labelbottom = False)

        ax1.stackplot(times_nu, np.array(all_mass_nu), labels=grouped_tags[grp][::-1])
        box = ax1.get_position()
        ax1.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        handles, labels = ax1.get_legend_handles_labels()
        leg = ax1.legend(handles[::-1][:MAX_N_LEGENDS+1],
                         labels[::-1][:MAX_N_LEGENDS]+['...'],
                         loc="center left",
                         bbox_to_anchor=(1, -0.1)) # loc='upper left'
        # leg = ax1.legend(handles[::-1], labels[::-1]) # loc='upper left'
        # leg.draggable()
        # reverse=True, requires matplotlib >= 3.7
        ax1.set_ylabel('Massflow (%s)' % mass_lbl)
        ax1.grid(True)

        for gen,enth in zip(grouped_tags[grp], all_enth_nu):
            ax2.plot(times_nu, enth)
        if len(grouped_tags[grp]) > 1:
            ax2.plot(times_nu, avg_enth, 'ko:', label='Average')
            ax2.legend()
        try:
            # new lim based on nonzeros
            all_enth_nu = np.array(all_enth_nu)
            all_enth_nz = all_enth_nu[np.nonzero(all_enth_nu)]
            minval = np.min(all_enth_nz)
            maxval = np.max(all_enth_nz)
            margin = max((maxval-minval) * 0.10, MIN_RANGE_ENTH / 2.0)
            ax2.set_ylim(minval-margin, maxval+margin)
            # ax2.margins(y=0.1)
        except ValueError:
            # means no non-zero values at all?
            pass
        box = ax2.get_position()
        ax2.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        ax2.set_ylabel('Enthalpy (%s)' % enth_lbl)
        ax2.set_xlabel('Time (%s)' % time_lbl)
        ax2.grid(True)

        # plt.show()
        pdf_pages.savefig(fig)
        plt.close(fig)
        fig.clear()
    return return_mass, return_enth

def group_mass_enth(grouping, mass, enth, tag=str, custom_sort_key=sorted):
    """ returns grouped mass/enth/names by following grouping, a dict with the
        same keys of mass and enth.

        tag is a function that creates a string from each name.  custom_sort_key
        is a func that can be specified to order how tags appear within each
        group.
    """
    if isinstance(custom_sort_key, list):
        def order():
            for n in custom_sort_key:
                yield n
    else:
        def order():
            for n in custom_sort_key(mass.keys()):
                yield n
    grouped_mass, grouped_enth = {}, {}
    grouped_tags = {}
    for name in order():
        # grp = grouping[name]
        grp = grouping.get(name, None)
        if grp is None:
            print("Skipping (%s, %s), does not have group." % name)
        if grp not in grouped_mass:
            grouped_mass[grp] = []
            grouped_enth[grp] = []
            grouped_tags[grp] = []
        grouped_mass[grp].append(mass[name])
        grouped_enth[grp].append(enth[name])
        grouped_tags[grp].append(tag(name))
    return grouped_mass, grouped_enth, grouped_tags


def main():
    with open('settings.json', 'r') as f:
        cfg = json.load(f)

    match_block, match_gener = cfg['injection']['block'], cfg['injection']['gener']
    rebn, regn = re.compile(match_block), re.compile(match_gener)
    use_spec = False
    if 'use_spec_json' in cfg:
        use_spec = cfg['use_spec_json']
    gener_alias = cfg.get('gener_alias', {})
    custom_grouping = cfg.get('custom_grouping', {})

    MASSNAME, ENTHNAME = 'Generation rate', 'Enthalpy'

    for sdir in cfg['dir_to_extract']:
        spec_filename = os.path.join(sdir, 'scenario_spec.json')
        if use_spec and os.path.isfile(spec_filename):
            with open(spec_filename, 'r') as f:
                spec_json = json.load(f)
            flsts = [os.path.join(sdir, sim['filename']+'.h5') for sim in spec_json['simulations']]
            fdats = [os.path.join(sdir, sim['filename']+'.dat') for sim in spec_json['simulations']]
            offset_year = spec_json['date_offset']
            print('Found optional spec %s, plot spec based grouping.' % spec_filename)
            use_spec = True
            output_postfix = '_spec'
        else:
            flsts = sorted(glob.glob('%s/wai*.h5' % sdir))
            fdats = [fn.replace('.h5', '.dat') for fn in flsts]
            offset_year = 0.0
            use_spec = False
            output_postfix = '_gengrp'

        # use basename (the last part of the the normalized path) as sname
        sname = os.path.basename(os.path.normpath(sdir))
        sname = external_name(cfg, sname)
        print("Extracting scenario '%s' from directory: %s" % (sname, sdir))

        fname_pdf = 'figs_inj_%s%s.pdf' % (sname, output_postfix)
        fname_cache = '_extract_inj_grps_%s%s.pkl' % (sname, output_postfix)


        use_cache = False
        if os.path.exists(fname_cache):
            ans = input('Cache file for %s exists. Use it? (y/n) ' % sname)
            if ans.lower().startswith('y'):
                use_cache = True

        if use_cache:
            print('Loading cached data from %s' % fname_cache)
            with open(fname_cache, 'rb') as f:
                gener_hist, bns_gns = pickle.load(f)
        else:
            print('Extracting from listings for %s...' % sname)
            lsts = [t2listingh5(fn) for fn in flsts]
            bns_gns = matching_geners_from_lsts(lsts, rebn, regn)
            if bns_gns:
                gener_hist, _ = get_gener_history(
                    [b for b,g in bns_gns], [g for b,g in bns_gns],
                    lsts, cols=[MASSNAME, ENTHNAME], silent=True)
            else:
                gener_hist, bns_gns = {}, []

            if not gener_hist:
                print("No generators found for %s. Skipping." % sname)
                continue

            print('Saving cache to %s' % fname_cache)
            with open(fname_cache, 'wb') as f:
                pickle.dump((gener_hist, bns_gns), f)

        print('    Extracted/Loaded %d generators for %s.' % (len(bns_gns), sname))

        b, g = bns_gns[0]
        times = gener_hist[(b, g, MASSNAME)][0]

        grp_total_mass = {(b,g): gener_hist[(b, g, MASSNAME)][1] for b,g in bns_gns}
        grp_total_enth = {(b,g): gener_hist[(b, g, ENTHNAME)][1] for b,g in bns_gns}

        # each set of plots requires the following four settings
        # grouping, tag, sort, mass unit

        pdf_pages = PdfPages(fname_pdf)

        orig_mass, orig_enth = grp_total_mass, grp_total_enth
        grouping = grouping_by_gener_name(bns_gns, alias=gener_alias)
        from pprint import pprint
        print('<<<<< use gener name >>>>>')
        # pprint(bns_gns)
        # for x,y in grouping.items():
        #     print(f"{x} :: {y}")

        def gener2tag(gen_key):
            return '(%s,%s)' % gen_key
        grouped_mass, grouped_enth, grouped_tags = group_mass_enth(
            grouping, orig_mass, orig_enth,
            tag=gener2tag, # cleaner of gener name: (bname,gname)
            custom_sort_key=bns_gns, # follow order of original list
            )
        grp_total_mass, grp_total_enth = plot_mass_enth_groups(
            pdf_pages, times,
            grouped_mass, grouped_enth, grouped_tags,
            title_prefix=sname,
            to_mass_unit=to_thr,
            to_enth_unit=to_kjkg,
            to_time_unit=partial(to_year, start_year=offset_year),
            )
        print('    Grouped by gener name DONE.')

        # standard set of plots
        orig_mass, orig_enth = grp_total_mass, grp_total_enth
        grouping = default_grouping(list(grp_total_mass.keys()), custom_grouping=custom_grouping)
        print('<<<<< standard set >>>>>')
        # pprint(grouping)
        grouped_mass, grouped_enth, grouped_tags = group_mass_enth(
            grouping, orig_mass, orig_enth,
            tag=str,
            custom_sort_key=sorted,
            )
        grp_total_mass, grp_total_enth = plot_mass_enth_groups(
            pdf_pages, times,
            grouped_mass, grouped_enth, grouped_tags,
            title_prefix=sname,
            to_mass_unit=to_ktd,
            to_enth_unit=to_kjkg,
            to_time_unit=partial(to_year, start_year=offset_year),
            )
        print('    Standard groups DONE.')

        # # final single group contains everything
        # orig_mass, orig_enth = grp_total_mass, grp_total_enth
        # grouping = {k: "All Geners: '%s'" % match_gener for k in grp_total_mass.keys()}
        # print('<<<<< all >>>>>')
        # # pprint(grouping)
        # grouped_mass, grouped_enth, grouped_tags = group_mass_enth(
        #     grouping, orig_mass, orig_enth,
        #     tag=str,
        #     custom_sort_key=sorted,
        #     )
        # grp_total_mass, grp_total_enth = plot_mass_enth_groups(
        #     pdf_pages, times,
        #     grouped_mass, grouped_enth, grouped_tags,
        #     title_prefix=sname,
        #     to_mass_unit=to_ktd_rev,
        #     to_enth_unit=to_kjkg,
        #     to_time_unit=partial(to_year, start_year=offset_year),
        #     )
        # print('    Final group DONE.')

        pdf_pages.close()

    return 0

if __name__ == '__main__':
    exit(main())

